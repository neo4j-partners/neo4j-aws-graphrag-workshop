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
SUBTITLE: "One tool reads the graph. A separate command writes to it."

TOP LANE, "READ PATH: ANSWER A QUESTION", left to right:
You -> Strands agent (Claude on Amazon Bedrock) -> search_hotel_knowledge
(the agent's only tool) -> Neo4j (hotel graph and indexes).
A return arrow carries "hotel facts, as JSON" from Neo4j back to the agent.
A dark bar closes the lane: the agent answers from those facts only, and says
the graph does not have the answer when they do not cover the question.

BOTTOM LANE, "WRITE PATH: MAKE A RESERVATION", left to right:
Reservation command (your Python code, not the model) -> Rule check in Neo4j
(at most 10 guests) -> Write in one transaction (one request_id, one saved
request).

FOOTER: "The model never writes to the graph."

Style: white background, Helvetica stack, flat fills, Neo4j blue for graph
boxes, teal for the tool, dark navy for the outcome bar.
```

---

## Usage Notes

- Set canvas to **1600 × 900 px (landscape 16:9)** before generating. This locks the horizontal format.
- Export as **PNG** (not JPEG) to preserve sharp text edges.
- After saving, reference in workshop content with\:
  `:image[Alt text]{src="../../images/FILENAME.png" width=800}`
- All diagrams use brand-neutral colors. Do not include logos other than Neo4j and AWS marks.
