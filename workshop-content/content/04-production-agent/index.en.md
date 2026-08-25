---
title: "Module 4: Production Agent with AgentCore"
weight: 50
---

## Deploy the Agent Tools and Memory

The Module 3 booking agent calls tools in the notebook process and stores state only for the current session. Module 4 adds three production capabilities:

| Gap | Fix |
|---|---|
| Tools as in-process functions | :link[Bedrock AgentCore]{href="https://aws.amazon.com/bedrock/agentcore/" external=true} Gateway and :link[AWS Lambda]{href="https://aws.amazon.com/lambda/" external=true}: managed MCP endpoints |
| Tool authentication | **IAM SigV4**: requests signed with AWS credentials |
| State limited to one session | **AgentCore Memory**: extracted records available across sessions |

Part 1 closes the first two gaps with a Gateway in front of two retrieval Lambdas, and Part 2 closes the third with AgentCore Memory.

:image[Module 4 architecture: a notebook agent uses AgentCore Memory and calls two Neo4j retrieval Lambdas through an IAM-authenticated Gateway]{src="../../images/03-agentcore-architecture.png" width=800}

---

## Part 1: Deploy the Gateway and Retrieval Lambdas

Open `notebooks/04-production-agent/4.1_agentcore_gateway.ipynb`.

:::alert{type="warning" header="These resources stay until you delete them"}
This part creates two Lambda functions:
`hotel-booking-search-hotel-knowledge` and `hotel-booking-graph-query`. It also
creates the AgentCore Gateway `hotel-booking-gateway` with one target per tool,
the Secrets Manager secret `neo4j-ws-retrieval`, and two IAM roles:
`workshop-hotel-lambda-role` and `workshop-hotel-gateway-role`.

The Gateway and secret incur charges while they exist. The Lambdas incur
charges per invocation. The notebook leaves these resources in place. Workshop
Studio removes them when the event ends. In your own account, delete them from
the console or CLI when you finish.
:::

Module 4 exposes two retrieval patterns through a managed endpoint:

| Gateway tool | Retriever | Question shape |
|---|---|---|
| `search_hotel_knowledge` | `HybridCypherRetriever` | Semantic: rooms, amenities, policies, services |
| `graph_query` | `Text2CypherRetriever` | Structured: counts, averages, filters, connected traversals |

Both tools import from `notebooks/workshop/hybrid_retrieval.py`. `search_hotel_knowledge` reuses the function called by Module 3.1. `graph_query` packages the Text2Cypher pattern demonstrated in Module 2.1 as a reusable function. Each Lambda handler unwraps the event and calls one of these functions.

Both interfaces are intended for retrieval. `search_hotel_knowledge` runs reviewed static Cypher. `graph_query` plans model-generated Cypher with `EXPLAIN` and executes it only when the planner reports a read-only query. The reservation command remains outside the Gateway.

AWS Secrets Manager provides the Neo4j connection to the Lambdas through
`neo4j-ws-retrieval`. The `workshop-hotel-lambda-role` execution role can read
that secret and invoke the required Bedrock models.

:::alert{type="info" header="Add production security controls"}
These Lambdas connect with ordinary workshop credentials. In production, connect with a **read-only Neo4j user** so the database rejects writes independently. Restrict the Lambda IAM role to the required secret and Bedrock models. `Text2CypherRetriever` first plans each statement with `EXPLAIN` and executes it only when the planner reports a read-only query. The notebook tests this application guard with a stub model that generates a write.
:::

After deployment, configure an MCP client to connect through
`mcp-proxy-for-aws`\:

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

The proxy signs every request with your AWS credentials. Strands passes the
resolved MCP tools to the agent through the same `tools` interface used for
local functions.

### Verify Successful and Empty Results

A grounded tool returns no evidence when the graph cannot answer a question.
A dead index, wrong index name, bad credential, or wrong database can produce
the same empty result.

The notebook therefore runs two checks for each tool. A **negative control**
confirms that a nonexistent hotel produces no match. A **positive control**
confirms that an existing hotel returns an exact address or guest rating. The
positive control verifies that retrieval can reach populated graph data.

---

## Part 2: Add AgentCore Memory

Open `notebooks/04-production-agent/4.2_agentcore_memory.ipynb`.

:::alert{type="warning" header="AWS resources created"}
This notebook creates one AgentCore Memory resource. The resource can incur charges until you delete it.
:::

**Session 1:** A guest provides a name, loyalty number, and room preference.

AgentCore extracts these records asynchronously. The notebook polls the service and shows the extracted records:

:::code{language=bash}
🧠 Preferences extracted (1 record(s)):
  • Prefers high floor, away from elevator

🧠 Facts extracted (2 record(s)):
  • Name is Alice Chen
  • Loyalty number LY-88421
:::

Extraction is LLM-driven, so the exact record count and wording can vary
between runs. The output above shows a typical result.

**Session 2:** The agent uses a new `session_id` and the same `actor_id`. It
recalls the room preference without receiving it again.

:::alert{type="info" header="Memory limitations"}
Extraction runs asynchronously. Recalled records do not link to their source
messages or related graph entities. Module 6 shows how graph-based memory
preserves those connections.
:::

## Next

Head to [Module 5](../05-agentcore-deploy/).
