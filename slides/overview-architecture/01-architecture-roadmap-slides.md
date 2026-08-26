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

# The Hotel Booking Assistant

The dataset, the environment, and who owns which control

<!--
This deck runs immediately before Setup, and its job is to make the room
confident about what they are about to build and what they own.

The shape is one roadmap slide, then the data and the one modeling choice that
makes the data worth having, then the request flow, then the control-ownership
table. That last slide is the workshop's actual argument, stated once, early,
so the later modules can point back at it.

Everything before the control table is orientation. Do not spend the deck
there.
-->

---

<style scoped>
/* A numbered list of six plus two closing lines. */
section { font-size: 24px; }
</style>

## What You Will Build

Six modules, six verbs:

1. **Build** a knowledge graph from hotel documents into your own Aura instance
2. **Compare** eight retrieval patterns and pick one for the application
3. **Ground** an agent in that retriever, and give it a write path it cannot reach
4. **Publish** the retrieval tools through AgentCore Gateway, on the Model Context Protocol
5. **Deploy** the whole agent to AgentCore Runtime as a container
6. **Remember** guest preferences in the same graph, with provenance

Modules 3, 4, and 5 are three deployments of one design, not three designs.

To start you need an Aura instance, an AWS account with Bedrock access in **us-east-1**, a filled-in `CONFIG.txt`, and a passing `environment/verify.py`. Setup has the steps.

<!--
Deck 1's thesis, restated: the model does not get smarter across these six
steps. What changes is what it can see and what it is allowed to do.

Say the grouping out loud, because it saves questions later. Modules 1 and 2
are where the day's understanding gets built. Modules 3, 4, and 5 are the same
design deployed three ways, so nobody should spend Module 5 wondering why the
Gateway disappeared. If you fall behind, 4 and 5 are the ones to demonstrate
rather than have everyone run.

Do not read the setup line out. It is on the screen so people know what is
coming, and the setup pages have the actual steps. Two things are worth saying
about it anyway.

First, everyone gets their own database. Resist the temptation to hand out a
shared one. When everyone reads the same graph, one person's mistake is
invisible to them and every later module appears to work.

Second, verify.py runs eight checks before Module 1: Python version, imports,
settings, AWS credentials, the hero hotel in the graph, and each of the three
Bedrock models. Tell the room to read the first failure rather than the last.
-->

---

<style scoped>
/* Four rows of two-column prose sit just under the theme's 29px. */
section { font-size: 26px; }
</style>

## Neo4j and AWS: What Each Platform Brings

| Component | Role in this workshop |
|---|---|
| **Neo4j Aura** | Stores connected hotel facts, source text, indexes, business rules, reservation requests, and memory |
| **Amazon Bedrock** | Provides Claude for extraction and reasoning, Amazon Nova for retrieval embeddings, Titan Text Embeddings V2 for memory |
| **Strands Agents** | Gives the model its tools and runs the agent loop |
| **AgentCore** | Exposes remote tools through Gateway and runs the deployed agent on Runtime |

The graph holds more than the retrieval corpus. Business rules and reservation requests live there too, and that is what makes the write path in Module 3 enforceable.

<!--
Give the two platforms parallel treatment. Neo4j is not a bolt-on to Bedrock
and Bedrock is not a bolt-on to Neo4j. The graph holds the facts and the rules,
Bedrock holds the reasoning and the embeddings, and neither can do the other's
job.

The closing line is the one that is worth slowing down for. Most agents keep
their business rules in a system prompt, where the rule and the reasoning share
one surface and the model can talk itself past either. Here a rule is data in
the same database as the booking, so Module 3 can check it inside the
transaction that writes.

The two agent layers arrive as the day goes on. The graph and the models are in
every module.
-->

---

<style scoped>
/* Seven rows of examples plus two closing paragraphs. */
section { font-size: 23px; }
</style>

## The Hotel Dataset

A fictional chain of AnyCompany hotels, one FAQ document per property.

| Node | Holds | Example |
|---|---|---|
| `Hotel` | `name`, `address`, `guest_rating`, `total_rooms` | AnyCompany Cairo Nile View |
| `Room` | `type`, `bed_configuration`, `max_occupancy`, rate range | Suite, one king bed |
| `Amenity` | `name`, unique across the graph | Full-Service Spa |
| `Policy` | `name`, `description` | 24-hour cancellation |
| `Service` | `name`, `cost`, `hours`, availability | Airport transfer |
| `Document` | `source_filename` | The FAQ file |
| `Chunk` | `text`, `embedding` | The searchable passage |

Hundreds of properties worldwide. These eight carry the workshop: Cairo, Chicago, Paris, Tokyo, Sydney, Rio de Janeiro, Cape Town, Prague.

You restore this from a prebuilt dump, and the dump deliberately ships with no vector index, no full-text index, and five hotels missing. Module 1 is where all three arrive.

<!--
The last line is the setup for Module 1. Participants often assume a prebuilt
graph means there is nothing to build. There is: the two indexes that every
later retrieval depends on, and five held-out documents to extract.

Cairo is deliberately not one of the five. Module 2's comparison has to work
identically for everyone, so it cannot depend on a participant's own extraction
run. The hero hotel, AnyCompany Cairo Nile View, also appears in the
environment check, in Module 3's grounded answer, and in the Module 5 smoke
tests. If someone sees it three times and asks, that is why.

Read the Amenity row out and stop there. The next slide is why it is written
that way.
-->

---

<style scoped>
/* Two code blocks and a closing comparison. */
section { font-size: 24px; }
</style>

## Amenity Is a Node, Not a Column

`Full-Service Spa` exists once. Every hotel that offers it points at that one node.

```cypher
MATCH (:Amenity {name: "Full-Service Spa"})<-[:OFFERS_AMENITY]-(h:Hotel)
RETURN h.name
```

Store the same fact as a list on each hotel and the question changes shape.

```cypher
MATCH (h:Hotel)
WHERE "Full-Service Spa" IN h.amenities
RETURN h.name
```

The second query can only ever answer "which hotels have this." The first can be walked in either direction: from a hotel to what it offers, or from an amenity to who offers it, and onward to whatever those hotels are connected to. Module 2's retrieval query depends on walking outward from whatever the search matched. That path does not exist in the second model.

<!--
Do not run these. They are on the screen to be read side by side.

The second query is the instinct most of the room brings in, because it is what
a column or a JSON array gets you, and it is not wrong. Do not argue it on
speed. At eight hotels, or at nine thousand, an index makes that scan fast
enough and someone in the room knows it. The argument is direction. A string in
a list is not addressable. Nothing attaches to it and nothing traverses out of
it, so the only question it can answer is the one it was written for.

Uniqueness is created at write time, not query time. Module 1's amenity parser
does MERGE on the name, which is the line of code that produces this shape. It
is also what collapses "Full-Service Spa," "Full Service Spa," and "Spa
(Full-Service)" into one node. Extraction produces all three spellings, and a
list column keeps all three, so every later query silently misses two of them.

This is also why the traversal in Module 2 stays short. A retrieval query that
lands anywhere near a hotel reaches everything a guest might ask about in one
hop. The hero question stacks four constraints, and here each one is another
hop that composes with the last.
-->

---

![bg contain](../images/foundations-grounded-request-flow.svg)

<!--
Walk this end to end, once, slowly. It is the only time today the whole path
is on one slide.

A question arrives at the Strands agent running Claude on Bedrock. The agent
calls search_hotel_knowledge. That tool embeds the query with Amazon Nova and
hits two Neo4j indexes, vector and full-text. The retrieval query then expands
from the matched chunk into the hotel and its properties. Context comes back,
and the model either answers from it or says the context cannot answer the
question.

The reservation write is not on this path at all. It runs beside the agent,
and the next slide is where you say who owns it.

The deployment changes three times across the day. This flow does not change
once.
-->

---

<style scoped>
/* Six rows of three-column prose. */
section { font-size: 21px; }
</style>

## The Model Owns One Row

| Control | Enforced by | If the model owned it instead |
|---|---|---|
| Which retriever runs | The application, chosen once in code | Eight retrievers described in a prompt, re-picked on every request |
| What the traversal returns | A fixed `retrieval_query` the model cannot edit | Cypher written by a text generator, against your live database |
| Rejecting an invalid or duplicate write | Neo4j, inside the transaction | You ask it nicely in the system prompt not to book a room that does not exist |
| Who can call AWS services | IAM, on the execution role | A credential handed to the model as a tool argument |
| Whose memory comes back | Cypher anchored at one guest | A prompt line asking it to ignore the other guests it can see |
| Answer or abstain | The model, from returned context only | Correct as it stands. Judging whether context answers a question is a language task |

In most agents shipped today, four of these six live in the right-hand column. Here, one does.

<!--
This is the workshop's signature slide. Everything after it is an
implementation of one row.

Ask the room where these controls live in their current agent, and wait. The
usual honest answer is the right-hand column, in a prompt, which is why that
column is written the way it is. None of those are straw men. Every one of them
ships.

The right-hand column is what makes the left one mean something. Ownership
without an alternative is just a description of the system.

Row two is the one to defend if someone pushes back. A fixed retrieval_query is
a security boundary, not a convenience. The alternative is not slower or
sloppier retrieval, it is arbitrary Cypher from a text generator running
against a live database, and no prompt makes that safe.

The model's row is the narrowest one and it is the one it is genuinely good at.
It answers from context, or it says it cannot. It does not choose the
retriever, write the traversal, or touch the database.

This table reuses cleanly with a different schema and a different domain, which
is the takeaway to name out loud.

Head to Setup. Every path ends in the same place: a terminal, four Neo4j
settings in CONFIG.txt, AWS credentials in us-east-1, and eight passing checks.
-->
