---
title: "Module 6: Neo4j Graph Memory"
weight: 70
---

Module 6 stores a hotel preference as a graph in Neo4j. The same actor can
recall the preference in a later session, while a second actor receives an
empty result.

**Brief overview**

* **Preference:** A stored statement about what an actor wants.
* **Application-controlled write:** The application writes the exact
  preference, which makes the stored value available when the transaction
  commits.
* **Actor-scoped recall:** A Cypher query starts at one `User` and follows only
  that user's preference relationships.
* **Provenance:** Relationships connect the preference to its source message,
  source session, and `Hotel` node.
* **Memory embedding:** Titan Text Embeddings V2 creates 1,024-dimensional
  vectors for the memory indexes.

:image[AgentCore Memory and Neo4j graph memory: two approaches to long-term preference memory]{src="../../images/04-memory-comparison.svg" width=800}

## Three Kinds of Agent Memory

Agent memory serves three purposes:

* **Short-term memory:** Stores the current conversation so the agent can
  resolve a phrase such as "that hotel" from an earlier turn.
* **Long-term memory:** Stores facts and preferences across sessions so the
  agent can remember that an actor prefers a high floor.
* **Reasoning memory:** Stores decisions, tool calls, and outcomes so an
  operator can trace which search result supported an answer.

This module implements long-term preference memory. It also stores source
messages to provide provenance. Short-term prompt recall and reasoning traces
need their own retention, access, and privacy rules because they store
different information for different purposes.

## The Preference Provenance Pattern

Open `notebooks/06-neo4j-memory/6.1_neo4j_memory.ipynb` to create the preference
memory and connect it to the workshop graph.

:::code{language=cypher showCopyAction=true}
(u:User)-[:HAS_PREFERENCE]->(p:Preference)-[:DERIVED_FROM]->(m:Message)
(p)-[:ABOUT_HOTEL]->(h:Hotel)
:::

The application performs each write itself. It first stores a source
message with automatic extraction disabled. It then calls
`add_preference` with the exact preference text and adds two relationships:

* **`DERIVED_FROM`:** Links the preference to the message that supplied it.
* **`ABOUT_HOTEL`:** Links the preference to the existing `Hotel` node.

These relationships record the source of each stored value. One Cypher query
can return the preference, the message that supplied it, the source session,
and the hotel it describes.

## How Actor-Scoped Recall Works

Multi-tenant mode requires a `user_identifier` on every memory write. The
application still authenticates each actor and authorizes access to session
IDs. The identifier selects the actor's graph records after those checks.

Recall starts with `MATCH (u:User {identifier: $actor})`. The query then
follows that user's `HAS_PREFERENCE` relationships to the requested hotel.
Actor A owns the only matching relationship, so Actor B's traversal returns an
empty list.

Version 0.5.0 of the memory library searches vectors across the full store.
This notebook uses the actor-anchored Cypher query for recall so the query
enforces the required actor scope.

## The Separate Memory Embedding Contract

The memory client configures Amazon Titan Text Embeddings V2 with 1,024
dimensions. The memory library uses this configuration for its own vector
indexes.

The hotel chunks use Amazon Nova embeddings in a different Neo4j index. The
two indexes compare vectors only within their own embedding spaces. Each index
can therefore use the model and request format required by its library. This
module's recall check uses the actor-scoped Cypher traversal described above.

## Verify Recall and Provenance

Run the notebook's recall checks to confirm that preferences remain isolated by
actor:

* **Actor A:** Starts `SESSION_A2` and recalls a preference from an earlier
  session.
* **Actor B:** Asks the same question and receives no preference.

Use the following Cypher query to return the complete provenance path. The
result identifies the actor, stored preference, source message, source session,
and hotel in one row.

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

Correct the stored value with
`SET p.preference = "high floor, away from elevator"`. The next recall reads
the updated property from the same `Preference` node.

## AgentCore Memory and Neo4j Graph Memory

:link[AgentCore Memory]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}
manages extraction and recall. This workshop implements memory in
Neo4j so the application controls each write and can connect preferences to
domain data.

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
writes, immediate recall, direct correction, and graph relationships to domain
data. This lab uses Neo4j graph memory to show the second design.

## Next

Head to [Summary](../summary/).
