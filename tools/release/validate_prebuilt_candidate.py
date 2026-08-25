# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Validate release-specific invariants on a restored prebuilt candidate.

Used for: maintainer verification that a prebuilt graph dump is releasable.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from neo4j import Driver, GraphDatabase

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
if str(NOTEBOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(NOTEBOOKS_DIR))

from workshop.graph_connection import (
    graph_database,
    neo4j_auth,
    neo4j_uri,
    require_neo4j_env,
)

EXPECTED_COUNTS = {
    "documents": 295,
    "chunks": 295,
    "hotels": 295,
    "amenities": 65,
    "offer_relationships": 1_606,
    "amenity_assertions": 1_606,
    "pool_sources": 172,
}

HISTORICAL_MISSING_HOTEL_SOURCES = (
    "hotel-austin-002.txt",
    "hotel-mumbai-001.txt",
    "hotel-sanfrancisco-004.txt",
    "hotel-tucson-001.txt",
)

CROSS_CITY_DUPLICATE_HOTEL_NAMES = {
    "Riverside Crossing Suites": (
        "hotel-dallas-002.txt",
        "hotel-windsor-002.txt",
    ),
    "Riverside Lodge": (
        "hotel-boise-002.txt",
        "hotel-calgary-002.txt",
    ),
    "Riverway Lodge": (
        "hotel-minneapolis-002.txt",
        "hotel-saskatoon-002.txt",
    ),
    "Waterway Inn": (
        "hotel-houston-002.txt",
        "hotel-kitchener-002.txt",
    ),
}

CHICAGO_SOURCES = (
    "hotel-chicago-001.txt",
    "hotel-chicago-002.txt",
)
CHICAGO_WIFI = "Complimentary High-Speed Wifi"

COUNT_QUERY = """
CYPHER 25
CALL () { MATCH (document:Document) RETURN count(document) AS documents }
CALL () { MATCH (chunk:Chunk) RETURN count(chunk) AS chunks }
CALL () { MATCH (hotel:Hotel) RETURN count(hotel) AS hotels }
CALL () { MATCH (amenity:Amenity) RETURN count(amenity) AS amenities }
CALL () {
  MATCH ()-[offer:OFFERS_AMENITY]->(amenity:Amenity)
  RETURN count(offer) AS offer_relationships,
         count(DISTINCT [offer.source_filename, amenity.name])
           AS amenity_assertions
}
CALL () {
  MATCH (document:Document)<-[:FROM_DOCUMENT]-(:Chunk)<-[:FROM_CHUNK]-
        (:Hotel)-[:OFFERS_AMENITY]->(amenity:Amenity)
  WHERE toLower(amenity.name) CONTAINS 'pool'
  RETURN count(DISTINCT document) AS pool_sources
}
RETURN documents, chunks, hotels, amenities, offer_relationships,
       amenity_assertions, pool_sources
""".strip()

INVALID_DOCUMENT_QUERY = """
CYPHER 25
MATCH (document:Document)
OPTIONAL MATCH (chunk:Chunk)-[:FROM_DOCUMENT]->(document)
OPTIONAL MATCH (hotel:Hotel)-[:FROM_CHUNK]->(chunk)
WITH document, count(DISTINCT chunk) AS chunk_count,
     count(DISTINCT hotel) AS hotel_count
WHERE document.source_filename IS NULL OR chunk_count <> 1 OR hotel_count <> 1
RETURN coalesce(
         document.source_filename,
         '<Document ' + elementId(document) + '>'
       ) AS filename,
       chunk_count, hotel_count
ORDER BY filename
""".strip()

INVALID_HOTEL_QUERY = """
CYPHER 25
MATCH (hotel:Hotel)
OPTIONAL MATCH (hotel)-[:FROM_CHUNK]->(:Chunk)-[:FROM_DOCUMENT]->
               (document:Document)
WITH hotel, count(DISTINCT document) AS document_count,
     collect(DISTINCT document.source_filename) AS source_filenames
WHERE document_count <> 1
RETURN coalesce(hotel.name, '<Hotel ' + elementId(hotel) + '>') AS hotel,
       document_count, source_filenames
ORDER BY hotel
""".strip()

INVALID_OFFER_QUERY = """
CYPHER 25
MATCH (source)-[offer:OFFERS_AMENITY]->(target)
OPTIONAL MATCH (source)-[:FROM_CHUNK]->(:Chunk)-[:FROM_DOCUMENT]->
               (document:Document)
WITH source, offer, target, count(DISTINCT document) AS document_count,
     collect(DISTINCT document.source_filename) AS source_filenames
WHERE NOT (source:Hotel) OR NOT (target:Amenity) OR document_count <> 1
   OR offer.source_filename IS NULL
   OR NOT offer.source_filename IN source_filenames
RETURN elementId(offer) AS relationship_id, labels(source) AS source_labels,
       labels(target) AS target_labels, offer.source_filename AS offer_source,
       document_count, source_filenames
ORDER BY relationship_id
""".strip()

SOURCE_HOTEL_QUERY = """
CYPHER 25
UNWIND $filenames AS filename
OPTIONAL MATCH (document:Document {source_filename: filename})
OPTIONAL MATCH (hotel:Hotel)-[:FROM_CHUNK]->(:Chunk)-[:FROM_DOCUMENT]->(document)
RETURN filename, count(DISTINCT document) AS document_count,
       count(DISTINCT hotel) AS hotel_count
ORDER BY filename
""".strip()

DUPLICATE_NAME_QUERY = """
CYPHER 25
UNWIND $expected AS item
OPTIONAL MATCH (hotel:Hotel {name: item.name})-[:FROM_CHUNK]->
               (:Chunk)-[:FROM_DOCUMENT]->(document:Document)
RETURN item.name AS name, item.filenames AS expected_filenames,
       count(DISTINCT hotel) AS hotel_count,
       collect(DISTINCT document.source_filename) AS actual_filenames
ORDER BY name
""".strip()

CHICAGO_WIFI_QUERY = """
CYPHER 25
UNWIND $filenames AS filename
OPTIONAL MATCH (document:Document {source_filename: filename})<-
               [:FROM_DOCUMENT]-(:Chunk)<-[:FROM_CHUNK]-(hotel:Hotel)
OPTIONAL MATCH (hotel)-[:OFFERS_AMENITY]->(amenity:Amenity {name: $wifi})
RETURN filename, count(DISTINCT hotel) AS hotel_count,
       collect(DISTINCT elementId(amenity)) AS wifi_element_ids
ORDER BY filename
""".strip()


def _rows(result: Any) -> list[dict[str, Any]]:
    return [dict(record) for record in result]


def read_candidate_facts(driver: Driver, database: str) -> dict[str, Any]:
    """Read every release gate from the restored candidate."""
    expected_duplicates = [
        {"name": name, "filenames": list(filenames)}
        for name, filenames in CROSS_CITY_DUPLICATE_HOTEL_NAMES.items()
    ]
    with driver.session(database=database) as session:
        count_record = session.run(COUNT_QUERY).single()
        if count_record is None:
            raise RuntimeError("candidate count query returned no record")
        return {
            "counts": dict(count_record),
            "invalid_documents": _rows(session.run(INVALID_DOCUMENT_QUERY)),
            "invalid_hotels": _rows(session.run(INVALID_HOTEL_QUERY)),
            "invalid_offers": _rows(session.run(INVALID_OFFER_QUERY)),
            "historical_sources": _rows(
                session.run(
                    SOURCE_HOTEL_QUERY,
                    filenames=list(HISTORICAL_MISSING_HOTEL_SOURCES),
                )
            ),
            "duplicate_names": _rows(
                session.run(DUPLICATE_NAME_QUERY, expected=expected_duplicates)
            ),
            "chicago_wifi": _rows(
                session.run(
                    CHICAGO_WIFI_QUERY,
                    filenames=list(CHICAGO_SOURCES),
                    wifi=CHICAGO_WIFI,
                )
            ),
        }


def candidate_contract_problems(facts: dict[str, Any]) -> list[str]:
    """Return release-contract defects from candidate facts."""
    problems: list[str] = []
    counts = facts["counts"]
    for name, expected in EXPECTED_COUNTS.items():
        actual = counts.get(name)
        if actual != expected:
            problems.append(f"{name} is {actual}, expected {expected}")

    for row in facts["invalid_documents"]:
        problems.append(
            f"{row['filename']} has {row['chunk_count']} Chunks and "
            f"{row['hotel_count']} Hotels, expected exactly one of each"
        )
    for row in facts["invalid_hotels"]:
        problems.append(
            f"{row['hotel']} resolves to {row['document_count']} Documents "
            f"through {sorted(row['source_filenames'])}, expected exactly one"
        )
    for row in facts["invalid_offers"]:
        problems.append(
            f"OFFERS_AMENITY {row['relationship_id']} has source labels "
            f"{row['source_labels']}, target labels {row['target_labels']}, "
            f"source_filename {row['offer_source']!r}, and provenance "
            f"{sorted(row['source_filenames'])}"
        )

    historical = {row["filename"]: row for row in facts["historical_sources"]}
    for filename in HISTORICAL_MISSING_HOTEL_SOURCES:
        row = historical.get(filename)
        if row is None or row["document_count"] != 1 or row["hotel_count"] != 1:
            document_count = None if row is None else row["document_count"]
            hotel_count = None if row is None else row["hotel_count"]
            problems.append(
                f"historical source {filename} has {document_count} Documents and "
                f"{hotel_count} Hotels, expected one of each"
            )

    duplicate_rows = {row["name"]: row for row in facts["duplicate_names"]}
    for name, filenames in CROSS_CITY_DUPLICATE_HOTEL_NAMES.items():
        row = duplicate_rows.get(name)
        actual_filenames = [] if row is None else sorted(row["actual_filenames"])
        hotel_count = None if row is None else row["hotel_count"]
        if hotel_count != 2 or actual_filenames != sorted(filenames):
            problems.append(
                f"duplicate-name pair {name!r} has {hotel_count} Hotels from "
                f"{actual_filenames}, expected two Hotels from {sorted(filenames)}"
            )

    chicago_rows = {row["filename"]: row for row in facts["chicago_wifi"]}
    wifi_ids: set[str] = set()
    for filename in CHICAGO_SOURCES:
        row = chicago_rows.get(filename)
        hotel_count = None if row is None else row["hotel_count"]
        element_ids = [] if row is None else row["wifi_element_ids"]
        if hotel_count != 1 or len(element_ids) != 1:
            problems.append(
                f"Chicago source {filename} has {hotel_count} Hotels and WiFi "
                f"node identities {element_ids}, expected one of each"
            )
        wifi_ids.update(element_ids)
    if len(wifi_ids) != 1:
        problems.append(
            "Chicago Hotels resolve to WiFi node identities "
            f"{sorted(wifi_ids)}, expected one shared node"
        )
    return problems


def main() -> int:
    """Validate the restored candidate and print actionable defects."""
    require_neo4j_env()
    with GraphDatabase.driver(neo4j_uri(), auth=neo4j_auth()) as driver:
        facts = read_candidate_facts(driver, graph_database())
    problems = candidate_contract_problems(facts)
    if problems:
        print("Prebuilt candidate contract failed:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("Prebuilt candidate contract passed:")
    for name, expected in EXPECTED_COUNTS.items():
        print(f"  {name}: {expected}")
    print("  historical missing-Hotel sources: 4 of 4")
    print("  cross-city duplicate-name pairs: 4 of 4")
    print(f"  Chicago shared WiFi node: {CHICAGO_WIFI}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
