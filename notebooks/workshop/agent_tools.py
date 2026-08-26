# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""The two read tools a Strands agent chooses between.

Module 3 registers both of these and lets the model pick. `search_hotel_passages`
is the semantic path and answers questions about hotel text. `query_hotel_records`
is the structured path and answers questions that need counts, averages,
rankings, filters, or relationship logic. The routing rule that decides between
them lives in the docstrings, because the docstring is what the model reads.

The wrappers live here rather than in a notebook cell so Modules 3 and 5
register the same two tools instead of two copies that drift. Each Python
function name is the model-visible tool name, so there is one name to search
for. The Module 3 notebook prints each final tool specification and the source
of each wrapper, which is what a participant needs to see; a second definition
in a cell would be a second thing to keep in step with this one.

Importing this module builds no clients and reads no environment variables.
`hybrid_retrieval` creates its driver, embedder, and Text2Cypher model lazily
inside the cached retriever builders, so both tool specifications can be
defined and printed before a participant has configured anything. Credentials
are needed only when a tool actually runs.

Every returned result is a Strands `ToolResult` dict whose one content block is
native JSON. Strands passes a returned dict straight through when it carries
both `status` and `content`, and its Bedrock model formatter forwards a `json`
block to Converse unchanged, so numbers stay numbers on the way to the model.
"""

from __future__ import annotations

from typing import Any, Final

from neo4j.exceptions import ClientError
from neo4j_graphrag.exceptions import LLMGenerationError, Text2CypherRetrievalError
from strands import tool

from workshop import grounding
from workshop.hybrid_retrieval import (
    MAX_GRAPH_QUERY_RECORDS,
    graph_query,
    search_hotel_knowledge,
)

PASSAGE_TOOL: Final = "search_hotel_passages"
RECORD_TOOL: Final = "query_hotel_records"

# The failures a structured read is expected to produce, as opposed to an
# outage. `Text2CypherRetrievalError` is what the read-only `EXPLAIN` guard
# raises when the generated Cypher would write, and what the retriever raises
# for Cypher the database reports as a syntax error. `LLMGenerationError` is a
# failure in the nested model call that writes the Cypher. `ClientError` is
# what the driver raises for a statement the database rejects for any other
# reason, such as a property the schema does not have; `CypherSyntaxError` is
# one of its subclasses. Anything else is left to propagate, because an outage
# should stay visible as an outage rather than arrive as a tidy error code.
EXPECTED_QUERY_ERRORS: Final = (
    Text2CypherRetrievalError,
    LLMGenerationError,
    ClientError,
)


def _success(payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap a success envelope as a native-JSON Strands tool result."""
    return {"status": "success", "content": [{"json": payload}]}


def _failure(error_code: str, message: object) -> dict[str, Any]:
    """Wrap a bounded failure envelope as a Strands error tool result."""
    return {
        "status": "error",
        "content": [{"json": grounding.error_payload(error_code, message)}],
    }


def _rejected_query(query: object) -> dict[str, Any] | None:
    """Return an error result when `query` is not usable, otherwise None.

    The generated Strands input schema can say that `query` is a required
    string. It cannot say that the string has to contain something, so an
    empty or whitespace-only query reaches the tool body and is rejected here.
    """
    if not isinstance(query, str) or not query.strip():
        return _failure(grounding.INVALID_QUERY, "query must be a non-empty string")
    return None


@tool
def search_hotel_passages(query: str) -> dict[str, Any]:
    """Find up to five hotel passages and the hotel facts linked to them.

    Use this for amenities, room descriptions, policies, services, and
    location details about one hotel or a few named hotels, and whenever the
    answer needs the source wording of the hotel text.

    Send counts, averages, rankings, and filters across many hotels to
    query_hotel_records instead. Neither read tool has live room availability,
    because the graph stores hotel knowledge and total room capacity rather
    than current inventory.

    Args:
        query: The guest's natural-language hotel question. Must not be empty.

    Returns:
        JSON carrying `ok`, the matching `passages`, the `hotel_ids` they name,
        the `top_result` fields of the best match, and a `grounding_result`
        verdict. An expected failure returns `ok: false` with an `error_code`
        and a short `error_message`.
    """
    rejected = _rejected_query(query)
    if rejected is not None:
        return rejected

    passages = search_hotel_knowledge(query)
    return _success(dict(grounding.passage_payload(query, passages)))


@tool
def query_hotel_records(query: str) -> dict[str, Any]:
    """Run model-generated read-only Cypher over the stored hotel records.

    Use this for counts, averages, rankings, filters, and relationship
    questions across many hotels, such as how many hotels offer a spa or the
    average guest rating of the hotels in one city.

    Send questions that need the source wording of hotel text to
    search_hotel_passages instead. An aggregate can cover every matching
    record, and a list result returns at most 25 rows. Empty records mean the
    generated query returned no rows, which does not prove that the graph
    lacks the fact. Neither read tool has live room availability.

    Args:
        query: The guest's natural-language hotel question. Must not be empty.

    Returns:
        JSON carrying `ok`, the generated `cypher`, the returned `records`,
        their `row_count`, and a `grounding_result` verdict. An expected
        failure returns `ok: false` with an `error_code` and a short
        `error_message`.
    """
    rejected = _rejected_query(query)
    if rejected is not None:
        return rejected

    try:
        result = graph_query(query)
    except EXPECTED_QUERY_ERRORS as error:
        return _failure(grounding.QUERY_FAILED, f"{type(error).__name__}: {error}")

    payload = grounding.record_payload(query, result["cypher"], result["records"])
    return _success(dict(payload))


READ_TOOLS: Final = (search_hotel_passages, query_hotel_records)

# The row bound is written as a number in the docstring above, because a
# docstring cannot be an f-string. `tests/test_agent_tools.py` checks that the
# number the model is told matches this one, so raising the bound in
# `hybrid_retrieval` cannot quietly leave the tool description behind.
ROW_LIMIT: Final = MAX_GRAPH_QUERY_RECORDS
