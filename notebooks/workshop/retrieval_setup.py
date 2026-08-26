# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Index setup and readiness checks shared by the Module 1 build paths.

The notebook only retrieves. Graph preparation owns index creation and checks
the deterministic fixtures every Module 1 build path needs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from neo4j import Driver
from neo4j_graphrag.indexes import create_fulltext_index, create_vector_index

from workshop.fixtures import _index_problems
from workshop.graph_connection import graph_database
from workshop.graph_schema import GRAPH_SCHEMA, SCHEMA_NODE_LABELS
from workshop.retrieval_contract import (
    CHUNK_FULLTEXT_INDEX,
    CHUNK_VECTOR_INDEX,
    EMBEDDING_DIMENSIONS,
)

# The source documents every module after Module 1 asks a question against. A
# build that samples the corpus has to include these or a later module opens
# onto a graph that cannot answer its own hero question.
REQUIRED_SOURCE_FILES = (
    "hotel-paris-001.txt",
    "hotel-paris-002.txt",
    "hotel-cairo-001.txt",
    "hotel-cairo-002.txt",
    "hotel-chicago-001.txt",
    "hotel-chicago-002.txt",
)

SOURCE_READINESS_QUERY = """
    CYPHER 25
    UNWIND $sources AS source
    OPTIONAL MATCH (document:Document {source_filename: source.source_filename})
    OPTIONAL MATCH (chunk:Chunk)-[:FROM_DOCUMENT]->(document)
    OPTIONAL MATCH (hotel:Hotel)-[:FROM_CHUNK]->(chunk)
    OPTIONAL MATCH (hotel)-[:OFFERS_AMENITY]->(amenity:Amenity)
    RETURN source.source_filename AS source_filename,
           count(DISTINCT document) AS document_count,
           count(DISTINCT chunk) AS chunk_count,
           count(DISTINCT CASE
               WHEN chunk.embedding IS NOT NULL
                AND size(chunk.embedding) = $dimensions
               THEN chunk
           END) AS embedded_chunk_count,
           count(DISTINCT hotel) AS hotel_count,
           count(DISTINCT CASE
               WHEN hotel IS NOT NULL THEN
                   elementId(hotel) + '|' + elementId(chunk) + '|' + elementId(document)
           END) AS source_path_count,
           collect(DISTINCT chunk.text) AS chunk_texts,
           collect(DISTINCT hotel.name) AS hotel_names,
           collect(DISTINCT hotel.hotel_id) AS hotel_ids,
           collect(DISTINCT hotel.address) AS hotel_addresses,
           collect(DISTINCT hotel.guest_rating) AS guest_ratings,
           collect(DISTINCT amenity.name) AS amenities
    ORDER BY source_filename
""".strip()

CHICAGO_FILTER_QUERY = """
    CYPHER 25
    MATCH (document:Document)<-[:FROM_DOCUMENT]-(chunk:Chunk)<-[:FROM_CHUNK]-(hotel:Hotel)
    WHERE hotel.address IS NOT NULL
      AND toLower(hotel.address) CONTAINS toLower($city)
      AND hotel.name IS NOT NULL
    OPTIONAL MATCH (hotel)-[:OFFERS_AMENITY]->(amenity:Amenity)
    WITH document.source_filename AS source_filename,
         hotel.name AS hotel_name,
         hotel.guest_rating AS guest_rating,
         chunk.text AS source_chunk,
         collect(DISTINCT amenity.name) AS amenities
    WITH *,
         any(name IN amenities WHERE toLower(name) CONTAINS 'spa') AS has_spa,
         any(name IN amenities WHERE toLower(name) CONTAINS 'pool') AS has_pool
    RETURN source_filename,
           hotel_name,
           guest_rating,
           amenities,
           source_chunk,
           has_spa,
           has_pool,
           has_spa AND has_pool AS qualifies,
           CASE
               WHEN has_spa AND has_pool THEN []
               WHEN NOT has_spa AND NOT has_pool THEN ['spa', 'swimming pool']
               WHEN NOT has_spa THEN ['spa']
               ELSE ['swimming pool']
           END AS missing_required_amenities
    ORDER BY hotel_name
""".strip()

CHICAGO_SOURCE_FILES = (
    "hotel-chicago-001.txt",
    "hotel-chicago-002.txt",
)
CHICAGO_QUALIFIER = "Lakeview Horizon Suites"
CHICAGO_EXCLUSION = "Windward Mile Tower"
CHICAGO_CITY = "Chicago"
CAIRO_HOTEL_ID = "81393d51-1df3-4f53-b58e-e4cda9736fd7"
FITNESS_AMENITY = "24-" "Hour Fitness Center"


@dataclass(frozen=True)
class SourceFixture:
    """Exact source-backed graph facts needed by a Module 2 example."""

    source_filename: str
    hotel_name: str
    address_term: str
    chunk_terms: tuple[str, ...]
    amenities: tuple[str, ...]
    guest_rating: float | None = None
    hotel_id: str | None = None

    def row(self) -> dict[str, str]:
        """Return the query parameter row for this fixture."""
        return {"source_filename": self.source_filename}


SOURCE_FIXTURES = (
    SourceFixture(
        source_filename="hotel-cairo-001.txt",
        hotel_name="AnyCompany Cairo Nile View",
        address_term="Cairo 11519",
        chunk_terms=("AnyCompany Cairo Nile View", "3:00 PM"),
        amenities=(
            "Outdoor Swimming Pool",
            "Full-Service Spa",
            FITNESS_AMENITY,
            "Complimentary High-Speed Wifi",
            "On-Site Restaurant",
            "Nile Views",
        ),
        guest_rating=4.5,
        hotel_id=CAIRO_HOTEL_ID,
    ),
    SourceFixture(
        source_filename="hotel-chicago-001.txt",
        hotel_name=CHICAGO_EXCLUSION,
        address_term="60611",
        chunk_terms=(CHICAGO_EXCLUSION, "60611"),
        amenities=(
            FITNESS_AMENITY,
            "Complimentary High-Speed Wifi",
            "On-Site Restaurant",
            "Lounge Bar",
            "Business Center",
        ),
    ),
    SourceFixture(
        source_filename="hotel-chicago-002.txt",
        hotel_name=CHICAGO_QUALIFIER,
        address_term="Chicago",
        chunk_terms=(CHICAGO_QUALIFIER,),
        amenities=(
            "Outdoor Swimming Pool",
            FITNESS_AMENITY,
            "Complimentary High-Speed Wifi",
            "On-Site Restaurant",
            "Full-Service Spa",
        ),
    ),
)

# Derived from the pinned schema rather than restated. The extraction contract
# in graph_schema is what the build refuses to write outside of, so counting a
# relationship type this readiness check names but that schema does not pin
# would report a number the build can never produce.
SCHEMA_RELATIONSHIP_TYPES = tuple(
    entry["label"]
    for entry in cast(Sequence[Mapping[str, str]], GRAPH_SCHEMA["relationship_types"])
)


class ReadinessError(RuntimeError):
    """Raised when an index exists but does not match the retrieval contract."""


@dataclass(frozen=True)
class Fixture:
    """One graph fact required by a learner-facing question."""

    name: str
    query: str
    parameters: Mapping[str, Any]
    minimum: int = 1


BUILD_HEALTH_FIXTURES = (
    Fixture(
        name="Paris ratings for aggregation",
        query="""
            MATCH (h:Hotel)
            WHERE toLower(h.address) CONTAINS 'paris'
              AND h.guest_rating IS NOT NULL
            RETURN count(DISTINCT h) AS actual
        """,
        parameters={},
        minimum=2,
    ),
    Fixture(
        name="hotel-to-pool relationship for counting",
        query="""
            MATCH (h:Hotel)-[:OFFERS_AMENITY]->(a:Amenity)
            WHERE toLower(a.name) CONTAINS 'pool'
            RETURN count(DISTINCT h) AS actual
        """,
        parameters={},
    ),
    Fixture(
        name="Cairo spa-and-pool connected traversal result",
        query="""
            MATCH (h:Hotel)-[:OFFERS_AMENITY]->(spa:Amenity),
                  (h)-[:OFFERS_AMENITY]->(pool:Amenity)
            WHERE toLower(h.address) CONTAINS 'cairo'
              AND toLower(spa.name) CONTAINS 'spa'
              AND toLower(pool.name) CONTAINS 'pool'
              AND h.guest_rating IS NOT NULL
            RETURN count(DISTINCT h) AS actual
        """,
        parameters={},
    ),
    Fixture(
        name="Windward Mile Tower hotel at postal code 60611",
        query="""
            MATCH (h:Hotel)
            WHERE h.name = $hotel_name AND h.address CONTAINS $postal_code
            RETURN count(h) AS actual
        """,
        parameters={
            "hotel_name": "Windward Mile Tower",
            "postal_code": "60611",
        },
    ),
    Fixture(
        name="embedded Windward Mile Tower chunk containing 60611",
        query="""
            MATCH (c:Chunk)
            WHERE c.text CONTAINS $hotel_name
              AND c.text CONTAINS $postal_code
              AND c.embedding IS NOT NULL
              AND size(c.embedding) = $dimensions
            RETURN count(c) AS actual
        """,
        parameters={
            "hotel_name": "Windward Mile Tower",
            "postal_code": "60611",
            "dimensions": EMBEDDING_DIMENSIONS,
        },
    ),
)


def missing_source_fixtures(paths: Iterable[Path]) -> list[str]:
    """Return required source filenames absent from ``paths``."""
    selected = {path.name for path in paths}
    return sorted(set(REQUIRED_SOURCE_FILES) - selected)


def _source_fixture_problems(
    records: Iterable[Mapping[str, Any]],
) -> list[str]:
    """Return exact source, path, property, and amenity fixture defects."""
    by_source = {record["source_filename"]: record for record in records}
    problems: list[str] = []

    for fixture in SOURCE_FIXTURES:
        record = by_source.get(fixture.source_filename)
        if record is None:
            problems.append(f"missing readiness record for {fixture.source_filename}")
            continue

        for field in (
            "document_count",
            "chunk_count",
            "embedded_chunk_count",
            "hotel_count",
            "source_path_count",
        ):
            if record.get(field) != 1:
                problems.append(
                    f"{fixture.source_filename} has {record.get(field, 0)} {field}, "
                    "expected 1"
                )

        hotel_names = set(record.get("hotel_names", []))
        if hotel_names != {fixture.hotel_name}:
            problems.append(
                f"{fixture.source_filename} has hotel names "
                f"{sorted(hotel_names)}, expected [{fixture.hotel_name!r}]"
            )

        if fixture.hotel_id is not None:
            hotel_ids = list(record.get("hotel_ids", []))
            if hotel_ids != [fixture.hotel_id]:
                problems.append(
                    f"{fixture.source_filename} has hotel IDs {hotel_ids}, "
                    f"expected exactly [{fixture.hotel_id!r}]"
                )

        addresses = [str(value) for value in record.get("hotel_addresses", [])]
        if len(addresses) != 1 or fixture.address_term not in addresses[0]:
            problems.append(
                f"{fixture.source_filename} does not have one Hotel address "
                f"containing {fixture.address_term!r}"
            )

        chunk_texts = [str(value) for value in record.get("chunk_texts", [])]
        if len(chunk_texts) != 1:
            problems.append(
                f"{fixture.source_filename} has {len(chunk_texts)} Chunk texts, "
                "expected 1"
            )
        else:
            missing_terms = [
                term for term in fixture.chunk_terms if term not in chunk_texts[0]
            ]
            if missing_terms:
                problems.append(
                    f"{fixture.source_filename} Chunk is missing terms: "
                    + ", ".join(missing_terms)
                )

        actual_amenities = set(record.get("amenities", []))
        expected_amenities = set(fixture.amenities)
        if actual_amenities != expected_amenities:
            missing = sorted(expected_amenities - actual_amenities)
            unexpected = sorted(actual_amenities - expected_amenities)
            if missing:
                problems.append(
                    f"{fixture.source_filename} is missing authored amenities: "
                    + ", ".join(missing)
                )
            if unexpected:
                problems.append(
                    f"{fixture.source_filename} has unexpected amenities: "
                    + ", ".join(unexpected)
                )

        if fixture.guest_rating is not None:
            ratings = set(record.get("guest_ratings", []))
            if ratings != {fixture.guest_rating}:
                problems.append(
                    f"{fixture.source_filename} has guest ratings "
                    f"{sorted(ratings)}, expected [{fixture.guest_rating}]"
                )

    return problems


def source_fixture_problems(driver: Driver) -> list[str]:
    """Read and validate exact source-backed Module 2 graph fixtures."""
    with _session(driver) as session:
        records = list(
            session.run(
                SOURCE_READINESS_QUERY,
                sources=[fixture.row() for fixture in SOURCE_FIXTURES],
                dimensions=EMBEDDING_DIMENSIONS,
            )
        )
    return _source_fixture_problems(records)


def chicago_filter_records(driver: Driver) -> list[dict[str, Any]]:
    """Return the deterministic Chicago candidates and filter context."""
    with _session(driver) as session:
        return [
            dict(record)
            for record in session.run(
                CHICAGO_FILTER_QUERY,
                city=CHICAGO_CITY,
            )
        ]


def chicago_filter_problems(records: Iterable[Mapping[str, Any]]) -> list[str]:
    """Validate the two Chicago candidates, qualifier, and exclusion."""
    candidates = list(records)
    problems: list[str] = []
    expected_sources = set(CHICAGO_SOURCE_FILES)
    actual_sources = {record.get("source_filename") for record in candidates}
    if len(candidates) != 2 or actual_sources != expected_sources:
        problems.append(
            "Chicago filter returned "
            f"{len(candidates)} candidates from {sorted(str(s) for s in actual_sources)}, "
            f"expected 2 from {sorted(expected_sources)}"
        )

    qualifiers = {
        record.get("hotel_name") for record in candidates if record.get("qualifies")
    }
    if qualifiers != {CHICAGO_QUALIFIER}:
        problems.append(
            f"Chicago filter qualifiers are {sorted(str(q) for q in qualifiers)}, "
            f"expected [{CHICAGO_QUALIFIER!r}]"
        )

    excluded = [
        record
        for record in candidates
        if record.get("hotel_name") == CHICAGO_EXCLUSION
    ]
    if len(excluded) != 1 or excluded[0].get("qualifies"):
        problems.append(f"Chicago filter did not explicitly exclude {CHICAGO_EXCLUSION}")
    elif set(excluded[0].get("missing_required_amenities", [])) != {
        "spa",
        "swimming pool",
    }:
        problems.append(
            f"{CHICAGO_EXCLUSION} exclusion does not name its missing spa and pool"
        )

    return problems


# The relationships the Module 2 graph-expansion query walks: text provenance,
# entity provenance, and the amenity edge the question is actually about.
GRAPH_CONTEXT_RELATIONSHIPS = ("FROM_DOCUMENT", "FROM_CHUNK", "OFFERS_AMENITY")

# The fields a graph-expanded record names a provenance path for.
GRAPH_CONTEXT_FIELDS = (
    "source_chunk",
    "source_filename",
    "hotel_name",
    "hotel_id",
    "guest_rating",
    "amenities",
)


def fixture_for(source_filename: str) -> SourceFixture:
    """Return the locked source fixture for one Module 2 document."""
    for fixture in SOURCE_FIXTURES:
        if fixture.source_filename == source_filename:
            return fixture
    raise KeyError(f"no source fixture for {source_filename!r}")


def source_context_problems(
    rows: Iterable[Mapping[str, Any]],
    fixture: SourceFixture,
    extra_terms: Sequence[str] = (),
) -> list[str]:
    """Return defects in retrieved text context for one source fixture.

    A text retriever earns its result by returning the fixture's source and the
    terms that answer the question. Both are already stated once in
    SOURCE_FIXTURES, so a notebook cell asks for them rather than restating
    them next to the search that produced them.
    """
    matches = [
        row for row in rows if row.get("source_filename") == fixture.source_filename
    ]
    if not matches:
        observed = sorted({str(row.get("source_filename")) for row in rows})
        return [
            (
                f"{fixture.source_filename} is not in the retrieved context; "
                f"observed {observed}"
            )
        ]

    chunk = str(matches[0].get("chunk") or "").casefold()
    return [
        f"{fixture.source_filename} context does not carry {term!r}"
        for term in (*fixture.chunk_terms, *extra_terms)
        if term.casefold() not in chunk
    ]


def graph_context_problems(
    records: Iterable[Mapping[str, Any]],
    fixture: SourceFixture,
) -> list[str]:
    """Return defects in graph-expanded context for one source fixture.

    Graph expansion adds named fields a chunk of text cannot supply, so this
    checks the fields, the relationships that produced them, and the provenance
    path each field names.
    """
    matches = [
        record
        for record in records
        if record.get("source_filename") == fixture.source_filename
    ]
    if len(matches) != 1:
        return [
            (
                f"expected one graph record for {fixture.source_filename}, "
                f"observed {len(matches)}"
            )
        ]

    record = matches[0]
    problems: list[str] = []
    for field, expected in (
        ("hotel_name", fixture.hotel_name),
        ("hotel_id", fixture.hotel_id),
        ("guest_rating", fixture.guest_rating),
    ):
        if expected is not None and record.get(field) != expected:
            problems.append(
                f"{fixture.source_filename} {field} is {record.get(field)!r}, "
                f"expected {expected!r}"
            )

    missing_fields = list(record.get("missing_requested_fields") or [])
    if missing_fields:
        problems.append(
            f"{fixture.source_filename} graph record is missing "
            f"{sorted(missing_fields)}"
        )

    if record.get("semantic_score") is None:
        problems.append(f"{fixture.source_filename} graph record has no semantic score")

    observed_types = set(record.get("relationship_types") or [])
    if observed_types != set(GRAPH_CONTEXT_RELATIONSHIPS):
        problems.append(
            f"{fixture.source_filename} relationship types are "
            f"{sorted(observed_types)}, expected {sorted(GRAPH_CONTEXT_RELATIONSHIPS)}"
        )

    provenance = record.get("field_provenance") or {}
    missing_provenance = [
        field for field in GRAPH_CONTEXT_FIELDS if field not in provenance
    ]
    if missing_provenance:
        problems.append(
            f"{fixture.source_filename} names no provenance path for "
            f"{missing_provenance}"
        )

    amenity_text = " ".join(record.get("amenities") or []).casefold()
    problems.extend(
        f"{fixture.source_filename} amenities do not include {amenity!r}"
        for amenity in fixture.amenities
        if amenity.casefold() not in amenity_text
    )
    return problems


def report_problems(problems: Sequence[str], passed_message: str) -> None:
    """Print one PASS line, or raise with every problem named.

    Checks return problems so a caller decides what a defect means. A notebook
    wants the run to stop, so it routes them here.
    """
    if problems:
        details = "\n  - ".join(problems)
        raise ReadinessError(f"Check failed:\n  - {details}")
    print(f"PASS  {passed_message}")

def _session(driver: Driver):
    """Open a session against the configured database.

    Indexes, counts, and fixture checks all have to land on the database the
    build wrote to. Left on the driver's home database, a participant who sets
    `NEO4J_DATABASE` gets data in one place and indexes in another, and every
    later module retrieves nothing while every call succeeds.
    """
    return driver.session(database=graph_database())


def ensure_retrieval_indexes(driver: Driver) -> None:
    """Create the two chunk indexes idempotently and verify their contracts."""
    database = graph_database()
    create_vector_index(
        driver=driver,
        name=CHUNK_VECTOR_INDEX,
        label="Chunk",
        embedding_property="embedding",
        dimensions=EMBEDDING_DIMENSIONS,
        similarity_fn="cosine",
        fail_if_exists=False,
        neo4j_database=database,
    )
    create_fulltext_index(
        driver=driver,
        name=CHUNK_FULLTEXT_INDEX,
        label="Chunk",
        node_properties=["text"],
        fail_if_exists=False,
        neo4j_database=database,
    )
    with _session(driver) as session:
        session.run(
            "CALL db.awaitIndexes($timeout_seconds)", timeout_seconds=300
        ).consume()
    verify_retrieval_indexes(driver)


def verify_retrieval_indexes(driver: Driver) -> None:
    """Raise with a precise message unless both retrieval indexes are ready.

    The index-contract check itself lives in `workshop.fixtures._index_problems`
    rather than being reimplemented here, so a future change to the vector or
    fulltext contract has one call site to update instead of two that can drift
    apart.
    """
    with _session(driver) as session:
        records = list(
            session.run(
                """
                SHOW INDEXES
                YIELD name, type, state, labelsOrTypes, properties, options
                WHERE name IN $names
                RETURN name, type, state, labelsOrTypes, properties, options
                """,
                names=[CHUNK_VECTOR_INDEX, CHUNK_FULLTEXT_INDEX],
            )
        )
    problems = _index_problems(records)
    if problems:
        details = "\n  - ".join(problems)
        raise ReadinessError(f"Retrieval index check failed:\n  - {details}")


def graph_counts(driver: Driver) -> tuple[int, int, dict[str, int], dict[str, int]]:
    """Return document, chunk, extracted-label, and relationship counts."""
    with _session(driver) as session:
        document_count = session.run(
            "MATCH (d:Document) RETURN count(d) AS count"
        ).single()["count"]
        chunk_count = session.run("MATCH (c:Chunk) RETURN count(c) AS count").single()[
            "count"
        ]
        label_counts = {
            record["label"]: record["count"]
            for record in session.run(
                """
                MATCH (n)
                UNWIND [label IN labels(n) WHERE label IN $labels] AS label
                RETURN label, count(*) AS count
                ORDER BY label
                """,
                labels=list(SCHEMA_NODE_LABELS),
            )
        }
        relationship_counts = {
            record["relationship"]: record["count"]
            for record in session.run(
                """
                MATCH ()-[r]->()
                WHERE type(r) IN $types
                RETURN type(r) AS relationship, count(*) AS count
                ORDER BY relationship
                """,
                types=list(SCHEMA_RELATIONSHIP_TYPES),
            )
        }
    return document_count, chunk_count, label_counts, relationship_counts


def build_health_problems(driver: Driver) -> list[str]:
    """Return broader defects protected by the build-time graph health gate."""
    problems: list[str] = []
    with _session(driver) as session:
        for fixture in BUILD_HEALTH_FIXTURES:
            record = session.run(fixture.query, **dict(fixture.parameters)).single()
            actual = 0 if record is None else record["actual"]
            if actual < fixture.minimum:
                problems.append(
                    f"{fixture.name}: found {actual}, expected at least {fixture.minimum}"
                )
    return problems


def hotel_provenance_problems(driver: Driver) -> list[str]:
    """Return Documents without one distinct Hotel and cross-source Hotel merges."""
    with _session(driver) as session:
        invalid_documents = list(
            session.run(
                """
                CYPHER 25
                MATCH (document:Document)
                OPTIONAL MATCH (chunk:Chunk)-[:FROM_DOCUMENT]->(document)
                OPTIONAL MATCH (hotel:Hotel)-[:FROM_CHUNK]->(chunk)
                WITH document, count(DISTINCT hotel) AS hotel_count
                WHERE hotel_count <> 1
                RETURN coalesce(
                    document.source_filename,
                    '<Document ' + elementId(document) + '>'
                ) AS filename,
                hotel_count
                ORDER BY filename
                """
            )
        )
        shared_hotels = list(
            session.run(
                """
                CYPHER 25
                MATCH (document:Document)<-[:FROM_DOCUMENT]-(chunk:Chunk)<-[:FROM_CHUNK]-(hotel:Hotel)
                WITH hotel,
                     collect(DISTINCT coalesce(
                         document.source_filename,
                         '<Document ' + elementId(document) + '>'
                     )) AS source_filenames,
                     count(DISTINCT document) AS document_count
                WHERE document_count > 1
                RETURN source_filenames
                ORDER BY source_filenames[0]
                """
            )
        )

    problems = [
        f"{record['filename']} resolves to {record['hotel_count']} Hotels, expected 1"
        for record in invalid_documents
    ]
    problems.extend(
        "one Hotel node is shared by source documents: "
        + ", ".join(sorted(record["source_filenames"]))
        for record in shared_hotels
    )
    return problems


def report_readiness(driver: Driver, expected_documents: int) -> list[str]:
    """Print readiness counts and return all graph fixture problems."""
    documents, chunks, labels, relationships = graph_counts(driver)
    chicago_records = chicago_filter_records(driver)
    qualifying_names = [
        record["hotel_name"] for record in chicago_records if record["qualifies"]
    ]
    excluded_names = [
        record["hotel_name"] for record in chicago_records if not record["qualifies"]
    ]
    print("\nModule 1 readiness report:")
    print(f"  documents: {documents} (expected {expected_documents})")
    print(f"  chunks: {chunks} (expected {documents})")
    print(f"  extracted labels: {labels}")
    print(f"  relationships: {relationships}")
    print(f"  Chicago candidates: {len(chicago_records)}")
    print(f"  Chicago spa-and-pool qualifiers: {qualifying_names}")
    print(f"  Chicago exclusions: {excluded_names}")

    problems = hotel_provenance_problems(driver)
    problems.extend(build_health_problems(driver))
    problems.extend(source_fixture_problems(driver))
    problems.extend(chicago_filter_problems(chicago_records))
    if documents != expected_documents:
        problems.insert(
            0,
            f"document count is {documents}, expected {expected_documents}",
        )
    if chunks != documents:
        problems.insert(1, f"chunk count is {chunks}, expected {documents}")
    hotels = labels.get("Hotel", 0)
    if hotels != expected_documents:
        problems.insert(
            2,
            f"Hotel count is {hotels}, expected {expected_documents}",
        )
    return problems
