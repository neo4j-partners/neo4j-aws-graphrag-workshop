[< Back to the workshop README](../../README.md)

# Module 6: Neo4j Graph Memory

This is the workshop's cross-session memory lab. It stores one preference as a graph record in Neo4j. The same actor recalls it in a new session, while a second actor receives no result. A Cypher query traces the preference to its source message and the `Hotel` node it describes.

The preference connects to its source and hotel through graph relationships. Those relationships provide the audit trail.

**What this module does**

- **Provenance:** Connects each preference to the message that produced it, so you can inspect and correct the stored value.
- **Neo4j writes:** Creates `Conversation`, `Message`, `User`, and `Preference` nodes. It also creates `DERIVED_FROM` and `ABOUT_HOTEL` relationships while preserving every `Hotel` node.
- **AWS service:** Uses Amazon Titan Text Embeddings V2 on Amazon Bedrock through the memory library.
- **Cleanup:** Stores memory records in the module namespace so the notebook's optional final cell can remove them.

---

## The notebook

| Notebook | What it demonstrates |
|---|---|
| [`6.1_neo4j_memory.ipynb`](6.1_neo4j_memory.ipynb) | Actor-scoped recall and the provenance path from a preference to its source message, session, and canonical hotel |

Every actor and session identifier includes a short run ID, which separates each run from earlier transcripts. Each live cell opens and closes its own memory client, so a failure cannot leave a connection open for the next cell. Live cells skip when credentials are unavailable.

The notebook can be launched from the repository root, `notebooks/`, or this
module directory. It resolves `memory_helpers.py` to this folder in every case.

## Conceptual Comparison: Managed and Graph Memory

AgentCore Memory is included here as a conceptual alternative. This module's
hands-on path shows how explicit graph writes provide immediate recall, direct
correction, source provenance, and relationships to domain data.

| | AgentCore Memory | Neo4j graph memory |
|---|---|---|
| How it is written | Managed extraction | Explicit application writes |
| When it is recallable | After asynchronous extraction | Immediately |
| Inspectability | A service API | A Cypher query returning the source message |
| Correction path | Managed through the Memory service API | `SET` on one property |
| Domain link | Separate from domain data | An edge to the real `Hotel` node |
| Operations | AWS runs it | You run Neo4j and the embedding contract |

## Recall Scope and Authorization

- Multi-tenant mode requires a user identifier for every memory write. The application must still authenticate actors and authorize access to session IDs.
- In version 0.5.0, the library's semantic searches cover the entire store. This module scopes recall by starting the query at the selected `User` and traversing that actor's relationships.

## Files in this folder

| File | Purpose |
|---|---|
| `6.1_neo4j_memory.ipynb` | The module notebook |
| `memory_helpers.py` | Builds the memory client on the hotel graph's Neo4j instance and contains the provenance and recall queries |
| `cleanup_memory.py` | Implements the scoped cleanup used by the notebook's optional final cell |

## The workshop page

`site/content/06-neo4j-memory/index.en.md`
