---
title: "Module 6: Neo4j Graph Memory"
weight: 70
---

Module 6 gives the hotel agent a memory. It stores one guest preference in
Neo4j, recalls that preference in a later session, and returns nothing when a
different guest asks the same question. Each stored preference points back to
the message it came from and to the hotel it describes.

This page uses **actor** for the person a memory belongs to. The graph holds
each actor as a `User` node, and every memory write names one.

**Brief overview**

* **Preference:** The graph stores one statement about what an actor wants.
* **Application-controlled write:** The application writes the exact preference
  text, so the value is readable as soon as the transaction commits.
* **Actor-scoped recall:** A Cypher query starts at one `User` node and follows
  only that actor's relationships.
* **Provenance:** Relationships connect each preference to its source message,
  its session, and a `Hotel` node.
* **Memory embedding:** Titan Text Embeddings V2 creates the 1,024-dimensional
  vectors the memory indexes hold.

## Three Kinds of Agent Memory

The `neo4j-agent-memory` library splits memory into three namespaces. The
notebook calls these names directly.

* **Short-term memory:** `memory.short_term` holds the current conversation.
  The agent reads it to work out that "that hotel" means the one from two turns
  ago. It writes `Conversation` and `Message` nodes.
* **Long-term memory:** `memory.long_term` holds facts and preferences that
  outlive a session. The agent reads it to remember that an actor wants a high
  floor. It writes `Preference` nodes.
* **Reasoning memory:** `memory.reasoning` holds decisions, tool calls, and
  outcomes. An operator reads it to find which search result produced an
  answer. It writes `ReasoningTrace` and `ReasoningStep` nodes.

This module writes long-term preference memory. It also writes four short-term
messages. Two of them give the preference a source to point at, and two drive
the actor-isolation check. It writes no reasoning traces.

Each layer carries different risk. A transcript and a reasoning trace hold far
more personal detail than a single stored preference. Decide how long you keep
each one and who may read it before you turn that layer on.

## Why Memory Lives in the Hotel Graph

Most memory products keep conversations in a store of their own. That split
leaves two systems to join by hand. "Which hotel does this guest keep asking
about" lives in one store, and "which hotels have a pool and a high floor"
lives in the other.

This module writes memory into the same Neo4j instance as the hotel graph, so
one query covers both halves. The traversal starts at a stored preference and
ends on the real `Hotel` node, with its rating, amenities, and source
documents.

* **One hotel, not two records:** The preference points at the `Hotel` node
  Module 1 created. No copy of that hotel exists in a separate memory store.
* **No join step:** The query matches the hotel once and keeps using it. The
  application never stitches two result sets together.
* **Name matching fails quietly:** Two separate stores force a text
  comparison on the hotel name. A difference in case or a trailing space makes
  that comparison miss, and the query returns an empty result instead of an
  error.

## What the Module Stores

The module writes one preference and connects it to the two things it came
from.

:::code{language=cypher showCopyAction=true}
(u:User)-[:HAS_PREFERENCE]->(p:Preference)-[:DERIVED_FROM]->(m:Message)
(p)-[:ABOUT_HOTEL]->(h:Hotel)
:::

* **`DERIVED_FROM`:** This relationship links the preference to the message
  that supplied it.
* **`ABOUT_HOTEL`:** This relationship links the preference to the hotel it
  describes.

One query then returns the preference, the message behind it, the session that
message belongs to, and the hotel, all in a single row.

These are the nodes and relationships that make up the memory half of the
graph.

| Label or relationship | What it holds |
|---|---|
| `(:User)` | One actor. `identifier` is the ID the application passes on every write |
| `(:Conversation)` | One session. `session_id` is the ID the notebook sets per run |
| `(:Message)` | One turn, question or answer, in `content` |
| `(:Preference)` | One durable statement, in `preference`, grouped by `category` |
| `(:User)-[:HAS_CONVERSATION]->(:Conversation)` | Which actor was talking |
| `(:Conversation)-[:HAS_MESSAGE]->(:Message)` | The turns in that session |
| `(:User)-[:HAS_PREFERENCE]->(:Preference)` | Which actor owns the preference |
| `(:Preference)-[:DERIVED_FROM]->(:Message)` | Where the preference came from |
| `(:Preference)-[:ABOUT_HOTEL]->(:Hotel)` | Which hotel the preference is about |

The library writes everything above except the last two relationships.
`memory_helpers.py` writes those, and they are what makes a preference
traceable.

## Why the Module Writes Memory by Hand

The library can send a transcript to a model and extract entities from it. This
module turns that off and writes every value directly.

* **Extraction is off:** The client sets `ExtractorType.NONE`, and each message
  write passes `extraction_mode="skip"`. No model runs on the write path.
* **The application already knows the facts:** It just handled a request naming
  a specific hotel. Paying a model to rediscover that name costs time and can
  return the wrong hotel.
* **The stored text is exact:** The application supplies the preference string,
  so the value in the graph is the value you can read in the code.

Use model extraction for free text nobody has parsed yet. Write memory directly
when the application already holds the facts.

### Why `ABOUT_HOTEL` and Not the Library's Own Relationship

The library connects a preference to its subject with
`(:Preference)-[:APPLIES_TO]->(:Entity)`. That relationship needs the target to
carry the `:Entity` label. Adding `:Entity` to the workshop's `Hotel` nodes
would also set library-owned properties on them, and `type` is one of those
properties.

This module writes its own `ABOUT_HOTEL` relationship instead. The `Hotel`
nodes keep exactly the labels and properties Module 1 gave them, and cleanup
removes the relationship without touching the node.

## How Actor-Scoped Recall Works

Multi-tenant mode requires a `user_identifier` on every memory write. The
application still authenticates each actor and authorizes access to session
IDs. The identifier selects that actor's records after those checks pass.

Recall starts with `MATCH (u:User {identifier: $actor})`. The query follows
that actor's `HAS_PREFERENCE` relationships to the requested hotel. Actor A
owns the only matching relationship, so Actor B's traversal returns an empty
list.

Version 0.5.0 of the library searches vectors across the whole store. Its
`search_preferences` call takes a query string and search options, and it takes
no actor. The notebook therefore recalls with the actor-anchored Cypher query
above, so the query itself enforces the scope.

## The Memory Embedding Contract

The memory client uses Amazon Titan Text Embeddings V2 at 1,024 dimensions for
the library's own vector indexes.

The hotel chunks use Amazon Nova embeddings in a different Neo4j index. Each
index compares vectors only within its own embedding space, so each library
uses the model and request format it needs.

Two rules follow from that split:

* **The width is part of the contract:** An index built at one width and
  queried with a vector of another width fails at query time, not at write
  time.
* **Changing the model means rebuilding the indexes:** The library sizes its
  vector indexes on first connect and revalidates them on every later connect.

`notebooks/workshop/retrieval_contract.py` holds both model IDs and both
widths, so Setup and Module 6 cannot drift apart.

## Run the Notebook

Open `notebooks/06-neo4j-memory/6.1_neo4j_memory.ipynb` and run it from top to
bottom. It stores the preference, recalls it in a new session, and confirms
that a second actor sees nothing.

Two checks confirm the scope holds:

* **Same actor, new session:** Actor A opens `SESSION_A2` and recalls the
  preference stored during the earlier session.
* **Different actor, same question:** Actor B asks the same question and
  receives no preference.

Run this query to see the full provenance path. It returns the actor, the
stored preference, the source message, the source session, and the hotel in one
row.

:::code{language=cypher showCopyAction=true}
CYPHER 25
MATCH (u:User {identifier: $actor})
      -[:HAS_PREFERENCE]->(p:Preference)
      -[:DERIVED_FROM]->(m:Message)
      <-[:HAS_MESSAGE]-(c:Conversation),
      (p)-[:ABOUT_HOTEL]->(h:Hotel {name: $hotel_name})
RETURN u.identifier AS actor, p.preference AS preference, m.content AS source_message,
       c.session_id AS source_session, h.name AS hotel
:::

Correct a stored value with
`SET p.preference = "high floor, away from elevator"`. The next recall reads
the updated property from the same `Preference` node.

### Explore the Memory Graph Yourself

Paste this query into the Neo4j Aura query editor once the notebook has run. It
returns every preference the workshop stored and the hotel each one describes.

:::code{language=cypher showCopyAction=true}
CYPHER 25
MATCH (u:User)-[:HAS_PREFERENCE]->(p:Preference)-[:ABOUT_HOTEL]->(h:Hotel)
RETURN u.identifier AS actor, p.category AS category,
       p.preference AS preference, h.name AS hotel
ORDER BY actor
:::

Then try three variations:

* Count the messages in each session, grouped by actor.
* Return preferences that have no `DERIVED_FROM` relationship. Those are the
  records you cannot trace.
* Start at one `Hotel` and walk back to every actor who stated a preference
  about it.

## Going Further: Reasoning Traces

Short-term memory records what people said. Long-term memory records what the
agent knows. Reasoning memory records what the agent **did**.

The library writes one `ReasoningTrace` per task, a series of `ReasoningStep`
nodes under it through `HAS_STEP`, and a `TOUCHED` relationship from each step
to every entity that step reached. This module writes none of them.

Once those traces exist, two questions become single queries:

* **Which agent decisions touched this hotel:** The traversal starts at the
  `Hotel` node, and every step that reached it is one hop away.
* **Which of those decisions failed:** Each step records the observation that
  came back, and each tool call records its status.

An incident review then runs as a query instead of a hunt through logs.

## AgentCore Memory and Neo4j Graph Memory

:link[AgentCore Memory]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}
manages extraction and recall for you. This workshop implements memory in Neo4j
instead, so the application controls each write and can connect preferences to
domain data.

:image[AgentCore Memory and Neo4j graph memory: two approaches to long-term preference memory]{src="../../images/04-memory-comparison.svg" width=800}

The diagram shows both approaches as they would run in production, with a
Lambda function performing the graph writes. The notebook writes from Python
directly, which keeps every write visible while you learn the pattern.

| | AgentCore Memory | :link[Neo4j graph memory]{href="https://neo4j.com/" external=true} |
|---|---|---|
| Write timing | Recall starts after asynchronous extraction finishes | Recall starts when the application transaction commits |
| Extraction | A model extracts memory from the transcript | The application writes the exact memory value |
| Auditability | The application reads memory through the API and operational logs through :link[Amazon CloudWatch]{href="https://aws.amazon.com/cloudwatch/" external=true} | A Cypher query returns the memory and its source message |
| Correction path | The application uses the Memory service API | The application uses `SET` on one property |
| Domain link | The application resolves domain links separately | `[:ABOUT_HOTEL]` points to the existing `Hotel` node |
| Operations | AWS manages it | You own it |

Choose AgentCore Memory when managed extraction and managed operations fit the
application. Choose Neo4j graph memory when the application needs explicit
writes, immediate recall, direct correction, and relationships to domain data.

A production system can use both. Managed memory can carry recent conversation
state, and graph memory can carry the records that have to be explainable.

## Remove What the Module Wrote

Every identifier the notebook creates starts with the `memory06-` prefix, and
every record it writes carries the `neo4j-ftw-memory` ownership marker. The
final cell uses both to delete its own data. That marker differs from the one
on the workshop fixtures, so memory cleanup cannot reach them.

* **Cleanup is off by default:** Running all cells leaves the finished exercise
  in the graph, so you can keep inspecting it.
* **Turn it on when you finish:** Set `CLEAN_UP_DEMO_MEMORY` to `True` and run
  the last cell.
* **Hotel nodes survive:** Cleanup counts `Hotel` nodes before and after, and
  it raises an error if that count changes.

The memory vector indexes stay in place. They are shared infrastructure, they
cost nothing while empty, and the workshop's setup check expects them.

Slides for this module\: [Agent Memory with Neo4j](../slides/overview-agent-memory/)

## Next

Head to [Summary](../summary/).
