---
title: "Setup"
weight: 10
---

## Get Your Environment Ready

Every module in this workshop talks to two services\: a :link[Neo4j]{href="https://neo4j.com/" external=true} database holding the hotel graph, and :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} for the models. Setup is the work of proving both are reachable from your terminal before you open a notebook.

Choose your path\:

| Path | When to use |
|------|------------|
| [Workshop Studio Access](./workshop-studio-access/) | AWS-hosted event — your account is pre-provisioned |
| [Own Account Setup](./own-account-setup/) | Self-paced — your own AWS account |

Both paths end at the same place\: a Code Editor terminal, four Neo4j settings, AWS credentials in **us-east-1**, and the workshop dependencies installed.

---

## What You Are Configuring

**Neo4j.** The graph arrives as a database dump that the environment restores for you. It already contains the hotel corpus, extracted under the pinned schema Module 1 explains. It deliberately does **not** contain the vector index, the full-text index, or the five hotels you extract yourself — Module 1 creates all of those.

**Amazon Bedrock.** Three models, all in **us-east-1**\:

| Model | Used by |
|---|---|
| `us.anthropic.claude-sonnet-5` | Extraction in Module 1, every agent from Module 2 onward |
| `amazon.nova-2-multimodal-embeddings-v1:0` | Chunk embeddings written in Module 1 and queried after |
| `amazon.titan-embed-text-v2:0` | Memory embeddings in Module 6 |

---

## The Settings File

The notebooks read their settings from a `.env` file in the `notebooks/` directory. Copy the template at the repository root and fill in the four Neo4j values your path gave you\:

:::code{language=bash showCopyAction=true}
cd notebooks
cp ../.env.example .env
:::

The file names\:

| Setting | Value |
|---|---|
| `NEO4J_URI` | The connection URI from your path's outputs |
| `NEO4J_USERNAME` | `neo4j` |
| `NEO4J_PASSWORD` | The password from your path's outputs |
| `NEO4J_DATABASE` | `neo4j` |
| `AWS_REGION` | `us-east-1` |

`NEO4J_URI` and `NEO4J_PASSWORD` have no defaults, on purpose. A built-in default password sends a bad credential to the right host and a built-in localhost URI sends a good credential to a host that is not listening, and both read like an outage rather than a missing setting.

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
The script looks for `.env` in the `notebooks/` directory first, then at the repository root. Confirm the file is in one of those two places and that the values have no surrounding quotes.
:::

:::expand{header="AuthError, or ServiceUnavailable" defaultExpanded=false}
The password is wrong, or the database is still starting. Re-copy the password from your path's outputs, then retry. If the URI is right and the password is right, give the database another moment to come up and run the script again.
:::

:::expand{header="the graph has no hotel named ..." defaultExpanded=false}
The connection works but the dump is not there. Check that `NEO4J_DATABASE` is `neo4j` and not some other database name, then confirm with your path that the restore finished.
:::

:::expand{header="AccessDeniedException from Bedrock" defaultExpanded=false}
Confirm `AWS_REGION` is `us-east-1`. All three models live there. On the Workshop Studio path model access is pre-enabled; on your own account, enable the three models listed above under **Model access** in the Bedrock console.
:::

:::expand{header="NoCredentialsError" defaultExpanded=false}
The terminal has no AWS credentials. On the Workshop Studio path the Code Editor instance carries them through an instance role, so this usually means you are running somewhere other than the Code Editor. On your own account, run `aws configure` or export the usual credential variables.
:::

---

## Next

With every line reporting `ok`, head to [Module 1](../01-build-graph/).

::children{depth=1 variant=list}
