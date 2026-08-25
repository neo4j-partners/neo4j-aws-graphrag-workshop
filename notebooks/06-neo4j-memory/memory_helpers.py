# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Memory client construction for the inspectable Neo4j memory demo.

Builds a ``neo4j-agent-memory`` :class:`MemoryClient` over the same Aura
instance as the hotel knowledge graph, so memory nodes (``Conversation``,
``Message``, ``Preference``, ``User``) land beside the domain nodes where
they can be inspected with plain Cypher.

The construction pattern is adapted from the earlier GraphRAG workshop's
``Lab_5_Agent_Memory/lib/memory_utils.py`` and solves the same non-obvious
problems:

- **Explicit embedder:** in ``neo4j-agent-memory`` 0.5.0 the client builds a
  concrete embedder from ``EmbeddingConfig`` for OpenAI and
  sentence-transformers only and returns ``None`` for every other provider,
  including Bedrock (``MemoryClient._create_embedder``). Left that way, the
  client has no embedder and ``generate_embedding=True`` silently writes
  zero-length vectors, so semantic recall finds nothing. The Bedrock embedder
  is therefore constructed explicitly here and passed via ``embedder=``.
- **Pinned dimensions:** ``EmbeddingConfig`` defaults to OpenAI's 1536
  dimensions. The memory vector indexes must match the vectors Titan Text
  Embeddings V2 actually produces, so dimensions are pinned to 1024.
- **Explicit database:** the library's ``Neo4jConfig`` passes its ``database``
  on every session, which overrides home-database routing. The target database
  is read from ``NEO4J_DATABASE`` so instances whose single database is not
  named ``neo4j`` still work.

Two choices are specific to this demo:

- **Titan Text Embeddings V2, not Nova:** the library's Bedrock embedder
  supports Titan and Cohere request formats only. The memory layer owns its
  own vector indexes, separate from the ``hotel_chunk_embeddings`` index, so
  this is a deliberately separate embedding contract from the workshop's
  pinned Nova chunk embeddings, not a conflict.
- **Multi-tenant mode is on:** every memory write must carry a
  ``user_identifier``, and the store raises ``ValueError`` for any write that
  omits one. That makes the demo's actor-isolation lesson structural rather
  than conventional.

No credentials are read and no connection is opened at import time; both
happen inside :func:`load_config` and ``MemoryClient.connect``.
"""

from __future__ import annotations

import logging
import os
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase
from neo4j_agent_memory import (
    EmbeddingConfig,
    EmbeddingProvider,
    ExtractionConfig,
    ExtractorType,
    MemoryClient,
    MemoryConfig,
    MemorySettings,
)
from neo4j_agent_memory import Neo4jConfig as MemoryNeo4jConfig
from neo4j_agent_memory.embeddings.bedrock import BedrockEmbedder

from workshop.aws_region import aws_region
from workshop.retrieval_contract import (
    MEMORY_EMBEDDING_DIMENSIONS,
    MEMORY_EMBEDDING_MODEL,
)
from pydantic import SecretStr

# The memory vector indexes use Titan Text Embeddings V2, a separate embedding
# contract from the Nova model that embeds the hotel chunks. Titan V2 produces
# 1024-dimensional vectors. The model id and dimensions live in
# workshop.retrieval_contract, not here, because Setup checks Bedrock access
# to the same model before the workshop starts and would otherwise drift from
# this module silently.

# Workshop ownership marker for the memory records this demo writes. It mirrors
# contracts.WORKSHOP_OWNER, a fixed namespace string ("neo4j-ftw-demo-6") the
# shared workshop code reuses as its ownership tag.
# cleanup_memory.py deletes only records carrying this marker, so cleanup can
# never reach the hotel graph or another module's data.
WORKSHOP_OWNER = "neo4j-ftw-demo-8"

# Every session id and user identifier the scenario notebook writes starts
# with this prefix. Cleanup sweeps the prefix as well as the ownership
# marker, so records from a run that failed before the tagging step are
# still removed.
DEMO_ID_PREFIX = "demo08-"

# One committed fixture keeps the participant path deterministic. Every Hotel
# node gets a hotel_id when it is created: the two fixture hotels are pinned
# from workshop/fixtures/hotel_ids.json and the rest get randomUUID(). This
# module anchors on the fixture's name rather than its id, and each query below
# guards on exactly one matching Hotel, so the name is the narrow lookup key
# here.
HERO_HOTEL_NAME = "AnyCompany Cairo Nile View"

# Preference-to-message provenance is one explicit workshop-owned relationship,
# because the library links extracted entities to their source messages but has
# no equivalent for preferences.
PROVENANCE_RELATIONSHIP = "DERIVED_FROM"
HOTEL_RELATIONSHIP = "ABOUT_HOTEL"

PREPARATION_HINT = (
    "Set NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD in the environment or "
    "in a .env file (see .env.example at the repository root) before building "
    "the memory client."
)

_DEMO_DIR = Path(__file__).resolve().parent

# Silence Neo4j server-notification logging. neo4j-agent-memory issues vector
# recall via db.index.vector.queryNodes, which Aura flags as deprecated; the
# driver logs one WARNING-level notification per call to the
# "neo4j.notifications" logger. The Cypher lives inside the memory library and
# MemoryClient builds its own driver, so the query cannot be rewritten and
# driver-level notification filters cannot be passed from here. Raising just
# this logger's level to ERROR drops the deprecation noise while leaving
# genuine errors intact.
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)


@dataclass(frozen=True)
class MemoryDemoConfig:
    """Connection and model settings for the memory demo."""

    uri: str
    username: str
    password: str
    database: str
    region: str


def load_config() -> MemoryDemoConfig:
    """Read the demo configuration from the environment or a ``.env`` file.

    Reads the same NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD settings the
    other demos use, checking this demo's ``.env`` and then the repository
    root ``.env``. Values already present in the environment win.

    Raises:
        RuntimeError: If NEO4J_PASSWORD is not set anywhere.
    """
    load_dotenv(_DEMO_DIR / ".env")
    load_dotenv(_DEMO_DIR.parent.parent / ".env")

    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError(f"NEO4J_PASSWORD is not set. {PREPARATION_HINT}")

    return MemoryDemoConfig(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        username=os.getenv("NEO4J_USERNAME", "neo4j"),
        password=password,
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
        region=aws_region(),
    )


def build_memory_settings(config: MemoryDemoConfig) -> MemorySettings:
    """Assemble ``MemorySettings`` for the bolt (direct-driver) path.

    Embedding-only configuration: Titan V2 supplies the vectors, no LLM is
    constructed, and entity extraction is off (``ExtractorType.NONE``). The
    demo writes memory explicitly, so nothing needs a model to extract
    entities from text. ``multi_tenant=True`` makes every write require a
    ``user_identifier``.
    """
    # 0.5.0 requires this object to size the indexes even though its settings
    # layer emits a migration warning saying the same shape is deprecated.
    # The package is pinned, so suppress only that known warning at the exact
    # construction point instead of adding noise to every participant run.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Passing EmbeddingConfig to MemorySettings.embedding.*",
            category=DeprecationWarning,
        )
        return MemorySettings(
            neo4j=MemoryNeo4jConfig(
                uri=config.uri,
                username=config.username,
                password=SecretStr(config.password),
                database=config.database,
            ),
            # EmbeddingConfig only sizes the vector indexes here; the working
            # embedder is passed to MemoryClient explicitly (see module
            # docstring). dimensions is pinned to Titan V2's 1024 because the
            # field defaults to OpenAI's 1536.
            embedding=EmbeddingConfig(
                provider=EmbeddingProvider.BEDROCK,
                model=MEMORY_EMBEDDING_MODEL,
                dimensions=MEMORY_EMBEDDING_DIMENSIONS,
                aws_region=config.region,
            ),
            extraction=ExtractionConfig(extractor_type=ExtractorType.NONE),
            memory=MemoryConfig(multi_tenant=True),
        )


def build_memory_embedder(config: MemoryDemoConfig) -> BedrockEmbedder:
    """Construct the Bedrock Titan V2 embedder the memory client needs.

    Built explicitly because ``MemoryClient._create_embedder`` returns
    ``None`` for the Bedrock provider in 0.5.0, which would silently write
    zero-length vectors. Construction is credential-free; AWS credentials are
    only exercised when the first embedding call runs.
    """
    return BedrockEmbedder(
        model=MEMORY_EMBEDDING_MODEL,
        region_name=config.region,
    )


def build_memory_client(config: MemoryDemoConfig | None = None) -> MemoryClient:
    """Construct an unconnected ``MemoryClient`` with a working embedder.

    Returned unconnected because ``connect()`` is a coroutine. Open it with::

        memory = build_memory_client()
        await memory.connect()

    and release it with ``await memory.close()``.
    """
    if config is None:
        config = load_config()
    return MemoryClient(
        build_memory_settings(config),
        embedder=build_memory_embedder(config),
    )


def _run_query(
    config: MemoryDemoConfig,
    query: str,
    parameters: dict,
    *,
    write: bool = False,
    driver: Driver | None = None,
) -> list[dict]:
    """Run one workshop-owned query through a managed transaction.

    ``memory.query.cypher`` is read-only by design, so workshop-owned writes
    go through a direct driver session. The same small helper also supports
    the actor-anchored read. ``write`` selects ``session.execute_write`` for
    queries that mutate the graph and ``session.execute_read`` otherwise, so
    each query gets the driver's automatic retry-on-transient-error behavior
    instead of running as a bare auto-commit statement. A caller-supplied
    ``driver`` is reused and left open; otherwise a short-lived driver is
    created and closed.
    """
    owns_driver = driver is None
    if driver is None:
        driver = GraphDatabase.driver(
            config.uri, auth=(config.username, config.password)
        )
    try:
        with driver.session(database=config.database) as session:
            run_transaction = session.execute_write if write else session.execute_read
            return run_transaction(lambda tx: tx.run(query, parameters).data())
    finally:
        if owns_driver:
            driver.close()


def link_preference_to_message_and_hotel(
    config: MemoryDemoConfig,
    preference_id: str,
    message_id: str,
    hotel_name: str,
    *,
    driver: Driver | None = None,
) -> bool:
    """Link one preference to its source message and the fixed Hotel.

    Both relationships are workshop-owned. Matching the existing ``Hotel``
    directly avoids adding ``Entity`` labels or memory properties to canonical
    domain nodes. Returns ``False`` unless the ids and exactly one Hotel match.
    """
    rows = _run_query(
        config,
        f"""
        CYPHER 25
        MATCH (p:Preference {{id: $preference_id}})
        MATCH (m:Message {{id: $message_id}})
        MATCH (h:Hotel {{name: $hotel_name}})
        WITH p, m, collect(h) AS hotels
        WHERE size(hotels) = 1
        WITH p, m, head(hotels) AS h
        MERGE (p)-[:{PROVENANCE_RELATIONSHIP}]->(m)
        MERGE (p)-[about:{HOTEL_RELATIONSHIP}]->(h)
        SET about.workshop_owner = $owner
        RETURN count(*) AS linked
        """,
        {
            "preference_id": preference_id,
            "message_id": message_id,
            "hotel_name": hotel_name,
            "owner": WORKSHOP_OWNER,
        },
        write=True,
        driver=driver,
    )
    return bool(rows and rows[0]["linked"])


def get_actor_preferences_for_hotel(
    config: MemoryDemoConfig,
    user_identifier: str,
    hotel_name: str,
    *,
    driver: Driver | None = None,
) -> list[dict]:
    """Return preferences owned by one actor and linked to one Hotel.

    This actor-anchored graph read is the demo's authorization-aware recall
    path. The library's vector search is intentionally not used because it is
    store-wide in 0.5.0.
    """
    return _run_query(
        config,
        f"""
        CYPHER 25
        MATCH (u:User {{identifier: $user_identifier}})
              -[:HAS_PREFERENCE]->(p:Preference)
              -[:{HOTEL_RELATIONSHIP}]->(h:Hotel {{name: $hotel_name}})
        WHERE p.preference IS NOT NULL
        RETURN p.id AS id, p.category AS category,
               p.preference AS preference, h.name AS hotel
        ORDER BY p.preference
        """,
        {"user_identifier": user_identifier, "hotel_name": hotel_name},
        driver=driver,
    )


def tag_demo_records(
    config: MemoryDemoConfig,
    *,
    session_ids: Sequence[str],
    user_identifiers: Sequence[str],
    driver: Driver | None = None,
) -> int:
    """Stamp the demo's memory records with the workshop ownership marker.

    Sets ``workshop_owner`` on the conversations and messages of the given
    sessions, on the given users, and on the preferences those users own.
    Cleanup then deletes exactly the marked records and nothing else.
    Returns the number of records marked.
    """
    rows = _run_query(
        config,
        """
        CYPHER 25
        OPTIONAL MATCH (c:Conversation)
        WHERE c.session_id IN $session_ids
        OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:Message)
        WITH collect(DISTINCT c) AS conversations,
             collect(DISTINCT m) AS messages
        OPTIONAL MATCH (u:User)
        WHERE u.identifier IN $user_identifiers
        OPTIONAL MATCH (u)-[:HAS_PREFERENCE]->(p:Preference)
        WITH conversations, messages,
             collect(DISTINCT u) AS users,
             collect(DISTINCT p) AS preferences
        WITH conversations + messages + users + preferences AS records
        UNWIND records AS record
        SET record.workshop_owner = $owner
        RETURN count(record) AS marked
        """,
        {
            "session_ids": list(session_ids),
            "user_identifiers": list(user_identifiers),
            "owner": WORKSHOP_OWNER,
        },
        write=True,
        driver=driver,
    )
    return int(rows[0]["marked"]) if rows else 0
