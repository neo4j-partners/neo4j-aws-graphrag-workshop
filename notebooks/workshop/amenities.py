# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Deterministically parse and materialize authored hotel amenities.

The hotel corpus already contains one structured ``## Hotel Amenities`` list
per document. This module treats those bullet labels as graph identity instead
of asking an LLM to recreate them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from neo4j import Driver, ManagedTransaction
from neo4j.exceptions import Neo4jError

AMENITY_HEADING = "## Hotel Amenities"

_HEADING = re.compile(r"^#{1,6}(?:\s+|$)")
_BULLET = re.compile(r"^-[ \t]+(.*?)\s*$")

AMENITY_NAME_CONSTRAINT = """
CYPHER 25
CREATE CONSTRAINT workshop_amenity_name IF NOT EXISTS
FOR (amenity:Amenity) REQUIRE amenity.name IS UNIQUE
""".strip()

_SOURCE_HOTEL_QUERY = """
CYPHER 25
MATCH (document:Document {source_filename: $source_filename})
OPTIONAL MATCH (chunk:Chunk)-[:FROM_DOCUMENT]->(document)
OPTIONAL MATCH (hotel:Hotel)-[:FROM_CHUNK]->(chunk)
RETURN count(DISTINCT document) AS document_count,
       count(DISTINCT hotel) AS hotel_count,
       collect(DISTINCT elementId(hotel)) AS hotel_element_ids
""".strip()

_MATERIALIZE_QUERY = """
CYPHER 25
MATCH (document:Document {source_filename: $source_filename})
MATCH (chunk:Chunk)-[:FROM_DOCUMENT]->(document)
MATCH (hotel:Hotel)-[:FROM_CHUNK]->(chunk)
WHERE elementId(hotel) = $hotel_element_id
WITH DISTINCT hotel, chunk
UNWIND $amenity_names AS amenity_name
MERGE (amenity:Amenity {name: amenity_name})
SET amenity:__Entity__:__KGBuilder__
MERGE (hotel)-[offer:OFFERS_AMENITY]->(amenity)
SET offer.source_filename = $source_filename
MERGE (amenity)-[:FROM_CHUNK]->(chunk)
RETURN count(DISTINCT amenity) AS amenity_count
""".strip()


class AmenitySectionError(ValueError):
    """Raised when a source document has no valid authoritative amenity list."""


class AmenityMaterializationError(RuntimeError):
    """Raised when amenities cannot be attached without ambiguous identity."""


@dataclass(frozen=True)
class ParsedAmenities:
    """Canonical amenity labels parsed from one source document."""

    source_filename: str
    names: tuple[str, ...]


def parse_amenity_section(text: str, source_filename: str) -> ParsedAmenities:
    """Parse the one direct bullet list under ``## Hotel Amenities``.

    Parsing stops at the next Markdown heading. Other non-empty content inside
    the section is rejected so prose can never be mistaken for an amenity.
    """
    lines = text.splitlines()
    headings = [
        index for index, line in enumerate(lines) if line.strip() == AMENITY_HEADING
    ]
    if len(headings) != 1:
        found = len(headings)
        raise AmenitySectionError(
            f"{source_filename}: found {found} {AMENITY_HEADING!r} sections, "
            "expected exactly 1"
        )

    names: list[str] = []
    seen: set[str] = set()
    heading_index = headings[0]
    for line_number, line in enumerate(
        lines[heading_index + 1 :], start=heading_index + 2
    ):
        stripped = line.strip()
        if _HEADING.match(stripped):
            break
        if not stripped:
            continue

        match = _BULLET.fullmatch(line)
        if match is None:
            raise AmenitySectionError(
                f"{source_filename}:{line_number}: expected a direct '- ' "
                "amenity bullet or the next Markdown heading"
            )

        name = match.group(1).strip()
        if not name:
            raise AmenitySectionError(
                f"{source_filename}:{line_number}: amenity label is empty"
            )
        if name in seen:
            raise AmenitySectionError(
                f"{source_filename}:{line_number}: duplicate amenity label {name!r}"
            )
        names.append(name)
        seen.add(name)

    if not names:
        raise AmenitySectionError(
            f"{source_filename}: {AMENITY_HEADING!r} has no amenity bullets"
        )

    return ParsedAmenities(source_filename=source_filename, names=tuple(names))


def ensure_amenity_constraint(driver: Driver, database: str) -> None:
    """Create the canonical Amenity-name constraint if it does not exist."""
    try:
        with driver.session(database=database) as neo4j_session:
            neo4j_session.run(AMENITY_NAME_CONSTRAINT).consume()
    except Neo4jError as exc:
        raise AmenityMaterializationError(
            "could not enforce unique Amenity names in Neo4j"
        ) from exc


def _materialize_transaction(
    transaction: ManagedTransaction,
    parsed: ParsedAmenities,
) -> int:
    source_result = transaction.run(
        _SOURCE_HOTEL_QUERY,
        source_filename=parsed.source_filename,
    ).single()
    if source_result is None:
        raise AmenityMaterializationError(
            f"{parsed.source_filename}: source lookup returned no result"
        )

    document_count = source_result["document_count"]
    if document_count != 1:
        raise AmenityMaterializationError(
            f"{parsed.source_filename}: found {document_count} Document nodes, "
            "expected exactly 1"
        )

    hotel_count = source_result["hotel_count"]
    if hotel_count != 1:
        raise AmenityMaterializationError(
            f"{parsed.source_filename}: found {hotel_count} Hotels through "
            "Document and Chunk provenance, expected exactly 1"
        )

    hotel_element_id = source_result["hotel_element_ids"][0]
    write_result = transaction.run(
        _MATERIALIZE_QUERY,
        source_filename=parsed.source_filename,
        hotel_element_id=hotel_element_id,
        amenity_names=list(parsed.names),
    ).single()
    amenity_count = 0 if write_result is None else write_result["amenity_count"]
    if amenity_count != len(parsed.names):
        raise AmenityMaterializationError(
            f"{parsed.source_filename}: materialized {amenity_count} Amenities, "
            f"expected {len(parsed.names)}"
        )
    return amenity_count


def materialize_amenities(
    driver: Driver,
    database: str,
    parsed: ParsedAmenities,
) -> int:
    """Idempotently attach one source document's canonical amenities."""
    try:
        with driver.session(database=database) as neo4j_session:
            return neo4j_session.execute_write(
                lambda transaction: _materialize_transaction(transaction, parsed)
            )
    except Neo4jError as exc:
        raise AmenityMaterializationError(
            f"{parsed.source_filename}: Neo4j amenity write failed"
        ) from exc
