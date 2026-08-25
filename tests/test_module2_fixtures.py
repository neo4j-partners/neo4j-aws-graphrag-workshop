# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Focused tests for the deterministic Module 2 source fixtures."""

from __future__ import annotations

import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from workshop import retrieval_setup

CONNECTED_CONTEXT = (
    Path(__file__).resolve().parents[1] / "notebooks" / "02-connected-context"
)
sys.path.insert(0, str(CONNECTED_CONTEXT))

import graph_config


def _ready_source_record(
    fixture: retrieval_setup.SourceFixture,
) -> dict[str, object]:
    return {
        "source_filename": fixture.source_filename,
        "document_count": 1,
        "chunk_count": 1,
        "embedded_chunk_count": 1,
        "hotel_count": 1,
        "source_path_count": 1,
        "chunk_texts": [" ".join(fixture.chunk_terms)],
        "hotel_names": [fixture.hotel_name],
        "hotel_ids": [fixture.hotel_id] if fixture.hotel_id is not None else [],
        "hotel_addresses": [f"Fixture address {fixture.address_term}"],
        "guest_ratings": (
            [fixture.guest_rating] if fixture.guest_rating is not None else []
        ),
        "amenities": list(fixture.amenities),
    }


def _chicago_records() -> list[dict[str, object]]:
    return [
        {
            "source_filename": "hotel-chicago-001.txt",
            "hotel_name": retrieval_setup.CHICAGO_EXCLUSION,
            "guest_rating": 4.5,
            "amenities": ["Complimentary High-Speed Wifi"],
            "has_spa": False,
            "has_pool": False,
            "qualifies": False,
            "missing_required_amenities": ["spa", "swimming pool"],
        },
        {
            "source_filename": "hotel-chicago-002.txt",
            "hotel_name": retrieval_setup.CHICAGO_QUALIFIER,
            "guest_rating": 4.4,
            "amenities": ["Full-Service Spa", "Outdoor Swimming Pool"],
            "has_spa": True,
            "has_pool": True,
            "qualifies": True,
            "missing_required_amenities": [],
        },
    ]


def test_lite_selection_uses_every_required_source_and_stays_at_30(
    tmp_path: Path,
) -> None:
    with ZipFile(CONNECTED_CONTEXT / "hotel-faqs.zip") as corpus:
        for filename in corpus.namelist():
            if filename.endswith(".txt"):
                (tmp_path / filename).touch()

    selected = graph_config.select_lite_files(tmp_path, max_docs=30)

    assert len(selected) == 30
    assert len(set(selected)) == 30
    assert set(retrieval_setup.REQUIRED_SOURCE_FILES) <= set(selected)
    assert "hotel-chicago-002.txt" in selected


def test_lite_selection_rejects_a_missing_required_source(tmp_path: Path) -> None:
    for filename in retrieval_setup.REQUIRED_SOURCE_FILES:
        if filename != "hotel-chicago-002.txt":
            (tmp_path / filename).touch()

    with pytest.raises(ValueError, match="hotel-chicago-002.txt"):
        graph_config.select_lite_files(tmp_path, max_docs=30)


def test_lite_selection_rejects_a_corpus_that_cannot_fill_the_sample(
    tmp_path: Path,
) -> None:
    for filename in retrieval_setup.REQUIRED_SOURCE_FILES:
        (tmp_path / filename).touch()

    with pytest.raises(ValueError, match="found only .* expected 30"):
        graph_config.select_lite_files(tmp_path, max_docs=30)


def test_exact_source_readiness_accepts_authored_fixture_facts() -> None:
    records = [
        _ready_source_record(fixture)
        for fixture in retrieval_setup.SOURCE_FIXTURES
    ]

    assert retrieval_setup._source_fixture_problems(records) == []


def test_exact_source_readiness_reports_path_chunk_and_amenity_defects() -> None:
    records = [
        _ready_source_record(fixture)
        for fixture in retrieval_setup.SOURCE_FIXTURES
    ]
    records[1]["source_path_count"] = 2
    records[1]["chunk_texts"] = ["text without the locked postal code"]
    records[2]["amenities"] = ["Full-Service Spa"]

    problems = retrieval_setup._source_fixture_problems(records)

    assert any("hotel-chicago-001.txt has 2 source_path_count" in p for p in problems)
    assert any("Chunk is missing terms" in p and "60611" in p for p in problems)
    assert any(
        "hotel-chicago-002.txt is missing authored amenities" in p for p in problems
    )


@pytest.mark.parametrize(
    ("hotel_ids", "hotel_count", "source_path_count"),
    [
        ([], 1, 1),
        (["wrong-hotel-id"], 1, 1),
        ([retrieval_setup.CAIRO_HOTEL_ID], 2, 2),
    ],
)
def test_cairo_readiness_rejects_missing_wrong_and_duplicated_hotel_identity(
    hotel_ids: list[str],
    hotel_count: int,
    source_path_count: int,
) -> None:
    records = [
        _ready_source_record(fixture)
        for fixture in retrieval_setup.SOURCE_FIXTURES
    ]
    cairo = records[0]
    cairo["hotel_ids"] = hotel_ids
    cairo["hotel_count"] = hotel_count
    cairo["source_path_count"] = source_path_count

    problems = retrieval_setup._source_fixture_problems(records)

    assert problems
    assert any("hotel-cairo-001.txt" in problem for problem in problems)


def test_chicago_candidates_are_selected_by_city_not_expected_source_names() -> None:
    query = retrieval_setup.CHICAGO_FILTER_QUERY

    assert "$city" in query
    assert "$source_filenames" not in query


def test_chicago_filter_accepts_two_candidates_one_qualifier_and_exclusion() -> None:
    assert retrieval_setup.chicago_filter_problems(_chicago_records()) == []


def test_chicago_filter_rejects_wrong_qualifier_and_implicit_exclusion() -> None:
    records = _chicago_records()
    records[0]["qualifies"] = True
    records[0]["missing_required_amenities"] = []

    problems = retrieval_setup.chicago_filter_problems(records)

    assert any("qualifiers" in problem for problem in problems)
    assert any("did not explicitly exclude Windward Mile Tower" in p for p in problems)
