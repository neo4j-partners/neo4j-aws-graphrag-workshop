# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Module 5 AgentCore Runtime entry point.

The same grounded booking agent Module 3.1 runs in a notebook kernel, with the
same two tools and the same rules, moved into a container that AgentCore
Runtime starts. Nothing about how the agent reasons changes here. What changes
is who holds the Neo4j credentials, where the model call originates, and
whether a caller can reach the agent without a Python interpreter.

Both tools run in-process against Neo4j, and this module deliberately holds no
Gateway or MCP client. The maximum-guests rule is enforced inside the same
transaction as the write, so the reservation command stays in the process that
talks to the graph. Putting a network hop between the agent and the rule would
mean the rule is only as trustworthy as whatever answers on the other end.
Module 4 covers what a Gateway is for; this module is about the write path.

This module creates no AWS resources. `5.1_deploy.ipynb` does that.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any
from uuid import UUID

from bedrock_agentcore import BedrockAgentCoreApp
from neo4j import Driver, GraphDatabase
from strands import Agent, tool
from strands.hooks.events import AfterToolCallEvent, BeforeToolCallEvent
from strands.hooks.registry import HookProvider, HookRegistry
from strands.models import BedrockModel

from reservation_command import Neo4jCommandConfig, create_reservation_request
from workshop.aws_region import aws_region
from workshop.bedrock_providers import default_model_id
from workshop.hybrid_retrieval import (
    GROUNDING_INSTRUCTIONS,
    search_hotel_knowledge as _search_hotel_knowledge,
)

LOGGER = logging.getLogger(__name__)

RESERVATION_TOOL = "create_reservation"
RETRIEVAL_TOOL = "search_hotel_knowledge"

SYSTEM_PROMPT = f"""
You are a grounded hotel-information and reservation-request assistant.

You have exactly two tools:
- {RETRIEVAL_TOOL} searches hotel evidence and returns a stable hotel ID.
- {RESERVATION_TOOL} validates policy and records a request. It does not
  reserve inventory, take payment, or confirm a booking.

Rules:
- Use {RETRIEVAL_TOOL} before creating any reservation request.
- Treat the tool's grounding_result as binding. When answerable is false,
  explain the missing fact and do not infer an answer from related evidence.
- Pass only a stable hotel ID returned by that search to the command.
- Use the caller-provided request ID exactly. Never invent or alter one.
- Never silently reduce the guest count or change dates. Make every policy
  rejection visible and ask the caller for a corrected request.
- Never claim that availability is guaranteed or that a booking is complete.

{GROUNDING_INSTRUCTIONS}
""".strip()

app = BedrockAgentCoreApp()


@lru_cache(maxsize=1)
def _command_driver() -> tuple[Driver, str]:
    """Open the reservation command's Neo4j driver once per container.

    Cached because AgentCore Runtime keeps a warm container across invocations,
    and a driver opened per request leaks a connection pool per request. The
    retrieval path caches its own driver the same way inside
    `hybrid_retrieval`, so the two halves of this agent hold one pool each
    rather than one pool per question asked.

    Raises at first use rather than at import. An import-time raise kills the
    container during startup, which AgentCore reports as a failed deployment
    with no application log line explaining which variable was missing.
    """
    config = Neo4jCommandConfig.from_environment()
    driver = GraphDatabase.driver(config.uri, auth=(config.username, config.password))
    return driver, config.database


class ReservationRequestGuard(HookProvider):
    """Bind reservation tool calls to the caller's correlation UUID.

    The request ID is the idempotency key for the write, so a model free to
    invent one turns a safe retry into a second reservation. The rule is
    enforced here rather than in the prompt because a prompt is guidance and
    this is a constraint.
    """

    def __init__(self, request_id: str | None) -> None:
        self.request_id = request_id

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeToolCallEvent, self._validate)

    def _validate(self, event: BeforeToolCallEvent) -> None:
        tool_use = event.tool_use
        if tool_use.get("name") != RESERVATION_TOOL:
            return
        parameters = tool_use.get("input") or {}
        if self.request_id is None:
            event.cancel_tool = (
                "BLOCKED: A caller-provided request_id is required for the "
                "reservation command."
            )
        elif parameters.get("request_id") != self.request_id:
            event.cancel_tool = (
                "BLOCKED: The reservation command must use the caller-provided "
                "request_id unchanged."
            )


def _tool_payload(result: Any) -> dict[str, Any] | None:
    """Parse a tool's own JSON response out of a Strands tool result.

    Both tools return JSON strings, and Strands wraps them in content blocks.
    A block that does not parse is skipped rather than coerced, because the two
    outcomes this has to tell apart are "the rule in the graph refused it" and
    "something broke between the agent and the graph." A parse failure reshaped
    into a verdict makes the second look like the first.
    """
    blocks = result.get("content") or [] if isinstance(result, dict) else []
    for block in blocks:
        text = block.get("text") if isinstance(block, dict) else None
        if not isinstance(text, str):
            continue
        try:
            parsed = json.loads(text)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


class ToolResultRecorder(HookProvider):
    """Keep one tool's structured verdict so `invoke` can return it.

    Without this the verdict is computed against the graph, read by the model,
    and then leaves the Runtime only as prose. `tools_used` records that a call
    was attempted, so a cancelled call, a rejected write, and a Neo4j outage all
    look identical from outside. This is what separates them.
    """

    def __init__(self, tool_name: str, key: str | None = None) -> None:
        self.tool_name = tool_name
        self.key = key
        self.last_result: dict[str, Any] | None = None

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self._record)

    def _record(self, event: AfterToolCallEvent) -> None:
        tool_use = event.tool_use or {}
        if tool_use.get("name") != self.tool_name:
            return
        payload = _tool_payload(event.result)
        if payload is None:
            self.last_result = None
        elif self.key is None:
            self.last_result = payload
        else:
            nested = payload.get(self.key)
            self.last_result = nested if isinstance(nested, dict) else None


def _grounding_result(
    query: str,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Describe whether bounded hotel evidence can answer the question.

    The graph holds hotel knowledge, not live inventory, so a question about
    availability is unanswerable no matter how much evidence came back. That
    case is decided here rather than left to the model, because a model looking
    at a rich evidence record will reliably find something to say.
    """
    normalized_query = query.casefold()
    asks_for_live_availability = any(
        term in normalized_query
        for term in ("availability", "available", "vacancy", "vacancies", "inventory")
    )
    evidence_ids = list(
        dict.fromkeys(
            item["hotel_id"]
            for item in evidence
            if isinstance(item.get("hotel_id"), str) and item["hotel_id"]
        )
    )
    supported_facts = [
        fact
        for fact, field in (
            ("hotel_identity", "hotel_id"),
            ("hotel_address", "address"),
            ("guest_rating", "guest_rating"),
            ("amenities", "amenities"),
        )
        if any(item.get(field) not in (None, "", []) for item in evidence)
    ]

    if asks_for_live_availability:
        answerable = False
        missing_fact = "live_room_availability"
    else:
        answerable = bool(evidence)
        missing_fact = None if answerable else "matching_hotel_evidence"

    # The top hit's checkable fields travel back to the caller alongside the
    # verdict. A refusal and a dead index look identical from outside: both
    # produce no answer. A test can only tell them apart if some real, specific
    # value from the graph crosses this boundary, so every verdict carries one.
    top = evidence[0] if evidence else {}
    top_evidence = {
        field: top.get(field)
        for field in ("hotel_id", "hotel_name", "address", "guest_rating")
    }

    return {
        "answerable": answerable,
        "supported_facts": supported_facts,
        "missing_fact": missing_fact,
        "evidence_ids": evidence_ids,
        "top_evidence": top_evidence,
    }


@tool(name=RETRIEVAL_TOOL)
def search_hotel_knowledge(query: str) -> str:
    """Search bounded hotel evidence and graph-enriched facts.

    Use this before answering hotel questions or creating a reservation
    request. The returned hotel_id is the only hotel identity accepted by the
    reservation command. Results do not represent live room availability.

    Args:
        query: Natural-language hotel question.

    Returns:
        JSON containing the unchanged bounded evidence records and a structured
        answerability verdict.
    """
    evidence = _search_hotel_knowledge(query)
    return json.dumps(
        {
            "evidence": evidence,
            "grounding_result": _grounding_result(query, evidence),
        },
        ensure_ascii=False,
    )


@tool(name=RESERVATION_TOOL)
def create_reservation(
    request_id: str,
    hotel_id: str,
    check_in: str,
    check_out: str,
    guests: int,
) -> str:
    """Validate and record one reservation request against the graph.

    This does not confirm a booking or reserve room availability. The maximum
    guest rule lives in Neo4j and is enforced inside the same transaction as
    the write, so an over-limit request is rejected with nothing written.

    Args:
        request_id: Caller-created UUID. Reuse it if this command is retried.
        hotel_id: Opaque stable hotel ID returned by grounded retrieval.
        check_in: Check-in date in YYYY-MM-DD format.
        check_out: Check-out date in YYYY-MM-DD format.
        guests: Requested number of guests.

    Returns:
        JSON carrying the frozen reservation response contract: status,
        reason_code, duplicate, and the recorded request.
    """
    driver, database = _command_driver()
    response = create_reservation_request(
        {
            "request_id": request_id,
            "hotel_id": hotel_id,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
        },
        driver=driver,
        database=database,
    )
    return json.dumps(response, ensure_ascii=False, default=str)


def _request_id(payload: dict[str, Any]) -> str | None:
    """Return the caller's correlation UUID, rejecting anything non-canonical.

    Canonical form is checked, not just parseability. `UUID` accepts a braced
    or hyphen-free string and normalizes it, so a caller correlating on the
    text they sent would find a different string in the graph and conclude the
    write never landed.
    """
    value = payload.get("request_id")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("request_id must be a UUID string")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError("request_id must be a valid UUID") from error
    if str(parsed) != value:
        raise ValueError("request_id must use canonical UUID format")
    return str(parsed)


def _prompt(payload: str | dict[str, Any]) -> tuple[str, str | None]:
    """Accept either a bare prompt string or the full request object."""
    if isinstance(payload, str):
        return _require_prompt(payload), None
    if isinstance(payload, dict):
        raw_prompt = payload.get("prompt")
        prompt = raw_prompt if isinstance(raw_prompt, str) else ""
        return _require_prompt(prompt), _request_id(payload)
    raise ValueError("payload must be a prompt string or object")


def _require_prompt(value: str) -> str:
    prompt = value.strip()
    if not prompt:
        raise ValueError("payload must include a non-empty prompt")
    return prompt


def _tools_used(result: Any) -> list[str]:
    metrics = getattr(result, "metrics", None)
    tool_metrics = getattr(metrics, "tool_metrics", None)
    return list(tool_metrics) if isinstance(tool_metrics, dict) else []


@app.entrypoint
def invoke(
    payload: str | dict[str, Any],
    context: Any | None = None,
) -> dict[str, Any]:
    """Handle one isolated Runtime invocation.

    `request_id` is optional for retrieval-only questions and required before
    the agent may create a reservation request.

    The returned `grounding_result` and `command_result` are the tools' own
    structured verdicts. They let a caller assert on evidence and graph
    behaviour rather than on the model's prose, which is the difference between
    a test that fails when the write breaks and one that fails when the model
    rephrases.
    """
    del context
    prompt, request_id = _prompt(payload)
    correlation_id = request_id or "retrieval-only"
    LOGGER.info("runtime_invocation_started request_id=%s", correlation_id)

    grounding_recorder = ToolResultRecorder(RETRIEVAL_TOOL, key="grounding_result")
    command_recorder = ToolResultRecorder(RESERVATION_TOOL)
    try:
        # One definition of the model id, in the shared package, honouring the
        # same MODEL_ID override every module reads. Restating the literal here
        # would put a second copy in the tree, and the copy that drifts is the
        # one that decides what the deployed agent runs on.
        # No `temperature`. The shared workshop model is claude-sonnet-5, which
        # rejects the parameter with "`temperature` is deprecated for this
        # model." Module 3.1 uses the same shared model ID and also omits the
        # parameter.
        model = BedrockModel(
            model_id=default_model_id(),
            region_name=aws_region(),
        )
        # Same grounded booking agent Module 3.1 built. Only its runtime changes.
        hotel_agent = Agent(
            name="hotel_agent",
            model=model,
            tools=[search_hotel_knowledge, create_reservation],
            system_prompt=SYSTEM_PROMPT,
            hooks=[
                ReservationRequestGuard(request_id),
                grounding_recorder,
                command_recorder,
            ],
        )
        caller_context = (
            f"\n\nCaller request ID: {request_id}" if request_id is not None else ""
        )
        result = hotel_agent(f"{prompt}{caller_context}")
    except Exception as error:
        # Type only, never the message. A Neo4j driver error carries the URI
        # and sometimes the credential that failed, and this line lands in a
        # CloudWatch log group with broader read access than the .env it came
        # from.
        LOGGER.error(
            "runtime_invocation_failed request_id=%s error_type=%s",
            correlation_id,
            type(error).__name__,
        )
        raise

    tools_used = _tools_used(result)
    command_result = command_recorder.last_result
    LOGGER.info(
        "runtime_invocation_completed request_id=%s tools_used=%s command_status=%s",
        correlation_id,
        ",".join(tools_used) or "none",
        (command_result or {}).get("status", "none"),
    )
    return {
        "response": str(result),
        "request_id": request_id,
        "tools_used": tools_used,
        "grounding_result": grounding_recorder.last_result,
        "command_result": command_result,
    }


if __name__ == "__main__":
    app.run()
