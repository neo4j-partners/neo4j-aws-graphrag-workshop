---
title: "Own Account Setup"
weight: 3
---

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

---

## Step 4: Give the Terminal AWS Credentials

The notebooks read AWS credentials the way any boto3 program does. Run `aws configure`, export the usual credential variables, or set `AWS_PROFILE` to a profile that already works. Confirm the region resolves to **us-east-1**.

---

## Step 5: Install and Verify

:::code{language=bash showCopyAction=true}
cd notebooks
uv venv && uv pip install -r requirements.txt
uv run python ../setup/verify_setup.py
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

Module 5 leaves running AWS resources behind, and this workshop does not delete them for you. The Module 5 notebook tags each one with `WorkshopResource`, so you can find them by that tag. When you finish, remove\:

- The AgentCore Runtime named `GraphRagBookingAgent`
- The ECR repository holding its container image
- The CodeBuild project that built the image
- The IAM execution role the Runtime uses
- The Secrets Manager secret and Lambda function Module 4 created

Then delete the AuraDB Free instance from :link[the Aura console]{href="https://console.neo4j.io/" external=true} if you no longer need the graph. A free instance costs nothing, so you can also leave it and let it pause on its own.
