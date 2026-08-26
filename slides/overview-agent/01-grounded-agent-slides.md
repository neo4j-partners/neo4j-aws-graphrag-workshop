---
marp: true
theme: default
paginate: true
---

<style>
section {
  --marp-auto-scaling-code: false;
}

li {
  opacity: 1 !important;
  animation: none !important;
  visibility: visible !important;
}

/* Disable all fragment animations */
.marp-fragment {
  opacity: 1 !important;
  visibility: visible !important;
}

ul > li,
ol > li {
  opacity: 1 !important;
}
</style>

# The Grounded Booking Agent

One tool it must call, and one thing it cannot do

<!--
This deck has two hinges, not one. "One Tool, On Purpose" argues for a single
tool. "Writes Do Not Go Through the Model" argues that the write path does not
go through the model at all.

Most agent talks cover the first half of this deck and stop. The reservation
half is where the workshop says something the room has probably not heard, so
protect the time for it. If you are running late, cut the ReAct slide, not the
write path.
-->

---

## What Is an Agent

A model with tools and a loop:

- **Perception:** it reads the question and the conversation so far
- **Reasoning:** it decides what it needs and which tool provides it
- **Action:** it calls the tool and gets a result back
- **Response:** it answers, or it loops again

The difference from a chatbot is the Action step. The model can reach your systems.

<!--
Say the last line as a warning, not a feature. Everything in this deck is about
what that reach is allowed to include.

A model that can call a search function is useful. A model that can call a
write function is a system where a wrong token becomes a row in a database.
"Writes Do Not Go Through the Model" is where that gets resolved.
-->

---

## The ReAct Loop

> Which Chicago hotel has both a spa and a swimming pool, what is its cancellation policy, and can I hold it for four guests?

1. **Reason:** I need hotel facts. I have one tool that returns them
2. **Act:** I call `search_hotel_knowledge_tool` with the question
3. **Observe:** the tool returns five results, each with hotel name, address, rating, amenities, and chunk text
4. **Reason:** the context names the hotel and the policy. The hold is not something I can do
5. **Respond:** I answer the first two clauses from context, and I say the third needs a reservation

Each turn of the loop is one round trip to the model.

<!--
Step 5 is the whole deck in miniature. The agent answers what the context
supports and declines the part that would require a write.

The last line is the practical note. Every loop turn costs a Bedrock call, so
the number of tools is not free. That is the argument the next slide makes on
different grounds.
-->

---

## Strands Agents in One Slide

```python
agent = Agent(
    model=BedrockModel(model_id=...),
    tools=[search_hotel_knowledge_tool],
    system_prompt=GROUNDING_INSTRUCTIONS,
)
```

- **`Agent`** runs the loop and calls whichever tool the model selects
- **`BedrockModel`** connects it to Claude on Amazon Bedrock
- **`@tool`** turns a Python function into a tool definition. The docstring is the only description the model sees
- **The system prompt** states which facts the model may use and when it must abstain

Model-driven, not developer-scripted. You do not write "retrieve, then answer."

<!--
The docstring point catches people. It is not a comment. It is the tool's
interface as far as the model is concerned, and a vague one produces an agent
that calls the wrong tool or calls nothing.

search_hotel_knowledge_tool's docstring says it searches hotel context and
returns JSON facts. That is enough, because there is only one tool to choose
from, which is the next slide.
-->

---

![bg contain](../images/strands-agents-graphrag-principles.svg)

<!--
Strands runs the agent loop. Amazon Bedrock provides the model. The retrieval
tool gives that agent verified facts and connected context from Neo4j.

Walk the three panels from left to right. Grounded retrieval resolves the
request to facts in the graph. Connected reasoning follows stored
relationships. Right-sized context returns only the small graph slice needed
for this question.

Neo4j complements Strands. It strengthens the context that the Strands agent
can use. The next slide narrows that design to one retrieval tool.
-->

---

## One Tool, On Purpose

This agent has exactly one retrieval tool. That is the design, not a simplification.

- **Nothing to route:** the agent cannot pick the wrong retriever for a question
- **Nothing to widen:** the tool takes query text, not an index name, a `top_k`, or a ranker
- **One path to test:** every answer in the workshop came through the same code

The hard part of an agent is not adding tools. It is trusting the answer.

<!--
Expect pushback here, and welcome it. Real systems have many tools.

The honest answer is that many tools is a routing problem, and routing is a
model decision, and this workshop is about moving decisions out of the model.
Add tools when the questions genuinely need different retrieval, and know that
each one you add is a decision you handed back.

Module 4 adds a second tool, graph_query, and it comes with a guard for exactly
this reason.
-->

---

![bg contain](../images/03-grounded-agent-overview.svg)

<!--
The shape to point at is the asymmetry. One arrow into Neo4j through the tool,
reading. One arrow into Neo4j from the reservation command, writing. They do
not touch.

The model sits on the read arrow only. It cannot reach the write arrow, and
that is not a permission setting. It is that the write function was never
registered as a tool.
-->

---

## Forcing the Read

A small `BedrockModel` subclass requires one tool call for every new hotel question.

- **Without it:** the model can decide it already knows the answer and skip retrieval
- **With it:** retrieval happens, then the model writes the answer
- **Why a subclass:** Strands lets you enforce this in a few lines instead of a custom orchestration loop

The grounding rule only holds if a tool call happens before every answer.

<!--
This is the difference between a system prompt that asks and a mechanism that
enforces, and it is the same distinction as pinning the extraction schema in
Module 1.

A prompt saying "always search first" works almost always. The failure case is
the question the model finds easy, which is precisely the question it is most
likely to answer from training data about a real hotel chain that is not this
fictional one.
-->

---

## The Result Contract

Every result, every time, the same eight keys:

`chunk_text`, `combined_score`, `exact_terms`, `hotel_id`, `hotel_name`, `address`, `guest_rating`, `amenities`

Three caps:

- **At most five results** per call
- **At most 1,200 characters** of `chunk_text` per result
- **At most 12 amenities** per hotel

The tool owns the driver session. The model receives data, never credentials.

<!--
The caps are the context-rot slide from deck 5, applied. Five results with
trimmed text and a bounded amenity list is a predictable context budget, and
predictable is what makes the agent's behavior repeatable.

The last line is worth stating plainly. There is no scenario in which the model
holds a Neo4j connection. It gets JSON. It cannot run Cypher of its own.
-->

---

## A Grounded Answer

> "What amenities and guest rating does AnyCompany Cairo Nile View have?"

- **Full-text** matches the hotel name exactly
- **Vector** matches the meaning of "amenities and a rating"
- **The traversal** returns the connected amenity list and the exact `guest_rating` property

Two different fields, for the same hotel, in one answer, returned alongside the chunk text that matched.

<!--
This question is chosen to exercise both arms of the hybrid retriever at once,
which is why it is first in the notebook.

Point at guest_rating specifically. It is an exact graph property, written as a
float during Module 1's extraction because the schema told it to. It is not a
number the model read out of a sentence.
-->

---

## Abstention

> "Does AnyCompany Cairo Nile View guarantee room availability next weekend?"

Retrieval succeeds. The agent still declines.

- **The graph holds** descriptive facts and policies, not live room inventory
- **"Subject to availability"** is a policy sentence, not proof that a room is open
- **The system prompt** tells the agent to treat policy text and live availability as different things

A correct "I cannot answer that" is a feature of the system, not a gap in it.

<!--
This slide tests the grounding rule rather than the retrieval, and it is the
one that gets the most comment in the room.

The subtlety is that the retriever did its job. It found relevant text. The
failure mode being prevented is the model reading "subject to availability" and
producing a confident sentence about next weekend, which is exactly the kind of
plausible answer deck 1 opened with.

Run this one live if you run anything live.
-->

---

## Writes Do Not Go Through the Model

The reservation command sits beside the agent, not inside it.

- **Not a tool.** It is plain Python the application calls
- **Five defined inputs.** The command accepts `request_id`, `hotel_id`, `check_in`, `check_out`, and `guests`
- **`hotel_id`** is the stable identifier retrieval already returned
- **Application-owned Cypher.** The model writes none of it

Retrieval and writes need different controls, so they get different code paths.

<!--
Second hinge, and the part of this deck that is least common elsewhere.

The usual design registers create_reservation as a tool and constrains it with
a careful prompt and a JSON schema. That works until the model passes a
plausible wrong value, and then you have a row.

Here the model's role ends at proposing. It can tell the user which hotel to
book and why. Turning that into a request is the application's call, and the
inputs are typed before anything opens a transaction.
-->

---

## The Rule Is Enforced Inside the Transaction

Neo4j stores a maximum-guests rule. A 15-guest request comes back:

```json
{
  "status": "rejected",
  "reason_code": "max_guests_exceeded",
  "max_guests": 10
}
```

- **One transaction** checks for an existing `request_id`, reads the enabled rule, verifies the hotel, and creates the node
- **The rejection returns before the create query runs.** No `ReservationRequest` node exists
- **No interleaving.** No other request can change the rule between the check and the write

<!--
Two things make this different from validating in Python.

The rule lives in the graph, so changing it does not require a deploy, and the
same rule is visible to anything else reading that graph.

The check and the write are in one transaction, so there is no window where
another request changes the relevant state between them. Validate first and
write second in separate calls and that window exists, however small.

reason_code is a machine-readable field on purpose. A caller can branch on it.
A human-readable message alone cannot be branched on reliably.
-->

---

## Retries Are Idempotent

The caller supplies `request_id`, and it stays the same across retries.

- **First call:** the command creates the `ReservationRequest` and links it with `FOR_HOTEL`
- **Second call, same id:** the command finds that node and returns `duplicate: true` with the original `created_at`
- **Two concurrent retries:** a uniqueness constraint lets Neo4j accept one and roll back the other

The command then reads the accepted node and returns it as the duplicate result.

<!--
Idempotency is what makes retrying safe, and retrying is what every network
client does. Without this, a timeout on a successful write produces two
reservations.

The concurrency case is the one worth naming. Application-level "check then
create" has a race. The uniqueness constraint closes it in the database, which
is the only layer that can.
-->

---

<style scoped>
/* Four rows of two-column prose plus framing. */
section { font-size: 25px; }
</style>

## Who Enforces What

| Layer | What it owns |
|---|---|
| **The model** | Proposes. Answers from returned context, or says it cannot |
| **The tool** | Fixes the retriever, the traversal, and the result shape |
| **The command** | Validates the five inputs and opens the transaction |
| **Neo4j** | Holds the maximum-guests rule and rejects a duplicate `request_id` |

Each rule sits in the layer that can actually enforce it.

<!--
This is deck 3's control-ownership table, now with an implementation behind
every row. Say that connection out loud.

The row people argue with is the first one. Proposing sounds weak for something
called an agent. It is the strongest guarantee on the slide, because a system
where the model only proposes has no failure mode where a wrong token becomes a
committed write.
-->

---

## Correct and Safe, and Running on Your Laptop

The agent is grounded, it abstains when it should, and it cannot write to the graph.

Everything is still in one notebook process: the retriever, the driver, the tool, the agent.

- **Module 4** moves the tools out, behind an AgentCore Gateway
- **Module 5** moves the whole agent out, onto AgentCore Runtime

The design does not change. Only where it runs does.

<!--
Synthesis, not restatement. The point is that the interesting work is done, and
the next two modules are deployments of it.

Say the last line clearly, because the room is about to see two new
architecture diagrams and could reasonably conclude the design is changing
underneath them. It is not. The same hybrid_retrieval.py runs in all three.
-->
