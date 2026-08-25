---
title: "Module 5: Deploy to AgentCore Runtime"
weight: 60
---

## Deploy the Agent to AgentCore Runtime

Nothing outside your notebook can call the grounded booking agent from Module 3. It runs in the Workshop Studio notebook kernel. The notebook environment holds the Neo4j password, and its AWS credentials authorize the Bedrock calls.

In this module, you package a deployment-oriented version of the agent in a container managed by :link[Amazon Bedrock AgentCore Runtime]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}. This deployment changes where the agent runs and how callers invoke it.

| Module 3.1 | Module 5.1 |
|---|---|
| Runs in your kernel | Runs in a container AgentCore starts |
| The notebook environment holds the Neo4j password | The Runtime holds it, injected at launch |
| Reachable only from Jupyter | Invoked through `InvokeAgentRuntime` by authorized AWS clients |
| Session is your kernel's memory | Each invocation uses a caller-provided session ID |

The deployed agent reuses the retrieval code, grounding instructions, and reservation command from Module 3.1. It also adds Runtime request handling.

In Module 3.1, the agent uses one retrieval tool and calls the reservation command directly in the write examples. In Module 5, the deployed agent uses both operations as tools. It retains the grounding instructions that tell it to decline questions the graph cannot answer.

---

## Deploy the Agent

Open `notebooks/05-agentcore-deploy/5.1_deploy.ipynb`.

:::alert{type="warning" header="AWS resources created"}
The notebook creates one IAM execution role, one ECR repository, one CodeBuild project, and one AgentCore Runtime. The container build takes three to five minutes.

Runtime use, ECR image storage, and CodeBuild builds can incur AWS charges. The workshop does not delete these resources automatically. At an AWS Workshop Studio event, the account is reclaimed when the event ends. If you use your own account, remove the Runtime, ECR repository, CodeBuild project, and IAM execution role when you finish.
:::

```
InvokeAgentRuntime
        |
        v
+------------------------------+
|  AgentCore Runtime           |
|  GraphRagBookingAgent        |
|                              |
|  booking_agent.py            |
|   |- search_hotel_knowledge -----> Neo4j hybrid retrieval
|   |- create_reservation ---------> Neo4j write, rule in-transaction
|   `- BedrockModel ---------------> Claude on Amazon Bedrock
+------------------------------+
```

Both tools connect directly to Neo4j from the deployed process. Neo4j enforces the maximum-guests rule in the same transaction that writes a reservation request. The rule therefore applies to every write from the deployed agent.

---

## Prepare the Docker Build Context

Docker copies files only from its build context. The agent needs two files outside that context:

- `notebooks/workshop/`, the package every module shares
- `notebooks/03-grounded-booking-agent/reservation_command.py`, the graph-enforced write path

Step 2 stages both dependencies in `runtime_app/` immediately before the build. Git ignores the staged copies, and the notebook replaces them on every run. The original files remain the source of truth for each build.

The staging step builds `workshop/` as a wheel with `uv build --wheel`. It also writes `BUILD_INFO.txt` with the current git commit and the working tree status. These details remain in the image and identify the source used for the build.

---

## Run Five Smoke Tests

The notebook invokes the deployed Runtime and checks the tools' structured results. These results show the retrieval and Neo4j decisions. The tests also check selected response text to confirm that the model used the retrieved facts.

| Test | What it verifies |
|---|---|
| Hotel details | Retrieval returns the recorded address, `789 Corniche el-Nil, Cairo 11519, Egypt` |
| Hotel that does not exist | The request is not accepted, and Neo4j records no request |
| Availability question | The tool returns `answerable: false` and `missing_fact: live_room_availability` |
| 15-guest request | Neo4j returns `status: rejected` and writes no node |
| 10-guest request, delivered twice | The first call creates one node, and the retry returns `duplicate=true` without creating another |

:::alert{type="info" header="Confirm retrieval before testing refusals"}
A failed retriever can make the agent decline every question. The hotel-details test first requires a specific value from the graph, which confirms that retrieval works. The availability test then checks both the refusal and the retrieved fixture-hotel address. Together, these assertions show that the agent declined because live availability is missing, not because retrieval failed.
:::

:::alert{type="info" header="Verify policy enforcement and safe retries"}
Neo4j rejects requests above the guest limit inside the write transaction. The idempotency key lets callers retry the same request without creating a second reservation node. These controls apply independently of the model's response text.
:::

---

## Read the Runtime Logs

Each successful invocation logs a start line and a completion line with the tools used and the command status. Use the caller-provided `request_id` to correlate log entries for reservation requests.

Run the notebook's **Read recent Runtime logs** cell. It uses boto3 to read the
Runtime's CloudWatch log group and displays recent entries directly in the
notebook.

The application's failure log records only the exception type, which keeps the exception message out of that log entry. The handler then raises the exception so AgentCore can report the invocation failure.

## Next

Head to [Module 6](../06-neo4j-memory/).
