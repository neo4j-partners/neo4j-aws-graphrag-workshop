---
title: "GraphRAG with Neo4j on AWS: From Search to Grounded Agents"
weight: 0
---

## Build Agents from Connected Evidence

A grounded booking agent identifies the hotel and shows the source for its
answer. Semantic search finds relevant source text. Graph traversal adds named
fields, relationships, and provenance.

This workshop uses a hotel booking scenario. You will:

- **Compare retrieval:** Test four retrieval patterns.
- **Select a retriever:** Choose one fixed pattern for the application.
- **Build an agent:** Ground answers in Neo4j evidence.
- **Deploy tools and the agent:** Use :link[Amazon Bedrock AgentCore]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}.
- **Add memory:** Store inspectable memory in :link[Neo4j]{href="https://neo4j.com/" external=true}.

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
| **Foundations** | Learn the property graph, GraphRAG evidence flow, service responsibilities, and AgentCore capability boundaries |
| **Setup** | Create a Neo4j AuraDB Free database, restore the workshop graph, verify Neo4j and :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} access |
| **Module 1: Build the Graph** | Extract five held-out hotel documents into the graph, pin the extraction schema, create both retrieval indexes |
| **Module 2: From Similarity Search to Connected Context** | Semantic retrieval, exact-term search, and connected graph context |
| **Module 3: Build the Grounded Booking Agent** | Grounded answers, abstention, and protected reservation writes |
| **Module 4: Production Agent with AgentCore** | AgentCore Gateway, IAM-authenticated MCP, and a Strands agent over remote tools |
| **Module 5: Deploy to AgentCore Runtime** | Containerize the agent, launch it on Runtime, correlate one request end to end |
| **Module 6: Inspectable Neo4j Memory** | Cross-session graph memory, actor-scoped recall, full provenance, and a conceptual AgentCore comparison |
| **Summary, Production Path, and Wrap-up** | The argument end to end, the decision tables, the work required for production, and where to take it next |

---

## Module 4 Tool Architecture

:image[Production agent architecture: a Strands agent calls Neo4j retrieval Lambdas through AgentCore Gateway]{src="../images/03-agentcore-architecture.svg" width=800}

Module 5 demonstrates a separate deployment pattern: a packaged agent on
AgentCore Runtime that connects directly to Neo4j. Module 6 then adds
cross-session graph memory.

- **Neo4j:** Stores hotel knowledge, indexes, business rules, reservation requests, and graph memory.
- **Amazon Bedrock:** Provides reasoning and embedding models.

---

## What You Will Learn

- **Graph construction:** Use a pinned schema and provenance to create queryable facts.
- **Retrieval:** Choose Vector, Hybrid, VectorCypher, or Text2Cypher for each question shape.
- **Grounding:** Answer from evidence and enforce write rules in one transaction.
- **Remote tools:** Deploy tools to AgentCore Gateway and call them through IAM-authenticated MCP.
- **Memory:** Store graph memory that supports audit and correction.
- **Architecture:** Assign clear roles to Neo4j, Bedrock, Strands, Gateway, Runtime, Lambda, and IAM.

---

## Prerequisites

- Basic Python and AWS CLI familiarity
- A :link[Neo4j Aura]{href="https://console.neo4j.io/" external=true} account, free to create, which you set up in the first Setup step
- Nothing to install on your own machine for the hosted path; the notebooks run in the JupyterLab environment Vocareum provides

:::alert{type="warning" header="Cost"}
This workshop creates AWS resources that incur charges. Follow the cleanup instructions at the end. Estimated cost\: under $2.
:::

::children{depth=2 variant=list}
