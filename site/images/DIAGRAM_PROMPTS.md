# Canva Diagram Prompts

Use these prompts in [Canva's AI image generator](https://www.canva.com/ai-image-generator/) or Magic Media to create professional diagrams for this workshop. Set canvas size to **1600 × 900 px (16:9 landscape)** before generating. Export as PNG and save to this directory.

**Important:** Do not use the word "infographic" in prompts. It causes Canva AI to generate tall vertical layouts. Use "diagram", "illustration", or "visual" instead.

---

## Diagram 3: Retrieval Patterns Decision Tree
**Filename:** `02-retrieval-decision-tree.png`
**Editable source:** `02-retrieval-decision-tree.excalidraw`
**Dimensions:** 1600 × 900 px (16:9)

The checked-in Excalidraw file is the authoritative source. Open it in
Excalidraw and export a 1600 × 900 PNG after editing. Copy the source and export
to both image trees, then run the repository checker to verify byte equality.

**Design contract:**
```
Modern flowchart decision tree on a white background with pastel node colors.

START: Diamond shape "What evidence does the question need?" at top

FOUR WORKSHOP BRANCHES flowing down, plus one separate optional extension:

BRANCH 1 (leftmost, purple):
Label: "Semantic or paraphrased source lookup"
Arrow to rounded rectangle: "VectorRetriever"
Sub-label: "embedding similarity"
Evidence: ranked source Chunks and scores
Example: "When does arrival processing begin?"

BRANCH 2 (left-center, blue):
Label: "Exact name, code, or ID"
Arrow to rounded rectangle: "HybridRetriever"
Sub-label: "vector plus full-text relevance"
Evidence: semantic score and exact-term hits
Example: "Find the policy for ZIP 60611"

BRANCH 3 (right-center, teal):
Label: "Semantic match plus connected facts"
Arrow to rounded rectangle: "VectorCypherRetriever"
Steps: semantic match finds a Chunk node, reviewed traversal expands the graph,
then named fields include provenance
Example: "Amenities and rating for the Cairo hotel"

BRANCH 4 (rightmost, orange):
Label: "Reviewed structured filtering"
Arrow to rounded rectangle: "Reviewed fixed Cypher"
Sub-label: "application-owned query over named fields and relationships"
Evidence: reviewed Cypher and database records
Example: "Chicago hotels with a spa and pool"

BOTTOM ROW: All four arrows connect to a final box "Neo4j Knowledge Graph."

SEPARATE OPTIONAL EXTENSION (orange dashed outline):
Arrow from the start diamond to "Optional: Text2CypherRetriever"
Sub-label: "Model-generated read-only Cypher for flexible questions"

Style: clean sans-serif font, flat design, white background, colored borders
matching branch colors
```

---

## Diagram 4: Grounded Agent Architecture
**Filename:** `03-grounded-agent-architecture.png`
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
   (reasons over retrieved evidence only)
3. "Strands Agent" - tool calling icon
   (tool: search_hotel_knowledge_tool)

CENTER (connecting the zones):
Arrow from Neo4j retrieval → Bedrock: "Bounded evidence JSON"
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
