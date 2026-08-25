# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Scoped cleanup for the inspectable Neo4j memory demo.

Removes exactly what the scenario notebook wrote:

1. Workshop-owned ``ABOUT_HOTEL`` relationships.
2. Conversations, messages, and users in the ``demo08-`` namespace.
3. Preferences tagged by this demo, but only after no user owns them.

The hotel graph, its chunk indexes, and other modules' data are untouched.
The library-managed memory vector indexes stay in place: they are shared
infrastructure, they cost nothing while empty, and the smoke test checks
them.

Requires live Neo4j credentials but no AWS access. Without them the script
prints a skip message and exits 0.

Run with:
    uv run --with-requirements ../requirements.txt python cleanup_memory.py
"""

from __future__ import annotations

import sys

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

from memory_helpers import (
    DEMO_ID_PREFIX,
    HOTEL_RELATIONSHIP,
    MemoryDemoConfig,
    WORKSHOP_OWNER,
    load_config,
)

SKIP_MESSAGE = (
    "skipped: set NEO4J_URI/NEO4J_USERNAME/NEO4J_PASSWORD to clean up the "
    "memory demo records."
)

DELETE_DEMO_HOTEL_LINKS = f"""
CYPHER 25
MATCH ()-[r:{HOTEL_RELATIONSHIP}]->()
WHERE r.workshop_owner = $owner
DELETE r
"""

DELETE_PREFIXED_SESSIONS = """
CYPHER 25
MATCH (c:Conversation)
WHERE c.session_id STARTS WITH $prefix
OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:Message)
DETACH DELETE c, m
"""

DELETE_PREFIXED_USERS = """
CYPHER 25
MATCH (u:User)
WHERE u.identifier STARTS WITH $prefix
DETACH DELETE u
"""

DELETE_ORPHANED_DEMO_PREFERENCES = """
CYPHER 25
MATCH (p:Preference)
WHERE p.workshop_owner = $owner
  AND NOT EXISTS { MATCH (:User)-[:HAS_PREFERENCE]->(p) }
DETACH DELETE p
"""

REMOVE_SHARED_PREFERENCE_MARKERS = """
CYPHER 25
MATCH (p:Preference)
WHERE p.workshop_owner = $owner
  AND EXISTS { MATCH (:User)-[:HAS_PREFERENCE]->(p) }
REMOVE p.workshop_owner
"""

COUNT_HOTELS = "CYPHER 25 MATCH (h:Hotel) RETURN count(h) AS hotels"


def run_cleanup(config: MemoryDemoConfig) -> int:
    """Delete the demo's memory records without changing Hotel nodes."""
    driver = GraphDatabase.driver(
        config.uri, auth=(config.username, config.password)
    )
    try:
        with driver.session(database=config.database) as session:
            hotels_before = session.execute_read(
                lambda tx: tx.run(COUNT_HOTELS).single()["hotels"]
            )

            nodes_deleted = 0
            relationships_deleted = 0
            for query, params in (
                (DELETE_DEMO_HOTEL_LINKS, {"owner": WORKSHOP_OWNER}),
                (DELETE_PREFIXED_SESSIONS, {"prefix": DEMO_ID_PREFIX}),
                (DELETE_PREFIXED_USERS, {"prefix": DEMO_ID_PREFIX}),
                (
                    DELETE_ORPHANED_DEMO_PREFERENCES,
                    {"owner": WORKSHOP_OWNER},
                ),
            ):
                counters = session.execute_write(
                    lambda tx, query=query, params=params: tx.run(
                        query, params
                    ).consume().counters
                )
                nodes_deleted += counters.nodes_deleted
                relationships_deleted += counters.relationships_deleted
            print(
                f"Deleted {nodes_deleted} node(s) and "
                f"{relationships_deleted} relationship(s)."
            )

            session.execute_write(
                lambda tx: tx.run(
                    REMOVE_SHARED_PREFERENCE_MARKERS,
                    {"owner": WORKSHOP_OWNER},
                ).consume()
            )

            hotels_after = session.execute_read(
                lambda tx: tx.run(COUNT_HOTELS).single()["hotels"]
            )
            if hotels_after != hotels_before:
                raise AssertionError(
                    f"Hotel count changed during cleanup: {hotels_before} "
                    f"before, {hotels_after} after. Investigate before "
                    "re-running."
                )
            print(f"Hotel graph intact: {hotels_after} Hotel node(s).")
    finally:
        driver.close()

    print("\nMemory cleanup finished.")
    return 0


def main() -> int:
    """Check prerequisites, then run the scoped cleanup."""
    try:
        config = load_config()
    except RuntimeError:
        print(SKIP_MESSAGE)
        return 0

    try:
        return run_cleanup(config)
    except AssertionError as exc:
        print(f"\nCleanup check failed: {exc}")
        return 1
    except (DriverError, Neo4jError) as exc:
        print(f"\nCleanup could not use Neo4j at {config.uri}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
