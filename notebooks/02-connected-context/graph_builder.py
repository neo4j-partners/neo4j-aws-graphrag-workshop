# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Shared knowledge-graph build machinery for Module 1.

Two entry points share the pinned schema, the extraction pipeline, the
verification queries, and the report, so the script path and the notebook path
cannot drift apart the way they previously did (one verified on `h.id`, the
other on `h.name`, and neither matched the notebook).

`run_additive_build` is what Module 1's notebook calls. It extracts a handful
of held-out documents into the graph the participant restored from the dump,
and it deletes nothing except a previous copy of those same documents. Work
the participant already has is never at risk.

`run_build` is the facilitator's rebuild-from-scratch tool, reached through
`prepare_graph.py`. It wipes first, and its order is deliberate:

    parse amenities -> wipe -> canary (3 docs) -> verify typing and identity
    -> wipe canary -> ingest all -> retry failures -> verify one Hotel per source
    -> materialize amenities -> report

The wipe precedes the canary because a from-scratch rebuild has nothing worth
preserving across a failed build, and because the canary then runs against an
empty graph, so the check reflects exactly what that run extracted. Neither
reason holds for `run_additive_build`, which is why it is a separate function
rather than `run_build` behind a flag.
"""

import asyncio
import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from graph_config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EXTRACTION_MAX_TOKENS,
)
from neo4j import Driver, GraphDatabase
from neo4j_graphrag.components.text_splitters.fixed_size_splitter import (
    FixedSizeSplitter,
)
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from workshop.amenities import (
    AmenityMaterializationError,
    AmenitySectionError,
    ParsedAmenities,
    ensure_amenity_constraint,
    materialize_amenities,
    parse_amenity_section,
)
from workshop.aws_region import aws_region
from workshop.bedrock_providers import (
    BedrockEmbeddings,
    BedrockLLM,
    default_model_id,
)
from workshop.graph_connection import graph_database, neo4j_auth, neo4j_uri
from workshop.graph_schema import (
    LLM_EXTRACTION_SCHEMA,
    LLM_SCHEMA_NODE_LABELS,
)
from workshop.retrieval_contract import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL_ID,
    EMBEDDING_PURPOSE,
)
from workshop.retrieval_setup import (
    ensure_retrieval_indexes,
    missing_source_fixtures,
    report_readiness,
)

# The per-document bound the build enforces with `asyncio.wait_for`. It sits
# above a single Bedrock read timeout, not above the whole retry chain:
# `bedrock_providers.BEDROCK_CONFIG` allows 6 attempts at 45s, so a worst case
# of six consecutive hung sockets runs to 270s. That case ends with this
# timeout firing and the build moving on while the worker thread underneath
# keeps going, which is the trade recorded next to BEDROCK_CONFIG.
DOC_TIMEOUT_SECONDS = 180

# The canary samples several documents rather than one. LLM extraction is
# stochastic, so a single-document gate intermittently fails a healthy
# pipeline, and a participant who hits that concludes the module is broken.
CANARY_DOCS = 3

# A document that failed once is tried once more. Extraction failures are
# usually a throttle or a timeout rather than a bad document, and without a
# retry one lost document costs a full rebuild.
RETRY_PASSES = 1

# Module 1 stays sequential by default. Facilitator release builds can opt into
# a small amount of parallelism with GRAPH_BUILD_CONCURRENCY. The upper bound
# protects Bedrock quotas and Neo4j's transaction pool from an accidental
# unbounded release invocation.
DEFAULT_BUILD_CONCURRENCY = 1
MAX_BUILD_CONCURRENCY = 8

# `ingest`'s `asyncio.wait_for` timeout cannot cancel a Bedrock call already
# handed to a worker thread (see `bedrock_providers.BEDROCK_CONFIG`), so a
# "timed-out" document can still be writing to Neo4j after `retry_failures`
# decides to clear and re-ingest it. `_recent_write_exists` treats a document
# whose most recent attempt started within this window as still plausibly
# in flight, and `retry_failures` defers clearing it rather than racing that
# write. This is a heuristic, not a guarantee: it narrows the window instead
# of closing it. The real fix is a cancellable future (see the
# `ProcessPoolExecutor` note in `bedrock_providers.py`).
RECENT_WRITE_SECONDS = 30

# Everything neo4j-graphrag writes carries this label, so the wipe can be
# scoped to pipeline output instead of `MATCH (n) DETACH DELETE n`, which would
# also take out anything else sharing the instance. Note what it does not buy:
# the label marks pipeline output, not one run's output. Any dump restored into
# this graph that was itself produced by this pipeline carries the label, and
# the wipe takes it with everything else.
KG_LABEL = "__KGBuilder__"

# Increment this when extraction semantics change in a way that is not already
# represented by the schema, model, embedding, or chunk settings included in
# `build_contract`. A resumed build only reuses Documents carrying this exact
# contract, so old partial graphs fail closed instead of mixing build recipes.
BUILD_CONTRACT_VERSION = 1


def build_concurrency() -> int:
    """Return the validated number of documents to extract concurrently."""
    raw_value = os.getenv(
        "GRAPH_BUILD_CONCURRENCY",
        str(DEFAULT_BUILD_CONCURRENCY),
    )
    try:
        concurrency = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            "GRAPH_BUILD_CONCURRENCY must be an integer from 1 to "
            f"{MAX_BUILD_CONCURRENCY}, found {raw_value!r}"
        ) from exc
    if not 1 <= concurrency <= MAX_BUILD_CONCURRENCY:
        raise ValueError(
            "GRAPH_BUILD_CONCURRENCY must be from 1 to "
            f"{MAX_BUILD_CONCURRENCY}, found {concurrency}"
        )
    return concurrency


def source_sha256(path: Path) -> str:
    """Return the digest used to prove a checkpoint matches its source."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_contract() -> str:
    """Return a stable digest of settings that affect extraction output."""
    payload = {
        "version": BUILD_CONTRACT_VERSION,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "extraction_max_tokens": EXTRACTION_MAX_TOKENS,
        "llm_model_id": default_model_id(),
        "embedding_model_id": EMBEDDING_MODEL_ID,
        "embedding_dimensions": EMBEDDING_DIMENSIONS,
        "embedding_purpose": EMBEDDING_PURPOSE,
        "schema": LLM_EXTRACTION_SCHEMA,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def connect() -> Driver:
    """Open a Neo4j driver using NEO4J_USERNAME / NEO4J_PASSWORD."""
    return GraphDatabase.driver(neo4j_uri(), auth=neo4j_auth())


def session(driver: Driver):
    """Open a session against the configured database."""
    return driver.session(database=graph_database())


def build_pipeline(driver: Driver) -> SimpleKGPipeline:
    """Construct the extraction pipeline with the schema pinned.

    Without `schema=`, `SimpleKGPipeline` asks the LLM to invent a schema per
    chunk, and the labels it invents do not match what the agent is told to
    query.
    """
    llm = BedrockLLM(
        region_name=aws_region(),
        max_tokens=EXTRACTION_MAX_TOKENS,
    )
    embedder = BedrockEmbeddings(
        region_name=aws_region(),
    )
    return SimpleKGPipeline(
        llm=llm,
        driver=driver,
        embedder=embedder,
        # neo4j-graphrag normalizes pattern tuples into compiled regular
        # expressions in place. Protect the shared schema because
        # `build_contract` serializes it after pipeline construction.
        schema=deepcopy(LLM_EXTRACTION_SCHEMA),
        text_splitter=FixedSizeSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        ),
        from_pdf=False,
        on_error="RAISE",
        perform_entity_resolution=False,
        neo4j_database=graph_database(),
    )


def snapshot_chunk_ids(driver: Driver) -> set[str]:
    """Return the element IDs of every :Chunk currently in the graph.

    Chunks are never merged, so they are a stable handle on what this run just
    extracted without relying on generated entity properties.
    """
    with session(driver) as neo4j_session:
        return {
            record["id"]
            for record in neo4j_session.run("MATCH (c:Chunk) RETURN elementId(c) AS id")
        }


def clear_extracted_graph(driver: Driver) -> None:
    """Delete every node the extraction pipeline ever wrote.

    Not scoped to a single run: see the note on `KG_LABEL`. Only `run_build`,
    the rebuild-from-scratch path, may call this. `run_additive_build` uses
    `clear_document` so it touches nothing but its own documents.
    """
    with session(driver) as neo4j_session:
        neo4j_session.run(f"MATCH (n:`{KG_LABEL}`) DETACH DELETE n")


# Entities are deleted only when every chunk they came from belongs to the
# document being cleared. This also handles shared deterministic Amenity nodes:
# an Amenity used by another document remains, while its relationship to the
# deleted Hotel and Chunk is removed by the detach operations.
# Keyed on `source_filename`, not `path`. `path` is the pipeline's own idea of
# where the text came from, and because `ingest` passes `text=` rather than a
# file handle, every document in the graph gets the synthetic path
# `document.txt`. Matching on it would find nothing on a good day and all 295
# documents on a bad one. `source_filename` is the value `ingest` attaches
# through `document_metadata`, and it is unique per document.
DELETE_DOCUMENT_ENTITIES = """
MATCH (d:Document {source_filename: $filename})<-[:FROM_DOCUMENT]-(c:Chunk)
WITH collect(c) AS chunks
UNWIND chunks AS chunk
MATCH (entity)-[:FROM_CHUNK]->(chunk)
WITH DISTINCT entity, chunks
WHERE all(source IN [(entity)-[:FROM_CHUNK]->(x) | x] WHERE source IN chunks)
DETACH DELETE entity
"""

DELETE_DOCUMENT_LEXICAL = """
MATCH (d:Document {source_filename: $filename})
OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
DETACH DELETE c, d
"""


def clear_document(driver: Driver, filename: str) -> None:
    """Remove everything one source document wrote, so a retry starts clean.

    A run that fails inside extraction can still have committed the lexical
    graph, and every node here is written with `CREATE` rather than `MERGE`. A
    plain retry would therefore leave a second `:Document` and a second
    `:Chunk` for that file, and the count assertion at the end of the build
    would fire on a graph that is otherwise complete.
    """
    with session(driver) as neo4j_session:
        neo4j_session.execute_write(
            lambda tx: tx.run(DELETE_DOCUMENT_ENTITIES, filename=filename).consume()
        )
        neo4j_session.execute_write(
            lambda tx: tx.run(DELETE_DOCUMENT_LEXICAL, filename=filename).consume()
        )


def check_documents_addressable(driver: Driver, paths: list[Path]) -> list[str]:
    """Return a list of problems with the `source_filename` on this run's documents.

    Guards the invariant `clear_document` depends on: every ingested file must
    land as exactly one `:Document` reachable by its own filename. The property
    arrives through `document_metadata`, which is pipeline behaviour rather than
    anything this module controls, so a library upgrade could stop populating it
    and nothing else here would notice. The symptom would be silent: retries and
    re-runs would quietly duplicate documents instead of replacing them, and
    Module 1's closing query would return no rows over a graph that looks fine.
    """
    problems: list[str] = []
    with session(driver) as neo4j_session:
        counts = {
            record["filename"]: record["count"]
            for record in neo4j_session.run(
                """
                MATCH (d:Document)
                WHERE d.source_filename IN $filenames
                RETURN d.source_filename AS filename, count(d) AS count
                """,
                filenames=[path.name for path in paths],
            )
        }
    for path in paths:
        found = counts.get(path.name, 0)
        if found == 0:
            problems.append(
                f"{path.name} has no :Document carrying its source_filename"
            )
        elif found > 1:
            problems.append(f"{path.name} has {found} :Document nodes, expected 1")
    return problems


def check_source_hotels(driver: Driver, paths: list[Path]) -> list[str]:
    """Require one Document, Chunk, and distinct Hotel per source file."""
    filenames = [path.name for path in paths]
    with session(driver) as neo4j_session:
        records = list(
            neo4j_session.run(
                """
                CYPHER 25
                UNWIND $filenames AS filename
                OPTIONAL MATCH (d:Document {source_filename: filename})
                OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
                OPTIONAL MATCH (h:Hotel)-[:FROM_CHUNK]->(c)
                RETURN filename,
                       count(DISTINCT d) AS document_count,
                       count(DISTINCT c) AS chunk_count,
                       count(DISTINCT h) AS hotel_count,
                       collect(DISTINCT elementId(h)) AS hotel_element_ids
                ORDER BY filename
                """,
                filenames=filenames,
            )
        )

    problems: list[str] = []
    hotel_sources: dict[str, list[str]] = {}
    for record in records:
        filename = record["filename"]
        document_count = record["document_count"]
        chunk_count = record["chunk_count"]
        hotel_count = record["hotel_count"]
        if document_count != 1:
            problems.append(
                f"{filename} has {document_count} Document nodes, expected 1"
            )
        if chunk_count != 1:
            problems.append(
                f"{filename} has {chunk_count} Chunk nodes through provenance, "
                "expected 1"
            )
        if hotel_count != 1:
            problems.append(
                f"{filename} has {hotel_count} Hotels through provenance, expected 1"
            )
            continue
        hotel_id = record["hotel_element_ids"][0]
        hotel_sources.setdefault(hotel_id, []).append(filename)

    for source_names in hotel_sources.values():
        if len(source_names) > 1:
            joined = ", ".join(sorted(source_names))
            problems.append(f"one Hotel node is shared by source documents: {joined}")
    return problems


def resumable_paths(
    driver: Driver,
    paths: list[Path],
    contract: str,
) -> tuple[list[Path], list[Path]]:
    """Partition sources into proven-complete and must-retry paths.

    Reuse is deliberately strict. The source bytes and build contract must
    match, and the graph must contain exactly one Document, one Chunk, and one
    Hotel through provenance. A Hotel shared by two sources proves neither
    source complete.
    """
    sources = [
        {"filename": path.name, "source_sha256": source_sha256(path)} for path in paths
    ]
    with session(driver) as neo4j_session:
        records = list(
            neo4j_session.run(
                """
                CYPHER 25
                UNWIND $sources AS source
                OPTIONAL MATCH (d:Document {source_filename: source.filename})
                OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
                OPTIONAL MATCH (h:Hotel)-[:FROM_CHUNK]->(c)
                WITH source,
                     count(DISTINCT d) AS document_count,
                     count(DISTINCT c) AS chunk_count,
                     count(DISTINCT h) AS hotel_count,
                     collect(DISTINCT d.source_sha256) AS source_sha256_values,
                     collect(DISTINCT d.build_contract) AS build_contract_values,
                     collect(DISTINCT elementId(h)) AS hotel_element_ids
                OPTIONAL MATCH (candidate_hotel:Hotel)
                WHERE elementId(candidate_hotel) IN hotel_element_ids
                OPTIONAL MATCH (candidate_hotel)-[:FROM_CHUNK]->(:Chunk)
                               -[:FROM_DOCUMENT]->(hotel_source:Document)
                RETURN source.filename AS filename,
                       source.source_sha256 AS expected_source_sha256,
                       document_count,
                       chunk_count,
                       hotel_count,
                       source_sha256_values,
                       build_contract_values,
                       hotel_element_ids,
                       count(DISTINCT hotel_source) AS hotel_source_document_count
                ORDER BY filename
                """,
                sources=sources,
            )
        )

    candidates: dict[str, str] = {}
    hotel_sources: dict[str, list[str]] = {}
    for record in records:
        if (
            record["document_count"] == 1
            and record["chunk_count"] == 1
            and record["hotel_count"] == 1
            and record["hotel_source_document_count"] == 1
            and record["source_sha256_values"] == [record["expected_source_sha256"]]
            and record["build_contract_values"] == [contract]
        ):
            filename = record["filename"]
            hotel_id = record["hotel_element_ids"][0]
            candidates[filename] = hotel_id
            hotel_sources.setdefault(hotel_id, []).append(filename)

    shared_sources = {
        filename
        for filenames in hotel_sources.values()
        if len(filenames) > 1
        for filename in filenames
    }
    complete_names = set(candidates) - shared_sources
    complete = [path for path in paths if path.name in complete_names]
    pending = [path for path in paths if path.name not in complete_names]
    return complete, pending


def parse_amenity_lists(paths: list[Path]) -> list[ParsedAmenities]:
    """Parse every authoritative list before any graph mutation begins."""
    return [
        parse_amenity_section(
            path.read_text(encoding="utf-8"),
            path.name,
        )
        for path in paths
    ]


def materialize_amenity_lists(
    driver: Driver,
    parsed_amenities: list[ParsedAmenities],
) -> int:
    """Attach all parsed amenities after extraction and retry have succeeded."""
    database = graph_database()
    ensure_amenity_constraint(driver, database)
    return sum(
        materialize_amenities(driver, database, parsed) for parsed in parsed_amenities
    )


def check_amenity_assertions(
    driver: Driver,
    parsed_amenities: list[ParsedAmenities],
) -> list[str]:
    """Compare exact source amenity pairs with graph traversal results."""
    expected = {
        (parsed.source_filename, name)
        for parsed in parsed_amenities
        for name in parsed.names
    }
    filenames = [parsed.source_filename for parsed in parsed_amenities]
    with session(driver) as neo4j_session:
        records = list(
            neo4j_session.run(
                """
                CYPHER 25
                UNWIND $filenames AS source_filename
                MATCH (document:Document {source_filename: source_filename})
                MATCH (chunk:Chunk)-[:FROM_DOCUMENT]->(document)
                MATCH (hotel:Hotel)-[:FROM_CHUNK]->(chunk)
                MATCH (hotel)-[:OFFERS_AMENITY]->(amenity:Amenity)
                RETURN DISTINCT source_filename, amenity.name AS amenity_name
                """,
                filenames=filenames,
            )
        )
    actual = {(record["source_filename"], record["amenity_name"]) for record in records}
    missing = expected - actual
    unexpected = actual - expected
    print(
        f"  amenity assertions reconciled: {len(actual)} graph pairs, "
        f"{len(expected)} source pairs"
    )

    problems: list[str] = []
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
    return problems


async def ingest(pipeline: SimpleKGPipeline, paths: list[Path]) -> list[Path]:
    """Run every document through the pipeline. Returns the ones that failed."""
    total = len(paths)
    contract = build_contract()
    concurrency = build_concurrency()
    semaphore = asyncio.Semaphore(concurrency)
    if total:
        print(f"  extraction concurrency: {concurrency}")

    async def ingest_one(index: int, path: Path) -> bool:
        async with semaphore:
            text = path.read_text(encoding="utf-8")
            prefix = f"  [{index}/{total}] {path.name}"
            print(f"{prefix}... started", flush=True)
            # `run_id` and `ingest_started_at` land on this document's
            # :Document node through `document_metadata` (the same mechanism
            # that attaches `source_filename`). `_recent_write_exists` reads
            # `ingest_started_at` back to distinguish a comfortably-finished
            # failure from one that might still be writing.
            try:
                await asyncio.wait_for(
                    pipeline.run_async(
                        file_path=path.name,
                        text=text,
                        document_metadata={
                            "source_filename": path.name,
                            "source_sha256": source_sha256(path),
                            "build_contract": contract,
                            "run_id": uuid4().hex,
                            "ingest_started_at": datetime.now(timezone.utc).isoformat(),
                        },
                    ),
                    timeout=DOC_TIMEOUT_SECONDS,
                )
                print(f"{prefix}... ✅", flush=True)
                return False
            except asyncio.TimeoutError:
                print(f"{prefix}... ⏰ timeout", flush=True)
                return True
            except Exception as exc:  # noqa: BLE001 - isolate one bad document
                print(f"{prefix}... ❌ {exc}", flush=True)
                return True

    failed = await asyncio.gather(
        *(ingest_one(index, path) for index, path in enumerate(paths, 1))
    )
    return [path for path, did_fail in zip(paths, failed) if did_fail]


def _recent_write_exists(
    driver: Driver, filename: str, within_seconds: int = RECENT_WRITE_SECONDS
) -> bool:
    """Return whether `filename`'s most recent ingest attempt started recently.

    A proxy for "might still be writing", not a direct measurement of it: a
    worker thread running `BedrockLLM.invoke` past the `asyncio.wait_for`
    timeout carries on writing after the timeout fires, and this graph has no
    per-write timestamp to observe that directly. `ingest_started_at` is set
    once, when the attempt begins, so a document whose only committed value is
    from moments ago is still a plausible in-flight write.
    """
    with session(driver) as neo4j_session:
        record = neo4j_session.run(
            """
            MATCH (d:Document {source_filename: $filename})
            WHERE d.ingest_started_at IS NOT NULL
              AND datetime(d.ingest_started_at)
                  > datetime() - duration({seconds: $within_seconds})
            RETURN count(d) > 0 AS recent
            """,
            filename=filename,
            within_seconds=within_seconds,
        ).single()
    return bool(record and record["recent"])


async def retry_failures(
    driver: Driver,
    pipeline: SimpleKGPipeline,
    failures: list[Path],
) -> list[Path]:
    """Re-ingest failed documents, clearing each one's partial write first.

    Without this, a single throttled document costs a fifteen-minute rebuild:
    the count assertion below fires, and the next run clears the graph and
    starts over. Returns whatever still failed after `RETRY_PASSES`.

    A document is only cleared if `_recent_write_exists` says its last attempt
    did not start within `RECENT_WRITE_SECONDS`. One that did is left alone
    this pass instead: clearing it here could race a write still landing from
    the timed-out attempt (see `RECENT_WRITE_SECONDS`), leaving a corrupted or
    duplicated partial extraction underneath the retry.
    """
    remaining = failures
    for attempt in range(1, RETRY_PASSES + 1):
        if not remaining:
            break
        print(
            f"\nRetry pass {attempt} of {RETRY_PASSES}: "
            f"{len(remaining)} document(s) to re-ingest"
        )
        ready = []
        for path in remaining:
            if _recent_write_exists(driver, path.name):
                print(
                    f"  {path.name}: deferring, a write landed within the last "
                    f"{RECENT_WRITE_SECONDS}s (possible in-flight write)"
                )
                continue
            clear_document(driver, path.name)
            ready.append(path)
        if not ready:
            continue
        still_failed = await ingest(pipeline, ready)
        deferred = [path for path in remaining if path not in ready]
        remaining = still_failed + deferred
    return remaining


def check_schema_held(driver: Driver, chunk_ids: set[str]) -> list[str]:
    """Return a list of problems with what `chunk_ids` extracted.

    Entities are reached by traversing `(:Chunk)<-[:FROM_CHUNK]-(entity)` from
    the chunks this run created, so the check does not depend on generated
    entity properties.

    An empty list means extraction honoured the pinned schema in
    `workshop.graph_schema`, which is the contract every later module queries.
    """
    problems: list[str] = []
    ids = list(chunk_ids)
    with session(driver) as neo4j_session:
        labels = {
            record["label"]: record["count"]
            for record in neo4j_session.run(
                """
                MATCH (c:Chunk)<-[:FROM_CHUNK]-(n)
                WHERE elementId(c) IN $ids
                UNWIND labels(n) AS label
                WITH label, count(*) AS count
                WHERE NOT label STARTS WITH '__'
                RETURN label, count
                """,
                ids=ids,
            )
        }
        print(f"  labels produced: {labels}")

        stray = sorted(set(labels) - set(LLM_SCHEMA_NODE_LABELS))
        if stray:
            problems.append(f"labels outside the LLM extraction schema: {stray}")

        if not labels.get("Hotel"):
            problems.append("no :Hotel node was extracted from these chunks")
            return problems

        # Extraction is stochastic: an LLM can miss a field on any single
        # document without the pipeline being broken. The gate is therefore
        # "at least one document extracted a complete Hotel", not "every one
        # did". The off-schema label check above stays strict,
        # because inventing an `Address` node is a schema failure rather than
        # a bad roll.
        hotels = list(
            neo4j_session.run(
                """
                MATCH (c:Chunk)<-[:FROM_CHUNK]-(h:Hotel)
                WHERE elementId(c) IN $ids
                OPTIONAL MATCH (h)-[r]->(n)
                WHERE type(r) IN ['HAS_ROOM', 'OFFERS_AMENITY',
                                  'HAS_POLICY', 'PROVIDES_SERVICE']
                RETURN DISTINCT elementId(h) AS id, h.name AS name,
                       h.address AS address, h.guest_rating AS guest_rating,
                       count(r) AS relationships
                """,
                ids=ids,
            )
        )

        conforming = []
        for hotel in hotels:
            missing = [
                field
                for field in ("name", "address", "guest_rating")
                if hotel[field] is None
            ]
            is_conforming = not missing and hotel["relationships"] > 0
            if is_conforming:
                conforming.append(hotel)
            status = "ok" if is_conforming else "INCOMPLETE"
            print(
                f"  hotel: {hotel['name']!r} rating={hotel['guest_rating']} "
                f"rels={hotel['relationships']} [{status}]"
            )

        print(f"  conforming hotels: {len(conforming)}/{len(hotels)}")
        if not conforming:
            problems.append(
                f"none of the {len(hotels)} extracted hotels had name, address, "
                "guest_rating and a contracted relationship"
            )

    return problems


def count_documents(driver: Driver) -> int:
    """Return the number of :Document nodes in the graph.

    The invariant: after a clean build this equals the number of source files
    that were processed. Anything else means two builds overlapped or a partial
    run was left behind, and the resulting graph looks plausible while being
    wrong.
    """
    with session(driver) as neo4j_session:
        return neo4j_session.run(
            "MATCH (d:Document) RETURN count(d) AS count"
        ).single()["count"]


def count_chunks(driver: Driver) -> int:
    """Return the number of :Chunk nodes in the graph."""
    with session(driver) as neo4j_session:
        return neo4j_session.run("MATCH (c:Chunk) RETURN count(c) AS count").single()[
            "count"
        ]


def report(driver: Driver) -> None:
    """Print the graph shape plus the three queries the notebook depends on."""
    with session(driver) as neo4j_session:
        print("\nNode labels:")
        node_counts = neo4j_session.run(
            """
            CYPHER 25
            CALL () { MATCH (hotel:Hotel) RETURN count(hotel) AS hotels }
            CALL () { MATCH (room:Room) RETURN count(room) AS rooms }
            CALL () { MATCH (amenity:Amenity) RETURN count(amenity) AS amenities }
            CALL () { MATCH (policy:Policy) RETURN count(policy) AS policies }
            CALL () { MATCH (service:Service) RETURN count(service) AS services }
            RETURN hotels, rooms, amenities, policies, services
            """
        ).single()
        extracted_counts = {
            label: count
            for label, count in {
                "Hotel": node_counts["hotels"],
                "Room": node_counts["rooms"],
                "Amenity": node_counts["amenities"],
                "Policy": node_counts["policies"],
                "Service": node_counts["services"],
            }.items()
            if count
        }
        for label, count in sorted(
            extracted_counts.items(), key=lambda item: item[1], reverse=True
        ):
            print(f"  :{label}: {count}")

        print("\nRelationship types:")
        for record in neo4j_session.run(
            """
            CYPHER 25
            MATCH ()-[r:HAS_ROOM|OFFERS_AMENITY|HAS_POLICY|PROVIDES_SERVICE]->()
            RETURN type(r) AS rel, count(*) AS count
            ORDER BY count DESC
            """
        ):
            print(f"  :{record['rel']}: {record['count']}")

        print("\n--- Acceptance queries (these are what the notebook asks) ---")

        record = neo4j_session.run(
            """
            MATCH (h:Hotel)
            WHERE toLower(h.address) CONTAINS 'paris'
            RETURN avg(h.guest_rating) AS avg_rating, count(h) AS hotels
            """
        ).single()
        print(
            f"  Aggregation  avg guest rating in Paris: {record['avg_rating']} "
            f"across {record['hotels']} hotels"
        )

        record = neo4j_session.run(
            """
            MATCH (h:Hotel)-[:OFFERS_AMENITY]->(a:Amenity)
            WHERE toLower(a.name) CONTAINS 'pool'
            RETURN count(DISTINCT h) AS hotels
            """
        ).single()
        print(f"  Counting  hotels with a pool: {record['hotels']}")

        print("  Connected traversal  Cairo hotels with spa AND pool:")
        rows = neo4j_session.run(
            """
            MATCH (h:Hotel)-[:OFFERS_AMENITY]->(spa:Amenity),
                  (h)-[:OFFERS_AMENITY]->(pool:Amenity)
            WHERE toLower(h.address) CONTAINS 'cairo'
              AND toLower(spa.name) CONTAINS 'spa'
              AND toLower(pool.name) CONTAINS 'pool'
            RETURN DISTINCT h.name AS name, h.guest_rating AS rating
            """
        )
        found = False
        for record in rows:
            found = True
            print(f"    {record['name']}: {record['rating']}")
        if not found:
            print("    (none)")


async def run_build(paths: list[Path], title: str, *, resume: bool = False) -> int:
    """Canary, ingest, verify, and report, optionally resuming a checkpoint."""
    if not paths:
        print("No documents selected.")
        return 1
    try:
        build_concurrency()
    except ValueError as exc:
        print(f"❌ Extraction concurrency is invalid: {exc}")
        return 1

    missing_sources = missing_source_fixtures(paths)
    if missing_sources:
        print(
            "Source documents that later modules depend on are missing from this build:"
        )
        for filename in missing_sources:
            print(f"  - {filename}")
        return 1

    try:
        parsed_amenities = parse_amenity_lists(paths)
    except AmenitySectionError as exc:
        print(f"❌ Amenity source validation failed: {exc}")
        return 1

    print(f"{title}: {len(paths)} documents")
    print(f"Database: {graph_database()}\n")
    driver = connect()
    try:
        pipeline = None
        pending = paths
        complete: list[Path] = []
        if resume:
            print("Inspecting the retained graph checkpoint...")
            complete, pending = resumable_paths(driver, paths, build_contract())
            print(
                f"✅ Retaining {len(complete)} proven-complete source(s); "
                f"{len(pending)} source(s) require extraction"
            )
            for path in pending:
                clear_document(driver, path.name)
        else:
            print("Clearing the previous graph this module built...")
            clear_extracted_graph(driver)
            print("✅ Cleared\n")

        # A new checkpoint still gets the same early schema gate as a clean
        # build. A resumed checkpoint already proves that it contains output
        # from the current build contract, so it proceeds directly to pending
        # sources and does not spend another Bedrock call on a canary.
        if not complete and pending:
            canary = pending[:CANARY_DOCS]
            names = ", ".join(path.name for path in canary)
            print(f"Canary: extracting {names} before ingesting the rest...")
            baseline = snapshot_chunk_ids(driver)
            pipeline = build_pipeline(driver)
            await ingest(pipeline, canary)

            new_chunks = snapshot_chunk_ids(driver) - baseline
            problems = [] if new_chunks else ["Canary produced no :Chunk"]
            if new_chunks:
                problems.extend(check_schema_held(driver, new_chunks))
            problems.extend(check_source_hotels(driver, canary))
            if problems:
                if resume:
                    for path in canary:
                        clear_document(driver, path.name)
                    retained_message = "checkpoint was retained"
                else:
                    clear_extracted_graph(driver)
                    retained_message = "graph was cleared"
                print(f"\n❌ Canary failed; {retained_message}. Fix and re-run:")
                for problem in problems:
                    print(f"  - {problem}")
                return 1
            print("✅ Canary passed: extraction matches the documented schema\n")

            if resume:
                complete.extend(canary)
                pending = pending[len(canary) :]
            else:
                print("Clearing the canary's documents before the full ingest...")
                clear_extracted_graph(driver)
                print("✅ Cleared\n")

        if pending and pipeline is None:
            pipeline = build_pipeline(driver)
        failures = await ingest(pipeline, pending) if pending else []
        # No `await pipeline.close()` here. `SimpleKGPipeline` defines no
        # `close()`, so that call raised `AttributeError` at the end of every
        # otherwise-successful build. It owns no resource needing release; the
        # driver is closed in the `finally` below.

        # The retry runs before the count check below, so a throttled document
        # gets a second attempt instead of costing a fifteen-minute rebuild.
        # The assertion itself is unchanged: every selected source still has to
        # end up with exactly one Document and one Chunk.
        failures = await retry_failures(driver, pipeline, failures)
        if failures:
            print(f"\n{len(failures)} document(s) still failed after the retry pass:")
            for path in failures:
                print(f"  - {path.name}")

        acknowledged = len(paths) - len(failures)
        print(f"\n{'=' * 60}")
        print(f"BUILD COMPLETE ({acknowledged}/{len(paths)} ingests acknowledged)")
        print(f"{'=' * 60}")

        documents = count_documents(driver)
        chunks = count_chunks(driver)
        expected = len(paths)
        print(f"\n:Document nodes: {documents} (expected {expected})")
        print(f":Chunk nodes: {chunks} (expected {expected}, one chunk per document)")
        if documents != expected or chunks != expected:
            print(
                "❌ Document or chunk count does not match the selected source "
                "files. That means a build was incomplete, another build "
                "overlapped this one, or a partial run was left behind."
            )
            return 1

        addressing = check_documents_addressable(driver, paths)
        if addressing:
            print("\n❌ Documents are not addressable by source_filename:")
            for problem in addressing:
                print(f"  - {problem}")
            return 1
        hotel_problems = check_source_hotels(driver, paths)
        if hotel_problems:
            print("\n❌ Every source must resolve to one distinct Hotel:")
            for problem in hotel_problems:
                print(f"  - {problem}")
            return 1
        if failures:
            print(
                "⚠️ One or more client acknowledgements were lost, but every "
                "source has a committed Document and Chunk. Continuing with "
                "graph fixture validation."
            )

        print("\nMaterializing authored amenity lists...")
        try:
            assertion_count = materialize_amenity_lists(driver, parsed_amenities)
        except AmenityMaterializationError as exc:
            print(f"❌ Amenity materialization failed: {exc}")
            return 1
        print(f"✅ Materialized {assertion_count} amenity assertions")
        amenity_problems = check_amenity_assertions(driver, parsed_amenities)
        if amenity_problems:
            print("❌ Amenity assertions do not match their source lists:")
            for problem in amenity_problems:
                print(f"  - {problem}")
            return 1

        print("\nCreating and verifying the workshop indexes...")
        ensure_retrieval_indexes(driver)
        print("✅ Retrieval and lookup indexes are online and match their contracts")

        readiness_problems = report_readiness(driver, expected_documents=expected)
        if readiness_problems:
            print("\n❌ Fixture validation for the later modules failed:")
            for problem in readiness_problems:
                print(f"  - {problem}")
            return 1

        report(driver)
        print("\n✅ Done!")
        return 0
    finally:
        driver.close()


async def run_additive_build(paths: list[Path], title: str) -> int:
    """Extract `paths` into the graph already restored from the dump.

    Module 1's entry point, and the counterpart to `run_build`. The difference
    is the whole point: this never calls `clear_extracted_graph`, so the
    documents the participant restored survive, and so does anything they
    built earlier in the session.

    There is no canary. The canary exists so a schema break surfaces after
    three documents rather than after three hundred; at this size the build is
    its own canary, and `check_schema_held` runs over the chunks this call
    created either way.

    Returns an exit code.
    """
    if not paths:
        print("No documents selected.")
        return 1
    try:
        build_concurrency()
    except ValueError as exc:
        print(f"❌ Extraction concurrency is invalid: {exc}")
        return 1

    try:
        parsed_amenities = parse_amenity_lists(paths)
    except AmenitySectionError as exc:
        print(f"❌ Amenity source validation failed: {exc}")
        return 1

    driver = connect()
    try:
        print(f"{title}: {len(paths)} documents")
        print(f"Database: {graph_database()}\n")

        # Scoped to these files alone, so re-running the notebook cell replaces
        # this extraction instead of writing a second copy of it. Every node
        # here is written with `CREATE` rather than `MERGE`, so without this a
        # second run leaves two :Document and two :Chunk nodes per file.
        for path in paths:
            clear_document(driver, path.name)

        # Counted after the clear, so the expected total below is the same on a
        # first run and on a re-run.
        already_loaded = count_documents(driver)
        print(f"The graph already holds {already_loaded} documents.\n")

        baseline = snapshot_chunk_ids(driver)
        pipeline = build_pipeline(driver)
        failures = await ingest(pipeline, paths)
        failures = await retry_failures(driver, pipeline, failures)
        if failures:
            print(f"\n{len(failures)} document(s) failed after the retry pass:")
            for path in failures:
                print(f"  - {path.name}")
            print(
                "\nRe-run this cell. It clears only these documents before "
                "retrying, so the rest of the graph is untouched."
            )
            return 1

        new_chunks = snapshot_chunk_ids(driver) - baseline
        if not new_chunks:
            print("\n❌ No :Chunk was created. Extraction did not run.")
            return 1

        addressing = check_documents_addressable(driver, paths)
        if addressing:
            print("\n❌ Documents are not addressable by source_filename:")
            for problem in addressing:
                print(f"  - {problem}")
            print(
                "\nRe-running this cell cannot repair that, because the clear "
                "step keys on the same property. See `check_documents_addressable`."
            )
            return 1

        problems = check_schema_held(driver, new_chunks)
        problems.extend(check_source_hotels(driver, paths))
        if problems:
            print("\n❌ Extraction did not match the documented schema:")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print("✅ Extraction matches the documented schema\n")

        print("Materializing authored amenity lists...")
        try:
            assertion_count = materialize_amenity_lists(driver, parsed_amenities)
        except AmenityMaterializationError as exc:
            print(f"❌ Amenity materialization failed: {exc}")
            return 1
        print(f"✅ Materialized {assertion_count} amenity assertions\n")
        amenity_problems = check_amenity_assertions(driver, parsed_amenities)
        if amenity_problems:
            print("❌ Amenity assertions do not match their source lists:")
            for problem in amenity_problems:
                print(f"  - {problem}")
            return 1

        # The dump ships without the workshop indexes, so this is where they
        # first come online. Idempotent regardless, so a re-run is harmless.
        # Module 1 still runs this so the participant watches the indexes come
        # online against the restored graph and the vectors their extraction wrote.
        print("Creating and verifying the workshop indexes...")
        ensure_retrieval_indexes(driver)
        print("✅ Retrieval and lookup indexes are online and match their contracts")

        expected = already_loaded + len(paths)
        readiness_problems = report_readiness(driver, expected_documents=expected)
        if readiness_problems:
            print("\n❌ Fixture validation for the later modules failed:")
            for problem in readiness_problems:
                print(f"  - {problem}")
            return 1

        report(driver)
        print("\n✅ Done!")
        return 0
    finally:
        driver.close()
