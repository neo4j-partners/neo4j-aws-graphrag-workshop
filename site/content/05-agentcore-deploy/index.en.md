---
title: "Module 5: Deploy to AgentCore Runtime"
weight: 60
---

## Deploy the Agent to AgentCore Runtime

The grounded booking agent from Module 3 runs in your JupyterLab kernel and
accepts calls only from that notebook process. The notebook environment holds
the Neo4j password, and its AWS credentials authorize the Bedrock calls.

Module 5 packages a deployment-oriented version of the agent in a container
managed by :link[Amazon Bedrock AgentCore Runtime]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}.
AgentCore Runtime starts the container and gives authorized AWS clients an API
for invoking the agent.

| Module 3.1 | Module 5.1 |
|---|---|
| Runs in your kernel | Runs in a container AgentCore starts |
| The notebook environment holds the Neo4j password | The Runtime holds it, injected at launch |
| Reachable only from Jupyter | Invoked through `InvokeAgentRuntime` by authorized AWS clients |
| Session is your kernel's memory | Each invocation uses a caller-provided session ID |

The deployed agent reuses the retrieval code, grounding instructions, and
reservation command from Module 3.1. Runtime request handling adapts these
components to the AgentCore invocation API.

Module 3.1 gives the agent one retrieval tool and calls the reservation command
directly in the write examples. Module 5 exposes both operations as tools for
the deployed agent. The grounding instructions require the agent to decline
questions that need context absent from Neo4j.

---

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

:image[Module 5 architecture: an authorized AWS client invokes the packaged agent on AgentCore Runtime, which calls Neo4j and Bedrock directly]{src="../../images/05-agentcore-runtime-architecture.svg" width=800}

Both tools connect directly to Neo4j from the deployed process. Neo4j evaluates
the maximum-guests rule in the same transaction that writes a reservation
request, so every write from the deployed agent follows the rule.

---

## Prepare the Docker Build Context

Docker can copy files only from its build context, while the agent depends on
two sources outside that directory. Step 2 stages these dependencies before the
build:

- `notebooks/workshop/`, the package every module shares
- `notebooks/03-grounded-booking-agent/reservation_command.py`, the graph-enforced write path

The notebook places both dependencies in `runtime_app/` immediately before the
build. Git ignores the staged copies, and each notebook run replaces them. The
original files remain the source of truth for every build.

The staging step packages `workshop/` as a wheel with `uv build --wheel`. It
also writes the current git commit and working tree status to `BUILD_INFO.txt`.
The container image retains this file so you can identify the source used for
the build.

---

## Run Five Smoke Tests

The notebook runs five smoke tests against the deployed Runtime. Each test
checks the tools' structured results to expose the retrieval and Neo4j
decisions. Selected response assertions also confirm that the model used the
context returned by Neo4j.

| Test | What it verifies |
|---|---|
| Hotel details | Retrieval returns the recorded address, `789 Corniche el-Nil, Cairo 11519, Egypt` |
| Hotel that does not exist | The request is not accepted, and Neo4j records no request |
| Availability question | The tool returns `answerable: false` and `missing_fact: live_room_availability` |
| 15-guest request | Neo4j returns `status: rejected` and writes no node |
| 10-guest request, delivered twice | The first call creates one node, and the retry returns `duplicate=true` without creating another |

:::alert{type="info" header="Confirm retrieval before testing refusals"}
A failed retriever can make the agent decline every question. The hotel-details
test first requires a specific value from Neo4j to confirm that retrieval
works. The availability test then checks both the refusal and the retrieved
fixture-hotel address. Together, these assertions distinguish a missing live
availability fact from a retrieval failure.
:::

:::alert{type="info" header="Verify policy enforcement and safe retries"}
Neo4j rejects requests above the guest limit inside the write transaction. The
idempotency key lets callers retry the same request while preserving one
reservation node. Both controls operate independently of the model's response
text.
:::

---

## Read the Runtime Logs

Each successful invocation logs a start line and a completion line that records
the tools used and the command status. Use the caller-provided `request_id` to
correlate entries for the same reservation request.

Run the notebook's **Read recent Runtime logs** cell to inspect recent entries.
The cell uses boto3 to read the Runtime's CloudWatch log group and displays the
results in the notebook.

The application's failure log records only the exception type, which excludes
the exception message from that entry. The handler then raises the exception so
AgentCore can report the invocation failure.

## Next

Head to [Module 6](../06-neo4j-memory/).
