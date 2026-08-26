[< Back to the workshop README](../../README.md)

# Module 1: Build the Graph

Five hotel FAQ documents go to Claude on Amazon Bedrock and come back as typed nodes and relationships in Neo4j. `SimpleKGPipeline` from `neo4j-graphrag` reads each document, creates and embeds its `Chunk` node, and extracts the facts that are written as prose. A small deterministic step reads the existing amenity bullet list directly. The module closes by creating the two retrieval indexes every later module queries.

**The mechanism, in one sentence: use the LLM for prose, and parse a structured list directly when the source already provides one.**

**At a Glance**
- **Failure it stops:** a graph where one document produced an `Address` node, the next put the address on a `Location`, and no single Cypher pattern matches both.
- **Neo4j:** writes `Hotel`, `Room`, `Amenity`, `Policy`, `Service`, and `Chunk` nodes; shares amenities by their exact source label; creates the `hotel_chunk_embeddings` vector index and the `hotel_chunk_fulltext` full-text index.
- **AWS:** Claude on Amazon Bedrock extracts the prose; Amazon Nova embeds each `Chunk` node. Amenity identity does not depend on a model response.
- **You'll build:** five hotels that were deliberately held out of the shipped dump. They join the graph permanently and nothing deletes them afterwards.

---

## The notebook

| Notebook | What it proves |
|---|---|
| [`1.0_verify_environment.ipynb`](1.0_verify_environment.ipynb) | The allocated Vocareum account has valid temporary credentials and can invoke Sonnet 4.6 and Nova embeddings in `us-east-1` |
| [`1.1_build_graph.ipynb`](1.1_build_graph.ipynb) | A pinned LLM schema and deterministic amenity parser turn five documents into a source-reconciled graph |

One optional cell extracts a single document with no schema and prints the labels the model invented. It is there for anyone who would rather see the problem than read about it, and skipping it changes nothing downstream.

## Files in this folder

| File | Purpose |
|---|---|
| `1.0_verify_environment.ipynb` | Fast, read-only AWS identity and Bedrock model-access gate |
| `1.1_build_graph.ipynb` | The module notebook |
| `held_out_documents.py` | Names the five documents held out of the dump and unpacks them from the corpus archive. The Cairo fixture hotel is deliberately not among them because Module 2 starts its retrieval comparison there, and that comparison must not depend on a participant's extraction having succeeded |
| `data/` | The five held-out source documents, unpacked |

## What this module hands forward

- **The pinned schema.** Module 2 compares source retrieval with graph-enriched retrieval that returns `name`, `address`, and `guest_rating` from the `Hotel` node. That contract is possible because extraction was constrained when the data was written.
- **The deterministic boundary.** The LLM extracts genuinely unstructured facts. The parser reads the authored `## Hotel Amenities` bullets and merges one shared `Amenity` node for each exact label.
- **Both indexes.** This module builds the vector and full-text indexes for every stored `Chunk`. `workshop/retrieval_setup.py` creates and verifies them. Module 2 compares the retrieved context and selects the graph-enriched pattern. Module 3 uses that pattern.

## The workshop page

`site/content/01-build-graph/index.en.md`
