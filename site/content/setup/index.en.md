---
title: "Setup"
weight: 10
---

## Get Your Environment Ready

Every module in this workshop talks to two services\: a :link[Neo4j]{href="https://neo4j.com/" external=true} database holding the hotel graph, and :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} for the models. Setup happens in two stages, each on its own page\: create the database, then pick the environment you run the notebooks in.

:::alert{type="warning" header="Set up AuraDB and restore the dump first"}
Do this before you start the Vocareum setup or the Own Account setup. Both paths assume the graph is already restored, and that step is the one most participants miss. Follow [Neo4j AuraDB Free Setup](./aura-free-setup/) now, then come back here.
:::

## Step 1\: Create the Database

Every path uses the same database. [Neo4j AuraDB Free Setup](./aura-free-setup/) walks through creating a **Neo4j AuraDB Free** instance and restoring the workshop graph into it.

## Step 2\: Pick Your Environment

| Path | When to use |
|------|------------|
| [Vocareum Access](./vocareum-access/) | Hosted event. Vocareum gives you JupyterLab and an AWS account |
| [Own Account Setup](./own-account-setup/) | Self-paced, on your own machine and your own AWS account |

Both paths end at the same place\: a terminal, four Neo4j settings in `CONFIG.txt`, AWS credentials in **us-east-1**, and the workshop dependencies installed. Each page walks through filling in `CONFIG.txt`, installing dependencies, and verifying the environment for that path.

---

## What You Are Configuring

**Neo4j.** The graph arrives as a database dump that you restore into your own AuraDB Free instance. It already contains the hotel corpus, extracted under the same extraction schema Module 1 explains. It deliberately does **not** contain the vector index, the full-text index, or the five hotels you extract yourself. Module 1 creates all of those.

**Amazon Bedrock.** Three models, all in **us-east-1**\:

| Model | Used by |
|---|---|
| `us.anthropic.claude-sonnet-4-6` | Extraction in Module 1, every agent from Module 2 onward |
| `amazon.nova-2-multimodal-embeddings-v1:0` | Chunk embeddings written in Module 1 and queried after |
| `amazon.titan-embed-text-v2:0` | Memory embeddings in Module 6 |

---

## Troubleshooting

:::expand{header="cannot import ... (provided by ...)" defaultExpanded=false}
The install step did not finish. Re-run `uv pip install -r requirements.txt` from the `notebooks/` directory and read the output for the package that failed.
:::

:::expand{header="NEO4J_URI, NEO4J_PASSWORD is not set" defaultExpanded=false}
The script did not find the values. Confirm `CONFIG.txt` is at the repository root, that you edited that file rather than a copy, and that the values have no surrounding quotes. The line the script prints before its first check names the settings file it actually loaded.
:::

:::expand{header="AuthError" defaultExpanded=false}
The password is wrong. Aura shows the generated password once, so a mistyped or truncated paste is the usual cause. Re-copy it from the credentials file you downloaded, or reset the password from the Aura console and paste the new one.
:::

:::expand{header="ServiceUnavailable, or a connection timeout" defaultExpanded=false}
The Aura instance is not accepting connections. Open :link[the Aura console]{href="https://console.neo4j.io/" external=true} and check its status. A newly created instance may still be provisioning, and a free instance left idle for three days pauses and has to be resumed. Wait for **RUNNING**, then run the script again.
:::

:::expand{header="the graph has no hotel named ..." defaultExpanded=false}
The connection works but the dump is not in this instance. Confirm `NEO4J_URI` points at the instance you restored into, that `NEO4J_DATABASE` is `neo4j`, and that the restore finished rather than failing partway. Re-running the restore is safe on a workshop instance, because it overwrites.
:::

:::expand{header="AccessDeniedException from Bedrock" defaultExpanded=false}
Confirm `AWS_REGION` is `us-east-1`. All three models live there. On the Vocareum path model access is enabled for you; on your own account, enable the three models listed above under **Model access** in the Bedrock console.
:::

:::expand{header="NoCredentialsError" defaultExpanded=false}
The terminal has no AWS credentials. On the Vocareum path they come from the lab environment, so this usually means the lab session expired or the terminal was opened before the lab started. On your own account, run `aws configure` or export the usual credential variables.
:::

---

Slides for this module\: [The Hotel Booking Assistant](../slides/overview-architecture/)

::children{depth=1 variant=list}
