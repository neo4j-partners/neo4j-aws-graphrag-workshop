---
title: "Module 6: Inspectable Neo4j Memory"
weight: 70
---

## Add Inspectable Memory with Neo4j

This is the workshop's hands-on cross-session memory lab. Neo4j graph memory gives the application direct access to each stored preference, its source message, and the hotel it describes. You can inspect and correct a preference such as "near the elevator" when the guest asked to stay away from it.

:image[AgentCore Memory vs Neo4j Memory: managed extraction compared with explicit graph provenance]{src="../../images/04-memory-comparison.png" width=800}

---

## Connect Each Preference to Its Source

Open `notebooks/06-neo4j-memory/6.1_neo4j_memory.ipynb`.

```
(User)-[:HAS_PREFERENCE]->(Preference)-[:DERIVED_FROM]->(Message)
                                      ↘[:ABOUT_HOTEL]->(Hotel)
```

Every preference links to its exact source message and the existing `Hotel` node. The `ABOUT_HOTEL` relationship connects to domain data instead of storing only the hotel name.

---

## Verify Recall and Provenance

The notebook checks recall for two actors:

- Actor A starts `SESSION_A2` and asks a new question. The actor-scoped query recalls the preference stored during the earlier session.
- Actor B asks the same question in a separate session. The actor-scoped query returns no preference.

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
| Auditability | Memory API and :link[Amazon CloudWatch]{href="https://aws.amazon.com/cloudwatch/" external=true} operational logs, without a source-message link | Full graph provenance |
| Correction path | Managed through the Memory service API | `SET` on one property |
| Domain link | Separate from domain data | `[:ABOUT_HOTEL]→Hotel` |
| Operations | AWS manages it | You own it |

## Next

Head to [Summary](../summary/).
