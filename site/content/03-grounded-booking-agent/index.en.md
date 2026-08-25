---
title: "Module 3: Build the Grounded Booking Agent"
weight: 40
---

Module 3 builds a hotel assistant that answers questions from context retrieved
from Neo4j. Module 2 selected a fixed Hybrid-Cypher path for this application.
This module exposes that path through `HybridCypherRetriever`. The retriever
combines semantic and exact-term search, then follows graph relationships to
return connected hotel data. When the graph lacks a requested fact, the
assistant explains what information is missing. A separate reservation command
validates business rules and writes approved requests to Neo4j.

:image[Grounded agent architecture: Neo4j supplies connected context and enforces reservation rules; Amazon Bedrock uses the context to answer questions]{src="../../images/03-grounded-agent-architecture-context.png" width=800}

## Learn the Strands Agent Basics

This module introduces the :link[Strands Agents SDK]{href="https://strandsagents.com/" external=true}. You use it to build a local agent.

**Brief overview**

- **`Agent`:** Sends questions to the model and runs the tools it requests.
- **`BedrockModel`:** Connects the agent to the Amazon Bedrock model named by the model ID.
- **`@tool`:** Marks a Python function as a tool the model can call.

The notebook exposes `search_hotel_knowledge` as a tool so the agent can retrieve
context for each hotel question. The agent answers from the facts returned by
the tool and explains when the context lacks a required fact.

## How the Grounded Agent Works

To answer a hotel question, the model calls `search_hotel_knowledge_tool`. The
tool runs the `HybridCypherRetriever` selected in Module 2 and returns bounded
JSON containing connected graph facts and source text. The model uses this
context to answer the question or explain which information is missing. The
tool function controls database access and keeps the result format consistent.

Reservation requests use a separate write path. The reservation command checks
the request and sends the write to Neo4j, where the database enforces the guest
limit and prevents duplicate requests in the same transaction.

Open `notebooks/03-grounded-booking-agent/3.1_grounded_booking_agent.ipynb`.

### Query 1: Retrieve Amenities and a Guest Rating

> **"What amenities and guest rating does AnyCompany Cairo Nile View have?"**

Run this query to see how the retriever combines three search operations.
Full-text search matches the hotel name, while vector search matches the request
for amenities and a rating. A Cypher traversal then follows the matched content
to the connected hotel and returns its amenity list and exact guest rating.

### Query 2: Does the hotel guarantee availability next weekend?

> **"Does AnyCompany Cairo Nile View guarantee room availability next weekend?"**

Run this query to test how the agent handles missing context. Neo4j contains
descriptive hotel facts but no live inventory field, so the retrieved context
cannot confirm availability. The agent explains that it cannot determine whether
rooms are available next weekend.

### Reject a 15-guest reservation

Submit a reservation for 15 guests to test the maximum-guests rule. Neo4j stores
a limit of 10 guests, so the command returns this rejection\:

:::code{language=json}
{
  "status": "rejected",
  "reason_code": "max_guests_exceeded",
  "max_guests": 10
}
:::

The rule check runs inside the write transaction. Because the request exceeds
the stored limit, Neo4j returns the rejection without creating a
`ReservationRequest` node.

### Safely Retry a Valid Request

Submit the same valid request twice to verify that retries are safe. The first
request creates one `ReservationRequest` node. The second returns
`duplicate: true` with the original `created_at` value because the uniqueness
constraint prevents another node from using the same `request_id`.

## Next

Head to [Module 4](../04-production-agent/).
