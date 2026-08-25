---
title: "Workshop Studio Access"
weight: 1
---

## Step 1: Access Your AWS Account

1. In the Workshop Studio left panel, click **Open AWS Console**
2. Confirm you are in **us-east-1 (N. Virginia)** — check the top-right region selector

---

## Step 2: Open Code Editor

1. In the Workshop Studio left panel, find the **Outputs** section
2. Copy the **CodeEditorURL** value
3. Open it in a new browser tab
4. Log in with the **CodeEditorUser** and password from the Outputs section

:::alert{type="info" header="Code Editor is VS Code in the browser"}
The workshop repository is already cloned at `/Workshop`. Open a terminal with **Terminal → New Terminal**.
:::

---

## Step 3: Set Environment Variables

Your :link[Neo4j]{href="https://neo4j.com/" external=true} connection details are in the Workshop Studio Outputs. In the Code Editor terminal\:

:::code{language=bash showCopyAction=true}
# Paste your values from Workshop Studio Outputs
export NEO4J_URI="<Neo4jURI from Outputs>"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="<Neo4jPassword from Outputs>"
export NEO4J_DATABASE="neo4j"
export AWS_REGION="us-east-1"
:::

To make these permanent for the session, add them to a `.env` file\:

:::code{language=bash showCopyAction=true}
cd /Workshop/notebooks
cat > .env << EOF
NEO4J_URI=${NEO4J_URI}
NEO4J_USERNAME=${NEO4J_USERNAME}
NEO4J_PASSWORD=${NEO4J_PASSWORD}
NEO4J_DATABASE=neo4j
AWS_REGION=us-east-1
EOF
:::

---

## Step 4: Install Dependencies

:::code{language=bash showCopyAction=true}
cd /Workshop/notebooks
uv venv && uv pip install -r requirements.txt
:::

---

## Step 5: Verify Everything Works

One command checks the interpreter, the installed packages, the Neo4j settings, the AWS credentials, the restored graph, and all three Bedrock models\:

:::code{language=bash showCopyAction=true}
cd /Workshop/notebooks
uv run python ../setup/verify_setup.py
:::

**Expected output\:**
:::code{language=text}
      loaded notebooks/.env
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

Any line that is not `ok` names what failed and what to do about it. The [Setup](../) page lists the failures worth expanding on.

:::alert{type="success" header="Ready"}
Proceed to [Module 1](../../01-build-graph/).
:::

---

## Troubleshooting

:::expand{header="Neo4j connection refused" defaultExpanded=false}
The ECS Fargate task may still be starting after stack creation. Wait for it to come up, then retry. You can check the task status in the ECS console under the workshop cluster.
:::

:::expand{header="Bedrock access denied" defaultExpanded=false}
Confirm you are in **us-east-1**. Amazon Nova 2 Multimodal Embeddings is an :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} model available only in us-east-1. Your workshop account has model access pre-enabled, so no console changes are needed.
:::
