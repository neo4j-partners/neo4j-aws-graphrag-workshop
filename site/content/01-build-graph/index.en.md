---
title: "Module 1: Build the Graph"
weight: 20
---

## Build a Typed Graph from Documents

A question such as "Which Cairo hotels have a spa that costs extra?" depends on three separate facts: the hotel's location, its spa amenity, and the spa fee. An embedding groups text by meaning, while a typed graph stores those facts as properties and relationships that a query can match directly. In this module, you build both representations so later retrieval can combine semantic similarity with graph structure.

You will add five hotels that the workshop held out of the prepared graph. The
build writes their embeddings and graph facts to Neo4j, creating the combined
representation used for retrieval in every later module.

:::alert{type="info" header="The graph keeps these hotels"}
The build keeps these five hotels in the graph so later modules can retrieve them.
:::

---

## Graph Structure

The build creates a lexical graph and a domain graph, each designed for a different retrieval operation.

**The lexical graph supports text search.** Each source file becomes one `Document` node. The pipeline divides the text into slices and stores each slice in a `Chunk` node with a 1024-dimension embedding. Vector and keyword searches read these nodes.

**The domain graph supports structured graph queries.** A `Hotel` node stores the name, address, and guest rating as properties. Typed relationships connect each hotel to its `Room`, `Amenity`, `Policy`, and `Service` nodes. The LLM extracts facts from prose, and a deterministic parser reads amenities from the `## Hotel Amenities` list. Cypher queries use this structure to match properties and relationships.

The `FROM_CHUNK` and `FROM_DOCUMENT` relationships connect the two graphs. After a search finds a chunk, a graph traversal can return the connected hotel, its properties, and its source document, which is what makes the search graph-enriched.

:image[The lexical graph and the domain graph: the source file becomes a Document and Chunk in the lexical graph, and a Hotel node with typed Room, Amenity, Policy, and Service relationships in the domain graph]{src="../../images/01-graph-structure.svg" width=800}

Every domain relationship starts at `Hotel`, which gives each document a one-hop star of facts.

| Term | What it means here |
|------|--------------------|
| `Document` | One source file. It carries `source_filename`, which is how the build finds and clears its own work |
| `Chunk` | A slice of that file's text, plus the embedding of that text. These documents produce one `Chunk` node each |
| `Hotel` | One hotel, with its name, address, and guest rating as properties on the node |
| `FROM_CHUNK` | Joins an extracted entity back to the `Chunk` node it came from |
| `FROM_DOCUMENT` | Joins a `Chunk` node back to its source file |

---

## Why the Module Extracts Five Documents

The source archive contains the workshop hotel FAQ corpus, and the graph dump restored during Setup contains most of those documents. The preloaded documents use the same extraction schema as this module. Because extracting the full corpus takes hours, you will extract five held-out documents in about four minutes.

You extract the `-002` document for Tokyo, Sydney, Rio de Janeiro, Cape Town, and Prague. These documents keep your build separate from the fixtures used by later modules\:

- Later-module fixtures use other hotels, so rebuilding these five `-002` hotels preserves the required fixture data.
- The dump retains the `-001` hotel for each city, which keeps those cities in the graph during extraction.
- The list excludes Cairo because Module 2 begins its retrieval comparison with a Cairo hotel whose data is already present in the dump.

Later modules run retrieval against the combined graph, including your five hotels.

---

## How the Extraction Pipeline Works

`SimpleKGPipeline` from the :link[neo4j-graphrag]{href="https://neo4j.com/docs/neo4j-graphrag-python/current/" external=true} sends document prose to Claude on :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} for fact extraction. The pipeline also creates and embeds the `Chunk` node for each document. Because the amenity list already has a reliable structure, a deterministic parser reads its bullets and uses each exact label as the shared amenity name.

For each document, `SimpleKGPipeline` runs the first five stages in the following table. The deterministic amenity parser completes the final stage. The workshop configures each stage explicitly.

| Stage | What it does here |
|-------|-------------------|
| Split | `FixedSizeSplitter` cuts the document into text slices of at most 12000 characters |
| Embed | Amazon Nova turns each text slice into a 1024-dimension vector and stores it on the `Chunk` node |
| Extract | Claude reads the `Chunk` text and returns JSON holding the nodes and relationships it found, restricted to the extraction schema |
| Resolve | Global name-based entity resolution stays off so same-name hotels in different cities remain distinct |
| Write | The pipeline creates the `Document`, `Chunk`, and entity nodes, then connects them |
| Amenities | The parser reads the amenity bullets and merges shared `Amenity` nodes by exact name |

Chunk size controls how much text the model receives in one call. The largest corpus document is 7,442 bytes, which fits within the configured chunk size of 12000 characters. Each document therefore becomes one `Chunk` node, and the hotel's name, address, rating, rooms, policies, and services reach the model together. A single chunk requires no overlap, so the build sets the overlap to 0.

Extracting one complete hotel can produce a JSON response larger than the workshop Bedrock client's 4096-token default. If the model truncates the response inside an object, the resulting JSON is invalid and the document fails. The build raises the extraction limit to 16000 tokens so the complete response can fit, then retries a failed document once.

To identify the output from the current run, the build records the existing `Chunk` element IDs before extraction. It also requires each source document to resolve to exactly one distinct `Hotel` before it attaches amenities.

---

## Why Extraction Uses a Fixed Schema

Without a schema, `SimpleKGPipeline` lets the model choose labels for each `Chunk` from headings that vary across documents. Test runs produced these label differences\:

| Kind of drift | Labels the model chose | Why it breaks queries |
|---------------|------------------------|-----------------------|
| A property promoted to a node | `Address`, `Fee`, `Location` | The address sits on the hotel node in one document and one hop away in the next |
| A type split from its instance | `RoomType`, `BedConfiguration` | A room's own properties become separate nodes to join through |
| Two names for one thing | `ContactMethod`, `ContactInfo` | Both are reasonable, and a query has to know which one a given document used |
| Geography expanded into a hierarchy | `City`, `Country` | The city is text inside the address in most documents and a node in a few |

Each structure can represent its source document, yet the variation prevents one Cypher pattern from matching the entire corpus. A fixed extraction schema gives the extraction process one vocabulary for every document.

The LLM schema provides the vocabulary for facts extracted from prose\:

:::code{language=text}
(:Hotel)-[:HAS_ROOM]->(:Room)
(:Hotel)-[:HAS_POLICY]->(:Policy)
(:Hotel)-[:PROVIDES_SERVICE]->(:Service)
:::

`SimpleKGPipeline` receives this structure through its `schema` argument, which carries `node_types`, `relationship_types`, and `patterns`. The pipeline prunes anything outside that structure before it writes, which prevents the model from creating new labels.

The model also follows the property descriptions in the schema\:

- `address` stores the address only as a `Hotel` property, which prevents the extraction from creating an `Address` node.
- `guest_rating` converts a value such as `4.6/5.0` into the float `4.6`. Later modules can average the numeric property.

Later modules require this structure. Module 2 compares source retrieval with graph-enriched retrieval that returns `name`, `address`, and `guest_rating` from each `Hotel` node. The fixed extraction schema writes those properties consistently.

### The deterministic amenity boundary

Each source document already contains one `## Hotel Amenities` bullet list. An LLM could recreate the same authored value with several plausible names, so the workshop reads this structured section directly\:

1. The LLM schema excludes `Amenity` and `OFFERS_AMENITY`.
2. Code reads only the bullets under `## Hotel Amenities` and stops at the next heading.
3. The exact trimmed bullet text becomes `Amenity.name`.
4. Neo4j merges that name into one shared node and connects it to the source hotel.

This boundary also prevents negative prose from creating a positive relationship. A later sentence such as "Pool facilities are not available at this property" sits outside the authoritative list, so it cannot create a Pool amenity.

This division assigns prose extraction to the LLM and preserves authored labels through deterministic parsing. The prebuilt graph and the five documents you add follow the same rule.

The notebook includes an optional comparison that extracts one document without a schema and prints the labels created by the LLM. A temporary source identity isolates that extraction, and cleanup removes only the comparison data after either success or failure. Participant and preloaded documents remain unchanged.

---

## Retrieval Indexes

The graph dump contains the extracted data and leaves index creation to this module. You will create vector and full-text indexes over every `Chunk` in the graph, including the nodes from your extraction\:

| Index | What it reads | What it finds |
|-------|---------------|---------------|
| `hotel_chunk_embeddings` | `Chunk.embedding`, cosine similarity over 1024 dimensions | Text that means the same thing as the question in different words |
| `hotel_chunk_fulltext` | `Chunk.text`, full-text | Exact strings that embeddings blur together, such as a postal code or a hotel name |

Each index handles a different search pattern. An embedding of `60611` resembles embeddings for other five-digit numbers, so vector search can rank the correct `Chunk` below other results. Keyword search matches `60611` exactly, while vector search matches a question to relevant text that uses different words. Module 2 compares these signals, combines them through hybrid retrieval, and selects the fixed graph-enriched pattern that Module 3 applies.

Matching the document and query embedding settings ensures that their vectors are comparable. A query embedding created with a different model, dimension count, or purpose can return incorrect rows without producing an error. The workshop embedder prevents this mismatch with fixed settings.

The build enforces one uniqueness constraint for deterministic identity: `Amenity.name` must be unique. The dump also contains the constraints used by later modules, including the one Module 3 verifies for its duplicate-request check.

---

## What the Build Verifies

The build runs four checks and stops when any check fails\:

1. **The schema held.** The build lists every label this run's own chunks produced and fails if an off-schema label appears.
2. **Every source produced one hotel.** A document with zero or multiple Hotels fails, as does one Hotel shared by multiple source documents.
3. **Amenities match the source.** The build compares exact pairs of source filename and amenity label after writing the graph.
4. **The graph is ready for retrieval.** The build verifies both indexes and runs the fixture queries used by later modules.

The document, chunk, Hotel, and amenity-source checks require all five documents to load, each document to produce one Hotel, and every authored amenity to connect to that Hotel. The fixture checks allow variation in LLM-extracted properties while requiring at least one Cairo hotel with a spa, a pool, and a rating, plus at least two Paris hotels with a rating.

---

## Run It

Open `notebooks/01-build-graph/1.1_build_graph.ipynb` and run the cells in order. Expect about four minutes for the five documents.

:::alert{type="warning" header="If extraction fails"}
Bedrock can throttle extraction calls, so the build retries them automatically. If a call still fails, rerun the cell. Before each attempt, the build removes data from only these five documents. It preserves all other graph data.
:::

At the end, the notebook confirms the build by comparing document and hotel counts from before and after extraction. It then lists the extracted hotels with their addresses, ratings, and amenity counts and walks the lexical graph and the domain graph for one hotel.

## Next

Head to [Module 2](../02-connected-context/).
