---
title: "Foundations: Neo4j, AWS, and AgentCore"
weight: 5
---

## Learn the Architecture Before You Build It

This workshop combines a knowledge graph, foundation models, agent tools, and
managed agent infrastructure. Each component has a distinct responsibility.
Neo4j stores and queries connected evidence. Amazon Bedrock provides models for
reasoning and embeddings. Strands gives the model a tool interface. Amazon
Bedrock AgentCore moves those tools and the agent into managed production
environments.

The modules build these layers in sequence. This page introduces the terms and
boundaries that remain consistent throughout the workshop.

---

## Read a Property Graph

A property graph represents information with three building blocks:

- **Nodes** represent things, such as a hotel, room, amenity, document, or text chunk.
- **Relationships** connect those things with a named direction, such as `OFFERS_AMENITY` or `FROM_DOCUMENT`.
- **Properties** store named values on nodes and relationships, such as a hotel name or guest rating.

The pattern below says that a hotel offers an amenity:

:::code{language=cypher}
(:Hotel {name: "AnyCompany Cairo Nile View"})
    -[:OFFERS_AMENITY]->
(:Amenity {name: "Spa"})
:::

Cypher is Neo4j's graph query language. Its pattern syntax follows the same
shape as the graph:

:::code{language=cypher showCopyAction=true}
CYPHER 25
MATCH (h:Hotel)-[:OFFERS_AMENITY]->(a:Amenity)
WHERE h.name = $hotel_name
RETURN h.name AS hotel, collect(a.name) AS amenities
:::

`MATCH` selects a graph pattern. Parentheses describe nodes, square brackets
describe relationships, and arrows describe direction. `WHERE` applies a
filter, and `RETURN` selects the evidence the application receives.

The value of the graph is not the drawing. The value is the ability to store a
fact once, connect it to related facts, and retrieve the required path directly.

---

## Move from RAG to GraphRAG

Retrieval-augmented generation gives a model selected source material before it
answers. A basic flow embeds a question, finds similar passages, and sends those
passages to the model. This grounds the answer in private or current evidence.

Vector similarity is useful, but it returns text that has similar meaning. It
does not guarantee exact identifiers, named fields, or relationships between
records. GraphRAG combines retrieval signals with graph structure.

| Pattern | What it contributes |
|---|---|
| Vector search | Passages that express similar meaning |
| Full-text search | Exact names, identifiers, and terms |
| Graph expansion | Connected fields, relationships, and provenance |
| Structured Cypher | Database filtering and aggregation over known fields |

The workshop graph keeps two connected layers:

```text
Lexical evidence                         Domain facts

(Document)<-[:FROM_DOCUMENT]-(Chunk)<-[:FROM_CHUNK]-(Hotel)
                                                        |
                                                        +--[:HAS_ROOM]-------->(Room)
                                                        +--[:OFFERS_AMENITY]-->(Amenity)
                                                        +--[:HAS_POLICY]------>(Policy)
                                                        `--[:PROVIDES_SERVICE]->(Service)
```

Search begins in the lexical layer. A reviewed traversal then returns domain
facts and the source that produced them. The source remains visible because
graph extraction can omit or merge information. The graph is queryable evidence,
and provenance makes that evidence inspectable.

---

## Follow One Grounded Request

The exact deployment changes across modules, but the evidence path stays stable:

```text
Question
   |
   v
Strands agent using Claude on Amazon Bedrock
   |
   v
search_hotel_knowledge tool
   |
   +--> Amazon Nova creates the query embedding
   |
   v
Neo4j vector and full-text indexes
   |
   v
Reviewed Cypher expands the matched Chunk into hotel facts
   |
   v
Bounded evidence with source provenance
   |
   v
Grounded answer or explicit abstention
```

The model reasons over returned evidence. It does not become the system of
record. A separate reservation command validates its input and applies the
maximum-guests rule in the same Neo4j transaction that performs the write.

---

## Know What Each Service Owns

| Component | Responsibility in this workshop |
|---|---|
| :link[Neo4j AuraDB]{href="https://neo4j.com/product/auradb/" external=true} | Stores hotel knowledge, source provenance, vector and full-text indexes, business rules, reservation requests, and graph memory |
| :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} | Provides Claude for extraction and reasoning, Amazon Nova for graph and query embeddings, and Titan Text Embeddings V2 for the memory module |
| :link[Strands Agents]{href="https://strandsagents.com/" external=true} | Presents Python functions or remote MCP operations to the model as tools and runs the agent loop |
| :link[AgentCore Gateway]{href="https://aws.amazon.com/bedrock/agentcore/" external=true} | Exposes the Module 4 Lambda retrieval functions through a managed MCP endpoint |
| :link[AgentCore Runtime]{href="https://aws.amazon.com/bedrock/agentcore/" external=true} | Hosts and invokes the packaged Module 5 agent as a managed service |
| AgentCore Memory | Provides the managed memory alternative discussed conceptually in Module 6 |
| :link[AWS Lambda]{href="https://aws.amazon.com/lambda/" external=true} | Runs the two retrieval tools deployed in Module 4 |
| :link[AWS Secrets Manager]{href="https://aws.amazon.com/secrets-manager/" external=true} | Supplies the Neo4j connection settings to the Module 4 Lambda functions |
| AWS IAM and SigV4 | Authorize deployment, model invocation, secret access, Gateway calls, and Runtime calls |

---

## Distinguish the AgentCore Capabilities

AgentCore is a family of capabilities rather than one box in the architecture.
This workshop uses or discusses three of them:

| Capability | Question it answers | Workshop use |
|---|---|---|
| Gateway | How can an agent call remote tools through a standard protocol? | Module 4 places retrieval Lambdas behind IAM-authenticated MCP |
| Runtime | Where can the complete agent run as an invokable service? | Module 5 packages the agent and invokes it with `InvokeAgentRuntime` |
| Memory | Who extracts, stores, and recalls cross-session memory? | Module 6 compares the managed service with explicit Neo4j graph memory |

Gateway and Runtime demonstrate separate production patterns here. The Runtime
agent in Module 5 connects directly to Neo4j. It does not call the Module 4
Gateway.

MCP standardizes how an agent discovers and calls tools. IAM SigV4 determines
whether the caller may reach this workshop's Gateway. The protocol and the
authorization mechanism solve different problems.

---

## Keep the Control Boundaries Explicit

The workshop places each decision at the layer that can enforce it:

- The application selects one fixed production retriever after comparing retrieval evidence.
- The model receives bounded tool results and must abstain when they do not support an answer.
- Reviewed Cypher defines the normal graph expansion path.
- Neo4j independently rejects invalid or duplicate reservation writes.
- IAM controls which AWS identities can deploy resources or invoke services.
- Actor-scoped Cypher prevents one memory recall query from crossing into another actor's records.

These boundaries matter more than the specific hotel domain. You can replace
the schema and questions while keeping the same division of responsibility.

## Next

Head to [Setup](../setup/).
