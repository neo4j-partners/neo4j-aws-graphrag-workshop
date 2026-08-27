# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""The shared read-tool contract: success envelope, bounded errors, and verdict.

Module 3 registers two read tools, and Modules 4 and 5 expose the same two
through AgentCore. All three need the same answer to three questions: what a
successful read returns, what an expected failure returns, and how a caller
decides whether the returned evidence supports the question. Those three
answers live here so one file can be changed instead of three.

The verdict and the evidence are separate things, and keeping them separate is
the point of this module.

The verdict is two fields, `answerable` and `missing_fact`, and it is identical
for both read tools. It is a property of the question asked against this graph,
not a property of the retrieval mechanism: both tools read the same Neo4j
database, so live room availability is unsupported whichever path ran. That is
what lets one Lambda envelope carry one `grounding_result` from either handler,
and what lets a caller iterate a list of verdicts from several tool calls
without asking which tool produced each one.

The evidence is per tool and sits beside the verdict rather than inside it. A
passage result carries `hotel_ids` and the top hotel's checkable fields. A
structured result carries the generated `cypher`, the returned `records`, and
their `row_count`. The two shapes are genuinely different, because an average
guest rating has no hotel identity and no address, and pretending otherwise
would put empty hotel fields on every aggregate.

Like `contracts`, this module holds no AWS or Neo4j clients, reads no
environment variables, and imports nothing outside the standard library. It is
safe to import from a test, a notebook, a Lambda, or the Runtime container
without causing a network call.
"""

from __future__ import annotations

from typing import Any, Final, Literal, Mapping, Sequence, TypedDict

# A tool result is echoed into notebook output and, in Module 5, into a Runtime
# response. An unbounded exception string from a driver or a model provider can
# run to several thousand characters and buries the error code that a caller
# actually branches on.
MAX_ERROR_CHARS: Final = 300

# The graph stores hotel knowledge and total room capacity. It stores no live
# room inventory, so a question about current availability cannot be answered
# from either read path no matter how much evidence comes back. That verdict is
# decided here rather than left to the model, because a model looking at a rich
# hotel record will reliably find something to say.
LIVE_AVAILABILITY_TERMS: Final = (
    "availability",
    "available",
    "vacancy",
    "vacancies",
    "inventory",
)

MISSING_LIVE_AVAILABILITY: Final = "live_room_availability"
MISSING_MATCHING_CONTEXT: Final = "matching_hotel_context"

# The top passage's checkable fields travel back to the caller beside the
# verdict. A refusal and a dead index look identical from outside, because both
# produce no answer. A check can only tell them apart if some real, specific
# value from the graph crosses this boundary, so every passage result carries
# one.
TOP_RESULT_FIELDS: Final = ("hotel_id", "hotel_name", "address", "guest_rating")

# Error codes, not error prose. A caller branches on the code and shows the
# message.
INVALID_QUERY: Final = "invalid_query"
QUERY_FAILED: Final = "query_failed"

# One wording for a rejected read input, shared by the Module 3 Strands tools
# and by both Module 4 Lambdas. Every read path advertises exactly one input
# field named `query`, so one sentence describes the rule on all of them, and a
# check that reads a rejection back does not have to know which path produced
# it. Three copies of this sentence drifted into two different messages once
# already.
INVALID_QUERY_MESSAGE: Final = "input must contain only query as a non-empty string"


class Verdict(TypedDict):
    """Whether the returned evidence can support the question, and what is missing."""

    answerable: bool
    missing_fact: str | None


class PassagePayload(TypedDict):
    """The passage tool's success envelope: verdict plus passage evidence."""

    ok: Literal[True]
    passages: list[dict[str, Any]]
    hotel_ids: list[str]
    top_result: dict[str, Any]
    grounding_result: Verdict


class RecordPayload(TypedDict):
    """The structured tool's success envelope: verdict plus row evidence."""

    ok: Literal[True]
    cypher: str
    records: list[dict[str, Any]]
    row_count: int
    grounding_result: Verdict


class ErrorPayload(TypedDict):
    """An expected, bounded read failure."""

    ok: Literal[False]
    error_code: str
    error_message: str


def validated_query(value: object) -> str | None:
    """Return `value` when it is a usable query string, otherwise None.

    A generated tool schema can say that `query` is a required string. It
    cannot say the string has to hold something, so an empty or whitespace-only
    query reaches the tool body and is rejected here.

    This is only the nonblank-string half of the rule, because that half is the
    part every caller shares. Each boundary adds what it alone requires: a
    Lambda first checks that the event carries `query` and nothing else, and a
    Strands tool passes its bare argument straight in.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def asks_for_live_availability(query: str) -> bool:
    """Report whether the question asks about current room inventory."""
    normalized = query.casefold()
    return any(term in normalized for term in LIVE_AVAILABILITY_TERMS)


def grounding_verdict(
    query: str,
    records: Sequence[Mapping[str, Any]],
) -> Verdict:
    """Judge whether `records` can support an answer to `query`.

    `records` is passage records from one read path or Cypher rows from the
    other. Only their presence is read here, because the verdict is about the
    question and the graph rather than about which retriever ran.

    Zero records is a successful read that matched nothing, and it is reported
    as unanswerable. It is not proof that the graph lacks the fact: a generated
    query can return no rows because it asked the wrong question, and this
    verdict cannot tell the two apart.
    """
    if asks_for_live_availability(query):
        return {"answerable": False, "missing_fact": MISSING_LIVE_AVAILABILITY}
    if not records:
        return {"answerable": False, "missing_fact": MISSING_MATCHING_CONTEXT}
    return {"answerable": True, "missing_fact": None}


def hotel_ids(passages: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return the distinct non-empty hotel ids the passages carry, in rank order."""
    return list(
        dict.fromkeys(
            item["hotel_id"]
            for item in passages
            if isinstance(item.get("hotel_id"), str) and item["hotel_id"]
        )
    )


def top_result(passages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the checkable fields of the highest-scoring passage's hotel."""
    top = passages[0] if passages else {}
    return {field: top.get(field) for field in TOP_RESULT_FIELDS}


def passage_payload(
    query: str,
    passages: Sequence[Mapping[str, Any]],
) -> PassagePayload:
    """Build the passage tool's success envelope."""
    return {
        "ok": True,
        "passages": [dict(item) for item in passages],
        "hotel_ids": hotel_ids(passages),
        "top_result": top_result(passages),
        "grounding_result": grounding_verdict(query, passages),
    }


def record_payload(
    query: str,
    cypher: str,
    records: Sequence[Mapping[str, Any]],
) -> RecordPayload:
    """Build the structured tool's success envelope."""
    rows = [dict(item) for item in records]
    return {
        "ok": True,
        "cypher": cypher,
        "records": rows,
        "row_count": len(rows),
        "grounding_result": grounding_verdict(query, rows),
    }


def error_payload(error_code: str, message: object) -> ErrorPayload:
    """Build a bounded failure envelope from an error code and a message."""
    text = " ".join(str(message).split())
    if len(text) > MAX_ERROR_CHARS:
        text = text[: MAX_ERROR_CHARS - 1] + "…"
    return {"ok": False, "error_code": error_code, "error_message": text}
