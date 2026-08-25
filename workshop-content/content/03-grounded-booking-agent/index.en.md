---
title: "Module 3: Build the Grounded Booking Agent"
weight: 40
---

Module 3 grounds hotel answers in Neo4j evidence. It uses the fixed Hybrid-Cypher
retriever selected in Module 2. A separate command handles reservation writes.

:image[Grounded agent architecture: Neo4j enforces retrieval, rules, and writes; Amazon Bedrock handles reasoning only]{src="../../images/03-grounded-agent-architecture.png" width=800}

## How the Grounded Agent Works

Module 3 uses a controlled reason-act-observe loop:

- **Question:** The model reads the hotel question.
- **Required tool:** The model must call `search_hotel_knowledge_tool`.
- **Fixed retriever:** The tool runs the `HybridCypherRetriever` selected in Module 2.
- **Observation:** The tool returns bounded JSON with graph facts and source evidence.
- **Answer:** The model uses the evidence or states that the evidence is missing.
- **Write:** A separate command validates and writes reservation requests.

- **`@tool` decorator:** Gives the model the function name, arguments, and description.
- **Tool boundary:** Keeps database access and result shape inside the function.
- **Database boundary:** Applies the guest limit and duplicate check during the write.

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
