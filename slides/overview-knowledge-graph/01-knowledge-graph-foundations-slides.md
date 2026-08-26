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

# Knowledge Graphs and AuraDB

What a property graph is, and where this one runs

<!--
Two movements. The first runs from "What Is a Graph Database" through "Beyond
Hotels": nodes, relationships, Cypher, and why the hotel schema looks the way
it does. The second is "Neo4j Aura" and "Aura Developer Tools": the product,
the tools you get, and what the Free tier omits.

Announce the split. Attendees who already know graphs can relax through the
first half, and the ones who do not will not think the whole day is theory.

Do not explain retrieval here. Deck 5 owns vectors, hybrid search, and
retrievers. This deck only has to make the graph feel like a normal database.
-->

---

## Where We Left Off

Deck 1 named a question that no single passage of text answers. The answer lives in the connections between facts, so this deck is what a graph actually is.

<!--
One line, said quickly. This is the recall slide.
-->

---

## What Is a Graph Database

Three structures, and that is the whole model:

- **Node:** A node is a thing, such as a hotel, a room, an amenity, a document, or a text chunk
- **Relationship:** A relationship is a named, directed connection between two nodes
- **Property:** A property is a named value stored on a node or on a relationship

The relationship is stored, not computed. Following one is a pointer hop, not a join.

<!--
The last line is the one that matters to anyone who has tuned a relational
database. In a relational store the connection between two rows is derived at
query time by matching values. In a property graph it is written down once and
traversed directly, so the cost of a hop does not grow with the size of the
table on the other side.

That single property is why the multi-hop questions later in the day are cheap
here and expensive in SQL.
-->

---

## Graph Notation

Cypher is Neo4j's query language. A pattern is written the way it is drawn:

```cypher
(:Hotel {name: "AnyCompany Cairo Nile View"})
    -[:OFFERS_AMENITY]->
(:Amenity {name: "Full-Service Spa"})
```

- **Parentheses** describe nodes
- **`:Hotel`** is a label, the node's type
- **Square brackets** describe relationships
- **The arrow** carries direction
- **Braces** hold properties

<!--
Read the pattern out loud as an English sentence: this hotel offers this
amenity. Cypher's whole design bet is that a query should look like the shape
it is looking for.

Point out that direction is stored but rarely required at query time. You can
match the pattern in either direction, and Module 2's retrieval queries do.
-->

---

## From Graph Database to Knowledge Graph

A graph database gives you the structures. A knowledge graph adds an agreement about what they mean.

- **Typed entities:** Five labels carry the whole domain, `Hotel`, `Room`, `Amenity`, `Policy`, and `Service`
- **Typed relationships:** Each edge is named for what it means, such as `OFFERS_AMENITY`, `HAS_POLICY`, and `FROM_CHUNK`
- **A schema a domain expert recognizes:** the labels are the business's own words
- **Provenance:** every extracted fact keeps a link back to the text it came from

The schema is the contract. Module 1 pins it so extraction cannot invent new labels.

<!--
Attendees often expect an ontology project here. There is not one. The schema
in this workshop is a Python dictionary of five node types with their property
names, and it fits on one screen.

The provenance bullet is worth a beat. It is what turns "the model said so"
into "this document said so, and here it is." Module 3 shows the answer
carrying its source filename.
-->

---

## Graphs and Relational Databases: The Easy Question

"What amenities does the Cairo hotel have?"

Both databases answer this well.

- **Relational:** join the hotel table to the amenity join table to the amenity table
- **Graph:** `MATCH (h:Hotel)-[:OFFERS_AMENITY]->(a:Amenity)`

Nobody switches databases over this question.

<!--
Be genuinely fair here. Single-hop lookups with a known key are what relational
databases are excellent at, and a room full of engineers will stop trusting you
if you pretend otherwise.

Set up the contrast honestly, then let the next slide do the work.
-->

---

<style scoped>
/* Two code blocks plus framing prose. */
section { font-size: 24px; }
</style>

## Graphs and Relational Databases: The Hard Question

"Which Chicago hotels have both a spa and a pool, and what is their cancellation policy?"

```sql
SELECT h.name
FROM hotel h
JOIN hotel_amenity ha1 ON ha1.hotel_id = h.id
JOIN amenity a1 ON a1.id = ha1.amenity_id AND a1.name = 'Full-Service Spa'
JOIN hotel_amenity ha2 ON ha2.hotel_id = h.id
JOIN amenity a2 ON a2.id = ha2.amenity_id AND a2.name = 'Outdoor Swimming Pool'
WHERE h.address LIKE '%Chicago%';
```

Correct, and it still does not have the cancellation policy. That needs two more joins.

<!--
Walk the joins. Two amenities means the amenity tables appear twice, aliased,
and every additional condition adds another pair. The query grows by the
condition, not by the answer.

Then point at the shape of the growth. Adding the policy adds a hotel_policy
table and a policy table, so the query is eight joins for a question a guest
would ask in one breath. Nothing here is beyond SQL. The cost is that the
query text grows with the number of conditions rather than with the answer.
-->

---

## The Same Question in Cypher

```cypher
CYPHER 25
MATCH (h:Hotel)-[:OFFERS_AMENITY]->(:Amenity {name: "Full-Service Spa"})
MATCH (h)-[:OFFERS_AMENITY]->(:Amenity {name: "Outdoor Swimming Pool"})
WHERE h.address CONTAINS "Chicago"
OPTIONAL MATCH (h)-[:HAS_POLICY]->(p:Policy)
RETURN h.name AS hotel, collect(p.name) AS policies
```

Each condition is one more line, not one more pair of joins.

The question SQL cannot reach is the next one. "Which other hotels offer this amenity" is one hop from a node you already hold.

<!--
Cypher glossary, for the room that has not seen it:

MATCH selects a pattern. Two MATCH clauses sharing the variable h mean both
patterns must hold for the same hotel, which is how the AND is guaranteed.

OPTIONAL MATCH keeps the hotel in the result even when the pattern does not
match, the way a LEFT JOIN does. Module 2's retrieval queries use it
everywhere, because a missing policy should not delete a hotel from the
results.

collect aggregates matched rows into a list, so one row comes back per hotel
rather than one per policy.

WHERE filters. RETURN names the fields the application receives.

CYPHER 25 pins the language version, so the query means the same thing on any
server the workshop runs against. Every Cypher query in the workshop carries it.

That is enough Cypher to read every query in this deck. Modules 2 and 6 add
CALL, WITH, and MERGE, and each one is introduced where it is first used.
-->

---

<style scoped>
/* Seven rows with examples. */
section { font-size: 24px; }
</style>

## The Hotel Knowledge Graph

| Label | Represents | Key properties |
|---|---|---|
| `Hotel` | One hotel in the chain | `name`, `address`, `guest_rating` |
| `Room` | A bookable room type | `type`, `max_occupancy`, `min_rate`, `max_rate` |
| `Amenity` | A facility, unique across the graph | `name` |
| `Policy` | A rule that governs a stay | `name`, `description` |
| `Service` | Something the hotel provides, free or paid | `name`, `cost`, `hours` |
| `Document` | One source FAQ file | `source_filename` |
| `Chunk` | A searchable passage of that file | `text`, `embedding` |

`Document` and `Chunk` are the lexical layer. Everything else is the domain layer.

<!--
The two-layer split is the single most important structural idea in the
workshop's schema, and Module 1's deck takes it apart in detail. Name it here
and move on.

Amenity being unique across the graph is the second thing to flag. Two hotels
with a spa point at the same Amenity node, so "which other hotels have this"
is one hop from a node you already have.
-->

---

![bg contain](../images/01-graph-structure.svg)

<!--
Left side, the lexical layer: a source file becomes a Document, which holds
Chunks, and each Chunk carries the text and its embedding.

Right side, the domain layer: a Hotel with typed relationships out to Room,
Amenity, Policy, and Service.

The line between them is FROM_CHUNK, and it is the whole reason this schema
works for retrieval. Search finds a Chunk by meaning. The traversal crosses
into the domain layer and returns structured facts. The same edge run backward
is the provenance answer.

Hotel is the hub, and every domain fact about a stay is one hop away. That
shape is deliberate. A retrieval query that lands anywhere near a hotel reaches
everything a guest might ask about in a single hop, which keeps the traversal
in Module 2 short and its returned context small.

Ask the room what happens if you also want to answer "which hotels are near
this attraction." You add a node type and an edge. You do not migrate a schema.

Deck 5 will put a retrieval path on top of this exact picture.
-->

---

## Why This Schema Design

Typed relationships over one generic `RELATES_TO`:

- **Relationship types are part of the stored structure.** Property values on a generic edge are not
- **The traversal reads as the question.** `OFFERS_AMENITY` says what the edge means
- **Extraction gets a smaller target.** A model choosing among four named relationships beats a model inventing them

Cost of the choice: the schema has to be decided before extraction runs.

<!--
The performance point is concrete. Traversing OFFERS_AMENITY visits only the
amenity edges out of that hotel. Traversing RELATES_TO and filtering on
type = 'amenity' visits every edge out of that hotel and then discards most of
them. The gap grows with the density of the node.

The last line is honest and it sets up Module 1. Pinning the schema is the fix
for extraction drift, and it means you own the modeling decision up front.
-->

---

<style scoped>
/* Four rows of domain examples. */
section { font-size: 25px; }
</style>

## Beyond Hotels

The same shape, three other domains:

| Domain | The hub | One hop away | The question a graph answers |
|---|---|---|---|
| **Fraud** | Account | Device, address, phone | Which accounts share a device |
| **Customer 360** | Customer | Order, ticket, contract | What happened before they churned |
| **Supply chain** | Part | Supplier, plant, shipment | What breaks if this supplier stops |
| **Hotels** | Hotel | Amenity, policy, room | Which hotels share this amenity |

Shared entities plus multi-hop questions. That is the pattern worth taking home.

<!--
This is the transfer slide. Nobody in the room is building a hotel booking
assistant, so say plainly what generalizes: a hub entity, shared nodes that
several hubs point at, and questions whose answers span more than one hop.

If a domain in the room does not have those two things, a graph may not be the
right tool, and saying so buys credibility for the cases where it is.

This closes the concept half of the deck. The rest is product.
-->

---

## Neo4j Aura

Neo4j as a managed service, with no server for you to run.

That is the model. This is where your copy of it lives.

- **AuraDB Free:** The tier takes no card, runs no cluster you manage, and gives one database per instance
- **`neo4j+s://` only:** Every connection is encrypted, and Aura offers no unencrypted alternative
- **Restore from a dump file:** the workshop graph loads through the console
- **Everything in this workshop runs on the Free tier**

You create your own instance. It is not shared with anyone else in the room.

<!--
The last line is the setup slide's argument in advance. A shared database hides
individual mistakes until the last module. A personal one surfaces them
immediately.

If someone asks about the paid tiers, the honest short answer is that Aura
Professional adds sizing, snapshots on demand, and cloud region choice, and
that none of the day depends on any of it.
-->

---

## Aura Developer Tools

- **Query:** Query runs Cypher and shows results as a table or as a rendered graph
- **Explore:** Explore lets you click through the graph without writing Cypher
- **Restore:** The Restore tab loads the workshop graph from a dump file

Two Free-tier limits worth knowing now:

- **An idle instance pauses after three days.** A paused instance refuses connections, which reads exactly like a wrong URI
- **200,000 nodes and 400,000 relationships.** The workshop graph sits far under both

<!--
Tell the room to open Query at least once during Setup, run the hero-hotel
check, and look at the rendered graph. Seeing their own restored data as a
picture does more for intuition than any slide here.

The pause limit is the single most common support question. Say it now, and
say it again to anyone who comes back from a long break with a connection
error.
-->

---

## Where the Graph Goes Next

The graph you are about to restore is the one every module reads:

- **Module 1** adds two indexes and five more hotels to it
- **Module 2** retrieves from it eight different ways
- **Module 3** grounds an agent in it, and writes a reservation into it
- **Module 6** writes guest preference memory into the same graph
- **Modules 4 and 5** change where the code runs, and not the graph

One database carries all six modules. You never create a second one.

<!--
This is the forward pointer. It also answers the question people are holding:
whether they are about to accumulate a pile of infrastructure. They are not.
One Aura instance and one AWS account carry the entire day.

Next up is the dataset and the environment, and then you build the instance
this deck has been describing.
-->
