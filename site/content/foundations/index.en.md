---
title: "Foundations: Neo4j, AWS, and AgentCore"
weight: 5
---

This workshop combines Neo4j, Amazon Bedrock, Strands, and Amazon Bedrock
AgentCore. Each component has one main role:

- **Neo4j:** Stores connected hotel facts, source text, rules, and memory.
- **Amazon Bedrock:** Provides models for reasoning and embeddings.
- **Strands:** Gives the model a set of tools it can call.
- **AgentCore:** Exposes remote tools and runs deployed agents.

These roles and terms appear in every module.

---

## The Property Graph Model

A property graph stores data with three parts:

- **Node:** A thing, such as a hotel, room, amenity, document, or text chunk.
- **Relationship:** A named connection between nodes, such as `OFFERS_AMENITY`.
- **Property:** A named value, such as a hotel name or guest rating.

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

- **`MATCH`:** Selects a graph pattern.
- **Parentheses:** Describe nodes.
- **Square brackets:** Describe relationships.
- **Arrows:** Describe relationship direction.
- **`WHERE`:** Filters the result.
- **`RETURN`:** Selects the fields sent to the application.

Neo4j stores facts and their connections. Cypher retrieves the required path
through those facts.

---

## From RAG to GraphRAG

Retrieval-augmented generation sends selected source material to a model before
it answers. GraphRAG adds graph facts and connections to that source material.

- **Vector search:** Finds text with similar meaning.
- **Full-text search:** Finds exact names, identifiers, and terms.
- **Graph expansion:** Adds connected entities, their properties, and provenance.
- **Structured Cypher:** Filters and aggregates known graph fields.

The workshop graph keeps a lexical graph and a domain graph, connected to each other:

:image[Two connected layers: the source file becomes a Document and Chunk in the lexical graph, and a Hotel node with typed Room, Amenity, Policy, and Service relationships in the domain graph]{src="../../images/01-graph-structure.svg" width=800}

- **Search:** Finds a `Chunk` in the lexical graph.
- **Expansion:** The retrieval query follows typed relationships into the domain graph.
- **Provenance:** Links each extracted fact to its source.

---

## One Grounded Request

The deployment changes across modules. The retrieval flow stays the same:

:image[A question moves through the Strands agent using Claude on Amazon Bedrock, a search_hotel_knowledge tool call that gets an Amazon Nova query embedding, Neo4j vector and full-text indexes, retrieval query expansion into hotel properties, and returned context, ending in a grounded answer or a clear statement that the context cannot answer the question]{src="../../images/foundations-grounded-request-flow.svg" width=800}

- **Answer flow:** The model answers from the returned context.
- **Reservation command:** A separate command validates the request and writes it.
- **Rule enforcement:** Neo4j checks the guest limit in the write transaction.

---

## Service Roles

- **:link[Neo4j AuraDB]{href="https://neo4j.com/product/auradb/" external=true}:** Stores hotel facts, source text, indexes, rules, reservation requests, and graph memory.
- **:link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true}:** Provides Claude for extraction and reasoning, Amazon Nova for retrieval embeddings, and Titan Text Embeddings V2 for memory.
- **:link[Strands Agents]{href="https://strandsagents.com/" external=true}:** Gives the model local or remote tools and runs the agent loop.
- **:link[AgentCore Gateway]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}:** Exposes the Module 4 Lambda functions through MCP.
- **:link[AgentCore Runtime]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}:** Runs the packaged Module 5 agent.
- **AgentCore Memory:** Provides the managed memory option discussed in Module 6.
- **:link[AWS Lambda]{href="https://aws.amazon.com/lambda/" external=true}:** Runs the Module 4 retrieval tools.
- **:link[AWS Secrets Manager]{href="https://aws.amazon.com/secrets-manager/" external=true}:** Stores the Neo4j settings used by the Lambda functions.
- **AWS IAM and SigV4:** Control access to AWS models, secrets, tools, and runtimes.

---

## AgentCore Capabilities

AgentCore includes several capabilities. This workshop uses or discusses three:

- **Gateway:** Gives agents access to remote tools. Module 4 exposes Lambda functions through IAM-authenticated MCP.
- **Runtime:** Runs a complete agent as a service. Module 5 invokes the agent with `InvokeAgentRuntime`.
- **Memory:** Stores and recalls information across sessions. Module 6 compares this managed option with Neo4j graph memory.
- **MCP:** Defines how an agent discovers and calls tools.
- **IAM SigV4:** Confirms that the caller can use the Gateway.

Module 4 and Module 5 show separate patterns. Module 4 routes remote tools
through Gateway. The Module 5 Runtime uses Neo4j as its data service.

---

## Control Ownership

Each control belongs to a layer that can enforce it:

- **Retriever:** The application selects one retriever and uses it for every question.
- **Answer:** The model answers from the context the tool returned, or states that the context is missing.
- **Graph query:** The fixed `retrieval_query` defines the traversal.
- **Database write:** Neo4j rejects invalid and duplicate requests.
- **AWS access:** IAM controls deployment and service calls.
- **Memory access:** Actor-scoped Cypher limits recall to one actor.

You can reuse this separation of layers with a different graph schema and domain.

## Next

Head to [Setup](../setup/).
