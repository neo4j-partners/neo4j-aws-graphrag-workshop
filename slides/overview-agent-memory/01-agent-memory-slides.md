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

Preferences that point back at where they came from

<!--
The hinge is slide 6, provenance. Memory that you can explain and correct is
the argument this deck makes, and it is the same argument the whole workshop
has been making about retrieval, applied to a new surface.

Deliberate framing choice: this deck uses "actor" for the person a memory
belongs to, matching the module page. The graph stores each actor as a User
node.
-->

---

## The Agent You Built Forgets Everything

The agent is deployed and callable over an API. It still meets every caller as a stranger.

Ask about the Cairo hotel. Then say "book that one."

- **Between turns in the notebook**, one long-lived agent object holds the conversation and can resolve "that one"
- **In the deployed container**, even that is gone. Each invocation builds a new agent
- **Between sessions**, nothing survives. Every conversation starts from zero
- **Across callers**, there is no notion of who is asking

The graph knows about hotels. It knows nothing about guests.

<!--
Recall plus motivation. The agent from Modules 3 through 5 is stateless by
design, and that was correct for what it had to do.

Open the door to the real question: a returning guest who always wants a high
floor should not have to say so every time, and the system that remembers has
to be able to say why it thinks that.
-->

---

## Three Layers of Agent Memory

The `neo4j-agent-memory` library splits memory into three namespaces:

- **Short-term, `memory.short_term`:** This layer holds the current conversation. It writes `Conversation` and `Message` nodes, and it is what resolves "that hotel"
- **Long-term, `memory.long_term`:** This layer holds facts and preferences that outlive a session. It writes `Preference` nodes
- **Reasoning, `memory.reasoning`:** This layer holds decisions, tool calls, and outcomes. It writes `ReasoningTrace` and `ReasoningStep` nodes

Each layer carries different risk. A transcript holds far more personal detail than one stored preference.

<!--
The risk line is not a footnote. Turning on short-term memory means storing
everything anyone typed, and turning on reasoning memory means storing what the
agent did with it.

Decide retention and access per layer before you enable it, not after. That is
the whole point of separating them into namespaces rather than one memory blob.
-->

---

## What This Module Builds

Long-term preference memory, and only that.

- **Writes one `Preference`**, connected to the actor who owns it
- **Writes short-term messages**, because a preference needs a source to point at
- **Writes no reasoning traces**

The test: store a preference in one session, recall it in a new session, and confirm that a different actor sees nothing.

<!--
Scope this tightly so the room does not expect a full memory system.

The three-part test is what the notebook actually asserts, and it is a good
minimal specification for any memory feature: it persists, it survives a new
session, and it does not leak to the wrong person.
-->

---

## A Preference Is Not a String

```text
  (:User {identifier})
        |
   [:HAS_PREFERENCE]
        |
   (:Preference {preference, category})
        |                       \
  [:DERIVED_FROM]            [:ABOUT_HOTEL]
        |                          \
   (:Message {content})          (:Hotel)
        |
  [:HAS_MESSAGE] from (:Conversation {session_id})
```

One query returns the preference, the message behind it, the session, and the hotel, in a single row.

<!--
Read the shape as a sentence: this actor prefers this, it came from that
message in that session, and it is about this hotel.

The library writes everything here except DERIVED_FROM and ABOUT_HOTEL.
memory_helpers.py writes those two, and they are exactly the two that make a
preference traceable. That is not a coincidence, it is the module's argument.
-->

---

## Provenance Is the Point

`DERIVED_FROM` links each preference to the message it came from.

- **You can always answer "why does the agent think this"** by returning the source message
- **A preference with no `DERIVED_FROM`** is a record you cannot trace. Finding those is one of the module's exercises
- **`ABOUT_HOTEL` points at the `Hotel` node Module 1 created.** No copy exists in a separate store

Memory you can explain is memory you can correct. Memory you can correct is memory you can trust.

<!--
The hinge. This is the same argument as source_filename in Module 2 and
field_provenance in the retrieval query, applied to memory.

Most memory systems store a derived assertion and discard the evidence. When
the assertion is wrong, and eventually one is, there is nothing to inspect and
no way to tell a bad extraction from a guest who changed their mind.

ABOUT_HOTEL is worth a note. The library's own relationship, APPLIES_TO,
requires the target to carry an :Entity label, which would set library-owned
properties on the workshop's Hotel nodes. Writing a separate relationship keeps
the Hotel nodes exactly as Module 1 left them, and cleanup can remove the
relationship without touching the node.
-->

---

## Why the Module Writes Memory by Hand

The library can send a transcript to a model and extract entities. This module turns that off.

- **The client sets `ExtractorType.NONE`.** Every message write also passes `extraction_mode="skip"`, so no model runs on the write path
- **The application already knows the facts.** It just handled a request naming a specific hotel
- **The stored text is exact.** The value in the graph is the value in the code

Use model extraction for free text nobody has parsed. Write directly when the application already holds the facts.

<!--
Same instinct as Module 1's deterministic amenity parser, and worth naming as
the callback it is. The model is good at prose. It is not the right tool for a
fact you are already holding.

There is a correctness angle too, not just a cost one. Paying a model to
rediscover the hotel name means accepting a chance it returns the wrong hotel,
in a write that is going to persist.
-->

---

## Recall Is Actor-Scoped

```cypher
MATCH (u:User {identifier: $actor})
      -[:HAS_PREFERENCE]->(p:Preference)
      -[:DERIVED_FROM]->(m:Message)<-[:HAS_MESSAGE]-(c:Conversation),
      (p)-[:ABOUT_HOTEL]->(h:Hotel {name: $hotel_name})
RETURN u.identifier AS actor, p.preference AS preference,
       m.content AS source_message, c.session_id AS source_session, h.name AS hotel
```

The traversal is anchored at one `User`. Actor B's query returns an empty list because Actor B owns no matching relationship.

<!--
The notebook has two anchored queries. The isolation check runs the short one
in memory_helpers.py, which stops at ABOUT_HOTEL. This is the long one, which
adds the provenance hop. Both anchor at the same User node, and that is the
point.

The scope is a property of the traversal, not a filter applied afterward. There
is no path from Actor B's User node to Actor A's preference, so there is
nothing to leak.

Be precise about why the notebook uses this query rather than the library's
search. Version 0.5.0 of the library searches vectors across the whole store,
and search_preferences takes a query string and options but no actor. Anchoring
in Cypher is what enforces the scope.

Also be precise about what this is not. The identifier selects an actor's
records after authentication and authorization. It is not the authentication.
The application still has to prove who the caller is.
-->

---

## A Separate Embedding Contract

Memory uses Amazon Titan Text Embeddings V2 at 1,024 dimensions. Hotel chunks use Amazon Nova, in a different index.

- **Each index compares vectors only within its own space.** Two models mean two indexes with no overlap
- **The width is part of the contract.** A mismatch fails at query time, not at write time
- **Changing the model means rebuilding the indexes.** The library sizes them on first connect and revalidates on every later one

`retrieval_contract.py` holds both model IDs and both widths, so Setup and Module 6 cannot drift apart.

<!--
Both are 1,024 dimensions, which makes this look like it should be one index. It
is not, and matching widths do not make vectors comparable. They come from
different models and mean different things.

The one file holding both contracts is the pattern worth taking home. Embedding
settings scattered across a build script and a query path is how a system ends
up comparing vectors from two spaces while reporting success.
-->

---

## Correction Is One SET

```cypher
SET p.preference = "high floor, away from elevator"
```

The next recall reads the updated property from the same `Preference` node.

- **The node keeps its identity**, so `DERIVED_FROM` and `ABOUT_HOTEL` still hold
- **Nothing is re-extracted.** No pipeline runs, and the new value is readable as soon as the transaction commits

A guest who changes their mind is the normal case, not an edge case.

<!--
This slide reads as small and is the practical argument for the whole approach.

Correcting a memory in a system built on extraction means changing the input
and hoping the pipeline derives something different. Here it is a property
update on a node you can point at, and the provenance survives because the node
survives.
-->

---

<style scoped>
/* Six rows of three-column prose. */
section { font-size: 23px; }
</style>

## AgentCore Memory or Neo4j Graph Memory

| | AgentCore Memory | Neo4j graph memory |
|---|---|---|
| **Write timing** | Recall starts after asynchronous extraction finishes | Recall starts when the transaction commits |
| **Extraction** | A model extracts memory from the transcript | The application writes the exact value |
| **Auditability** | Read memory through the API, logs through CloudWatch | A Cypher query returns the memory and its source message |
| **Correction** | The Memory service API | `SET` on one property |
| **Domain link** | The application resolves it separately | `ABOUT_HOTEL` points at the existing `Hotel` node |
| **Operations** | AWS manages it | You own it |

Managed extraction is the row that decides it the other way. If nobody has parsed the input, the service does work you would otherwise write.

<!--
Give AgentCore Memory a fair hearing. Managed extraction and managed operations
are real advantages, and a team that does not want to own a memory schema
should take them.

The row that decides most cases is write timing. Asynchronous extraction means
a preference stated in this turn may not be recallable in the next one, and
whether that matters depends entirely on your product.

A production system can use both. Managed memory for recent conversation state,
graph memory for the records that have to be explainable.
-->

---

![bg contain](../images/04-memory-comparison.svg)

<!--
Both approaches as they would run in production, with a Lambda performing the
graph writes. The notebook writes from Python directly, which keeps every write
visible while you learn the pattern.

The asymmetry to point at is the domain link. On the AgentCore side, the
application resolves the hotel separately, which in practice means matching on
a name string. On the Neo4j side, the preference points at the node itself.

Name matching fails quietly. A difference in case or a trailing space returns
an empty result rather than an error, and an empty result looks exactly like a
guest with no preferences.
-->

---

## Where This Goes

One graph now holds hotel facts, the documents behind them, reservation requests, and guest memory.

- **Reasoning traces** are the layer this module skipped. Once they exist, "which agent decisions touched this hotel" is one query
- **An incident review** becomes a traversal instead of a hunt through logs
- **The Production Path page** covers read-only database users, secret handling, and the controls this workshop simplified
- **The Summary page** collects every pattern from today in one list you can take back

Every module today was one design: the layer that can enforce a rule is the layer that owns it.

<!--
Close on the synthesis, not a recap.

The takeaway that transfers is the control-ownership table from deck 2, now
with six modules of implementation behind it. The schema was hotels. The
separation was the lesson.

Point people at the Production Path page for what was deliberately left out,
and at the cleanup cell in this notebook. Every identifier it writes starts
with memory06- and carries an ownership marker, so cleanup deletes only its own
data. It is off by default so the finished exercise stays inspectable.
-->
