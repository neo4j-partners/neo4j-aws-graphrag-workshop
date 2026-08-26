---
title: "Module 3: Build the Grounded Booking Agent"
weight: 40
---

Module 3 builds a local hotel assistant with the Strands Agents SDK. The agent
answers hotel questions from Neo4j context and says when the graph lacks a
requested fact. A separate reservation command checks business rules before it
writes an approved request to Neo4j.

**Brief overview**

* **Hotel questions:** A required retrieval tool call finds context with the
  `HybridCypherRetriever` from Module 2.
* **Grounded answers:** Agent instructions limit each answer to the returned
  chunk text and graph properties.
* **Reservation requests:** A separate command validates the input, checks the
  stored guest limit, and writes one request in a Neo4j transaction.
* **Safe retries:** A unique `request_id` identifies a repeated request and
  prevents a second `ReservationRequest` node.

:image[Grounded agent architecture: Neo4j supplies graph-enriched context and enforces reservation rules; Amazon Bedrock uses the context to answer questions]{src="../../images/03-grounded-agent-architecture-context.png" width=800}

## Strands Agent Basics

The :link[Strands Agents SDK]{href="https://strandsagents.com/" external=true}
connects the model, its instructions, and its tools. The notebook uses these
parts:

* **`Agent`:** Sends messages to the model and runs the tools that the model
  selects.
* **`BedrockModel`:** Connects the agent to the Amazon Bedrock model named by
  the model ID.
* **`@tool`:** Turns a Python function and its docstring into a tool definition
  that the model can select.
* **System prompt:** Defines which facts the model may use and when it must say
  that the graph lacks an answer.

The notebook exposes `search_hotel_knowledge` as
`search_hotel_knowledge_tool`. Its docstring tells the model that the function
searches hotel context and returns JSON facts. A small `BedrockModel` subclass
requires one tool call for every new hotel question; after the tool returns,
the model can write the final answer.

## How the Grounded Agent Works

The agent follows this flow for every hotel question:

1. The model calls `search_hotel_knowledge_tool` with the user's question.
2. The tool runs hybrid search and the fixed `retrieval_query` from Module 2.
3. The retrieval query follows `FROM_CHUNK` to the matched `Hotel` and returns
   its properties with source chunk text.
4. The model answers only from that context.

The tool owns the Neo4j driver session, so the model receives data instead of
database credentials. Every result uses the same eight keys:
`chunk_text`, `combined_score`, `exact_terms`, `hotel_id`, `hotel_name`,
`address`, `guest_rating`, and `amenities`. The function returns at most five
results, limits each `chunk_text` value to 1,200 characters, and returns at
most 12 amenities per hotel.

The system prompt supplies the grounding rule. For example, “subject to
availability” describes a policy. It does not prove that a room is available
now, so the agent says that the available hotel knowledge cannot answer a live
inventory question.

Open `notebooks/03-grounded-booking-agent/3.1_grounded_booking_agent.ipynb`.

### Query 1: Retrieve Amenities and a Guest Rating

> **"What amenities and guest rating does AnyCompany Cairo Nile View have?"**

Run this query to test graph-enriched retrieval. Full-text search matches the
hotel name, while vector search matches the request for amenities and a rating.
The fixed retrieval query then returns the connected hotel's amenity list and
exact `guest_rating` property.

### Query 2: A Question the Graph Cannot Answer

> **"Does AnyCompany Cairo Nile View guarantee room availability next weekend?"**

Run this query to test the grounding rule. Neo4j stores descriptive hotel facts
and policies, while live room inventory is outside this workshop graph. The
agent therefore explains that the available hotel knowledge cannot confirm
room availability for next weekend.

## The Reservation Command

Reservation requests use a separate command because retrieval and writes need
different controls. The model never writes Cypher. Instead, the command accepts
five defined inputs and runs application-owned queries.

* **`request_id`:** A caller-created UUID that stays the same when the caller
  retries a request.
* **`hotel_id`:** The stable hotel identifier returned by retrieval.
* **`check_in` and `check_out`:** ISO dates that the command validates before
  opening the write transaction.
* **`guests`:** A positive integer checked against the enabled Neo4j rule.

Inside one write transaction, the command checks for an existing `request_id`,
reads the enabled maximum-guests rule, verifies the hotel, and creates the
request only when every check passes. Keeping the rule check and write in one
transaction prevents another request from changing the relevant graph state
between those operations.

### Reject a 15-Guest Reservation

Submit a reservation for 15 guests to test the maximum-guests rule. Neo4j
stores a limit of 10 guests, so the command returns this result:

:::code{language=json}
{
  "status": "rejected",
  "reason_code": "max_guests_exceeded",
  "max_guests": 10
}
:::

The transaction returns the rejection before the create query runs. Neo4j
therefore creates no `ReservationRequest` node for this request.

### Safely Retry a Valid Request

Submit the same valid request twice with one `request_id`. The first call
creates a `ReservationRequest` node and links it to the hotel with `FOR_HOTEL`.
The second call finds that node and returns `duplicate: true` with the original
`created_at` value.

A uniqueness constraint also covers concurrent retries. If two transactions
try to create the same `request_id`, Neo4j accepts one node and rolls back the
other transaction. The command then reads the accepted node and returns it as
the duplicate result.

## Next

Head to [Module 4](../04-production-agent/).
