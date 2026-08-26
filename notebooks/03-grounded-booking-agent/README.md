[< Back to the workshop README](../../README.md)

# Module 3: Build the Grounded Booking Agent

Apply the fixed Hybrid-Cypher pattern selected in Module 2. Build a grounded
agent that declines unsupported questions, then use a protected reservation
command to test a rule-enforced write.

**The retrieval path uses vector and full-text search to find candidate `Chunk` nodes. A reviewed Cypher traversal returns connected facts as named fields, including the stable `hotel_id` used by the reservation command.**

**At a Glance**

- **What it demonstrates:** ground an answer in named sources, abstain when the returned context cannot answer, reject requests that exceed the guest limit, and prevent duplicate writes for a retried `request_id`.
- **Strands Agents:** teaches the `Agent` loop, `BedrockModel`, and `@tool` before you build the local agent.
- **Neo4j:** reads through the `hotel_chunk_embeddings` and `hotel_chunk_fulltext` indexes; writes one workshop-owned `ReservationRequest` node behind a uniqueness constraint on `request_id`.
- **AWS:** Amazon Bedrock provides LLM reasoning; Amazon Nova embeds each query.
- **You'll build:** one workshop-owned `ReservationRequest` node. The write path preserves the hotel data and all other graph content.

---

## The notebook

| Notebook | What it demonstrates |
|---|---|
| [`3.1_grounded_booking_agent.ipynb`](3.1_grounded_booking_agent.ipynb) | Introduces Strands Agents, grounds answers in graph facts, checks a guest limit, and prevents duplicate writes |

## Strands agent basics

**Brief overview**

- **`Agent`:** Sends questions to the model and runs the tools it requests.
- **`BedrockModel`:** Connects the agent to the Amazon Bedrock model named by the model ID.
- **`@tool`:** Marks a Python function as a tool the model can call.

The notebook turns `search_hotel_knowledge` into a tool. The agent calls it for each new hotel question. It answers from the returned facts. It says it cannot determine the answer when required facts are absent.

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
| `grounded_bedrock_model.py` | The `BedrockModel` subclass that forces a tool call on every fresh hotel question |

The production retriever lives in `workshop/hybrid_retrieval.py`. Module 2 selects its fixed Hybrid-Cypher pattern because the application needs exact hotel-name support and connected graph fields. The `search_hotel_knowledge` function exposes that decision through one `query` argument. Modules 4 and 5 deploy the same function unchanged.

The notebook can be launched from the repository root, `notebooks/`, or this
module directory. It resolves `reservation_command.py` to this folder in every
case.

## The workshop page

`site/content/03-grounded-booking-agent/index.en.md`
