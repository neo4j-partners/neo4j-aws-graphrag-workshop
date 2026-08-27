---
title: "Module 1: Build the Graph"
weight: 20
---

This module adds five hotel documents to Neo4j. The build stores each document as searchable text and extracts hotel facts into a structured graph.

The two structures answer different parts of a question such as "Which Cairo hotels have a spa that costs extra?" Search finds text with similar meaning. Graph relationships connect the hotel, spa, and fee so one Cypher query can match all three facts.

**What this module builds**

* **Searchable text:** `Document` and `Chunk` nodes store source text and embeddings.
* **Structured facts:** `Hotel`, `Room`, `Amenity`, `Policy`, and `Service` nodes store properties and relationships.
* **Module result:** Five held-out hotels join the prepared graph and remain available to later modules.

---

## Graph Structure

The build creates two connected graph structures.

* **Lexical graph:** Each source file becomes a `Document` node. Its text becomes a `Chunk` node with a 1024-dimension embedding. Vector and full-text indexes search these nodes.
* **Domain graph:** A `Hotel` node stores the name, address, and guest rating. Relationships connect the hotel to its `Room`, `Amenity`, `Policy`, and `Service` nodes, so Cypher can match facts across them.
* **Graph bridge:** `FROM_CHUNK` connects each extracted hotel to its source chunk. `FROM_DOCUMENT` connects that chunk to its source file. A retriever follows these relationships to add hotel properties to a text match.

:image[The lexical graph and the domain graph: the source file becomes a Document and Chunk in the lexical graph, and a Hotel node with typed Room, Amenity, Policy, and Service relationships in the domain graph]{src="../../images/01-graph-structure.svg" width=800}

Every domain relationship starts at `Hotel`, so its facts are one hop away.

* **`Document`:** One source file. Its `source_filename` property identifies the build output for cleanup and provenance.
* **`Chunk`:** One searchable text slice and its embedding. Each hotel document in this module produces one chunk.
* **`Hotel`:** One hotel with `name`, `address`, and `guest_rating` properties.
* **`FROM_CHUNK`:** Connects an extracted entity to the chunk that produced it.
* **`FROM_DOCUMENT`:** Connects a chunk to its source file.

---

## Why the Module Extracts Five Documents

The graph dump from Setup already contains most of the hotel FAQ corpus. Extracting the full corpus takes hours, so this module adds five held-out documents in about four minutes. These documents use the same extraction schema as the prepared data.

You extract the `-002` document for Tokyo, Sydney, Rio de Janeiro, Cape Town, and Prague. These documents keep your build separate from the fixtures used by later modules\:

* **Separate fixtures:** Later modules use other hotels, so rebuilding the five `-002` hotels preserves their fixture data.
* **City coverage:** The dump retains each city's `-001` hotel while the build adds its `-002` hotel.
* **Cairo baseline:** The list excludes Cairo because Module 2 starts with a Cairo hotel already stored in the dump.

Later modules run retrieval against the combined graph, including your five hotels.

---

## How the Extraction Pipeline Works

`SimpleKGPipeline` from :link[neo4j-graphrag]{href="https://neo4j.com/docs/neo4j-graphrag-python/current/" external=true} sends document text to Claude on :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true}. Claude extracts facts that match the schema. `SimpleKGPipeline` also creates and embeds each `Chunk` node. A deterministic parser reads amenity bullets because that section already has a stable structure.

The build sets every stage. `SimpleKGPipeline` runs the first five stages, and the amenity parser runs the last stage.

| Stage | What it does here |
|-------|-------------------|
| Split | `FixedSizeSplitter` cuts the document into text slices of at most 12000 characters |
| Embed | Amazon Nova turns each text slice into a 1024-dimension vector and stores it on the `Chunk` node |
| Extract | Claude reads the `Chunk` text and returns JSON holding the nodes and relationships it found, restricted to the extraction schema |
| Resolve | Global name-based entity resolution stays off so same-name hotels in different cities remain distinct |
| Write | The pipeline creates the `Document`, `Chunk`, and entity nodes, then connects them |
| Amenities | The parser reads the amenity bullets and merges shared `Amenity` nodes by exact name |

Chunk size controls how much text reaches the model in one call. The largest document is 7,442 bytes, which fits within the 12000-character limit, so the hotel's name, rooms, policies, and services stay together in one `Chunk`. The build sets overlap to 0 because each document creates only one chunk.

A complete hotel can produce more JSON than the Bedrock client's 4096-token default. Truncation can cut a JSON object in half and make the document fail, so the build raises the extraction limit to 16000 tokens. It retries one time after a failure.

To identify the output from the current run, the build records the existing `Chunk` element IDs before extraction. It also requires each source document to resolve to exactly one distinct `Hotel` before it attaches amenities.

---

## Why Extraction Uses a Fixed Schema

The extraction schema gives every document one graph vocabulary. Schema-free extraction lets the model choose labels from headings that vary across documents. Test runs produced these differences\:

| Kind of drift | Labels the model chose | Why it breaks queries |
|---------------|------------------------|-----------------------|
| A property promoted to a node | `Address`, `Fee`, `Location` | The address sits on the hotel node in one document and one hop away in the next |
| A type split from its instance | `RoomType`, `BedConfiguration` | A room's own properties become separate nodes to join through |
| Two names for one thing | `ContactMethod`, `ContactInfo` | Both are reasonable, and a query has to know which one a given document used |
| Geography expanded into a hierarchy | `City`, `Country` | The city is text inside the address in most documents and a node in a few |

Each structure describes its source document. The label differences break corpus-wide Cypher queries because each form needs a different pattern. A fixed extraction schema removes that drift.

The LLM schema defines the vocabulary for facts extracted from prose\:

:::code{language=text}
(:Hotel)-[:HAS_ROOM]->(:Room)
(:Hotel)-[:HAS_POLICY]->(:Policy)
(:Hotel)-[:PROVIDES_SERVICE]->(:Service)
:::

`SimpleKGPipeline` receives this structure through its `schema` argument. The argument contains `node_types`, `relationship_types`, and `patterns`. Schema-driven pruning removes other extracted items before the graph write, so the graph contains only the defined labels.

The model also follows the property descriptions in the schema\:

* **`address`:** Stores the address as a `Hotel` property, so every query reads it from the same place.
* **`guest_rating`:** Converts a value such as `4.6/5.0` to the float `4.6`, so later modules can calculate an average.

Later modules require this structure. Module 2 compares source retrieval with graph-enriched retrieval that returns `name`, `address`, and `guest_rating` from each `Hotel` node. The fixed extraction schema writes those properties consistently.

### Deterministic Amenity Parsing

Each source document contains a `## Hotel Amenities` bullet list. An LLM can rewrite one amenity with several valid names, so the build reads this structured section with code.

1. The extraction schema covers prose facts and leaves amenities to the parser.
2. The parser reads bullets under `## Hotel Amenities` and stops at the next heading.
3. The trimmed bullet text becomes `Amenity.name`.
4. Neo4j merges that exact name into one shared node and connects it to the source hotel with `OFFERS_AMENITY`.

### Shared Amenity Nodes Connect Hotels

`Full-Service Spa` is one shared `Amenity` node. Every hotel that offers it connects through `OFFERS_AMENITY`.

:::code{language=cypher}
MATCH (a:Amenity {name: "Full-Service Spa"})
      <-[:OFFERS_AMENITY]-(h:Hotel)
RETURN a.name, collect(h.name) AS hotels
:::

* **One shared entity:** `MERGE` creates one node for the normalized amenity name.
* **Two-way traversal:** Start at a hotel to list amenities, or start at an amenity to find hotels.
* **Connected context:** Continue from each hotel to rooms, policies, services, chunks, and documents.
* **Composable paths:** Module 2 starts from a matching chunk and walks through these relationships to assemble connected context.

The section rule also prevents a sentence such as "Pool facilities are not available at this property" from creating a Pool relationship. The parser reads only the authoritative amenity list.

This division assigns prose extraction to the LLM and preserves authored labels through deterministic parsing. The prebuilt graph and the five documents you add follow the same rule.

The notebook includes an optional schema-free extraction and prints the labels created by the LLM. A temporary source identity isolates that extraction, and cleanup removes only the comparison data after either success or failure. Participant and preloaded documents remain unchanged.

---

## Retrieval Indexes

The graph dump contains the extracted data. This module adds vector and full-text indexes over every `Chunk`, including the five new chunks\:

| Index | What it reads | What it finds |
|-------|---------------|---------------|
| `hotel_chunk_embeddings` | `Chunk.embedding`, cosine similarity over 1024 dimensions | Text that means the same thing as the question in different words |
| `hotel_chunk_fulltext` | `Chunk.text`, full-text | Exact strings that embeddings blur together, such as a postal code or a hotel name |

Each index serves a different query type. Vector search matches meaning, but an embedding of `60611` resembles other five-digit numbers and can rank the correct chunk too low. Full-text search matches the literal value. Module 2 owns the retrieval comparison: it combines both results with hybrid search and then adds hotel properties through a graph traversal.

Matching the document and query embedding settings makes their vectors comparable. A different model, dimension count, or purpose can return incorrect rows while reporting success. The workshop embedder prevents this mismatch with fixed settings.

The build enforces one uniqueness constraint for deterministic identity: `Amenity.name` must be unique. The dump also contains the constraints used by later modules, including the one Module 3 verifies for its duplicate-request check.

---

## What the Build Verifies

The build stops when any of these four checks fails\:

* **Schema check:** Lists every label created from the five chunks and rejects labels outside the extraction schema.
* **Hotel identity check:** Requires each document to produce one `Hotel` and prevents one hotel from linking to several source documents.
* **Amenity check:** Compares exact pairs of source filename and amenity label after the graph write.
* **Retrieval check:** Verifies both indexes and runs the fixture queries used by later modules.

The document, chunk, Hotel, and amenity-source checks require all five documents to load, each document to produce one Hotel, and every authored amenity to connect to that Hotel. The fixture checks allow variation in LLM-extracted properties while requiring at least one Cairo hotel with a spa, a pool, and a rating, plus at least two Paris hotels with a rating.

---

## Run It

Open `notebooks/01-build-graph/1.1_build_graph.ipynb` and run the cells in order. Expect about four minutes for the five documents.

:::alert{type="warning" header="If extraction fails"}
Bedrock can throttle extraction calls, so the build retries them automatically. If a call still fails, rerun the cell. Before each attempt, the build removes data from only these five documents. It preserves all other graph data.
:::

At the end, the notebook confirms the build by comparing document and hotel counts from before and after extraction. It then lists the extracted hotels with their addresses, ratings, and amenity counts and walks the lexical graph and the domain graph for one hotel.

Slides for this module\: [From Documents to a Knowledge Graph](../slides/overview-documents-to-graph/)

## Next

Head to [Module 2](../02-connected-context/).
