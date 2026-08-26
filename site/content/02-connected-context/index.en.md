---
title: "Module 2: From Vector Search to Graph-Enriched Retrieval"
weight: 30
---

## Four Retrieval Patterns Over One Graph

A question such as "Which Chicago hotels offer both a spa and a swimming pool?" cannot be answered by finding one similar passage. It asks for two independent facts that must hold for the same hotel, and in this corpus those facts live in two different source documents. Similarity ranking has no way to express the word "both". A graph query does.

This module runs four retrieval patterns against the graph you built in Module 1 and compares the context each one returns: vector search, hybrid search, graph-enriched search, and a fixed Cypher filter. Answer generation stays out of scope until Module 3, because a wrong answer built on good context and a wrong answer built on bad context look identical once a model has phrased them.

## The Lexical Graph and the Domain Graph

The build wrote two connected structures. **The lexical graph is what text search reads.** One `Document` node holds each source file, and one `Chunk` node holds a slice of that file's text along with its 1024-dimension embedding. **The domain graph is what Cypher reads.** A `Hotel` node carries `name`, `address`, and `guest_rating` as properties, and `HAS_ROOM`, `OFFERS_AMENITY`, `HAS_POLICY`, and `PROVIDES_SERVICE` connect it to its `Room`, `Amenity`, `Policy`, and `Service` nodes.

Two relationships bridge them, and their direction matters when you read the retrieval query. Extraction wrote entity provenance as `(:Hotel)-[:FROM_CHUNK]->(:Chunk)`, so retrieval, which starts at the chunk, traverses that relationship backwards as `(node)<-[:FROM_CHUNK]-(hotel:Hotel)`. Text provenance runs the other way, `(node)-[:FROM_DOCUMENT]->(:Document)`, which is how a result names the file it came from. That crossing from matched text into typed properties is what makes GraphRAG possible here.

:image[Two connected structures: the source file becomes a Document and Chunk in the lexical graph, and a Hotel node with typed Room, Amenity, Policy, and Service relationships in the domain graph]{src="../../images/01-graph-structure.svg" width=800}

## Chunks, Embeddings, and Vector Search

A chunk is a slice of a source document, stored as a node so that search has something to rank. Module 1 set the chunk size to 12000 characters against a largest corpus document of 7,442 bytes, so every hotel FAQ becomes exactly one `Chunk`. That choice serves extraction, because the hotel's name, rooms, policies, and services reach the model in a single prompt instead of being split across several. It also makes every retrieved passage a whole document, which is coarse. A production system would write smaller retrieval chunks beside the large extraction chunks. This workshop instead trims returned text at read time, capped at 1,200 characters in `workshop/hybrid_retrieval.py`.

An embedding is a list of numbers that acts as a fingerprint for the meaning of a passage rather than for the words in it. Amazon Nova 2 multimodal embeddings, model `amazon.nova-2-multimodal-embeddings-v1:0`, turn each chunk into 1024 floats, and passages describing similar ideas land near each other. The notebook's first question tests exactly that. It asks when "standard arrival processing" begins at AnyCompany Cairo Nile View, while the Cairo document says "Standard check-in time". Those two phrasings share no keyword, and the Cairo chunk still ranks in the top three carrying its supported `3:00 PM` value.

Vector search embeds the question with the same embedder that wrote the chunk vectors, then asks the `hotel_chunk_embeddings` index for the nearest stored vectors by cosine similarity. `top_k` is how many chunks come back. The notebook uses 3 for the arrival question and 5 for the postal-code comparison, and it holds that 5 constant across the vector run and the hybrid run so the two are scored on lists of the same length. The read side of the embedding settings has to match the write side exactly, so the retriever's embedder must be the same model, the same 1024 dimensions, and the same `GENERIC_INDEX` purpose that Module 1 embedded with. Both the build and the retrieval path therefore import those five values from `workshop/retrieval_contract.py` and nowhere else. A mismatch does not raise an error. It returns rows that are simply wrong. What vector search hands back at best is still a ranked list of isolated passages and a score, saying nothing about which hotel a passage describes or what that hotel's rating is.

## The Exact-Term Problem

The notebook's second question asks for the cancellation policy of the hotel at `60611`. Vector search struggles here, because a five-digit token carries almost no distinguishing meaning, so its embedding sits in a crowd of other five-digit numerals rather than next to the Chicago question. You are not asked to take that on faith. The notebook runs a diagnostic scan at `top_k=30` over the same query vector and prints the live vector rank of the Chicago chunk, so you read the vector arm's real position for the chunk you wanted.

Full-text search covers that gap by never converting anything to a vector. `hotel_chunk_fulltext` is an Apache Lucene index over `Chunk.text`. Lucene splits the stored text into tokens, matches query terms literally, and scores a match by weighing how often a term appears in a chunk against how rare it is across the corpus (a BM25-style relevance score). A token as rare as `60611` therefore scores hard in the one chunk that contains it. Lucene syntax carries two more operators worth knowing. A trailing `~` makes a term fuzzy, so a guest who types `Winward~` still reaches Windward Mile Tower, and `AND`, `OR`, and `NOT` combine terms, so `spa AND pool` requires both in the same chunk.

A hybrid retriever runs both arms, and the two arms are independently addressable\:

:::code{language=python}
hybrid_identifier_result = hybrid_retriever.search(
    query_text='60611',
    query_vector=vector_identifier_result.metadata['query_vector'],
    top_k=IDENTIFIER_TOP_K,
    ranker='linear',
    alpha=0.2,
)
:::

The full-text arm receives only the token `60611`, which is what keeps the exact-term signal sharp instead of diluting it across a sentence of common words. The vector arm receives `query_vector`, the embedding of the complete question, reused from the earlier `VectorRetriever` call. Passing the stored vector rather than the question text skips a second Bedrock embedding call, and it guarantees both retrievers ranked against the identical vector.

## Hybrid Fusion: Normalization, Rankers, and Alpha

The two arms produce numbers on incompatible scales. Cosine similarity runs roughly 0 to 1, while a Lucene relevance score has no upper bound and depends on corpus statistics, so adding them directly would let the full-text arm decide every ranking. The library normalizes each arm against itself instead. It takes the maximum score within each arm's own result set, divides every row in that arm by that maximum so the arm's best hit becomes 1.0, then merges the two lists on the `Chunk` node and re-ranks the merged list. How the merge combines the two normalized numbers is the ranker's job. `HybridSearchRanker.NAIVE` is the library default, and it takes the larger of the two normalized scores for each chunk. `HybridSearchRanker.LINEAR` takes a weighted sum instead, computed as `alpha * vector + (1 - alpha) * fulltext`, where a chunk that appears in only one index scores 0 on the other. `alpha` must be between 0 and 1, and the linear ranker requires it.

Choosing `ranker='linear'` is therefore an explicit act, and so is choosing `alpha=0.2`. For this question the postal code is the discriminating signal and the surrounding prose is not, so 0.2 sends 80 percent of the fused weight to the full-text arm. Raise `alpha` toward 1 and the ranking slides back toward the vector arm, and toward chunks that merely sound like cancellation questions. The value is not a constant of nature. It is a decision about which signal separates the right chunk from the wrong ones for the questions you actually get, and the notebook shows its result: the Windward Mile Tower chunk, carrying both `60611` and the phrase "at least 24 hours prior to arrival".

## The neo4j-graphrag Library

Every retriever class on this page comes from :link[neo4j-graphrag]{href="https://neo4j.com/docs/neo4j-graphrag-python/current/" external=true}, Neo4j's official GraphRAG library for Python. Module 1 already used it, because `SimpleKGPipeline`, which built the graph, ships in the same package. Module 2 imports the read side of it\:

:::code{language=python}
from neo4j_graphrag.retrievers import HybridRetriever, VectorCypherRetriever, VectorRetriever
from neo4j_graphrag.types import RetrieverResultItem
:::

Every retriever exposes one method, `search()`, and behind that method it does four things\:

1. It embeds your question with the configured embedder, returning 1024 floats from Amazon Nova.
2. It queries `hotel_chunk_embeddings` with that vector. A hybrid retriever also queries `hotel_chunk_fulltext` and fuses the two result sets.
3. It runs the `retrieval_query` you supplied, once per matched chunk, if the retriever is a Cypher retriever.
4. It maps each returned record into a `RetrieverResultItem`.

Knowing those four steps is what makes Module 4 readable, because Module 4 puts this same `search()` call inside a Lambda function behind an AgentCore Gateway and adds almost nothing else. A `RetrieverResultItem` has two fields, and the split between them is deliberate. `content` is the context as it will be provided to the LLM, while `metadata` is structured data the application can inspect programmatically. A `result_formatter` function makes the split, putting the chunk text in `content` and the hotel properties in `metadata`. Without a formatter, the default serializes the whole record into one string and the properties become prose. Module 3 depends on the split, because deciding whether it can answer means testing `metadata['hotel_id']` rather than reading a sentence.

## Graph-Enhanced Vector Search

`VectorCypherRetriever` runs a vector search, then executes a fixed Cypher query on each matched chunk. This is the notebook's retrieval query, trimmed to its structural core\:

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

The query opens on an unbound `node`, which looks wrong until you know where it comes from. The retriever binds `node` to each chunk the index matched and `score` to that chunk's index score before your Cypher runs, so those two names are supplied rather than declared. Under a hybrid retriever the same `score` is the fused score, which is why the shipped query aliases it `combined_score`. `OPTIONAL MATCH` on the hotel is a teaching decision, not a stylistic one. A plain `MATCH` would silently drop a semantically strong chunk whose hotel extraction failed, and you would see a shorter result list with nothing telling you why. The optional match keeps the row and `graph_enrichment_status` labels it, so the notebook prints how many results arrived complete and how many arrived without a hotel.

`field_provenance` is a literal Cypher map from each returned field to the graph path that produced it. A reviewer holding `amenities: '(:Hotel)-[:OFFERS_AMENITY]->(:Amenity)'` knows which relationship to walk to check an amenity against the authored source list, without reading the query that returned it.

The fan-out to amenities is the one place this query could quietly break. A hotel with 12 amenities, 4 room types, and 5 policies matched as three top-level `MATCH` clauses produces 12 x 4 x 5 = 240 rows for a single chunk, because every combination of the three is a distinct path, and each `collect` then counts the same amenity 20 times. The notebook survives with one top-level fan-out. The shipped query, which needs several, scopes each list in its own subquery\:

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

A scoped subquery runs once per `hotel` row and returns one list, so adding a second fan-out for rooms multiplies nothing. The `LIMIT`, interpolated from a shared constant rather than typed as a literal, is also what keeps the returned context to a predictable size. Determinism is the last detail, and it matters because scores tie. The notebook orders by `semantic_score` and then breaks ties on whether `hotel_id` is null and on `hotel_id` itself, while the shipped query goes further and uses `head(collect(candidate))` after an ordered `WITH` to pick exactly one hotel per chunk. An unordered tie makes a workshop assertion pass on one run and fail on the next. The result that carries this section is a single field. `hotel_id` appears nowhere in the source text, because it is a property extraction wrote onto the `Hotel` node, so the vector arm cannot return it at any `top_k`. Running both retrievers on the same Cairo question, the notebook prints 1 of 5 requested properties from `VectorRetriever` against 5 of 5 from `VectorCypherRetriever`, alongside a character count that separates structured properties from source text.

:::alert{type="info" header="Extraction defines the graph result"}
Graph enrichment returns only what the extraction pipeline placed in the graph, so it is not an independent source of truth. The result keeps source provenance visible so you can compare an extracted omission or merge against the authored document.
:::

## Structured Filtering with a Fixed Cypher Query

The opening question defeats every retriever above, and it is worth being precise about why. "Which Chicago hotels offer both a spa and a swimming pool?" is two independent existence checks that must hold on the same `Hotel` node, under a predicate on `address`. That is a conjunction over relationships, and no similarity ranking evaluates a conjunction. A database does, in one pass\:

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

The notebook splits the output into candidates, qualifiers, and exclusions, and that split is what makes the answer checkable instead of merely plausible. Two Chicago hotels are considered. Lakeview Horizon Suites qualifies. Windward Mile Tower comes back as an exclusion whose missing amenities are named, both `spa` and `swimming pool`, so you see the hotel that was rejected and the reason, rather than an answer that quietly omits it.

## Optional Model-Generated Cypher

`Text2CypherRetriever` hands query writing to the model. The notebook's optional cell shows the flow step by step. The pinned extraction schema and three worked examples are formatted into one prompt, the model returns text, a helper strips any code fence from that text, and the statement runs with a 15-second timeout. Giving the model the schema first is what keeps it useful. A model guessing relationship names writes `(:Hotel)-[:HAS_AMENITY]->(:Amenity)` against a graph that stores `OFFERS_AMENITY`, and that query does not fail. It returns zero rows, which reads to a user as "there is no such hotel". The schema text and the examples both name the real relationship, so the generated query matches the graph the build actually wrote.

:::alert{type="info" header="Three layers protect the write path"}
The prompt tells the model never to write, merge, or delete, which is advisory and nothing more. The notebook then plans the generated statement with `EXPLAIN` and refuses to execute it unless Neo4j classifies the query as read-only, which is a real check but runs inside the same application that issues the query. In production a read-only Neo4j user is the third layer, and the only one the application cannot route around.
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

`VectorRetriever` is the baseline. Use it when the question and the source say the same thing in different words, and accept that the result is a passage with no idea what it describes.

`HybridRetriever` adds the Lucene arm for the cases where meaning is not the discriminator. A postal code, a hotel name, or a rate code is a string to be matched, not a concept to be approximated.

`VectorCypherRetriever` is the one that returns properties. It is the right choice whenever the answer needs a value the prose never states, such as `hotel_id`, or needs the amenity list as a list rather than as a paragraph.

`HybridCypherRetriever` composes the two lessons above. Hybrid fusion finds the chunk, and the same retrieval query expands it. Nothing about it is new once you have read this page.

A fixed Cypher query is the right tool when the condition is known in advance and has to be evaluated rather than ranked. The Chicago spa-and-pool filter is that case.

`Text2CypherRetriever` covers structured questions nobody wrote a query for. It buys flexibility with a statement no human reviewed, which is why it stays optional and stays gated.

The booking application needs an exact hotel name matched reliably **and** the connected hotel properties in one result, so Module 2 selects `HybridCypherRetriever`, exposed as `search_hotel_knowledge` in `notebooks/workshop/hybrid_retrieval.py`. That function takes one argument, the query text. The index names, the `NAIVE` ranker, the `top_k` of 5, and the traversal are all fixed inside the module, so there is no ranker, alpha, or result-count parameter for a caller to set. Those comparisons were made once, on this page, by you, and a model-issued tool call does not get to re-run them per request.

## Who Decides What to Retrieve

| Stage | Pattern | Who decides what to retrieve |
|-------|---------|------------------------------|
| Module 2 notebook | Direct retriever calls, one per cell | You do, by choosing the cell |
| Module 3 | `search_hotel_knowledge` as a Strands tool | The model decides when; the retriever fixes how |
| Module 4 | The same function behind a Lambda and an AgentCore Gateway | The model, over IAM-authenticated MCP |
| Module 5 | The packaged agent on AgentCore Runtime | The model, inside a deployed container |

Decision authority moves one row at a time, from you to the model to a deployed container. The retrieval configuration does not move at all. That constant is why the same `hybrid_retrieval.py` runs unchanged in a notebook, in a Lambda, and in a container.

## Pattern Reference

This module implements the **Graph-Enhanced Vector Search** pattern from Neo4j's :link[GraphRAG Pattern Catalog]{href="https://graphrag.com/reference/" external=true}, a vector match followed by a fixed graph traversal that enriches each hit. `VectorCypherRetriever` and `HybridCypherRetriever` are the library's implementations of it, and the retrieval query is the traversal. The optional path implements a second catalog pattern, **Text2Cypher**, where the model composes the query at request time. The two sit at opposite ends of a controlled-to-autonomous spectrum, which is the framing that justifies shipping the fixed one and leaving the generated one optional.

## Run It

Open `notebooks/02-connected-context/2.1_connected_context.ipynb` and run the cells in order. Before any retriever is built, the **Verify the prepared graph** cell confirms that Module 1 created the required fixtures and that both indexes are online. That check runs from Python, so no terminal command is needed. If the cell reports that Module 2.1 is not ready, return to the Module 1 notebook and run its cells through completion, then rerun this notebook from the top. Every operation here reads the graph without clearing it, so your Module 1 work is preserved.

:::alert{type="info" header="Use one Neo4j connection"}
Configure one Neo4j connection, because every module uses the same credentials. The optional Text2Cypher cell reuses that same connection with a read-only session and a 15-second statement timeout.
:::

## Next

Head to [Module 3](../03-grounded-booking-agent/).
