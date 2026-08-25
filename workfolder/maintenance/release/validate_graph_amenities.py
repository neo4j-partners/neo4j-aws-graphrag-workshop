# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Reconcile a restored graph's amenities with the committed source archive.

Used for: maintainer validation of restored or release-candidate graph data.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from neo4j import Driver, GraphDatabase

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
if str(NOTEBOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(NOTEBOOKS_DIR))
CONNECTED_CONTEXT_DIR = NOTEBOOKS_DIR / "02-connected-context"
if str(CONNECTED_CONTEXT_DIR) not in sys.path:
    sys.path.insert(0, str(CONNECTED_CONTEXT_DIR))

from graph_config import HELD_OUT_DOCUMENTS
from workshop.amenities import AmenitySectionError, parse_amenity_section
from workshop.graph_connection import (
    graph_database,
    neo4j_auth,
    neo4j_uri,
    require_neo4j_env,
)

CORPUS_ARCHIVE = CONNECTED_CONTEXT_DIR / "hotel-faqs.zip"

DOCUMENT_QUERY = """
CYPHER 25
MATCH (document:Document)
RETURN document.source_filename AS filename,
       count(document) AS document_count
ORDER BY filename
""".strip()

OFFER_QUERY = """
CYPHER 25
MATCH (hotel)-[offer:OFFERS_AMENITY]->(amenity:Amenity)
OPTIONAL MATCH (hotel)-[:FROM_CHUNK]->(:Chunk)-[:FROM_DOCUMENT]->(document:Document)
RETURN elementId(offer) AS relationship_id,
       offer.source_filename AS relationship_source_filename,
       amenity.name AS amenity_name,
       collect(DISTINCT document.source_filename) AS provenance_filenames
ORDER BY relationship_source_filename, amenity_name, relationship_id
""".strip()

AMENITY_QUERY = """
CYPHER 25
MATCH (amenity:Amenity)
RETURN amenity.name AS amenity_name,
       count(amenity) AS node_count
ORDER BY amenity_name
""".strip()


def _read_graph_rows(
    driver: Driver,
    database: str,
) -> tuple[list[Any], list[Any], list[Any]]:
    with driver.session(database=database) as session:
        documents = list(session.run(DOCUMENT_QUERY))
        offers = list(session.run(OFFER_QUERY))
        amenities = list(session.run(AMENITY_QUERY))
    return documents, offers, amenities


def expected_source_filenames(archive_names: set[str], mode: str) -> set[str]:
    """Return the exact source contract for a release artifact mode."""
    corpus_sources = {name for name in archive_names if name.endswith(".txt")}
    if mode == "full":
        return corpus_sources
    if mode == "prebuilt":
        return corpus_sources - set(HELD_OUT_DOCUMENTS)
    raise ValueError(f"unsupported artifact mode: {mode}")


def amenity_reconciliation_problems(
    driver: Driver,
    database: str,
    corpus_archive: Path = CORPUS_ARCHIVE,
    expected_filenames: set[str] | None = None,
) -> list[str]:
    """Return exact source-to-graph reconciliation defects.

    The graph supplies the loaded source filenames. The same validator can
    therefore check lite, prebuilt, and complete artifacts without receiving
    the original build paths.
    """
    document_rows, offer_rows, amenity_rows = _read_graph_rows(driver, database)

    problems: list[str] = []
    source_filenames: set[str] = set()
    for row in document_rows:
        filename = row["filename"]
        document_count = row["document_count"]
        if not filename:
            problems.append(
                f"{document_count} Document node(s) have no source_filename"
            )
            continue
        if document_count != 1:
            problems.append(
                f"{filename} has {document_count} Document nodes, expected 1"
            )
            continue
        source_filenames.add(filename)

    try:
        with ZipFile(corpus_archive) as corpus:
            archive_names = set(corpus.namelist())
            missing_sources = source_filenames - archive_names
            if missing_sources:
                examples = ", ".join(sorted(missing_sources)[:5])
                problems.append(
                    f"{len(missing_sources)} graph source files are absent from the "
                    f"committed corpus archive; examples: {examples}"
                )
            if expected_filenames is not None:
                missing_documents = expected_filenames - source_filenames
                unexpected_documents = source_filenames - expected_filenames
                if missing_documents:
                    examples = ", ".join(sorted(missing_documents)[:5])
                    problems.append(
                        f"{len(missing_documents)} expected source Documents are "
                        f"missing; examples: {examples}"
                    )
                if unexpected_documents:
                    examples = ", ".join(sorted(unexpected_documents)[:5])
                    problems.append(
                        f"{len(unexpected_documents)} unexpected source Documents "
                        f"exist; examples: {examples}"
                    )
                contract_filenames = expected_filenames
            else:
                contract_filenames = source_filenames
            expected = {
                (filename, amenity_name)
                for filename in contract_filenames & archive_names
                for amenity_name in parse_amenity_section(
                    corpus.read(filename).decode("utf-8"), filename
                ).names
            }
    except (
        BadZipFile,
        FileNotFoundError,
        UnicodeDecodeError,
        AmenitySectionError,
    ) as exc:
        problems.append(f"could not read authoritative amenity sources: {exc}")
        return problems

    actual_pairs: list[tuple[str, str]] = []
    for row in offer_rows:
        relationship_id = row["relationship_id"]
        relationship_source = row["relationship_source_filename"]
        amenity_name = row["amenity_name"]
        provenance_filenames = row["provenance_filenames"]
        if not amenity_name:
            problems.append(
                f"OFFERS_AMENITY relationship {relationship_id} targets an "
                "Amenity without a name"
            )
            continue
        if len(provenance_filenames) != 1:
            problems.append(
                f"OFFERS_AMENITY relationship {relationship_id} for "
                f"{amenity_name!r} resolves through its Hotel to "
                f"{len(provenance_filenames)} source Documents, expected 1"
            )
            continue
        provenance_filename = provenance_filenames[0]
        if relationship_source != provenance_filename:
            problems.append(
                f"OFFERS_AMENITY relationship {relationship_id} has "
                f"source_filename {relationship_source!r}, expected "
                f"{provenance_filename!r} from Hotel provenance"
            )
        actual_pairs.append((provenance_filename, amenity_name))

    pair_counts = Counter(actual_pairs)
    actual = set(actual_pairs)
    missing = expected - actual
    unexpected = actual - expected
    if missing:
        examples = ", ".join(
            f"{filename}: {name}" for filename, name in sorted(missing)[:5]
        )
        problems.append(
            f"{len(missing)} source amenity assertions are missing; examples: "
            f"{examples}"
        )
    if unexpected:
        examples = ", ".join(
            f"{filename}: {name}"
            for filename, name in sorted(
                unexpected,
                key=lambda pair: (str(pair[0]), str(pair[1])),
            )[:5]
        )
        problems.append(
            f"{len(unexpected)} unexpected amenity assertions exist; examples: "
            f"{examples}"
        )

    for (filename, amenity_name), relationship_count in sorted(pair_counts.items()):
        if relationship_count != 1:
            problems.append(
                f"{filename}: {amenity_name} has {relationship_count} "
                "OFFERS_AMENITY relationships, "
                "expected 1"
            )

    expected_names = {name for _, name in expected}
    actual_names = {
        row["amenity_name"] for row in amenity_rows if row["amenity_name"] is not None
    }
    missing_names = expected_names - actual_names
    unexpected_names = actual_names - expected_names
    if missing_names:
        problems.append(
            "Amenity nodes are missing for: " + ", ".join(sorted(missing_names)[:5])
        )
    if unexpected_names:
        problems.append(
            "unexpected Amenity nodes exist for: "
            + ", ".join(sorted(unexpected_names)[:5])
        )
    for row in amenity_rows:
        if not row["amenity_name"]:
            problems.append(
                f"{row['node_count']} Amenity node(s) have no canonical name"
            )
            continue
        if row["node_count"] != 1:
            problems.append(
                f"Amenity {row['amenity_name']!r} has {row['node_count']} nodes, "
                "expected 1 shared node"
            )

    print(
        f"Amenity reconciliation: {len(source_filenames)} sources, "
        f"{len(expected_names)} names, {len(offer_rows)} graph relationships, "
        f"{len(actual)} distinct graph assertions, "
        f"{len(expected)} expected assertions"
    )
    return problems


def parse_args() -> argparse.Namespace:
    """Parse the release artifact contract to validate."""
    parser = argparse.ArgumentParser(
        description="Reconcile a restored graph with the committed amenity sources."
    )
    parser.add_argument(
        "--mode",
        choices=("prebuilt", "full"),
        default="prebuilt",
        help="Expected artifact source set. Default: prebuilt.",
    )
    return parser.parse_args()


def main() -> int:
    """Validate the configured restored graph and print actionable defects."""
    args = parse_args()
    require_neo4j_env()
    try:
        with ZipFile(CORPUS_ARCHIVE) as corpus:
            expected_filenames = expected_source_filenames(
                set(corpus.namelist()), args.mode
            )
    except (BadZipFile, FileNotFoundError) as exc:
        print(f"Could not read the committed corpus archive: {exc}")
        return 1
    with GraphDatabase.driver(neo4j_uri(), auth=neo4j_auth()) as driver:
        problems = amenity_reconciliation_problems(
            driver,
            graph_database(),
            expected_filenames=expected_filenames,
        )
    if problems:
        print("Amenity reconciliation failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("Amenity reconciliation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
