---
title: "Module 1: Build the Graph"
weight: 20
---

## Build a Typed Graph from Documents

Ask a hotel search which Cairo hotels have a spa that costs extra, and an embedding alone cannot answer it. An embedding groups text by meaning. It does not record that the hotel sits in Cairo, that it offers a spa, or that the spa costs extra. This module writes those facts down as nodes and relationships, so a query can match them directly instead of inferring them from nearby text.

You add five hotels that the workshop held out of the prepared graph. This module writes the embeddings and the graph facts for them, and every later module reads both.

:::alert{type="info" header="The graph keeps these hotels"}
The five hotels remain in the graph because later modules use them.
:::

---

## Graph Structure

The build writes two connected layers.

**The lexical layer holds the text.** Each source file becomes one `Document` node. The text is split into slices, and each slice becomes a `Chunk` node carrying that text and a 1024-dimension embedding of it. Vector search and keyword search read this layer.

**The domain layer holds the facts stated in that text.** A `Hotel` node carries the name, address, and guest rating as properties. Typed relationships connect it to `Room`, `Amenity`, `Policy`, and `Service` nodes. The LLM extracts the prose facts. The parser reads amenities from the `## Hotel Amenities` list. Cypher queries read this layer.

`FROM_CHUNK` and `FROM_DOCUMENT` connect the two layers. A search finds a chunk. A graph traversal then reaches its typed facts and source document.

:::code{language=text}
hotel-tokyo-002.txt
    |  one source file, about 7 KB of text
    v
(:Document {source_filename: "hotel-tokyo-002.txt"})
    ^
    |  FROM_DOCUMENT                      the lexical layer: the text
(:Chunk {text, embedding: 1024 floats})
    ^
    |  FROM_CHUNK                         the domain layer: the facts
(:Hotel {name, address, guest_rating, total_rooms, email, phone})
    |
    +-[:HAS_ROOM]---------> (:Room)
    +-[:OFFERS_AMENITY]---> (:Amenity)
    +-[:HAS_POLICY]-------> (:Policy)
    +-[:PROVIDES_SERVICE]-> (:Service)
:::

Every domain relationship starts at `Hotel`, so each document produces a one-hop star of facts.

| Term | What it means here |
|------|--------------------|
| `Document` | One source file. It carries `source_filename`, which is how the build finds and clears its own work |
| `Chunk` | A slice of that file's text, plus the embedding of that text. These documents produce one `Chunk` node each |
| `Hotel` | One hotel, with its name, address, and guest rating as properties on the node |
| `FROM_CHUNK` | Joins an extracted entity back to the `Chunk` node it came from |
| `FROM_DOCUMENT` | Joins a `Chunk` node back to its source file |

---

## Why the Module Extracts Five Documents

The source archive contains the workshop hotel FAQ corpus. The graph dump restored during Setup contains the preloaded documents, extracted with the same pinned schema used in this module. Building the full corpus takes hours. You extract five held-out documents in about four minutes.

You extract the `-002` document for Tokyo, Sydney, Rio de Janeiro, Cape Town, and Prague. These documents keep your build separate from the fixtures used by later modules\:

- Later-module fixtures do not depend on these five `-002` hotels, so rebuilding them preserves the required fixture data.
- The dump retains the `-001` hotel for each city, which keeps those cities in the graph during extraction.
- The list excludes Cairo because Module 2 begins its retrieval comparison with a Cairo hotel. That evidence uses data already present in the dump.

Later modules run retrieval against the combined graph, including your five hotels.

---

## How the Extraction Pipeline Works

Claude on :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} extracts the facts stated in prose, and `SimpleKGPipeline` from the :link[neo4j-graphrag]{href="https://neo4j.com/docs/neo4j-graphrag-python/current/" external=true} package runs that extraction. The same pipeline creates and embeds the `Chunk` node for each document. The amenity list is already structured, so a deterministic parser reads those bullets directly and uses each exact label as the shared amenity name.

For each document, `SimpleKGPipeline` runs the first five stages. The deterministic amenity parser then runs. The workshop sets the behavior for every stage.

| Stage | What it does here |
|-------|-------------------|
| Split | `FixedSizeSplitter` cuts the document into text slices of at most 12000 characters |
| Embed | Amazon Nova turns each text slice into a 1024-dimension vector and stores it on the `Chunk` node |
| Extract | Claude reads the `Chunk` text and returns JSON holding the nodes and relationships it found, restricted to the pinned schema |
| Resolve | Global name-based entity resolution stays off so same-name hotels in different cities remain distinct |
| Write | The pipeline creates the `Document`, `Chunk`, and entity nodes, then connects them |
| Amenities | The parser reads the amenity bullets and merges shared `Amenity` nodes by exact name |

Chunk size controls how much text the model sees in one call. The largest corpus document is 7,442 bytes, and the chunk size is 12000 characters, so each document becomes one `Chunk` node. The hotel's name, address, rating, rooms, policies, and services reach the model together. The overlap is 0 because each document has only one `Chunk` node.

Extracting one complete hotel produces a large JSON response that can exceed the 4096-token default that the workshop's Bedrock client sets. The model can truncate the response in the middle of an object, which makes the JSON invalid and fails that document. The build raises the extraction limit to 16000 tokens so the complete response fits, and a failed document receives one retry.

The build records the existing `Chunk` element IDs before extraction, so every new `Chunk` belongs to the current run. It also requires each source document to resolve to exactly one distinct `Hotel` before attaching amenities.

---

## Why the Schema Is Pinned

`SimpleKGPipeline` can extract data without a schema. In that mode, the model chooses labels for each `Chunk` based on headings that vary across documents. Test runs produced these label differences\:

| Kind of drift | Labels the model chose | Why it breaks queries |
|---------------|------------------------|-----------------------|
| A property promoted to a node | `Address`, `Fee`, `Location` | The address sits on the hotel node in one document and one hop away in the next |
| A type split from its instance | `RoomType`, `BedConfiguration` | A room's own properties become separate nodes to join through |
| Two names for one thing | `ContactMethod`, `ContactInfo` | Both are reasonable, and a query has to know which one a given document used |
| Geography expanded into a hierarchy | `City`, `Country` | The city is text inside the address in most documents and a node in a few |

Each structure represents its source document, but a single Cypher pattern cannot match all of them. The extraction process needs one vocabulary that applies to every document.

The LLM schema provides the vocabulary for facts extracted from prose\:

:::code{language=text}
(:Hotel)-[:HAS_ROOM]->(:Room)
(:Hotel)-[:HAS_POLICY]->(:Policy)
(:Hotel)-[:PROVIDES_SERVICE]->(:Service)
:::

The schema restricts extraction to the listed node types, relationship types, and patterns. The model drops facts that do not fit instead of creating new labels.

The model also follows the property descriptions in the schema\:

- `address` stores the address as a `Hotel` property and keeps `Address` out of the graph.
- `guest_rating` converts a value such as `4.6/5.0` into the float `4.6`. Later modules can average the numeric property.
Later modules require this structure. Module 2 compares source retrieval with graph-enriched retrieval that returns `name`, `address`, and `guest_rating` from each `Hotel` node. The pinned schema writes those properties consistently.

### The deterministic amenity boundary

Each source document already contains one `## Hotel Amenities` bullet list. Asking an LLM to recreate those labels can turn the same authored value into several plausible names. The workshop takes the simpler path\:

1. The LLM schema excludes `Amenity` and `OFFERS_AMENITY`.
2. Code reads only the bullets under `## Hotel Amenities` and stops at the next heading.
3. The exact trimmed bullet text becomes `Amenity.name`.
4. Neo4j merges that name into one shared node and connects it to the source hotel.

This boundary also handles negative prose safely. A later sentence such as "Pool facilities are not available at this property" sits outside the authoritative list and cannot create a positive Pool amenity.

Use the LLM for prose, and parse a structured list directly when the source already provides one. The prebuilt graph and the five documents you add use this same rule.

The notebook includes an optional comparison. It extracts one document without a schema and prints the labels created by the LLM. The comparison uses a temporary source identity and removes only that data after either success or failure. Participant and preloaded documents remain unchanged.

---

## Retrieval Indexes

The graph dump contains the extracted data but excludes the vector and full-text indexes. This module creates both indexes over every `Chunk` in the graph, including the `Chunk` nodes your extraction just wrote\:

| Index | What it reads | What it finds |
|-------|---------------|---------------|
| `hotel_chunk_embeddings` | `Chunk.embedding`, cosine similarity over 1024 dimensions | Text that means the same thing as the question in different words |
| `hotel_chunk_fulltext` | `Chunk.text`, full-text | Exact strings that embeddings blur together, such as a postal code or a hotel name |

Each index handles a different search pattern. An embedding of `60611` is similar to embeddings for other five-digit numbers, so vector search can rank the correct `Chunk` below other results. Keyword search matches `60611` exactly. Vector search handles the opposite case by matching a question to relevant text that uses different words. Module 2 compares these signals, combines them through hybrid retrieval, and selects the fixed graph-enriched pattern that Module 3 applies.

The document and query embeddings must use the same model, dimensions, and purpose. A query embedding with different settings can return incorrect rows without producing an error. The workshop embedder prevents this mismatch by using fixed settings.

The build enforces one uniqueness constraint for deterministic identity: `Amenity.name` must be unique. The dump also contains the constraints used by later modules, including the one Module 3 verifies for its duplicate-request check.

---

## What the Build Verifies

The build runs four checks and stops when any check fails\:

1. **The schema held.** The build lists every label this run's own chunks produced and fails if an off-schema label appears.
2. **Every source produced one hotel.** A document with zero or multiple Hotels fails, as does one Hotel shared by multiple source documents.
3. **Amenities match the source.** The build compares exact pairs of source filename and amenity label after writing the graph.
4. **The graph is ready for retrieval.** The build verifies both indexes and runs the fixture queries used by later modules.

The document, chunk, Hotel, and amenity-source checks are strict. All five documents must load, each must produce one Hotel, and every authored amenity must be connected to that Hotel. The fixture checks allow variation in LLM-extracted properties. They require at least one Cairo hotel with a spa, a pool, and a rating, and at least two Paris hotels with a rating.

---

## Run It

Open `notebooks/01-build-graph/1.1_build_graph.ipynb` and run the cells in order. Expect about four minutes for the five documents.

:::alert{type="warning" header="If extraction fails"}
Bedrock can throttle extraction calls, so the build retries them automatically. If a call still fails, rerun the cell. Before each attempt, the build removes data from only these five documents. It preserves all other graph data.
:::

At the end, the notebook compares the document and hotel counts from before and after the build. It also lists the hotels you extracted with their addresses, ratings, and amenity counts, and it walks both layers of the graph for one of them.

---

## Learn the Agent Basics for Module 3

The final notebook section introduces the :link[Strands Agents SDK]{href="https://strandsagents.com/" external=true}. It explains how an `Agent` works, why `BedrockModel` uses an explicit model ID, and how the `@tool` decorator exposes a Python function to the model. Module 2 first compares retrieved evidence and selects a fixed retrieval function. Module 3 gives that function to the agent.

Accurate tool results support grounded answers. The application must also recognize when those results do not support the request. A fixed model ID holds the runtime configuration steady, but model wording can still vary.

## Next

Head to [Module 2](../02-connected-context/).
