---
title: "Module 4: Production Agent with AgentCore"
weight: 50
---

Module 3's tools run as Python functions inside the notebook process, where
the model calls a local function that already holds an open Neo4j driver
session. Module 4 moves those retrieval tools to AWS-managed services instead,
so a caller can reach them over a network with its identity checked on every
call, never holding the Neo4j credentials itself. AWS Lambda runs each tool,
and Bedrock AgentCore Gateway presents both tools through one managed Model
Context Protocol endpoint. IAM Signature Version 4 authenticates each request
with the caller's AWS identity.

**What this module introduces**

* **Model Context Protocol, or MCP:** A standard interface for listing and
  calling tools from an AI application. Because Strands and the Gateway both
  speak MCP, the agent can discover and call the Lambda-backed tools without
  any tool-specific integration code.
* **AWS Lambda:** Runs one Python handler for each retrieval tool. On its own,
  a Lambda function only exposes an AWS API for invoking that code directly;
  it does not speak MCP.
* **AgentCore Gateway:** Publishes one MCP endpoint that lists every
  registered Lambda's tool name and input schema, and translates each MCP
  tool call into the matching Lambda invocation. This is what turns a set of
  Lambda functions into tools an MCP client can discover and call.
* **IAM SigV4:** AWS's request-signing scheme. The caller signs each request
  with its AWS credentials, and the Gateway verifies that signature against
  IAM to confirm the caller's identity, so no separate API key is required.
* **AWS Secrets Manager:** Stores the Neo4j connection outside the Lambda
  package and limits access through IAM, so the credential is not baked into
  deployed code.

:image[Module 4 architecture: a Strands agent calls Neo4j retrieval Lambdas through an IAM-authenticated AgentCore Gateway]{src="../../images/03-agentcore-architecture.svg" width=800}

The diagram traces one request through the deployed system. On the left, a
user's question reaches the Strands agent, which runs in the notebook process
on Claude via Amazon Bedrock. The agent's MCP tool call crosses into the AWS
Cloud boundary to the AgentCore Gateway, shown as the MCP server that
authenticates each call with IAM SigV4. The Gateway invokes whichever Lambda
backs the requested tool, `search_hotel_knowledge` or `graph_query`. Each
Lambda reads its Neo4j credential from AWS Secrets Manager at cold start, then
sends EXPLAIN-checked Cypher to Neo4j Aura, which sits outside the AWS Cloud
boundary because it is a separately managed database. The arrow colors mark
three kinds of traffic: the dashed blue arrow is the user's interaction with
the agent, the orange arrows are the MCP call, the Lambda invocation, and the
secret read, and the solid blue arrow is the retrieval Cypher that reaches
Neo4j.

## The Managed Tool Flow

The Gateway publishes two registered Lambda targets through one MCP endpoint.
An MCP client first lists the tool names and input schemas. The agent can then
select a tool, send its arguments to the Gateway, and receive the Lambda result
through the same protocol.

This design changes where the tools run while preserving their interface.
Strands sees both a local `@tool` function and a remote MCP tool as a name, a
JSON schema, and a callable operation. The agent code can therefore use the
remote tools through its existing `tools` parameter.

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

The two tools use different retrieval strategies:

| Gateway tool | How it works | Use it for |
|---|---|---|
| `search_hotel_knowledge` | Runs `HybridCypherRetriever` with the fixed `retrieval_query` selected in Module 2 | Rooms, amenities, policies, services, and other semantic questions |
| `graph_query` | Uses `Text2CypherRetriever` to generate a query, checks it with `EXPLAIN`, and runs it only when Neo4j reports a read-only plan | Counts, averages, filters, and varied graph traversals |

Both tools import their retrieval functions from
`notebooks/workshop/hybrid_retrieval.py`. The first Lambda reuses the function
called by Module 3. The second packages the Text2Cypher pattern from Module 2 as
a reusable function. Each handler reads the Gateway event, extracts the query,
and calls its matching function.

The reservation command stays outside this Gateway because these two tools
only retrieve data. In production, use a read-only Neo4j user for both Lambdas.
The database will then reject a write even if an application check misses it.

## Connection and Access Controls

The notebook stores four Neo4j connection values in
`neo4j-ws-retrieval`: the URI, username, password, and database name. Each
Lambda reads the secret during a cold start, which keeps credentials out of the
deployment package and lets a new cold start read an updated secret without a
code rebuild.

The `workshop-hotel-lambda-role` grants the Lambdas permission to read that one
secret and call the required Bedrock models. Restricting the role reduces the
resources that a faulty or compromised function can access.

:::alert{type="info" header="Add production security controls"}
These Lambdas connect with ordinary workshop credentials. In production,
connect with a **read-only Neo4j user** so the database rejects every write.
Restrict the Lambda IAM role to the required secret and Bedrock models.
`Text2CypherRetriever` also plans each statement with `EXPLAIN` and executes it
only when the planner reports a read-only query. The notebook verifies this
application guard with a stub model that generates a write.
:::

## Connect Through IAM-Authenticated MCP

The Strands MCP client communicates with a local process through standard input
and output. The `mcp-proxy-for-aws` process receives those MCP messages, sends
them to the Gateway over HTTPS, and adds an IAM SigV4 signature. The signature
binds the request to the caller's AWS credentials, so the Gateway can verify
the caller before it invokes a Lambda.

Configure the client with the proxy:

:::code{language=python showCopyAction=true}
gateway_mcp = MCPClient(
    lambda: stdio_client(StdioServerParameters(
        command="uvx",
        args=["mcp-proxy-for-aws@latest", GATEWAY_URL, "--region", "us-east-1"],
        env=os.environ.copy(),
    ))
)
with gateway_mcp:
    agent = Agent(tools=gateway_mcp.list_tools_sync(), ...)
:::

Authentication comes from the AWS credentials already available to the
notebook process. The proxy signs the request, and Gateway applies IAM
permissions to the caller's identity.

## Telling an Empty Result from a Failure

A valid search can return no context when Neo4j has no matching hotel. An
unavailable index, an incorrect index name, invalid credentials, or the wrong
database can produce the same empty shape, so one empty response proves little
by itself.

The notebook runs two controls for each tool:

* **Negative control:** A nonexistent hotel returns no match.
* **Positive control:** An existing hotel returns its exact address or guest
  rating.

Together, these checks separate expected empty context from a broken retrieval
path. The negative control checks empty-result behavior, while the positive
control proves that the tool can reach the populated Neo4j database.

## The Strands Agent over Gateway Tools

After the direct MCP checks, the notebook passes the listed Gateway tools to a
Strands agent. The model selects a remote tool, uses its returned context in the
answer, and records the selected tool in the trace. This is the same model and
tool loop used in Module 3, with Lambda and Gateway replacing local Python
calls.

Module 5 packages a separate version of the agent for AgentCore Runtime. Module
6 adds cross-session memory by storing each preference in Neo4j and linking it
to its source message and hotel.

## Next

Head to [Module 5](../05-agentcore-deploy/).
