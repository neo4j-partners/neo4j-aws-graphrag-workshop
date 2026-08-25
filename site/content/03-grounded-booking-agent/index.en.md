---
title: "Module 3: Build the Grounded Booking Agent"
weight: 40
---

Module 3 grounds hotel answers in Neo4j evidence. It uses the fixed Hybrid-Cypher
retriever selected in Module 2. A separate command handles reservation writes.

:image[Grounded agent architecture: Neo4j enforces retrieval, rules, and writes; Amazon Bedrock handles reasoning only]{src="../../images/03-grounded-agent-architecture.png" width=800}

## Learn the Strands Agent Basics

This module introduces the :link[Strands Agents SDK]{href="https://strandsagents.com/" external=true}. You use it to build a local agent.

**Brief overview**

- **`Agent`:** Sends questions to the model and runs the tools it requests.
- **`BedrockModel`:** Connects the agent to the Amazon Bedrock model named by the model ID.
- **`@tool`:** Marks a Python function as a tool the model can call.

The notebook turns `search_hotel_knowledge` into a tool. The agent calls this tool for every new hotel question. It answers from the returned facts. It reports missing evidence when required facts are absent.

## How the Grounded Agent Works

Module 3 runs these steps:

- **Question:** The model reads the hotel question.
- **Tool call:** The model calls `search_hotel_knowledge_tool`.
- **Search:** The tool runs the `HybridCypherRetriever` selected in Module 2.
- **Result:** The tool returns JSON with graph facts and source text.
- **Answer:** The model uses the facts or reports missing evidence.
- **Write:** A separate command checks and writes reservation requests.
- **Tool boundary:** The function controls database access and the result format.
- **Database boundary:** Neo4j checks the guest limit and duplicate requests during the write.

Open `notebooks/03-grounded-booking-agent/3.1_grounded_booking_agent.ipynb`.

### Query 1: Retrieve Amenities and a Guest Rating

> **"What amenities and guest rating does AnyCompany Cairo Nile View have?"**

Run this query.

- **Full-text search:** Matches the hotel name.
- **Vector search:** Matches the request for amenities and a rating.
- **Graph expansion:** Returns the amenity list and exact guest rating.

### Query 2: Does the hotel guarantee availability next weekend?

> **"Does AnyCompany Cairo Nile View guarantee room availability next weekend?"**

Run this query.

- **Stored evidence:** Neo4j contains hotel facts.
- **Missing evidence:** The graph has no live inventory field.
- **Result:** The agent states that it cannot confirm availability.

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

Submit the same valid request twice.

- **First request:** Creates one `ReservationRequest` node.
- **Second request:** Returns `duplicate: true` with the original `created_at`.
- **Constraint:** Prevents a second node for the same `request_id`.

## Next

Head to [Module 4](../04-production-agent/).
