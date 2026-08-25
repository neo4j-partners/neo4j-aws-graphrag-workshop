---
title: "Module 6: Inspectable Neo4j Memory"
weight: 70
---

## Add Inspectable Memory with Neo4j

:link[AgentCore Memory]{href="https://aws.amazon.com/bedrock/agentcore/" external=true} provides managed extraction and recall. Neo4j graph memory gives the application direct access to each stored preference, its source message, and the hotel it describes. You can inspect and correct a preference such as "near the elevator" when the guest asked to stay away from it.

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

## AgentCore vs Neo4j Memory

| | :link[Neo4j]{href="https://neo4j.com/" external=true} | AgentCore |
|---|---|---|
| Write timing | Synchronous | Asynchronous, from seconds to minutes |
| Extraction | Explicit writes | LLM-driven |
| Auditability | Full graph provenance | Memory API and :link[Amazon CloudWatch]{href="https://aws.amazon.com/cloudwatch/" external=true} operational logs, without a source-message link |
| Correction | `SET` | No in-place workflow in this workshop |
| Domain link | `[:ABOUT_HOTEL]→Hotel` | Separate from domain data |
| Operations | You own it | AWS manages it |

## Next

Head to [Summary](../summary/).
