---
title: "Setup"
weight: 10
---

## Get Your Environment Ready

Every module in this workshop talks to two services\: a :link[Neo4j]{href="https://neo4j.com/" external=true} database holding the hotel graph, and :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} for the models. Setup is the work of proving both are reachable from your terminal before you open a notebook.

Start with the database, because every path uses the same one. You create a **Neo4j AuraDB Free** instance and restore the workshop graph into it yourself. The steps are on the [Neo4j AuraDB Free Setup](./aura-free-setup/) page.

Then pick the environment you run the notebooks in\:

| Path | When to use |
|------|------------|
| [Vocareum Access](./vocareum-access/) | Hosted event. Vocareum gives you JupyterLab and an AWS account |
| [Own Account Setup](./own-account-setup/) | Self-paced, on your own machine and your own AWS account |

Both paths end at the same place\: a terminal, four Neo4j settings in `CONFIG.txt`, AWS credentials in **us-east-1**, and the workshop dependencies installed.

---

## What You Are Configuring

**Neo4j.** The graph arrives as a database dump that you restore into your own AuraDB Free instance. It already contains the hotel corpus, extracted under the pinned schema Module 1 explains. It deliberately does **not** contain the vector index, the full-text index, or the five hotels you extract yourself. Module 1 creates all of those.

**Amazon Bedrock.** Three models, all in **us-east-1**\:

| Model | Used by |
|---|---|
| `us.anthropic.claude-sonnet-4-6` | Extraction in Module 1, every agent from Module 2 onward |
| `amazon.nova-2-multimodal-embeddings-v1:0` | Chunk embeddings written in Module 1 and queried after |
| `amazon.titan-embed-text-v2:0` | Memory embeddings in Module 6 |

---

## The Settings File

The notebooks read their settings from `CONFIG.txt` at the repository root. It is already there, filled with placeholders. Open it and replace the Neo4j values with the ones from the instance you created\:

| Setting | Value |
|---|---|
| `NEO4J_URI` | The `neo4j+s://` URI from your Aura credentials file |
| `NEO4J_USERNAME` | `neo4j` |
| `NEO4J_PASSWORD` | The password from your Aura credentials file |
| `NEO4J_DATABASE` | `neo4j` |
| `AWS_REGION` | `us-east-1`, already set |

Only the URI and the password actually need typing. The username and the database name are already `neo4j`, and everything below the Neo4j block already has a working value. Paste the credentials with no surrounding quotes and no trailing spaces.

`NEO4J_URI` and `NEO4J_PASSWORD` have no defaults, on purpose. A built-in default password sends a bad credential to the right host and a built-in localhost URI sends a good credential to a host that is not listening, and both read like an outage rather than a missing setting.

:::alert{type="warning" header="Do not commit your filled-in CONFIG.txt"}
The repository ships `CONFIG.txt` as a template, so the file is tracked and your edits to it show up in `git status` like any other change. Leave them uncommitted. If you work from a fork, the safest move is `git update-index --skip-worktree CONFIG.txt` before you paste the password in.
:::

---

## Install the Dependencies

:::code{language=bash showCopyAction=true}
cd notebooks
uv venv && uv pip install -r requirements.txt
:::

You can launch a notebook from the repository root, from `notebooks/`, or from
that notebook's own module directory. Each location resolves the same shared
package and module files. Custom launchers can set `WORKSHOP_NOTEBOOKS_DIR` to
the absolute `notebooks/` directory.

---

## Verify It

One command checks everything the workshop needs. Run it from the `notebooks/` directory so it uses the environment you just built\:

:::code{language=bash showCopyAction=true}
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

Anything other than `ok` on every line means stop and fix it here. The script exits non-zero, prints what failed, and prints what to do about it.

:::alert{type="info" header="Why it checks a named hotel and not a node count"}
`setup/verify_setup.py` does not ask Neo4j how many hotels it holds. A count is plausible at any value, so a half-restored dump passes that check. Instead it reads one specific hotel by name and compares its address to the value the later modules depend on. The same rule governs the two embedding checks\: they compare the returned vector width to the frozen contract width, because a model that answers at the wrong width breaks Module 3 silently rather than loudly.
:::

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

## Next

With every line reporting `ok`, head to [Module 1](../01-build-graph/).

::children{depth=1 variant=list}
