# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline contract tests for the four indexes Module 1 prepares."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import Mock

from workshop import contracts, fixtures, retrieval_setup


def _index(
    name: str,
    index_type: str,
    label: str,
    property_name: str,
    *,
    options: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "type": index_type,
        "state": "ONLINE",
        "labelsOrTypes": [label],
        "properties": [property_name],
        "options": options or {},
    }


def _healthy_indexes() -> list[dict[str, object]]:
    return [
        _index(
            contracts.CHUNK_VECTOR_INDEX,
            "VECTOR",
            "Chunk",
            "embedding",
            options={
                "indexConfig": {
                    "vector.dimensions": contracts.EMBEDDING_DIMENSIONS,
                    "vector.similarity_function": "cosine",
                }
            },
        ),
        _index(contracts.CHUNK_FULLTEXT_INDEX, "FULLTEXT", "Chunk", "text"),
        _index(
            contracts.DOCUMENT_SOURCE_FILENAME_INDEX,
            "RANGE",
            "Document",
            "source_filename",
        ),
        _index(contracts.HOTEL_NAME_INDEX, "RANGE", "Hotel", "name"),
    ]


def test_index_contract_accepts_both_retrieval_and_lookup_indexes() -> None:
    assert fixtures._index_problems(_healthy_indexes()) == []


def test_index_contract_requires_both_lookup_indexes() -> None:
    problems = fixtures._index_problems(_healthy_indexes()[:2])

    assert problems == [
        f"missing index {contracts.DOCUMENT_SOURCE_FILENAME_INDEX}",
        f"missing index {contracts.HOTEL_NAME_INDEX}",
    ]


def test_index_contract_checks_lookup_type_label_and_property() -> None:
    records = _healthy_indexes()
    records[2] = _index(
        contracts.DOCUMENT_SOURCE_FILENAME_INDEX,
        "TEXT",
        "Chunk",
        "text",
    )

    problems = fixtures._index_problems(records)

    assert f"index {contracts.DOCUMENT_SOURCE_FILENAME_INDEX} is not RANGE" in problems
    assert (
        f"index {contracts.DOCUMENT_SOURCE_FILENAME_INDEX} targets the wrong label"
        in problems
    )
    assert (
        f"index {contracts.DOCUMENT_SOURCE_FILENAME_INDEX} targets the wrong property"
        in problems
    )


def test_shared_setup_owns_both_idempotent_lookup_index_statements(
    monkeypatch,
) -> None:
    statements: list[tuple[str, dict[str, object]]] = []

    class _Result:
        def consume(self) -> None:
            return None

    class _Session:
        def run(self, statement: str, **parameters: object) -> _Result:
            statements.append((statement, parameters))
            return _Result()

    @contextmanager
    def _fake_session(_driver):
        yield _Session()

    monkeypatch.setattr(retrieval_setup, "create_vector_index", Mock())
    monkeypatch.setattr(retrieval_setup, "create_fulltext_index", Mock())
    monkeypatch.setattr(retrieval_setup, "_session", _fake_session)
    verify = Mock()
    monkeypatch.setattr(retrieval_setup, "verify_retrieval_indexes", verify)

    driver = Mock()
    retrieval_setup.ensure_retrieval_indexes(driver)

    assert statements[:2] == [
        (retrieval_setup.DOCUMENT_SOURCE_FILENAME_INDEX_DDL, {}),
        (retrieval_setup.HOTEL_NAME_INDEX_DDL, {}),
    ]
    assert all("IF NOT EXISTS" in statement for statement, _ in statements[:2])
    assert statements[2] == (
        "CALL db.awaitIndexes($timeout_seconds)",
        {"timeout_seconds": 300},
    )
    verify.assert_called_once_with(driver)
