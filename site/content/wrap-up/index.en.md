---
title: "Wrap-up"
weight: 90
---

This workshop built a GraphRAG system from source documents through production
deployment and graph memory. The result can retrieve connected context, answer
from that context, protect database writes, and preserve provenance.

## What You Accomplished

### Module 1: Built the Graph

- **Source documents:** Extracted the held-out hotel documents into :link[Neo4j]{href="https://neo4j.com/" external=true}.
- **Extraction schema:** Defined predictable node labels and relationship types before extraction.
- **Uniqueness constraints:** Verified the constraints that prevent duplicate entities.
- **Retrieval indexes:** Created the vector and full-text indexes used by later modules.

### Module 2: Built Graph-Enriched Retrieval

- **Semantic search:** Found relevant source text by meaning.
- **Exact-term search:** Preserved names, identifiers, and postal codes.
- **Graph expansion:** Added connected entities, their properties, and provenance to each matched chunk.
- **Result comparison:** Compared returned context before asking a model to generate an answer.

### Module 3: Built the Grounded Booking Agent

- **Automatic routing:** Let the model choose between passage search and a structured record query from their tool specifications.
- **Inspectable evidence:** Traced the selected tools and read their bounded JSON results.
- **Grounding verdict:** Verified that live room availability was reported as a missing fact without grading final-answer wording.
- **Protected reservation command:** Checked booking rules and wrote the request in one transaction.

### Modules 4 and 5: Built Production Infrastructure

- **AgentCore Gateway:** Exposed Lambda retrieval tools through a managed MCP endpoint.
- **IAM SigV4 authentication:** Signed tool calls with the caller's AWS identity.
- **Strands over MCP:** Passed the Gateway's resolved remote tools to an agent.
- **AgentCore Runtime:** Ran the containerized agent and correlated one request from invocation through response.

### Module 6: Stored Memory as a Graph

- **Actor-scoped recall:** Recalled a preference for the same actor in a new session while isolating a second actor.
- **Graph memory:** Stored each preference as a graph node.
- **Conversation entities:** Linked the source `Message` to the real `Hotel` it mentions.
- **Full provenance:** Linked every `Preference` to its source `Message` and the same `Hotel` node.
- **Retained history:** Replaced changed preferences by appending and superseding instead of overwriting stale text and embeddings.
- **Memory comparison:** Compared Neo4j memory with AgentCore Memory by write timing, auditability, correction, and operational ownership.

---

## Key Concepts to Remember

- **Complementary retrieval signals:** Semantic similarity finds relevant language, exact terms protect identifiers, and graph structure adds connected entities and their properties.
- **Structural precision:** Properties and relationships support precise queries, filters, and commands while retaining provenance.
- **MCP tool interface:** Gateway tools enter the Strands agent through the same `tools` interface as local functions. Module 5 uses a separate pattern in which a packaged Runtime agent connects to Neo4j itself.
- **Auditable graph memory:** Entity links capture what a turn is about, and provenance keeps durable memory tied to its evidence.

---

## Architectures You Built

:image[Three architectures recapped: Module 4's Notebook Strands agent calling AgentCore Gateway and Lambda retrieval tools into Neo4j, Module 5's authorized caller invoking AgentCore Runtime with a packaged Strands agent calling both Neo4j and Bedrock, and Module 6's notebook or app writing to the Neo4j graph memory]{src="../../images/wrap-up-architectures.svg" width=800}

Module 4 routes remote tools through Gateway. Module 5 packages an agent on
Runtime and connects it to Neo4j. Module 6 adds the hands-on graph memory path.

---

## Next Steps

### Start With Your Own Data

1. **Adapt the schema:** Replace the hotel entities with your own and define the schema the same way.
2. **Re-run the extraction:** Preserve source identifiers and provenance in the new domain.
3. **Build a retrieval evaluation set:** Include semantic, exact-term, graph-enriched, and structured questions.

### Then Tune What You Built

1. **Tune retrieval quality:** Adjust the hybrid `alpha` and the traversal in `retrieval_query` against your own query logs.
2. **Add guardrails:** Validate generated Cypher and run it with a read-only Neo4j identity.
3. **Set up monitoring:** Start with the Runtime traces from Module 5.

### Then Operate It

1. **Deploy from your own pipeline:** Build and deploy the workshop container through CI.
2. **Close the feedback loop:** Collect corrections and write them back as graph memory with provenance.
3. **Automate graph maintenance:** Refresh, re-embed, and re-index on a schedule.

---

## Resources

### Documentation

- [Amazon Bedrock Developer Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/)
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
- [Neo4j GraphRAG for Python](https://neo4j.com/docs/neo4j-graphrag-python/current/)
- [Strands Agents](https://strandsagents.com/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)

### Code Repositories

- [Neo4j MCP Server](https://github.com/neo4j-contrib/mcp-neo4j)
- [LangChain Neo4j Integration](https://python.langchain.com/docs/integrations/graphs/neo4j_cypher)

### Further Learning

- [AWS Workshop: Amazon Bedrock Agents](https://catalog.workshops.aws/amazon-bedrock-agents)
- [Neo4j Graph Academy](https://graphacademy.neo4j.com/)

---

## Feedback

:::alert{type="info" header="Share your experience"}
Share what worked well and what should change. Your feedback improves the next workshop session.
:::

## Thank You

You now have a complete example of how GraphRAG turns relevant source text into
connected, traceable context for an agent.
