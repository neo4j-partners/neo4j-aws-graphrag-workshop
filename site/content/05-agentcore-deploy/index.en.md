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
