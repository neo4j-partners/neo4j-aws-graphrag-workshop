---
title: "Module 2: From Similarity Search to Connected Context"
weight: 30
---

## Compare Retrieval Evidence

Vector search returns the passage that reads closest to a question. That is enough
when the answer sits inside that passage. Ask which Chicago hotels offer both a spa
and a swimming pool, and the answer depends on facts held in two separate documents.

Use semantic search to find a relevant source, then use graph structure to return
connected facts as named fields. This module compares retrieval evidence before
any optional answer generation.

Open `notebooks/02-connected-context/2.1_connected_context.ipynb`.

:::alert{type="info" header="Use One Neo4j Connection"}
Every module uses the same Neo4j credentials. Configure one connection.
The optional Text2Cypher example first plans generated Cypher with `EXPLAIN` and
runs it only when Neo4j classifies it as read-only. In production, use a
read-only Neo4j user so the database independently rejects writes.
:::

## Prepare the Graph

The notebook verifies its graph fixtures and both retrieval indexes before it
constructs a retriever. Module 1 already prepared the graph. Run the
Module 2.1 notebook cells in order. Its **Verify the prepared graph** cell runs
the non-destructive readiness check directly from Python, so no terminal command
is required.

If the readiness cell reports that Module 2.1 is not ready, return to the Module
1 notebook, run its cells through completion, and then rerun Module 2.1 from the
top. The Module 2.1 notebook only reads the graph and never clears learner work.

## Semantic and Exact-Term Retrieval

Vector retrieval finds source text with similar meaning. Hybrid retrieval adds a
full-text signal for exact identifiers such as `60611`. Compare the ranked
evidence, source text, and scores returned by each pattern.

## Connected Graph Context

Vector-Cypher retrieval starts from a semantic Chunk match and follows reviewed
relationships to return the connected hotel and its named fields. Compare field
coverage, provenance, and context size with the source-only result.

:::alert{type="info" header="Extraction defines the graph result"}
Graph enrichment contains the facts that the extraction pipeline placed in the
graph. It is not an independent source of truth. Source provenance remains visible so
you can compare omissions or merges with the authored document.
:::

## Structured Filtering

Structured retrieval lets Neo4j apply filters over connected fields and
relationships. The notebook displays the query and returned records so the
selection mechanism remains visible.

## Select the Application Retriever

:image[Decision tree for selecting a Neo4j retrieval pattern by query shape]{src="../../images/02-retrieval-decision-tree.png" width=800}

| Retriever | Best for | Contribution |
|-----------|----------|--------------|
| `VectorRetriever` | Paraphrased questions | Semantic relevance |
| `HybridRetriever` | Names, identifiers, and postal codes | Semantic and exact-term relevance |
| `VectorCypherRetriever` | Semantic lookup with connected context | Semantic entry plus graph expansion |
| Reviewed fixed Cypher | Known structured questions | Application-owned database filtering over named fields and relationships |
| `Text2CypherRetriever` (optional) | Flexible structured questions | Model-generated read-only database queries |

The booking application needs exact hotel-name support and connected named
fields in the same evidence record. Module 2 therefore selects the fixed
`HybridCypherRetriever` exposed by `search_hotel_knowledge`. Module 3 applies that function for grounding, abstention, and the protected write.

## Next

Head to [Module 3](../03-grounded-booking-agent/).
