# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline behavior checks for the Module 5 AgentCore Runtime controls."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from strands.hooks.events import AfterToolCallEvent, BeforeToolCallEvent
from strands.hooks.registry import HookRegistry
from workshop.agent_tools import PASSAGE_TOOL, READ_TOOLS, RECORD_TOOL
from workshop.prompts import BASE_GROUNDING_PROMPT

RUNTIME_PATH = (
    Path(__file__).resolve().parents[1]
    / "notebooks"
    / "05-agentcore-deploy"
    / "runtime_app"
    / "booking_agent.py"
)


def _load_runtime_module():
    """Load the tracked Runtime without depending on its staged command copy."""
    reservation_command = ModuleType("reservation_command")
    missing = object()
    previous = sys.modules.get("reservation_command", missing)

    class Neo4jCommandConfig:
        @classmethod
        def from_environment(cls):
            raise AssertionError("the offline tests must not open Neo4j")

    reservation_command.Neo4jCommandConfig = Neo4jCommandConfig
    reservation_command.create_reservation_request = lambda *args, **kwargs: None
    try:
        sys.modules["reservation_command"] = reservation_command
        spec = importlib.util.spec_from_file_location(
            "module5_booking_agent", RUNTIME_PATH
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if previous is missing:
            del sys.modules["reservation_command"]
        else:
            sys.modules["reservation_command"] = previous
    return module


@pytest.fixture(scope="module")
def runtime():
    return _load_runtime_module()


def _after_event(tool_name: str, payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        tool_use={"name": tool_name},
        result={"status": "success", "content": [{"json": payload}]},
    )


def _before_reservation(
    runtime,
    request_id: str,
    hotel_id: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        tool_use={
            "name": runtime.RESERVATION_TOOL,
            "input": {"request_id": request_id, "hotel_id": hotel_id},
        },
        cancel_tool=None,
    )


# The two helpers below build the real Strands events and dispatch them through
# a real `HookRegistry`, so what they exercise is the wiring in
# `register_hooks` rather than a hand-called private method. Both event
# dataclasses construct offline: nothing here touches Bedrock, Neo4j, or the
# network.


def _dispatch_after(
    registry: HookRegistry,
    tool_name: str,
    payload: dict[str, Any],
) -> AfterToolCallEvent:
    event = AfterToolCallEvent(
        agent=None,
        selected_tool=None,
        tool_use={"name": tool_name, "input": {}},
        invocation_state={},
        result={"status": "success", "content": [{"json": payload}]},
    )
    registry.invoke_callbacks(event)
    return event


def _dispatch_before_reservation(
    registry: HookRegistry,
    runtime,
    request_id: str,
    hotel_id: str,
) -> BeforeToolCallEvent:
    event = BeforeToolCallEvent(
        agent=None,
        selected_tool=None,
        tool_use={
            "name": runtime.RESERVATION_TOOL,
            "input": {"request_id": request_id, "hotel_id": hotel_id},
        },
        invocation_state={},
    )
    registry.invoke_callbacks(event)
    return event


def _passage_payload(hotel_id: str, chunk_text: str) -> dict[str, Any]:
    """A passage envelope shaped like `workshop.grounding.passage_payload`."""
    return {
        "ok": True,
        "passages": [
            {
                "hotel_id": hotel_id,
                "hotel_name": "Hero Hotel",
                "address": "1 Hero Street",
                "guest_rating": 4.5,
                "chunk_text": chunk_text,
            }
        ],
        "hotel_ids": [hotel_id],
        "top_result": {
            "hotel_id": hotel_id,
            "hotel_name": "Hero Hotel",
            "address": "1 Hero Street",
            "guest_rating": 4.5,
        },
        "grounding_result": {"answerable": True, "missing_fact": None},
    }


def test_runtime_reuses_the_shared_prompt_and_both_read_tools(runtime) -> None:
    assert BASE_GROUNDING_PROMPT in runtime.SYSTEM_PROMPT
    assert runtime.READ_TOOL_NAMES == frozenset((PASSAGE_TOOL, RECORD_TOOL))
    assert tuple(READ_TOOLS) == tuple(runtime.READ_TOOLS)
    assert PASSAGE_TOOL in runtime.SYSTEM_PROMPT
    assert RECORD_TOOL in runtime.SYSTEM_PROMPT


def test_write_requires_the_id_from_passage_evidence_even_after_records(
    runtime,
) -> None:
    request_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    hotel_id = "hotel-from-structured-row"
    guard = runtime.ReservationRequestGuard(request_id)

    guard._record_hotel_ids(
        _after_event(
            RECORD_TOOL,
            {
                "ok": True,
                "records": [{"hotel_id": hotel_id}],
                "grounding_result": {"answerable": True, "missing_fact": None},
            },
        )
    )
    blocked = _before_reservation(runtime, request_id, hotel_id)
    guard._validate(blocked)
    assert PASSAGE_TOOL in blocked.cancel_tool

    guard._record_hotel_ids(
        _after_event(
            PASSAGE_TOOL,
            {
                "ok": True,
                "hotel_ids": [hotel_id],
                "grounding_result": {"answerable": True, "missing_fact": None},
            },
        )
    )
    allowed = _before_reservation(runtime, request_id, hotel_id)
    guard._validate(allowed)
    assert allowed.cancel_tool is None


def test_failed_passage_result_does_not_authorize_a_write(runtime) -> None:
    request_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    guard = runtime.ReservationRequestGuard(request_id)
    guard._record_hotel_ids(
        _after_event(
            PASSAGE_TOOL,
            {"ok": False, "hotel_ids": ["invented-id"], "error_code": "failed"},
        )
    )

    event = _before_reservation(runtime, request_id, "invented-id")
    guard._validate(event)
    assert event.cancel_tool is not None


def test_guard_register_hooks_wires_the_write_gate(runtime) -> None:
    """Delete either `add_callback` in `ReservationRequestGuard` and this fails.

    Every other guard test calls `_validate` and `_record_hotel_ids` directly,
    so all of them stay green against a provider that registers nothing. This
    one goes through `HookRegistry.add_hook`, which is the only caller of
    `register_hooks` in production.
    """
    request_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    hotel_id = "hotel-from-passage"
    registry = HookRegistry()
    registry.add_hook(runtime.ReservationRequestGuard(request_id))

    # Nothing has been retrieved yet, so the BeforeToolCallEvent callback has
    # to cancel this write. An unregistered `_validate` leaves it None.
    blocked = _dispatch_before_reservation(registry, runtime, request_id, hotel_id)
    assert blocked.cancel_tool, "the write gate did not run on BeforeToolCallEvent"

    # Now the AfterToolCallEvent callback has to see the passage result, or the
    # same write stays blocked forever.
    _dispatch_after(registry, PASSAGE_TOOL, _passage_payload(hotel_id, "prose"))
    allowed = _dispatch_before_reservation(registry, runtime, request_id, hotel_id)
    assert allowed.cancel_tool is False, (
        "passage evidence never reached the guard on AfterToolCallEvent"
    )


def test_recorder_register_hooks_wires_the_result_capture(runtime) -> None:
    """Delete the `add_callback` in `ToolResultRecorder` and this fails."""
    registry = HookRegistry()
    recorder = runtime.ToolResultRecorder(RECORD_TOOL)
    registry.add_hook(recorder)

    payload = {"status": "accepted", "reason_code": None}
    _dispatch_after(registry, RECORD_TOOL, payload)

    assert recorder.last_result == payload


def test_recorded_read_result_drops_passage_text_and_keeps_the_verdict(
    runtime,
) -> None:
    """The Runtime response carries the verdict and identifiers, not the prose."""
    prose = "Rooftop pool prose that the model read and the caller does not need."
    hotel_id = "hotel-from-passage"
    recorder = runtime.ToolResultRecorder(
        runtime.READ_TOOL_NAMES,
        fields=runtime.RECORDED_READ_FIELDS,
        max_results=runtime.MAX_RECORDED_READ_RESULTS,
        include_tool_name=True,
    )
    recorder._record(_after_event(PASSAGE_TOOL, _passage_payload(hotel_id, prose)))
    recorder._record(
        _after_event(
            RECORD_TOOL,
            {
                "ok": True,
                "cypher": "MATCH (h:Hotel) RETURN count(h)",
                "records": [{"count": 3}],
                "row_count": 1,
                "grounding_result": {"answerable": True, "missing_fact": None},
            },
        )
    )

    passage, structured = recorder.results
    assert "passages" not in passage, passage
    assert prose not in json.dumps(recorder.results), recorder.results

    # The verdict and the checkable identifiers still cross the boundary.
    assert passage["grounding_result"] == {"answerable": True, "missing_fact": None}
    assert passage["hotel_ids"] == [hotel_id]
    assert passage["top_result"]["hotel_id"] == hotel_id
    assert structured["cypher"].startswith("MATCH")
    assert structured["records"] == [{"count": 3}]
    assert structured["row_count"] == 1


def test_read_recorder_keeps_bounded_results_from_both_tools(runtime) -> None:
    recorder = runtime.ToolResultRecorder(
        runtime.READ_TOOL_NAMES,
        max_results=2,
        include_tool_name=True,
    )
    verdict = {"answerable": True, "missing_fact": None}
    recorder._record(
        _after_event(PASSAGE_TOOL, {"ok": True, "grounding_result": verdict})
    )
    recorder._record(
        _after_event(RECORD_TOOL, {"ok": True, "grounding_result": verdict})
    )
    recorder._record(
        _after_event(PASSAGE_TOOL, {"ok": True, "grounding_result": verdict})
    )

    assert len(recorder.results) == 2
    assert [item["tool_name"] for item in recorder.results] == [
        RECORD_TOOL,
        PASSAGE_TOOL,
    ]
    assert all(item["grounding_result"] == verdict for item in recorder.results)


def test_tool_payload_accepts_native_json_and_text_json(runtime) -> None:
    native = {"ok": True, "records": [{"average": 4.2}]}
    assert runtime._tool_payload({"content": [{"json": native}]}) == native
    assert runtime._tool_payload({"content": [{"text": '{"status": "accepted"}'}]}) == {
        "status": "accepted"
    }


def test_invoke_registers_three_tools_and_returns_plural_read_results(
    runtime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    verdict = {"answerable": True, "missing_fact": None}

    class Result:
        metrics = SimpleNamespace(tool_metrics={RECORD_TOOL: {}})

        def __str__(self) -> str:
            return "The average rating is 4.2."

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def __call__(self, prompt: str) -> Result:
            event = _after_event(
                RECORD_TOOL,
                {
                    "ok": True,
                    "cypher": "MATCH (h:Hotel) RETURN avg(h.guest_rating)",
                    "records": [{"average": 4.2}],
                    "row_count": 1,
                    "grounding_result": verdict,
                },
            )
            for hook in captured["hooks"]:
                record = getattr(hook, "_record", None)
                if record is not None:
                    record(event)
            return Result()

    monkeypatch.setattr(runtime, "Agent", FakeAgent)
    monkeypatch.setattr(runtime, "BedrockModel", lambda **kwargs: object())
    monkeypatch.setattr(runtime, "default_model_id", lambda: "test-model")
    monkeypatch.setattr(runtime, "aws_region", lambda: "us-east-1")

    response = runtime.invoke("What is the average rating in Paris?")

    assert [item.tool_spec["name"] for item in captured["tools"]] == [
        PASSAGE_TOOL,
        RECORD_TOOL,
        runtime.RESERVATION_TOOL,
    ]
    assert "grounding_result" not in response
    assert response["grounding_results"] == [
        {
            "tool_name": RECORD_TOOL,
            "ok": True,
            "cypher": "MATCH (h:Hotel) RETURN avg(h.guest_rating)",
            "records": [{"average": 4.2}],
            "row_count": 1,
            "grounding_result": verdict,
        }
    ]
