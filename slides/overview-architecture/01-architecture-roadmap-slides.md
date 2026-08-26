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

Two halves. First the dataset and the environment, which is orientation.
Then the control-ownership table, which is the workshop's actual argument
stated once, early, so the later modules can point back at it.
-->

---

## Where We Left Off

Deck 2 showed what a property graph is and where one runs. This deck is the data you put in it, and who owns which control over that data.

<!--
One line, said quickly. This is the recall slide.
-->

---

## What You Will Build

Six modules, six verbs:

1. **Build** a knowledge graph from hotel documents into your own Aura instance
2. **Compare** eight retrieval patterns and pick one for the application
3. **Ground** an agent in that retriever, and give it a write path it cannot reach
4. **Publish** the retrieval tools through AgentCore Gateway, on the Model Context Protocol
5. **Deploy** the whole agent to AgentCore Runtime as a container
6. **Remember** guest preferences in the same graph, with provenance

<!--
Deck 1's thesis, restated: the model does not get smarter across these six
steps.
What changes is what it can see and what it is allowed to do.

Modules 4 and 5 are two different deployments of the same design, not a
progression. Say that now so nobody spends Module 5 wondering why the Gateway
disappeared.
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

Four roles. The graph and the models are in every module. The two agent layers arrive as the day goes on.

<!--
Give the two platforms parallel treatment here. Neo4j is not a bolt-on to
Bedrock and Bedrock is not a bolt-on to Neo4j. The graph holds the facts and
the rules; Bedrock holds the reasoning and the embeddings; neither can do the
other's job.

The row that surprises people is the first one. Business rules and reservation
requests live in the graph too, not just the retrieval corpus. That is what
makes the write path in Module 3 enforceable.
-->

---

<style scoped>
/* Seven rows of examples need room. */
section { font-size: 24px; }
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

Hundreds of properties worldwide. These eight carry the workshop:

Cairo, Chicago, Paris, Tokyo, Sydney, Rio de Janeiro, Cape Town, Prague.

<!--
Amenity is the row to point at. It is unique across the graph, so two hotels
offering a spa connect through one Amenity node. That single modeling choice
is what makes "which hotels share this amenity" a one-hop traversal instead
of a scan. Deck 2 made the same point from the schema side.

The hero hotel, AnyCompany Cairo Nile View, appears in the environment check,
in Module 3's grounded answer, and in the Module 5 smoke tests. If someone
sees it three times and asks, that is why.
-->

---

## Workshop Infrastructure: Shared

Provisioned before the event. You never touch these:

- **Amazon Bedrock models** in **us-east-1**, three of them
- **The prebuilt graph dump**, a release artifact you restore rather than build
- **The Vocareum lab definition**, if you are at a hosted event

The dump deliberately ships with no vector index, no full-text index, and five hotels missing.

<!--
The last line is the setup for Module 1. Participants often assume a prebuilt
graph means there is nothing to build. There is: the two indexes that every
later retrieval depends on, and five held-out documents to extract.

Cairo is deliberately not one of the five. Module 2's comparison has to work
identically for everyone, so it cannot depend on a participant's own
extraction run.
-->

---

## Workshop Infrastructure: Personal

Yours, and yours alone:

- **A Neo4j AuraDB Free instance** you create and restore yourself
- **An AWS account**, either a Vocareum seat or your own
- **`CONFIG.txt`**, four Neo4j settings and a region

A broken restore shows up in Module 1 as an empty result. That is the point.

<!--
Resist the temptation to hand out a shared database. When everyone reads the
same graph, one person's mistake is invisible to them and every later module
appears to work. Here it does not, and they find out immediately.

Eight checks in environment/verify.py gate the first module: Python version,
imports, settings, AWS credentials, the hero hotel in the graph, and each of
the three Bedrock models. Tell the room to run it before Module 1 and to read
the first failure rather than the last.
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
/* Six rows of two-column prose. */
section { font-size: 25px; }
</style>

## Who Owns Which Control

Each control belongs to the layer that can actually enforce it:

| Control | Owner |
|---|---|
| Which retriever runs | The **application**, chosen once |
| Answer or abstain | The **model**, from returned context only |
| What the traversal returns | The fixed **`retrieval_query`** |
| Rejecting an invalid or duplicate write | **Neo4j**, in the transaction |
| Who can call AWS services | **IAM** |
| Whose memory comes back | **Cypher scoped to one guest** |

<!--
This is the workshop's signature slide. Everything after it is an
implementation of one of these six rows.

Notice what the model owns: one row, and it is the narrowest one. It answers
from context, or it says it cannot. It does not choose the retriever, write
the traversal, or touch the database.

Ask the room where these controls live in their current agent. The usual
honest answer is that the model owns four of the six, in a prompt.

This table reuses cleanly with a different schema and a different domain,
which is the takeaway to name out loud.
-->

---

## Workshop Roadmap

**Foundations and Setup**
Property graph model, Cypher, Aura instance, verified Bedrock access

**Modules 1 and 2: the graph and the retrieval**
Extract five documents, create both indexes, compare eight retrieval patterns

**Modules 3, 4, and 5: three deployments of one design**
Local agent, remote tools through Gateway, whole agent on Runtime

**Module 6: memory**
Preference memory with provenance, in the same graph

<!--
The middle group is where the day's understanding is built and the last two
groups are where it gets deployed. If you fall behind, Modules 4 and 5 are
the ones to demonstrate rather than have everyone run.

Head to Setup. Every path ends in the same place: a terminal, four Neo4j
settings in CONFIG.txt, AWS credentials in us-east-1, and eight passing checks.
-->
