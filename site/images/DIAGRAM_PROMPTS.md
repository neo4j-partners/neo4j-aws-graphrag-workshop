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

## Diagram 4: Grounded Agent Architecture
**Filename:** `03-grounded-agent-architecture-context.png`
**Dimensions:** 1600 × 900 px (16:9)

**Canva prompt:**
```
Clean architecture diagram on white background showing responsibility separation between Neo4j and AWS.

TWO-ZONE LAYOUT divided by a vertical dashed line:

LEFT ZONE labeled "Neo4j Aura" (cyan/teal theme, #4581C3):
Header: Neo4j logo + "Knowledge + Rules"

Boxes from top to bottom:
1. "Hotel Knowledge Graph" - network nodes icon
   (hotels, amenities, ratings, policies)
2. "Vector Index: hotel_chunk_embeddings" - cylinder icon
3. "Full-text Index: hotel_chunk_fulltext" - text search icon
4. "HybridCypherRetriever" - fixed traversal icon
5. "Maximum-Guests Rule (cap: 10)" - shield/rule icon
6. "Idempotent ReservationRequest Write" - database write icon

RIGHT ZONE labeled "Amazon Bedrock" (orange theme, #FF9900):
Header: AWS logo + "Reasoning only"

Boxes from top to bottom:
1. "Amazon Nova 2 Embeddings" - vector icon
   (1024-dim query embedding)
2. "Claude Sonnet" - brain/LLM icon
   (reasons over retrieved context only)
3. "Strands Agent" - tool calling icon
   (tool: search_hotel_knowledge_tool)

CENTER (connecting the zones):
Arrow from Neo4j retrieval → Bedrock: "Bounded context JSON"
Arrow from Bedrock decision → Neo4j write: "Validated command input"

BOTTOM BAR: "The LLM never sees the write path. Rules are enforced by the graph."

Style: AWS architecture style, two-tone zones, flat icons, clean labels, professional workshop look
```

---

## Usage Notes

- Set canvas to **1600 × 900 px (landscape 16:9)** before generating. This locks the horizontal format.
- Export as **PNG** (not JPEG) to preserve sharp text edges.
- After saving, reference in workshop content with\:
  `:image[Alt text]{src="../../images/FILENAME.png" width=800}`
- All diagrams use brand-neutral colors. Do not include logos other than Neo4j and AWS marks.
