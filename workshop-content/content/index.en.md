---
title: "GraphRAG with Neo4j on AWS: From Search to Grounded Agents"
weight: 0
---

## Build Agents from Connected Evidence

A booking agent is useful only when it can name the hotel it means and show where that answer came from. Semantic search finds source text that is relevant to a question. Graph traversal can extend that match with named fields, relationships, and provenance. The two signals solve different parts of the retrieval problem.

This workshop uses a hotel booking scenario to compare four retrieval patterns, select a fixed production retriever, and wire a grounded agent with :link[Amazon Bedrock AgentCore]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}, :link[Neo4j]{href="https://neo4j.com/" external=true} retrieval tools, and inspectable graph memory.

:::alert{type="info" header="Region"}
This workshop runs in **us-east-1 (N. Virginia)**. Your AWS account arrives pre-configured. You create the Neo4j database yourself in Setup, on the free tier.
:::

---

## Workshop Flow

| Module | What You Will Build |
|--------|---------------------|
| **Setup** | Create a Neo4j AuraDB Free database, restore the workshop graph, verify Neo4j and :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} access |
| **Module 1: Build the Graph** | Extract five held-out hotel documents into the graph, pin the extraction schema, create both retrieval indexes |
| **Module 2: From Similarity Search to Connected Context** | Semantic retrieval, exact-term search, and connected graph context |
| **Module 3: Build the Grounded Booking Agent** | Grounded answers, abstention, and protected reservation writes |
| **Module 4: Production Agent with AgentCore** | AgentCore Gateway, IAM-authenticated MCP, and a Strands agent over remote tools |
| **Module 5: Deploy to AgentCore Runtime** | Containerize the agent, launch it on Runtime, correlate one request end to end |
| **Module 6: Inspectable Neo4j Memory** | Cross-session graph memory, actor-scoped recall, full provenance, and a conceptual AgentCore comparison |
| **Summary and Wrap-up** | The argument end to end, the two decision tables, and where to take it next |

---

## Module 4 Tool Architecture

:image[Production agent architecture: a Strands agent calls Neo4j retrieval Lambdas through AgentCore Gateway]{src="../images/03-agentcore-architecture.png" width=800}

Module 5 demonstrates a separate deployment pattern: a packaged agent on
AgentCore Runtime that connects directly to Neo4j. Module 6 then adds
cross-session graph memory.

**Neo4j owns:** hotel knowledge, retrieval indexes, business rules, reservation writes, and graph memory.
**Amazon Bedrock owns:** reasoning over retrieved evidence and embeddings.

---

## What You Will Learn

1. How a pinned schema and provenance make extracted knowledge predictable to query
2. When to use Vector, Hybrid, VectorCypher, and Text2Cypher retrieval
3. How to build a grounded agent that declines unsupported requests and enforces rules atomically
4. How to deploy tools to AgentCore Gateway and connect agents over IAM-authenticated MCP
5. How explicit graph memory supports audit and correction

---

## Prerequisites

- Basic Python and AWS CLI familiarity
- A :link[Neo4j Aura]{href="https://console.neo4j.io/" external=true} account, free to create, which you set up in the first Setup step
- Nothing to install on your own machine for the hosted path; the notebooks run in the JupyterLab environment Vocareum provides

:::alert{type="warning" header="Cost"}
This workshop creates AWS resources that incur charges. Follow the cleanup instructions at the end. Estimated cost\: under $2.
:::

::children{depth=2 variant=list}
