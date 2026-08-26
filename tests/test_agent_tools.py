# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline checks for the two read tools and the shared grounding contract.

Everything here runs without Neo4j, without AWS, and without a network call.
The retrievers are built lazily inside `hybrid_retrieval`, so both tool
specifications can be read and both tool bodies can be driven with a stubbed
retrieval function.

What these tests are protecting is not the Python. It is the text and the shape
that a model and three modules depend on: the tool descriptions the model
routes with, the `{"status", "content"}` envelope Strands passes through
untouched, and the `answerable` / `missing_fact` verdict that Modules 4 and 5
read back out of a tool result.

Run them with:

    uv run --with pytest pytest tests/test_agent_tools.py
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from neo4j.exceptions import CypherSyntaxError
from neo4j_graphrag.exceptions import LLMGenerationError, Text2CypherRetrievalError

from workshop import agent_tools, grounding
from workshop.agent_tools import (
    PASSAGE_TOOL,
    READ_TOOLS,
    RECORD_TOOL,
    ROW_LIMIT,
    query_hotel_records,
    search_hotel_passages,
)
from workshop.workshop_utils import ToolTraceHook, selected_tool_names

PASSAGES = [
    {
        "hotel_id": "hotel-1",
        "hotel_name": "AnyCompany Cairo Nile View",
        "address": "1 Corniche El Nil, Cairo",
        "guest_rating": 4.6,
        "text": "The rooftop pool and the spa are open to all guests.",
    },
    {
        "hotel_id": "hotel-1",
        "hotel_name": "AnyCompany Cairo Nile View",
        "address": "1 Corniche El Nil, Cairo",
        "guest_rating": 4.6,
        "text": "Cancellations are free until 48 hours before arrival.",
    },
    {
        "hotel_id": "hotel-2",
        "hotel_name": "AnyCompany Paris Rive Gauche",
        "address": "9 Rue de Sevres, Paris",
        "guest_rating": 4.2,
        "text": "The hotel has a fitness room and a business center.",
    },
]

AMENITY_QUESTION = "What amenities does AnyCompany Cairo Nile View have?"
AVAILABILITY_QUESTION = "Does AnyCompany Cairo Nile View have rooms available?"


def payload(result: dict[str, Any]) -> dict[str, Any]:
    """Return the one JSON payload out of a tool result envelope."""
    assert set(result) == {"status", "content"}, result
    assert len(result["content"]) == 1, result
    return result["content"][0]["json"]


# --------------------------------------------------------------------------
# The specification the model reads
# --------------------------------------------------------------------------


def test_both_read_tools_are_registered_under_their_named_constants() -> None:
    """The constants are what the notebook and the tests route on."""
    assert [read_tool.tool_spec["name"] for read_tool in READ_TOOLS] == [
        PASSAGE_TOOL,
        RECORD_TOOL,
    ]


@pytest.mark.parametrize("read_tool", READ_TOOLS, ids=lambda t: t.tool_spec["name"])
def test_a_specification_carries_one_required_query_string(read_tool) -> None:
    schema = read_tool.tool_spec["inputSchema"]["json"]
    assert schema["required"] == ["query"]
    assert schema["properties"]["query"]["type"] == "string"


@pytest.mark.parametrize(
    ("read_tool", "other_name"),
    [(search_hotel_passages, RECORD_TOOL), (query_hotel_records, PASSAGE_TOOL)],
    ids=[PASSAGE_TOOL, RECORD_TOOL],
)
def test_a_description_names_the_other_tool_at_its_boundary(
    read_tool, other_name: str
) -> None:
    """Routing is taught in the descriptions, so each one has to point away."""
    assert other_name in read_tool.tool_spec["description"]


@pytest.mark.parametrize("read_tool", READ_TOOLS, ids=lambda t: t.tool_spec["name"])
def test_a_description_states_that_live_availability_is_unsupported(read_tool) -> None:
    assert "live room availability" in read_tool.tool_spec["description"]


def test_the_row_bound_in_the_description_matches_the_retrieval_bound() -> None:
    """A docstring cannot be an f-string, so the number is checked instead."""
    assert f"{ROW_LIMIT} rows" in query_hotel_records.tool_spec["description"]


# --------------------------------------------------------------------------
# The success envelope
# --------------------------------------------------------------------------


def test_the_passage_tool_returns_passage_evidence_beside_the_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agent_tools, "search_hotel_knowledge", lambda query: PASSAGES)
    result = search_hotel_passages(AMENITY_QUESTION)

    assert result["status"] == "success"
    body = payload(result)
    assert list(body) == [
        "ok",
        "passages",
        "hotel_ids",
        "top_result",
        "grounding_result",
    ]
    assert body["ok"] is True
    assert body["hotel_ids"] == ["hotel-1", "hotel-2"]
    assert body["top_result"] == {
        "hotel_id": "hotel-1",
        "hotel_name": "AnyCompany Cairo Nile View",
        "address": "1 Corniche El Nil, Cairo",
        "guest_rating": 4.6,
    }
    assert body["grounding_result"] == {"answerable": True, "missing_fact": None}


def test_the_structured_tool_returns_the_generated_cypher_and_its_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cypher = "MATCH (h:Hotel) RETURN avg(h.guest_rating) AS avg_rating"
    monkeypatch.setattr(
        agent_tools,
        "graph_query",
        lambda query: {"cypher": cypher, "records": [{"avg_rating": 4.4}]},
    )
    result = query_hotel_records("What is the average guest rating?")

    assert result["status"] == "success"
    body = payload(result)
    assert list(body) == ["ok", "cypher", "records", "row_count", "grounding_result"]
    assert body["cypher"] == cypher
    assert body["records"] == [{"avg_rating": 4.4}]
    assert body["row_count"] == 1
    assert body["grounding_result"] == {"answerable": True, "missing_fact": None}


def test_a_number_stays_a_number_in_the_returned_json_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `json` block is why the envelope is explicit rather than a bare dict."""
    monkeypatch.setattr(
        agent_tools,
        "graph_query",
        lambda query: {"cypher": "RETURN 1", "records": [{"hotels": 292}]},
    )
    body = payload(query_hotel_records("How many hotels are there?"))
    assert body["records"][0]["hotels"] == 292
    assert isinstance(body["records"][0]["hotels"], int)


# --------------------------------------------------------------------------
# The verdict
# --------------------------------------------------------------------------


def test_an_availability_question_is_unanswerable_even_with_rich_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The graph stores capacity, not inventory, so evidence cannot rescue this."""
    monkeypatch.setattr(agent_tools, "search_hotel_knowledge", lambda query: PASSAGES)
    body = payload(search_hotel_passages(AVAILABILITY_QUESTION))

    assert body["grounding_result"] == {
        "answerable": False,
        "missing_fact": grounding.MISSING_LIVE_AVAILABILITY,
    }
    assert body["hotel_ids"] == ["hotel-1", "hotel-2"]


def test_both_read_paths_reach_the_same_verdict_for_one_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The verdict belongs to the question and the graph, not to the retriever."""
    monkeypatch.setattr(agent_tools, "search_hotel_knowledge", lambda query: PASSAGES)
    monkeypatch.setattr(
        agent_tools,
        "graph_query",
        lambda query: {"cypher": "MATCH (h:Hotel) RETURN h.name", "records": [{"n": 1}]},
    )
    passage_verdict = payload(search_hotel_passages(AVAILABILITY_QUESTION))
    record_verdict = payload(query_hotel_records(AVAILABILITY_QUESTION))
    assert passage_verdict["grounding_result"] == record_verdict["grounding_result"]


@pytest.mark.parametrize(
    "question",
    [
        "Is a room AVAILABLE tonight?",
        "What is the current Vacancy?",
        "Show me the room inventory for next weekend.",
    ],
)
def test_availability_wording_is_matched_without_regard_to_case(question: str) -> None:
    assert grounding.asks_for_live_availability(question) is True


def test_an_ordinary_hotel_question_is_not_read_as_an_availability_question() -> None:
    assert grounding.asks_for_live_availability(AMENITY_QUESTION) is False


def test_no_records_is_a_successful_read_that_cannot_support_an_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        agent_tools,
        "graph_query",
        lambda query: {"cypher": "MATCH (h:Hotel) RETURN h", "records": []},
    )
    result = query_hotel_records("Which hotels are in Antarctica?")

    assert result["status"] == "success"
    body = payload(result)
    assert body["row_count"] == 0
    assert body["grounding_result"] == {
        "answerable": False,
        "missing_fact": grounding.MISSING_MATCHING_CONTEXT,
    }


def test_an_empty_passage_result_still_carries_the_top_result_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Module 5's controls read `top_result` unconditionally."""
    monkeypatch.setattr(agent_tools, "search_hotel_knowledge", lambda query: [])
    body = payload(search_hotel_passages("Which hotel is on the moon?"))

    assert set(body["top_result"]) == set(grounding.TOP_RESULT_FIELDS)
    assert body["hotel_ids"] == []
    assert body["grounding_result"]["missing_fact"] == grounding.MISSING_MATCHING_CONTEXT


# --------------------------------------------------------------------------
# Expected failures
# --------------------------------------------------------------------------


@pytest.mark.parametrize("read_tool", READ_TOOLS, ids=lambda t: t.tool_spec["name"])
@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_an_empty_query_is_rejected_before_any_retrieval(read_tool, query: str) -> None:
    """The generated schema can require a string. It cannot require content."""
    result = read_tool(query)
    assert result["status"] == "error"
    assert payload(result) == {
        "ok": False,
        "error_code": grounding.INVALID_QUERY,
        "error_message": "query must be a non-empty string",
    }


@pytest.mark.parametrize(
    "error",
    [
        Text2CypherRetrievalError("write query rejected by the read-only guard"),
        LLMGenerationError("the model could not write Cypher"),
        CypherSyntaxError("Unknown property name: h.availability"),
    ],
    ids=["read_only_guard", "llm_failure", "database_rejection"],
)
def test_every_expected_query_failure_becomes_one_bounded_error_result(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def raise_it(query: str) -> dict[str, Any]:
        raise error

    monkeypatch.setattr(agent_tools, "graph_query", raise_it)
    result = query_hotel_records("How many hotels have a helipad?")

    assert result["status"] == "error"
    body = payload(result)
    assert body["ok"] is False
    assert body["error_code"] == grounding.QUERY_FAILED
    assert type(error).__name__ in body["error_message"]


def test_an_unexpected_failure_is_left_to_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An outage should stay visible as an outage, not arrive as an error code."""

    def raise_it(query: str) -> dict[str, Any]:
        raise MemoryError("the container ran out of memory")

    monkeypatch.setattr(agent_tools, "graph_query", raise_it)
    with pytest.raises(MemoryError):
        query_hotel_records("How many hotels have a helipad?")


def test_a_long_driver_message_is_clipped_to_the_shared_bound() -> None:
    body = grounding.error_payload(grounding.QUERY_FAILED, "x" * 5000)
    assert len(body["error_message"]) == grounding.MAX_ERROR_CHARS


def test_a_multiline_driver_message_is_collapsed_to_one_line() -> None:
    body = grounding.error_payload(grounding.QUERY_FAILED, "line one\n  line two")
    assert body["error_message"] == "line one line two"


# --------------------------------------------------------------------------
# Reading a run back as data
# --------------------------------------------------------------------------


def turn(*tool_names: str) -> SimpleNamespace:
    """A stand-in for the `AgentResult` of a turn that used `tool_names`."""
    metrics = SimpleNamespace(tool_metrics={name: object() for name in tool_names})
    return SimpleNamespace(metrics=metrics)


def test_the_tools_a_turn_used_are_read_from_its_own_metrics() -> None:
    assert selected_tool_names(turn(RECORD_TOOL, PASSAGE_TOOL)) == sorted(
        [PASSAGE_TOOL, RECORD_TOOL]
    )


def test_a_turn_that_called_no_tool_reports_no_tools() -> None:
    """This is the whole check behind the social-turn example."""
    assert selected_tool_names(turn()) == []
    assert selected_tool_names(SimpleNamespace()) == []


def after_tool(hook: ToolTraceHook, name: str, result: dict[str, Any]) -> None:
    """Drive the hook's after-tool callback with one recorded tool call."""
    hook._after_tool(
        SimpleNamespace(
            tool_use={"name": name, "input": {"query": AVAILABILITY_QUESTION}},
            result=result,
            exception=None,
        )
    )


def test_the_trace_records_a_whole_json_payload_not_the_printed_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A verdict check reads the recorded payload, so it must not be truncated."""
    monkeypatch.setattr(agent_tools, "search_hotel_knowledge", lambda query: PASSAGES)
    result = search_hotel_passages(AVAILABILITY_QUESTION)

    hook = ToolTraceHook()
    after_tool(hook, PASSAGE_TOOL, result)
    printed = capsys.readouterr().out

    assert len(hook.calls) == 1
    call = hook.calls[0]
    assert call["name"] == PASSAGE_TOOL
    assert call["status"] == "success"
    assert call["payloads"] == [payload(result)]
    assert call["payloads"][0]["grounding_result"]["missing_fact"] == (
        grounding.MISSING_LIVE_AVAILABILITY
    )
    assert "…" in printed


def test_the_trace_reads_a_serialized_text_block_as_data_too() -> None:
    """A Gateway tool returns the same payload serialized into a text block."""
    hook = ToolTraceHook()
    after_tool(
        hook,
        RECORD_TOOL,
        {"status": "success", "content": [{"text": '{"ok": true, "row_count": 2}'}]},
    )
    assert hook.calls[0]["payloads"] == [{"ok": True, "row_count": 2}]


def test_the_trace_records_a_tool_that_raised_as_an_exception() -> None:
    hook = ToolTraceHook()
    hook._after_tool(
        SimpleNamespace(
            tool_use={"name": RECORD_TOOL, "input": {"query": "anything"}},
            result=None,
            exception=RuntimeError("boom"),
        )
    )
    assert hook.calls[0]["status"] == "exception"
    assert hook.calls[0]["payloads"] == []
