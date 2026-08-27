# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Prove the shared setup adds indexes without changing restored graph data."""

from __future__ import annotations

import os

from neo4j import GraphDatabase
from workshop.retrieval_setup import (
    WORKSHOP_INDEX_NAMES,
    ensure_retrieval_indexes,
)


def _counts(driver, database: str) -> tuple[int, int]:
    with driver.session(database=database) as session:
        record = session.run(
            """
            CYPHER 25
            CALL () { MATCH (node) RETURN count(node) AS nodes }
            CALL () { MATCH ()-[relationship]->() RETURN count(relationship) AS relationships }
            RETURN nodes, relationships
            """
        ).single(strict=True)
    return record["nodes"], record["relationships"]


def main() -> int:
    database = os.environ.get("NEO4J_DATABASE") or "neo4j"
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(
            os.environ.get("NEO4J_USERNAME") or "neo4j",
            os.environ["NEO4J_PASSWORD"],
        ),
    )
    try:
        before = _counts(driver, database)
        ensure_retrieval_indexes(driver)
        after = _counts(driver, database)
        with driver.session(database=database) as session:
            indexes = list(
                session.run(
                    """
                    SHOW INDEXES
                    YIELD name, type, state, labelsOrTypes, properties
                    WHERE name IN $names
                    RETURN name, type, state, labelsOrTypes, properties
                    ORDER BY name
                    """,
                    names=list(WORKSHOP_INDEX_NAMES),
                )
            )
    finally:
        driver.close()

    if before != after:
        raise RuntimeError(
            "post-restore index setup changed graph data counts: "
            f"before={before}, after={after}"
        )

    print(
        "Post-restore setup preserved graph data: "
        f"{after[0]} nodes, {after[1]} relationships"
    )
    for index in indexes:
        print(
            f"{index['name']}: {index['type']} {index['state']} "
            f"{index['labelsOrTypes']}.{index['properties']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
