---
marp: true
theme: default
paginate: true
---

<style>
section {
  --marp-auto-scaling-code: false;
}

li {
  opacity: 1 !important;
  animation: none !important;
  visibility: visible !important;
}

/* Disable all fragment animations */
.marp-fragment {
  opacity: 1 !important;
  visibility: visible !important;
}

ul > li,
ol > li {
  opacity: 1 !important;
}
</style>

# MCP and AgentCore Gateway

The tools leave the notebook. The agent stays.

<!--
The hinge is slide 9, testing the guard on model-generated Cypher, because
deck 5 introduced that guard and this is the first place the workshop proves
it holds.

The framing to hold onto all deck: the retrieval logic does not change. The
same hybrid_retrieval.py that ran in Module 3 runs inside these Lambdas. What
changes is where it executes and who is allowed to invoke it.

Modules 4 and 5 are two patterns, not two steps. Say that at the start and
again at the end.
-->

---

## Model Context Protocol

The retriever, the driver, and the tool all live inside your notebook process.
That works on a laptop and nowhere else.

MCP is one standard, so an agent can use tools it was never built against.

- **`tools/list`:** the client asks what exists. Each tool comes back as a name, a description, and a JSON Schema for its input
- **`tools/call`:** the client sends a tool name and arguments. The server runs it and returns the result

Strands calls these as `list_tools_sync()` and `call_tool_sync()`. The Gateway answers them.

An MCP tool is three things: a name, an input schema, and something callable.

<!--
Name the three problems with the notebook process without dwelling: the
credential is in the process, nothing checks who is calling, and the only way
to share the tool is to share the notebook.

The last line is the one that makes MCP feel small rather than mysterious. A
local Python function decorated with @tool is exactly those same three things.
That is why the agent code at the end of this module looks almost identical to
Module 3's.

Do not detour into the rest of the MCP specification. Two operations is all
this workshop uses.
-->

---

<style scoped>
/* Five rows of two-column prose. */
section { font-size: 24px; }
</style>

## What Moves and What Does Not

| Aspect | Module 3, local `@tool` | Module 4, Gateway MCP tool |
|---|---|---|
| Where the code runs | The notebook process | An AWS Lambda function |
| How the model learns the tool | Strands reads the signature and the docstring | The client calls `tools/list` |
| Who holds the Neo4j credential | The notebook process | The Lambda, from Secrets Manager |
| Who checks the caller | Nobody. The caller is the process | IAM checks the SigV4 signature |
| What the agent passes to Strands | `tools=[search_hotel_knowledge_tool]` | `tools=gateway_mcp.list_tools_sync()` |

The agent stays local. The tools go remote.

<!--
Row four is the one that matters. In Module 3 there is no caller to check,
because the caller and the tool are the same process. The moment the tool moves
out, "who is allowed to call this" becomes a real question, and IAM answers it.

Row five is the whole code diff. One line.
-->

---

![bg contain](../images/03-agentcore-architecture.svg)

<!--
Follow one request across the diagram.

The agent runs in the notebook and calls Claude on Bedrock. Its MCP tool call
crosses into AWS and reaches the Gateway, which checks the SigV4 signature. The
Gateway invokes the Lambda backing that tool. The Lambda read its Neo4j
credential from Secrets Manager at cold start. It sends EXPLAIN-checked Cypher
to Aura.

Note where Aura sits: outside the AWS Cloud boundary, because it is a
separately managed database. Slide 11 comes back to that.

Arrow colors: dashed blue is the user talking to the agent, orange is the MCP
call plus the Lambda invocation plus the secret read, solid blue is the
retrieval Cypher.
-->

---

## AgentCore Gateway

One managed MCP endpoint in front of several backends.

- **Gateway:** the MCP server. It owns the URL, the protocol, and the authorizer
- **Target:** one registered backend. It names a Lambda and the tool schema to advertise for it

```python
gateway = control_client.create_gateway(
    name=GATEWAY_NAME, roleArn=gateway_role_arn,
    protocolType="MCP", authorizerType="AWS_IAM",
)
```

Adding a tool means registering another target. The agent, the client, and the URL do not change.

<!--
Two settings define what this is. protocolType="MCP" makes the endpoint an MCP
server. authorizerType="AWS_IAM" selects SigV4, so callers present AWS
identities and there is no API key to distribute or rotate.

One operational note that costs people time: wait for status. Targets can only
be added once the Gateway leaves CREATING, and a session opened before every
target reports READY lists an incomplete tool set rather than failing. The
notebook polls for both.

Also flag the name prefix. The Gateway advertises each tool under a longer name
that ends with the registered one, so match with endswith. An equality check on
the bare name finds nothing.
-->

---

## The Two Tools

| Tool | How it works | For |
|---|---|---|
| `search_hotel_knowledge` | The fixed `HybridCypherRetriever` from Module 2 | Rooms, amenities, policies, services |
| `graph_query` | `Text2CypherRetriever`, `EXPLAIN`-checked, read plans only | Counts, averages, filters, varied traversals |

A top-k retriever returns the five best chunks. "What is the average guest rating" needs every matching row, so `graph_query` exists.

Each tool is one Lambda function and one Gateway target.

The reservation command stays outside this Gateway. Both tools only read.

<!--
This is the second tool the workshop adds, and deck 5 flagged that Text2Cypher
would arrive here behind the same EXPLAIN guard. Slide 9 is that guard.

Both tools import from the same hybrid_retrieval.py. The first reuses the exact
function Module 3 called. The second turns Module 2's Text2Cypher pattern into
a reusable function.

The last line is deliberate and worth saying out loud. Nothing about moving
tools to a Gateway changed the rule that the model does not write.
-->

---

## The Tool Schema Is the Contract

The schema is committed to the repository, not built at deploy time, so the Gateway advertises the same contract every run.

- **The description is model input.** It replaces Module 3's docstring. The model reads it to choose between the two tools
- **What to write:** State what the tool is for, what question shape it suits, and what it will not do
- **The Gateway reads a subset of JSON Schema.** It keeps `type`, `description`, and `items` on each property
- **The Gateway ignores the stricter keys.** It drops `minLength`, `format`, and `additionalProperties`

Validate in the handler. The Gateway drops the constraint, so nothing else enforces it.

<!--
The subset behaviour is the practical trap. The committed schema keeps the
stricter keys because the local tools validate against them, and the notebook
projects the schema down to the keys the Gateway actually reads. If you assume
minLength is enforced, an empty query string reaches your handler.

One more cap worth knowing: a target description is limited to 200 characters.
The notebook gives the target the opening sentence and gives the tool the full
text, so the cap trims the operator-facing label rather than the text the model
reads.
-->

---

## Text2Cypher Needs a Guard

Model-generated Cypher reaches the database. Test the guard rather than assume it.

```python
# A label no build ever creates, so this statement is a no-op even if it runs.
WRITE_CYPHER = "MATCH (n:__WorkshopGuardProbe) SET n.tampered = true RETURN count(n) AS n"
```

- **The real model** follows its prompt and generates reads, so it never trips the guard
- **A stub model** always returns a write. The test asserts the call raises before execution
- **The probe targets a label no build creates**, so the data is safe even if the guard fails

Two layers run here. The prompt asks and `EXPLAIN` verifies. A read-only database user is the third layer, and production needs it.

<!--
The hinge of this deck, and the discipline worth stealing regardless of stack.

A guard that has never been triggered is a guard you are assuming works. The
only way to know is to feed it the input it exists to reject, which means
building a component whose job is to misbehave.

Note the layering. EXPLAIN is an application control and it sits in the same
process as the code that could have a bug. A read-only Neo4j user is a separate
boundary the application cannot talk its way past, and production should have
both. These Lambdas connect with ordinary workshop credentials, which is a
workshop simplification, not a recommendation.
-->

---

<style scoped>
/* A code block, four bullets, and a closing line overflow at the theme's 29px. */
section { font-size: 24px; }
</style>

## Identity, SigV4 All the Way Down

```python
gateway_mcp = MCPClient(lambda: stdio_client(StdioServerParameters(
    command="uvx",
    args=["mcp-proxy-for-aws@latest", GATEWAY_URL, "--region", REGION],
    env=os.environ.copy(),
)))
```

- **`mcp-proxy-for-aws`** bridges MCP's standard input and output transport to a signed HTTPS request
- **The caller** proves its identity to the Gateway with SigV4
- **`workshop-hotel-gateway-role`** lets the Gateway invoke functions named `hotel-booking-*`
- **`workshop-hotel-lambda-role`** lets the Lambda read one secret and invoke the embedding model and the chat model

The credential reaches only the Lambda. No policy in the chain grants a write.

<!--
Walk the chain as three hops with three different identities. The caller never
holds the Neo4j credential, and that is a property of the role split rather
than of anyone being careful.

The proxy gets a copy of the environment, so it finds the AWS credentials the
notebook is already using. The Gateway sees that identity and IAM permissions
apply to it.

One operational note: IAM is eventually consistent, so a freshly created role
can be rejected for a few seconds after it exists. The notebook retries that
specific failure rather than stopping.
-->

---

## Neo4j Sits Outside the AWS Boundary

Aura is a separately managed database. The trust boundary does not stop at the VPC edge.

- **IAM controls** who invokes the Gateway and who invokes the Lambda
- **The Lambda role controls** which identity can read the Neo4j credential from Secrets Manager
- **Neo4j controls** what that credential is allowed to do

A read-only Neo4j user is the control IAM cannot provide.

<!--
Be honest about this rather than drawing a box around everything and calling it
secured. The diagram deliberately puts Aura outside the AWS Cloud boundary.

The reason it matters: every AWS control in this module governs invocation. Not
one of them governs what the Cypher does once the Lambda holds a connection.
That control lives in the database, and it is a separate thing to configure.
-->

---

## Negative and Positive Controls

An empty result has two possible causes. Neo4j holds no matching hotel, or the retrieval path is broken.

- **Negative control:** ask about a hotel that does not exist. Expect no match
- **Positive control:** ask about a hotel that does exist. Expect its exact address or guest rating

Both import their expected values from `workshop.fixtures`.

The notebook runs both controls directly against each Lambda, then repeats the positive controls through the Gateway.

<!--
A dead index, a wrong index name, a bad credential, and the wrong database all
return the same empty shape as a genuine miss. One test cannot tell them apart.
Two can.

Running the pair at both layers is what makes a failure diagnosable. Direct
invocation proves the Lambda reaches the graph. Through the Gateway proves the
Gateway invokes the Lambda and returns the same values. If the first passes and
the second fails, you know exactly which layer to look at.

Related trap worth naming: packaging errors appear at invocation, not at
deployment. create_function accepts any zip, and a missing dependency shows up
the first time the function runs.
-->

---

## The Same Agent, Remote Tools

```python
agent = Agent(tools=gateway_mcp.list_tools_sync(), ...)
```

One line changes from Module 3. Strands sees a name, a JSON schema, and a callable operation in both cases.

> Which Chicago hotel has both a spa and a swimming pool, what is its cancellation policy, and can I hold it for four guests?

Same question, same answer. The tool now runs in Lambda.

<!--
This is the payoff, and it is deliberately anticlimactic. Everything hard in
this module was deployment and identity. The agent code barely moved.

That is the point of a protocol. The agent does not know or care that its tool
is now a Lambda behind a signed HTTPS endpoint.

Run the hero question here if you are demonstrating live. The model picks a
remote tool, answers from the returned context, and records the tool it chose
in the trace, which is the thing worth showing.
-->

---

<style scoped>
/* Three rows of three-column prose plus framing. */
section { font-size: 25px; }
</style>

## Two Paths to the Same Shape

| Stage | Where the tool runs | Who checks the caller | Who holds the credential |
|---|---|---|---|
| **Module 3** | The notebook process | Nobody | The notebook process |
| **Module 4** | An AWS Lambda | IAM, through Gateway SigV4 | The Lambda, from Secrets Manager |
| **Module 5** | An AgentCore Runtime container | IAM, on `InvokeAgentRuntime` | The container |

Module 4 keeps the agent local and moves the tools out. Module 5 packages the agent itself.

<!--
Close by repeating the framing from the opening. These are two patterns, not
two steps, and the next deck is not a continuation of this one.

Choose Gateway when several agents share one set of tools, or when the tools
belong to a different team than the agent. Choose Runtime when the whole agent
is the unit you want to deploy and invoke.

The resources created here stay until they are deleted: two Lambdas named
hotel-booking-*, the Gateway with one target per tool, the secret, and two IAM
roles. Workshop Studio cleans them up at the end of a hosted event. In your own
account, delete them yourself.
-->
