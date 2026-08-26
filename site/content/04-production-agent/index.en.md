---
title: "Module 4: Production Agent with AgentCore"
weight: 50
---

## Deploy the Agent Tools

Module 4 moves the booking agent's retrieval tools from the notebook process to
AWS-managed services. AgentCore Gateway provides a managed MCP endpoint, and
AWS Lambda runs each retrieval tool. IAM SigV4 authenticates every request with
the caller's AWS credentials.

| Notebook constraint | Production capability |
|---|---|
| Tools as in-process functions | :link[Bedrock AgentCore]{href="https://aws.amazon.com/bedrock/agentcore/" external=true} Gateway presents :link[AWS Lambda]{href="https://aws.amazon.com/lambda/" external=true} tools through a managed MCP endpoint |
| Tool authentication | **IAM SigV4**: requests signed with AWS credentials |

The Gateway places two retrieval Lambdas behind one managed endpoint. A Strands
agent then resolves the remote MCP tools and uses them through the same tool
interface as local functions.

:image[Module 4 architecture: a Strands agent calls Neo4j retrieval Lambdas through an IAM-authenticated AgentCore Gateway]{src="../../images/03-agentcore-architecture.svg" width=800}

---

## Deploy the Gateway and Retrieval Lambdas

Open `notebooks/04-production-agent/4.1_agentcore_gateway.ipynb` to deploy the
Gateway, its retrieval Lambdas, and the supporting AWS resources.

:::alert{type="warning" header="These resources stay until you delete them"}
The notebook creates two Lambda functions:
`hotel-booking-search-hotel-knowledge` and `hotel-booking-graph-query`. It also
creates the AgentCore Gateway `hotel-booking-gateway` with one target per tool,
the Secrets Manager secret `neo4j-ws-retrieval`, and two IAM roles:
`workshop-hotel-lambda-role` and `workshop-hotel-gateway-role`.

The Gateway and secret incur charges while they exist, and the Lambdas incur
charges per invocation. The notebook leaves these resources in place. Workshop
Studio removes them when the event ends. In your own account, delete them from
the console or CLI when you finish.
:::

The managed endpoint exposes two retrieval patterns, which lets the agent match
each question to the appropriate Neo4j query strategy:

| Gateway tool | Retriever | Question shape |
|---|---|---|
| `search_hotel_knowledge` | `HybridCypherRetriever` | Semantic: rooms, amenities, policies, services |
| `graph_query` | `Text2CypherRetriever` | Structured: counts, averages, filters, connected traversals |

Both tools import from `notebooks/workshop/hybrid_retrieval.py`.
`search_hotel_knowledge` reuses the function called by Module 3.1, while
`graph_query` packages the Text2Cypher pattern from Module 2.1 as a reusable
function. Each Lambda handler unwraps the Gateway event and calls the matching
function.

Both interfaces retrieve context from Neo4j. `search_hotel_knowledge` runs the
fixed `retrieval_query` selected in Module 2. `graph_query` validates model-generated Cypher with
`EXPLAIN` and executes the statement only when the planner reports a read-only
query. The reservation command remains outside the Gateway because this
endpoint serves retrieval operations.

AWS Secrets Manager supplies the Neo4j connection to both Lambdas through
`neo4j-ws-retrieval`. The `workshop-hotel-lambda-role` execution role grants the
Lambdas access to that secret and to the required Bedrock models.

:::alert{type="info" header="Add production security controls"}
These Lambdas connect with ordinary workshop credentials. In production,
connect with a **read-only Neo4j user** so the database rejects every write.
Restrict the Lambda IAM role to the required secret and Bedrock models.
`Text2CypherRetriever` also plans each statement with `EXPLAIN` and executes it
only when the planner reports a read-only query. The notebook verifies this
application guard with a stub model that generates a write.
:::

After deployment, configure an MCP client with `mcp-proxy-for-aws` to connect to
the IAM-authenticated Gateway\:

:::code{language=python showCopyAction=true}
gateway_mcp = MCPClient(
    lambda: stdio_client(StdioServerParameters(
        command="uvx",
        args=["mcp-proxy-for-aws@latest", GATEWAY_ENDPOINT_URL, "--region", "us-east-1"],
        env=os.environ.copy(),
    ))
)
with gateway_mcp:
    agent = Agent(tools=gateway_mcp.list_tools_sync(), ...)
:::

The proxy signs every Gateway request with your AWS credentials. Strands then
passes the resolved MCP tools to the agent through the same `tools` interface
used for local functions.

### Verify Successful and Empty Results

The retrieval tool returns no context when Neo4j cannot answer a question. An
unavailable index, an incorrect index name, invalid credentials, or the wrong
database can also produce an empty result, so an empty response alone cannot
confirm correct retrieval behavior.

The notebook distinguishes a valid empty result from a retrieval failure by
running two checks for each tool. A **negative control** confirms that a
nonexistent hotel produces no match. A **positive control** confirms that an
existing hotel returns an exact address or guest rating, which verifies that
the tool can reach populated Neo4j data.

---

## Connect a Strands Agent

After the direct MCP checks, the notebook passes the resolved Gateway tools to
a Strands agent. The agent uses context from the selected remote tool to answer
a hotel question, and the trace identifies which Gateway tool it called. The
consistent tool interface lets the agent use the Lambda implementations in the
same way it used local functions.

Module 5 packages a separate version of the agent for AgentCore Runtime. Module
6 then adds cross-session memory by storing each preference in Neo4j and linking
it to its source message and hotel.

## Next

Head to [Module 5](../05-agentcore-deploy/).
