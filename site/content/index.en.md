---
title: "GraphRAG with Neo4j on AWS: From Search to Grounded Agents"
weight: 0
---

This workshop shows how to build a booking agent that answers from a connected
graph. Semantic search finds relevant source text. Graph traversal then adds
properties, relationships, and provenance so the agent can identify the hotel
and show the source for its answer.

This workshop uses a hotel booking scenario. You will:

- **Compare retrieval:** Test four retrieval patterns.
- **Select a retriever:** Choose one fixed pattern for the application.
- **Build an agent:** Ground answers in the Neo4j graph.
- **Deploy tools and the agent:** Use :link[Amazon Bedrock AgentCore]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}.
- **Add memory:** Store agent memory as a graph in :link[Neo4j]{href="https://neo4j.com/" external=true}.

Read [Foundations](./foundations/) first if property graphs, GraphRAG, or
AgentCore are new to you.

**Source code:** :link[Open the workshop repository on GitHub]{href="https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop" external=true}.

:::alert{type="info" header="Region"}
This workshop runs in **us-east-1**, the N. Virginia region. Your AWS account
arrives pre-configured. Setup guides you through creating a free Neo4j database.
:::

---

## Workshop Flow

| Module | What You Will Build |
|--------|---------------------|
| **Foundations** | Learn the property graph, the GraphRAG retrieval flow, service responsibilities, and AgentCore capabilities |
| **Setup** | Create a Neo4j AuraDB Free database, restore the workshop graph, verify Neo4j and :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} access |
| **Module 1: Build the Graph** | Extract five held-out hotel documents into the graph, define the extraction schema, create both retrieval indexes |
| **Module 2: From Similarity Search to Graph-Enriched Retrieval** | Semantic search, exact-term search, and graph-enriched retrieval |
| **Module 3: Build the Grounded Booking Agent** | Grounded answers, clear handling of unsupported questions, and protected reservation writes |
| **Module 4: Production Agent with AgentCore** | AgentCore Gateway, IAM-authenticated MCP, and a Strands agent over remote tools |
| **Module 5: Deploy to AgentCore Runtime** | Containerize the agent, launch it on Runtime, correlate one request end to end |
| **Module 6: Neo4j Graph Memory** | Cross-session graph memory, actor-scoped recall, full provenance, and a conceptual AgentCore comparison |
| **Summary, Production Path, and Wrap-up** | The argument end to end, the decision tables, the work required for production, and where to take it next |

This sequence moves one retrieval design from a local notebook into deployed
tools, a runtime service, and cross-session memory.

---

## Module 4 Tool Architecture

:image[Production agent architecture: a Strands agent calls Neo4j retrieval Lambdas through AgentCore Gateway]{src="../images/03-agentcore-architecture.svg" width=800}

Module 5 demonstrates a separate deployment pattern: a packaged agent on
AgentCore Runtime that connects to Neo4j itself. Module 6 then adds
cross-session graph memory.

- **Neo4j:** Stores hotel knowledge, indexes, business rules, reservation requests, and graph memory.
- **Amazon Bedrock:** Provides reasoning and embedding models.

---

## What You Will Learn

- **Graph construction:** Use a fixed extraction schema and provenance to build a queryable graph.
- **Retrieval:** Choose Vector, Hybrid, VectorCypher, or Text2Cypher for each query need.
- **Grounding:** Answer from the returned context and enforce write rules in one transaction.
- **Remote tools:** Deploy tools to AgentCore Gateway and call them through IAM-authenticated MCP.
- **Memory:** Store auditable, correctable graph memory.
- **Architecture:** Assign clear roles to Neo4j, Bedrock, Strands, Gateway, Runtime, Lambda, and IAM.

---

## Prerequisites

- **Skills:** Use basic Python and AWS CLI commands.
- **Neo4j Aura:** Create a free account during the first Setup step.
- **Hosted environment:** Run the notebooks in Vocareum's JupyterLab environment.

:::alert{type="warning" header="Cost"}
This workshop creates AWS resources that incur charges. Follow the cleanup instructions at the end. Estimated cost\: under $2.
:::

::children{depth=2 variant=list}
