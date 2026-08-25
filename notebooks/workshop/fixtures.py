# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Idempotent Neo4j preparation and readiness checks for the reservation fixtures.

This module verifies the indexes Module 1 owns. It only writes the two fixture
hotel IDs, ordinary uniqueness constraints, and the maximum-guests rule.

The hero constants live here rather than in the module that narrates them
because `readiness_problems` checks the graph against them. They are the
fixture definition, not presentation: a hero address changed in one place and
verified against another would report a graph as unready for a reason no
participant could act on.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import UUID

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase

from workshop import contracts, graph_connection

MANIFEST_PATH = Path(str(files("workshop") / "fixtures" / "hotel_ids.json"))
HERO_SOURCE = "hotel-cairo-001.txt"
HERO_NAME = "AnyCompany Cairo Nile View"
HERO_ADDRESS = "789 Corniche el-Nil, Cairo 11519, Egypt"
HERO_RATING = 4.5
HERO_AMENITY_TERMS = ("pool", "spa", "fitness", "wifi", "restaurant")
# Interpolated rather than written out, so the sentence a participant reads
# cannot drift away from the number the rule is actually enforced against.
RULE_REJECTION_MESSAGE = (
    f"Reservation requests are limited to {contracts.MAX_GUESTS} guests."
)
RULE_STEERING_MESSAGE = (
    f"Ask for a party size of {contracts.MAX_GUESTS} guests or fewer."
)

RESERVATION_REQUEST_PROPERTIES = (
    "request_id",
    "check_in",
    "check_out",
    "guests",
    "status",
    "workshop_owner",
    "created_at",
)
FOR_HOTEL_PATTERN = "(:ReservationRequest)-[:FOR_HOTEL]->(:Hotel)"

HOTEL_ID_CONSTRAINT = """
CYPHER 25
CREATE CONSTRAINT demo06_fixture_hotel_id IF NOT EXISTS
FOR (hotel:Hotel) REQUIRE hotel.hotel_id IS UNIQUE
""".strip()

REQUEST_ID_CONSTRAINT = """
CYPHER 25
CREATE CONSTRAINT demo06_reservation_request_id IF NOT EXISTS
FOR (request:ReservationRequest) REQUIRE request.request_id IS UNIQUE
""".strip()

RULE_ID_CONSTRAINT = """
CYPHER 25
CREATE CONSTRAINT demo06_rule_id IF NOT EXISTS
FOR (rule:Rule) REQUIRE rule.rule_id IS UNIQUE
""".strip()

FIXTURE_RESOLUTION_QUERY = """
CYPHER 25
UNWIND $fixtures AS fixture
OPTIONAL MATCH (document:Document {source_filename: fixture.source_filename})
OPTIONAL MATCH (document)<-[:FROM_DOCUMENT]-(chunk:Chunk)
OPTIONAL MATCH (chunk)<-[:FROM_CHUNK]-(hotel:Hotel)
RETURN fixture.source_filename AS source_filename,
       fixture.hotel_id AS expected_hotel_id,
       count(DISTINCT document) AS documents,
       count(DISTINCT chunk) AS chunks,
       count(DISTINCT hotel) AS hotels,
       collect(DISTINCT elementId(hotel)) AS hotel_element_ids,
       collect(DISTINCT hotel.hotel_id) AS actual_hotel_ids
ORDER BY source_filename
""".strip()

APPLY_FIXTURE_IDS_QUERY = """
CYPHER 25
UNWIND $fixtures AS fixture
MATCH (document:Document {source_filename: fixture.source_filename})
MATCH (document)<-[:FROM_DOCUMENT]-(chunk:Chunk)
MATCH (chunk)<-[:FROM_CHUNK]-(hotel:Hotel)
SET hotel.hotel_id = fixture.hotel_id,
    hotel.demo6_fixture = true
RETURN count(DISTINCT hotel) AS updated
""".strip()

UPSERT_RULE_QUERY = """
CYPHER 25
MERGE (rule:Rule {rule_id: $rule_id})
SET rule.rule_type = 'MAXIMUM_GUESTS',
    rule.max_guests = $max_guests,
    rule.enabled = true,
    rule.rejection_message = $rejection_message,
    rule.steering_message = $steering_message,
    rule.workshop_owner = $workshop_owner,
    rule.schema_version = 1
RETURN rule.rule_id AS rule_id
""".strip()

INDEX_QUERY = """
SHOW INDEXES
YIELD name, type, state, labelsOrTypes, properties, options
WHERE name IN $names
RETURN name, type, state, labelsOrTypes, properties, options
""".strip()

CONSTRAINT_QUERY = """
SHOW CONSTRAINTS
YIELD name, type, labelsOrTypes, properties
WHERE name IN $names
RETURN name, type, labelsOrTypes, properties
""".strip()

HERO_QUERY = """
CYPHER 25
MATCH (hotel:Hotel {hotel_id: $hotel_id})
OPTIONAL MATCH (hotel)-[:OFFERS_AMENITY]->(amenity:Amenity)
WHERE amenity.name IS NOT NULL
RETURN hotel.name AS name,
       hotel.address AS address,
       hotel.guest_rating AS guest_rating,
       collect(DISTINCT amenity.name) AS amenities
""".strip()

RULE_QUERY = """
CYPHER 25
OPTIONAL MATCH (rule:Rule {rule_id: $rule_id})
WITH collect(rule) AS rules
RETURN size(rules) AS rule_count,
       head(rules).max_guests AS max_guests,
       head(rules).enabled AS enabled,
       head(rules).rejection_message AS rejection_message,
       head(rules).steering_message AS steering_message,
       head(rules).workshop_owner AS workshop_owner
""".strip()


@dataclass(frozen=True)
class FixtureManifest:
    version: int
    hotels: Mapping[str, str]

    def rows(self) -> list[dict[str, str]]:
        return [
            {"source_filename": filename, "hotel_id": hotel_id}
            for filename, hotel_id in sorted(self.hotels.items())
        ]


def load_manifest(path: Path = MANIFEST_PATH) -> FixtureManifest:
    """Load and validate the committed filename-to-opaque-ID mapping."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if set(payload) != {"manifest_version", "hotels"}:
        raise ValueError("Fixture manifest must contain manifest_version and hotels")
    if payload["manifest_version"] != contracts.FIXTURE_MANIFEST_VERSION:
        raise ValueError("Fixture manifest version does not match contracts.py")
    hotels = payload["hotels"]
    if not isinstance(hotels, dict) or not hotels:
        raise ValueError("Fixture manifest hotels must be a non-empty object")
    if set(hotels) != {"hotel-cairo-001.txt", "hotel-cairo-002.txt"}:
        raise ValueError("Fixture manifest must contain exactly the two Cairo fixtures")

    ids: list[str] = []
    for filename, hotel_id in hotels.items():
        if Path(filename).name != filename or not filename.endswith(".txt"):
            raise ValueError(f"Invalid source filename: {filename!r}")
        try:
            UUID(hotel_id)
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"Hotel ID for {filename!r} must be an opaque UUID") from exc
        ids.append(hotel_id)
    if len(ids) != len(set(ids)):
        raise ValueError("Fixture hotel IDs must be unique")
    return FixtureManifest(version=payload["manifest_version"], hotels=hotels)


def _index_problems(records: Iterable[Mapping[str, Any]]) -> list[str]:
    indexes = {record["name"]: record for record in records}
    expected = {
        contracts.CHUNK_VECTOR_INDEX: ("VECTOR", ["Chunk"], ["embedding"]),
        contracts.CHUNK_FULLTEXT_INDEX: ("FULLTEXT", ["Chunk"], ["text"]),
    }
    problems: list[str] = []
    for name, (index_type, labels, properties) in expected.items():
        record = indexes.get(name)
        if record is None:
            problems.append(f"missing index {name}")
            continue
        if record.get("state") != "ONLINE":
            problems.append(f"index {name} is not ONLINE")
        if record.get("type") != index_type:
            problems.append(f"index {name} is not {index_type}")
        if record.get("labelsOrTypes") != labels:
            problems.append(f"index {name} targets the wrong label")
        if record.get("properties") != properties:
            problems.append(f"index {name} targets the wrong property")

    vector = indexes.get(contracts.CHUNK_VECTOR_INDEX)
    if vector is not None:
        config = vector.get("options", {}).get("indexConfig", {})
        if config.get("vector.dimensions") != contracts.EMBEDDING_DIMENSIONS:
            problems.append("vector index has the wrong dimensions")
        similarity = config.get("vector.similarity_function")
        if not isinstance(similarity, str) or similarity.casefold() != "cosine":
            problems.append("vector index does not use cosine similarity")
    return problems


def _fixture_problems(
    records: Iterable[Mapping[str, Any]],
    manifest: FixtureManifest,
    *,
    require_ids: bool,
) -> list[str]:
    by_source = {record["source_filename"]: record for record in records}
    problems: list[str] = []
    hotel_sources: dict[str, list[str]] = {}
    for source_filename, expected_id in manifest.hotels.items():
        record = by_source.get(source_filename)
        if record is None:
            problems.append(f"missing source record for {source_filename}")
            continue
        if record.get("documents") == 0:
            problems.append(
                f"{source_filename} has no source Document; rebuild the Module 1 graph "
                "so Document.source_filename is recorded"
            )
        for field in ("documents", "chunks", "hotels"):
            if record.get(field) != 1:
                problems.append(
                    f"{source_filename} resolves to {record.get(field, 0)} {field}, expected 1"
                )
        for element_id in record.get("hotel_element_ids", []):
            hotel_sources.setdefault(element_id, []).append(source_filename)
        actual_ids = [value for value in record.get("actual_hotel_ids", []) if value]
        if require_ids and actual_ids != [expected_id]:
            problems.append(
                f"{source_filename} has hotel IDs {actual_ids}, expected [{expected_id}]"
            )
    for element_id, sources in hotel_sources.items():
        if len(sources) > 1:
            problems.append(
                "fixture sources resolve to the same Hotel node "
                f"{element_id}: {', '.join(sorted(sources))}"
            )
    return problems


UNIQUENESS_CONSTRAINT_TYPES = frozenset({"UNIQUENESS", "NODE_PROPERTY_UNIQUENESS"})


def _constraint_problems(records: Iterable[Mapping[str, Any]]) -> list[str]:
    constraints = {record["name"]: record for record in records}
    expected = {
        "demo06_fixture_hotel_id": (["Hotel"], ["hotel_id"]),
        "demo06_reservation_request_id": (
            ["ReservationRequest"],
            ["request_id"],
        ),
        "demo06_rule_id": (["Rule"], ["rule_id"]),
    }
    problems: list[str] = []
    for name, (labels, properties) in expected.items():
        record = constraints.get(name)
        if record is None:
            problems.append(f"missing constraint {name}")
            continue
        # Aura reports 'NODE_PROPERTY_UNIQUENESS' where Neo4j 5.x reported
        # 'UNIQUENESS'. Both name the same constraint, and what this check
        # is asking is whether the constraint enforces uniqueness, not which
        # server spelled the answer.
        if record.get("type") not in UNIQUENESS_CONSTRAINT_TYPES:
            problems.append(f"constraint {name} is not UNIQUENESS")
        if record.get("labelsOrTypes") != labels:
            problems.append(f"constraint {name} targets the wrong label")
        if record.get("properties") != properties:
            problems.append(f"constraint {name} targets the wrong property")
    return problems


def _hero_problems(record: Mapping[str, Any] | None) -> list[str]:
    if record is None:
        return [f"missing hero hotel {HERO_NAME}"]
    problems: list[str] = []
    if record.get("name") != HERO_NAME:
        problems.append(f"hero hotel name is {record.get('name')!r}")
    if record.get("address") != HERO_ADDRESS:
        problems.append(f"hero hotel address is {record.get('address')!r}")
    if record.get("guest_rating") != HERO_RATING:
        problems.append(f"hero hotel rating is {record.get('guest_rating')!r}")
    raw_amenities = " ".join(record.get("amenities") or []).casefold()
    amenity_text = "".join(
        character
        for character in raw_amenities
        if character.isalnum() or character.isspace()
    )
    for term in HERO_AMENITY_TERMS:
        if term not in amenity_text:
            problems.append(f"hero hotel is missing expected amenity term {term!r}")
    return problems


def _rule_problems(record: Mapping[str, Any] | None) -> list[str]:
    if record is None:
        return ["maximum-guests rule is missing"]
    if record.get("rule_count") != 1:
        return [
            "maximum-guests rule count is "
            f"{record.get('rule_count', 0)!r}, expected 1"
        ]
    expected = {
        "max_guests": contracts.MAX_GUESTS,
        "enabled": True,
        "workshop_owner": contracts.WORKSHOP_OWNER,
        "rejection_message": RULE_REJECTION_MESSAGE,
        "steering_message": RULE_STEERING_MESSAGE,
    }
    problems = [
        f"rule {key} is {record.get(key)!r}, expected {value!r}"
        for key, value in expected.items()
        if record.get(key) != value
    ]
    return problems


def _session(driver: Driver, database: str):
    return driver.session(database=database)


def apply_reservation_fixtures(
    driver: Driver,
    database: str,
    manifest: FixtureManifest,
) -> list[str]:
    """Apply the idempotent graph-owned data the reservation write path depends on.

    Return any blocking problems that prevent preparation, for example a
    missing Module 1 graph. When the returned list is empty, the fixture IDs,
    constraints, and maximum-guests rule have been applied.
    """
    with _session(driver, database) as session:
        session.execute_write(lambda tx: tx.run(HOTEL_ID_CONSTRAINT).consume())
        session.execute_write(lambda tx: tx.run(REQUEST_ID_CONSTRAINT).consume())
        session.execute_write(lambda tx: tx.run(RULE_ID_CONSTRAINT).consume())
        resolution = list(
            session.run(FIXTURE_RESOLUTION_QUERY, fixtures=manifest.rows())
        )
        problems = _fixture_problems(resolution, manifest, require_ids=False)
        if problems:
            return problems
        session.execute_write(
            lambda tx: tx.run(
                APPLY_FIXTURE_IDS_QUERY,
                fixtures=manifest.rows(),
            ).consume()
        )
        session.execute_write(
            lambda tx: tx.run(
                UPSERT_RULE_QUERY,
                rule_id=contracts.MAX_GUESTS_RULE_ID,
                max_guests=contracts.MAX_GUESTS,
                rejection_message=RULE_REJECTION_MESSAGE,
                steering_message=RULE_STEERING_MESSAGE,
                workshop_owner=contracts.WORKSHOP_OWNER,
            ).consume()
        )
    return []


def readiness_problems(
    driver: Driver,
    database: str,
    manifest: FixtureManifest,
) -> list[str]:
    """Return every corrective readiness issue without changing the graph."""
    constraint_names = (
        "demo06_fixture_hotel_id",
        "demo06_reservation_request_id",
        "demo06_rule_id",
    )
    with _session(driver, database) as session:
        indexes = list(
            session.run(
                INDEX_QUERY,
                names=[
                    contracts.CHUNK_VECTOR_INDEX,
                    contracts.CHUNK_FULLTEXT_INDEX,
                ],
            )
        )
        constraints = list(
            session.run(CONSTRAINT_QUERY, names=list(constraint_names))
        )
        fixtures = list(
            session.run(FIXTURE_RESOLUTION_QUERY, fixtures=manifest.rows())
        )
        hero_id = manifest.hotels[HERO_SOURCE]
        hero = session.run(HERO_QUERY, hotel_id=hero_id).single()
        rule = session.run(
            RULE_QUERY,
            rule_id=contracts.MAX_GUESTS_RULE_ID,
        ).single()

    problems = _index_problems(indexes)
    problems.extend(_constraint_problems(constraints))
    problems.extend(_fixture_problems(fixtures, manifest, require_ids=True))
    problems.extend(_hero_problems(hero))
    problems.extend(_rule_problems(rule))
    return problems


def _missing_configuration() -> list[str]:
    """Return a corrective line when required Neo4j env values are absent."""
    # contracts owns the required-variable tuple and the database default. A
    # second copy here would let this script accept a connection the read and
    # write paths reject, or default to a different database than they use.
    missing = [
        name for name in contracts.REQUIRED_NEO4J_ENV if not os.environ.get(name)
    ]
    if missing:
        return [f"set {', '.join(missing)} in your environment or .env"]
    return []


def _configuration() -> tuple[str, tuple[str, str], str]:
    return (
        os.environ["NEO4J_URI"],
        (os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
        graph_connection.graph_database(),
    )


def _report(problems: Iterable[str]) -> None:
    """Print the readiness report header and each corrective action."""
    print("Reservation fixtures are not ready:")
    for problem in problems:
        print(f"  - {problem}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare or verify the reservation graph fixtures.")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify readiness without applying IDs, constraints, or the rule.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    manifest = load_manifest()

    problems = _missing_configuration()
    if problems:
        _report(problems)
        return 1

    uri, auth, database = _configuration()
    # notifications_min_severity="OFF" matches the drivers hybrid_retrieval and
    # reservation_command open. Without it this readiness step prints Neo4j
    # planner notices the Module 3.1 retrieval and reservation paths both
    # suppress, so the same query looks different depending on which file
    # opened the connection.
    driver = GraphDatabase.driver(uri, auth=auth, notifications_min_severity="OFF")
    problems: list[str] = []
    try:
        driver.verify_connectivity()
        if not args.check_only:
            problems = apply_reservation_fixtures(driver, database, manifest)
        if not problems:
            problems = readiness_problems(driver, database, manifest)
    finally:
        driver.close()

    if problems:
        _report(problems)
        return 1
    print("Module 3.1 fixtures are ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
