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

# Agent Memory with Neo4j

Conversations, durable knowledge, and reasoning carried across sessions

<!--
This deck follows one learning progression: why an agent needs memory, what
the three layers do, how entity linking gives conversations structure, and how
Module 6 applies those ideas to the hotel graph.
-->

---

## The Agent You Built Forgets Everything

- **The booking agent handles one request well**, but a fresh session starts without the last conversation
- **Ask about a hotel.** Then ask "does it have a pool?" and the new session does not know what *it* means
- **The missing link is not more model context.** It is durable, queryable state outside the context window
- **Memory turns separate requests into an ongoing relationship** with the guest

**Most agents are stateless until you design memory on purpose.**

<!--
Earlier modules were stateless by design. That was correct for one request at
a time. Module 6 introduces state across sessions and makes the storage and
access choices visible.
-->

---

## Three Layers of Agent Memory

- **Short-term memory**
  - Conversation history and session state
  - Entities and topics mentioned in each turn
  - Context for references such as "that hotel"
- **Long-term memory**
  - Durable facts and preferences
  - Knowledge shared across sessions
  - History of what changed and when
- **Reasoning memory**
  - Tool calls, decisions, and outcomes
  - Evidence for debugging and review

<!--
The layers serve different readers and retention policies. A transcript holds
more personal detail than one confirmed preference. A reasoning trace may hold
tool inputs and outputs that should have a separate access policy.
-->

---

## Short-Term Memory

Conversation history becomes a graph instead of a flat transcript.

- **Sessions and messages persist** as `Conversation` and `Message` nodes
- **Sequence preserves dialog context**, so recent turns can resolve pronouns and follow-up questions
- **Entity links record what each turn is about**, even when the exact wording changes
- **Semantic search can find related turns** from earlier conversations

```text
(:User)-[:HAS_CONVERSATION]->(:Conversation)-[:HAS_MESSAGE]->(:Message)
```

<!--
Short-term does not mean disposable. It means the raw conversational layer.
Retention can still be minutes, days, or longer depending on the application.
-->

---

## Entity Extraction Gives Conversations Structure

```text
Message text -> entity candidates -> entity resolution -> canonical graph nodes
```

- **Extraction finds subjects** such as hotels, people, locations, events, and products
- **A pipeline can combine fast taggers with an LLM fallback** for ambiguous language
- **Entity resolution merges aliases and near matches** instead of creating a new node for every spelling
- **Known tool results skip rediscovery.** When the agent already has a stable hotel identifier, it links that canonical node directly

Entity extraction answers: **what is this conversation about?**

<!--
Extraction and persistence are separate decisions. The extractor proposes
subjects. Resolution binds them to graph identity. Neither decision means
that every sentence should become durable long-term memory.
-->

---

## Long-Term Memory

Durable memory stores knowledge that should outlive one conversation.

- **Preferences:** room location, accessibility needs, communication style
- **Facts:** stable information the user confirmed or the application verified
- **Temporal history:** replacement memories can supersede old ones without erasing them
- **Domain links:** a preference can point to the same `Hotel` node the booking tools query

```text
(:User)-[:HAS_PREFERENCE]->(:Preference)-[:ABOUT_HOTEL]->(:Hotel)
```

<!--
Long-term memory is curated state, not a copy of the transcript. Promotion
should be deliberate because these records change future behavior.
-->

---

## Reasoning Memory

Reasoning memory records what the agent did, not only what people said.

- **Tool call traces:** tool name, parameters, result, and status
- **Decision provenance:** which evidence and policy led to an action
- **Reusable experience:** similar prior situations and successful paths
- **Operations:** incident review, compliance, and debugging as graph traversals

This module leaves reasoning memory for a production extension.

<!--
Reasoning traces complete the chain from conversation to action. They can also
hold sensitive operational data, so they need a retention and access policy of
their own.
-->

---

## Why Graphs for Agent Memory

- **Relationships are first-class.** A message can mention the same hotel that a preference and reservation reference
- **Multi-hop queries combine memory with domain facts** without joining separate stores in application code
- **Provenance stays traversable.** A durable memory can point back to the exact source turn
- **Graph identity prevents copies.** One canonical `Hotel` accumulates facts, conversations, preferences, and actions
- **History remains visible.** New memories can supersede old ones while both stay inspectable

<!--
This is the thesis of the deck. Graph memory is valuable when the relationship
between a conversation and domain data matters as much as the text itself.
-->

---

## Not Every Mention Becomes a Memory

| Conversation signal | Store as | Decision |
|---|---|---|
| "Tell me about the Cairo Nile View" | `Message` plus `MENTIONS` | The turn is about this hotel |
| "A high floor is a must for me" | Preference candidate | Confirm or apply a promotion policy |
| "Actually, I prefer a lower floor now" | Replacement preference | Supersede the old preference and retain history |
| Tool call and outcome | Reasoning trace | Enable only when operational value justifies retention |

**Entity extraction identifies context. Memory policy controls durable behavior.**

<!--
This separation is the design boundary that the earlier version of this deck
blurred. A broad set of message-to-entity links can be useful while long-term
memory remains selective.
-->

---

## What Module 6 Builds

- **Short-term messages** for the source conversation
- **A `MENTIONS` link** from the source message to the canonical `Hotel`
- **One confirmed `Preference`** owned by the guest
- **`DERIVED_FROM` provenance** back to the exact source message
- **`ABOUT_HOTEL`** to the same hotel the message mentions
- **No reasoning traces** in this exercise

The notebook stores a preference in one session, recalls it in another, and verifies the graph path to its evidence.

<!--
The scenario is intentionally fixed so participants can focus on the graph
shape. The application still separates the raw turn, the subject link, and the
decision to promote a preference.
-->

---

## The Workshop Uses a Hybrid Write Path

1. **Store the turn:** Keep the user's exact words and session.
2. **Link the subject:** Use extraction for free text; use the agent or tool's resolved hotel when its identity is already known.
3. **Promote deliberately:** Store a preference only after confirmation or policy validation.
4. **Keep evidence:** Link the preference to its source message and canonical hotel.
5. **Replace, do not overwrite:** Supersede a changed preference so history, provenance, and embeddings stay consistent.

The pinned library version does not reliably retain every automatically extracted `MENTIONS` edge, so the workshop demonstrates explicit canonical linking.

<!--
This is the workshop fix. The prior deck said the module turned entity
extraction off because the application already knew the facts. That collapsed
message subjects and durable preferences into one decision. The new design
keeps topic links while preserving a deliberate promotion gate.
-->

---

![bg contain](../images/06-preference-provenance.svg)

<!--
Read the graph as a sentence. This guest said this message about this hotel.
The confirmed preference came from that message and concerns the same hotel.
One traversal returns the durable memory and the evidence behind it.
-->
