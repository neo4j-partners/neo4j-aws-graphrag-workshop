# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""The Module 2 notebook checks that replaced its inline assertions.

The notebook executes live in CI, so these are what turn a degraded graph red.
Each check gets a healthy input that must come back clean and a damaged one
that must name what broke, because a check that cannot fail proves nothing.
"""

from __future__ import annotations

import pytest
from workshop import retrieval_setup
from workshop.retrieval_setup import (
    GRAPH_CONTEXT_FIELDS,
    GRAPH_CONTEXT_RELATIONSHIPS,
    ReadinessError,
    fixture_for,
    graph_context_problems,
    report_problems,
    source_context_problems,
)

CAIRO = fixture_for("hotel-cairo-001.txt")
CHICAGO = fixture_for("hotel-chicago-001.txt")


def _text_row(fixture: retrieval_setup.SourceFixture, chunk: str | None = None):
    return {
        "source_filename": fixture.source_filename,
        "chunk": chunk if chunk is not None else " ".join(fixture.chunk_terms),
    }


def _graph_record(fixture: retrieval_setup.SourceFixture, **overrides):
    record = {
        "source_filename": fixture.source_filename,
        "hotel_name": fixture.hotel_name,
        "hotel_id": fixture.hotel_id,
        "guest_rating": fixture.guest_rating,
        "amenities": list(fixture.amenities),
        "semantic_score": 0.91,
        "relationship_types": list(GRAPH_CONTEXT_RELATIONSHIPS),
        "field_provenance": {field: "(:Chunk)" for field in GRAPH_CONTEXT_FIELDS},
        "missing_requested_fields": [],
    }
    record.update(overrides)
    return record


# --------------------------------------------------------------------------
# fixture_for
# --------------------------------------------------------------------------


def test_every_locked_fixture_is_reachable_by_name() -> None:
    for fixture in retrieval_setup.SOURCE_FIXTURES:
        assert fixture_for(fixture.source_filename) is fixture


def test_an_unknown_source_is_refused_rather_than_silently_empty() -> None:
    with pytest.raises(KeyError):
        fixture_for("hotel-atlantis-999.txt")


# --------------------------------------------------------------------------
# source_context_problems
# --------------------------------------------------------------------------


def test_retrieved_text_carrying_every_fixture_term_is_clean() -> None:
    assert source_context_problems([_text_row(CAIRO)], CAIRO) == []


def test_a_source_missing_from_the_results_is_named_with_what_was_returned() -> None:
    problems = source_context_problems([_text_row(CHICAGO)], CAIRO)

    assert len(problems) == 1
    assert CAIRO.source_filename in problems[0]
    assert CHICAGO.source_filename in problems[0]


def test_the_right_source_without_its_terms_is_still_a_defect() -> None:
    """A retriever can return the correct document and still miss the answer."""
    problems = source_context_problems(
        [_text_row(CAIRO, chunk="AnyCompany Cairo Nile View")], CAIRO
    )

    assert problems == [f"{CAIRO.source_filename} context does not carry '3:00 PM'"]


def test_extra_terms_are_checked_without_being_pinned_to_the_fixture() -> None:
    """Module 2 asks for a term Module 1's readiness query does not pin."""
    rows = [_text_row(CHICAGO)]

    assert source_context_problems(rows, CHICAGO) == []
    assert source_context_problems(rows, CHICAGO, extra_terms=("no refunds",)) == [
        f"{CHICAGO.source_filename} context does not carry 'no refunds'"
    ]


def test_term_matching_ignores_case() -> None:
    rows = [_text_row(CAIRO, chunk=" ".join(CAIRO.chunk_terms).upper())]

    assert source_context_problems(rows, CAIRO) == []


# --------------------------------------------------------------------------
# graph_context_problems
# --------------------------------------------------------------------------


def test_a_complete_graph_record_is_clean() -> None:
    assert graph_context_problems([_graph_record(CAIRO)], CAIRO) == []


def test_other_hotels_in_the_result_set_do_not_count_against_the_fixture() -> None:
    records = [_graph_record(CHICAGO), _graph_record(CAIRO)]

    assert graph_context_problems(records, CAIRO) == []


def test_a_duplicated_source_is_reported_rather_than_silently_first_wins() -> None:
    problems = graph_context_problems([_graph_record(CAIRO)] * 2, CAIRO)

    assert problems == [
        f"expected one graph record for {CAIRO.source_filename}, observed 2"
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hotel_name", "AnyCompany Cairo Riverside"),
        ("hotel_id", "00000000-0000-0000-0000-000000000000"),
        ("guest_rating", 3.9),
    ],
)
def test_a_wrong_locked_field_names_both_the_observed_and_expected_value(
    field: str, value: object
) -> None:
    problems = graph_context_problems([_graph_record(CAIRO, **{field: value})], CAIRO)

    assert len(problems) == 1
    assert field in problems[0]
    assert repr(value) in problems[0]
    assert repr(getattr(CAIRO, field)) in problems[0]


def test_a_severed_amenity_relationship_names_the_missing_amenity() -> None:
    """The negative case the whole rewrite exists to keep catching."""
    kept = [a for a in CAIRO.amenities if a != "Full-Service Spa"]

    problems = graph_context_problems([_graph_record(CAIRO, amenities=kept)], CAIRO)

    assert problems == [
        f"{CAIRO.source_filename} amenities do not include 'Full-Service Spa'"
    ]


def test_a_semantic_hit_with_no_hotel_expansion_is_a_defect() -> None:
    record = _graph_record(
        CAIRO,
        relationship_types=["FROM_DOCUMENT"],
        missing_requested_fields=["hotel_id", "amenities"],
    )

    problems = graph_context_problems([record], CAIRO)

    assert any("missing ['amenities', 'hotel_id']" in problem for problem in problems)
    assert any("relationship types" in problem for problem in problems)


def test_an_unscored_record_is_a_defect() -> None:
    problems = graph_context_problems([_graph_record(CAIRO, semantic_score=None)], CAIRO)

    assert problems == [f"{CAIRO.source_filename} graph record has no semantic score"]


def test_a_field_with_no_provenance_path_is_named() -> None:
    provenance = {
        field: "(:Chunk)" for field in GRAPH_CONTEXT_FIELDS if field != "amenities"
    }

    problems = graph_context_problems(
        [_graph_record(CAIRO, field_provenance=provenance)], CAIRO
    )

    assert problems == [
        f"{CAIRO.source_filename} names no provenance path for ['amenities']"
    ]


# --------------------------------------------------------------------------
# report_problems
# --------------------------------------------------------------------------


def test_no_problems_prints_one_pass_line(capsys: pytest.CaptureFixture[str]) -> None:
    report_problems([], "Cairo context is complete.")

    assert capsys.readouterr().out == "PASS  Cairo context is complete.\n"


def test_problems_raise_with_every_problem_named(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(ReadinessError) as caught:
        report_problems(["spa is missing", "pool is missing"], "unused")

    assert "spa is missing" in str(caught.value)
    assert "pool is missing" in str(caught.value)
    assert capsys.readouterr().out == ""
