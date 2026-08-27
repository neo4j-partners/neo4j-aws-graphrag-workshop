# Canva Diagram Prompts

Use these prompts in [Canva's AI image generator](https://www.canva.com/ai-image-generator/) or Magic Media to create professional diagrams for this workshop. Set canvas size to **1600 × 900 px (16:9 landscape)** before generating. Export as PNG and save to this directory.

**Important:** Do not use the word "infographic" in prompts. It causes Canva AI to generate tall vertical layouts. Use "diagram", "illustration", or "visual" instead.

---

## Diagram 3: Retrieval Patterns Decision Tree
**Filename:** `02-select-retriever.svg`
**Editable source:** the SVG itself
**Dimensions:** 960 x 720 viewBox, rendered at `width=800`

This diagram is hand-authored SVG, in the same style as `01-graph-structure.svg`.
There is no separate editor file and no raster export. Edit the SVG directly and
the site picks the change up on the next build. Keep the `id` attributes on the
group elements because `tests/test_module2_diagrams.py` checks the retrieval
roles and resolves the Chicago example through `branch-fixed-cypher`.

**Design contract:**
```
TITLE: "Build retrieval one capability at a time."

THREE COLUMNS pair an entry search with its graph-enriched form:

VECTOR COLUMN (purple):
1. `VectorRetriever` finds chunks by embedding similarity.
2. `VectorCypherRetriever` adds a reviewed graph traversal.

FULL-TEXT COLUMN (blue):
3. Full-Text Search finds chunks through a Neo4j full-text index.
4. Full-Text + Cypher adds a reviewed traversal. Label it as a parameterized
query or custom retriever, not as a packaged Python class.

HYBRID COLUMN (teal):
5. `HybridRetriever` fuses vector and full-text results.
6. `HybridCypherRetriever` adds a reviewed traversal and is the workshop choice.

BOTTOM ROW contains the two direct domain-graph paths:
7. Cypher Templates (amber, id "branch-fixed-cypher") uses the Chicago hotels
with a spa and swimming pool example.
8. `Text2CypherRetriever` (amber dashed outline, id "optional-text2cypher")
generates Cypher from a question and schema.

The footer states that all eight paths read the same Neo4j knowledge graph.

Style: white card with a warm border and soft shadow, Helvetica stack, flat fills,
one hue per branch, metadata labels in small caps.
```

---

## Diagram 4: Grounded Agent Overview
**Filename:** `03-grounded-agent-overview.svg`
**Editable source:** the SVG itself
**Dimensions:** 900 x 540 viewBox, rendered at `width=800`

This diagram is hand-authored SVG, in the same style as
`foundations-grounded-request-flow.svg`. There is no editor file and no raster
export. Edit the SVG directly and the site picks the change up on the next build.

**Design contract:**
```
TITLE: "The Grounded Booking Agent"
SUBTITLE: "The model chooses a read path. A separate application command writes."

TOP LANE, "READ PATH: ANSWER A QUESTION":
You -> Strands agent, which reads both tool specifications and chooses one or
both of these paths:
1. search_hotel_passages -> source text and linked hotel facts.
2. query_hotel_records -> model-generated Cypher whose plan is checked with
EXPLAIN before Neo4j runs it.
Both paths reach Neo4j. A return arrow carries bounded JSON evidence and a
shared grounding verdict back to the agent. A dark bar closes the lane with
the prompt policy and the trace boundary: answer from evidence or state what is
missing; inspect the trace to see whether a tool call and verdict happened.

BOTTOM LANE, "WRITE PATH: RECORD A RESERVATION REQUEST", left to right:
Reservation command (application code, not an agent tool) -> Rule check in Neo4j
(at most 10 guests) -> Write in one transaction (one request_id, one saved
request).

FOOTER: "Module 3 registers no write tool."

Style: white background, Helvetica stack, flat fills, Neo4j blue for graph
boxes, teal for the tool, dark navy for the outcome bar.
```

---

## Diagram 5: The Retrieval Substrate
**Filename:** `retrieval-substrate.svg`
**Editable source:** the SVG itself
**Dimensions:** 960 x 540 viewBox, rendered at `width=800`

Hand-authored SVG in the style of `01-graph-structure.svg`, and deliberately so.
That diagram shows the build writing the two layers. This one shows retrieval
crossing the same two layers in the opposite direction, so the band labels and
the palette are reused on purpose.

**Design contract:**
```
TITLE: "Retrieval crosses the same graph in reverse"
SUBTITLE: "The build wrote FROM_CHUNK out of Hotel. Search enters at Chunk and
follows that relationship back."

A neutral question pill sits above the bands, inside the card and outside the
graph: "cancellation policy for the hotel at 60611".

TOP BAND, "THE LEXICAL LAYER: THE TEXT": the two named indexes,
hotel_chunk_embeddings and hotel_chunk_fulltext, both arrowing into (:Chunk).
(:Document) sits above (:Chunk) with FROM_DOCUMENT pointing up, the direction
it was written. A side panel gives both Cypher patterns: BUILD WROTE
(:Hotel)-[:FROM_CHUNK]->(:Chunk), SEARCH READS (node)<-[:FROM_CHUNK]-(hotel:Hotel).

THE CROSSING: one heavy arrow down from (:Chunk) to (:Hotel), badged
"FROM_CHUNK, FOLLOWED IN REVERSE".

BOTTOM BAND, "THE DOMAIN LAYER: THE FACTS": (:Hotel) as a filled hub with all
four typed edges. OFFERS_AMENITY and (:Amenity) are solid because the shipped
traversal collects them. HAS_ROOM, HAS_POLICY, and PROVIDES_SERVICE are dashed
and gray, one hop away but not collected.

FOOTER: the returned record from the Module 2 teaching retrieval_query, in
order, ending at field_provenance.

Style: white card, Helvetica stack, the blue family from 01-graph-structure.svg
and nothing outside it.
```

---

## Diagram 6: Preference Provenance
**Filename:** `06-preference-provenance.svg`
**Editable source:** the SVG itself
**Dimensions:** 960 x 540 viewBox, rendered at `width=800`

Hand-authored SVG. Its job is to separate what the memory library writes from
what `memory_helpers.py` writes, because that split is the module's argument.

**Design contract:**
```
TITLE: "A preference points back at the message it came from"
SUBTITLE: "The library writes the memory nodes. Two workshop relationships are
what make one preference traceable."

TOP BAND, "WHAT THE AGENT REMEMBERS": (:User {identifier}) -[:HAS_PREFERENCE]->
(:Preference {preference, category, id}), and (:Preference)-[:ABOUT_HOTEL]->
(:Hotel {name}), noted as the same node Module 1 created.

BOTTOM BAND, "THE EVIDENCE IT CAME FROM": (:Conversation {session_id})
-[:HAS_MESSAGE]-> (:Message {content}), with (:Preference)-[:DERIVED_FROM]->
(:Message) crossing between the bands.

DERIVED_FROM and ABOUT_HOTEL are the two edges drawn in blue, because they are
the two that memory_helpers.py writes. Everything else is the library's.

PANEL, "ONE QUERY RETURNS": actor, preference, hotel, source_message,
source_session, the aliases from the module's recall query.

Style: white card, Helvetica stack, the palette from 01-graph-structure.svg,
(:Preference) and (:Hotel) as filled hubs.
```

---

## Usage Notes

- Set canvas to **1600 × 900 px (landscape 16:9)** before generating. This locks the horizontal format.
- Export as **PNG** (not JPEG) to preserve sharp text edges.
- After saving, reference in workshop content with\:
  `:image[Alt text]{src="../../images/FILENAME.png" width=800}`
- All diagrams use brand-neutral colors. Do not include logos other than Neo4j and AWS marks.
