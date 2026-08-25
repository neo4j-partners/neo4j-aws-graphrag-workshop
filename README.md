# Grounded AI Agents with Neo4j and AWS

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
| [01: Build the Graph](./workshop-content/content/01-build-graph/) | `1.1_build_graph.ipynb` | Live extraction of five held-out hotels, deterministic amenities, both retrieval indexes |
| [02: From Similarity Search to Connected Context](./workshop-content/content/02-connected-context/) | `2.1_connected_context.ipynb` | Semantic, exact-term, graph-enriched, and structured retrieval evidence |
| [03: Build the Grounded Booking Agent](./workshop-content/content/03-grounded-booking-agent/) | `3.1_grounded_booking_agent.ipynb` | Grounded answers, abstention, and a protected reservation command |
| [04: Production Agent with AgentCore](./workshop-content/content/04-production-agent/) | `4.1_agentcore_gateway.ipynb` + `4.2_agentcore_memory.ipynb` | Gateway Lambda tools, IAM-authenticated MCP, cross-session memory |
| [05: Deploy to AgentCore Runtime](./workshop-content/content/05-agentcore-deploy/) | `5.1_deploy.ipynb` | Containerized agent on AgentCore Runtime, one request correlated end to end |
| [06: Inspectable Neo4j Memory](./workshop-content/content/06-neo4j-memory/) | `6.1_neo4j_memory.ipynb` | Graph-backed preference storage with full provenance tracing |

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

Vocareum provides a browser-based JupyterLab environment and an AWS account with Amazon Bedrock model access enabled in `us-east-1`. Neo4j is not part of that environment. You create your own free database and restore the workshop graph into it.

1. Create a Neo4j AuraDB Free instance and restore `neo4j-hotel-graph.dump` into it through the Aura console. The steps are on the [Neo4j AuraDB Free Setup](./workshop-content/content/setup/aura-free-setup/) page.
2. Launch JupyterLab from the Vocareum lab page and open a terminal in it.
3. Paste the Aura URI, username, and password into `CONFIG.txt` at the repository root.
4. Install dependencies: `cd notebooks && uv venv && uv pip install -r requirements.txt`
5. Open `notebooks/01-build-graph/1.1_build_graph.ipynb` and work forward through the modules in order.

The [Setup](./workshop-content/content/setup/) pages carry the exact commands and a verification snippet that checks both Neo4j and Bedrock before Module 1 starts. Run that check first; every failure it catches is cheaper here than three modules in.

### Self-paced, in your own AWS account

You supply the AWS account and run the notebooks locally. The database is the same AuraDB Free instance the hosted path uses. See [Own Account Setup](./workshop-content/content/setup/own-account-setup/) for the full path.

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

Prerequisites for this path are Python 3.11+, [`uv`](https://docs.astral.sh/uv/), an AWS account with Amazon Bedrock model access enabled in `us-east-1`, and a reachable Neo4j instance. A [Neo4j AuraDB Free](https://console.neo4j.io/) database is what the workshop targets.

`prepare_graph.py` wipes and rebuilds. Module 1's notebook uses the additive path instead, so it extends a restored graph without deleting anything a participant has already built.

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

Contributions are welcome! See [CONTRIBUTING](CONTRIBUTING.md) for more information.

---

## Security

If you discover a potential security issue in this project, notify AWS/Amazon Security via the [vulnerability reporting page](http://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

---

## License

This library is licensed under the MIT-0 License. See the [LICENSE](LICENSE) file for details.
