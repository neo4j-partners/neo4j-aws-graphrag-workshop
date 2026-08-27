---
title: "Neo4j Graph Intelligence Platform"
weight: 3
---

A grounded agent needs a knowledge layer that can retrieve source text and
follow the connections around it. Neo4j provides that layer. In this workshop,
one AuraDB database holds the hotel knowledge graph, retrieval indexes,
provenance, booking rules, reservation requests, and cross-session memory.

| Capability | What it contributes |
|---|---|
| **Native graph database** | Stores entities and relationships as the domain model the application queries |
| **Cypher** | Expresses connected patterns, structured filters, provenance paths, and transactional rules |
| **Vector and full-text indexes** | Combine semantic similarity with exact names, identifiers, and terms |
| **GraphRAG** | Expands a matched text chunk into connected hotel facts and their sources |
| **Graph memory** | Links actor-scoped preferences to conversations, messages, and real domain entities |
| **Drivers, connectors, and MCP** | Connect application code, data pipelines, and agents to the graph |

---

## AuraDB and the Property Graph

:link[Neo4j AuraDB]{href="https://neo4j.com/product/auradb/" external=true} is the
managed graph database used by every module. The workshop graph represents
hotels, rooms, amenities, policies, services, documents, and chunks as nodes.
Named relationships make the paths between them explicit.

For example, a query can require that the same hotel connects to both a spa and
a swimming pool, then continue from that hotel to its cancellation policy and
the source chunk that supports the answer. Cypher describes that shape directly.

The graph transaction is also where the application-owned reservation command
checks the hotel's guest limit and writes the request. Model behavior is not
the final control.

---

## One Graph, Multiple Retrieval Signals

The workshop keeps source text and structured domain facts in one connected
graph:

- **Vector search** finds chunks whose meaning resembles a question.
- **Full-text search** protects exact hotel names, postal codes, and other identifiers.
- **Graph expansion** follows a matched chunk to the hotel, amenities, policy, service, room, and source document.
- **Structured Cypher** filters and aggregates known graph fields.

These are complementary entry paths over the same data. GraphRAG is the step
that combines retrieved text with the explicit entities and relationships
around it.

:image[The workshop graph connects source documents and chunks to structured hotel facts]{src="../../images/01-graph-structure.svg" width=800}

---

## Provenance and Grounding

The graph does more than return an answer-shaped record. It keeps the path back
to the source document. The retrieval tools return source filenames, source
chunks, graph fields, and a field-level provenance description in a bounded
result shape.

That evidence lets the agent distinguish three outcomes:

- **Supported:** The graph contains the facts required for the answer.
- **Missing fact:** The graph has related context but lacks a required fact.
- **No evidence:** The tool returned no usable evidence.

The prompt tells the model how to respond, while the returned evidence and trace
make the behavior inspectable.

---

## Graph Memory

Module 6 extends the same graph with `User`, `Conversation`, `Message`, and
`Preference` nodes. A saved preference links to the message it came from and to
the real `Hotel` node it describes.

This structure makes memory:

- **Actor-scoped:** Recall starts from one selected `User` node. A production application must bind that identifier to the authenticated caller.
- **Auditable:** A preference retains its source message and session.
- **Correctable:** The application can update a specific graph record directly.
- **Connected:** Recalled information can traverse to current domain data.

Neo4j graph memory complements the AWS agent infrastructure. AgentCore can host
the agent, while Neo4j provides memory the application can query and govern as
connected data.

---

## Where Neo4j Appears in the Workshop

| Module | Neo4j capabilities |
|---|---|
| **Setup** | Create AuraDB, restore the workshop graph, and verify connectivity |
| **1. Build the Graph** | Fixed schema, extraction, constraints, vector index, full-text index, and provenance |
| **2. Graph-Enriched Retrieval** | Vector, hybrid, VectorCypher, and Text2Cypher retrieval |
| **3. Grounded Booking Agent** | Bounded read tools, connected evidence, and transactional booking rules |
| **4. Production Agent** | Neo4j driver access from Lambda-backed Gateway tools |
| **5. AgentCore Deployment** | Direct AuraDB access from the Runtime-hosted agent |
| **6. Neo4j Graph Memory** | Actor-scoped recall, source links, correction, and domain connections |

## Learn More

- :link[Neo4j Graph Intelligence Platform]{href="https://neo4j.com/" external=true}
- :link[Neo4j Aura documentation]{href="https://neo4j.com/docs/aura/" external=true}
- :link[Neo4j GraphRAG for Python]{href="https://neo4j.com/docs/neo4j-graphrag-python/current/" external=true}
- :link[Neo4j connectors]{href="https://neo4j.com/docs/connectors/" external=true}

## Next

Continue to [Foundations](../foundations/) to learn the property graph and
GraphRAG concepts used in the labs.
