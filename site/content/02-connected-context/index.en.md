---
title: "Module 2: From Vector Search to Graph-Enriched Retrieval"
weight: 30
---

This module walks through the retrieval strategies below, then compares four patterns your application can call directly. Each pattern answers a different kind of question well.

Take the question "Which Chicago hotels offer both a spa and a swimming pool?" This question needs two amenity checks on the same `Hotel` node. A similarity search only ranks passages by how closely they match the question's meaning, so it cannot test two exact conditions at once. A Cypher query tests both relationships as exact conditions instead.

**Retrieval strategies in this module**

| Strategy | What it does | Best for |
|----------|---------------|----------|
| Vector search | Turns the question into numbers and finds chunks with similar meaning. | Questions phrased differently than the source text. |
| Full-text search | Matches exact words using the Lucene search engine. | Questions needing an exact term: postal codes, IDs, names. |
| Hybrid search | Runs vector search and full-text search together, then merges the two scores into one ranked list. | Questions that need both meaning and an exact term. |
| Graph-enriched search | Finds a matching chunk, then follows graph relationships to add hotel properties. | Questions that need facts connected to the matched text. |
| Fixed Cypher query | Tests known property and relationship conditions directly in Neo4j. | Questions with known, structured conditions. |
| Text2Cypher (optional) | Asks the model to write a Cypher query from the graph schema. | Flexible structured questions with no fixed query. |

Four of these strategies are patterns your application can call directly: vector search, hybrid search, graph-enriched search, and a fixed Cypher query. The notebook runs each one and compares the context it returns. Module 3 uses that context to generate answers.

## The Lexical Graph and the Domain Graph

Module 1 wrote two connected graph structures.

* **Lexical graph:** `Document` nodes hold source files. `Chunk` nodes hold searchable text and 1024-dimension embeddings.
* **Domain graph:** `Hotel` nodes hold `name`, `address`, and `guest_rating`. The `HAS_ROOM`, `OFFERS_AMENITY`, `HAS_POLICY`, and `PROVIDES_SERVICE` relationships connect other hotel facts.
* **Entity provenance:** Extraction writes `(:Hotel)-[:FROM_CHUNK]->(:Chunk)`. Retrieval starts at the chunk and follows this relationship in reverse as `(node)<-[:FROM_CHUNK]-(hotel:Hotel)`.
* **Text provenance:** `(node)-[:FROM_DOCUMENT]->(:Document)` connects the chunk to its source file.

Graph-enriched search moves from the lexical graph to the domain graph. This step turns a matched chunk of text into hotel properties and source provenance.

:image[Two connected structures: the source file becomes a Document and Chunk in the lexical graph, and a Hotel node with typed Room, Amenity, Policy, and Service relationships in the domain graph]{src="../../images/01-graph-structure.svg" width=800}

## The neo4j-graphrag Retriever Library

The :link[neo4j-graphrag]{href="https://neo4j.com/docs/neo4j-graphrag-python/current/" external=true} library provides every retriever this module uses. Module 1 used the same library for `SimpleKGPipeline`. Module 2 imports its retriever classes\:

:::code{language=python}
from neo4j_graphrag.retrievers import HybridRetriever, VectorCypherRetriever, VectorRetriever
from neo4j_graphrag.types import RetrieverResultItem
:::

Every retriever in this library exposes one method: `search()`. The three retrievers imported above all run `search()` the same way\:

1. Embed the question with Amazon Nova.
2. Query `hotel_chunk_embeddings`. A hybrid retriever also queries `hotel_chunk_fulltext` and merges both results.
3. Run the supplied `retrieval_query` for each matched chunk, if the retriever is a Cypher retriever.
4. Map each result to a `RetrieverResultItem`.

* **`content`:** Holds the chunk text. The LLM reads this as context.
* **`metadata`:** Holds hotel properties for application checks, such as `metadata['hotel_id']`.
* **`result_formatter`:** Maps each query record into the `content` and `metadata` fields.

`Text2CypherRetriever` shares the same `search()` method and returns the same `RetrieverResultItem`, but it skips embedding the question. It asks the model to write Cypher from the graph schema instead, which the "Optional Model-Generated Cypher" section below covers.

Module 4 places this same `search()` call inside a Lambda function behind an AgentCore Gateway.

## Vector Search: Chunks and Embeddings

`VectorRetriever` turns text into numbers and compares those numbers.

* **Chunk:** A searchable slice of source text. The 12000-character setting is larger than the biggest 7,442-byte document, so each hotel FAQ becomes one chunk.
* **Embedding:** A numeric representation of meaning. Amazon Nova model `amazon.nova-2-multimodal-embeddings-v1:0` creates 1024 floats for each chunk.
* **Vector search:** Embeds the question and uses cosine similarity to find the closest vectors in `hotel_chunk_embeddings`.
* **`top_k`:** Sets the number of chunks returned. The notebook uses 3 for the arrival question and 5 for the vector and hybrid postal-code comparison.

A large chunk keeps the complete hotel in a single extraction prompt, but it also returns a whole document during search. `workshop/hybrid_retrieval.py` limits returned chunk text to 1,200 characters. A production design can use large extraction chunks and smaller retrieval chunks.

The first question asks when "standard arrival processing" begins at AnyCompany Cairo Nile View. The source text says "Standard check-in time." Vector search still finds the Cairo chunk, because both phrases carry the same meaning. The result includes `3:00 PM`.

The query embedder must match the build settings: the same model, 1024 dimensions, and `GENERIC_INDEX` purpose. Both paths import these values from `workshop/retrieval_contract.py`. A mismatched configuration can return incorrect rows while it still reports success.

## The Exact-Term Problem

The second question asks for the cancellation policy of the hotel at `60611`. A five-digit token carries little meaning on its own, so its embedding lands near many unrelated numbers. The notebook runs a `top_k=30` diagnostic scan and prints the Chicago chunk's vector rank to show how far down the list it falls.

Full-text search fixes this problem. It uses the Apache Lucene index `hotel_chunk_fulltext` over `Chunk.text`. Lucene breaks the text into tokens, matches literal terms, and scores each match by how often the term appears and how rare it is. The rare token `60611` gets a strong score in the chunk that contains it.

* **Exact term:** `60611` matches the same literal token in the source.
* **Fuzzy term:** `Winward~` can match the misspelled hotel name `Windward`.
* **Boolean terms:** `spa AND pool` requires both terms. `OR` accepts either term, and `NOT` excludes a term.

`HybridRetriever` runs a vector arm and a full-text arm together. You can send different input to each arm\:

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

## Hybrid Fusion: Normalization, Rankers, and Alpha

Cosine similarity scores range from roughly 0 to 1. Lucene relevance scores use a different scale. The library normalizes both result sets to the same scale before it merges them: it divides every score by the highest score in its own index, so each arm's best result becomes 1.0.

* **`HybridSearchRanker.NAIVE`:** Uses the larger normalized score for each chunk. This is the library default.
* **`HybridSearchRanker.LINEAR`:** Calculates `alpha * vector + (1 - alpha) * fulltext` for each chunk.
* **`alpha`:** Sets the vector weight from 0 to 1. The full-text weight is `1 - alpha`.

The notebook sets `ranker='linear'` and `alpha=0.2` for the postal-code question. This gives the full-text arm 80 percent of the weight, because `60611` identifies the hotel more clearly than the surrounding prose does. The result finds Windward Mile Tower and its 24-hour cancellation policy.

## Graph-Enhanced Vector Search

`VectorCypherRetriever` runs vector search first, then runs a fixed `retrieval_query` for every matched chunk. The notebook uses this core query\:

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

The retriever hands `node` and `score` to the query before it runs. `node` is the matched chunk. `score` is its vector score. A hybrid retriever hands over the fused score instead, which the shipped query names `combined_score`.

* **`OPTIONAL MATCH`:** Keeps a strong chunk even when hotel extraction failed. `graph_enrichment_status` then reports the missing hotel.
* **`field_provenance`:** Maps each returned field to its graph path. For example, `amenities` comes from `(:Hotel)-[:OFFERS_AMENITY]->(:Amenity)`.
* **`source_filename`:** Names the source document, so a reviewer can check an extracted value against the authored text.

A single top-level pattern cannot hold multiple relationship lists safely. Matching 12 amenities, 4 room types, and 5 policies in one pattern would create 240 path combinations for a single chunk. The shipped query avoids this: it collects each list inside its own subquery\:

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

Each subquery returns one amenity list per hotel, so the room and policy lists stay independent from it. A shared limit caps each list at 12 items. Ordered tie-breaking and `head(collect(candidate))` pick one hotel per chunk, every time, in the same way.

The comparison tests five hotel properties. `VectorRetriever` returns only one, because it only returns chunk text. `VectorCypherRetriever` returns all five, because it follows `FROM_CHUNK` to the `Hotel` node, where `hotel_id` exists as a graph property.

:::alert{type="info" header="Extraction defines the graph result"}
Graph enrichment returns facts written during extraction. Each result includes `source_filename`, so a missing or merged property can be checked against the authored document.
:::

## Structured Filtering with a Fixed Cypher Query

The Chicago question requires two relationships on the same hotel and a city condition on `address`. Similarity scores rank text, while this fixed Cypher query tests all three conditions in Neo4j\:

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

This result shape records why each hotel passed or failed.

## Optional Model-Generated Cypher

`Text2CypherRetriever` asks the model to write a query from the extraction schema. The optional notebook cell uses this flow\:

1. Add the schema and three examples to the prompt.
2. Ask the model for Cypher and remove any code fence.
3. Plan the statement with `EXPLAIN`.
4. Run only a read query, identified by `query_type == 'r'`, with a 15-second timeout.

The schema names the stored relationship `OFFERS_AMENITY`. A guessed relationship such as `HAS_AMENITY` is valid Cypher, but it returns zero rows because that relationship does not exist in the graph. The schema and examples in the prompt stop this guess, so an empty result never gets mistaken for a missing hotel.

:::alert{type="info" header="Three layers protect the database"}
The prompt asks for read-only Cypher. The application checks the planned query type with `EXPLAIN`. A production read-only Neo4j user makes the database reject write operations even if the earlier checks miss one.
:::

## Choosing the Application Retriever

:image[Decision tree for selecting a Neo4j retrieval pattern by question type: VectorRetriever, HybridRetriever, VectorCypherRetriever, or a fixed Cypher query, with Text2CypherRetriever as an optional extension]{src="../../images/02-select-retriever.svg" width=800}

| Retriever | How it works | Best for | What it returns |
|-----------|--------------|----------|-----------------|
| `VectorRetriever` | Embeds the question and returns the nearest `Chunk` nodes by cosine similarity | Paraphrased questions | Ranked chunk text and a similarity score |
| `HybridRetriever` | Runs a vector arm and a Lucene arm, normalizes each to its own maximum, then re-ranks | Names, identifiers, and postal codes | Ranked chunk text and a fused score |
| `VectorCypherRetriever` | Matches by vector, then runs the retrieval query on each matched chunk | Semantic entry that needs hotel properties | Chunk text, hotel properties, and provenance |
| `HybridCypherRetriever` | Fuses both arms, then runs the same retrieval query on each matched chunk | An exact hotel name plus connected properties | Fused-score chunk text and hotel properties |
| Fixed Cypher query | The database evaluates a parameterized query the application wrote | Known structured conditions | Candidate, qualifier, and exclusion records |
| `Text2CypherRetriever` | The model writes Cypher from the schema, and `EXPLAIN` gates it | Flexible structured questions | The generated query, the planner result, and records |

* **`VectorRetriever`:** Finds paraphrased text by cosine similarity and returns chunk text with a score.

* **`HybridRetriever`:** Adds Apache Lucene when a postal code, hotel name, or rate code needs a literal match.

* **`VectorCypherRetriever`:** Adds hotel properties after a vector match. Use it for fields such as `hotel_id` or a structured amenity list.

* **`HybridCypherRetriever`:** Uses hybrid search to find the chunk, then runs the fixed retrieval query to add hotel properties.

* **Fixed Cypher query:** Evaluates known conditions in the database. The Chicago spa-and-pool filter uses this pattern.

* **`Text2CypherRetriever`:** Generates Cypher for a new structured question. The notebook keeps it optional and checks the query before execution.

The booking application needs exact hotel-name matching and connected hotel properties in one result. It therefore uses `HybridCypherRetriever` through `search_hotel_knowledge` in `notebooks/workshop/hybrid_retrieval.py`.

The function accepts only the query text. It fixes the index names, the `NAIVE` ranker, `top_k=5`, and the traversal, so each tool call uses the tested retrieval configuration.

## Who Decides What to Retrieve

| Stage | Pattern | Who decides what to retrieve |
|-------|---------|------------------------------|
| Module 2 notebook | Direct retriever calls, one per cell | You do, by choosing the cell |
| Module 3 | `search_hotel_knowledge` as a Strands tool | The model decides when; the retriever fixes how |
| Module 4 | The same function behind a Lambda and an AgentCore Gateway | The model, over IAM-authenticated MCP |
| Module 5 | The packaged agent on AgentCore Runtime | The model, inside a deployed container |

The caller changes across the modules, but the retrieval configuration stays fixed. The same `hybrid_retrieval.py` therefore runs in a notebook, a Lambda, and a container.

## Pattern Reference

This module uses two patterns from Neo4j's :link[GraphRAG Pattern Catalog]{href="https://graphrag.com/reference/" external=true}\:

* **Graph-Enhanced Vector Search:** Finds a chunk and follows a fixed graph traversal. `VectorCypherRetriever` and `HybridCypherRetriever` implement this pattern.
* **Text2Cypher:** Asks a model to create Cypher at request time. This flexible path remains optional because each generated query needs validation.

## Run It

Open `notebooks/02-connected-context/2.1_connected_context.ipynb` and run the cells in order. The **Verify the prepared graph** cell checks the Module 1 fixtures and both indexes before it creates a retriever. If the check fails, complete Module 1 and restart this notebook. Module 2 reads the graph and preserves the Module 1 data.

:::alert{type="info" header="Use one Neo4j connection"}
Configure one Neo4j connection, because every module uses the same credentials. The optional Text2Cypher cell reuses that same connection with a read-only session and a 15-second statement timeout.
:::

## Next

Head to [Module 3](../03-grounded-booking-agent/).
