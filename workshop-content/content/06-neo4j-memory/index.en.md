---
title: "Module 6: Inspectable Neo4j Memory"
weight: 70
---

## Add Inspectable Memory with Neo4j

Module 6 stores one hotel preference in Neo4j. The preference links to its actor,
source message, session, and hotel. You can inspect, recall, and correct it.

:image[AgentCore Memory vs Neo4j Memory: managed extraction compared with explicit graph provenance]{src="../../images/04-memory-comparison.png" width=800}

---

## Place This Lab in the Memory Landscape

Agent memory can store three kinds of state:

- **Short-term memory:** Stores the current conversation. It can resolve "it" to a hotel from the previous turn.
- **Long-term memory:** Stores facts and preferences across sessions. It can remember that an actor prefers a high floor.
- **Reasoning memory:** Stores decisions, tool calls, and outcomes. It can show which search result supported an answer.

- **This module:** Implements long-term preference memory with actor-scoped recall.
- **Provenance:** Connects the preference to its source `Message` and `Hotel`.
- **Extensions:** Short-term prompt recall and reasoning traces require separate retention and access rules.

---

## Connect Each Preference to Its Source

Open `notebooks/06-neo4j-memory/6.1_neo4j_memory.ipynb`.

```
(User)-[:HAS_PREFERENCE]->(Preference)-[:DERIVED_FROM]->(Message)
                                      ↘[:ABOUT_HOTEL]->(Hotel)
```

- **`DERIVED_FROM`:** Links the preference to its source message.
- **`ABOUT_HOTEL`:** Links the preference to the existing `Hotel` node.

---

## Verify Recall and Provenance

The notebook checks actor-scoped recall:

- **Actor A:** Starts `SESSION_A2` and recalls a preference from an earlier session.
- **Actor B:** Asks the same question and receives no preference.

The following Cypher query returns the complete provenance path:

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

Correct the preference directly with `SET p.preference = "high floor, away from elevator"`.

---

## Conceptual Comparison: AgentCore vs Neo4j Memory

:link[AgentCore Memory]{href="https://aws.amazon.com/bedrock/agentcore/" external=true}
is a managed alternative for extraction and recall. The workshop implements
the Neo4j path so you can inspect its provenance and domain relationships.

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
