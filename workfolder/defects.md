# Workshop Defects and Proposed Fixes

Date: 2026-08-21
Branch: finalize-course

What was checked:

- `notebooks/01-build-graph/1.1_build_graph.ipynb` and `workshop-content/content/01-build-graph/index.en.md`
- `notebooks/02-vector-rag-hallucinates/` and `workshop-content/content/02-vector-rag-hallucinates/index.en.md`
- Every Cypher query in both modules, run live against the Aura instance in `.env`
- Every factual claim in the prose, checked against the code that backs it

Live environment at the time of the check:

- Neo4j 5.27-aura, enterprise, Cypher 5 and 25 both available
- 300 `Document`, 300 `Chunk`, 292 `Hotel`
- Both retrieval indexes online
- The instance is not a clean restore. Module 1 and Module 6 have already run on it.

A note on every reference below: the line numbers in this file have drifted as the
working tree changed. Patch by symbol, not by line number, and confirm the symbol
still exists before editing it.

---

## Module 1: fixed

All of these were wrong in the prose. All are now corrected in the working tree.

- **"No other file in this workshop names those five cities" was false.** The `-001` document for each of those cities is in the dump. The source docstring says no *authored* file names them, and the word "authored" was dropped in the rewrite. Now says no later module asks a question about these five `-002` hotels.
- **"This module has no cleanup step or run identifier" was wrong about the run identifier.** `graph_builder.py:255` puts a `run_id` on every document. Now says nothing in this module deletes the five hotels.
- **"The cell removes this temporary data when it finishes" was false.** See the outstanding item below. The prose now says the demo leaves its data behind and that nothing downstream reads it.
- **"Bedrock's 4096-token default" named the wrong owner.** 4096 is the default in the workshop's own wrapper at `bedrock_providers.py:178`. Now says the workshop's Bedrock client sets it.
- **Cell 23 sent the reader to Module 3 for the output comparison.** Module 2 is the module that compares. Fixed.
- **Cell 23 said "Module 2 demonstrates and fixes this failure."** Module 2 only demonstrates it. Module 3 fixes it. Fixed.
- **"The workshop's embedder accepts no override" dropped a word.** The code comment says no *environment* override. `BedrockEmbeddings.__init__` does accept `model_id` and `dimensions` as arguments. Now says no environment override, with the model and width set in code.
- **"Every property in the schema appears in that text as plain prose under a heading" was too strong.** `Service.is_available` and `Service.is_complimentary` are booleans that appear nowhere as prose. The 400-character preview only reaches the six `Hotel` properties. Now lists what actually appears where.
- **"Your own five hotels get the same treatment after the build" promised five.** The cell walks one. Fixed.
- **"The build asserts one chunk per document" described the wrong check.** The build compares the total chunk count against the total document count. One document with two chunks and another with none would pass. Fixed in both files.
- **"Clearing each document again before it retries" was unconditional.** `retry_failures` skips the clear when a write for that document started in the last 30 seconds. Fixed.
- **The Cairo fixture check also requires a rating.** Both files said spa and pool only. The live margin on that gate is exactly one hotel, so the full condition matters. Fixed in both files.
- **"Against the vectors your own extraction just wrote" was too narrow.** The indexes cover every `Chunk` in the graph, which is 300 of them. The participant wrote 5. Fixed.
- **Style leftovers.** Removed the throat-clearing openers in cell 0, cell 23, and the content page intro. Changed "SimpleKGPipeline extracts without a schema" to "can extract". Added the missing gloss for `SimpleKGPipeline` in the notebook. Removed the definite article in front of "the two retrieval indexes" 13 cells before they are introduced. Replaced the bare "Module 2 directory" reference with the actual directory name and what it holds. Split three sentences that carried two claims each.

Checks that pass after the fixes:

- nbformat validates
- All nine original code cells are byte-identical to the git index
- `nbformat_minor` is still 4 and no cell IDs were added
- Zero em-dashes and zero litotes in both files
- The three new code cells compile, longest line 81 characters

Live Cypher results for the three new cells:

- The `count { (h)-[:HAS_ROOM]->() }` subquery form works, including under an explicit `CYPHER 25` prefix
- `FROM_DOCUMENT` and `FROM_CHUNK` point the direction the new query assumes
- `hotel-paris-001.txt` returns exactly one row, 1 chunk, embedding width 1024, 3 rooms, 6 amenities, 11 policies, 8 services
- `SHOW INDEXES` returns both indexes online at 1024 dimensions and cosine similarity
- A sweep of all 300 filenames found no case where the query returns more than one row

---

## Module 1: outstanding

### M1-1. The optional unpinned demo leaves data in the graph forever

- **Where:** `1.1_build_graph.ipynb` cell 15.
- **What is wrong:** The cell calls `run_async(file_path=..., text=...)` with no `document_metadata`. `source_filename` only ever arrives through `document_metadata`. The `finally` block calls `clear_document`, which matches on `MATCH (d:Document {source_filename: $filename})`, so it matches nothing and deletes nothing.
- **Why it matters:** The demo's `Document`, its `Chunk`, and every off-schema label it invented stay in the graph permanently. Nothing catches it. The schema check only looks at the build run's own chunks, and the count checks still balance because the orphan adds one to each side.
- **The obvious one-line fix is unsafe.** Adding `document_metadata={"source_filename": sample.name}` does make the `finally` block match, but `sample = paths[0]` is one of the participant's five real held-out documents. On a first pass through the notebook that is harmless, because the demo runs before the build. A participant who sets `RUN_UNPINNED_DEMO = True` and re-executes cell 15 after the build has finished deletes the correctly built `Document`, `Chunk`, and entities for that hotel, and the next readiness check then fails with no visible cause.
- **Proposed fix:** Give the demo a filename that cannot collide with a real document.
  ```python
  demo_filename = f"unpinned-demo-{sample.name}"
  ```
  Pass it as `file_path` and as `document_metadata={"source_filename": demo_filename}`, and clear that name in the `finally` block. Cleanup becomes exact, re-running after the build is harmless, and the demo's document is unambiguously the demo's. Then change the cell 14 prose back to promising cleanup.
- **Why it is not done yet:** This changes an existing code cell, which was explicitly out of scope for the writing pass. It needs a decision.
- **Recommendation:** Make the fix with the distinct filename. The alternative is shipping a workshop that tells participants it leaves junk in their graph, or one that can silently delete a hotel it just built.

---

## Module 2: defects

Note: `2.1_vector_rag_hallucinates.ipynb` and its `README.md` already have uncommitted edits from an earlier style pass. This audit covers that current state.

### Blockers

#### M2-1. The vector agent does not work at all, and the committed index has no compatibility contract

- **Status, 2026-08-21:** The artifact half is complete and committed in `2de1d08`. `faqs_vector.index` is an `IndexFlatIP` at `d` 1024 with `ntotal` 300 and L2-normalized vectors. The manifest records and the loader validates `vectors_sha256`, the fixed graph `vector_source`, metric, normalization, shared embedding contract, document count, and corpus checksum. All 16 focused artifact tests and Ruff pass. Every notebook-side item below remains open.
- **Where:** `2.1_vector_rag_hallucinates.ipynb` cells 5 and 8.
- **What was wrong:** The committed `faqs_vector.index` was 384-dimensional. `_embed()` asks for 1024 dimensions, which is `EMBEDDING_DIMENSIONS` in `workshop.retrieval_contract`. FAISS raised a bare `AssertionError`. The `except` block in `search_faqs` swallows it and returns the string `"Query error:"`, which is still true and still has to be fixed.
- **Why it matters:** All four demonstrations in the module are empty. The vector agent never receives a single document. It answers by declining politely, which is the opposite of the point the module is making.
- **Evidence:** The committed run at `setup/notebook-output/20260821T011118Z-18505/02-vector-rag-hallucinates/2.1_vector_rag_hallucinates-executed.ipynb` shows `Query error:` on every tool call in all four tests. Test 1's answer reads "I'm sorry... Booking Platforms: Websites like Booking.com...".
- **Every participant hits this.** The 384-dimensional file is tracked in git, and `build_faiss_if_needed()` only checks whether the file exists. It never builds one.
- **Fix:** Keep FAISS as Module 2's standalone vector-RAG baseline and rebuild `faqs_vector.index` at 1024 dimensions using the shared Nova embedding contract: `EMBEDDING_MODEL_ID`, `EMBEDDING_DIMENSIONS`, and `EMBEDDING_PURPOSE` from `workshop.retrieval_contract`.
- **Source the vectors only from the graph, not from 300 new Bedrock calls.** The vectors already exist. Every one of the 300 `faqs_docs.json` texts is byte-identical to its `data/*.txt` file and the longest is 7,442 characters. `graph_config.CHUNK_SIZE` is 12,000 with zero overlap, so each document becomes exactly one `Chunk` whose text is the whole document. Module 1 embeds those chunks through `BedrockEmbeddings`, which is pinned to the same model, the same purpose, and the same 1024 width that the notebook's `_embed` sends. The rebuild script should read the 300 chunk vectors out of Neo4j and write them to FAISS in `faqs_docs.json` order. A missing, duplicate, null, or wrong-width Aura row is an export failure, not a reason to silently switch embedding sources.
- **Why that beats re-embedding:** it removes the cost, quota exposure, and throttling risk from the rebuild, and it prevents the standalone FAISS baseline from drifting onto a second embedding space. The Module 2 graph arm still uses structured Cypher rather than vectors. The benefit is that FAISS and the Neo4j vector retrieval introduced in Module 3 start from the same stored embeddings while the two modules retain different teaching goals.
- **Commit a compatibility manifest:** Add `faqs_vector.manifest.json` beside the index with these values:
  - `embedding_model_id`
  - `embedding_dimensions`
  - `embedding_purpose`
  - `document_count`
  - `corpus_sha256`, the SHA-256 checksum of the exact committed `faqs_docs.json` bytes
  - `faiss_metric`, the metric the index was built with
  - `vectors_sha256`, a digest over the raw vector bytes read back out of the index
  - `vector_source`, fixed to the graph's `Chunk.embedding` export path
  - `vector_normalization`, the normalization applied before indexing and querying
- **Decide the metric explicitly.** The original index was an `IndexFlatL2`, file magic `IxF2`, `d` 384, `ntotal` 300, while Neo4j's chunk index is cosine, and nothing recorded that difference. If the Nova vectors are not unit-norm then an L2 baseline ranks differently from Module 3's Neo4j retrieval for a reason that has nothing to do with the lesson. **Settled:** the rebuild L2-normalizes every vector and stores them in an `IndexFlatIP`, so the baseline ranks by cosine like the graph side. The manifest records `faiss_metric` and `vector_normalization`, and the loader rejects any index that is not inner product.
- **Validate before use:** Loading the baseline must fail with a descriptive error unless all of these hold:
  - the manifest's embedding values equal the shared contract constants
  - `index.d == manifest.embedding_dimensions == EMBEDDING_DIMENSIONS`
  - `index.ntotal == manifest.document_count == len(documents)`
  - the computed corpus checksum equals `manifest.corpus_sha256`
  - the metric recorded in the manifest matches the metric of the loaded index
  - `manifest.vector_source` names the graph `Chunk.embedding` export and `manifest.vector_normalization` matches the query-normalization path
  - the digest of the vectors read back out of the index equals `manifest.vectors_sha256`
- **Shape checks alone are not enough.** Every check in the first four bullets above tests shape. An index whose bytes are corrupted but whose `d` and `ntotal` are still right passes all of them. That is what `vectors_sha256` is for.
- **Make the artifact reproducible:** Commit the facilitator-side rebuild script that walks `faqs_docs.json` in its stored order, pulls each document's vector from the graph, writes the index, and writes the manifest. Participants load the pre-built artifacts; they should not spend the workshop making 300 embedding calls.
- **Do not swallow retrieval failures:** Remove the broad `except Exception` in `search_faqs`, or re-raise with context. Returning `"Query error:"` as an ordinary tool result is what allowed an end-to-end notebook run to look successful while every retrieval had failed.
- **Show the evidence:** Before each vector-agent answer, display the raw retrieved-document set, including filenames, FAISS distances or scores, and the complete document text actually passed to the model. Use a scrollable or collapsible display if needed. The model's response is an observation; the retrieved evidence is the deterministic part of the demonstration.
- **Recommendation:** This is the only recommended architecture. Module 2 should remain the comparison between standalone FAISS document retrieval and structured Cypher over Neo4j. Module 3 owns Neo4j vector, hybrid, and graph-enriched retrieval patterns; moving Module 2 onto Neo4j's vector index would blur that boundary.

#### M2-2. Even with M2-1 fixed, two of the four tests still fail for a hidden reason

- **Where:** `search_faqs` in cell 8, `doc['text'][:500]`.
- **What is wrong:** Each document is cut to 500 characters before the model sees it. In every source document the word "Spa" first appears around offset 2,000 and "Pool" around 2,800. Both are past the cut.
- **Why it matters:** The counting test and the multi-criteria test would fail because of truncation, not because of how vector search works. The prose never mentions truncation, so the participant draws the wrong conclusion. The first 500 characters do contain `Guest Rating` and `Total Rooms`, so the averaging test would work.
- **Fix:** Remove the slice and pass the complete retrieved document to the model. Do not replace 500 with another unexplained constant.
- **Recommendation:** The lesson is about which documents top-k retrieval selects, so do not let a second, hidden truncation step cause the failure.

#### M2-2a. Test 1 can retrieve the complete Paris set even though the prose says it cannot

- **Where:** notebook cell 9 and `index.en.md:42`.
- **What is wrong:** The graph contains two Paris hotels and the FAISS baseline asks for three documents. A `k=3` search can retrieve both Paris documents, whose text contains both ratings, and the model can then compute the correct 4.7 average. The claim that three retrieved documents cannot cover every Paris hotel is not guaranteed and may be false in the repaired run.
- **Why it matters:** Fixing the index can turn the first headline failure into a success. That would teach that vector retrieval cannot aggregate when the actual example just gave it the complete qualifying set.
- **Fix:** Change Test 1 to a city with more matching hotels than `k`. Use Orlando: the live graph contains five Orlando hotels and their average rating is 4.62. With `k=3`, the vector arm is provably missing at least two qualifying documents even if its ranking is perfect.
- **Confirmed at source:** there are five Orlando documents, rated 4.7, 4.5, 4.6, 4.7, and 4.6, so the mean is exactly 4.62.
- **Keep both build paths deterministic:** Add all five Orlando source documents to the lite-build selection, and have the readiness cell report the rated Orlando hotels it found rather than hard-failing, on the same report-do-not-gate principle as M2-7. Update the notebook, page, README, expected result, and both diagrams together.

#### M2-2b. Test 2 has a knowable ground truth and states none

- **Where:** notebook cells 12, 13, and 14, and the counting row of cell 0's table.
- **What is wrong:** The query is "How many hotels in the database have a swimming pool?" and no surface anywhere states the right answer, so a participant reading the output cannot tell a correct count from a wrong one.
- **The answer is derivable.** 175 of the 300 source documents name a pool in their amenity bullet list. The other 125 carry an explicit "Pool facilities are not available at this property" section. The two add to exactly 300.
- **Those 125 negations are a hazard for the count.** If the extraction turned any of them into a `Pool` amenity, the graph's count is inflated, and the test reports a confident wrong number with nothing to check it against.
- **Fix:** Print the source-derived count of 175 beside the graph's count. Marking a test optional in the learner path does not excuse it from having a right answer.

#### M2-3. Neither agent pins a model

- **Where:** cell 8. Both `Agent(...)` calls omit `model=`.
- **What is wrong:** Strands falls back to its own default, `global.anthropic.claude-sonnet-4-6`. The workshop pins `us.anthropic.claude-sonnet-5` in `bedrock_providers.py:66`.
- **Why it matters, three ways:**
  - Module 1's cell 23 teaches "use a fixed model" one notebook earlier, and shows `BedrockModel(model_id="us.anthropic.claude-sonnet-5")`. Module 2 is the only notebook in the workshop that ignores that advice, and it is the only notebook whose whole purpose is comparing two outputs.
  - The `global.` inference profile needs its own Bedrock grant. Module 2 can fail with `AccessDeniedException` in an account where everything else works.
  - `setup/verify_setup.py:282` checks `default_model_id()`, which is not the model Module 2 uses. Setup can pass and Module 2 still fail.
- **Proposed fix:** Pass `model=BedrockModel(model_id=default_model_id())` to both agents.
- **Recommendation:** Do it. It is a two-line change and it closes a real access risk.

#### M2-4. The participant's AWS region is ignored

- **Where:** cell 3 calls `configure_aws_region()`. Cell 5 calls `load_dotenv(find_dotenv())`.
- **What is wrong:** The order is backwards. At cell 3 the `AWS_REGION` from `.env` is not loaded yet, so region resolution falls through to the profile or to `us-east-1`, and writes that into the environment. `load_dotenv` defaults to `override=False`, so cell 5 cannot correct it.
- **Why it matters:** A participant in any other region silently runs the entire module against `us-east-1`. `.env.example` ships `AWS_REGION`, and `aws_region.py:32` says that variable is the one a participant edits.
- **Proposed fix:** Move `load_dotenv(find_dotenv())` above `configure_aws_region()`, matching Module 1's cell 3.
- **Recommendation:** Do it. Module 1 already has the correct order, so this is bringing Module 2 in line.

#### M2-5. Sessions do not name the database

- **Where:** cells 5 and 8. `GraphDatabase.driver(...)` then `.session()` with no `database=`.
- **What is wrong:** Module 2 hand-rolls its connection instead of using `workshop.graph_connection`, which exists to stop this. Module 1 passes `database=graph_database()` in six places.
- **Why it matters:** With `NEO4J_DATABASE` set, Module 2 reads a different database than the one Module 1 wrote to. Every test returns "No results found." and nothing raises an error.
- **Proposed fix:** Use `require_neo4j_env()`, `neo4j_auth()`, and `session(database=graph_database())` from the shared helper.
- **Recommendation:** Do it in the same pass as M2-6.

#### M2-6. Module 2 reads a credential variable the shared helper rejects

- **Where:** cell 5. `os.getenv('NEO4J_USERNAME', os.getenv('NEO4J_USER', 'neo4j'))`.
- **What is wrong:** `graph_connection.py:5` states that the older `NEO4J_USER` spelling is deliberately not read. Cell 5 reads it anyway, and reimplements the missing-variable check that `require_neo4j_env()` already does.
- **Why it matters:** Two places now define what a valid environment looks like, and they disagree.
- **Proposed fix:** Delete the hand-rolled block and call the shared helper.

### Wrong facts in the content

#### M2-7. Test 3 proves nothing, because nothing gets filtered out

- **Where:** `index.en.md:61` and `:63`, notebook cell 15.
- **What is wrong:** There is exactly one hotel whose address contains "Cairo", and it already has both a spa and a pool. So "Cairo hotels with a spa and a pool" returns the same single row as "Cairo hotels". The AND condition excludes nothing.
- **Live result:** 1 row, AnyCompany Cairo Nile View, rating 4.5.
- **Also wrong:** The prose is plural in both places. And the `select_lite_files` docstring in `graph_config.py` claims the opposite, saying the Cairo query has more than one hotel to work with.
- **Why it matters:** The test is supposed to show that a graph applies every condition while similarity ranking does not. As written the claim cannot be observed either way.
- **Fix:** Use Chicago with the existing spa-and-pool criteria. The live graph has two Chicago hotels: Lakeview Horizon Suites has both amenities, while Windward Mile Tower has neither. The AND predicate therefore returns one hotel and visibly excludes the other.
- **Confirmed at source:** `hotel-chicago-001.txt` is Windward Mile Tower, rated 4.5, and its amenity bullet list names no pool and no spa. `hotel-chicago-002.txt` is Lakeview Horizon Suites, rated 4.4, with an Outdoor Swimming Pool and a Full-Service Spa.
- **The lite build can undo this.** Windward Mile Tower's Pool section reads "Pool facilities are not available at this property." `Amenity` carries only `name` and `description` and has no availability flag, so nothing stops the extraction from minting a `Pool` amenity out of that negation. On the full build it does not matter, because Chicago comes from the frozen dump. On the lite build both documents are re-extracted live, and if the negation is extracted as an amenity then Test 3 returns two rows and excludes nothing, which is this same defect again.
- **Report, do not gate.** A hard readiness fixture turns a stochastic extraction into a stochastic notebook failure. Have the readiness cell query the graph for a city with at least two candidates, at least one match, and at least one exclusion, prefer Chicago, and print the city and the counts it actually found. The prose documents Chicago and says the cell prints the live numbers.
- **Also fix:** the false claim that Cairo has more than one hotel to work with. It is in the `select_lite_files` docstring in `graph_config.py`, not at line 50, and `REQUIRED_CITIES` is still `("paris", "cairo")`.

#### M2-8. Both module images contain wrong facts

- **Where:** `workshop-content/images/01-rag-vs-graphrag-problem.png` and `01-rag-vs-graphrag-architecture.png`.
- **The problem diagram:**
  - Shows the Paris average as 4.21. The live answer is 4.7. The average across all hotels is 4.6. 4.21 matches nothing.
  - Says "computed across all 300 hotels". There are 292 hotels, and the Paris query touches 2 of them.
  - Draws a `City` node type. Module 1's page now lists `City` and `Country` as the exact schema drift the pinned schema exists to prevent. The live graph has zero of them.
  - Shows a "fabricated average 3.6" that appears in no run.
  - Has a stray bracket in `AVG()]`.
- **The architecture diagram:**
  - Runs `MATCH (h:Hotel) RETURN AVG(h.rating)`. The property is `guest_rating`. `h.rating` exists on zero of 292 hotels, so the query returns null. The notebook's own tool docstring warns about exactly this mistake.
  - Arrows flow downward into a "Same user query" box at the bottom, which reverses cause and effect.
  - One box renders as two empty shapes.
  - Says "300 Hotel FAQ Documents" over the graph side, where the hotel count is 292.
- **This is authoring, not editing.** These two are the only images in the repository with no `.drawio` source, and `workshop-content/images/DIAGRAM_PROMPTS.md` sits beside them, which is the likely reason they carry 4.21, a `City` node, `h.rating`, a stray bracket, and a doubled box. There is nothing to correct, so both have to be built from scratch.
- **Both images live in two trees.** `workshop-content/images/` and `static/images/` hold byte-identical copies. A fix that lands in one leaves a stale copy in the other.
- **Proposed fix:** Author both as new `.drawio` sources, the way every other diagram in the workshop is authored, and export the PNGs into both trees. Draw them around the repaired Orlando test. Use 4.62 across five matching Orlando hotels, `guest_rating`, no `City` node, and arrows that start at the user query. Keep the vector side explicitly labeled as the standalone FAISS baseline so the diagram does not pre-empt Module 3.
- **Give this its own owner.** Redrawing from scratch is a different skill and a different deliverable from the prose pass, and it should not ride along with it.
- **Consider dropping one of them.** Two diagrams ahead of the module's first cell is a lot, and every fact in them is another thing that has to stay in sync with the notebook.
- **Recommendation:** Do this before any live delivery. These are the first two things a participant sees in the module, and one of them contradicts what Module 1 just taught.

#### M2-9. "Chunks" is the wrong word throughout

- **Where:** `index.en.md` lines 8, 14, 15, 42, 55, 63. Notebook cells 0, 12, 15, 18. `README.md` lines 11, 28, 29, 41.
- **What is wrong:** `faqs_docs.json` holds 300 entries, one per whole document, averaging 7,276 characters. Nothing is chunked. The FAISS store indexes whole documents, and `search_faqs` then truncates each one to 500 characters.
- **Why it matters:** A participant who just finished Module 1 learned that a chunk is a specific node type with an embedding on it. Module 2 uses the same word for something else.
- **Proposed fix:** Say "documents" everywhere the code means the whole entries in `faqs_docs.json`. Keep `Chunk` for Neo4j's actual `Chunk` nodes in Modules 1 and 3.

#### M2-10. The README claims both agents read the graph

- **Where:** `README.md:12`, "Both agents read the graph restored during Setup, including the five hotels added in Module 1."
- **What is wrong:** The vector agent reads a committed FAISS file. It never touches Neo4j.
- **Related:** `README.md:13` says Amazon Nova creates the query embeddings. That is true of the code and false in effect, because the index rejects those embeddings (M2-1).
- **Proposed fix:** Say that the vector agent reads a committed FAISS index over the 300 source documents while the graph agent reads the Neo4j graph extracted from that corpus. They share an underlying source corpus, not a storage engine or an identical representation.

#### M2-11. "Multi-hop" is one hop

- **Where:** `index.en.md:16`.
- **What is wrong:** `Hotel-[:OFFERS_AMENITY]->Amenity` is a single hop. Module 1's page now says every domain relationship starts at `Hotel`, so each document produces a one-hop star.
- **Note:** The notebook heading and the README both say "multiple criteria", which is correct. Only the content page overclaims.
- **Proposed fix:** Use "multiple criteria" on the page too.

#### M2-12. "Text2Cypher" is used wrongly and before it is defined

- **Where:** `index.en.md:30`.
- **What is wrong:** The notebook does not use `Text2CypherRetriever`. It uses a hand-written `@tool` whose docstring carries the schema and lets the model write raw Cypher. `Text2CypherRetriever` is Module 3's subject and is defined there, not here.
- **Proposed fix:** Delete the term, or describe the actual mechanism.

#### M2-13. The prose states what the model will do

- **Where:** `index.en.md:42`, `:55`, `:72`. Notebook cell 0's table, twice. Notebook cells 11, 13, and 14 print "Vector agent reasons from 3 documents" unconditionally, after the fact, regardless of what happened.
- **What is wrong:** These are LLM calls. The output varies. The page says "It will return results from similar-looking documents and the LLM may fabricate details."
- **Refuted by the live run:** On the Antarctica test the agent did not fabricate. It answered that Antarctica has virtually no traditional hotels and explained the Antarctic Treaty System.
- **Why it matters:** A current Claude given three irrelevant hotel documents is likely to notice they are irrelevant. Test 4 probably will not produce a hallucination even after M2-1 is fixed, and the module's title rests on it.
- **Proposed fix:** Reframe test 4 around what is actually observable and always true. The retriever gives no signal that its results are irrelevant, and the model has to notice on its own. Change the unconditional print lines to report what happened rather than what was expected.
- **Recommendation:** Do this. A test whose stated outcome does not reproduce is worse than no test.
- **Test status:** Keep all four tests. Treat Tests 1 and 3 as the core path. Mark Test 2 as an optional reinforcement of the same complete-set limitation as Test 1, and Test 4 as an optional observation because the model's response to irrelevant neighbors is stochastic. Optional does not mean unverified: all four retrieval paths still need automated execution coverage.

#### M2-14. Token numbers are cumulative, and the prose says they are comparable

- **Where:** cell 9 tells the participant the numbers let them compare token usage between the two agents.
- **What is wrong:** The same two `Agent` objects run all four tests, so `accumulated_usage` is a lifetime sum. The graph agent reaches 11,981 by test 4. Tool counters carry over too, so by test 4 each agent has four turns of prior history.
- **Why it matters:** In test 4 the vector agent already knows from earlier turns that its tool is broken, which changes its answer.
- **Proposed fix:** Create fresh agents per test. If the reuse is deliberate, say the numbers are cumulative.
- **Recommendation:** Fresh agents per test. It gives clean per-query numbers and removes the cross-test contamination.

#### M2-15. Dead configuration guidance and unused imports

- **Where:** cell 3's trailing comment tells the participant to set `MODEL = OpenAIModel(model_id="gpt-4o-mini")`.
- **What is wrong:** Nothing reads a `MODEL` variable, because neither agent takes a `model=` argument. Following the instruction does nothing.
- **Also:** `from pathlib import Path` is unused. `os` is imported three times, in cells 2, 3, and 5.
- **Proposed fix:** Delete the comment and the unused imports. If M2-3 is fixed, the comment could become real guidance.

#### M2-16. The three test names disagree across three surfaces

- **Page:** Aggregation, Counting, Multi-hop, Out-of-domain.
- **README:** Aggregation, Counting, Multiple criteria, No matching data.
- **Notebook headings:** Calculate an Average, Count Matching Hotels, Apply Multiple Criteria, Handle a Question with No Matching Data.
- **Why it matters:** A participant switching between the page and the notebook has to re-map the names each time.
- **Proposed fix:** Pick one set of four names and use it everywhere.

#### M2-17. The tool docstring drifts from the live graph

- **Where:** `query_knowledge_graph` in cell 8. This docstring is the graph agent's entire model of the schema.
- **What is wrong:**
  - `Amenity` properties omit `fee`, which is present on 32 of 83 nodes.
  - `Service` appears in the relationship list with no properties documented. The live node has `name`, `description`, `is_complimentary`, `is_available`, `hours`, and `cost`.
  - `Hotel` omits `hotel_id`, present on 287 of 292.
  - `Document` and `Chunk` are absent entirely.
- **Proposed fix:** Regenerate the docstring from `graph_schema.py` rather than maintaining it by hand.
- **Recommendation:** Worth doing. A wrong schema in the docstring makes the agent write wrong Cypher, and that failure looks like a graph problem.

#### M2-18. The notebook depends on the working directory without saying so

- **Where:** cell 2 uses `os.path.join(os.getcwd(), "..")`. Cell 5 opens the FAISS index and document file by relative path; the repaired version will also open the manifest.
- **What is wrong:** All of those paths need the working directory to be the module folder. The page says only "open the notebook".
- **Evidence this has already bitten someone:** `build_faiss_if_needed()`'s error message interpolates `os.getcwd()`.
- **Proposed fix:** Resolve paths relative to the notebook file, or state the requirement on the page.

### Style and structure

- **One em-dash**, `index.en.md:33`. The rest of the module is clean.
- **Nine of 21 notebook cells have bare-string sources** instead of lists. Cells 7, 10, 11, 13, 14, 16, 17, 19, 20. The other twelve are lists.
- **21 code lines over 88 characters.** One 110-character token-printing line is copy-pasted into eight separate cells.
- **Trailing whitespace** in cells 5, 7, and 8.
- **Two claims in one sentence** at `index.en.md:8`, `:55`, `:63`, `:72`, and notebook cells 12 and 18.
- **Vague phrasing where a concrete statement belongs.** `:42` says the agent "generates and executes Cypher along these lines". Either show the query it produced, or say the query varies per run. `:42` also says "Run both agents and compare their outputs" without saying what to compare or what a correct answer looks like.
- **Three bare arXiv links** under a `**Research background:**` label in the notebook's opening cell. No subject and verb after the label, and no sentence saying what the papers establish or why to open them.
- **Cells do not lead with their purpose.** Cell 4 is a bare heading, followed by cell 5, the largest and most consequential cell in the notebook, with no prose. Cell 6 is a bare heading followed by a 40-line `HookProvider` class with no explanation of what a Strands hook is.
- **Token instrumentation is buried inside Test 1.** It is a general topic and belongs before the tests. The content page never mentions token metrics at all.
- **The notebook has no closing cell.** It ends on a `print()`. No summary and no pointer to Module 3. The page has a Next section; the notebook does not.

### Missing explanation

- **The core mechanism is asserted eight times and explained zero times.** Nowhere does the module say why vector search cannot aggregate. The reason is simple: an approximate-nearest-neighbour index returns a fixed-length list ranked by distance and has no aggregation operator, so any count or average has to be computed by the model from whatever documents it happened to receive. Module 1's page now has exactly this kind of paragraph for why an embedding of `60611` ranks badly. Module 2 needs its equivalent.
- **`k=3` is never explained, and the honest limit is never stated.** Raising `k` would partly fix aggregation, until context and cost stop you. As written the module implies impossibility where the truth is a ceiling.
- **Why FAISS is separate is never answered.** Module 2 should say that FAISS is deliberately retained as a minimal standalone document-RAG baseline. Module 3 then introduces Neo4j vector retrieval, hybrid retrieval, and graph enrichment. The separation is curricular, not an endorsement of maintaining two production embedding stores. The rebuilt FAISS artifact must still use the workshop's shared Nova model, purpose, and width so the baseline is compatible and reproducible.
- **The Module 1 relationship is never stated.** Module 2 has no hard dependency on Module 1. It never touches either retrieval index, never queries the held-out hotels, and its FAISS file is committed. Ordering is enforced only by page weight. The README asserts a dependency that does not exist. The notebook prints a hotel count with no expected value, so a participant cannot tell whether their graph is right.

---

## Recommended order of work

1. **M2-1**, the dimension mismatch and missing artifact contract. The artifact half is complete and committed: the index is rebuilt at 1024 dimensions from the graph's chunk vectors, the metric is settled, and the manifest, rebuild script, vector checksum, fixed source, and tests are in place. The notebook-side validator and error-handling work remain open.
2. **Phase 1.5**, the empirical comparison gate. Run 1 is complete and its conclusions are retracted: the vector arm received an anti-fabrication instruction the graph arm did not, and the judge used the graph's own extraction output as ground truth. Run 2 corrects both, removes the graph tool's row caps, adds traversal questions, and raises the trial and judge-sample counts. The module title stays undecided until run 2 lands. See the Phase 1.5 section for the full defect list.
3. **M2-2 and M2-2a**, the hidden truncation and invalid Paris aggregation example. Pass complete documents and use the five-hotel Orlando set so `k=3` is provably incomplete.
4. **M2-3, M2-4, M2-5, M2-6**, the four environment and configuration bugs. All are small, all are already solved correctly in Module 1, and all can be done in one pass.
5. **M1-1**, the one-line cleanup fix in Module 1's optional demo.
6. **M2-7 and M2-2b**, tests 3 and 2. Replace Cairo with the verified Chicago comparison, add its lite-build selection and its reporting readiness cell, and give the pool count its source-derived answer of 175.
7. **M2-13**, test 4 and test status. Reframe it around observable retrieval behaviour, retain all four tests, and mark Tests 2 and 4 optional in the learner path.
8. **M2-8**, the two images. Authored from scratch as `.drawio` sources by their own owner and exported into both image trees. Required before any live delivery.
9. **M2-14, M2-15, M2-16, M2-17, M2-18**, the remaining code and consistency fixes.
10. **The prose pass**, covering the style items, the missing explanations, and the Module 1 relationship.

The single highest-value change is rebuilding the FAISS baseline with an explicit compatibility contract. Build it from the chunk vectors the graph already holds: that costs nothing, it is repeatable, and it puts both arms on one embedding space, which is the comparison the module is trying to make. It restores every demonstration without collapsing Module 2 into Module 3. The next highest-value change is replacing Paris with Orlando: a working index is not enough if the headline example can retrieve the complete qualifying set and answer correctly.

---

## Implementation plan

### Goal

Restore Module 2 as a reliable comparison between standalone FAISS document retrieval and structured Cypher over Neo4j, while keeping Module 3 responsible for Neo4j vector, hybrid, and graph-enriched retrieval patterns.

### Assumptions

- FAISS remains the only vector store used by Module 2.
- The committed FAISS artifact uses the shared Nova embedding model, purpose, and 1024-dimension width.
- The committed FAISS vectors are the same vectors Module 1 wrote onto the graph's `Chunk` nodes, exported rather than recomputed.
- Participants load the committed index and do not make 300 document-embedding calls.
- Tests 1 and 3 are the core learner path. Tests 2 and 4 remain in the notebook as optional exercises.
- All four tests remain in automated execution coverage even when some are optional for learners.
- The raw retrieval result is the deterministic evidence. The LLM answer is an observed outcome and is not used as the sole pass condition.
- "Vector RAG Hallucinates" is a hypothesis until Phase 1.5 measures the repaired baseline. The title and learner-facing claims may change based on that evidence.
- Existing unrelated working-tree changes are preserved.

### Risks

- The graph-sourced rebuild depends on an Aura graph holding all 300 source documents with exactly one embedded chunk per filename. A lite, partial, duplicated, or stale graph must fail validation rather than mix embeddings from a fallback source.
- FAISS IDs are positional. Any change to document ordering without rebuilding the index can silently associate a vector with the wrong document.
- A valid dimension alone does not prove compatibility. The model, purpose, metric, corpus bytes, document count, index size, and stored vector bytes must agree too. An `IndexFlatL2` baseline and Neo4j's cosine chunk index rank differently unless the vectors are unit-norm.
- The corpus carries 125 explicit "not available" amenity sections. LLM extraction can turn a negation into a positive amenity, which silently breaks any test that depends on a hotel being excluded.
- Full documents increase the model context compared with the current 500-character previews. Token usage and context limits must be measured after truncation is removed.
- LLM wording remains stochastic. Assertions about exact model prose will be brittle.
- Phase 1.5 requires repeated, cost-bearing Bedrock calls. Its report must record the model, region, artifact checksum, graph state, run time, and trial count so later runs can explain different outcomes.
- The repository already contains unrelated uncommitted notebook and content edits, so each worker needs exclusive file ownership and a narrow patch.

### Parallel execution model

Use at most three worker agents at a time alongside the coordinating agent. Work proceeds in waves so tasks with stable interfaces run together and content work waits for the final queries and outputs.

- **Artifact agent, complete:** Delivered the FAISS rebuild script, `faqs_vector.index`, `faqs_vector.manifest.json`, shared loader and query normalization, and focused artifact-contract tests. It did not edit the Module 2 notebook or learner content.
- **Evaluation agent, complete:** Delivered `setup/phase15/`, holding the comparison harness, the deterministic reference-fact module, the report generator, the raw evidence, and the findings. It edited no notebook, learner content, fixture, or diagram.
- **Notebook agent, pending:** Owns the Module 2 notebook runtime: environment loading, pinned model, shared Neo4j connection helpers, manifest validation at load, complete document delivery, visible retrieval evidence, fresh agents per test, and exception handling. It must not rebuild or replace the committed FAISS artifacts.
- **Fixture agent, pending:** Owns `graph_config.py`, the lite-build selection, the readiness cells, and their tests. Its job is to make the five rated Orlando hotels and the filtering Chicago pair present in the full build and reported in any build, not to gate the notebook on an extraction it cannot control. It does not edit the notebook or images.
- **Content agent, pending:** Starts after the Orlando and Chicago contracts are stable. Owns the Module 2 README and the workshop page. It does not write the notebook, and it does not draw the diagrams.
- **Diagram agent, pending:** Owns the two new `.drawio` sources and the exported PNGs in both image trees. Starts once the Orlando numbers are final.
- **Coordinating agent:** Owns the plan, resolves overlaps, integrates the worker patches, runs repository-wide validation, and performs the final factual review.

**One agent writes the notebook.** The notebook agent is the only writer of `2.1_vector_rag_hallucinates.ipynb`. Two agents editing one JSON file cannot be parallelized safely, and nine of the 21 cells still carry bare-string sources, so concurrent rewrites produce diffs nobody can review. Prose changes to notebook cells go to the notebook agent as a patch, and it applies them.

### Phase 1: Rebuild and contract the FAISS artifact

**Status: Complete**

`notebooks/workshop/faiss_artifacts.py`, `notebooks/02-vector-rag-hallucinates/rebuild_faiss_index.py`, `faqs_vector.manifest.json`, `setup/test_faiss_artifacts.py`, and `setup/test_rebuild_faiss_index.py` are committed with the rebuilt `faqs_vector.index`. Verified: `IndexFlatIP`, `d` 1024, `ntotal` 300, vector norms within floating-point tolerance of 1.0, manifest and vector checksums matching, fixed Aura provenance, 16 tests passing, and Ruff clean.

**Outcome:** A reproducible 1024-dimension FAISS artifact that fails loudly when its model, purpose, metric, corpus, ordering, vector bytes, or dimensions drift.

**Checklist:**

- [x] Add a facilitator-side rebuild script that walks `faqs_docs.json` in its stored order and reads each document's vector from the graph's matching `Chunk`.
- [x] Reject missing filenames, duplicate chunks, null embeddings, and wrong-width vectors; do not fall back to a second embedding source.
- [x] Decide the FAISS metric. Settled: L2-normalized vectors in an `IndexFlatIP`, which makes the baseline rank by cosine like Neo4j's chunk index, with the loader rejecting any other metric.
- [x] Add the manifest dataclass, the corpus checksum, and a loader that validates the contract fields, `index.d`, `index.ntotal`, and the document count.
- [x] Add negative tests that prove each mismatch produces a descriptive failure.
- [x] Extend the manifest and the validator with `faiss_metric` and `vector_normalization`, and add their negative tests.
- [x] Extend them with `vectors_sha256` and the fixed graph `vector_source`, and add negative tests that reject source drift and same-shape vector-content tampering.
- [x] Rebuild `faqs_vector.index` at 1024 dimensions.
- [x] Commit the rebuilt `faqs_vector.index` and `faqs_vector.manifest.json`.
- [x] Run the artifact tests and record the rebuilt index size, vector count, dimension, and metric.

**Validation:** The index loads as 1024-dimensional with 300 vectors at the recorded metric; the manifest matches the shared contract, the exact corpus bytes, and the vectors actually stored; deliberately altered test fixtures fail for the expected reason; a vector-byte corruption that leaves `d` and `ntotal` intact is still rejected.

**Notes:** The graph export removes the cost and throttling exposure of a 300-call rebuild. Aura access and a complete graph are facilitator-side artifact-build prerequisites; participants still use the committed FAISS artifact without Aura access on the vector arm.

### Phase 1.5: Test the repaired FAISS baseline against Neo4j

**Status: Run 1 complete and retracted. Run 2 complete with one grading defect. Gate
decision recorded below.**

Run 2 ran 2026-08-21 as six parallel slices, one per question, each covering both arms and
both prompt conditions at 10 trials per cell. That is 240 trials and 720 judge calls. All
six slices exited cleanly and every cell holds exactly 10 trials. Run 2's factuality
labels are usable. Its grounding labels are not, for the reason given under Defect E.

#### Run 1, 2026-08-21: retracted

Run 1 executed 48 fresh-agent trials, 6 per question per arm, against
`us.anthropic.claude-sonnet-5` in `us-east-1` and the staging Aura instance. No tool
error was swallowed and every trial's raw evidence was saved. The run reported that the
vector arm produced zero fabrications and concluded that the module title was refuted.

**That conclusion is withdrawn.** The judged comparison carries four design defects, and
the first one alone can produce the observed result. The raw evidence is kept at
`evidence/phase15/evidence/phase15-merged.json` and the tables at
`evidence/phase15/PHASE-1.5-REPORT.md`, because the deterministic measurements in them
remain valid. The conclusions in `evidence/phase15/PHASE-1.5-FINDINGS.md` do not.

**The scoreboard also does not say what the run 1 summary said.** On the judge's own
labels the graph arm scored 24 correct out of 24 and the vector arm scored 15 correct, 8
partial, and 1 incorrect. The graph arm won every question. The claim that "the graph arm
is confidently wrong on pool counting" was an analyst's reading laid over the data using
the source count of 175, and it was not a result the harness produced. The judge scored
all six of those graph answers `correct` and `grounded`.

**Defect A, the vector arm received an anti-fabrication instruction that the graph arm
did not.** The notebook's prompt is "You are a travel agent. Use vector search to find
relevant FAQ information." The harness used that plus one added sentence, "Base your
answer on what the search returns." The graph arm received the notebook's prompt nearly
verbatim. The added sentence is the exact intervention that converts fabrication into
hedging, so the headline finding was measured under a treatment the module does not
apply and the other arm did not get. This confound alone can explain the entire result.

**Defect B, the graph's own output was used as ground truth for both arms.** The judge
received `source` facts and `graph` facts together and settled on the graph value in
every case. Its rationales grading the *vector* arm read "the true count is 168 hotels
with pools," where 168 is what extraction produced and 175 is what the corpus says. The
graph was therefore graded against itself, and the vector arm was penalised for failing
to reach a number the corpus does not contain. This is a pro-graph bias in the rubric,
and it means the harness never tested the 175 against 168 question that run 1 reported on.

**Defect C, truncation was removed from one arm and left in the other.** The vector tool
returned complete document text, which is the M2-1 repair. The graph tool still capped
its returned text at 15 rows and its recorded evidence at 50. Fifteen graph calls
exceeded the display cap, including seven Chicago calls returning 23 to 50 or more rows.
The judge saw complete evidence for the vector arm and truncated evidence for the graph
arm.

**Defect D, no question in the set is one a graph is expected to win.** The four
questions cover aggregation, counting, conjunction, and no-match. None requires
traversal, a path, or a relationship-mediated join. The module is sold on multi-hop
reasoning and run 1 never tested multi-hop.

Two further limits are weaker but real. Six trials per cell puts a 95 percent interval of
roughly 15 to 85 percent around the 3-of-6 Orlando result. The judge was a single sample
from the same model family as the agents, with no self-consistency check and no human
adjudication.

**What survives from run 1.** These measurements involve no model and no judge, so the
defects above do not reach them.

- Orlando's five qualifying documents cannot fit inside a `k=3` window. Computed from the
  committed index.
- The graph agent wrote off-schema tokens against a docstring stating the correct schema:
  `LOCATED_IN` 24 times, `City` 20, `HAS_AMENITY` 13, `rating` 13, and `guestRating` 6,
  across 121 tool calls of which 26 percent returned zero rows. M2-17 is confirmed. The
  M2-8 architecture diagram draws the same `City` node and the same `h.rating`, so the
  diagram matches the model's wrong prior rather than the graph.
- The source count of 175 pool hotels reconciles exactly to the graph's 168. Four
  pool-listing documents produced no `Hotel` node, four pool hotels are each shared across
  two documents by entity resolution, and `hotel-austin-001.txt` had its "Pool facilities
  are not available" negation minted into a `Pool` amenity. That last one is M2-7's hazard
  observed live. Per document the extraction is right 295 times out of 296. This is a
  Module 1 extraction finding and it stands on its own, but it is not a Module 2
  comparison finding and run 1 wrongly presented it as one.
- The vector arm was cheaper than the graph arm on three of four questions, with a largest
  mean of 43,345 total tokens. Complete documents caused no context problem. The module
  must not claim the graph arm is cheaper.

Run 1 settles no question about hallucination, and it settles no question about which arm
is better. Both remain open until run 2.

#### Run 2: what changes

1. **Both arms use the notebook's exact system prompts.** A second condition adds the
   grounding instruction to *both* arms, so the prompt effect is measured as a variable
   instead of confounded into one arm.
2. **The judge grades against source facts only.** The graph's extraction gap is reported
   as a separate deterministic finding and is never used as the reference answer.
3. **The graph tool's 15-row and 50-row caps are removed**, so neither arm's evidence is
   truncated relative to the other.
4. **Two traversal questions are added**, so the graph arm is given a question of the kind
   it is supposed to win.
5. **Ten trials per cell, and three judge samples per answer scored by majority vote.**

#### Run 2, 2026-08-21: results

Evidence is at `evidence/phase15/evidence/run2/phase15-run2-merged.json` and the tables are
at `evidence/phase15/PHASE-1.5-REPORT-RUN2.md`.

**Factuality under the notebook prompt, as `correct / partial / incorrect` out of 10.**

| Question | Vector | Graph |
| --- | --- | --- |
| Orlando aggregation | 0 / 10 / 0 | 10 / 0 / 0 |
| Pool counting | 0 / 10 / 0 | 0 / 8 / 2 |
| Chicago multiple criteria | 10 / 0 / 0 | 10 / 0 / 0 |
| Antarctica no match | 10 / 0 / 0 | 10 / 0 / 0 |
| Chicago shared amenities, bounded traversal | 9 / 0 / 1 | 4 / 6 / 0 |
| Suite under $600 with a spa, traversal at scale | 0 / 3 / 7 | 0 / 10 / 0 |
| **Total across 60 trials per arm** | **29 / 23 / 8** | **34 / 24 / 2** |

Adding the grounding sentence to both arms moves almost nothing. The vector arm goes to
31 / 20 / 7 with 2 unscored, and the graph arm goes to 33 / 26 / 1.

**Defect E, the judge's evidence budget silently truncated the grounding axis.** Fix 3
removed the row caps from the graph tool, and `JUDGE_EVIDENCE_BUDGET` then reintroduced
truncation one layer later at 40,000 characters. All 18 `fabricated` labels in the run
fall on trials whose evidence exceeded that budget. Not one of the 153 trials the judge
saw in full drew a `fabricated` label, in either arm. The rationales show the mechanism
directly rather than merely correlating with it. On `suite_and_spa` graph trial 3 the
judge wrote that "the actual tool query returned an empty result set", when the agent's
seventh Cypher call returned 77 rows and the evidence was cut 15,500 characters short of
reaching it. The grounding axis therefore measures what the grader was shown rather than
what the agent did. Fabrication is unmeasured in run 2. It is not disproven.

**The factuality axis survives Defect E.** Reference facts come from the source corpus,
they are small, and they sit at the top of the grader prompt ahead of any truncation. Fix
2 keeps the graph's extraction output out of the reference. The factuality table above
stands.

**What run 2 establishes.**

- **The vector arm's dominant failure is missing evidence, not invention.** Under the
  notebook prompt it returned `insufficient` on 24 of 60 trials against the graph arm's 4.
  On Orlando and on pool counting it was `partial` on all 20 trials, because `k=3` cannot
  supply the qualifying set.
- **The vector arm does state confidently wrong counts on traversal at scale.** On the
  suite-and-spa question it was `incorrect` on 7 of 10 notebook trials, answering "3
  hotels" or "4 hotels" against a source truth of 78. This is graded against source facts
  and no truncation reaches it. It is the strongest un-confounded result in the run.
- **Defect A was not the explanation for run 1's zero fabrications.** Removing the
  asymmetric instruction changed the vector arm's labels very little. Run 1's result came
  from its question set rather than from its prompt.
- **Two of the module's four original questions no longer separate the arms.** Chicago
  multiple criteria is 10 correct out of 10 for both arms under both conditions. Antarctica
  is 10 correct out of 10 for both arms under both conditions. Neither can carry a
  learner-facing contrast.
- **The graph arm loses the bounded traversal question.** On Chicago shared amenities it
  was `correct` on 4 of 10 against the vector arm's 9 of 10. Entity resolution split `WiFi`
  from `Complimentary High-Speed WiFi` into two `Amenity` nodes and hid a shared amenity
  that the raw document text states plainly. This is a Module 1 extraction defect
  surfacing as a Module 2 comparison result.
- **The graph arm costs more.** It averaged 41,956 total tokens and 5.5 tool calls against
  the vector arm's 16,311 and 1.7 under the notebook prompt. The module must not claim the
  graph arm is cheaper.
- **The graph arm answers Antarctica from model memory.** It drew `unsupported_correct` on
  6 of 10 notebook trials and 8 of 10 grounded trials, and the vector arm never did. Both
  arms reach the right answer, and the graph arm reaches it without evidence.

**Four smaller harness defects, all found while reading run 2's output.**

1. The grader's JSON parse requires the entire response to be JSON, so a preamble sentence
   produces an `unscored` trial. This cost 2 trials in the suite-and-spa vector grounded
   cell.
2. The recorded `rationale` always comes from judge sample 0, which disagreed with the
   majority grounding label on 22 of 240 trials. The report prints rationales that
   contradict the label sitting beside them.
3. Three `fabricated` labels won on a plurality of one. All three judge samples disagreed
   and `most_common` broke the tie arbitrarily.
4. `report.py` divides the trial count by questions and arms only, so it reports "20 per
   question per arm" when the real cell size is 10 per question per arm per condition.

**Gate result: the module title is not supported, and the rename is not yet safe to
finalize.** The factuality evidence refutes "Vector RAG Hallucinates" as a description of
what the repaired baseline does. The vector arm's failures are missing evidence and
undercounting, and both are retrieval-limit failures rather than invention. That supports
renaming the module around incomplete top-k evidence and retrieval limits. The decision is
held one step short of final because Defect E leaves hallucination unmeasured, so the
rename must not be justified by a claim that the vector arm never fabricates. Rescoring
run 2's saved evidence with the judge budget removed will settle it, and that needs no new
agent trials. Phase 3 and Phase 4 stay blocked on the rescore.

**Outcome:** An evidence report that determines whether the repaired Module 2 comparison actually demonstrates hallucination, merely demonstrates incomplete top-k evidence, or produces different outcomes across runs. Phase 2 must use this result rather than preserving the module title and claims by assumption.

**Definitions:**

- **Grounded and correct:** Every material claim follows from the tool evidence and agrees with the applicable source or graph result.
- **Correct but unsupported:** A claim happens to be factually correct but is not supported by the retrieved documents or graph result.
- **Insufficient-evidence response:** The model declines, qualifies its answer, or states that the retrieved evidence cannot establish the requested corpus-wide result.
- **Incorrect or fabricated:** The answer conflicts with the evidence or introduces unsupported specific hotels, values, amenities, or counts.

The report must score factual correctness and grounding separately. A correct statement about Antarctica from model memory is unsupported by the hotel corpus, but it is not the same failure as inventing a hotel or a numeric result.

**Checklist:**

- [x] Build a standalone comparison harness that uses the committed manifest-validated FAISS artifact, normalized query vectors, the pinned workshop model, shared AWS and Neo4j configuration, and read-only database sessions.
- [x] Keep the harness independent of the current Module 2 notebook so the notebook's known loading, truncation, model, history, and exception-handling defects cannot contaminate the result.
- [x] Run the intended four questions: Orlando aggregation, pool counting, Chicago multiple criteria, and Antarctica no-match handling.
- [x] Record the raw FAISS filenames, cosine-equivalent scores, and complete document text before every vector-agent answer.
- [x] Record the generated Cypher, raw Neo4j result, and final graph-agent answer for the same question.
- [x] Establish deterministic reference facts from the source documents and from Neo4j separately. Do not call a graph aggregate the corpus ground truth when extraction omitted or misclassified a source fact.
- [x] For Orlando, verify that the source and graph each contain five rated hotels, that the reference mean is 4.62, and that `k=3` cannot supply the complete qualifying set.
- [x] For pool counting, report the source-derived count of 175 and the Neo4j count separately, then explain any extraction gap before comparing either agent answer.
- [x] For Chicago, verify the source documents and live graph candidate set, matching set, and exclusions before judging either answer.
- [x] For Antarctica, verify that FAISS still returns three nearest documents and Neo4j returns no matching hotel, then distinguish refusal, unsupported outside knowledge, and fabrication in the final answers.
- [x] Use fresh agents for every invocation and run at least three independent trials per question and retrieval arm so one stochastic response does not decide the module's claim.
- [x] Capture per-trial token usage, tool calls, retrieved evidence, final answer, factual-correctness label, grounding label, and concise rationale.
- [x] Summarize results by question and retrieval arm, including how often the vector agent was grounded, insufficient, unsupported-but-correct, or incorrect/fabricated.
- [x] Give both arms the notebook's own system prompt, and measure any added grounding instruction as a condition applied to both arms rather than to one.
- [x] Grade every answer against source-derived facts, and report the graph extraction gap separately instead of using a graph aggregate as the reference answer.
- [x] Remove the graph tool's row caps so neither arm's evidence is truncated relative to the other.
- [x] Add traversal questions that a knowledge graph is expected to answer better than top-k retrieval.
- [x] Run at least ten trials per cell and take three judge samples per answer, scoring by majority vote.
- [ ] Remove or raise `JUDGE_EVIDENCE_BUDGET` above the largest trial's evidence, then rescore run 2's saved evidence so the grounding axis measures the agent rather than the grader's window. No new agent trials are needed.
- [ ] Parse the grader's JSON out of a response that carries surrounding prose, so a preamble sentence does not produce an `unscored` trial.
- [ ] Record a rationale from a judge sample that agrees with the majority label, and record the vote margin beside every label.
- [ ] Replace or drop the Chicago multiple-criteria and Antarctica questions, because neither separates the arms at 10 trials per cell under either prompt condition.
- [ ] Correct `report.py`'s per-cell divisor, which ignores the prompt-condition axis and overstates cell size by a factor of two.
- [ ] Decide the learner-facing claim from the results: retain and qualify "Vector RAG Hallucinates" only if the repaired baseline reproducibly produces unsupported or incorrect answers; otherwise rename the module around incomplete top-k evidence and retrieval limits.

**Validation, partially met.** Run 1 met the mechanical requirements. All 48 fresh-agent trials completed without a swallowed tool error, raw FAISS and Neo4j evidence is saved for every trial, deterministic source and graph reference facts are recorded, and every answer carries separate factuality and grounding labels. Run 1 did not meet the requirement that the comparison be fair between arms, so its labels cannot decide the module's claim. Run 2 met that requirement at the prompt layer and at the tool layer, and it failed it at the grading layer. Its factuality labels are usable and decide the module title. Its grounding labels are not usable and leave hallucination unmeasured. What remains is a rescore of run 2's saved evidence with the judge budget removed, which costs judge calls only.

**Notes:** This phase makes cost-bearing Bedrock model and query-embedding calls and requires live Aura read access. Execute it deliberately and record the model ID, region, artifact checksum, graph counts, and run timestamp so the result can be reproduced. The phase is a gate: do not rewrite the notebook narrative, title, or diagrams until this evidence report is complete. Run 1 is retained as evidence of what a confounded comparison looks like, and its conclusions must not be cited. Run 2's grounding labels must not be cited either, for the reason given under Defect E.

### Phase 2: Repair notebook setup and retrieval execution

**Status: Pending**

**Outcome:** Module 2 loads the contracted FAISS artifact, uses the intended AWS and Neo4j configuration, and exposes retrieval failures instead of converting them into ordinary answers.

**Checklist:**

- [ ] Load `.env` before resolving and exporting the AWS region.
- [ ] Pin both agents to the workshop model and resolved region.
- [ ] Replace the hand-written Neo4j credential and database handling with the shared helpers.
- [ ] Resolve the index, documents, and manifest paths predictably and give an actionable error when the notebook starts in the wrong directory.
- [ ] Validate the complete FAISS contract before creating either agent.
- [ ] Normalize the query vector before searching, so the printed scores are cosine similarities and agree with `manifest.vector_normalization`. Ranking is unaffected either way, because an unnormalized query scales every inner product by the same constant, but the displayed number is only interpretable when both sides are normalized.
- [ ] Remove the 500-character slice and pass complete retrieved documents to the vector agent.
- [ ] Stop swallowing FAISS and Cypher exceptions.
- [ ] Display filenames, scores or distances, and the complete retrieved text before each vector-agent answer.
- [ ] Create fresh agent instances for every test and report per-test token usage.
- [ ] Restrict the Cypher tool to read operations and apply a query timeout.

**Validation:** Setup fails on a mismatched artifact or database; a direct vector smoke query returns three complete documents; tool errors remain visible; repeated tests do not share history or token counters.

**Notes:** Start this phase only after Phase 1.5 settles what the repaired comparison actually demonstrates. Implementation defects can be fixed independently, but learner-facing outcome claims must follow the evidence report.

### Phase 3: Make all four tests factually observable

**Status: Pending**

**Outcome:** Each test demonstrates a property visible in the raw retrieval or graph result, without relying on a particular LLM response.

**Checklist:**

- [ ] Replace the Paris aggregation with the five-hotel Orlando query and document the graph answer of 4.62.
- [ ] Add all five Orlando documents to lite selection, and have the readiness cell report the rated Orlando hotels it found instead of hard-failing.
- [ ] Assert deterministically, with no model call, that a `k=3` retrieval for the Orlando query returns three hits covering fewer than five of the five Orlando documents.
- [ ] Keep the pool-counting test, print the source-derived count of 175 beside the graph's count, and mark it optional in the learner path.
- [ ] Replace Cairo with the verified two-hotel Chicago spa-and-pool comparison, and update `REQUIRED_CITIES` and the `select_lite_files` docstring with it.
- [ ] Have the readiness cell find and print a city with multiple candidates, at least one match, and at least one exclusion, preferring Chicago, rather than gating on Chicago alone.
- [ ] Keep the Antarctica test, expose the nearest documents and scores, and mark the learner exercise optional.
- [ ] Describe Test 4 as the behaviour of a top-k baseline without a relevance threshold, not as a guarantee that the model fabricates an answer.
- [ ] Ensure all four tests still execute in the automated notebook run.

**Validation:** Orlando has five rated graph records; `k=3` cannot contain the complete Orlando set; the Chicago AND query filters at least one candidate; Antarctica returns FAISS neighbors while Neo4j returns no matching hotel; all four test cells execute from fresh agents.

### Phase 4: Align learner content and diagrams

**Status: Pending**

**Outcome:** The notebook, README, workshop page, and diagrams describe the repaired implementation and clearly distinguish Modules 2 and 3.

**Checklist:**

- [ ] Use "documents" for the whole FAISS records and reserve "chunks" for actual Neo4j `Chunk` nodes.
- [ ] Explain that Module 2 deliberately uses FAISS as a minimal standalone vector-RAG baseline.
- [ ] Explain that Module 3 introduces Neo4j vector, hybrid, and graph-enriched retrieval.
- [ ] Use one consistent set of four test names and visibly label Tests 2 and 4 optional.
- [ ] Explain why top-k retrieval alone cannot guarantee exact set aggregation, while acknowledging that filters, thresholds, and larger `k` can change the baseline.
- [ ] Replace deterministic claims about model answers with instructions for comparing retrieved evidence, Cypher results, and grounding.
- [ ] Author both diagrams as new `.drawio` sources around Orlando, the 4.62 graph result, the standalone FAISS branch, and the correct `guest_rating` property, then export the PNGs into both `workshop-content/images/` and `static/images/`.
- [ ] Add a notebook closing cell that summarizes the limitation and points to Module 3.

**Validation:** A cross-surface terminology and fact check finds no Paris or Cairo test remnants, no `h.rating`, no `City` node, no claim that both agents read Neo4j, and no guarantee that the model hallucinates.

### Phase 5: Integrate and run the workshop path

**Status: Pending**

**Outcome:** The repaired module passes static checks and an end-to-end Module 1 through Module 3 execution without hiding failures.

**Checklist:**

- [ ] Review every worker patch against its assigned file ownership and preserve unrelated edits.
- [ ] Validate notebook structure, source formatting, and Python compilation.
- [ ] Run focused unit tests for the artifact contract, the rebuild script, lite selection, the readiness cells, and the notebook runner.
- [ ] Execute Modules 1 through 3 in order against the configured workshop environment.
- [ ] Confirm the notebook's own deterministic retrieval assertion passes: three hits for the Orlando query, covering fewer than five of the five Orlando documents. That assertion is the module's lesson and needs no model call, so it is the gate rather than an eyeball check for `Query error:`.
- [ ] Confirm no vector tool call returns `Query error:`.
- [ ] Confirm expected Orlando and Chicago graph facts in the executed notebook.
- [ ] Review token usage after complete documents replace 500-character previews.
- [ ] Save or report the executed-notebook evidence and any stochastic answer differences.

**Validation:** All focused tests pass; Modules 1 through 3 execute successfully; no tool error is represented as a successful text result; retrieval evidence and graph answers match their documented contracts.

### Completion criteria

- The committed FAISS index is reproducible from the graph's own chunk vectors, 1024-dimensional, built at a recorded metric, and protected by a manifest that validates the contract fields, the corpus bytes, and the stored vector bytes.
- Module 2 remains architecturally distinct from Module 3.
- The notebook passes complete retrieved documents and shows them before the agent answer.
- Orlando makes the `k=3` aggregation limitation provable.
- Chicago makes the multiple-criteria filter observable.
- All four tests remain present, with Tests 2 and 4 optional for learners and mandatory for automated execution.
- Configuration, database selection, model selection, token metrics, and failure handling match the shared workshop contracts.
- Notebook, README, workshop page, diagrams, and executed results agree.
- Both diagrams have committed `.drawio` sources and identical exports in both image trees.
- The deterministic retrieval assertion, not a reading of the model's answer, is what proves the `k=3` limitation.
- Phase 1.5 records raw evidence, gives both arms the same system prompt and the same evidence treatment, grades against source-derived facts, scores factuality separately from grounding, and determines whether the module title is supported.

---

## Verified offline for this revision

Checked against the working tree and the committed corpus, with no live service, so
no worker needs to repeat them:

- All 300 `faqs_docs.json` entries are byte-identical to their `data/*.txt` file. The longest document is 7,442 characters, so nothing reaches the 8,000-character truncation in `_embed` and nothing splits at `CHUNK_SIZE` 12,000. Each document is therefore exactly one `Chunk` whose text is the whole document.
- The originally committed `faqs_vector.index` was an `IndexFlatL2` with `d` 384 and `ntotal` 300, its 450 KB matching 384 x 4 x 300 exactly. That is the defect M2-1 describes.
- The rebuilt `faqs_vector.index` in the working tree is an `IndexFlatIP` with `d` 1024 and `ntotal` 300. Its first vectors have norm exactly 1.0, so the export normalizes and the baseline now ranks by cosine, matching Neo4j's chunk index. `faqs_vector.manifest.json` records `faiss_metric` `inner_product` and `vector_normalization` `l2`, and its `corpus_sha256` matches the committed corpus bytes.
- The 16 tests in `setup/test_faiss_artifacts.py` and `setup/test_rebuild_faiss_index.py` pass. The manifest carries all nine fields, including `vectors_sha256` and `vector_source`. One of the 16 loads the committed artifact itself rather than a synthetic fixture, so a stale or corrupted shipped index fails the suite instead of only failing at notebook runtime.
- `BedrockEmbeddings` sends `EMBEDDING_MODEL_ID`, `EMBEDDING_PURPOSE`, and 1024 dimensions, the same three values the notebook's `_embed` sends.
- Orlando has five documents, rated 4.7, 4.5, 4.6, 4.7, and 4.6. The mean is 4.62.
- Chicago has two documents. Windward Mile Tower, rated 4.5, lists no pool and no spa, and its Pool section is a negation. Lakeview Horizon Suites, rated 4.4, has both.
- 175 documents name a pool in their amenity bullet list. 125 carry an explicit "Pool facilities are not available at this property" section. The two add to 300.
- `sample = paths[0]` in Module 1's cell 15 is one of the participant's real held-out documents, which is what makes the naive M1-1 fix unsafe.
- The two Module 2 PNGs have no `.drawio` source, and they are byte-identical in `workshop-content/images/` and `static/images/`.

---

## Not verified

- **The pre-build state of the graph.** Module 1 and Module 6 have both already run on the Aura instance. The dump's own contents were inferred from the 287 hotels carrying `hotel_id` versus the 5 that do not, and from the 295-document claim on Module 1's page. A clean restore is needed to check the participant path from the start.
- **Whether cell 19's empty-index message and cell 22's no-hotel message ever print.** Both indexes are already online and all five held-out documents are already loaded. Both code paths were shown to be reachable: four documents in the corpus produce no hotel at all, and the query correctly returns zero rows for them.
- **The four-minute build time.** Checking it means running the extraction and spending Bedrock tokens.
- ~~**Whether the extraction turned any of the 125 pool negations into a `Pool` amenity.**~~ Settled in Phase 1.5 run 1, by deterministic measurement that the run's retraction does not affect. Exactly one did. `hotel-austin-001.txt` carries the negation and the graph gave it a `Pool` amenity anyway. Windward Mile Tower is genuinely excluded on the current build. The graph counts 168 hotels with a pool against the source's 175, and the gap is 4 pool-listing documents that produced no `Hotel` node, plus 4 pool hotels each shared across two documents, minus the one false positive.
- **Whether the vector agent hallucinates once M2-1 is fixed.** Still open. Phase 1.5 run 1 reported zero fabrications across 24 trials, but its vector arm carried an added "base your answer on what the search returns" instruction that the graph arm did not, which is the exact intervention that turns fabrication into hedging. Run 2 measures this without the confound. Test 4's premise and the module title both stay undecided.
- **Whether `global.anthropic.claude-sonnet-4-6` is granted in the workshop account.** M2-3 is a real divergence from the pinned model either way, but no Bedrock call was made to check the grant.
- **The three arXiv links in the notebook's opening cell.** Outbound network was blocked, and a known-good control returned empty too, so nothing was proven. `2601.05214` is worth a manual check.
