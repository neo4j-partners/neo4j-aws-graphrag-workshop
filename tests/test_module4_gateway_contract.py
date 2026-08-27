"""Focused contract checks for the Module 4 Gateway and Lambda boundaries."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from neo4j_graphrag.exceptions import Text2CypherRetrievalError
from workshop import grounding

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = REPO_ROOT / "notebooks" / "04-production-agent"
SCHEMAS = MODULE_DIR / "tool_schemas" / "tools.json"
GATEWAY_CONTRACT = MODULE_DIR / "gateway_contract.py"
PASSAGE_HANDLER = (
    MODULE_DIR / "lambda_tools" / "search_hotel_passages" / "lambda_function.py"
)
RECORD_HANDLER = (
    MODULE_DIR / "lambda_tools" / "query_hotel_records" / "lambda_function.py"
)

PASSAGES = [
    {
        "hotel_id": "hotel-1",
        "hotel_name": "Example Hotel",
        "address": "Paris",
        "guest_rating": 4.7,
        "text": "A quiet hotel in Paris.",
    }
]


def load_module(name: str, path: Path) -> ModuleType:
    """Load one Lambda entry point under a test-only module name."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gateway_contract() -> ModuleType:
    return load_module("module4_gateway_contract", GATEWAY_CONTRACT)


@pytest.fixture
def passage_handler() -> ModuleType:
    return load_module("module4_passage_lambda", PASSAGE_HANDLER)


@pytest.fixture
def record_handler() -> ModuleType:
    return load_module("module4_record_lambda", RECORD_HANDLER)


def test_gateway_schema_advertises_the_two_shared_read_tools() -> None:
    schemas = json.loads(SCHEMAS.read_text())
    assert [entry["name"] for entry in schemas] == [
        "search_hotel_passages",
        "query_hotel_records",
    ]

    passage, records = schemas
    assert "query_hotel_records" in passage["description"]
    assert "source wording" in passage["description"]
    assert "search_hotel_passages" in records["description"]
    assert "at most 25 rows" in records["description"]

    for entry in schemas:
        input_schema = entry["input_schema"]
        assert input_schema == {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 1,
                    "description": (
                        "The guest's natural-language hotel question. "
                        "Must not be empty."
                    ),
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        }


def test_registered_gateway_schema_uses_only_supported_fields(
    gateway_contract: ModuleType,
) -> None:
    source = json.loads(SCHEMAS.read_text())[0]["input_schema"]

    assert gateway_contract.gateway_input_schema(source) == {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The guest's natural-language hotel question. Must not be empty."
                ),
            }
        },
        "required": ["query"],
    }


@pytest.mark.parametrize(
    "event",
    [
        None,
        {},
        {"query": None},
        {"query": 7},
        {"query": ""},
        {"query": "  \n\t"},
        {"query": "Where is it?", "limit": 5},
    ],
)
def test_both_handlers_reject_invalid_or_extra_input(
    passage_handler: ModuleType,
    record_handler: ModuleType,
    event: object,
) -> None:
    expected = {
        "ok": False,
        "error_code": grounding.INVALID_QUERY,
        "error_message": "input must contain only query as a non-empty string",
    }
    assert passage_handler.handler(event, None) == expected
    assert record_handler.handler(event, None) == expected


def test_passage_handler_returns_the_shared_success_envelope(
    passage_handler: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        passage_handler,
        "search_hotel_knowledge",
        lambda query: PASSAGES,
    )

    result = passage_handler.handler({"query": "Where is the hotel?"}, None)

    assert result == grounding.passage_payload("Where is the hotel?", PASSAGES)
    assert result["ok"] is True
    assert result["passages"] == PASSAGES
    assert "context" not in result


def test_passage_handler_uses_the_shared_unsupported_fact_verdict(
    passage_handler: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        passage_handler,
        "search_hotel_knowledge",
        lambda query: PASSAGES,
    )
    result = passage_handler.handler(
        {"query": "Is a room available next weekend?"}, None
    )

    assert result["grounding_result"] == {
        "answerable": False,
        "missing_fact": grounding.MISSING_LIVE_AVAILABILITY,
    }


def test_record_handler_returns_success_and_empty_envelopes(
    record_handler: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        record_handler,
        "graph_query",
        lambda query: {
            "cypher": "RETURN 4.5 AS average_rating",
            "records": [{"average_rating": 4.5}],
        },
    )
    result = record_handler.handler({"query": "Average rating?"}, None)
    assert result == grounding.record_payload(
        "Average rating?",
        "RETURN 4.5 AS average_rating",
        [{"average_rating": 4.5}],
    )

    monkeypatch.setattr(
        record_handler,
        "graph_query",
        lambda query: {"cypher": "MATCH (h:Hotel) RETURN h LIMIT 25", "records": []},
    )
    empty = record_handler.handler({"query": "Hotels nowhere?"}, None)
    assert empty["ok"] is True
    assert empty["records"] == []
    assert empty["row_count"] == 0


def test_record_handler_bounds_expected_text2cypher_failures(
    record_handler: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(query: str) -> None:
        raise Text2CypherRetrievalError("x" * 1_000)

    monkeypatch.setattr(record_handler, "graph_query", fail)
    result = record_handler.handler({"query": "Try a generated query"}, None)

    assert result["ok"] is False
    assert result["error_code"] == grounding.QUERY_FAILED
    assert len(result["error_message"]) <= grounding.MAX_ERROR_CHARS
    assert result["error_message"].startswith("Text2CypherRetrievalError:")


def test_record_handler_leaves_unexpected_infrastructure_failure_visible(
    record_handler: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(query: str) -> None:
        raise TimeoutError("Neo4j connection timed out")

    monkeypatch.setattr(record_handler, "graph_query", fail)
    with pytest.raises(TimeoutError, match="Neo4j connection timed out"):
        record_handler.handler({"query": "Try a generated query"}, None)


def test_gateway_names_map_directly_to_lambdas_and_normalize_prefixes(
    gateway_contract: ModuleType,
) -> None:
    assert gateway_contract.lambda_function_name("search_hotel_passages") == (
        "hotel-booking-search_hotel_passages"
    )
    assert gateway_contract.lambda_function_name("query_hotel_records") == (
        "hotel-booking-query_hotel_records"
    )
    assert gateway_contract.gateway_base_name(
        "passage-target___search_hotel_passages"
    ) == ("search_hotel_passages")
    assert (
        gateway_contract.gateway_base_name("query_hotel_records")
        == "query_hotel_records"
    )
    assert PASSAGE_HANDLER.is_file()
    assert RECORD_HANDLER.is_file()
