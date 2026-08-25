# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline regressions for persistent, provenance-checked graph resumes."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

from workshop.amenities import ParsedAmenities

CONNECTED_CONTEXT = (
    Path(__file__).resolve().parents[2] / "notebooks" / "02-connected-context"
)
sys.path.insert(0, str(CONNECTED_CONTEXT))

import graph_builder


def _driver_with_records(records: list[dict[str, object]]) -> Mock:
    neo4j_session = Mock()
    neo4j_session.__enter__ = Mock(return_value=neo4j_session)
    neo4j_session.__exit__ = Mock(return_value=False)
    neo4j_session.run.return_value = records
    driver = Mock()
    driver.session.return_value = neo4j_session
    return driver


def test_resume_reuses_only_exact_unshared_provenance(tmp_path: Path) -> None:
    paths = [tmp_path / f"{name}.txt" for name in "abcde"]
    for path in paths:
        path.write_text(f"source for {path.stem}", encoding="utf-8")

    records = []
    for path in paths:
        records.append(
            {
                "filename": path.name,
                "expected_source_sha256": graph_builder.source_sha256(path),
                "document_count": 1,
                "chunk_count": 1,
                "hotel_count": 1,
                "source_sha256_values": [graph_builder.source_sha256(path)],
                "build_contract_values": ["current-contract"],
                "hotel_element_ids": [f"hotel-{path.stem}"],
                "hotel_source_document_count": 1,
            }
        )
    records[1]["source_sha256_values"] = ["stale-source"]
    records[2]["chunk_count"] = 2
    records[3]["hotel_element_ids"] = ["shared-hotel"]
    records[4]["hotel_element_ids"] = ["shared-hotel"]
    records[3]["hotel_source_document_count"] = 2
    records[4]["hotel_source_document_count"] = 2

    complete, pending = graph_builder.resumable_paths(
        _driver_with_records(records), paths, "current-contract"
    )

    assert complete == [paths[0]]
    assert pending == paths[1:]


def test_resume_rejects_exact_source_whose_hotel_is_shared_with_stale_source(
    tmp_path: Path,
) -> None:
    exact = tmp_path / "exact.txt"
    stale = tmp_path / "stale.txt"
    exact.write_text("current exact source", encoding="utf-8")
    stale.write_text("current stale source", encoding="utf-8")
    records = [
        {
            "filename": exact.name,
            "expected_source_sha256": graph_builder.source_sha256(exact),
            "document_count": 1,
            "chunk_count": 1,
            "hotel_count": 1,
            "source_sha256_values": [graph_builder.source_sha256(exact)],
            "build_contract_values": ["current-contract"],
            "hotel_element_ids": ["shared-hotel"],
            "hotel_source_document_count": 2,
        },
        {
            "filename": stale.name,
            "expected_source_sha256": graph_builder.source_sha256(stale),
            "document_count": 1,
            "chunk_count": 1,
            "hotel_count": 1,
            "source_sha256_values": ["old-source-digest"],
            "build_contract_values": ["current-contract"],
            "hotel_element_ids": ["shared-hotel"],
            "hotel_source_document_count": 2,
        },
    ]

    complete, pending = graph_builder.resumable_paths(
        _driver_with_records(records), [exact, stale], "current-contract"
    )

    assert complete == []
    assert pending == [exact, stale]


def test_ingest_records_source_and_build_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "hotel-a.txt"
    path.write_text("hotel source", encoding="utf-8")
    pipeline = Mock()
    pipeline.run_async = AsyncMock()
    monkeypatch.setattr(graph_builder, "build_contract", Mock(return_value="contract"))

    failures = asyncio.run(graph_builder.ingest(pipeline, [path]))

    assert failures == []
    metadata = pipeline.run_async.await_args.kwargs["document_metadata"]
    assert metadata["source_filename"] == path.name
    assert metadata["source_sha256"] == graph_builder.source_sha256(path)
    assert metadata["build_contract"] == "contract"


def test_resume_clears_only_pending_and_runs_final_gates_over_all_sources(
    monkeypatch,
) -> None:
    complete = Path("complete.txt")
    pending = Path("pending.txt")
    paths = [complete, pending]
    parsed = [
        ParsedAmenities(complete.name, ("WiFi",)),
        ParsedAmenities(pending.name, ("Pool",)),
    ]
    driver = Mock()
    pipeline = Mock()

    monkeypatch.setattr(graph_builder, "missing_source_fixtures", Mock(return_value=[]))
    monkeypatch.setattr(graph_builder, "parse_amenity_lists", Mock(return_value=parsed))
    monkeypatch.setattr(graph_builder, "connect", Mock(return_value=driver))
    monkeypatch.setattr(
        graph_builder,
        "resumable_paths",
        Mock(return_value=([complete], [pending])),
    )
    monkeypatch.setattr(graph_builder, "build_contract", Mock(return_value="contract"))
    monkeypatch.setattr(graph_builder, "clear_document", Mock())
    monkeypatch.setattr(graph_builder, "clear_extracted_graph", Mock())
    monkeypatch.setattr(graph_builder, "build_pipeline", Mock(return_value=pipeline))
    ingest = AsyncMock(return_value=[])
    monkeypatch.setattr(graph_builder, "ingest", ingest)
    monkeypatch.setattr(graph_builder, "retry_failures", AsyncMock(return_value=[]))
    monkeypatch.setattr(graph_builder, "count_documents", Mock(return_value=2))
    monkeypatch.setattr(graph_builder, "count_chunks", Mock(return_value=2))
    monkeypatch.setattr(
        graph_builder, "check_documents_addressable", Mock(return_value=[])
    )
    monkeypatch.setattr(graph_builder, "check_source_hotels", Mock(return_value=[]))
    monkeypatch.setattr(
        graph_builder, "materialize_amenity_lists", Mock(return_value=2)
    )
    monkeypatch.setattr(
        graph_builder, "check_amenity_assertions", Mock(return_value=[])
    )
    monkeypatch.setattr(graph_builder, "ensure_retrieval_indexes", Mock())
    monkeypatch.setattr(graph_builder, "report_readiness", Mock(return_value=[]))
    monkeypatch.setattr(graph_builder, "report", Mock())

    result = asyncio.run(graph_builder.run_build(paths, "resume", resume=True))

    assert result == 0
    graph_builder.clear_document.assert_called_once_with(driver, pending.name)
    graph_builder.clear_extracted_graph.assert_not_called()
    ingest.assert_awaited_once_with(pipeline, [pending])
    graph_builder.check_documents_addressable.assert_called_once_with(driver, paths)
    graph_builder.check_source_hotels.assert_called_once_with(driver, paths)
    graph_builder.report_readiness.assert_called_once_with(
        driver, expected_documents=len(paths)
    )
