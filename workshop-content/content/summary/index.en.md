---
title: "Summary"
weight: 80
---

## The Retrieval Spectrum

Semantic search is strong when the question and source use different words. Exact-term search protects identifiers and names. Graph traversal extends a match with connected fields and relationships. Structured queries filter or aggregate records in the database.

GraphRAG combines these signals instead of treating one as universally best. The graph is only as reliable as its extraction and provenance, so Module 1 pins both before later modules compare retrieval evidence.

---

## What Each Module Proved

| Module | The claim | How you saw it |
|---|---|---|
| **1. Build the Graph** | Extraction is only queryable if the schema was pinned when the data was written | You extracted five held-out documents under the same pinned schema as the rest of the corpus, then created both retrieval indexes against your own vectors |
| **2. From Similarity Search to Connected Context** | Different question shapes need different retrieval signals | You compared semantic, exact-term, graph-enriched, and structured evidence before generating an answer |
| **3. Build the Grounded Booking Agent** | A fixed retrieval contract gives the agent a stable evidence boundary | You applied the selected retriever, declined unsupported requests, and protected a reservation write inside one transaction |
| **4. Production Agent** | Tools move out of the notebook without changing their agent interface | Retrieval behind an :link[AgentCore]{href="https://aws.amazon.com/bedrock/agentcore/" external=true} Gateway over IAM-authenticated MCP, then passed to a Strands agent |
| **5. Deploy to AgentCore Runtime** | A deployment-oriented agent runs as a service | The agent containerized, launched on Runtime, and one request correlated end to end |
| **6. Inspectable Neo4j Memory** | Cross-session memory should be actor-scoped, auditable, and correctable | The same actor recalled a preference in a new session, then traced it back to its source message and forward to the real `Hotel` node |

---

## The Evidence

| Question shape | Retrieval pattern | Evidence returned |
|---|---|---|
| Paraphrased description | Vector | Relevant source `Chunk` nodes with score and provenance |
| Exact postal code or hotel name | Hybrid | Semantic matches plus exact-term matches |
| Semantic match that needs hotel fields | VectorCypher | Matched source plus connected names, ratings, amenities, and provenance |
| Flexible structured filter | Text2Cypher | Database records selected by a generated read-only query |

This comparison is about evidence quality and fit. Answer generation comes later, after the application has selected what context the model may use.

---

## Choosing a Retriever

| Question shape | Retriever | Why |
|---|---|---|
| Paraphrased, semantic | `VectorRetriever` | Nothing exact to match on |
| Exact name, identifier, postal code | `HybridRetriever` | Embeddings blur short exact strings; the full-text arm holds them |
| Semantic entry, connected answer | `VectorCypherRetriever` | Reviewed traversal turns matched text into named fields |
| Flexible structured filtering or aggregation | `Text2CypherRetriever` | The database evaluates a read-only query over matching records |

`HybridCypherRetriever` is the one the workshop ships to production, behind `search_hotel_knowledge` in `notebooks/workshop/hybrid_retrieval.py`. It takes a single `query` argument. There is no ranker, alpha, or top-k parameter for a caller to set, because those comparisons were made once, by you, and a request does not get to re-run them.

:::alert{type="warning" header="Model-generated Cypher"}
`Text2CypherRetriever` executes Cypher a model wrote. The workshop uses its one
shared Neo4j credential and runs a planner check before execution. In production,
use a read-only Neo4j user so the database independently rejects writes, and
grant the surrounding application only the IAM permissions it needs.
:::

---

## Choosing a Memory Store

Module 6 implements the Neo4j path. AgentCore Memory remains a conceptual
managed alternative for teams that prefer automatic extraction and AWS-run
operations.

| | AgentCore Memory | Neo4j graph memory |
|---|---|---|
| How it is written | Managed extraction from the transcript | Explicit application writes |
| When it is recallable | After asynchronous extraction | Immediately |
| Auditability | Retrieved through a service API | A Cypher query returning the source message |
| Correction path | Managed through the Memory service API | `SET` on one property |
| Link to domain data | Separate from it | An edge to the real `Hotel` node |
| Operations | AWS runs it | You run it |

The stores serve different needs. Managed extraction is the shorter path to a working prototype. Graph memory is useful for facts that need explicit provenance and direct correction. A production system can use managed memory for recency and graph memory for records that must be explainable.

---

## What to Take With You

Three pieces of this repository port to another domain without being rewritten\:

- **The pinned extraction schema** in `notebooks/01-build-graph/1.1_build_graph.ipynb`. Swap the node labels and relationship types for your own entities; the argument for pinning them does not change.
- **The retrieval contract** in `notebooks/workshop/retrieval_contract.py` and `workshop/hybrid_retrieval.py`. One function, one argument, a fixed return shape. That shape is what makes the tool safe to hand to a model.
- **The grounded write** in `notebooks/03-grounded-booking-agent/reservation_command.py`. Rule check and write in the same transaction, keyed on a `request_id` so a replay is a no-op rather than a second booking.

## Next

Head to [Wrap-up](../wrap-up/).
