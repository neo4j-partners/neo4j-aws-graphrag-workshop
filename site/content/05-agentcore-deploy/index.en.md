---
title: "Module 5: Deploy to AgentCore Runtime"
weight: 60
---

Module 5 moves the grounded booking agent from JupyterLab to a managed
container. Amazon Bedrock AgentCore Runtime starts the container and gives
authorized AWS clients an API for invoking the agent.

**What this module deploys**

* **AgentCore Runtime:** Runs the packaged agent outside the notebook.
* **Deployment package:** Reuses the Module 3 retrieval code, system prompt,
  and reservation command.
* **Request handling:** Reads the prompt and request ID, then returns the model
  response and structured tool results.
* **Warm resources:** Reuses Neo4j drivers and the retriever while the container
  stays warm.
* **Invocation API:** Lets authorized clients invoke the deployed agent through
  `InvokeAgentRuntime`.

The deployment changes where the agent runs and where its credentials live:

| Module 3.1 | Module 5.1 |
|---|---|
| Runs in your kernel | Runs in a container AgentCore starts |
| The notebook environment holds the Neo4j password | The Runtime holds it, injected at launch |
| Reachable only from Jupyter | Invoked through `InvokeAgentRuntime` by authorized AWS clients |
| Session is your kernel's memory | Each invocation uses a caller-provided session ID |

The deployed agent keeps the same retrieval and reservation behavior. Runtime
request handling only changes how a caller sends a request and receives a
result.

Module 3.1 gives the agent one retrieval tool and calls the reservation command
as a local Python operation in the write examples. Module 5 exposes both
operations as tools. The system prompt requires the agent to state when Neo4j
lacks the required context.

## What AgentCore Runtime Provides

Amazon Bedrock AgentCore is a set of managed services for running agents in
production. Module 4 used **Gateway** to turn Lambda functions into tools. This
module uses **Runtime** to host the agent.

Runtime runs the container and handles the operations work around it.

* **Session isolation:** Each session gets its own microVM with its own CPU,
  memory, and file system. One caller's session stays private from every other
  caller.
* **Session lifetime:** A session ends after 15 idle minutes or 8 total hours.
  AgentCore then deletes the microVM and wipes its memory.
* **Session context:** Invocations that share a session ID reach the same
  container. Step 6 gives each smoke test its own session ID, so each test
  starts clean.
* **Scaling:** AWS starts and stops containers as traffic changes. AWS also
  picks the instance size and patches the hosts.
* **Invocation API:** Clients call `InvokeAgentRuntime` with the Runtime ARN, a
  session ID, and a JSON payload. AWS supplies the endpoint.
* **Access control:** IAM decides who may invoke this deployment. Runtime also
  accepts OAuth 2.0 bearer tokens from a provider such as Amazon Cognito, Okta,
  or Microsoft Entra ID.
* **Versions and endpoints:** Creating the Runtime creates version 1 and a
  `DEFAULT` endpoint. Each update creates a new version, and `DEFAULT` moves to
  it. Rerunning the notebook therefore ships a new version behind the same ARN.
* **Protocols:** This agent speaks HTTP. Runtime hosts MCP servers and A2A
  agents from the same kind of container.
* **Long requests and streaming:** One invocation can run up to 8 hours. An
  agent can stream partial output over server-sent events or a WebSocket. This
  agent returns one JSON result instead.

### The Container Contract

Runtime talks to the container over HTTP. The image has to meet a fixed
contract, and the `bedrock-agentcore` SDK implements most of it.

* **Port 8080 on `0.0.0.0`:** Runtime posts every request to `/invocations` on
  that port.
* **`linux/arm64`:** Runtime runs ARM64 images. Step 4 builds for that platform
  in CodeBuild.
* **`BedrockAgentCoreApp`:** `booking_agent.py` creates this object at module
  level. It serves the HTTP contract, so the agent code skips routing code.
* **`@app.entrypoint`:** Marks the one function Runtime calls per invocation.
  The function receives the payload as a dictionary and returns a dictionary.
  Runtime passes that dictionary back to the caller as JSON.
* **`app.run()`:** The container's start command runs the module, and
  `app.run()` serves port 8080. The same line runs the agent locally before you
  deploy it.

The deployed agent keeps that shape:

:::code{language=python}
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload, context=None):
    prompt, request_id = _prompt(payload)
    ...
    return {
        "response": str(result),
        "request_id": request_id,
        "tools_used": tools_used,
        "grounding_result": grounding_recorder.last_result,
        "command_result": command_result,
    }

if __name__ == "__main__":
    app.run()
:::

### What Runtime Observes

AgentCore emits telemetry in OpenTelemetry format and stores it in Amazon
CloudWatch. The container starts under `opentelemetry-instrument`, which adds
the instrumentation for you.

* **Metrics, on by default:** Invocations, session count, active sessions,
  latency, throttles, user errors, and system errors.
* **Traces and spans:** A span records one step of the agent loop, such as a
  model call or a tool call, with its timing. Enable CloudWatch Transaction
  Search once per account to view them.
* **Logs:** Application log lines land in the Runtime log group. The **Read the
  Runtime Logs** section below reads them with boto3.
* **GenAI observability dashboard:** CloudWatch draws the execution path, token
  usage, and an error breakdown for each session.
* **Your own signals:** Add spans, metrics, and log lines in agent code when
  the built-in data misses something you need.

### The Rest of AgentCore

Runtime is one service in a larger set. The others cover the remaining parts of
a production agent.

* **Gateway:** Turns APIs, Lambda functions, and existing MCP servers into
  tools. Module 4 uses it.
* **Memory:** Stores short-term conversation state and long-term facts across
  sessions. Module 6 builds this in Neo4j instead.
* **Identity:** Holds the credentials an agent needs for outside services, such
  as Slack or GitHub, and issues tokens at call time.
* **Code Interpreter and Browser:** Give the agent a sandboxed shell and a
  managed browser as tools.
* **Evaluations and Optimization:** Score recorded agent runs, then recommend
  prompt and tool-description changes and A/B test them.
* **Policy:** Applies rules to each tool call at the Gateway before the call
  runs.

AgentCore also includes Harness, Registry, and Payments. Each service works on
its own, so you can adopt Runtime alone and add the others later.

### What This Module Leaves Out

This deployment covers the shortest path to a running agent. A production
deployment adds four things.

* **OAuth inbound auth:** This Runtime accepts IAM callers only. A user-facing
  app validates bearer tokens from an identity provider instead.
* **Secret handling:** Step 4 passes the Neo4j credentials as environment
  variables. Production reads them from AWS Secrets Manager or AgentCore
  Identity at call time.
* **Custom endpoints:** This deployment invokes `DEFAULT`. Teams that need a
  test stage create named endpoints and move each one to a version on its own
  schedule.
* **Streaming responses:** This entry point returns one JSON object. A chat UI
  streams tokens over server-sent events or a WebSocket so the user sees text
  as it arrives.

## Deploy the Agent

Open `notebooks/05-agentcore-deploy/5.1_deploy.ipynb` to build the container,
deploy the Runtime, and invoke the deployed agent.

:::alert{type="warning" header="AWS resources created"}
The notebook creates one IAM execution role, one ECR repository, one CodeBuild project, and one AgentCore Runtime. The container build takes three to five minutes.

Runtime use, ECR image storage, and CodeBuild builds can incur AWS charges. The
workshop leaves these resources in place. On the Vocareum path, the lab account
goes away when the lab session ends. If you use your own account, remove the
Runtime, ECR repository, CodeBuild project, and IAM execution role when you
finish.
:::

:image[Module 5 architecture: an authorized AWS client invokes the packaged agent on AgentCore Runtime, which calls Neo4j and Bedrock from the Runtime container]{src="../../images/05-agentcore-runtime-architecture.svg" width=800}

The diagram traces one invocation through the container. An authorized AWS
client calls `InvokeAgentRuntime`, reaching the AgentCore Runtime box that runs
as `GraphRagBookingAgent`. Inside, `booking_agent.py` holds three parts: the
`search_hotel_knowledge` tool, the `create_reservation` tool, and the
`BedrockModel` connection. Both tools call Neo4j directly from inside the
container: `search_hotel_knowledge` reaches the hybrid retriever, and
`create_reservation` reaches the write that enforces the guest-limit rule
inside its own transaction. The `BedrockModel` connection calls Claude on
Amazon Bedrock, which reasons over the context the tools returned. No
component here calls out to a Gateway or an MCP server; both tools reach
Neo4j from the same process that received the request.

## How Runtime Requests Work

An authorized client calls `InvokeAgentRuntime` with a session ID and a JSON
payload. The Runtime entry point reads `prompt` and `request_id` from the
payload, then sends the prompt to the Strands agent. Hooks capture the tools'
structured results and return them beside the model response.

AgentCore keeps the container's microVM running between invocations instead of
restarting it for each one. The entry point splits its code to take advantage
of that:

* **Warm container resources:** Cached Neo4j drivers and the hybrid retriever
  keep their connection pools available for later invocations, instead of
  opening a new pool on every request.
* **Per-request state:** A new Strands `Agent` and message history are created
  for every invocation. A Strands `Agent` accumulates conversation state as it
  runs, so a single `Agent` shared across callers would leak one caller's
  messages into another caller's conversation. Rebuilding it per request keeps
  every invocation isolated.
* **Caller request ID:** A hook requires the reservation tool to use the exact
  UUID supplied by the caller. Reusing that UUID makes a retry return the first
  result and keeps the graph at one reservation node.

## Why the Build Context Needs Staging

Docker copies files only from its build context. The agent depends on two
sources outside that directory, so Step 2 stages them before the build:

* **Shared package:** `notebooks/workshop/` contains the retrieval code used by
  every module.
* **Reservation command:** Module 3's `reservation_command.py` contains the
  graph-enforced write command.

The notebook places both dependencies in `runtime_app/` immediately before the
build. Git ignores the staged copies, and each notebook run replaces them. The
original files remain the source of truth, including
`notebooks/03-grounded-booking-agent/reservation_command.py`.

The staging step packages `workshop/` as a wheel with `uv build --wheel`. It
also writes the current git commit and working tree status to `BUILD_INFO.txt`.
The container retains this file as a record of the source used for the build.

The AgentCore toolkit builds a `linux/arm64` image in CodeBuild. Building for
the Runtime target ensures that native Python packages match the container's
processor architecture.

## The Five Smoke Tests

The notebook runs five smoke tests against the deployed Runtime. Each test
checks structured tool results so a failure points to the retrieval or Neo4j
decision that caused it. Selected response checks also confirm that the model
used the context returned by Neo4j.

| Test | What it verifies |
|---|---|
| Hotel details | Retrieval returns the recorded address, `789 Corniche el-Nil, Cairo 11519, Egypt` |
| Unknown hotel | The request is rejected, and Neo4j records no request |
| Availability question | The tool returns `answerable: false` and `missing_fact: live_room_availability` |
| 15-guest request | Neo4j returns `status: rejected` and writes no node |
| 10-guest request, delivered twice | The first call creates one node, and the retry returns `duplicate=true` while preserving that one node |

:::alert{type="info" header="Confirm retrieval before testing refusals"}
A failed retriever can make the agent decline every question. The hotel-details
test first requires a specific value from Neo4j to confirm that retrieval
works. The availability test then checks the refusal and the fixture hotel's
address. These assertions separate a missing live-availability fact from a
retrieval failure.
:::

:::alert{type="info" header="Verify policy enforcement and safe retries"}
Neo4j rejects requests above the guest limit inside the write transaction. The
idempotency key lets callers retry the same request while preserving one
reservation node. Both controls work independently of the model's response
text.
:::

## Read the Runtime Logs

Each successful invocation logs a start line and a completion line. The
completion line records the tools used and the command status. Use the
caller-provided `request_id` to connect entries for the same reservation
request.

Run the notebook's **Read recent Runtime logs** cell to inspect recent entries.
The cell uses boto3 to read the Runtime's CloudWatch log group and displays the
results in the notebook.

The failure log records only the exception type. This rule keeps connection
details and credentials from exception messages out of CloudWatch. The handler
then raises the exception so AgentCore can report the invocation failure.

## Next

Head to [Module 6](../06-neo4j-memory/).
