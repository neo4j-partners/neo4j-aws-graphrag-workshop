# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Module 5 AgentCore Runtime entry point.

This deployment-oriented variant carries Module 3.1's two read tools and the
reservation command into a container that AgentCore Runtime starts. It keeps
the same model-driven read-tool choice as the local lesson and adds the write
tool. Runtime also changes who holds the Neo4j credentials, where the model
call originates, and how a caller reaches the agent.

All three tools run in-process against Neo4j, and this module deliberately
holds no Gateway or MCP client. The maximum-guests rule is enforced inside the
same transaction as the write, so the reservation command stays in the process
that talks to the graph. Putting a network hop between the agent and the rule
would mean the rule is only as trustworthy as whatever answers on the other
end. Module 4 covers what a Gateway is for; this module is about the write path.

This module creates no AWS resources. `5.1_deploy.ipynb` does that.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any
from uuid import UUID

from bedrock_agentcore import BedrockAgentCoreApp
from neo4j import Driver, GraphDatabase
from reservation_command import Neo4jCommandConfig, create_reservation_request
from strands import Agent, tool
from strands.hooks.events import AfterToolCallEvent, BeforeToolCallEvent
from strands.hooks.registry import HookProvider, HookRegistry
from strands.models import BedrockModel
from workshop.agent_tools import (
    PASSAGE_TOOL,
    READ_TOOLS,
    RECORD_TOOL,
)
from workshop.aws_region import aws_region
from workshop.bedrock_providers import default_model_id
from workshop.prompts import BASE_GROUNDING_PROMPT

LOGGER = logging.getLogger(__name__)

RESERVATION_TOOL = "create_reservation"
READ_TOOL_NAMES = frozenset((PASSAGE_TOOL, RECORD_TOOL))
MAX_RECORDED_READ_RESULTS = 6

# What a recorded read result is narrowed to before it leaves the Runtime. The
# two read tools return different shapes, so this is the union of both: the
# `grounding_result` verdict both carry, the passage tool's `hotel_ids` and
# `top_result`, the structured tool's `cypher`, `records`, and `row_count`, and
# the bounded error fields. Every field here is either a short identifier, a
# verdict, or a row set the retriever already caps.
#
# `passages` is deliberately absent. Each passage carries up to
# `MAX_CONTEXT_CHARS` characters of raw hotel prose and a call returns up to
# five of them, so recording six read calls verbatim would put a few hundred
# kilobytes of text into one Runtime response. Nothing downstream reads it: the
# model already saw the prose, and the notebook checks verdicts and identifiers.
# An allowlist rather than a deny of `passages`, so a new bulky field added to
# either envelope stays out until someone puts it here on purpose.
RECORDED_READ_FIELDS = frozenset(
    (
        "ok",
        "grounding_result",
        "hotel_ids",
        "top_result",
        "cypher",
        "records",
        "row_count",
        "error_code",
        "error_message",
    )
)

SYSTEM_PROMPT = f"""
{BASE_GROUNDING_PROMPT}

You can also create a reservation request. {RESERVATION_TOOL} validates policy
and records a request. It does not reserve inventory, take payment, or confirm
a booking.

Reservation rules:
- Before {RESERVATION_TOOL}, call {PASSAGE_TOOL} and pass only a stable
  hotel_id from that passage result to the command.
- {RECORD_TOOL} cannot verify a booking identity. If you use it to choose a
  hotel, call {PASSAGE_TOOL} for that hotel before the write.
- Use the caller-provided request ID exactly. Never invent or alter one.
- Never silently reduce the guest count or change dates. Make every policy
  rejection visible and ask the caller for a corrected request.
- Never claim that availability is guaranteed or that a booking is complete.
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
    """Bind writes to the caller UUID and a passage-grounded hotel ID.

    The request ID is the idempotency key for the write, so a model free to
    invent one turns a safe retry into a second reservation. The rule is
    enforced here rather than in the prompt because a prompt is guidance and
    this is a constraint. The hotel ID follows the same rule: only the passage
    tool can establish a stable booking identity, including when a structured
    lookup chose the hotel first.
    """

    def __init__(self, request_id: str | None) -> None:
        self.request_id = request_id
        self.verified_hotel_ids: set[str] = set()

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeToolCallEvent, self._validate)
        registry.add_callback(AfterToolCallEvent, self._record_hotel_ids)

    def _record_hotel_ids(self, event: AfterToolCallEvent) -> None:
        tool_use = event.tool_use or {}
        if tool_use.get("name") != PASSAGE_TOOL:
            return
        payload = _tool_payload(event.result)
        if payload is None or payload.get("ok") is not True:
            return
        hotel_ids = payload.get("hotel_ids")
        if not isinstance(hotel_ids, list):
            return
        self.verified_hotel_ids.update(
            hotel_id for hotel_id in hotel_ids if isinstance(hotel_id, str) and hotel_id
        )

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
        elif parameters.get("hotel_id") not in self.verified_hotel_ids:
            event.cancel_tool = (
                f"BLOCKED: Call {PASSAGE_TOOL} first and use one of the stable "
                "hotel_id values returned by that passage result."
            )


def _tool_payload(result: Any) -> dict[str, Any] | None:
    """Parse a tool's own JSON response out of a Strands tool result.

    The shared read tools return native JSON blocks. The reservation tool
    returns a JSON string, which Strands wraps in a text block. A block that
    does not parse is skipped rather than coerced, because the two outcomes
    this has to tell apart are "the rule in the graph refused it" and
    "something broke between the agent and the graph." A parse failure
    reshaped into a verdict makes the second look like the first.
    """
    blocks = result.get("content") or [] if isinstance(result, dict) else []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        native_json = block.get("json")
        if isinstance(native_json, dict):
            return native_json
        text = block.get("text")
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
    """Keep bounded structured results so `invoke` can return them.

    Without this the verdict is computed against the graph, read by the model,
    and then leaves the Runtime only as prose. `tools_used` records that a call
    was attempted, so a cancelled call, a rejected write, and a Neo4j outage all
    look identical from outside. This is what separates them.

    Bounded in two directions. `max_results` caps how many results are kept,
    oldest dropped first. `fields`, when given, caps how large each kept result
    is by narrowing the tool's envelope to that allowlist of top-level keys,
    which is what keeps a recorder of text-carrying tools from turning the
    Runtime response into a transcript of the corpus.
    """

    def __init__(
        self,
        tool_names: str | frozenset[str],
        *,
        fields: frozenset[str] | None = None,
        max_results: int = 1,
        include_tool_name: bool = False,
    ) -> None:
        self.tool_names = (
            frozenset((tool_names,)) if isinstance(tool_names, str) else tool_names
        )
        self.fields = fields
        self.max_results = max_results
        self.include_tool_name = include_tool_name
        self.results: list[dict[str, Any]] = []

    @property
    def last_result(self) -> dict[str, Any] | None:
        return self.results[-1] if self.results else None

    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(AfterToolCallEvent, self._record)

    def _record(self, event: AfterToolCallEvent) -> None:
        tool_use = event.tool_use or {}
        tool_name = tool_use.get("name")
        if tool_name not in self.tool_names:
            return
        payload = _tool_payload(event.result)
        if payload is None:
            return
        if self.fields is not None:
            payload = {
                name: value for name, value in payload.items() if name in self.fields
            }
        if self.include_tool_name:
            payload = {"tool_name": tool_name, **payload}
        self.results.append(payload)
        if len(self.results) > self.max_results:
            del self.results[0]


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

    The returned `grounding_results` and `command_result` are the tools' own
    structured results. They let a caller assert on evidence and graph
    behaviour rather than on the model's prose, which is the difference between
    a test that fails when the write breaks and one that fails when the model
    rephrases.

    `grounding_results` holds at most `MAX_RECORDED_READ_RESULTS` read results,
    each narrowed to `RECORDED_READ_FIELDS`: the verdict plus the evidence
    identifiers. The raw passage text the model read is not part of the
    response. `command_result` is the reservation response contract in full.
    """
    del context
    prompt, request_id = _prompt(payload)
    correlation_id = request_id or "retrieval-only"
    LOGGER.info("runtime_invocation_started request_id=%s", correlation_id)

    grounding_recorder = ToolResultRecorder(
        READ_TOOL_NAMES,
        fields=RECORDED_READ_FIELDS,
        max_results=MAX_RECORDED_READ_RESULTS,
        include_tool_name=True,
    )
    command_recorder = ToolResultRecorder(RESERVATION_TOOL)
    try:
        # One definition of the model id, in the shared package, honouring the
        # same MODEL_ID override every module reads. Restating the literal here
        # would put a second copy in the tree, and the copy that drifts is the
        # one that decides what the deployed agent runs on.
        # Model id and region only. Module 3.1 builds its `BedrockModel` with
        # exactly these two arguments, so the deployed agent runs the same
        # model on the same defaults as the lesson it is packaging. A sampling
        # parameter set here and not there would make a routing difference
        # between the two look like something the deployment caused.
        model = BedrockModel(
            model_id=default_model_id(),
            region_name=aws_region(),
        )
        # The same two automatic-choice read tools as Module 3, plus the write
        # command whose guard requires passage-grounded identity first.
        hotel_agent = Agent(
            name="hotel_agent",
            model=model,
            tools=[*READ_TOOLS, create_reservation],
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
        "grounding_results": grounding_recorder.results,
        "command_result": command_result,
    }


if __name__ == "__main__":
    app.run()
