---
title: "Wrap-up"
weight: 90
---

# Workshop Wrap-up

**Congratulations on completing the GraphRAG workshop.**

## What You Accomplished

### Module 1: Built the Graph
- Extracted the **held-out hotel documents** into :link[Neo4j]{href="https://neo4j.com/" external=true}
- **Fixed the extraction schema** so extraction produced predictable node labels and relationships
- Verified the **uniqueness constraints** that keep entities de-duplicated
- Created **both retrieval indexes** (vector and full-text) that every later module queries

### Module 2: Built Graph-Enriched Retrieval
- Used **semantic search** to find relevant source text
- Added **exact-term retrieval** for names, identifiers, and postal codes
- Expanded matched chunks into **graph-enriched results** carrying connected entities, their properties, and provenance
- Compared the returned context before asking a model to generate an answer

### Module 3: Built the Grounded Booking Agent
- Applied the selected **retriever** to the booking workflow
- Used **hybrid retrieval** with a vector arm, a full-text arm, and the traversal in its `retrieval_query`
- Declined questions when the returned context did not support an answer
- **A grounded booking agent** that abstains when the graph is silent, and writes only inside a transaction that has already checked the rules

### Modules 4 and 5: Built Production Infrastructure
- **AgentCore Gateway:** Lambda retrieval tools exposed as a managed MCP endpoint
- **IAM SigV4 authentication:** signed tool calls with no API keys to manage
- **Strands over MCP:** the Gateway's resolved remote tools passed directly to an agent
- **AgentCore Runtime:** the agent containerized, launched on Runtime, and one request correlated end to end

### Module 6: Stored Memory as a Graph
- Recalled a preference for the same actor in a new session while isolating a second actor
- Stored preferences as **graph nodes** instead of opaque managed records
- Kept **full provenance**: every `Preference` links back to its source `Message` and to the real `Hotel` node
- Corrected a wrong preference with a single `SET`, no delete and re-extract
- Compared **Neo4j memory with AgentCore Memory** conceptually on write timing, auditability, correction, and who operates it

---

## Key Concepts to Remember

1. **Retrieval signals are complementary.** Semantic similarity finds relevant language. Exact terms protect identifiers. Graph structure adds connected entities and their properties.
2. **A graph gives structural precision.** Properties and relationships can be queried, filtered, and handed to a write path with their provenance.
3. **MCP keeps remote-tool integration clean.** In Module 4, Gateway tools enter the Strands agent through the same `tools` interface as local functions. Module 5 demonstrates a separate deployment pattern: a packaged agent on Runtime that connects directly to Neo4j.
4. **Graph memory gives long-term context you can audit.** Provenance is what turns a wrong preference from an outage into a one-line correction.

---

## Architectures You Built

:image[Three architectures recapped: Module 4's Notebook Strands agent calling AgentCore Gateway and Lambda retrieval tools into Neo4j, Module 5's authorized caller invoking AgentCore Runtime with a packaged Strands agent calling both Neo4j and Bedrock, and Module 6's notebook or app writing directly to the Neo4j graph memory]{src="../../images/wrap-up-architectures.svg" width=800}

Runtime does not call Gateway in this workshop. Modules 4 and 5 are two
production patterns built from the earlier retrieval work, while Module 6 is
the canonical hands-on memory path.

---

## Next Steps

### Start with your own data
1. **Adapt the schema:** replace the hotel entities with your own, and define the schema the same way
2. **Re-run the extraction:** preserve source identifiers and provenance in the new domain
3. **Build a retrieval evaluation set:** include semantic, exact-term, graph-enriched, and structured questions

### Then tune what you built
1. **Tune retrieval quality:** adjust the hybrid `alpha` and the traversal in `retrieval_query` against your own query logs
2. **Add guardrails:** validate generated Cypher, and never let it write
3. **Set up monitoring:** the Runtime traces from Module 5 are the starting point

### Then operate it
1. **Deploy from your own pipeline:** the container the workshop built is the same one CI would build
2. **Close the feedback loop:** collect corrections and write them back as graph memory, with provenance
3. **Automate graph maintenance:** refresh, re-embed, and re-index on a schedule

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
What worked well? What would you change? Tell us, so the next room gets a better version of this.
:::

## Thank You

We hope you enjoyed learning how GraphRAG turns relevant source text into connected, traceable context with full provenance for an agent.

Happy building.
