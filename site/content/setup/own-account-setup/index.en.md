---
title: "Own Account Setup"
weight: 3
---

:::alert{type="info" header="Hosted workshop? You don't need this page"}
If you are at a hosted workshop event, follow [Vocareum Access](../vocareum-access/) instead. This page is only for running the workshop self-paced against your own AWS account.
:::

## Prerequisites

- An AWS account with admin or PowerUser access in **us-east-1**
- Bedrock model access enabled, which is step 1 below
- A :link[Neo4j Aura]{href="https://console.neo4j.io/" external=true} account, free to create
- Python and :link[uv]{href="https://docs.astral.sh/uv/" external=true} on the machine you run the notebooks from
- Roughly $2 of AWS spend for the resources this workshop creates

---

## Step 1: Enable Bedrock Model Access

1. Open :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} in **us-east-1**
2. Go to **Model access → Manage model access**
3. Enable\:
   - **Amazon Nova 2 Multimodal Embeddings** (`amazon.nova-2-multimodal-embeddings-v1:0`)
   - **Claude Sonnet 4.6** (`us.anthropic.claude-sonnet-4-6`)
   - **Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`)
4. Click **Save changes**

Amazon Nova 2 Multimodal Embeddings is available only in us-east-1, so the whole workshop runs there.

---

## Step 2: Create Your Neo4j Database

If you have not done it already, follow [Neo4j AuraDB Free Setup](../aura-free-setup/) to create an instance and restore the hotel graph into it. Come back here with the URI and password in hand.

---

## Step 3: Clone the Repository and Fill In CONFIG.txt

:::code{language=bash showCopyAction=true}
git clone https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop.git
cd neo4j-aws-graphrag-workshop
:::

`CONFIG.txt` at the repository root holds every setting the notebooks read. Replace the placeholder URI and password with the ones from your Aura instance\:

:::code{language=text}
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_DATABASE=neo4j
:::

The username and the database name are already `neo4j`, which is what every Aura instance uses. Nothing below the Neo4j block needs changing either.

`CONFIG.txt` is tracked, so it ships as a placeholder and your filled-in values should stay uncommitted. If you would rather not risk that, create a `.env` file at the repository root (or in `notebooks/`) with the same four settings instead. `.env` is in `.gitignore`, and `environment/verify.py` and the notebooks load it ahead of `CONFIG.txt`, so it is only needed if you want your real credentials to never touch a tracked file at all.

---

## Step 4: Give the Terminal AWS Credentials

The notebooks read AWS credentials the way any boto3 program does. Run `aws configure`, export the usual credential variables, or set `AWS_PROFILE` to a profile that already works. Confirm the region resolves to **us-east-1**.

---

## Step 5: Install and Verify

:::code{language=bash showCopyAction=true}
cd notebooks
uv venv && uv pip install -r requirements.txt
uv run python ../environment/verify.py
:::

**Expected output\:**
:::code{language=text}
      loaded CONFIG.txt
ok    python interpreter is supported
ok    workshop dependencies import
ok    neo4j settings are present
ok    aws credentials resolve
ok    neo4j returns the hero hotel
ok    bedrock chat model answers
ok    bedrock chunk embeddings are 1024-wide
ok    bedrock memory embeddings are 1024-wide

Your environment is ready. Open the Module 1 notebook.
:::

With every line reporting `ok`, proceed to [Module 1](../../01-build-graph/). The [Setup](../) page lists the failures worth expanding on.

---

## Cleanup

Modules 4 and 5 leave AWS resources in your account. The workshop does not
delete them for you. Clean up both resource sets when you finish.

### Module 4 resources

The Module 4 notebook applies the tag
`WorkshopResource=graphrag-with-neo4j` to the Gateway, Lambda functions,
secret, and IAM roles. Gateway targets and generated CloudWatch log groups do
not carry an independent workshop tag. Use the tag and names to confirm
ownership, then remove\:

- The `search-hotel-passages` and `query-hotel-records` targets, followed by
  the AgentCore Gateway `hotel-booking-gateway`
- The Lambda functions `hotel-booking-search_hotel_passages` and
  `hotel-booking-query_hotel_records`
- Every Secrets Manager secret whose name starts with
  `neo4j-ws-retrieval`. A retry can create a name with a numeric suffix.
- The IAM roles `workshop-hotel-lambda-role` and
  `workshop-hotel-gateway-role`
- The CloudWatch log groups
  `/aws/lambda/hotel-booking-search_hotel_passages` and
  `/aws/lambda/hotel-booking-query_hotel_records`

Secrets Manager charges for each secret while it remains stored and for API
calls. Lambda charges for requests and execution duration. AgentCore Gateway
charges are usage based for API invocations, search, and tool indexing. There
is no flat charge solely because this Gateway exists. IAM has no additional
charge. Stored CloudWatch logs can continue to incur storage charges.

### Module 5 resources

The Module 5 notebook applies the tag
`WorkshopResource=graphrag-with-neo4j` to these four resources\:

- The AgentCore Runtime `GraphRagBookingAgent`
- The ECR repository `workshop-graphrag-booking-agent`
- The CodeBuild project `bedrock-agentcore-graphragbookingagent-builder`
- The IAM execution role `workshop-graphrag-runtime-role`

Use the tag to confirm ownership before deletion. Also remove the generated
CloudWatch log groups, including
`/aws/bedrock-agentcore/runtimes/{runtime-id}-DEFAULT` and
`/aws/codebuild/bedrock-agentcore-graphragbookingagent-builder` if they exist.
Runtime use, ECR image storage, CodeBuild builds, and stored CloudWatch logs
can incur charges. IAM has no additional charge.

Then delete the AuraDB Free instance from :link[the Aura console]{href="https://console.neo4j.io/" external=true} if you no longer need the graph. A free instance costs nothing, so you can also leave it and let it pause on its own.
