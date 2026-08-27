---
title: "GraphRAG with Neo4j on AWS: From Search to Grounded Agents"
weight: 0
---

This workshop shows how to build a booking agent that answers from a connected
graph. Semantic search finds relevant source text. Graph traversal then adds
properties, relationships, and provenance so the agent can identify the hotel
and show the source for its answer.

This workshop uses a hotel booking scenario. You will:

- **Compare retrieval:** Test GraphRAG retrieval paths for different question types.
- **Shape retrieval tools:** Turn complementary passage and structured patterns into bounded interfaces.
- **Build an agent:** Let the model route between those tools and inspect its grounding evidence.
- **Deploy tools and the agent:** Use :link[Amazon Bedrock AgentCore]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}.
- **Add memory:** Store agent memory as a graph in :link[Neo4j]{href="https://neo4j.com/" external=true}.

Start with [How Neo4j + AWS Work Together](./platform/). It leads through short
guides to [AWS GenAI Services](./aws-services/) and the
[Graph Intelligence Platform](./neo4j-platform/), then into the GraphRAG
concepts in [Foundations](./foundations/).

**Source code:** :link[Open the workshop repository on GitHub]{href="https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop" external=true}.

## Why Grounding Matters

A booking agent needs evidence for its answers and controls for its actions.

- **Wrong answer:** The agent promises an amenity that the hotel does not offer.
- **Wrong action:** The agent accepts a reservation request for more guests than the hotel allows.
- **Missing provenance:** The team cannot trace a claim to its source document.
- **Workshop challenge:** Which Chicago hotel has both a spa and a swimming pool, what is its cancellation policy, and can I submit a booking request for four guests?

You will connect each answer to its sources. A separate reservation command
will enforce booking rules before it saves a request.

:::alert{type="info" header="Region"}
This workshop runs in **us-east-1**, the N. Virginia region. Your AWS account
arrives pre-configured. Setup guides you through creating a free Neo4j database.
:::

---

## Workshop Flow

| Module | What You Will Build |
|--------|---------------------|
| **Platform overview** | See how AWS and Neo4j work together, then learn the capabilities each platform contributes |
| **Foundations** | Learn the property graph, the GraphRAG retrieval flow, service responsibilities, and AgentCore capabilities |
| **Setup** | Create a Neo4j AuraDB Free database, restore the workshop graph, verify Neo4j and :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} access |
| **Module 1: Build the Graph** | Extract five held-out hotel documents into the graph, define the extraction schema, create both retrieval indexes |
| **Module 2: From Vector Search to Graph-Enriched Retrieval** | Semantic search, exact-term search, and graph-enriched retrieval |
| **Module 3: Build a Grounded Booking Agent with GraphRAG** | Turn two GraphRAG read paths into agent tools, check grounding verdicts, and protect reservation writes |
| **Module 4: Production Agent with AgentCore** | AgentCore Gateway, IAM-authenticated MCP, and a Strands agent over remote tools |
| **Module 5: Deploy to AgentCore Runtime** | Containerize the agent, launch it on Runtime, correlate one request end to end |
| **Module 6: Neo4j Graph Memory** | Cross-session graph memory, actor-scoped recall, full provenance, and a conceptual AgentCore comparison |
| **Summary, Production Path, and Wrap-up** | The argument end to end, the decision tables, the work required for production, and where to take it next |

This sequence moves the retrieval capabilities from local tools into production
deployment patterns, then adds cross-session memory.

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
- **Grounding:** Inspect tool selection and structured evidence, state missing facts, and enforce write rules in one transaction.
- **Remote tools:** Deploy tools to AgentCore Gateway and call them through IAM-authenticated MCP.
- **Memory:** Store auditable, correctable graph memory.
- **Architecture:** Assign clear roles to Neo4j, Bedrock, Strands, Gateway, Runtime, Lambda, and IAM.

---

## Prerequisites

- **Skills:** Use basic Python and AWS CLI commands.
- **Neo4j Aura:** Create a free account during the first Setup step.
- **Hosted environment:** Run the notebooks in Vocareum's JupyterLab environment.

Presenter slides for the opening\: [The Business Case for Grounded Agents](./slides/overview-business-story/)

:::alert{type="warning" header="Cost"}
This workshop creates AWS resources that incur charges. Follow the cleanup instructions at the end. Estimated cost\: under $2.
:::

::children{depth=2 variant=list}
