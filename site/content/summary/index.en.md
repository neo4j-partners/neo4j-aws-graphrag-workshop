---
title: "Summary"
weight: 80
---

Semantic search is strong when the question and source use different words. Exact-term search protects identifiers and names. Graph traversal extends a match with connected entities and their properties. Structured queries filter or aggregate records in the database.

GraphRAG combines these signals to match the retrieval method to each query need. Reliable results require reliable extraction and provenance, so Module 1 fixes both before later modules compare retrieval results.

---

## What Each Module Proved

| Module | The claim | How you saw it |
|---|---|---|
| **1. Build the Graph** | A fixed schema makes extracted data queryable | You extracted five held-out documents under the same extraction schema as the rest of the corpus, then created both retrieval indexes against your own vectors |
| **2. From Similarity Search to Graph-Enriched Retrieval** | Different query needs require different retrieval signals | You compared semantic, exact-term, graph-enriched, and structured retrieval results before generating an answer |
| **3. Build the Grounded Booking Agent** | A fixed retriever gives the agent a predictable result shape | You applied the selected retriever, declined unsupported requests, and protected a reservation write inside one transaction |
| **4. Production Agent** | Tools keep the same agent interface when they move out of the notebook | You put retrieval behind an :link[AgentCore]{href="https://aws.amazon.com/bedrock/agentcore/" external=true} Gateway over IAM-authenticated MCP, then passed the remote tools to a Strands agent |
| **5. Deploy to AgentCore Runtime** | A deployment-oriented agent runs as a service | You containerized the agent, launched it on Runtime, and correlated one request end to end |
| **6. Neo4j Graph Memory** | Cross-session memory should be actor-scoped, auditable, and correctable | The same actor recalled a preference in a new session, then traced it back to its source message and forward to the real `Hotel` node |

Together, the modules keep retrieval, answer generation, commands, deployment,
and memory as separate components with clear responsibilities.

---

## What Each Retriever Returns

| Query need | Retrieval strategy | What it returns |
|---|---|---|
| Paraphrased description | Vector | Relevant source `Chunk` nodes with score and provenance |
| Exact postal code or hotel name | Hybrid | Semantic matches plus exact-term matches |
| Semantic match that needs hotel fields | VectorCypher | Matched source plus connected names, ratings, amenities, and provenance |
| Flexible structured filter | Text2Cypher | Database records selected by a generated read-only query |

This comparison is about retrieval quality and fit. Answer generation comes later, after the application has selected what context the model may use.

---

## Choosing a Retriever

| Query need | Retriever | Why |
|---|---|---|
| Paraphrased, semantic | `VectorRetriever` | Semantic similarity is the main signal |
| Exact name, identifier, postal code | `HybridRetriever` | Embeddings blur short exact strings; the full-text arm holds them |
| Semantic entry, connected answer | `VectorCypherRetriever` | The retrieval query turns matched text into connected entities and their properties |
| Flexible structured filtering or aggregation | `Text2CypherRetriever` | The database evaluates a read-only query over matching records |

The workshop ships `HybridCypherRetriever` behind `search_hotel_knowledge` in `notebooks/workshop/hybrid_retrieval.py`. The function takes one `query` argument. Its fixed configuration owns the ranker, alpha, and result limit, so every caller uses the retrieval settings you selected in Module 2.

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

Three pieces of this repository can be adapted to another domain\:

- **Fixed extraction schema:** Adapt the node labels and relationship types in `notebooks/01-build-graph/1.1_build_graph.ipynb` to your domain.
- **Retriever:** Keep the one-argument function and fixed return shape from `notebooks/workshop/retrieval_contract.py` and `notebooks/workshop/hybrid_retrieval.py`. The fixed shape gives the model a predictable tool result.
- **Grounded write:** Reuse the transaction pattern in `notebooks/03-grounded-booking-agent/reservation_command.py`. The command checks the rule and writes in the same transaction. A `request_id` makes a replay return the existing result and prevents a second booking.

## Next

Head to [Production Path](../production-path/) to turn the workshop components
into an operated system.
