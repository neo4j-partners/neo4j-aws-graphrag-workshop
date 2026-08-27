---
title: "Module 3: Build the Grounded Booking Agent"
weight: 40
---

Module 3 builds a local hotel assistant with the Strands Agents SDK. A plain
Strands agent chooses between two read tools, inspects what the selected tools
return, and writes its response from that evidence. A separate reservation
command checks business rules before it writes an approved request to Neo4j.

**Brief overview**

* **Automatic tool selection:** The model reads two tool specifications and
  chooses passage search, a structured graph query, both, or no tool when the
  turn needs no hotel fact.
* **Observable grounding:** The system prompt directs the model to use tool
  evidence before stating hotel facts. A trace records each tool call, and both
  read tools return the same structured answerability verdict.
* **An explicit limit:** Live room inventory is absent from the graph. The
  returned verdict marks that fact as missing instead of relying on a phrase in
  the model's answer.
* **A separate write path:** A reservation command, not the model, validates a
  reservation request and writes it to Neo4j in one transaction.
* **Safe retries:** A caller-supplied `request_id` lets a retried request
  return the original result instead of creating a second `ReservationRequest`
  node.

:image[Grounded agent architecture: the model chooses passage search or a structured record query for reads, while a separate application command writes reservations]{src="../../images/03-grounded-agent-overview.svg" width=800}

The agent has two ways to read the graph and no registered write tool. A
separate command handles the notebook's reservation examples.

* **Strands agent:** Runs Claude on Amazon Bedrock. It reads the question and
  picks the tool to call.
* **`search_hotel_passages`:** Runs the Module 2 hybrid search and returns up to
  five source passages with linked hotel facts. It fits amenities, rooms,
  policies, services, and location details.
* **`query_hotel_records`:** Uses `Text2CypherRetriever` for counts, averages,
  rankings, filters, and relationship questions. It returns the generated
  Cypher beside the database records.
* **Neo4j:** Stores the hotel graph, both search indexes, and the
  maximum-guests rule.
* **Grounded response policy:** The model is instructed to answer from returned
  facts and state what is missing when the evidence does not support an answer.
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
* **Why this workshop uses it:** Strands makes the model's routing decision
  visible without a custom orchestration loop. The notebook can inspect the
  selected tools and their structured results directly.

The notebook uses these parts:

* **`Agent`:** Runs the loop above. It sends messages to the model and calls
  whichever tool the model selects.
* **`BedrockModel`:** Connects the agent to the Amazon Bedrock model named by
  the model ID.
* **`@tool`:** Turns a Python function into a tool specification the model can
  select. The specification contains a name, a description derived mostly from
  the docstring, and an input schema.
* **`ToolTraceHook`:** Prints each tool call and records its complete bounded
  result for the notebook checks.
* **System prompt:** Defines which facts the model may use and when it must say
  that the graph lacks an answer.

The notebook prints the final specification for both read tools before it
creates an agent. This is the interface the model actually receives. The
descriptions explain the routing boundary between passage questions and
structured questions, and both schemas require one natural-language `query`.

Module 3 uses `BedrockModel` directly. Nothing forces a tool call. The system
prompt says to use a tool before stating a hotel fact, but a greeting or thank
you can receive a direct answer. Routing is a model decision, so the notebook
uses fresh agents and traces to make variation visible.

## How the Grounded Agent Works

For a hotel question, the normal agent loop is:

1. The model reads each tool's name, description, and input schema.
2. It chooses `search_hotel_passages`, `query_hotel_records`, or both and sends
   the user's question as `query`.
3. Strands runs the selected tool and returns its JSON evidence to the model.
4. The model writes a response. The trace shows which path ran and what came
   back.

* **Why the tool owns the driver session:** The model receives data, not
  database credentials. It cannot run its own Cypher.
* **Passage result:** `ok`, up to five `passages`, `hotel_ids`, `top_result`,
  and `grounding_result`. Each passage keeps at most 8,000 characters of source
  text and 12 amenities.
* **Record result:** `ok`, generated `cypher`, at most 25 list `records`,
  `row_count`, and `grounding_result`. An aggregate can still cover every
  matching graph record.
* **Shared verdict:** On a successful read, `grounding_result` contains exactly
  `answerable` and `missing_fact`. Empty records and a failed query remain
  distinct outcomes.

### The Nested Model Call in `query_hotel_records`

The structured path reaches a model twice. First, the agent model chooses the
tool. Inside the tool, `Text2CypherRetriever` asks a model to generate Cypher
from the pinned graph schema. Neo4j plans the statement with `EXPLAIN` and runs
it only when the plan is read-only. The tool returns the generated Cypher for
inspection because a query can run successfully and still express the wrong
meaning.

Open `notebooks/03-grounded-booking-agent/3.1_grounded_booking_agent.ipynb`.

### Route Questions by Evidence Shape

> **"What amenities and guest rating does AnyCompany Cairo Nile View have?"**

This named-hotel question should reach `search_hotel_passages`. The notebook
also routes an average rating and a hotel count to `query_hotel_records`, then
routes a request for recorded cancellation-policy wording back to
`search_hotel_passages`. Each case gets a fresh agent. A mismatch produces a
warning because automatic model routing can vary; it does not make the notebook
fail.

### Query 2: A Question the Graph Cannot Answer

> **"Does AnyCompany Cairo Nile View guarantee room availability next weekend?"**

* **What it tests:** Whether a read tool ran and returned the explicit missing
  fact, without grading the model's wording.
* **Why the evidence is insufficient:** Neo4j stores descriptive hotel facts,
  policies, and total room capacity, not live room inventory. Either read tool
  can return real hotel evidence, but its verdict reports
  `missing_fact: live_room_availability`.

The next example sends `thanks, that is all`. Because it needs no hotel fact,
the expected behavior is a direct reply with no tool call. Together, these
checks demonstrate the intended policy and expose deviations during the lab;
they are not a hard runtime guarantee that the model will always route or word
an answer correctly.

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

Slides for this module\: [The Grounded Booking Agent](../slides/overview-agent/)

## Next

Head to [Module 4](../04-production-agent/).
