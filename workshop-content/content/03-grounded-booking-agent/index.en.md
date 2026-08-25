---
title: "Module 3: Build the Grounded Booking Agent"
weight: 40
---

Ask a booking agent for a guest rating and it can return a plausible number it never read, then accept a reservation the hotel cannot honor. Module 2 selected a fixed Hybrid-Cypher path because hotel questions need exact-name support and connected named fields. Module 3 uses that path through `search_hotel_knowledge` and keeps reservation writes behind a reviewed command.

:image[Grounded agent architecture: Neo4j enforces retrieval, rules, and writes; Amazon Bedrock handles reasoning only]{src="../../images/03-grounded-agent-architecture.png" width=800}

## How the Grounded Agent Works

An agent combines a model, instructions, and tools in a reason-act-observe loop.
The model reads the question, calls a tool, observes the returned result, and
then decides whether it has enough evidence to answer.

Module 3 narrows that general loop to one controlled path:

1. A fresh hotel question requires a call to `search_hotel_knowledge_tool`.
2. The tool calls the fixed `HybridCypherRetriever` selected in Module 2.
3. The retriever returns bounded JSON with graph fields, source evidence, and provenance.
4. The tool result becomes the model's observation for that question.
5. The grounding instructions require an evidence-backed answer or an explicit abstention.

The Strands `@tool` decorator publishes the Python function's name, arguments,
and description to the model. It does not give the model direct database access.
The function controls the query contract and the result shape.

The reservation exercise uses a separate reviewed command. Module 3 calls that
command directly so the model cannot bypass its validation. Neo4j applies the
guest limit and the idempotency constraint inside the write boundary.

Open `notebooks/03-grounded-booking-agent/3.1_grounded_booking_agent.ipynb`.

### Query 1: Retrieve Amenities and a Guest Rating

> **"What amenities and guest rating does AnyCompany Cairo Nile View have?"**

Run this query. The `HybridCypherRetriever` uses full-text search to match the hotel name and vector search to match the requested meaning. It then traverses the graph relationships and returns structured facts, including the amenity list and exact guest rating.

### Query 2: Does the hotel guarantee availability next weekend?

> **"Does AnyCompany Cairo Nile View guarantee room availability next weekend?"**

Run this query. Neo4j stores hotel knowledge, and live inventory is outside its scope. The graph has no `guaranteedAvailability` property. The retrieved evidence cannot confirm availability, so the agent abstains.

### Reject a 15-guest reservation

Submit a reservation for 15 guests. The maximum is 10\:

:::code{language=json}
{
  "status": "rejected",
  "reason_code": "max_guests_exceeded",
  "max_guests": 10
}
:::

The rule check runs inside the write transaction and blocks the `CREATE` operation.

### Safely Retry a Valid Request

Submit a valid reservation with a new `request_id`, then submit the same valid payload again. The first call creates one node. The second call returns `duplicate: true` with the original `created_at`. The uniqueness constraint prevents another node.

## Next

Head to [Module 4](../04-production-agent/).
