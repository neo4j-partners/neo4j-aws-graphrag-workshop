[< Back to the workshop README](../../README.md)

# Module 2: From Similarity Search to Connected Context

Use semantic search to find the right source, then traverse the graph to return
compact, connected facts with provenance. The notebook compares retrieval
evidence directly, so its lessons do not depend on one generated answer.

**At a Glance**

- **What it demonstrates:** semantic retrieval, exact-term retrieval,
  graph-enriched retrieval, and structured filtering.
- **Neo4j:** reads the `hotel_chunk_embeddings` and `hotel_chunk_fulltext`
  indexes plus connected hotel entities.
- **AWS:** Amazon Nova creates query embeddings. Amazon Bedrock supports the
  optional Text2Cypher example.
- **Graph changes:** the notebook reads the prepared graph and does not change
  it.

The workshop uses the same Neo4j credentials in every module so participants
configure one connection. Optional Text2Cypher plans its generated statement
with `EXPLAIN` and runs it only when Neo4j classifies it as read-only. In
production, use a read-only Neo4j user so the database enforces that boundary
independently.

---

## The notebook

| Notebook | What it demonstrates |
|---|---|
| [`2.1_connected_context.ipynb`](2.1_connected_context.ipynb) | Compares vector, hybrid, Vector-Cypher, and structured retrieval evidence |

Module 1 already prepared the graph. Run the notebook cells in order. The
**Verify the prepared graph** cell performs the non-destructive readiness check
directly from Python, so no terminal command is required.

If the readiness cell reports that Module 2.1 is not ready, return to the Module
1 notebook, run its cells through completion, and then rerun Module 2.1 from the
top. The Module 2.1 notebook only reads the graph and never clears learner work.
For the setup that gets you to a prepared graph, see the
[repository README](../../README.md).

## Evidence and application boundaries

Graph-enriched results reflect the facts that extraction placed in Neo4j. They
are not an independent source of truth. The notebook keeps the source
`Document`, matched `Chunk`, and relationship provenance visible so you can
inspect an omission or merge against the authored source.

The comparison closes by selecting the fixed `HybridCypherRetriever` behind
`workshop.hybrid_retrieval.search_hotel_knowledge`. The application question
needs exact hotel-name support plus connected graph fields. Module 3 applies
that selected function and focuses on grounding, abstention, and the protected
reservation command.

## Files in this folder

| File | Purpose |
|---|---|
| `2.1_connected_context.ipynb` | The module notebook |
| `hotel-faqs.zip` | The source corpus stored with the workshop |
| `graph_builder.py` | The extraction pipeline shared with Module 1 |
| `graph_config.py` | Chunking and deterministic corpus selection |
| `prepare_graph.py` | Prepares the graph for this module when you run the workshop outside the hosted environment |

## The workshop page

`workshop-content/content/02-connected-context/index.en.md`
