# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Regressions for deterministic amenities in both graph build paths."""

from __future__ import annotations

import asyncio
import inspect
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from zipfile import ZipFile

import pytest
from workshop import retrieval_setup
from workshop.amenities import (
    POOL_AMENITY_NAMES,
    ParsedAmenities,
    parse_amenity_section,
)
from workshop.graph_schema import GRAPH_SCHEMA, LLM_EXTRACTION_SCHEMA

CONNECTED_CONTEXT = (
    Path(__file__).resolve().parents[1] / "notebooks" / "02-connected-context"
)
SHARED_DIR = Path(__file__).resolve().parents[1] / "notebooks" / "shared"
RELEASE_DIR = Path(__file__).resolve().parents[1] / "tools" / "release"
sys.path.insert(0, str(RELEASE_DIR))
sys.path.insert(0, str(CONNECTED_CONTEXT))

HISTORICAL_MISSING_HOTEL_SOURCES = (
    "hotel-austin-002.txt",
    "hotel-mumbai-001.txt",
    "hotel-sanfrancisco-004.txt",
    "hotel-tucson-001.txt",
)

import graph_builder
import prepare_graph
import validate_graph_amenities


def _labels(schema: dict[str, object]) -> set[str]:
    return {node["label"] for node in schema["node_types"]}


def _relationships(schema: dict[str, object]) -> set[str]:
    return {relationship["label"] for relationship in schema["relationship_types"]}


def _properties(schema: dict[str, object], label: str) -> set[str]:
    node = next(node for node in schema["node_types"] if node["label"] == label)
    return {prop["name"] for prop in node["properties"]}


def _driver_with_records(records: list[dict[str, object]]) -> Mock:
    neo4j_session = Mock()
    neo4j_session.__enter__ = Mock(return_value=neo4j_session)
    neo4j_session.__exit__ = Mock(return_value=False)
    neo4j_session.run.return_value = records
    driver = Mock()
    driver.session.return_value = neo4j_session
    return driver


def test_llm_schema_excludes_only_deterministic_amenities() -> None:
    assert _labels(GRAPH_SCHEMA) == {
        "Hotel",
        "Room",
        "Amenity",
        "Policy",
        "Service",
    }
    assert _labels(LLM_EXTRACTION_SCHEMA) == {
        "Hotel",
        "Room",
        "Policy",
        "Service",
    }
    assert "OFFERS_AMENITY" in _relationships(GRAPH_SCHEMA)
    assert "OFFERS_AMENITY" not in _relationships(LLM_EXTRACTION_SCHEMA)
    assert _properties(GRAPH_SCHEMA, "Amenity") == {"name"}
    assert ("Hotel", "OFFERS_AMENITY", "Amenity") not in LLM_EXTRACTION_SCHEMA[
        "patterns"
    ]


def test_build_report_uses_explicit_count_store_patterns() -> None:
    source = inspect.getsource(graph_builder.report)

    for pattern in (
        "MATCH (hotel:Hotel) RETURN count(hotel) AS hotels",
        "MATCH (room:Room) RETURN count(room) AS rooms",
        "MATCH (amenity:Amenity) RETURN count(amenity) AS amenities",
        "MATCH (policy:Policy) RETURN count(policy) AS policies",
        "MATCH (service:Service) RETURN count(service) AS services",
    ):
        assert f"CALL () {{ {pattern} }}" in source
    assert "MATCH (n)" not in source
    assert (
        "MATCH ()-[r:HAS_ROOM|OFFERS_AMENITY|HAS_POLICY|PROVIDES_SERVICE]->()"
        in source
    )
    assert "WHERE type(r)" not in source


def test_build_report_cairo_fixture_matches_address_case_insensitively() -> None:
    source = inspect.getsource(graph_builder.report)

    assert "toLower(h.address) CONTAINS 'cairo'" in source
    assert "h.address CONTAINS 'Cairo'" not in source


def test_pipeline_raises_component_errors_and_disables_entity_resolution(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class PipelineStub:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(graph_builder, "SimpleKGPipeline", PipelineStub)
    monkeypatch.setattr(graph_builder, "BedrockLLM", Mock(return_value=Mock()))
    monkeypatch.setattr(graph_builder, "BedrockEmbeddings", Mock(return_value=Mock()))
    monkeypatch.setattr(graph_builder, "aws_region", Mock(return_value="us-west-2"))
    monkeypatch.setattr(
        graph_builder, "graph_database", Mock(return_value="workshop-db")
    )

    graph_builder.build_pipeline(Mock())

    assert captured["schema"] == LLM_EXTRACTION_SCHEMA
    assert captured["schema"] is not LLM_EXTRACTION_SCHEMA
    assert captured["on_error"] == "RAISE"
    assert captured["perform_entity_resolution"] is False
    assert captured["neo4j_database"] == "workshop-db"


def test_pipeline_cannot_mutate_the_schema_used_by_build_contract(monkeypatch) -> None:
    contract_before = graph_builder.build_contract()

    class MutatingPipelineStub:
        def __init__(self, **kwargs) -> None:
            kwargs["schema"]["patterns"][0] = re.compile("mutated")

    monkeypatch.setattr(graph_builder, "SimpleKGPipeline", MutatingPipelineStub)
    monkeypatch.setattr(graph_builder, "BedrockLLM", Mock(return_value=Mock()))
    monkeypatch.setattr(graph_builder, "BedrockEmbeddings", Mock(return_value=Mock()))

    graph_builder.build_pipeline(Mock())

    assert graph_builder.build_contract() == contract_before
    assert LLM_EXTRACTION_SCHEMA["patterns"][0] == (
        "Hotel",
        "HAS_ROOM",
        "Room",
    )


def test_source_hotel_check_rejects_missing_ambiguous_and_shared_hotels() -> None:
    records = [
        {
            "filename": "missing.txt",
            "document_count": 0,
            "chunk_count": 0,
            "hotel_count": 0,
            "hotel_element_ids": [],
        },
        {
            "filename": "ambiguous.txt",
            "document_count": 1,
            "chunk_count": 1,
            "hotel_count": 2,
            "hotel_element_ids": ["hotel-1", "hotel-2"],
        },
        {
            "filename": "shared-a.txt",
            "document_count": 1,
            "chunk_count": 1,
            "hotel_count": 1,
            "hotel_element_ids": ["shared-hotel"],
        },
        {
            "filename": "shared-b.txt",
            "document_count": 1,
            "chunk_count": 1,
            "hotel_count": 1,
            "hotel_element_ids": ["shared-hotel"],
        },
    ]
    paths = [Path(record["filename"]) for record in records]

    problems = graph_builder.check_source_hotels(
        _driver_with_records(records),
        paths,
    )

    assert any("missing.txt has 0 Document" in problem for problem in problems)
    assert any("missing.txt has 0 Hotels" in problem for problem in problems)
    assert any("ambiguous.txt has 2 Hotels" in problem for problem in problems)
    assert any("shared-a.txt, shared-b.txt" in problem for problem in problems)


def test_historical_missing_hotel_sources_fail_the_current_builder_gate() -> None:
    records = [
        {
            "filename": filename,
            "document_count": 1,
            "chunk_count": 1,
            "hotel_count": 0,
            "hotel_element_ids": [],
        }
        for filename in HISTORICAL_MISSING_HOTEL_SOURCES
    ]

    problems = graph_builder.check_source_hotels(
        _driver_with_records(records),
        [Path(filename) for filename in HISTORICAL_MISSING_HOTEL_SOURCES],
    )

    assert len(problems) == 4
    for filename in HISTORICAL_MISSING_HOTEL_SOURCES:
        assert any(f"{filename} has 0 Hotels" in problem for problem in problems)


def test_amenity_reconciliation_reports_missing_and_unexpected_pairs() -> None:
    records = [
        {"source_filename": "one.txt", "amenity_name": "WiFi"},
        {"source_filename": "two.txt", "amenity_name": "Unexpected Spa"},
    ]
    parsed = [
        ParsedAmenities("one.txt", ("WiFi",)),
        ParsedAmenities("two.txt", ("Pool",)),
    ]

    problems = graph_builder.check_amenity_assertions(
        _driver_with_records(records),
        parsed,
    )

    assert any("1 source amenity assertions are missing" in item for item in problems)
    assert any("two.txt: Pool" in item for item in problems)
    assert any("1 unexpected amenity assertions exist" in item for item in problems)
    assert any("two.txt: Unexpected Spa" in item for item in problems)


def test_shared_readiness_rejects_missing_ambiguous_and_shared_hotels() -> None:
    neo4j_session = Mock()
    neo4j_session.__enter__ = Mock(return_value=neo4j_session)
    neo4j_session.__exit__ = Mock(return_value=False)
    neo4j_session.run.side_effect = [
        [
            {"filename": "missing.txt", "hotel_count": 0},
            {"filename": "ambiguous.txt", "hotel_count": 2},
        ],
        [{"source_filenames": ["shared-a.txt", "shared-b.txt"]}],
    ]
    driver = Mock()
    driver.session.return_value = neo4j_session

    problems = retrieval_setup.hotel_provenance_problems(driver)

    assert any("missing.txt resolves to 0 Hotels" in item for item in problems)
    assert any("ambiguous.txt resolves to 2 Hotels" in item for item in problems)
    assert any("shared-a.txt, shared-b.txt" in item for item in problems)


def test_report_readiness_includes_hotel_provenance_failures(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setattr(
        retrieval_setup,
        "graph_counts",
        Mock(return_value=(2, 2, {"Hotel": 1}, {})),
    )
    monkeypatch.setattr(
        retrieval_setup, "build_health_problems", Mock(return_value=[])
    )
    monkeypatch.setattr(
        retrieval_setup,
        "source_fixture_problems",
        Mock(return_value=[]),
    )
    monkeypatch.setattr(
        retrieval_setup,
        "chicago_filter_records",
        Mock(
            return_value=[
                {
                    "hotel_name": retrieval_setup.CHICAGO_QUALIFIER,
                    "qualifies": True,
                },
                {
                    "hotel_name": retrieval_setup.CHICAGO_EXCLUSION,
                    "qualifies": False,
                },
            ]
        ),
    )
    monkeypatch.setattr(
        retrieval_setup,
        "chicago_filter_problems",
        Mock(return_value=[]),
    )
    monkeypatch.setattr(
        retrieval_setup,
        "hotel_provenance_problems",
        Mock(return_value=["hotel provenance is incomplete"]),
    )

    problems = retrieval_setup.report_readiness(Mock(), expected_documents=2)
    output = capsys.readouterr().out

    assert "Hotel count is 1, expected 2" in problems
    assert "hotel provenance is incomplete" in problems
    assert "Chicago candidates: 2" in output
    assert "Chicago spa-and-pool qualifiers: ['Lakeview Horizon Suites']" in output
    assert "Chicago exclusions: ['Windward Mile Tower']" in output


def test_restored_graph_reconciliation_proves_chicago_hotels_share_wifi(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "corpus.zip"
    with ZipFile(archive, "w") as corpus:
        corpus.writestr(
            "hotel-chicago-001.txt",
            "# Windward Mile Tower\n\n## Hotel Amenities\n\n"
            "- Complimentary High-Speed Wifi\n",
        )
        corpus.writestr(
            "hotel-chicago-002.txt",
            "# Lakeview Horizon Suites\n\n## Hotel Amenities\n\n"
            "- Complimentary High-Speed Wifi\n- Outdoor Swimming Pool\n",
        )

    neo4j_session = Mock()
    neo4j_session.__enter__ = Mock(return_value=neo4j_session)
    neo4j_session.__exit__ = Mock(return_value=False)
    neo4j_session.run.side_effect = [
        [
            {"filename": "hotel-chicago-001.txt", "document_count": 1},
            {"filename": "hotel-chicago-002.txt", "document_count": 1},
        ],
        [
            {
                "relationship_id": "offer-1",
                "relationship_source_filename": "hotel-chicago-001.txt",
                "amenity_name": "Complimentary High-Speed Wifi",
                "provenance_filenames": ["hotel-chicago-001.txt"],
            },
            {
                "relationship_id": "offer-2",
                "relationship_source_filename": "hotel-chicago-002.txt",
                "amenity_name": "Complimentary High-Speed Wifi",
                "provenance_filenames": ["hotel-chicago-002.txt"],
            },
            {
                "relationship_id": "offer-3",
                "relationship_source_filename": "hotel-chicago-002.txt",
                "amenity_name": "Outdoor Swimming Pool",
                "provenance_filenames": ["hotel-chicago-002.txt"],
            },
        ],
        [
            {"amenity_name": "Complimentary High-Speed Wifi", "node_count": 1},
            {"amenity_name": "Outdoor Swimming Pool", "node_count": 1},
        ],
    ]
    driver = Mock()
    driver.session.return_value = neo4j_session
    problems = validate_graph_amenities.amenity_reconciliation_problems(
        driver, "neo4j", archive
    )

    assert problems == []
    assert neo4j_session.run.call_count == 3


def test_restored_graph_reconciliation_reports_all_integrity_defects(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "corpus.zip"
    with ZipFile(archive, "w") as corpus:
        corpus.writestr(
            "hotel-a.txt",
            "# Hotel A\n\n## Hotel Amenities\n\n- Shared WiFi\n- Pool\n",
        )

    neo4j_session = Mock()
    neo4j_session.__enter__ = Mock(return_value=neo4j_session)
    neo4j_session.__exit__ = Mock(return_value=False)
    neo4j_session.run.side_effect = [
        [{"filename": "hotel-a.txt", "document_count": 1}],
        [
            {
                "relationship_id": "offer-1",
                "relationship_source_filename": "wrong-source.txt",
                "amenity_name": "Shared WiFi",
                "provenance_filenames": ["hotel-a.txt"],
            },
            {
                "relationship_id": "offer-2",
                "relationship_source_filename": "hotel-a.txt",
                "amenity_name": "Shared WiFi",
                "provenance_filenames": ["hotel-a.txt"],
            },
            {
                "relationship_id": "offer-3",
                "relationship_source_filename": "hotel-a.txt",
                "amenity_name": "Invented Spa",
                "provenance_filenames": ["hotel-a.txt"],
            },
            {
                "relationship_id": "offer-4",
                "relationship_source_filename": "orphan.txt",
                "amenity_name": "Shared WiFi",
                "provenance_filenames": [],
            },
        ],
        [
            {"amenity_name": "Shared WiFi", "node_count": 2},
            {"amenity_name": "Invented Spa", "node_count": 1},
        ],
    ]
    driver = Mock()
    driver.session.return_value = neo4j_session
    problems = validate_graph_amenities.amenity_reconciliation_problems(
        driver, "neo4j", archive
    )

    assert any("1 source amenity assertions are missing" in item for item in problems)
    assert any("1 unexpected amenity assertions exist" in item for item in problems)
    assert any("2 OFFERS_AMENITY relationships" in item for item in problems)
    assert any("wrong-source.txt" in item for item in problems)
    assert any(
        "resolves through its Hotel to 0 source Documents" in item for item in problems
    )
    assert any("unexpected Amenity nodes" in item for item in problems)
    assert any("has 2 nodes, expected 1 shared node" in item for item in problems)


def test_restored_graph_reconciliation_enforces_expected_source_set(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "corpus.zip"
    with ZipFile(archive, "w") as corpus:
        corpus.writestr(
            "hotel-a.txt",
            "# Hotel A\n\n## Hotel Amenities\n\n- Shared WiFi\n",
        )
        corpus.writestr(
            "hotel-b.txt",
            "# Hotel B\n\n## Hotel Amenities\n\n- Pool\n",
        )

    neo4j_session = Mock()
    neo4j_session.__enter__ = Mock(return_value=neo4j_session)
    neo4j_session.__exit__ = Mock(return_value=False)
    neo4j_session.run.side_effect = [
        [{"filename": "hotel-a.txt", "document_count": 1}],
        [
            {
                "relationship_id": "offer-1",
                "relationship_source_filename": "hotel-a.txt",
                "amenity_name": "Shared WiFi",
                "provenance_filenames": ["hotel-a.txt"],
            }
        ],
        [{"amenity_name": "Shared WiFi", "node_count": 1}],
    ]
    driver = Mock()
    driver.session.return_value = neo4j_session

    problems = validate_graph_amenities.amenity_reconciliation_problems(
        driver,
        "neo4j",
        archive,
        expected_filenames={"hotel-a.txt", "hotel-b.txt"},
    )

    assert any("1 expected source Documents are missing" in item for item in problems)
    assert any("hotel-b.txt: Pool" in item for item in problems)


def test_release_source_contract_omits_only_held_out_documents() -> None:
    corpus_archive = SHARED_DIR / "hotel-faqs.zip"
    with ZipFile(corpus_archive) as corpus:
        archive_names = set(corpus.namelist())

    full = validate_graph_amenities.expected_source_filenames(archive_names, "full")
    prebuilt = validate_graph_amenities.expected_source_filenames(
        archive_names, "prebuilt"
    )

    assert len(full) == 300
    assert len(prebuilt) == 295
    assert full - prebuilt == set(prepare_graph.HELD_OUT_DOCUMENTS)


def _patch_shared_build_dependencies(
    monkeypatch,
    driver: Mock,
    parsed: list[ParsedAmenities],
) -> Mock:
    materialize = Mock(return_value=sum(len(item.names) for item in parsed))
    monkeypatch.setattr(graph_builder, "connect", Mock(return_value=driver))
    monkeypatch.setattr(graph_builder, "parse_amenity_lists", Mock(return_value=parsed))
    monkeypatch.setattr(graph_builder, "build_pipeline", Mock(return_value=Mock()))
    monkeypatch.setattr(graph_builder, "ingest", AsyncMock(return_value=[]))
    monkeypatch.setattr(graph_builder, "retry_failures", AsyncMock(return_value=[]))
    monkeypatch.setattr(graph_builder, "check_schema_held", Mock(return_value=[]))
    monkeypatch.setattr(graph_builder, "check_source_hotels", Mock(return_value=[]))
    monkeypatch.setattr(
        graph_builder, "check_amenity_assertions", Mock(return_value=[])
    )
    monkeypatch.setattr(
        graph_builder, "check_documents_addressable", Mock(return_value=[])
    )
    monkeypatch.setattr(graph_builder, "materialize_amenity_lists", materialize)
    monkeypatch.setattr(graph_builder, "ensure_retrieval_indexes", Mock())
    monkeypatch.setattr(graph_builder, "report_readiness", Mock(return_value=[]))
    monkeypatch.setattr(graph_builder, "report", Mock())
    return materialize


def test_full_build_materializes_parsed_amenities_after_extraction(
    monkeypatch,
) -> None:
    paths = [Path("one.txt"), Path("two.txt")]
    parsed = [
        ParsedAmenities("one.txt", ("WiFi",)),
        ParsedAmenities("two.txt", ("WiFi", "Pool")),
    ]
    driver = Mock()
    materialize = _patch_shared_build_dependencies(monkeypatch, driver, parsed)
    monkeypatch.setattr(graph_builder, "missing_source_fixtures", Mock(return_value=[]))
    monkeypatch.setattr(graph_builder, "clear_extracted_graph", Mock())
    monkeypatch.setattr(
        graph_builder,
        "snapshot_chunk_ids",
        Mock(side_effect=[set(), {"canary-chunk"}]),
    )
    monkeypatch.setattr(graph_builder, "count_documents", Mock(return_value=2))
    monkeypatch.setattr(graph_builder, "count_chunks", Mock(return_value=2))

    result = asyncio.run(graph_builder.run_build(paths, "test full build"))

    assert result == 0
    materialize.assert_called_once_with(driver, parsed)
    graph_builder.check_amenity_assertions.assert_called_once_with(driver, parsed)
    assert graph_builder.check_source_hotels.call_count == 2
    driver.close.assert_called_once_with()


def test_additive_build_materializes_the_same_parsed_amenities(
    monkeypatch,
) -> None:
    paths = [Path("held-out.txt")]
    parsed = [ParsedAmenities("held-out.txt", ("WiFi", "Pool"))]
    driver = Mock()
    materialize = _patch_shared_build_dependencies(monkeypatch, driver, parsed)
    monkeypatch.setattr(graph_builder, "clear_document", Mock())
    monkeypatch.setattr(graph_builder, "count_documents", Mock(return_value=295))
    monkeypatch.setattr(
        graph_builder,
        "snapshot_chunk_ids",
        Mock(side_effect=[set(), {"held-out-chunk"}]),
    )

    result = asyncio.run(graph_builder.run_additive_build(paths, "test additive"))

    assert result == 0
    materialize.assert_called_once_with(driver, parsed)
    graph_builder.check_amenity_assertions.assert_called_once_with(driver, parsed)
    graph_builder.clear_document.assert_called_once_with(driver, "held-out.txt")
    driver.close.assert_called_once_with()


def test_malformed_amenity_source_stops_before_the_graph_is_opened(
    tmp_path: Path,
    monkeypatch,
) -> None:
    path = tmp_path / "broken.txt"
    path.write_text("# Hotel without an amenity section\n", encoding="utf-8")
    connect = Mock()
    monkeypatch.setattr(graph_builder, "connect", connect)
    monkeypatch.setattr(graph_builder, "missing_source_fixtures", Mock(return_value=[]))

    result = asyncio.run(graph_builder.run_build([path], "broken build"))

    assert result == 1
    connect.assert_not_called()


def test_prebuilt_selection_omits_only_the_five_live_documents(
    tmp_path: Path,
    monkeypatch,
) -> None:
    corpus_archive = SHARED_DIR / "hotel-faqs.zip"
    with ZipFile(corpus_archive) as corpus:
        filenames = sorted(name for name in corpus.namelist() if name.endswith(".txt"))
        prebuilt_amenities = [
            parse_amenity_section(corpus.read(name).decode("utf-8"), name)
            for name in filenames
            if name not in prepare_graph.HELD_OUT_DOCUMENTS
        ]
    for filename in filenames:
        (tmp_path / filename).touch()
    monkeypatch.setattr(prepare_graph, "DATA_DIR", tmp_path)

    selected = prepare_graph.selected_paths("prebuilt")

    assert len(selected) == 295
    assert {path.name for path in selected}.isdisjoint(prepare_graph.HELD_OUT_DOCUMENTS)
    assert sum(len(parsed.names) for parsed in prebuilt_amenities) == 1_606
    assert len({name for parsed in prebuilt_amenities for name in parsed.names}) == 65
    authored_pool_names = {
        name
        for parsed in prebuilt_amenities
        for name in parsed.names
        if "pool" in name.casefold()
    }
    pool_sources = sum(
        bool(authored_pool_names.intersection(parsed.names))
        for parsed in prebuilt_amenities
    )

    assert authored_pool_names == set(POOL_AMENITY_NAMES)
    assert pool_sources == 172


def test_prebuilt_selection_rejects_an_incomplete_source_corpus(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for filename in prepare_graph.HELD_OUT_DOCUMENTS[1:]:
        (tmp_path / filename).touch()
    monkeypatch.setattr(prepare_graph, "DATA_DIR", tmp_path)

    with pytest.raises(prepare_graph.SourceSelectionError, match="expected 300"):
        prepare_graph.selected_paths("prebuilt")
