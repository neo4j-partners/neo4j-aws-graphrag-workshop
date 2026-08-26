[< Back to the workshop README](../../README.md)

# Module 5: Deploy to AgentCore Runtime

The grounded booking agent from Module 3.1 runs in your JupyterLab notebook kernel. The notebook environment holds the Neo4j password, and its AWS credentials authorize the Bedrock calls. This module packages a deployment-oriented version of that agent in a container managed by Amazon Bedrock AgentCore Runtime. It reuses the retrieval code, grounding instructions, and reservation command. It also exposes the command as an agent tool and adds Runtime request handling.

**At a Glance**

- **Goal:** run the booking agent outside Jupyter and invoke it through an AWS API.
- **Neo4j:** The deployed container reads hotel data and writes reservation requests. Neo4j checks the maximum-guests rule in the write transaction. A uniqueness constraint on `request_id` prevents duplicate reservation nodes.
- **AWS:** the deployment uses one IAM execution role, one ECR repository, one CodeBuild project, and one AgentCore Runtime. The agent invokes Claude on Amazon Bedrock through a cross-region inference profile. The execution role authorizes that call when the container has no Bedrock API key. A key authenticates the call in place of the role.
- **Result:** a running AgentCore Runtime named `GraphRagBookingAgent`, available through `InvokeAgentRuntime` and tagged for cleanup.

---

## The notebook

| Notebook | What it verifies |
|---|---|
| [`5.1_deploy.ipynb`](5.1_deploy.ipynb) | Deploys the agent and runs five smoke tests against the tools' structured results |

Docker can copy files only from its build context, so the notebook stages the shared `workshop` package and `reservation_command.py` in `runtime_app/` before the build. It then creates the execution role and ECR repository, launches the Runtime with the AgentCore starter toolkit, tags the deployment resources, runs five smoke tests against the live endpoint, and reads recent Runtime logs through boto3.

The notebook can be launched from the repository root, `notebooks/`, or this
module directory. The deployment build context remains this module's
`runtime_app/` directory in every case.

The cells that create or invoke AWS resources check `DEPLOY_READY` first. They skip when AWS credentials or any of the four Neo4j environment variables are missing. The local staging step still runs so you can inspect the build context without deploying.

## Prerequisites

- Module 3.1's grounded booking agent working end to end.
- AWS credentials with permission to create an IAM role, an ECR repository, a CodeBuild project, and an AgentCore Runtime.
- The same four `NEO4J_*` values every other module reads from `.env`.

## Files in this folder

| File | Purpose |
|---|---|
| `5.1_deploy.ipynb` | The module notebook |
| `runtime_app/` | The container build context with `booking_agent.py`, `agent_requirements.txt`, and the `Dockerfile`. Git ignores the staged `workshop` wheel, `reservation_command.py`, the `workshop/` tree, and `BUILD_INFO.txt`, all of which the notebook regenerates on every run. |

## Cleanup

Runtime use, ECR image storage, and CodeBuild builds can incur AWS charges. This module does not delete its resources automatically. The notebook applies the `WorkshopResource` tag to each resource so you can find and remove them when you finish. On the Vocareum path, the lab account goes away when the lab session ends.

## The workshop page

`site/content/05-agentcore-deploy/index.en.md`
