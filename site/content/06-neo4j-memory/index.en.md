---
title: "Module 6: Neo4j Graph Memory"
weight: 70
---

## Store Agent Memory as a Graph

Module 6 adds long-term hotel preference memory to Neo4j so the agent can recall
a preference across sessions. Each stored preference links to its actor, source
message, session, and hotel. These relationships let you trace a
preference to its source or correct it directly.

:image[AgentCore Memory and Neo4j graph memory: two approaches to long-term preference memory]{src="../../images/04-memory-comparison.svg" width=800}

---

## Place This Lab in the Memory Landscape

Agent memory serves three distinct purposes:

- **Short-term memory:** Stores the current conversation so the agent can resolve
  "it" to a hotel from the previous turn.
- **Long-term memory:** Stores facts and preferences across sessions so the agent
  can remember that an actor prefers a high floor.
- **Reasoning memory:** Stores decisions, tool calls, and outcomes so you can see
  which search result supplied the answer's context.

This module implements long-term preference memory and scopes each recall to one
actor. The graph connects every preference to its source `Message` and `Hotel`,
and those links preserve its provenance alongside the domain data. Adding
short-term prompt recall or reasoning traces requires separate retention and
access rules.

---

## Connect Each Preference to Its Source

Open `notebooks/06-neo4j-memory/6.1_neo4j_memory.ipynb` to create the preference
memory and connect it to the workshop graph.

```
(User)-[:HAS_PREFERENCE]->(Preference)-[:DERIVED_FROM]->(Message)
                                      ↘[:ABOUT_HOTEL]->(Hotel)
```

The two relationships make the preference traceable:

- **`DERIVED_FROM`:** Links the preference to its source message.
- **`ABOUT_HOTEL`:** Links the preference to the existing `Hotel` node.

---

## Verify Recall and Provenance

Run the notebook's recall checks to confirm that preferences remain isolated by
actor:

- **Actor A:** Starts `SESSION_A2` and recalls a preference from an earlier session.
- **Actor B:** Asks the same question and receives no preference.

Use the following Cypher query to return the complete provenance path. The result
identifies the actor, stored preference, source message, source session, and hotel
in one row.

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

Correct the stored value directly with
`SET p.preference = "high floor, away from elevator"`. The next recall reads the
updated property from the same `Preference` node.

---

## Conceptual Comparison: AgentCore vs Neo4j Memory

:link[AgentCore Memory]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}
provides managed extraction and recall. This workshop implements memory in Neo4j
so you can inspect its provenance and connect each preference to domain data.

| | AgentCore Memory | :link[Neo4j graph memory]{href="https://neo4j.com/" external=true} |
|---|---|---|
| Write timing | Asynchronous, from seconds to minutes | Synchronous |
| Extraction | LLM-driven | Explicit writes |
| Auditability | Memory API and :link[Amazon CloudWatch]{href="https://aws.amazon.com/cloudwatch/" external=true} operational logs | Full graph provenance with a source-message link |
| Correction path | Managed through the Memory service API | `SET` on one property |
| Domain link | Separate from domain data | `[:ABOUT_HOTEL]→Hotel` |
| Operations | AWS manages it | You own it |

## Next

Head to [Summary](../summary/).
