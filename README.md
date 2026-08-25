# Grounded AI Agents with Neo4j and AWS

**[Open the workshop microsite](https://neo4j-partners.github.io/neo4j-aws-graphrag-workshop/)**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![Amazon Bedrock](https://img.shields.io/badge/Amazon-Bedrock-FF9900.svg?style=flat&logo=amazon-aws)](https://aws.amazon.com/bedrock/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Graph--RAG-4581C3.svg?style=flat&logo=neo4j)](https://neo4j.com)
[![Strands Agents](https://img.shields.io/badge/Strands_Agents-1.27+-00B4D8.svg?style=flat)](https://strandsagents.com)
[![Vocareum](https://img.shields.io/badge/Hosted_on-Vocareum-1F6FEB.svg?style=flat)](https://www.vocareum.com/)

> Semantic search finds relevant source text. Graph traversal turns that entry point into compact, connected evidence with explicit provenance.

A hands-on workshop in six modules. You build a hotel knowledge graph, compare semantic, exact-term, graph-enriched, and structured retrieval, apply a fixed retriever in a grounded booking agent, deploy its tools through Amazon Bedrock AgentCore, and add graph memory whose provenance you can inspect and correct.

---

## Modules

| Module | Notebooks | What You Build |
|--------|-----------|----------------|
| [01: Build the Graph](https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/tree/main/workshop-content/content/01-build-graph) | `1.1_build_graph.ipynb` | Live extraction of five held-out hotels, deterministic amenities, both retrieval indexes |
| [02: From Similarity Search to Connected Context](https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/tree/main/workshop-content/content/02-connected-context) | `2.1_connected_context.ipynb` | Semantic, exact-term, graph-enriched, and structured retrieval evidence |
| [03: Build the Grounded Booking Agent](https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/tree/main/workshop-content/content/03-grounded-booking-agent) | `3.1_grounded_booking_agent.ipynb` | Grounded answers, abstention, and a protected reservation command |
| [04: Production Agent with AgentCore](https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/tree/main/workshop-content/content/04-production-agent) | `4.1_agentcore_gateway.ipynb` | Gateway Lambda tools, IAM-authenticated MCP, and a Strands agent over the Gateway |
| [05: Deploy to AgentCore Runtime](https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/tree/main/workshop-content/content/05-agentcore-deploy) | `5.1_deploy.ipynb` | Containerized agent on AgentCore Runtime, one request correlated end to end |
| [06: Inspectable Neo4j Memory](https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/tree/main/workshop-content/content/06-neo4j-memory) | `6.1_neo4j_memory.ipynb` | Cross-session graph memory with actor-scoped recall and full provenance tracing |

Each module folder under `notebooks/` carries its own `README.md`: an At a Glance summary, what the module proves, and what every file in the folder is for.

Notebook path setup supports three launch locations: the repository root,
`notebooks/`, and the notebook's own module directory. All three resolve the
same repository assets. If a launcher uses another working directory, set
`WORKSHOP_NOTEBOOKS_DIR` to the absolute `notebooks/` directory; the notebooks
validate that it contains the shared `workshop` package before using it.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    JupyterLab (browser)                         │
│                                                                 │
│  Jupyter Notebook ──► Strands Agent ──► @tool                  │
│                              │                                  │
│                    ┌─────────┴──────────┐                       │
│                    │                    │                       │
│             ┌──────▼──────┐    ┌────────▼────────┐             │
│             │ Neo4j Aura  │    │ Amazon Bedrock  │             │
│             │             │    │                 │             │
│             │ • Hotel KG  │    │ • Claude Sonnet │             │
│             │ • Indexes   │    │ • Nova 2 Embed  │             │
│             │ • Rules     │    │                 │             │
│             │ • Writes    │    │                 │             │
│             └─────────────┘    └─────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

Neo4j owns: connected hotel knowledge, retrieval indexes, business rules, and reservation writes.
Amazon Bedrock owns: reasoning over retrieved evidence and query embedding.

Module 1 uses a simple boundary that participants can inspect: Claude extracts
facts from prose, while the existing `## Hotel Amenities` bullet list is parsed
directly. The exact bullet text becomes the shared amenity name. The same rule
created the prebuilt graph and applies to the five hotels added during the lab.

---

## Getting Started

This is a hosted workshop. Almost everyone runs it the first way.

### At a hosted event, on Vocareum

Vocareum provides a browser-based JupyterLab environment and an AWS account with Amazon Bedrock model access enabled in `us-east-1`. Neo4j is not part of that environment. You create your own free database and restore the workshop graph into it. Everything you need is on this page.

#### Step 1: Create a Neo4j AuraDB Free instance

1. Open [the Neo4j Aura console](https://console.neo4j.io/) and sign in, or create a free account
2. Click **New Instance** and choose **AuraDB Free**
3. Name the instance and click **Create Instance**

> **Save the credentials the moment they appear.** Aura generates the password and shows it once, at creation. Click **Download and continue** to save the credentials file, or copy the password somewhere safe before you dismiss the dialog. If you lose it, reset the password from the instance's actions menu and use the new one.

Wait for the instance card to report **RUNNING**. A restore into an instance that is still provisioning fails.

#### Step 2: Download the workshop graph

The hotel graph ships as a Neo4j database dump. Download it to the machine your browser is running on, not to the Vocareum environment, because the Aura console uploads it from that browser:

```
https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/raw/main/static/neo4j-hotel-graph.dump
```

#### Step 3: Restore the dump

1. On the instance card in the Aura console, open the more menu (`...`) and choose **Inspect**
2. Select the **Restore from backup file** tab, which sits next to **Snapshots**
3. Drag `neo4j-hotel-graph.dump` onto the upload area, or browse to it
4. Confirm the restore and wait for the instance to return to **RUNNING**

The tab accepts `.backup`, `.dump`, and `.tar` files, so the dump goes in as it downloaded. Restoring replaces everything already in the instance, which is why it is the first thing you do with a freshly created one.

Confirm the restore landed. Open **Query** on the instance and run:

```cypher
MATCH (hotel:Hotel {name: "AnyCompany Cairo Nile View"})
RETURN hotel.name AS name, hotel.address AS address
```

One row comes back, and its address is `789 Corniche el-Nil, Cairo 11519, Egypt`.

The restored graph deliberately carries no vector index, no full-text index, and five fewer hotels than the finished graph. Module 1 creates both indexes and extracts those five hotels live. An instance with no indexes is the expected starting state, not a failed restore.

AuraDB Free pauses an instance after three days without a connection. If you return to the workshop after a break, resume the instance from the console before running anything.

#### Step 4: Fill in CONFIG.txt

Launch JupyterLab from the Vocareum lab page, open `CONFIG.txt` at the repository root, and replace the placeholder Neo4j values:

| Setting | Value |
|---|---|
| `NEO4J_URI` | The `neo4j+s://` URI from your Aura credentials file |
| `NEO4J_USERNAME` | `neo4j` |
| `NEO4J_PASSWORD` | The password from your Aura credentials file |
| `NEO4J_DATABASE` | `neo4j` |
| `AWS_REGION` | `us-east-1`, already set |

Only the URI and the password need typing. The username and the database name are already `neo4j`, which is what every Aura instance uses, and everything below the Neo4j block already has a working value. Paste the credentials with no surrounding quotes and no trailing spaces.

`NEO4J_URI` and `NEO4J_PASSWORD` have no defaults, on purpose. A built-in default password sends a bad credential to the right host and a built-in localhost URI sends a good credential to a host that is not listening. Both read like an outage rather than a missing setting.

#### Step 5: Install and verify

Open a terminal in JupyterLab and run:

```bash
cd notebooks
uv venv && uv pip install -r requirements.txt
uv run python ../setup/verify_setup.py
```

Every line must read `ok`:

```
      loaded CONFIG.txt
ok    python interpreter is supported
ok    workshop dependencies import
ok    neo4j settings are present
ok    aws credentials resolve
ok    neo4j returns the hero hotel
ok    bedrock chat model answers
ok    bedrock chunk embeddings are 1024-wide
ok    bedrock memory embeddings are 1024-wide
```

Anything else means stop and fix it here. The script exits non-zero, prints what failed, and prints what to do about it. Run this check before Module 1; every failure it catches is cheaper here than three modules in.

#### Step 6: Open the first notebook

Open `notebooks/01-build-graph/1.1_build_graph.ipynb` and work forward through the modules in order.

#### If verification fails

| What you see | What to do |
|---|---|
| `NEO4J_URI, NEO4J_PASSWORD is not set` | The script did not find the values. Confirm `CONFIG.txt` is at the repository root, that you edited that file rather than a copy, and that the values carry no quotes. The line printed before the first check names the settings file it actually loaded. |
| `AuthError` | The password is wrong. Aura shows it once, so a mistyped or truncated paste is the usual cause. Re-copy it from the credentials file, or reset the password from the Aura console. |
| `ServiceUnavailable`, or a connection timeout | The instance is not accepting connections. Check its status in the Aura console. A newly created instance may still be provisioning, and a free instance left idle for three days pauses and has to be resumed. Wait for **RUNNING**, then run the script again. |
| `the graph has no hotel named ...` | The connection works but the dump is not in this instance. Confirm `NEO4J_URI` points at the instance you restored into, that `NEO4J_DATABASE` is `neo4j`, and that the restore finished. Re-running the restore is safe, because it overwrites. |
| `AccessDeniedException` from Bedrock | Confirm `AWS_REGION` is `us-east-1`. All three models live there. |
| `NoCredentialsError` | The terminal has no AWS credentials. They come from the lab environment, so this usually means the lab session expired or the terminal was opened before the lab started. |
| `cannot import ... (provided by ...)` | The install step did not finish. Re-run `uv pip install -r requirements.txt` from the `notebooks/` directory and read the output for the package that failed. |

### Self-paced, in your own AWS account

You supply the AWS account and run the notebooks locally. The database is the same AuraDB Free instance the hosted path uses, so Steps 1 through 3 above apply unchanged. You also enable the three models yourself in the Bedrock console under **Model access** in `us-east-1`: `us.anthropic.claude-sonnet-5`, `amazon.nova-2-multimodal-embeddings-v1:0`, and `amazon.titan-embed-text-v2:0`.

To run the notebooks against a Neo4j instance you already have:

```bash
# 1. Configure environment
# Edit CONFIG.txt at the repository root with your Neo4j connection details

# 2. Install dependencies
cd notebooks
uv venv && uv pip install -r requirements.txt

# 3. Build the graph from scratch instead of restoring the dump
uv run python 02-connected-context/prepare_graph.py

# 4. Run the modules in order
uv run jupyter lab
# Open 01-build-graph/1.1_build_graph.ipynb first
```

Prerequisites for this path are Python 3.11+, [`uv`](https://docs.astral.sh/uv/), an AWS account with Amazon Bedrock model access enabled in `us-east-1`, and a reachable Neo4j instance. A [Neo4j AuraDB Free](https://console.neo4j.io/) database is what the workshop targets. The full walkthrough is on the [Own Account Setup](https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/tree/main/workshop-content/content/setup/own-account-setup) page.

`prepare_graph.py` wipes and rebuilds. Module 1's notebook uses the additive path instead, so it extends a restored graph without deleting anything a participant has already built.

Modules 4 and 5 leave running AWS resources behind on this path, and the workshop does not delete them for you. Module 4 resources are not tagged, so remove the `hotel-booking-gateway` Gateway, both `hotel-booking-*` Lambda functions, the `workshop-hotel-lambda-role` and `workshop-hotel-gateway-role` IAM roles, and the Secrets Manager secret whose name begins with `neo4j-ws-retrieval`. The Module 5 notebook tags its resources with `WorkshopResource`; use that tag to find and remove the AgentCore Runtime, ECR repository, CodeBuild project, and Runtime execution role. Then delete the AuraDB Free instance from the Aura console if you no longer need the graph.

---

## Workshop Content

The workshop is hosted on [Vocareum](https://www.vocareum.com/). The `workshop-content/content/` directory contains the workshop pages. Participants run the notebooks in `notebooks/` during the session.

| Directory | Purpose |
|-----------|---------|
| `workshop-content/content/` | Workshop markdown pages |
| `workshop-content/images/` | Diagram images referenced by the workshop pages |
| `notebooks/` | Jupyter notebooks (one or two per module) |
| `static/` | Architecture diagrams (PNG exports and drawio sources) |

---

## Contributing

Contributions are welcome! See [CONTRIBUTING](https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/blob/main/CONTRIBUTING.md) for more information.

---

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

---

## License

This library is licensed under the MIT-0 License. See the [LICENSE](https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/blob/main/LICENSE) file for details.

---

## Updating and Maintaining the Workshop Site

The published workshop site is available at [neo4j-partners.github.io/neo4j-aws-graphrag-workshop](https://neo4j-partners.github.io/neo4j-aws-graphrag-workshop/). Its source content lives in `workshop-content/`; do not edit the generated files under `site/modules/` or `site/build/`.

To update a lesson, edit the relevant page in `workshop-content/content/`. Add or replace diagrams in `workshop-content/images/`, then reference them from the page using the existing `:image[...]` directive. The site build converts this Markdown and its workshop directives into the published Antora site.

Preview changes locally before opening a pull request:

```bash
cd site
npm ci
npm run build
npm run serve
```

This requires Node.js and [Pandoc](https://pandoc.org/). Open http://localhost:8080 and check the edited page, navigation, links, and images. `npm run build` regenerates the ignored `site/modules/` directory and writes the static output to the ignored `site/build/` directory.

Pushing changes to `main` that affect `workshop-content/`, `site/`, or `.github/workflows/deploy-site.yml` automatically deploys the site through GitHub Pages. Check deployment progress in the [Deploy workshop site workflow](https://github.com/neo4j-partners/neo4j-aws-graphrag-workshop/actions/workflows/deploy-site.yml).
