---
title: "Module 3: Build the Grounded Booking Agent"
weight: 40
---

Module 3 builds a local hotel assistant with the Strands Agents SDK. The agent
answers hotel questions from Neo4j context and says when the graph lacks a
requested fact. A separate reservation command checks business rules before it
writes an approved request to Neo4j.

**Brief overview**

* **Grounded answers:** The agent must call a retrieval tool before it answers.
  The tool runs `HybridCypherRetriever` from Module 2 and hands the model only
  chunk text and graph properties, so the model cannot invent facts.
* **A stated limit:** The system prompt tells the agent to say when the graph
  does not contain a requested fact, instead of guessing.
* **A separate write path:** A reservation command, not the model, validates a
  reservation request and writes it to Neo4j in one transaction.
* **Safe retries:** A caller-supplied `request_id` lets a retried request
  return the original result instead of creating a second `ReservationRequest`
  node.

:image[Grounded agent architecture: the agent reads hotel facts from Neo4j through one tool, and a separate command writes reservations back to Neo4j]{src="../../images/03-grounded-agent-overview.svg" width=800}

The agent has one way to read the graph and no way to write to it. A separate
command handles reservations.

* **Strands agent:** Runs Claude on Amazon Bedrock. It reads the question and
  picks the tool to call.
* **`search_hotel_knowledge` tool:** The agent's only tool. It runs the
  Module 2 hybrid search and returns hotel facts as JSON.
* **Neo4j:** Stores the hotel graph, both search indexes, and the
  maximum-guests rule.
* **Grounded answer:** The agent answers from the returned facts. When those
  facts do not cover the question, it says the graph does not have the answer.
* **Reservation command:** Plain Python code. It checks the rule and writes the
  request in one transaction, so the model never writes to the graph.

## Strands Agent Basics

The :link[Strands Agents SDK]{href="https://strandsagents.com/" external=true}
is an open-source Python library for building agents where the model decides
what happens next, not the developer.

* **Model-driven:** You do not write code that says "call the retrieval
  function, then call the answer function." You write a system prompt and
  register tools. The model reads the question, the tools' docstrings, and the
  conversation so far, then decides which tool to call and when it has enough
  information to answer.
* **The agent loop:** Strands runs a loop similar to the common "ReAct"
  (Reason plus Act) pattern used by most agent frameworks. The model reasons
  about what it needs, acts by calling a tool, observes the tool's result, and
  repeats until it can answer. Each turn of the loop is one round trip to the
  model.
* **Why this workshop uses it:** The grounding rule, answer only from
  retrieved context, only holds if a tool call happens before every answer.
  Strands lets the workshop enforce that with a small model subclass instead of
  a custom orchestration loop.

The notebook uses these parts:

* **`Agent`:** Runs the loop above. It sends messages to the model and calls
  whichever tool the model selects.
* **`BedrockModel`:** Connects the agent to the Amazon Bedrock model named by
  the model ID.
* **`@tool`:** Turns a Python function and its docstring into a tool definition
  the model can select. The docstring is the only description the model sees,
  so it has to state what the tool does and what it returns.
* **System prompt:** Defines which facts the model may use and when it must say
  that the graph lacks an answer.

The notebook exposes `search_hotel_knowledge` as
`search_hotel_knowledge_tool`. Its docstring tells the model that the function
searches hotel context and returns JSON facts. A small `BedrockModel` subclass
forces one tool call for every new hotel question, so the model cannot skip
retrieval and answer from memory. After the tool returns, the model can write
the final answer.

## How the Grounded Agent Works

The agent follows the same four steps for every hotel question:

1. The model calls `search_hotel_knowledge_tool` with the user's question.
2. The tool runs hybrid search and the fixed `retrieval_query` from Module 2.
3. The retrieval query follows `FROM_CHUNK` from the matched chunk to its
   `Hotel`, and returns the hotel's properties along with the source chunk
   text.
4. The model answers using only that returned context.

* **Why the tool owns the driver session:** The model receives data, not
  database credentials. It cannot run its own Cypher.
* **What every result contains:** The same eight keys: `chunk_text`,
  `combined_score`, `exact_terms`, `hotel_id`, `hotel_name`, `address`,
  `guest_rating`, and `amenities`.
* **Result limits:** At most five results, at most 1,200 characters of
  `chunk_text` per result, and at most 12 amenities per hotel.
* **The grounding rule in practice:** "Subject to availability" is a policy
  sentence stored in the graph, not proof that a room is open right now. The
  system prompt tells the agent to treat policy text and live availability as
  different things, so it says the available hotel knowledge cannot answer a
  live inventory question.

Open `notebooks/03-grounded-booking-agent/3.1_grounded_booking_agent.ipynb`.

### Query 1: Retrieve Amenities and a Guest Rating

> **"What amenities and guest rating does AnyCompany Cairo Nile View have?"**

* **What it tests:** Whether graph-enriched retrieval can pull two different
  fields, amenities and a rating, for the same hotel in one answer.
* **Why it works:** Full-text search matches the hotel name exactly. Vector
  search matches the meaning of "amenities and a rating." `HybridCypherRetriever`
  combines both signals, then the fixed retrieval query returns the connected
  hotel's amenity list and its exact `guest_rating` property.

### Query 2: A Question the Graph Cannot Answer

> **"Does AnyCompany Cairo Nile View guarantee room availability next weekend?"**

* **What it tests:** The grounding rule, not retrieval.
* **Why the agent abstains:** Neo4j stores descriptive hotel facts and
  policies, not live room inventory. Retrieval still succeeds and returns
  policy text, but that text cannot confirm next weekend's availability, so
  the agent says the available hotel knowledge cannot answer the question
  instead of guessing.

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
