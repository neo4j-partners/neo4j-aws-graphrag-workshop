# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Fixed graph-enriched retrieval shared by Module 3.1 and the Module 4 Lambdas.

Two read paths live here and nothing else. ``search_hotel_knowledge`` is the
semantic path over ``HybridCypherRetriever`` and accepts only ``query``. Index
names, fusion behavior, result count, and graph traversal are deliberately
fixed rather than caller-tunable. ``graph_query`` is the structured path over
``Text2CypherRetriever`` and accepts only ``query`` as well.

Both are exported as functions rather than as Lambda handlers on purpose. The
handler is four lines of event unwrapping that belongs at the Lambda boundary,
in ``notebooks/04-production-agent/lambda_tools/``. What crosses that boundary
unchanged is this file, so the retrieval a participant runs in Module 3 is the
same code the Gateway calls in Module 4.

Neither function writes. ``search_hotel_knowledge`` runs reviewed static
Cypher, and ``graph_query`` runs model-generated Cypher that
``Text2CypherRetriever`` first plans with ``EXPLAIN`` and refuses unless the
planner reports it read-only.

The driver behind both retrievers is cached with ``lru_cache`` and is never
closed by this module. That is fine for a warm, recycled Lambda container,
which is the only caller that matters in production. A notebook that calls
``search_hotel_knowledge`` or ``graph_query`` repeatedly across a long
session and wants to release the connection can close the cached driver and
then call ``_get_driver.cache_clear()`` to drop the reference.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Mapping, Sequence, TypedDict, cast

import boto3
from neo4j import GraphDatabase
from neo4j_graphrag.embeddings.base import Embedder
from neo4j_graphrag.llm.base import LLMInterface
from neo4j_graphrag.retrievers import HybridCypherRetriever, Text2CypherRetriever
from neo4j_graphrag.types import HybridSearchRanker, RetrieverResultItem

from workshop import contracts, graph_connection
from workshop.bedrock_providers import BedrockEmbeddings, BedrockLLM
from workshop.graph_schema import GRAPH_SCHEMA

MAX_EVIDENCE_CHARS = 1_200
MAX_EXACT_TERMS = 20

GROUNDING_INSTRUCTIONS = """
Answer hotel questions only from the returned chunk evidence and graph fields.
Do not infer live room inventory, guaranteed availability, or a completed
booking. Wording such as "subject to availability" describes a policy and is
not evidence that rooms are currently available. If the evidence does not
support the requested fact, say it cannot determine the answer from the
available hotel knowledge.
""".strip()

# ``node`` and ``score`` are supplied by HybridCypherRetriever. The traversal
# is reviewed, static Cypher: no query text is interpolated and no model writes
# or generates any part of it.
#
# The only two interpolated values are MAX_AMENITIES and MAX_EVIDENCE_CHARS,
# the named constants the rest of this module already trims to. Written as
# literals they agreed with the constants by coincidence, so changing a constant
# left the query returning the old bound. Both are module-level ints, never
# caller input. The doubled braces are the f-string escape for the Cypher
# subquery block.
RETRIEVAL_QUERY = f"""
OPTIONAL MATCH (node:Chunk)<-[:FROM_CHUNK]-(candidate:Hotel)
WITH node, score, candidate
WHERE score IS NOT NULL
ORDER BY score DESC,
         coalesce(candidate.hotel_id, '\uffff'),
         coalesce(candidate.name, '\uffff')
WITH node, score, head(collect(candidate)) AS hotel
CALL (hotel) {{
    MATCH (hotel)-[:OFFERS_AMENITY]->(amenity:Amenity)
    WHERE amenity.name IS NOT NULL
    WITH DISTINCT amenity.name AS amenity_name
    ORDER BY amenity_name
    LIMIT {contracts.MAX_AMENITIES}
    RETURN collect(amenity_name) AS amenities
}}
RETURN left(coalesce(node.text, ''), {MAX_EVIDENCE_CHARS}) AS chunk_evidence,
       score AS combined_score,
       hotel.hotel_id AS hotel_id,
       hotel.name AS hotel_name,
       hotel.address AS address,
       hotel.guest_rating AS guest_rating,
       amenities
ORDER BY combined_score DESC,
         coalesce(hotel_id, '\uffff'),
         coalesce(hotel_name, '\uffff')
""".strip()

_TERM_PATTERN = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)


@dataclass(frozen=True)
class Neo4jConfig:
    """Connection values shared by local and deployed retrieval paths.

    ``reservation_command.Neo4jCommandConfig`` is a near-duplicate of this
    class, and merging the two would break the reservation Lambda. That module
    documents why.
    """

    uri: str
    username: str = field(repr=False)
    password: str = field(repr=False)
    database: str

    @classmethod
    def from_environment(cls) -> "Neo4jConfig":
        """Load a participant's Aura connection from local environment values."""
        values = {name: os.environ.get(name) for name in contracts.REQUIRED_NEO4J_ENV}
        missing = [name for name, value in values.items() if not value]
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Missing required Neo4j environment values: {names}")
        return cls(
            uri=values["NEO4J_URI"] or "",
            username=values["NEO4J_USERNAME"] or "",
            password=values["NEO4J_PASSWORD"] or "",
            database=graph_connection.graph_database(),
        )

    @classmethod
    def from_secret(
        cls,
        secret_id: str,
        *,
        secrets_client: Any | None = None,
    ) -> "Neo4jConfig":
        """Load the deployed read connection from an AWS Secrets Manager value."""
        client = secrets_client or boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=secret_id)
        secret = json.loads(response["SecretString"])
        if not isinstance(secret, dict):
            raise ValueError("Neo4j secret must contain a JSON object")
        missing = [name for name in contracts.SECRET_FIELDS if not secret.get(name)]
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Neo4j secret is missing required fields: {names}")
        return cls(**{name: secret[name] for name in contracts.SECRET_FIELDS})


@lru_cache(maxsize=2)
def _get_driver(config: Neo4jConfig):
    """Create once per connection and reuse the driver on warm invocations."""
    return GraphDatabase.driver(
        config.uri,
        auth=(config.username, config.password),
        notifications_min_severity="OFF",
    )


def _format_record(record: Mapping[str, Any]) -> RetrieverResultItem:
    """Preserve evidence separately from its structured graph enrichment."""
    return RetrieverResultItem(
        content=record.get("chunk_evidence") or "",
        metadata={
            "combined_score": record.get("combined_score"),
            "hotel_id": record.get("hotel_id"),
            "hotel_name": record.get("hotel_name"),
            "address": record.get("address"),
            "guest_rating": record.get("guest_rating"),
            "amenities": record.get("amenities") or [],
        },
    )


def build_retriever(
    config: Neo4jConfig,
    *,
    embedder: Embedder | None = None,
) -> HybridCypherRetriever:
    """Build the one fixed workshop retriever around the cached driver."""
    return HybridCypherRetriever(
        driver=_get_driver(config),
        vector_index_name=contracts.CHUNK_VECTOR_INDEX,
        fulltext_index_name=contracts.CHUNK_FULLTEXT_INDEX,
        retrieval_query=RETRIEVAL_QUERY,
        # The same class Module 1 wrote the chunk vectors with, so the query and
        # the stored vectors cannot drift onto different models or widths.
        embedder=embedder or BedrockEmbeddings(),
        result_formatter=_format_record,
        neo4j_database=config.database,
    )


@lru_cache(maxsize=1)
def _get_retriever() -> HybridCypherRetriever:
    secret_id = os.environ.get(contracts.RETRIEVAL_SECRET_ID_ENV)
    config = (
        Neo4jConfig.from_secret(secret_id)
        if secret_id
        else Neo4jConfig.from_environment()
    )
    return build_retriever(config)


def _exact_terms(query: str, evidence: str) -> list[str]:
    """Return bounded query terms using their verbatim spelling in evidence."""
    matches: list[str] = []
    seen: set[str] = set()
    for query_match in _TERM_PATTERN.finditer(query):
        term = query_match.group(0)
        evidence_match = re.search(
            rf"(?<!\w){re.escape(term)}(?!\w)",
            evidence,
            flags=re.IGNORECASE,
        )
        if evidence_match is None:
            continue
        verbatim = evidence_match.group(0)
        key = verbatim.casefold()
        if key in seen:
            continue
        seen.add(key)
        matches.append(verbatim)
        if len(matches) == MAX_EXACT_TERMS:
            break
    return matches


def _clean_amenities(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    unique = {
        amenity.strip()
        for amenity in value
        if isinstance(amenity, str) and amenity.strip()
    }
    return sorted(unique, key=str.casefold)[: contracts.MAX_AMENITIES]


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string or null")
    return value


def _number(value: Any, field: str, *, nullable: bool) -> float | None:
    if value is None:
        if nullable:
            return None
        raise ValueError(f"{field} must be numeric")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field} must be numeric")
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(f"{field} must be numeric") from error


def _to_evidence(query: str, item: RetrieverResultItem) -> contracts.HotelEvidence:
    evidence = str(item.content or "")[:MAX_EVIDENCE_CHARS]
    metadata = item.metadata or {}
    score = metadata.get("combined_score")
    rating = metadata.get("guest_rating")
    return {
        "chunk_evidence": evidence,
        "combined_score": _number(
            score,
            "combined_score",
            nullable=False,
        ),
        "exact_terms": _exact_terms(query, evidence),
        "hotel_id": _optional_string(metadata.get("hotel_id"), "hotel_id"),
        "hotel_name": _optional_string(
            metadata.get("hotel_name"),
            "hotel_name",
        ),
        "address": _optional_string(metadata.get("address"), "address"),
        "guest_rating": _number(
            rating,
            "guest_rating",
            nullable=True,
        ),
        "amenities": _clean_amenities(metadata.get("amenities")),
    }


def search_hotel_knowledge(query: str) -> list[contracts.HotelEvidence]:
    """Search hotel knowledge using the frozen, one-field tool contract."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")

    result = _get_retriever().search(
        query_text=query,
        top_k=contracts.HYBRID_TOP_K,
        ranker=HybridSearchRanker.NAIVE,
    )
    evidence = [
        _to_evidence(query, item)
        for item in result.items[: contracts.HYBRID_TOP_K]
    ]
    return sorted(
        evidence,
        key=lambda item: (
            -item["combined_score"],
            item["hotel_id"] or "\uffff",
            item["hotel_name"] or "\uffff",
        ),
    )


# --------------------------------------------------------------------------- #
# The structured path: graph_query
# --------------------------------------------------------------------------- #

# A Text2Cypher prompt is only as safe as the schema it is given, so the schema
# is rendered from GRAPH_SCHEMA rather than restated as a literal. A hand-typed
# copy agrees with the extraction contract on the day it is written and drifts
# the first time a property is added, which produces Cypher against properties
# the build never wrote and an empty result with no error.
MAX_GRAPH_QUERY_RECORDS = 25

GRAPH_QUERY_EXAMPLES = (
    "USER INPUT: What is the average guest rating of hotels in Paris? "
    "CYPHER: MATCH (hotel:Hotel) WHERE toLower(hotel.address) CONTAINS 'paris' "
    "AND hotel.guest_rating IS NOT NULL RETURN avg(hotel.guest_rating) AS average_rating",
    "USER INPUT: How many hotels offer a spa? "
    "CYPHER: MATCH (hotel:Hotel)-[:OFFERS_AMENITY]->(amenity:Amenity) "
    "WHERE toLower(amenity.name) CONTAINS 'spa' RETURN count(DISTINCT hotel) AS hotel_count",
    "USER INPUT: What is the guest rating of the hotel named Example Hotel? "
    "CYPHER: MATCH (hotel:Hotel {name: 'Example Hotel'}) "
    "RETURN hotel.guest_rating AS guest_rating",
)

GRAPH_QUERY_PROMPT = """
Generate one read-only Cypher query that answers the user question.
Use only the labels, properties, and relationships in the supplied schema.
Never write, merge, or delete data, and never call a procedure.
Return only the columns the question asks for, and nothing else.
Return only the Cypher query, with no markdown fence and no explanation.
Schema:
{schema}
Examples:
{examples}
User question: {query_text}
""".strip()


class GraphQueryResult(TypedDict):
    """What the structured tool hands back: the Cypher, and what it returned."""

    cypher: str
    records: list[dict[str, Any]]


def pinned_schema_text() -> str:
    """Render GRAPH_SCHEMA as the schema block a Text2Cypher prompt takes."""
    lines = ["Node properties:"]
    for node in cast(Sequence[Mapping[str, Any]], GRAPH_SCHEMA["node_types"]):
        properties = cast(
            Sequence[Mapping[str, str]], node.get("properties", ())
        )
        rendered = ", ".join(
            f"{prop['name']}: {prop.get('type', 'STRING')}" for prop in properties
        )
        lines.append(f"{node['label']} {{{rendered}}}")
    lines.append("Relationships:")
    for start, relationship, end in cast(
        Sequence[tuple[str, str, str]], GRAPH_SCHEMA["patterns"]
    ):
        lines.append(f"(:{start})-[:{relationship}]->(:{end})")
    return "\n".join(lines)


def _format_graph_record(record: Mapping[str, Any]) -> RetrieverResultItem:
    """Keep a returned row as named columns rather than a repr.

    Without a formatter the base retriever stringifies each row, so a rating of
    4.5 arrives as the text ``<Record guest_rating=4.5>``. That reads fine and
    cannot be compared to a number, which is exactly the shape of failure this
    tool has to make visible.
    """
    return RetrieverResultItem(content=_json_safe(dict(record)))


def build_graph_query_retriever(
    config: Neo4jConfig,
    *,
    llm: LLMInterface | None = None,
) -> Text2CypherRetriever:
    """Build the one fixed structured retriever around the cached driver."""
    return Text2CypherRetriever(
        driver=_get_driver(config),
        llm=llm or BedrockLLM(),
        neo4j_schema=pinned_schema_text(),
        examples=list(GRAPH_QUERY_EXAMPLES),
        custom_prompt=GRAPH_QUERY_PROMPT,
        result_formatter=_format_graph_record,
        neo4j_database=config.database,
    )


@lru_cache(maxsize=1)
def _get_graph_query_retriever() -> Text2CypherRetriever:
    secret_id = os.environ.get(contracts.RETRIEVAL_SECRET_ID_ENV)
    config = (
        Neo4jConfig.from_secret(secret_id)
        if secret_id
        else Neo4jConfig.from_environment()
    )
    return build_graph_query_retriever(config)


def _json_safe(value: Any) -> Any:
    """Return a value the Gateway can serialize, without losing a number.

    Neo4j hands back temporal and spatial types that ``json.dumps`` refuses.
    Stringifying everything would turn 4.5 into "4.5" and make an exact check
    on a rating impossible, so only the types JSON has no equivalent for are
    converted.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)


def graph_query(query: str) -> GraphQueryResult:
    """Answer a structured hotel question with model-generated read-only Cypher.

    This is the one place in the workshop where the database executes a
    statement no human wrote. The generated Cypher is returned alongside its
    records so a caller can always see what ran.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")

    result = _get_graph_query_retriever().search(query_text=query)
    records = [
        cast(dict[str, Any], item.content)
        for item in result.items[:MAX_GRAPH_QUERY_RECORDS]
    ]
    return {
        "cypher": str((result.metadata or {}).get("cypher", "")),
        "records": records,
    }
