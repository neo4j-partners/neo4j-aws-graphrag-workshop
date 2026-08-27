"""Focused contract checks for the Module 4 Gateway and Lambda boundaries."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from neo4j_graphrag.exceptions import Text2CypherRetrievalError
from workshop import contracts, grounding
from workshop.agent_tools import PASSAGE_TOOL, RECORD_TOOL

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = REPO_ROOT / "notebooks" / "04-production-agent"
NOTEBOOK = MODULE_DIR / "4.1_agentcore_gateway.ipynb"
SCHEMAS = MODULE_DIR / "tool_schemas" / "tools.json"
LAMBDA_SRC = MODULE_DIR / "lambda_tools"
PASSAGE_HANDLER = LAMBDA_SRC / PASSAGE_TOOL / "lambda_function.py"
RECORD_HANDLER = LAMBDA_SRC / RECORD_TOOL / "lambda_function.py"

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


def tool_schemas() -> list[dict]:
    """Return the committed Gateway tool schemas."""
    return json.loads(SCHEMAS.read_text())


def notebook_code() -> str:
    """Return every code cell of the Module 4 notebook as one string."""
    cells = json.loads(NOTEBOOK.read_text())["cells"]
    return "\n".join(
        "".join(cell["source"]) for cell in cells if cell["cell_type"] == "code"
    )


@pytest.fixture
def passage_handler() -> ModuleType:
    return load_module("module4_passage_lambda", PASSAGE_HANDLER)


@pytest.fixture
def record_handler() -> ModuleType:
    return load_module("module4_record_lambda", RECORD_HANDLER)


def test_gateway_schema_advertises_the_two_shared_read_tools() -> None:
    schemas = tool_schemas()
    assert [entry["name"] for entry in schemas] == [PASSAGE_TOOL, RECORD_TOOL]

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


@pytest.mark.parametrize(
    ("tool_name", "sibling"),
    [(PASSAGE_TOOL, RECORD_TOOL), (RECORD_TOOL, PASSAGE_TOOL)],
    ids=[PASSAGE_TOOL, RECORD_TOOL],
)
def test_each_description_routes_away_to_its_sibling_tool(
    tool_name: str, sibling: str
) -> None:
    """The description is the whole routing rule, so check what it has to carry.

    Not the exact prose. A description is edited for a model, and pinning it
    byte for byte turns every wording improvement into a failing test that
    teaches nothing. What has to hold is that a description exists, that it
    says something, and that it names the other tool so a misrouted question
    has somewhere to go.
    """
    entry = next(item for item in tool_schemas() if item["name"] == tool_name)
    description = entry["description"]

    assert isinstance(description, str)
    assert description.strip()
    assert sibling in description
    assert "live room availability" in description


def test_the_notebook_packages_exactly_the_tools_the_gateway_registers() -> None:
    """One rename must not leave a Gateway target pointed at a missing Lambda.

    The packaging cell derives its function list from `tools.json` rather than
    restating the names, and this is the offline check that it still does.
    """
    code = notebook_code()
    assert 'json.loads((MODULE_DIR / "tool_schemas" / "tools.json").read_text())' in code
    assert 'LAMBDA_SRC / entry["name"]' in code
    assert "assert TOOL_NAMES == [PASSAGE_TOOL, RECORD_TOOL]" in code

    for entry in tool_schemas():
        handler = LAMBDA_SRC / entry["name"] / "lambda_function.py"
        assert handler.is_file(), handler

    built = sorted(path.name for path in LAMBDA_SRC.iterdir() if path.is_dir())
    assert built == sorted(entry["name"] for entry in tool_schemas())


def test_the_notebook_forwards_the_configured_model_to_the_lambdas() -> None:
    """The role grants one model; the function has to be told to use that one."""
    code = notebook_code()
    assert '"MODEL_ID": CONFIGURED_MODEL_ID' in code
    assert "get_function_configuration" in code


@pytest.mark.parametrize("index", [0, 1], ids=[PASSAGE_TOOL, RECORD_TOOL])
def test_registered_gateway_schema_uses_only_supported_fields(index: int) -> None:
    source = tool_schemas()[index]["input_schema"]

    assert contracts.gateway_input_schema(source) == {
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


def test_the_gateway_projection_drops_every_unsupported_property_key() -> None:
    """`minLength`, `format`, and `additionalProperties` are not registrable."""
    projected = contracts.gateway_reservation_input_schema()

    assert "additionalProperties" not in projected
    for definition in projected["properties"].values():
        assert set(definition) <= contracts.GATEWAY_PROPERTY_KEYS


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
        "error_message": grounding.INVALID_QUERY_MESSAGE,
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


def test_the_record_lambda_shares_the_one_expected_error_tuple(
    record_handler: ModuleType,
) -> None:
    """A fourth expected exception has to reach both callers, not one of them."""
    from workshop import agent_tools, hybrid_retrieval

    assert record_handler.EXPECTED_QUERY_ERRORS is (
        hybrid_retrieval.EXPECTED_QUERY_ERRORS
    )
    assert agent_tools.EXPECTED_QUERY_ERRORS is hybrid_retrieval.EXPECTED_QUERY_ERRORS


def test_record_handler_leaves_unexpected_infrastructure_failure_visible(
    record_handler: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(query: str) -> None:
        raise TimeoutError("Neo4j connection timed out")

    monkeypatch.setattr(record_handler, "graph_query", fail)
    with pytest.raises(TimeoutError, match="Neo4j connection timed out"):
        record_handler.handler({"query": "Try a generated query"}, None)


def test_gateway_names_map_directly_to_lambdas_and_normalize_prefixes() -> None:
    assert contracts.lambda_function_name(PASSAGE_TOOL) == (
        f"hotel-booking-{PASSAGE_TOOL}"
    )
    assert contracts.lambda_function_name(RECORD_TOOL) == f"hotel-booking-{RECORD_TOOL}"
    assert contracts.gateway_base_name(f"passage-target___{PASSAGE_TOOL}") == (
        PASSAGE_TOOL
    )
    assert contracts.gateway_base_name(RECORD_TOOL) == RECORD_TOOL
    assert PASSAGE_HANDLER.is_file()
    assert RECORD_HANDLER.is_file()
