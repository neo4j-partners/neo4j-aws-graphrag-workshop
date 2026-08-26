---
title: "Module 2: From Vector Search to Graph-Enriched Retrieval"
weight: 30
---

This module introduces retrieval in the order that each new pattern builds on the previous one. It starts with vector search, adds a reviewed graph traversal, introduces full-text search and its graph-enriched form, combines vector and full-text signals with hybrid retrieval, and finishes with two structured-query patterns.

Take the question "Which Chicago hotels offer both a spa and a swimming pool?" A similarity search ranks passages by how closely they match the question's meaning. It cannot guarantee that two amenity conditions apply to the same `Hotel` node. A Cypher query can test both relationships as exact conditions.

**Retrieval order in this module**

| Order | Name | Type | Best for |
|-------|------|------|----------|
| 1 | `VectorRetriever` | neo4j-graphrag retriever | Questions phrased differently from the source text |
| 2 | `VectorCypherRetriever` | neo4j-graphrag retriever | Semantic matches that need connected graph facts |
| 3 | Full-text search | Neo4j search method | Exact terms such as postal codes, IDs, and names |
| 4 | Full-text search with Cypher traversal | Neo4j query pattern | Exact-term matches that need connected graph facts |
| 5 | `HybridRetriever` | neo4j-graphrag retriever | Questions that need both meaning and an exact term |
| 6 | `HybridCypherRetriever` | neo4j-graphrag retriever | Hybrid matches that need connected graph facts |
| 7 | Cypher Templates | GraphRAG pattern | Known structured conditions |
| 8 | `Text2CypherRetriever` (optional) | neo4j-graphrag retriever | Flexible structured questions with no predefined query |

Vector, full-text, and hybrid describe how a matching `Chunk` is found. A Cypher traversal describes what happens after that match. Cypher Templates and Text2Cypher take a different path: they query the domain graph directly instead of starting with chunk similarity.

## The Lexical Graph and the Domain Graph

Module 1 wrote two connected graph structures.

* **Lexical graph:** `Document` nodes hold source files. `Chunk` nodes hold searchable text and 1024-dimension embeddings.
* **Domain graph:** `Hotel` nodes hold `name`, `address`, and `guest_rating`. The `HAS_ROOM`, `OFFERS_AMENITY`, `HAS_POLICY`, and `PROVIDES_SERVICE` relationships connect other hotel facts.
* **Entity provenance:** Extraction writes `(:Hotel)-[:FROM_CHUNK]->(:Chunk)`. Retrieval starts at the chunk and follows this relationship in reverse as `(node)<-[:FROM_CHUNK]-(hotel:Hotel)`.
* **Text provenance:** `(node)-[:FROM_DOCUMENT]->(:Document)` connects the chunk to its source file.

Graph-enriched retrieval moves from the lexical graph to the domain graph. This step turns a matched chunk of text into hotel properties and source provenance.

:image[Two connected structures: the source file becomes a Document and Chunk in the lexical graph, and a Hotel node with typed Room, Amenity, Policy, and Service relationships in the domain graph]{src="../../images/01-graph-structure.svg" width=800}

## The neo4j-graphrag Retriever Library

The :link[neo4j-graphrag]{href="https://neo4j.com/docs/neo4j-graphrag-python/current/" external=true} library supplies the retriever classes used by the notebook and the application path that follows it. Across those paths, the workshop uses these classes\:

:::code{language=python}
from neo4j_graphrag.retrievers import (
    HybridCypherRetriever,
    HybridRetriever,
    Text2CypherRetriever,
    VectorCypherRetriever,
    VectorRetriever,
)
from neo4j_graphrag.types import RetrieverResultItem
:::

The four index-backed retrievers expose the same `search()` method and vary along two dimensions\:

| Initial retrieval | Return the matched chunk | Run a reviewed traversal from the chunk |
|-------------------|--------------------------|------------------------------------------|
| Vector | `VectorRetriever` | `VectorCypherRetriever` |
| Vector plus full-text | `HybridRetriever` | `HybridCypherRetriever` |

A standalone full-text search and a full-text-plus-Cypher query use Neo4j's full-text procedure directly. The installed `neo4j-graphrag` Python API does not give those two paths separate retriever class names.

For each index-backed retriever, `search()` performs the applicable steps\:

1. Embed the question with Amazon Nova when the retriever has a vector arm.
2. Query `hotel_chunk_embeddings`, `hotel_chunk_fulltext`, or both.
3. Run the supplied `retrieval_query` for each matched chunk when using a Cypher retriever.
4. Map each record to a `RetrieverResultItem`.

* **`content`:** Holds the chunk text. The LLM reads this as context.
* **`metadata`:** Holds hotel properties for application checks, such as `metadata['hotel_id']`.
* **`result_formatter`:** Maps each query record into the `content` and `metadata` fields.

`Text2CypherRetriever` also exposes `search()` and returns `RetrieverResultItem` records, but it does not use a vector or full-text index. It asks a model to write Cypher from the graph schema.

Module 4 places the application retrievers' `search()` calls inside Lambda functions behind an AgentCore Gateway.

## 1. Vector Search with VectorRetriever

`VectorRetriever` turns text into numbers and compares those numbers.

* **Chunk:** A searchable slice of source text. The 12000-character setting is larger than the biggest 7,442-byte document, so each hotel FAQ becomes one chunk.
* **Embedding:** A numeric representation of meaning. Amazon Nova model `amazon.nova-2-multimodal-embeddings-v1:0` creates 1024 floats for each chunk.
* **Vector search:** Embeds the question and uses cosine similarity to find the closest vectors in `hotel_chunk_embeddings`.
* **`top_k`:** Sets the number of chunks returned. The notebook uses 3 for the arrival question and 5 for the vector and hybrid postal-code comparison.

A large chunk keeps the complete hotel in a single extraction prompt, but it also returns a whole document during search. `workshop/hybrid_retrieval.py` limits returned chunk text to 1,200 characters. A production design can use large extraction chunks and smaller retrieval chunks.

The first question asks when "standard arrival processing" begins at AnyCompany Cairo Nile View. The source text says "Standard check-in time." Vector search still finds the Cairo chunk because both phrases carry the same meaning. The result includes `3:00 PM`.

The query embedder must match the build settings: the same model, 1024 dimensions, and `GENERIC_INDEX` purpose. Both paths import these values from `workshop/retrieval_contract.py`. A mismatched configuration can return incorrect rows while still reporting success.

## 2. Graph-Enhanced Vector Search with VectorCypherRetriever

`VectorCypherRetriever` runs vector search first, then runs a reviewed `retrieval_query` for every matched chunk. Neo4j calls this GraphRAG pattern **Graph-Enhanced Vector Search**. The notebook uses this core query\:

:::code{language=cypher}
MATCH (node)-[:FROM_DOCUMENT]->(document:Document)
OPTIONAL MATCH (hotel:Hotel)-[:FROM_CHUNK]->(node)
OPTIONAL MATCH (hotel)-[:OFFERS_AMENITY]->(amenity:Amenity)
WITH node, score, document, hotel, collect(DISTINCT amenity.name) AS amenities
RETURN hotel.name AS hotel_name,
       hotel.hotel_id AS hotel_id,
       hotel.guest_rating AS guest_rating,
       document.source_filename AS source_filename,
       amenities,
       node.text AS source_chunk,
       score AS semantic_score,
       CASE WHEN hotel IS NULL THEN 'missing Hotel enrichment for semantic hit'
            ELSE 'complete Hotel enrichment' END AS graph_enrichment_status,
       {hotel_id: '(:Hotel)-[:FROM_CHUNK]->(:Chunk)',
        amenities: '(:Hotel)-[:OFFERS_AMENITY]->(:Amenity)'} AS field_provenance
ORDER BY semantic_score DESC, CASE WHEN hotel_id IS NULL THEN 1 ELSE 0 END, hotel_id
:::

The retriever puts `node` and `score` in scope before the retrieval query runs. `node` is the matched chunk, and `score` is its vector score.

* **`OPTIONAL MATCH`:** Keeps a strong chunk even when hotel extraction failed. `graph_enrichment_status` then reports the missing hotel.
* **`field_provenance`:** Maps each returned field to its graph path. For example, `amenities` comes from `(:Hotel)-[:OFFERS_AMENITY]->(:Amenity)`.
* **`source_filename`:** Names the source document so a reviewer can check an extracted value against the authored text.

A single top-level pattern cannot hold a one-to-many relationship safely: matching a hotel's amenities directly in the main pattern would return one row per amenity instead of one row per matched chunk. The shipped query avoids this by collecting the amenity list inside its own subquery\:

:::code{language=cypher}
CALL (hotel) {
    MATCH (hotel)-[:OFFERS_AMENITY]->(amenity:Amenity)
    WHERE amenity.name IS NOT NULL
    WITH DISTINCT amenity.name AS amenity_name
    ORDER BY amenity_name
    LIMIT 12
    RETURN collect(amenity_name) AS amenities
}
:::

The subquery returns one amenity list per hotel, so the traversal returns exactly one row per matched chunk no matter how many amenities the hotel has. A limit caps the list at 12 items (`contracts.MAX_AMENITIES` in `hybrid_retrieval.py`). Ordered tie-breaking and `head(collect(candidate))` select one hotel per chunk deterministically.

The comparison tests five hotel properties. `VectorRetriever` returns only chunk text. `VectorCypherRetriever` returns all five fields because it follows `FROM_CHUNK` to the `Hotel` node, where `hotel_id` exists as a graph property.

:::alert{type="info" header="Extraction defines the graph result"}
Graph enrichment returns facts written during extraction. Each result includes `source_filename`, so a missing or merged property can be checked against the authored document.
:::

## 3. Full-Text Search for Exact Terms

The second notebook question asks for the cancellation policy of the hotel at `60611`. A five-digit token carries little meaning on its own, so its embedding lands near many unrelated numbers. The notebook runs a `top_k=30` diagnostic scan and prints the Chicago chunk's vector rank to show how far down the list it falls.

Full-text search fixes this problem. It uses the Apache Lucene index `hotel_chunk_fulltext` over `Chunk.text`. Lucene breaks the text into tokens, matches literal terms, and assigns a relevance score. The rare token `60611` gets a strong score in the chunk that contains it.

* **Exact term:** `60611` matches the same literal token in the source.
* **Fuzzy term:** `Winward~` can match the misspelled hotel name `Windward`.
* **Boolean terms:** `spa AND pool` requires both terms. `OR` accepts either term, and `NOT` excludes a term.

Neo4j exposes standalone full-text lookup through a Cypher procedure\:

:::code{language=cypher}
CALL db.index.fulltext.queryNodes(
    'hotel_chunk_fulltext',
    '60611',
    {limit: 5}
)
YIELD node, score
RETURN node.text AS source_chunk, score AS fulltext_score
ORDER BY fulltext_score DESC
:::

This is a direct Neo4j search method. It is not a class named `FulltextRetriever` in the workshop's `neo4j-graphrag` Python version.

## 4. Full-Text Search with Cypher Traversal

Full-text search can also act as the entry point for graph-enriched retrieval. The query first finds matching `Chunk` nodes with the full-text index, then continues in the same Cypher statement from each `node` into the domain graph\:

:::code{language=cypher}
CALL db.index.fulltext.queryNodes(
    'hotel_chunk_fulltext',
    $query_text,
    {limit: $top_k}
)
YIELD node, score
MATCH (node)-[:FROM_DOCUMENT]->(document:Document)
OPTIONAL MATCH (hotel:Hotel)-[:FROM_CHUNK]->(node)
OPTIONAL MATCH (hotel)-[:OFFERS_AMENITY]->(amenity:Amenity)
RETURN node.text AS source_chunk,
       score AS fulltext_score,
       document.source_filename AS source_filename,
       hotel.name AS hotel_name,
       hotel.hotel_id AS hotel_id,
       collect(DISTINCT amenity.name) AS amenities
ORDER BY fulltext_score DESC
:::

This is a full-text Cypher retrieval pattern: full-text search selects the starting chunks, and reviewed Cypher adds connected facts. The workshop's Python dependency does not expose it as a separate `FulltextCypherRetriever` class, so an application implements it as a reviewed parameterized query or a custom retriever.

## 5. Hybrid Search with HybridRetriever

Vector and full-text search fail in opposite directions. Vector search handles paraphrases but can blur literal identifiers. Full-text search preserves literal identifiers but cannot match different wording by meaning. `HybridRetriever` runs both arms and combines their ranked results.

The notebook sends different input to each arm\:

:::code{language=python}
hybrid_identifier_result = hybrid_retriever.search(
    query_text='60611',
    query_vector=vector_identifier_result.metadata['query_vector'],
    top_k=IDENTIFIER_TOP_K,
    ranker='linear',
    alpha=0.2,
)
:::

* **`query_text`:** Sends only `60611` to the full-text arm. This creates a focused exact-term match.
* **`query_vector`:** Reuses the vector already computed for the full question. This avoids a second Bedrock call and keeps the vector comparison identical.

### Hybrid Fusion: Normalization, Rankers, and Alpha

Cosine similarity scores range from roughly 0 to 1. Lucene relevance scores use a different scale. The library normalizes both result sets before it merges them: it divides every score by the highest score from the same index, so each arm's best result becomes 1.0.

* **`HybridSearchRanker.NAIVE`:** Uses the larger normalized score for each chunk. This is the library default.
* **`HybridSearchRanker.LINEAR`:** Calculates `alpha * vector + (1 - alpha) * fulltext` for each chunk.
* **`alpha`:** Sets the vector weight from 0 to 1. The full-text weight is `1 - alpha`.

The notebook sets `ranker='linear'` and `alpha=0.2` for the postal-code question. This gives the full-text arm 80 percent of the weight because `60611` identifies the hotel more clearly than the surrounding prose. The result finds Windward Mile Tower and its 24-hour cancellation policy.

## 6. Graph-Enriched Hybrid Search with HybridCypherRetriever

`HybridCypherRetriever` combines the previous two ideas. It runs vector and full-text search, fuses the results, and then executes a reviewed `retrieval_query` from every matched chunk.

:::code{language=python}
hybrid_cypher_retriever = HybridCypherRetriever(
    driver=driver,
    vector_index_name='hotel_chunk_embeddings',
    fulltext_index_name='hotel_chunk_fulltext',
    retrieval_query=RETRIEVAL_QUERY,
    embedder=embedder,
)
:::

The retrieval query receives `node` and the fused `score`. It can then return the source chunk, hotel properties, connected amenities, and provenance in one result. The booking application uses this retriever through `search_hotel_knowledge` in `notebooks/workshop/hybrid_retrieval.py` because hotel questions can contain both paraphrased language and exact names.

The function accepts only query text. It fixes the index names, the `NAIVE` ranker, `top_k=5`, and the graph traversal so every tool call uses the tested retrieval configuration.

## 7. Cypher Templates for Structured Filtering

Neo4j's **Cypher Templates** pattern uses reviewed, parameterized queries for known question shapes. It does not start with a similarity or full-text search. The database evaluates conditions directly against the domain graph.

The Chicago question requires two relationships on the same hotel and a city condition on `address`. This Cypher template tests all three conditions\:

:::code{language=cypher}
MATCH (document:Document)<-[:FROM_DOCUMENT]-(chunk:Chunk)<-[:FROM_CHUNK]-(hotel:Hotel)
WHERE toLower(hotel.address) CONTAINS toLower($city)
OPTIONAL MATCH (hotel)-[:OFFERS_AMENITY]->(amenity:Amenity)
WITH hotel.name AS hotel_name,
     document.source_filename AS source_filename,
     collect(DISTINCT amenity.name) AS amenities
WITH *,
     any(name IN amenities WHERE toLower(name) CONTAINS 'spa') AS has_spa,
     any(name IN amenities WHERE toLower(name) CONTAINS 'pool') AS has_pool
RETURN hotel_name, source_filename, amenities, has_spa AND has_pool AS qualifies
ORDER BY hotel_name
:::

The notebook returns three result groups\:

* **Candidates:** Lists both Chicago hotels considered by the query.
* **Qualifiers:** Lists Lakeview Horizon Suites because it has both amenities.
* **Exclusions:** Lists Windward Mile Tower and names its missing spa and swimming pool.

This result shape records why each hotel passed or failed. "Reviewed fixed Cypher" describes this workshop's implementation; **Cypher Templates** is the Neo4j GraphRAG pattern name.

## 8. Optional Text2Cypher with Text2CypherRetriever

`Text2CypherRetriever` asks a model to write a query from the extraction schema. The optional notebook cell demonstrates the same Text2Cypher flow explicitly so each validation step remains visible\:

1. Add the schema and three examples to the prompt.
2. Ask the model for Cypher and remove any code fence.
3. Plan the statement with `EXPLAIN`.
4. Run only a read query, identified by `query_type == 'r'`, with a 15-second timeout.

The application path constructs the actual `Text2CypherRetriever` in `notebooks/workshop/hybrid_retrieval.py`. The schema names the stored relationship `OFFERS_AMENITY`. A guessed relationship such as `HAS_AMENITY` is valid Cypher, but it returns zero rows because that relationship does not exist in the graph. Supplying the schema and examples reduces that failure mode.

:::alert{type="info" header="Three layers protect the database"}
The prompt asks for read-only Cypher. The application checks the planned query type with `EXPLAIN`. A production read-only Neo4j user makes the database reject write operations even if the earlier checks miss one.
:::

## Choosing the Application Retrieval Pattern

:image[Decision guide for choosing among vector, full-text, hybrid, Cypher traversal, Cypher Templates, and Text2Cypher retrieval]{src="../../images/02-select-retriever.svg" width=800}

| Order | Pattern or retriever | How it works | Best for | What it returns |
|-------|----------------------|--------------|----------|-----------------|
| 1 | `VectorRetriever` | Finds the nearest `Chunk` nodes by vector similarity | Paraphrased questions | Ranked chunk text and a similarity score |
| 2 | `VectorCypherRetriever` | Runs a reviewed traversal from each vector match | Semantic entry that needs hotel properties | Chunk text, graph properties, and provenance |
| 3 | Full-text search | Queries a Neo4j full-text index | Names, identifiers, and postal codes | Ranked chunk text and a Lucene score |
| 4 | Full-text search with Cypher traversal | Continues from each full-text match into the graph | Exact-term entry that needs related properties | Chunk text, graph properties, and provenance |
| 5 | `HybridRetriever` | Fuses vector and full-text results | Questions needing meaning and exact terms | Ranked chunk text and a fused score |
| 6 | `HybridCypherRetriever` | Runs a reviewed traversal from each fused match | Meaning, exact terms, and connected properties | Chunk text, graph properties, and provenance |
| 7 | Cypher Templates | Executes a reviewed parameterized query | Known structured conditions | Candidate, qualifier, and exclusion records |
| 8 | `Text2CypherRetriever` | Generates Cypher from the question and schema | Flexible structured questions | Generated Cypher and database records |

The booking application selects `HybridCypherRetriever`. It needs exact hotel-name support, semantic matching, and connected hotel properties in the same context record.

## Who Decides What to Retrieve

| Stage | Pattern | Who decides what to retrieve |
|-------|---------|------------------------------|
| Module 2 notebook | Direct retrieval calls, one per exercise | You do, by choosing the cell |
| Module 3 | `search_hotel_knowledge` as a Strands tool | The model decides when; the retriever fixes how |
| Module 4 | The same function behind a Lambda and an AgentCore Gateway | The model, over IAM-authenticated MCP |
| Module 5 | The packaged agent on AgentCore Runtime | The model, inside a deployed container |

The caller changes across the modules, but the retrieval configuration stays fixed. The same `hybrid_retrieval.py` therefore runs in a notebook, a Lambda, and a container.

## Pattern Reference

This module uses three named patterns from Neo4j's :link[GraphRAG Pattern Catalog]{href="https://graphrag.com/reference/" external=true}\:

* **Graph-Enhanced Vector Search:** Finds a chunk through vector similarity and follows a reviewed graph traversal. `VectorCypherRetriever` implements this pattern directly. Full-text and hybrid retrieval can use the same graph-enrichment structure with different entry searches.
* **Cypher Templates:** Runs reviewed, parameterized Cypher for known structured question shapes.
* **Text2Cypher:** Asks a model to create Cypher at request time. This flexible path remains optional because every generated query requires validation.

## Run It

Open `notebooks/02-connected-context/2.1_connected_context.ipynb` and run the cells in order. The **Verify the prepared graph** cell checks the Module 1 fixtures and both indexes before it creates a retriever. The notebook runs the core vector, hybrid, vector-Cypher, Cypher Template, and optional Text2Cypher exercises. The page also explains standalone full-text retrieval, full-text retrieval with Cypher traversal, and the `HybridCypherRetriever` selected for Module 3.

If the readiness check fails, complete Module 1 and restart this notebook. Module 2 reads the graph and preserves the Module 1 data.

:::alert{type="info" header="Use one Neo4j connection"}
Configure one Neo4j connection because every module uses the same credentials. The optional Text2Cypher cell reuses that connection with a read-only session and a 15-second statement timeout.
:::

Slides for this module\: [GraphRAG Retrieval](../slides/overview-graphrag/)

## Next

Head to [Module 3](../03-grounded-booking-agent/).
