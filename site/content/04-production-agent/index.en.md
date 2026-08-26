---
title: "Module 4: Production Agent with AgentCore"
weight: 50
---

Module 3 runs the retrieval tools inside the notebook process. Module 4 moves
them to AWS services.

The retrieval logic stays the same. `search_hotel_knowledge` runs the same
`HybridCypherRetriever` from Module 2 and returns the same eight keys. Two
things change: where the tool runs, and who is allowed to call it.

**What this module introduces**

| Order | Name | Type | What it contributes |
|-------|------|------|---------------------|
| 1 | Model Context Protocol | Open protocol | Lets an agent discover and call tools it was not built against |
| 2 | AWS Lambda | AWS service | Runs one retrieval function per tool |
| 3 | AgentCore Gateway | AWS service | Puts one MCP endpoint in front of several Lambda functions |
| 4 | Tool schema | Published contract | Gives the model the name, description, and input shape of each tool |
| 5 | IAM SigV4 | AWS request signing | Proves the caller's AWS identity on every tool call |
| 6 | AWS Secrets Manager | AWS service | Holds the Neo4j credential outside the deployment package |

Items 1 to 3 decide where the tool runs. Items 4 to 6 decide who may call it
and where the credential lives.

:image[Module 4 architecture: a Strands agent calls Neo4j retrieval Lambdas through an IAM-authenticated AgentCore Gateway]{src="../../images/03-agentcore-architecture.svg" width=800}

The diagram follows one request:

* **The agent:** The Strands agent runs in the notebook process and calls
  Claude on Amazon Bedrock.
* **The Gateway:** The agent's MCP tool call crosses into AWS and reaches the
  AgentCore Gateway. The Gateway checks the IAM SigV4 signature.
* **The Lambdas:** The Gateway invokes the Lambda that backs the requested
  tool, either `search_hotel_knowledge` or `graph_query`.
* **The secret:** Each Lambda reads its Neo4j credential from AWS Secrets
  Manager at cold start.
* **The database:** Each Lambda sends EXPLAIN-checked Cypher to Neo4j Aura.
  Aura sits outside the AWS Cloud boundary because it is a separately managed
  database.
* **The arrow colors:** The dashed blue arrow is the user talking to the agent.
  The orange arrows are the MCP call, the Lambda invocation, and the secret
  read. The solid blue arrow is the retrieval Cypher.

## 1. Model Context Protocol

MCP is a standard way for an agent to use tools that were built separately
from it. The client asks a server which tools exist, then asks it to run one.

[MCP](https://modelcontextprotocol.io/) defines two operations:

* **`tools/list`:** The client asks the server for every tool. Each tool comes
  back as a name, a description, and a JSON Schema for its input.
* **`tools/call`:** The client sends a tool name and an argument object. The
  server runs the tool and returns the result.

Strands calls these through `list_tools_sync()` and `call_tool_sync()`. The
Gateway answers them.

An MCP tool is three things: a name, an input schema, and something callable. A
local Python function with `@tool` is the same three things. The agent code at
the end of this module therefore looks almost identical to Module 3.

| Aspect | Module 3 local `@tool` | Module 4 Gateway MCP tool |
|---|---|---|
| Where the code runs | The notebook process | An AWS Lambda function |
| How the model learns the tool | Strands reads the function signature and docstring | The client calls `tools/list` |
| Where the description comes from | The Python docstring | The tool schema on the target |
| Who holds the Neo4j credential | The notebook process | The Lambda, from Secrets Manager |
| Who checks the caller | Nobody, the caller is the process itself | IAM checks the SigV4 signature |
| How a failure appears | A Python exception | A network error, an IAM denial, or a function error |
| What the agent passes to Strands | `tools=[search_hotel_knowledge_tool]` | `tools=gateway_mcp.list_tools_sync()` |

### Transport and Sessions

* **Transport:** MCP messages travel over standard input and output here. The
  client starts a local process and exchanges messages with it over pipes. That
  process is `mcp-proxy-for-aws`, covered in section 5.
* **Session:** Each `with gateway_client() as ...` block opens a session and
  closes it at the end of the block. The notebook opens one session for the
  direct tool checks and another for the agent. Sessions are cheap, so open a
  new one per task.

:::alert{type="info" header="Gateway tool names carry a prefix"}
The Gateway advertises each tool under a longer name that ends with the
registered tool name. Match a tool with `name.endswith(tool_name)`. An equality
check on the bare name finds nothing.
:::

## 2. AWS Lambda as the Tool Host

Lambda runs one Python handler per tool. Each handler does three things: read
the event, call a retrieval function, and return JSON.

:::code{language=python showCopyAction=true}
from workshop.hybrid_retrieval import search_hotel_knowledge


def handler(event, context):
    """Return grounded hotel context for the Gateway's ``query`` input."""
    del context
    query = (event or {}).get("query")
    if not isinstance(query, str) or not query:
        return {"error": "query must be a non-empty string"}
    try:
        return {"context": search_hotel_knowledge(query)}
    except ValueError as error:
        return {"error": str(error)}
:::

A Lambda function does not speak MCP. An MCP client cannot discover it. Section
3 closes that gap.

### Cold Starts

Lambda reuses a function's process for calls that arrive close together and
shuts the process down when it goes idle. The first call into a new process is
a **cold start**. A cold start runs every import and opens every connection
the function needs before it can answer.

Two settings in the notebook exist because of cold starts:

* **`LAMBDA_MEMORY_MB = 1024`:** Lambda gives a function more CPU at higher
  memory settings. The extra CPU shortens the import of the Neo4j driver and
  the retriever library.
* **`LAMBDA_TIMEOUT_SECONDS = 120`:** A `graph_query` call makes a Bedrock call
  to generate Cypher, runs `EXPLAIN`, and then runs the query. The default
  three-second timeout is too short for that.

The Neo4j credential is also read at cold start. Section 6 explains that
choice.

### Packaging a Retrieval Function for Lambda

The deployment zip must hold wheels that run on Lambda, not wheels that run on
the machine that built the zip. `build_lambda_zips` handles four problems:

* **Platform wheels:** Lambda runs Amazon Linux on `arm64` here. The build
  passes `--python-platform aarch64-manylinux2014` and `--only-binary :all:`,
  so the wheels match the runtime even when the notebook runs on macOS.
* **`--no-deps` for the shared package:** The `workshop` package declares
  dependencies for every module in the workshop, including the Strands agent.
  `--no-deps` keeps those out of a zip that only needs retrieval.
* **Packages left out of the requirements:** Lambda already ships `boto3`, so
  adding it only grows the zip. The requirements also skip `neo4j-rust-ext`, an
  optional native driver accelerator. It would add a compiled artifact to a
  package that is otherwise pure Python wheels.
* **Packages stripped from the zip:** `neo4j-graphrag` pulls in `numpy` and
  `scipy` for its extraction pipeline and its sentence-transformers embedder.
  This search path uses neither, so the zip step removes them.

Removing `numpy` and `scipy` keeps the archive under Lambda's 50 MB
direct-upload limit. This module therefore needs no S3 staging bucket.

Both functions use the same dependencies and differ only in their entry point.
The platform install therefore runs once, and each zip adds its own
`lambda_function.py` at the archive root.

:::alert{type="warning" header="Packaging errors appear at invocation, not deployment"}
A missing dependency does not fail the deploy. `create_function` accepts any
zip. The import error appears the first time the function runs. Step 5 of the
notebook invokes both functions directly to catch this before the Gateway is
involved.
:::

## 3. AgentCore Gateway and Its Targets

AgentCore Gateway puts one MCP endpoint in front of several backends. Two
terms matter here:

* **Gateway:** The Gateway is the MCP server. It owns the URL, the protocol,
  and the authorizer that checks every caller.
* **Target:** A target is one backend registered with the Gateway. Each target
  names a Lambda function and the tool schema to advertise for it. The Gateway
  turns a matching `tools/call` into an invocation of that function.

Two settings define what the Gateway is:

:::code{language=python showCopyAction=true}
gateway = control_client.create_gateway(
    name=GATEWAY_NAME,
    roleArn=gateway_role_arn,
    protocolType="MCP",
    authorizerType="AWS_IAM",
)
:::

* **`protocolType="MCP"`:** This makes the endpoint an MCP server.
* **`authorizerType="AWS_IAM"`:** This selects SigV4 for inbound
  authentication. Callers present AWS identities instead of an API key.

Registering a target names the function and supplies its schema inline:

:::code{language=python showCopyAction=true}
target_config = {
    "mcp": {
        "lambda": {
            "lambdaArn": f"arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{function_name}",
            "toolSchema": {"inlinePayload": [tool]},
        }
    }
}
:::

Targets make Lambda functions discoverable as tools. To add a tool,
register another target. The agent, the client, and the endpoint URL stay the
same.

Wait for status before using either resource. Targets can only be added after
the Gateway leaves `CREATING`. Open an MCP session only after every target
reports `READY`. A session opened early lists an incomplete tool set instead of
failing, so the notebook polls for both.

## 4. The Tool Schema as a Published Contract

The tool schemas live in
`notebooks/04-production-agent/tool_schemas/tools.json`. They are committed to
the repository instead of built at deploy time, so the Gateway advertises the
same contract on every rerun and in every environment.

:::code{language=json}
{
  "name": "search_hotel_knowledge",
  "description": "Search grounded hotel documents and enrich the matching chunks with reviewed Neo4j hotel facts. Use for semantic questions about a hotel's rooms, amenities, policies, and services. Does not provide live inventory or guaranteed availability, and never writes.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "minLength": 1,
        "description": "Natural-language hotel question."
      }
    },
    "required": ["query"],
    "additionalProperties": false
  }
}
:::

* **The description is model input:** The model reads it to decide between
  `search_hotel_knowledge` and `graph_query`. It replaces the docstring that
  Module 3's `@tool` exposed.
* **What to put in a description:** State what the tool is for, what question
  shape it suits, and what it will not do.

### The Gateway Reads a Subset of JSON Schema

* **Keys AgentCore reads:** It reads `type`, `description`, and `items` for
  each property.
* **Keys AgentCore ignores:** It ignores `minLength`, `format`, and
  `additionalProperties`.

The notebook projects the committed schema down to the keys the Gateway uses:

:::code{language=python showCopyAction=true}
GATEWAY_PROPERTY_KEYS = {"type", "description", "items"}


def gateway_input_schema(schema: dict) -> dict:
    return {
        "type": schema["type"],
        "properties": {
            name: {k: v for k, v in definition.items() if k in GATEWAY_PROPERTY_KEYS}
            for name, definition in schema["properties"].items()
        },
        "required": schema["required"],
    }
:::

The committed schema keeps the stricter keys because the local tools validate
against it. The Gateway receives the projection.

Validate inputs in the handler. The Gateway drops `minLength`, so nothing else
enforces it. That is why the handler checks that `query` is a non-empty
string.

A target description is capped at 200 characters. The tool descriptions are
longer on purpose. The notebook gives the target the opening sentence and gives
the tool the full text, so the cap trims the operator-facing label instead of
the text the model reads.

## 5. IAM SigV4 and the MCP Proxy

Two pieces work together on each tool call:

* **IAM Signature Version 4:** SigV4 is the AWS request-signing scheme. The
  caller signs each request with its AWS credentials. The Gateway checks that
  signature against IAM to confirm who is calling. No API key exists to
  distribute or rotate.
* **`mcp-proxy-for-aws`:** MCP's standard input and output transport talks to a
  local process, and the Gateway is an HTTPS endpoint that expects a signature.
  The proxy bridges the two. It reads MCP messages on standard input, signs
  them with SigV4, and forwards them to the Gateway URL.

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

The proxy receives a copy of the environment, so it finds the AWS credentials
the notebook already uses. The Gateway sees that identity, and IAM permissions
apply to it.

## 6. Secrets Manager and the Two Execution Roles

The notebook stores four Neo4j values in the secret `neo4j-ws-retrieval`: the
URI, username, password, and database name. Each Lambda reads the secret at
cold start through `Neo4jConfig.from_secret`.

Reading it at cold start gives two benefits:

* **The credential stays out of the code:** It is absent from the deployment
  package and from the environment variables shown in the console.
* **Rotation needs no rebuild:** The next cold start reads the updated secret.

Two roles carry the deployment. Neither one can do the other's job:

| Role | Assumed by | What it allows |
|---|---|---|
| `workshop-hotel-lambda-role` | `lambda.amazonaws.com` | Write CloudWatch Logs, read that one secret, and invoke the embedding and chat models |
| `workshop-hotel-gateway-role` | `bedrock-agentcore.amazonaws.com` | Invoke functions named `hotel-booking-*` |

The split is why the caller never holds the Neo4j credential:

1. The caller proves its identity to the Gateway.
2. The Gateway assumes its own role to invoke the Lambda.
3. The Lambda assumes its own role to read the secret.

The credential exists only inside step 3. No policy in the chain grants a
write.

Expect a delay on new roles. IAM is eventually consistent, so a role can be
rejected for a few seconds after it exists. The notebook retries that specific
failure instead of stopping.

## The Two Retrieval Tools

| Gateway tool | How it works | Use it for |
|---|---|---|
| `search_hotel_knowledge` | Runs `HybridCypherRetriever` with the fixed `retrieval_query` selected in Module 2 | Rooms, amenities, policies, services, and other semantic questions |
| `graph_query` | Uses `Text2CypherRetriever` to generate a query, checks it with `EXPLAIN`, and runs it only when Neo4j reports a read-only plan | Counts, averages, filters, and varied graph traversals |

Both tools import their retrieval functions from
`notebooks/workshop/hybrid_retrieval.py`. The first Lambda reuses the function
Module 3 calls. The second turns the Module 2 Text2Cypher pattern into a
reusable function.

`graph_query` exists because counts and averages need the whole matching set. A
top-k retriever returns the five best chunks. A question such as "what is the
average guest rating" needs the database to calculate over every matching row.

The reservation command stays outside this Gateway. These two tools only read.

## Telling an Empty Result from a Failure

An empty result has two possible causes. Neo4j may hold no matching hotel, or
the retrieval path may be broken. A dead index, a wrong index name, a bad
credential, or the wrong database all return the same empty shape.

The notebook runs two controls for each tool:

* **Negative control:** Ask about a hotel that does not exist. Expect no
  match.
* **Positive control:** Ask about a hotel that does exist. Expect its exact
  address or guest rating.

Together they separate the two causes. The negative control checks
empty-result behavior. The positive control proves the tool reaches the
populated database. Both import their expected values from
`workshop.fixtures`, so the tests and the readiness check compare against the
same hotel.

The notebook runs this pair twice:

* **Step 5, direct invocation:** These calls prove each Lambda reaches the
  graph.
* **Step 7, through the Gateway:** These calls prove the Gateway invokes the
  Lambda and returns the same values.

Running the two steps separately shows which layer failed.

## Guarding Model-Generated Cypher

`graph_query` sends model-generated Cypher to the database. Test the guard
rather than assume it. `Text2CypherRetriever` plans each statement with
`EXPLAIN` and runs it only when the planner reports a read-only query.

The configured model follows its prompt and generates read queries, so it
never triggers the guard. The notebook substitutes a stub model that always
returns a write:

:::code{language=python showCopyAction=true}
# A label no build ever creates, so this statement is a no-op even if it runs.
WRITE_CYPHER = "MATCH (n:__WorkshopGuardProbe) SET n.tampered = true RETURN count(n) AS n"


class WriteAttemptLLM(LLMInterface):
    """Stands in for a model that has been talked into generating a write."""

    def invoke(self, input, message_history=None, system_instruction=None):
        return LLMResponse(content=WRITE_CYPHER)
:::

The statement targets a label that no build creates, so the data stays safe
even if the guard fails. The test then asserts that the call raises before
execution.

:::alert{type="info" header="Add production security controls"}
These Lambdas connect with ordinary workshop credentials. In production,
connect with a **read-only Neo4j user** so the database rejects every write.
Restrict the Lambda IAM role to the required secret and Bedrock models. The
`EXPLAIN` check is an application control. A read-only database user is a
separate boundary underneath it.
:::

## The Strands Agent over Gateway Tools

The notebook passes the listed Gateway tools to a Strands agent. The model
picks a remote tool, answers from the returned context, and records the
selected tool in the trace. This is the same model and tool loop as Module 3,
with Lambda and Gateway replacing local Python calls.

One line changes. `tools=agent_mcp.list_tools_sync()` replaces
`tools=[search_hotel_knowledge_tool]`. Strands sees a name, a JSON schema, and
a callable operation in both cases.

## Where Each Piece Runs

| Stage | Where the tool runs | Who checks the caller | Who holds the Neo4j credential |
|---|---|---|---|
| Module 3 | The notebook process | Nobody | The notebook process |
| Module 4 | An AWS Lambda function | IAM, through Gateway SigV4 | The Lambda, from Secrets Manager |
| Module 5 | An AgentCore Runtime container | IAM, on `InvokeAgentRuntime` | The container |

Module 4 and Module 5 are two separate patterns, not two steps of one path.
Module 4 keeps the agent local and moves the tools out. Module 5 packages the
agent itself and connects it to Neo4j from inside the container.

## Run It

Open `notebooks/04-production-agent/4.1_agentcore_gateway.ipynb` and run the
cells in order. The notebook stores the secret, builds and deploys both Lambda
functions, tests them directly, creates the Gateway and its targets, repeats
the tests over MCP, and then hands the tools to an agent.

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

Module 5 packages a separate version of the agent for AgentCore Runtime. Module
6 adds cross-session memory by storing each preference in Neo4j and linking it
to its source message and hotel.

Slides for this module\: [MCP and AgentCore Gateway](../slides/overview-mcp-gateway/)

## Next

Head to [Module 5](../05-agentcore-deploy/).
