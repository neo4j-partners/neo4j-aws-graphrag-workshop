---
title: "Vocareum Access"
weight: 2
---

## Step 1: Launch Your Environment

1. Sign into Vocareum using the link from your event invitation
2. Open the workshop lab and start it
3. Launch the hosted **JupyterLab** environment from the lab page

Vocareum provisions an AWS account for you and supplies its credentials to the lab environment.

:::alert{type="info" header="Where your AWS credentials come from"}
The lab environment carries the AWS credentials the notebooks use. You do not run `aws configure` and you do not paste an access key anywhere. Modules 4, 5, and 6 create AWS resources under that lab account, and everything lands in **us-east-1**.
:::

---

## Step 2: Find the Workshop Files

The lab starts you with the workshop files already in place\: the `notebooks/` directory, `setup/verify_setup.py`, `CONFIG.txt`, and the repository `README.md`. Open the JupyterLab file browser and confirm you can see them.

Every path on this page is relative to the directory holding those files. Open a terminal there with **File → New → Terminal**.

If the files are not there, clone the repository yourself and work from that checkout instead\:

:::code{language=bash showCopyAction=true}
git clone https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop.git
cd neo4j-aws-graphrag-workshop
:::

---

## Step 3: Create Your Neo4j Database

The Vocareum lab does not include Neo4j. Follow [Neo4j AuraDB Free Setup](../aura-free-setup/) to create an instance and restore the hotel graph into it, then come back here with the URI and password in hand.

---

## Step 4: Fill In CONFIG.txt

`CONFIG.txt` at the repository root holds every setting the notebooks read. Open it from the JupyterLab file browser, or edit it in the terminal. Replace the three placeholder Neo4j values with the ones from your Aura instance\:

:::code{language=text}
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_DATABASE=neo4j
:::

Save the file. Nothing below the Neo4j block needs changing. Paste the values with no surrounding quotes and no trailing spaces.

---

## Step 5: Install the Dependencies

:::code{language=bash showCopyAction=true}
cd notebooks
uv venv && uv pip install -r requirements.txt
:::

---

## Step 6: Verify Everything Works

One command checks the interpreter, the installed packages, the Neo4j settings, the AWS credentials, the restored graph, and all three Bedrock models\:

:::code{language=bash showCopyAction=true}
cd notebooks
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

Any line that is not `ok` names what failed and what to do about it. The [Setup](../) page lists the failures worth expanding on.

:::alert{type="success" header="Ready"}
Proceed to [Module 1](../../01-build-graph/).
:::

---

## Troubleshooting

:::expand{header="Neo4j connection refused, or a connection timeout" defaultExpanded=false}
The Aura instance is not accepting connections yet. Open :link[the Aura console]{href="https://console.neo4j.io/" external=true} and look at the instance status. A newly created instance may still be provisioning, and an instance left idle for three days pauses and has to be resumed. Wait for **RUNNING**, then run the script again.
:::

:::expand{header="NoCredentialsError" defaultExpanded=false}
The terminal has no AWS credentials, which usually means the Vocareum lab session has expired or was never started. Return to the lab page, start the lab again, and open a fresh terminal so it picks up the new credentials.
:::

:::expand{header="Bedrock access denied" defaultExpanded=false}
Confirm you are in **us-east-1**. Amazon Nova 2 Multimodal Embeddings is an :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} model available only in that region. The Vocareum lab account has model access enabled for you, so no console changes are needed.
:::
