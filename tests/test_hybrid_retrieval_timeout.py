# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline checks for the wall-clock bound on `graph_query`.

`graph_query` runs model-generated Cypher, so a query that plans badly can run
far longer than anyone waiting on it is willing to wait. These tests pin the
bound and, just as importantly, pin where the failure lands: a timeout has to
arrive as a member of `EXPECTED_QUERY_ERRORS`, because that is the tuple the
Module 3 Strands tool and the Module 4 record Lambda catch. Anything outside it
reaches a caller as an unhandled failure, which in the Lambda is a 500.

Nothing here touches Neo4j, AWS, or a network. The retriever is faked and the
bound is shortened, so the slow case fails in a fraction of a second.

Run them with:

    uv run --with pytest pytest tests/test_hybrid_retrieval_timeout.py
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from types import SimpleNamespace
from typing import Any, Iterator

import pytest
from neo4j_graphrag.exceptions import Text2CypherRetrievalError
from workshop import agent_tools, grounding, hybrid_retrieval

CYPHER = "MATCH (hotel:Hotel) RETURN count(hotel) AS hotel_count"
QUESTION = "How many hotels are in the graph?"

# Short enough to keep the suite fast, long enough that a machine under load
# does not trip it on the fast case.
TEST_TIMEOUT_SECONDS = 0.25

# How long the slow fake would run if nothing stopped it. Well past
# TEST_TIMEOUT_SECONDS, so a `graph_query` that returned in less than this had
# to have given up on its own.
SLOW_CALL_SECONDS = 30.0


def fake_result(records: list[dict[str, Any]]) -> SimpleNamespace:
    """Build the shape `Text2CypherRetriever.search` returns."""
    return SimpleNamespace(
        items=[SimpleNamespace(content=record) for record in records],
        metadata={"cypher": CYPHER},
    )


class FakeRetriever:
    """A `Text2CypherRetriever` stand-in whose `search` can be made slow.

    The slow call blocks on an event rather than sleeping so the test can
    release the stranded worker thread as soon as the assertion is done. The
    thread is stranded on purpose: the bound is wall clock, so the work it is
    waiting on is still running, exactly as a real query would still be running
    on the server.
    """

    def __init__(self, *, released: threading.Event, block: bool) -> None:
        self.released = released
        self.block = block
        self.calls: list[str] = []

    def search(self, query_text: str) -> SimpleNamespace:
        self.calls.append(query_text)
        if self.block:
            self.released.wait(timeout=SLOW_CALL_SECONDS)
        return fake_result([{"hotel_count": 300}])


@pytest.fixture
def released() -> Iterator[threading.Event]:
    """Release any stranded worker thread when the test finishes."""
    event = threading.Event()
    try:
        yield event
    finally:
        event.set()


def install(
    monkeypatch: pytest.MonkeyPatch,
    retriever: FakeRetriever,
    *,
    timeout: float | None = None,
) -> None:
    """Point `graph_query` at a fake retriever, optionally shortening the bound."""
    monkeypatch.setattr(
        hybrid_retrieval, "_get_graph_query_retriever", lambda: retriever
    )
    if timeout is not None:
        monkeypatch.setattr(
            hybrid_retrieval, "GRAPH_QUERY_TIMEOUT_SECONDS", timeout
        )


# --------------------------------------------------------------------------
# The bound itself
# --------------------------------------------------------------------------


def test_shipped_bound_is_a_positive_number_of_seconds() -> None:
    bound = hybrid_retrieval.GRAPH_QUERY_TIMEOUT_SECONDS
    assert isinstance(bound, (int, float)) and not isinstance(bound, bool)
    # An aggregate over the workshop's roughly 300 hotels answers in
    # milliseconds and the nested model call adds a few seconds, so a bound
    # outside this range is either useless or no longer a bound.
    assert 5 <= bound <= 60


def test_a_call_that_runs_past_the_bound_stops_waiting(
    monkeypatch: pytest.MonkeyPatch, released: threading.Event
) -> None:
    retriever = FakeRetriever(released=released, block=True)
    install(monkeypatch, retriever, timeout=TEST_TIMEOUT_SECONDS)

    started = time.monotonic()
    with pytest.raises(Text2CypherRetrievalError) as raised:
        hybrid_retrieval.graph_query(QUESTION)
    elapsed = time.monotonic() - started

    # Returning long before SLOW_CALL_SECONDS is what proves the bound is wired
    # up. It also catches shutting the executor down with wait=True, which
    # would block until the slow call finished and undo the timeout.
    assert elapsed < SLOW_CALL_SECONDS / 2
    assert retriever.calls == [QUESTION]
    assert isinstance(raised.value.__cause__, FutureTimeoutError)
    assert str(TEST_TIMEOUT_SECONDS) in str(raised.value)


def test_a_timeout_is_one_of_the_expected_query_errors(
    monkeypatch: pytest.MonkeyPatch, released: threading.Event
) -> None:
    """The tuple both callers catch has to cover the timeout.

    `workshop.agent_tools` and the Module 4 record Lambda both import
    `EXPECTED_QUERY_ERRORS` from `hybrid_retrieval` and catch exactly it. A
    timeout outside the tuple would propagate as an unhandled failure.
    """
    install(
        monkeypatch,
        FakeRetriever(released=released, block=True),
        timeout=TEST_TIMEOUT_SECONDS,
    )

    with pytest.raises(hybrid_retrieval.EXPECTED_QUERY_ERRORS):
        hybrid_retrieval.graph_query(QUESTION)


def test_the_record_tool_turns_a_timeout_into_a_bounded_error_payload(
    monkeypatch: pytest.MonkeyPatch, released: threading.Event
) -> None:
    install(
        monkeypatch,
        FakeRetriever(released=released, block=True),
        timeout=TEST_TIMEOUT_SECONDS,
    )

    result = agent_tools.query_hotel_records(QUESTION)

    assert result["status"] == "error"
    payload = result["content"][0]["json"]
    assert payload["ok"] is False
    assert payload["error_code"] == grounding.QUERY_FAILED


# --------------------------------------------------------------------------
# The healthy call the bound must not touch
# --------------------------------------------------------------------------


def test_a_call_inside_the_bound_returns_normally(
    monkeypatch: pytest.MonkeyPatch, released: threading.Event
) -> None:
    retriever = FakeRetriever(released=released, block=False)
    install(monkeypatch, retriever)

    result = hybrid_retrieval.graph_query(QUESTION)

    assert retriever.calls == [QUESTION]
    assert result == {"cypher": CYPHER, "records": [{"hotel_count": 300}]}


def test_the_row_bound_still_applies_under_the_timeout_wiring(
    monkeypatch: pytest.MonkeyPatch, released: threading.Event
) -> None:
    rows = [{"hotel_name": f"Hotel {index}"} for index in range(60)]
    retriever = FakeRetriever(released=released, block=False)
    monkeypatch.setattr(retriever, "search", lambda query_text: fake_result(rows))
    install(monkeypatch, retriever)

    result = hybrid_retrieval.graph_query(QUESTION)

    assert result["records"] == rows[: hybrid_retrieval.MAX_GRAPH_QUERY_RECORDS]


def test_an_empty_query_is_still_refused_before_any_retriever_call(
    monkeypatch: pytest.MonkeyPatch, released: threading.Event
) -> None:
    retriever = FakeRetriever(released=released, block=True)
    install(monkeypatch, retriever, timeout=TEST_TIMEOUT_SECONDS)

    with pytest.raises(ValueError):
        hybrid_retrieval.graph_query("   ")

    assert retriever.calls == []
