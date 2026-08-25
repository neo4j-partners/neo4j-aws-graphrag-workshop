---
title: "Module 2: From Similarity Search to Connected Context"
weight: 30
---

## Compare Retrieval Context

Use this module to compare the context produced by several retrieval patterns before
you add optional answer generation. Vector search can answer a question when one
semantically similar passage contains the required facts. A question such as "Which
Chicago hotels offer both a spa and a swimming pool?" requires facts distributed
across two documents, so similarity alone cannot assemble the complete answer.

The notebook first uses semantic search to find a relevant source. It then traverses
the graph to return connected facts as named fields, which makes the additional
context and its provenance visible for comparison.

Open `notebooks/02-connected-context/2.1_connected_context.ipynb`.

:::alert{type="info" header="Use One Neo4j Connection"}
Configure one Neo4j connection because every module uses the same credentials.
The optional Text2Cypher example plans generated Cypher with `EXPLAIN` and runs the
query only when Neo4j classifies it as read-only. In production, a read-only Neo4j
user provides a second control by making the database reject writes.
:::

## Prepare the Graph

Run the Module 2.1 notebook cells in order. Before constructing a retriever, the
**Verify the prepared graph** cell confirms that Module 1 created the required graph
fixtures and both retrieval indexes. The cell runs this read-only check directly
from Python, so you do not need a terminal command.

If the readiness cell reports that Module 2.1 is not ready, return to the Module 1
notebook and run its cells through completion. Then rerun Module 2.1 from the top.
Module 2.1 preserves learner work because every operation in the notebook reads the
graph without clearing it.

## Semantic and Exact-Term Retrieval

Vector retrieval ranks source text by semantic similarity. Hybrid retrieval combines
that vector score with a full-text signal, which improves matching for exact
identifiers such as `60611`. Compare the ranked context, source text, and scores to
see how the additional signal changes the results.

## Connected Graph Context

Vector-Cypher retrieval starts with a semantic `Chunk` match and follows reviewed
relationships to the connected hotel and its named fields. Compare this graph
context with the source-only result to see the change in field coverage, provenance,
and context size.

:::alert{type="info" header="Extraction defines the graph result"}
Graph enrichment contains only the facts that the extraction pipeline placed in the
graph, so it is not an independent source of truth. The result keeps source
provenance visible so you can compare extracted omissions or merges with the authored
document.
:::

## Structured Filtering

Structured retrieval asks Neo4j to filter connected fields and relationships. The
notebook displays both the query and its returned records, which lets you inspect the
selection mechanism directly.

## Select the Application Retriever

:image[Decision tree for selecting a Neo4j retrieval pattern by question shape: VectorRetriever, HybridRetriever, VectorCypherRetriever, or reviewed fixed Cypher, with Text2CypherRetriever as an optional extension]{src="../../images/02-select-retriever.svg" width=800}

| Retriever | Best for | Contribution |
|-----------|----------|--------------|
| `VectorRetriever` | Paraphrased questions | Semantic relevance |
| `HybridRetriever` | Names, identifiers, and postal codes | Semantic and exact-term relevance |
| `VectorCypherRetriever` | Semantic lookup with connected context | Semantic entry plus graph expansion |
| Reviewed fixed Cypher | Known structured questions | Application-owned database filtering over named fields and relationships |
| `Text2CypherRetriever` (optional) | Flexible structured questions | Model-generated read-only database queries |

The booking application needs exact hotel-name matching and connected named fields
in one context record. Module 2 therefore selects the fixed `HybridCypherRetriever`
exposed by `search_hotel_knowledge`. Module 3 uses that function to ground answers,
abstain when required context is missing, and keep reservation writes behind a
separate protected command.

## Next

Head to [Module 3](../03-grounded-booking-agent/).
