[< Back to the workshop README](../../README.md)

# Module 3: Build the Grounded Booking Agent

Give a Strands agent two complementary read tools and let the model choose the
one that fits each hotel question. Inspect the selected tool and its evidence,
then use a protected reservation command to test a rule-enforced write.

**The passage path uses vector and full-text search plus a reviewed traversal.
The structured path uses model-generated Cypher that is planned with `EXPLAIN`
and run only when Neo4j reports a read-only plan.**

**At a Glance**

- **What it demonstrates:** inspect two tool specifications, observe automatic
  routing between passage and structured reads, report unsupported facts,
  reject requests that exceed the guest limit, and prevent duplicate writes
  for a retried `request_id`.
- **Strands Agents:** teaches the `Agent` loop, plain `BedrockModel`, `@tool`,
  and `ToolTraceHook` before you build the local agent.
- **Neo4j:** reads through the `hotel_chunk_embeddings` and `hotel_chunk_fulltext` indexes; writes one workshop-owned `ReservationRequest` node behind a uniqueness constraint on `request_id`.
- **AWS:** Amazon Bedrock provides LLM reasoning; Amazon Nova embeds each query.
- **You'll build:** one workshop-owned `ReservationRequest` node. The write path preserves the hotel data and all other graph content.

---

## The notebook

| Notebook | What it demonstrates |
|---|---|
| [`3.1_grounded_booking_agent.ipynb`](3.1_grounded_booking_agent.ipynb) | Lets a Strands agent choose between passage and structured graph reads, inspects its evidence, checks a guest limit, and prevents duplicate writes |

## Strands agent basics

**Brief overview**

- **`Agent`:** Sends questions to the model and runs the tools it requests.
- **`BedrockModel`:** Connects the agent to the Amazon Bedrock model named by the model ID.
- **`@tool`:** Builds a tool specification with a name, description, and input
  schema from a Python function.
- **`ToolTraceHook`:** Shows which tool ran and records its bounded result.

The notebook registers `search_hotel_passages` for source text and linked hotel
facts, and `query_hotel_records` for counts, averages, rankings, filters, and
relationship questions. A plain `BedrockModel` makes the choice from the tool
specifications. No subclass forces a call. The system prompt directs the model
to use tool evidence before stating hotel facts, while greetings and thanks can
receive a direct reply.

Successful calls from both tools return `ok: true` and a two-field
`grounding_result`. The passage tool also returns passages, hotel IDs, and the
best matching hotel fields. The structured tool returns generated Cypher,
bounded records, and a row count. Expected query failures instead return
`ok: false` with a bounded error. The notebook reads the trace and verdicts
directly instead of grading the model's prose.

## The reservation command

`reservation_command.py` is a narrow, idempotent command. It reads one enabled rule from the graph, matches one hotel, and writes one `ReservationRequest`. Room booking, hotel data changes, payment, confirmation, and cancellation are outside its scope.

The database enforces two behaviors:

- **The command rejects a reservation over the guest limit.** The rule check runs in the write transaction and blocks the `CREATE` operation.
- **A replayed `request_id` returns `duplicate: true`.** The uniqueness constraint prevents a second node for the same identifier.

## Files in this folder

| File | Purpose |
|---|---|
| `3.1_grounded_booking_agent.ipynb` | The grounded agent and the protected reservation write |
| `reservation_command.py` | The local reservation command that Module 5 deploys with the agent |

The retrieval implementations live in `workshop/hybrid_retrieval.py`. Module 3
wraps its fixed Hybrid-Cypher passage search and its guarded Text2Cypher record
query in `workshop/agent_tools.py`. Both wrappers accept one `query` argument,
but their result shapes and intended question types are different.

The notebook can be launched from the repository root, `notebooks/`, or this
module directory. It resolves `reservation_command.py` to this folder in every
case.

## The workshop page

`site/content/03-grounded-booking-agent/index.en.md`
