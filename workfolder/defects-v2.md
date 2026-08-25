# Workshop Defects and Redesign Plan, Version 2

Date: 2026-08-21
Last reviewed: 2026-08-23
Branch: `restructure-modules-02-03`
Status: Historical. Frozen on 2026-08-23. Do not edit.

> **This document is history.** The open work now lives in
> `../fix-defects-v3.md`. The Module 2 and Module 3 specification below is
> implemented, so the notebooks are now the specification and the tests are the
> enforcement. Everything here is the design rationale and audit trail that
> produced them. Its phase numbers, defect IDs, test totals, and FAISS and
> Phase 1.5 references describe earlier states of the repository and no longer
> describe current work.

This document replaces the Module 2 direction in `defects.md`. The detailed audit
in that file remains useful as historical evidence. This version records the new
curriculum decision and turns it into an implementation plan.

## Scope and current state

The deterministic graph release tracked in `clean-graph.md` is complete. Its
published artifact is `static/neo4j-hotel-graph.dump`, which is 6,542,982 bytes
and has SHA-256
`a6eeecc3305acbbffe46e0ef7531db34c5a62d62db200c5574c3946102e29f02`.
That completion does not complete this curriculum redesign.

This plan remains open because the implemented Module 2 evidence contract still
needs live semantic acceptance, the optional Module 1 demo has a cleanup defect,
working-directory assumptions still need a final supported-path audit, and the
redesigned path needs a final end-to-end run. The Phase 1.5 evaluator, retention
policy, learner prose, and Module 2 diagrams are complete for offline use.

The current offline baseline passes 220 tests. The repository checker, notebook
code-cell compilation, shell syntax checks, and whitespace validation also pass.
These gates establish implementation health. They do not prove the locked
retrieval examples, evidence fields, provenance displays, or curriculum claims.

Three compact historical decision records under `evidence/phase15/` are now
trackable. Raw trial evidence, generated reports, logs, executed notebooks, and
the archived notebook remain excluded and have no recorded durable external
URI. They are local diagnostics, not release evidence, and are absent from a
fresh clone.

## Brief summary

### What has already been fixed

- Module 1's core graph-build descriptions have been corrected. The notebook and
  workshop page now describe the actual schema, embedding configuration, build
  checks, held-out documents, and later-module handoffs accurately. The optional
  unpinned demo cleanup remains open work.
- Deterministic graph construction now parses authored amenity bullets directly,
  preserves exact amenity identity, rejects incomplete Hotel extraction, and
  prevents same-named Hotels from merging across sources.
- The broken FAISS artifact has been rebuilt. It now contains 300 normalized
  vectors with 1,024 dimensions in an inner-product index.
- A compatibility manifest now records and validates the embedding model,
  embedding purpose, dimensions, document count, corpus checksum, metric,
  normalization, vector source, and vector checksum.
- A reproducible graph-to-FAISS export script and focused artifact tests have
  been added. Sixteen focused tests passed when this work was recorded.
- Phase 1.5 executed the repaired retrieval paths repeatedly and saved the raw
  evidence. Run 2 established that the old Module 2 title is unsupported by the
  factuality results.
- The empirical result is clear enough for the curriculum decision: the old
  exercises mostly demonstrate missing evidence, variable agent behavior, and
  graph extraction quality. They do not provide a stable demonstration that
  vector RAG hallucinates.
- Phase 2 completed the active path migration. Module 2 now lives under
  `02-connected-context`, Module 3 now lives under `03-grounded-booking-agent`,
  and the old Module 2 notebook has a local archival copy under
  `evidence/phase15/archive/`. Phase 6 classifies that copy as a local diagnostic,
  not release evidence.
- A post-migration semantic audit corrected Module 3.1 and Module 2.1 ownership
  throughout Modules 4 and 5, shared helpers, setup messages, and deployment
  documentation. Active learner surfaces contain no retired path or filename.
- Phase 3 now implements the evidence-first Module 2 notebook, exact source and
  Chicago readiness contracts, the deterministic lite-source selector, focused
  semantic contract tests, governed optional Text2Cypher, and the explicit
  Module 3 handoff. Live Neo4j and Bedrock execution remains a Phase 8 gate.
- Phase 5 now aligns Module 1 through Module 4 learner prose with the
  connected-context story. The active Module 2 decision tree has one editable
  Excalidraw source, synchronized exports, the structured-filter example, and an
  explicit semantic-entry and graph-expansion sequence. The unsupported
  performance comparison image has left both active image trees.
- Phase 6 retains FAISS as facilitator-only evaluation infrastructure outside
  the learner path, establishes the compact-versus-local retention boundary,
  and repairs the active evaluator contract. Historical grounding labels remain
  invalid and cannot enter a published report.

### Summary of the design changes

- Retire the title **Vector RAG Hallucinates**.
- Replace the two-agent answer contest with an evidence-first retrieval lesson.
- Rename Module 2 to **From Similarity Search to Connected Context**.
- Teach semantic search as the entry point and graph traversal as the way to add
  focused, structured, connected facts.
- Move the existing retrieval-pattern comparison from Module 3.1 into Module 2.
- Make vector retrieval and Vector-Cypher retrieval the main comparison.
- Keep hybrid retrieval and Text2Cypher as supporting patterns. They should show
  exact matching and structured filtering without making counting the headline.
- Simplify Module 3 so it focuses on building the grounded booking agent and its
  protected reservation command.
- Compare raw retrieval evidence, named fields, provenance, and context size.
  Treat generated answers as a secondary observation.
- Remove the old Paris, pool-count, Cairo, and Antarctica answer contest from the
  core learner path.

## Why the framing changes

The original module begins with a conclusion and asks four stochastic agent runs
to prove it. The repaired baseline did not produce that result consistently.
Phase 1.5 found that missing evidence was the vector arm's dominant problem. It
also found examples where both arms succeeded and examples where graph extraction
reduced the quality of the graph answer.

The stronger lesson is about complementary retrieval capabilities:

- Semantic search finds relevant source material when the question paraphrases
  the document.
- Exact-term search preserves names, identifiers, and postal codes that embeddings
  can rank poorly.
- Graph traversal expands a semantic match into connected rooms, amenities,
  policies, services, ratings, and provenance.
- Structured Cypher applies explicit filters when a question needs the database
  to select records by known fields and relationships.

This framing does not claim that graph enrichment always returns better context.
The graph can omit or distort facts when extraction or entity resolution is wrong.
The lesson is that semantic retrieval and graph structure contribute different
signals. A useful retrieval design combines those signals according to the
question.

## Proposed Module 2

### Title

**Module 2: From Similarity Search to Connected Context**

Suggested subtitle:

> Use semantic search to find the right source, then traverse the graph to return
> compact, connected facts with provenance.

### Learning objective

By the end of Module 2, a participant should be able to explain what each
retrieval signal contributes and select a retrieval pattern from the evidence a
question requires.

The participant should be able to distinguish:

- semantic relevance from exact matching;
- a relevant source document from a complete answer context;
- unstructured source text from connected, named graph fields;
- retrieved evidence from an LLM's final wording;
- facts present in the source from facts successfully extracted into the graph.

### Proposed notebook flow

#### 1. Verify the retrieval contract

Show the graph size, vector index, full-text index, embedding dimensions, metric,
and required fixtures before running a retriever. Fail with an actionable message
when the graph or indexes are missing.

#### 2. Start with semantic retrieval

Use a paraphrased hotel-policy question. Display the ranked `Chunk` results,
scores, filenames, and complete evidence. Explain why semantic similarity finds
the relevant wording even when the query and source use different terms.

#### 3. Show the exact-term gap

Use the existing `60611` example. Compare vector retrieval with hybrid retrieval.
The lesson is that semantic similarity and exact matching solve different parts
of the question.

#### 4. Add connected graph context

Use semantic retrieval to find the source for a hotel, then use Vector-Cypher to
return the connected hotel name, stable identifier, guest rating, amenities, and
source filename as named fields.

The main comparison should answer these questions:

- Did both methods identify the same hotel?
- Which requested facts appear in each result?
- How much unrelated text does each result contain?
- Can the learner trace every returned fact to a source or relationship?
- Does graph enrichment return a compact context that is easier for an agent to
  use?

#### 5. Show structured filtering without centering counting

Use the Chicago spa-and-pool example as a mechanism demonstration. The graph has
two Chicago candidates and one qualifying hotel in the current full build. Show
that Cypher applies both relationship conditions and excludes the other candidate.

Do not claim that vector retrieval must fail. Phase 1.5 showed that both Chicago
answers can succeed when the relevant documents fit inside the retrieval window.
The observable difference is how each result was selected.

#### 6. Summarize the retrieval spectrum

Use a concise decision table:

| Question need | Starting pattern | Contribution |
| --- | --- | --- |
| Paraphrased source lookup | Vector retrieval | Semantic relevance |
| Name, code, or identifier | Hybrid retrieval | Semantic and exact-term relevance |
| Semantic match plus connected facts | Vector-Cypher retrieval | Semantic entry and graph expansion |
| Flexible structured filtering | Text2Cypher retrieval | Database selection over named fields and relationships |

#### 7. Hand off to Module 3

Close by selecting the fixed Hybrid-Cypher retrieval function used by the booking
agent. Module 3 should apply that function rather than compare all retrieval
patterns again.

### What Module 2 should stop claiming

- Vector RAG reliably hallucinates on the workshop questions.
- Returning nearest neighbors causes the model to fabricate an answer.
- Graph retrieval always produces the correct answer.
- Graph retrieval is cheaper than vector retrieval.
- Both old agents read Neo4j.
- A one-hop `Hotel` to `Amenity` relationship is multi-hop reasoning.
- The model will respond in one predetermined way.

### Evidence to display

Every comparison should expose the deterministic retrieval result before any
optional answer generation:

- query text;
- retriever name and configuration;
- result rank and score;
- source filename;
- complete retrieved text when the pattern returns text;
- named graph fields when the pattern returns structured context;
- relationships traversed;
- result count;
- approximate context size;
- missing requested fields;
- provenance for each structured result.

The notebook can optionally ask a model to answer from each context. The lesson
must still work when the wording changes between runs.

## Locked Module 2 learning contract

> **Implemented.** Every locked value below now lives in
> `notebooks/workshop/retrieval_setup.py` and is asserted by
> `setup/test_module2_fixtures.py` and
> `setup/test_module2_notebook_contract.py`. Read the code, not this section.

This section is the Phase 1 specification. Later phases may improve wording and
layout, but they should preserve these questions, expected results, and module
boundaries unless new test evidence requires a change.

### Title and learner promise

**Title:** Module 2: From Similarity Search to Connected Context

**Learner promise:** Use semantic search to find the right source, then traverse
the graph to return compact, connected facts with provenance.

The lesson compares retrieved evidence. An LLM answer may be shown as an optional
extension, but it is outside the completion gate.

### Core examples and expected results

#### Example A: semantic paraphrase

**Question:** When does standard arrival processing begin at AnyCompany Cairo
Nile View?

Use `VectorRetriever` with the pinned Amazon Nova embedding contract. The query
paraphrases check-in instead of copying the source heading or the phrase
`Standard check-in time`.

The deterministic acceptance result is:

- the top three results include the chunk from `hotel-cairo-001.txt`;
- that chunk contains the supported time `3:00 PM`;
- the result displays rank, vector score, complete chunk text, source filename,
  and approximate character count;
- the lesson makes no claim about the wording of an LLM answer.

#### Example B: exact-term retrieval

**Question:** What is the cancellation policy for the hotel at 60611?

Compare the same question with `VectorRetriever` and `HybridRetriever`. Supply
`60611` as the full-text term and the complete question as the vector signal.
Keep the current linear hybrid configuration with `alpha=0.2`. Phase 3 preserves
and tests that contract offline; Phase 8 owns live retrieval revalidation.

The deterministic acceptance result is:

- hybrid retrieval returns `hotel-chicago-001.txt` in the top five;
- the returned chunk identifies Windward Mile Tower and contains `60611`;
- the evidence contains the supported cancellation policy of at least 24 hours
  before arrival;
- both result lists display the same top-k limit, ranks, scores, filenames,
  exact-term hits, complete text, and approximate context size;
- the notebook reports the live vector rank instead of treating historical rank
  12 as a permanent guarantee.

#### Example C: semantic entry plus graph enrichment

**Question:** What amenities and guest rating does AnyCompany Cairo Nile View
have?

Run the question first through `VectorRetriever`, then through
`VectorCypherRetriever`. This is the primary Module 2 comparison. Vector retrieval
finds the relevant source. Vector-Cypher uses that semantic entry point and a
reviewed traversal to return focused fields.

The deterministic acceptance result for the enriched record is:

| Field | Expected value |
| --- | --- |
| `hotel_name` | `AnyCompany Cairo Nile View` |
| `hotel_id` | `81393d51-1df3-4f53-b58e-e4cda9736fd7` |
| `guest_rating` | `4.5` |
| `source_filename` | `hotel-cairo-001.txt` |
| `amenities` | Values containing pool, spa, fitness, WiFi, and restaurant terms |

The record must also include the source chunk, semantic score, approximate
context size, missing requested fields, and the relationship types used to add
the structured fields. The notebook should compare field coverage and context
size, then state that extraction quality limits the graph result.

#### Example D: structured AND filtering

**Question:** Which hotels in Chicago offer both a spa and a swimming pool?

Use reviewed, fixed Cypher for the required demonstration. Match Chicago hotels,
require both `OFFERS_AMENITY` relationships on the same hotel, and return the
candidate and qualifying records with their source filenames. A supporting
Text2Cypher example may ask the same question, but its generated query is outside
the deterministic completion gate.

The deterministic acceptance result is:

- the candidate set contains Windward Mile Tower from `hotel-chicago-001.txt`
  and Lakeview Horizon Suites from `hotel-chicago-002.txt`;
- Lakeview Horizon Suites is the only qualifying result;
- the result shows that Windward Mile Tower was excluded because its connected
  amenities do not satisfy both predicates;
- the database returns selected records rather than a pool count;
- no claim says that vector retrieval must fail on this question.

### Evidence display contract

Every retrieval block must display the question, retriever name, relevant fixed
configuration, top-k limit when applicable, result rank, score when applicable,
source filename, approximate context size, and requested fields that are absent.

Pattern-specific evidence is:

| Pattern | Required display |
| --- | --- |
| Vector | Complete chunk text and vector score |
| Hybrid | Complete chunk text, combined score, and exact query terms found in the evidence |
| Vector-Cypher | Source chunk, semantic score, named hotel fields, amenities, traversed relationship types, and field provenance |
| Fixed Cypher | Reviewed query purpose, parameters, candidate records, qualifying records, and source filename for each hotel |
| Supporting Text2Cypher | Generated query, read-only validation state, returned records, and any execution error |

For text results, provenance is
`(:Chunk)-[:FROM_DOCUMENT]->(:Document {source_filename})`. For graph-enriched
hotel fields, provenance adds
`(:Hotel)-[:FROM_CHUNK]->(:Chunk)` and the named relationship used for each
connected fact. A stable `hotel_id` identifies the entity but does not replace
source provenance.

### Pattern priority

The two core patterns are:

1. `VectorRetriever` for semantic source discovery.
2. `VectorCypherRetriever` for semantic entry plus connected, named context.

The supporting patterns are:

- `HybridRetriever` for exact terms such as `60611`;
- reviewed fixed Cypher for deterministic structured filtering;
- `Text2CypherRetriever` as an optional natural-language interface to a pinned,
  read-only schema.

`HybridCypherRetriever` is the handoff pattern. Module 2 identifies it as the
combination selected for the application, while Module 3 uses the fixed shared
function instead of reopening the retriever survey.

### Required fixtures

All examples require an online `hotel_chunk_embeddings` vector index over
`Chunk.embedding`, an online `hotel_chunk_fulltext` index over `Chunk.text`,
1024-dimensional query and stored embeddings, cosine similarity, and exactly one
source chunk for each required source document in the current workshop build.

The example-specific fixture checks are:

| Source | Required graph facts |
| --- | --- |
| `hotel-cairo-001.txt` | One Document, one embedded Chunk, one connected Hotel with the locked ID, name, address, rating 4.5, and amenities containing pool, spa, fitness, WiFi, and restaurant terms |
| `hotel-chicago-001.txt` | One Document, one embedded Chunk containing Windward Mile Tower and `60611`, one connected Hotel at the `60611` address, and no extracted combination of both spa and swimming-pool amenities |
| `hotel-chicago-002.txt` | One Document, one embedded Chunk for Lakeview Horizon Suites, one connected Chicago Hotel, and extracted spa and swimming-pool amenities |

Each hotel must resolve through one source path from Hotel to Chunk to Document.
Phase 3 should turn these checks into executable readiness assertions. In
particular, `hotel-chicago-002.txt` must join the lite-build required-source list
before the Chicago example becomes a learner-facing gate.

### Boundary with Module 3

Module 2 ends by selecting `search_hotel_knowledge` from
`workshop.hybrid_retrieval`. Module 3 begins with that function and the same Cairo
hero question. Module 3 teaches evidence-grounded answers, abstention, and the
protected reservation command. It does not repeat the retriever comparison.

## Proposed Module 3

### Title

**Module 3: Build the Grounded Booking Agent**

### Scope

Module 3 should begin with the selected Hybrid-Cypher retrieval function and use
it in the booking agent. It should retain the existing lessons on:

- returning named evidence fields;
- declining questions that the graph cannot answer;
- keeping the reservation write separate from generated Cypher;
- enforcing the guest limit inside the write transaction;
- using `request_id` to make retries idempotent.

The current Module 3.1 retrieval comparison should move to Module 2. The current
Module 3.2 grounded booking notebook should become the only Module 3 notebook and
be renumbered as Module 3.1.

## Defect status

### Resolved redesign defects

- **V2-1:** The active Module 2 title, route, folder, and notebook filename have
  been renamed. A repository gate rejects the retired names on active surfaces.
- **V2-2:** Retrieval-pattern comparison now has one active learner notebook in
  Module 2. The booking agent is the sole active notebook in Module 3.
- **V2-10:** Module ownership and numbering have been reviewed by meaning across
  Modules 3 through 5, shared helpers, fixtures, setup messages, and READMEs.
- **V2-11:** Graph preparation and every active path consumer now use the renamed
  Module 2 location.
- **V2-14:** Repository validation now checks retired learner-facing paths while
  allowing historical defect and Phase 1.5 records.
- **V2-8a:** Amenity extraction no longer interprets Chicago's negative pool prose
  as a positive amenity. The deterministic parser reads only the authoritative
  amenity bullets, so the Chicago qualification result no longer depends on LLM
  amenity extraction.
- **V2-3:** The replacement notebook now enforces the locked questions, evidence
  fields, provenance paths, result counts, expected values, and handoff without
  grading generated answer wording.
- **V2-6:** Module 2 now resolves its repository base deterministically and uses
  the shared embedding, model, region, database, schema, and retrieval contracts.
  Every workshop pattern uses the same Neo4j credentials to keep participant
  setup small. Optional Text2Cypher adds the application guard described in
  V2-7.
- **V2-7:** Optional Text2Cypher now uses the pinned shared schema, a planner
  check, the configured database, and a bounded query timeout. It plans with
  `EXPLAIN` and executes only queries Neo4j classifies as read-only. The workshop
  intentionally reuses its ordinary Neo4j credentials; production should add a
  read-only Neo4j user so the database independently rejects writes.
- **V2-8:** The lite selector now consumes `REQUIRED_SOURCE_FILES`, includes both
  Chicago sources, preserves exactly 30 documents, and fails when the required
  fixtures or sample size cannot be satisfied. Readiness reports two candidates,
  one qualifier, and the explicit Windward exclusion.
- **V2-4:** The active Module 2 decision tree now teaches structured filtering,
  semantic entry, reviewed graph expansion, named fields, and provenance. Both
  image trees have synchronized Excalidraw sources and PNG exports. The
  unsupported speed-and-accuracy comparison image is no longer active.
- **V2-5:** Learner surfaces no longer claim that Module 2 builds competing
  agents or that Module 3 first combines the retrieval indexes. One-hop examples
  use connected-traversal language, graph `Chunk` nodes are distinguished from
  whole documents, model wording is described as variable, and graph results
  are described as extracted facts rather than an independent source of truth.
- **V2-12:** FAISS remains a complete facilitator-only evaluation baseline with
  its manifest, loader, rebuild script, harness, and tests. It is outside the
  learner path. Three compact Phase 1.5 decision records are trackable. Raw
  evidence and the archived notebook remain local diagnostics without a durable
  external URI and are not release evidence.
- **V2-13:** The active evaluator rejects incomplete judge evidence, invalid
  response schemas and labels, unresolved vote ties, mismatched sample counts,
  and judge errors. It preserves every sample, selects rationales from samples
  that cast each winning label, and reports the complete evaluation-cell
  divisor. Historical grounding labels remain explicitly invalid until a
  repaired rescore exists.

### Outstanding defects

### Module 1

#### M1-1. The optional unpinned extraction demo leaves data behind

The optional demo still uses a real held-out document name incorrectly. Its
cleanup query cannot find the generated document in the current form. The safe
fix is to give the demo a distinct filename, pass that filename as metadata, and
delete only that distinct document during cleanup.

### Module 2 redesign

#### V2-9. Working-directory assumptions remain in setup and notebooks

Several paths rely on launching from one module directory. The rename increases
the chance of silent path breakage. Resolve repository and module assets from one
documented base path and test execution from the supported working directory.

### Repository hygiene and validation

#### V2-15. The redesigned semantic acceptance path has not passed

The clean-graph release executed Modules 1 through 3. The active Module 2
notebook now implements the locked redesign contract, and the offline suite
passes 220 tests. A live run has not yet validated the new retrieval behavior.
After Phase 7, rerun Modules 1 through 3 and validate the exact
retrieval fields, provenance, fixtures, diagrams, handoffs, and learner claims.

## Implementation plan

### Goal

Replace the unsupported hallucination lesson with a deterministic explanation of
how semantic search, exact-term search, and graph traversal combine to produce
focused answer context. Simplify Module 3 around the grounded booking agent and
preserve the working setup and deployment path. Keep this redesign status
separate from the completed deterministic graph release.

### Assumptions

- The approved learner-facing title is **From Similarity Search to Connected
  Context**.
- Module 2 will own retrieval-pattern comparison and graph preparation.
- Module 3 will own the grounded booking agent and reservation command.
- The primary comparison is vector retrieval versus Vector-Cypher retrieval.
- Hybrid retrieval and Text2Cypher remain supporting patterns.
- The old four-question agent contest will leave the core learner path.
- Phase 1.5 remains historical evidence. The optional benchmark and FAISS
  baseline are actively maintained facilitator infrastructure outside the
  learner path.
- `static/neo4j-hotel-graph.dump` is the committed published graph artifact.
- Only the three compact records named by the Phase 1.5 retention policy are
  trackable under `evidence/`. Other evidence files remain local-only unless a
  future publication records an immutable external URI and checksum.
- The 220-test offline result is the current implementation baseline. Final
  redesign acceptance requires live semantic execution and end-to-end checks.
- Existing unrelated working-tree changes will be preserved.

### Risks

- Renaming the Module 2 directory affects imports, setup utilities, tests, links,
  notebook execution order, and held-out document loading.
- Moving a notebook between modules can leave stale titles and downstream prose
  even when all file paths resolve.
- Removing the FAISS baseline too early can break evaluation tools or discard a
  useful reproducibility artifact.
- Graph-enriched context can look authoritative when extraction omitted or merged
  source facts. The notebook must show provenance and state this limit.
- A broad Text2Cypher example can generate unsafe or invalid queries. Keep it
  read-only, schema-pinned, time-bounded, and visibly separate from writes.
- LLM-extracted Hotel properties can vary between builds. Amenity identity and
  Chicago qualification are deterministic, so readiness should enforce those
  exact source-backed facts while reporting other live extraction variation.
- A test suite can pass while learner prose, displayed fields, and example
  ownership remain wrong. Semantic gates must inspect the locked contract rather
  than relying only on notebook execution.
- The optional 240-trial benchmark remains cost-bearing. Its evidence gate now
  rejects incomplete judge evidence, invalid samples, ties, and arithmetic
  mismatches before publication.
- Local-only evidence can disappear or become unavailable to collaborators.
  Preserve compact proof and publish a durable location for large raw evidence.
- Moving content without updating Modules 4 and 5 can break the production story.

### Phase 1: Lock the new learning contract

**Status: Complete**

**Outcome:** A short specification defines the exact questions, evidence fields,
expected fixtures, and boundary between Modules 2 and 3.

**Checklist:**

- [x] Confirm the Module 2 title and one-sentence learner promise.
- [x] Select the semantic paraphrase example.
- [x] Retain the deterministic `60611` exact-term example.
- [x] Select one graph-enrichment example that returns a hotel, stable ID, rating,
  amenities, and source filename.
- [x] Retain Chicago as a structured-filter mechanism example.
- [x] Define the fields and provenance each retriever must display.
- [x] Define which patterns are core and which are supporting.
- [x] Record the graph fixtures required by every example.
- [x] Confirm that Module 3 begins with the selected Hybrid-Cypher function.

**Validation:** Complete. Every example has a deterministic expected retrieval
result that can be checked without grading an LLM answer. The expected facts were
cross-checked against the committed source corpus, fixture manifest, retrieval
readiness checks, and existing Phase 1.5 Chicago evidence.

**Notes:** Pool counting, Orlando aggregation, and Antarctica leave the core path.
They may remain in historical Phase 1.5 evidence. The contract also identifies
`hotel-chicago-002.txt` as a required lite-build source fixture. Phase 3 added it
to the shared required-source contract, made the lite selector guarantee both
Chicago documents while preserving 30 sources, and added readiness tests for the
expected source paths and authored amenities.

### Phase 2: Restructure the module files

**Status: Complete**

**Outcome:** Active module paths, notebook numbering, and executable path
consumers match the new curriculum. The move preserves authored history and
leaves generated local files behind.

**Locked path map:**

| Current path | Destination | Treatment |
| --- | --- | --- |
| `notebooks/03-retrieval-patterns/3.1_retrieval_patterns.ipynb` | `notebooks/02-connected-context/2.1_connected_context.ipynb` | Becomes the sole Module 2 learner notebook |
| `notebooks/03-retrieval-patterns/3.2_grounded_booking_agent.ipynb` | `notebooks/03-grounded-booking-agent/3.1_grounded_booking_agent.ipynb` | Becomes the sole Module 3 learner notebook |
| `notebooks/03-retrieval-patterns/reservation_command.py` | `notebooks/03-grounded-booking-agent/reservation_command.py` | Moves with the booking agent |
| `notebooks/02-vector-rag-hallucinates/2.1_vector_rag_hallucinates.ipynb` | `evidence/phase15/archive/2.1_vector_rag_hallucinates.ipynb` | Local-only historical diagnostic, excluded from release evidence |
| `workshop-content/content/02-vector-rag-hallucinates/` | `workshop-content/content/02-connected-context/` | Becomes the Module 2 route |
| `workshop-content/content/03-retrieval-patterns/` | `workshop-content/content/03-grounded-booking-agent/` | Becomes the Module 3 route |

The tracked Module 2 support assets move to `notebooks/02-connected-context/`:
the README, graph builder, graph configuration, preparation script, source
archive, and legacy FAISS files. Phase 6 retains the FAISS files as
facilitator-only evaluation infrastructure. The Module 3 README moves to
`notebooks/03-grounded-booking-agent/` and
receives only the minimum identity and path corrections in this phase.

**Review:** Ready to execute. The phase is large but remains one atomic path
migration. Splitting the moves from their active consumers would create broken
intermediate paths.

**Checklist:**

- [x] Record the pre-move tracked-file inventory and current working-tree changes
  so unrelated edits remain untouched.
- [x] Move tracked authored files individually. Leave ignored `data/`,
  `__pycache__/`, notebook outputs, and virtual environments out of the move.
- [x] Move the retrieval-pattern notebook to
  `notebooks/02-connected-context/2.1_connected_context.ipynb`.
- [x] Move Module 2 graph preparation, corpus, README, and legacy FAISS assets to
  `notebooks/02-connected-context/` without changing their behavior.
- [x] Archive the old agent-comparison notebook at
  `evidence/phase15/archive/2.1_vector_rag_hallucinates.ipynb` and remove it from
  the notebook runner.
- [x] Move the booking notebook to
  `notebooks/03-grounded-booking-agent/3.1_grounded_booking_agent.ipynb`.
- [x] Move the Module 3 README and `reservation_command.py` into
  `notebooks/03-grounded-booking-agent/`.
- [x] Rename both workshop content routes according to the locked path map.
- [x] Apply minimum identity edits to the moved notebooks and READMEs: titles,
  module numbers, preparation hints, relative imports, file inventories, and
  handoff references. Defer lesson rewriting to Phases 3 through 5.
- [x] Update the notebook runner so it registers exactly one Module 2 notebook
  and one Module 3 notebook in the correct order.
- [x] Update active Python path consumers in Module 1, held-out loading, dump
  repair, the Phase 1.5 harness, and the FAISS tests.
- [x] Update Module 5's executable source path for `reservation_command.py` in
  the deployment notebook. Defer its explanatory lineage rewrite to Phase 4.
- [x] Update active route and filename references in root navigation, workshop
  navigation, summary links, and module next links. Defer full prose rewriting
  to Phase 5.
- [x] Add the retired Module 2 and Module 3 routes and notebook filenames to the
  active-surface stale-path gate while allowing historical files under
  the final Phase 6 evidence location and the defect records.
- [x] Update path-sensitive tests and keep the module-folder-to-page parity gate
  passing.
- [x] Review the final rename set for accidental generated files, unrelated
  notebook output churn, or deletion of legacy FAISS assets.

**Validation:**

- The repository contains one active learner notebook for Module 2 and one for
  Module 3, and every notebook-runner path resolves.
- Every numbered notebook folder has a matching workshop content folder.
- Active code, tests, navigation, and learner files contain no retired routes or
  notebook filenames. Historical Phase 1.5 and defect records are excluded.
- The repository structure check, notebook-runner tests, and path-sensitive
  FAISS tests pass without Neo4j, Bedrock, or deployment access.
- Both moved notebooks remain valid JSON and every Python code cell compiles.
- The change summary shows tracked renames and focused identity edits. It shows
  no ignored data, cache files, generated notebook output, or unrelated changes.

**Validation result:** Complete for the Phase 2 structural scope. All 71 focused
repository, runner, FAISS, and rebuild tests pass. Notebook parsing, Python
compilation, content references, content weights, module-to-page parity, and
named paths pass in the repository checker. Active surfaces contain no retired
routes or notebook filenames. Unchanged support assets and the archived notebook
are byte-identical to their original Git blobs.

At Phase 2 completion, the repository checker still reported two pre-existing
content issues outside the structural scope: fixed graph counts in Module 1 and
a mismatched `03-agentcore-architecture.png` export. The post-migration quality
review removed the fixed counts and synchronized the current Module 4 export.
The full repository checker now passes.

**Notes:** This phase was an atomic path migration, so every active executable
consumer moved with its source. It did not change retrieval behavior, graph
fixtures, learner examples, diagrams, or FAISS ownership. Phases 3 through 6
completed those changes. The workshop remains mid-redesign and is not ready for
release until the cleanup and integration phases pass.
The existing ignored corpus extract now lives under the new Module 2 path. Old
bytecode caches were preserved under hidden retired-directory names and remain
outside Git.

### Phase 3: Build the evidence-first Module 2 notebook

**Status: Complete**

**Outcome:** Module 2 demonstrates semantic, exact-term, and graph-enriched
retrieval through visible evidence.

**Checklist:**

- [x] Remove generated-answer grading and cumulative agent metrics from the
  active Module 2 notebook.
- [x] Verify the vector and full-text indexes before constructing retrievers.
- [x] Rewrite the opening around the locked learner promise: semantic entry,
  exact-term support, graph expansion, and structured filtering.
- [x] Make lite selection consume `REQUIRED_SOURCE_FILES`, add
  `hotel-chicago-002.txt`, guarantee every required source, and keep the sample
  size at 30.
- [x] Add exact readiness assertions for the Cairo source, both Chicago sources,
  their embedded Chunks, one Hotel per source path, and their authored amenities.
- [x] Report two Chicago candidates, one qualifier, and Windward Mile Tower as
  the explicit exclusion.
- [x] Add focused tests for required-source selection, stable sample size,
  Chicago readiness, candidate records, qualifying records, and exclusion data.
- [x] Resolve imports and assets from a stable base path instead of the current
  working directory.
- [x] Use the shared embedding, model, AWS region, database, schema, retrieval,
  and authentication contracts in every pattern. Use the planner guard for
  optional Text2Cypher and recommend a read-only Neo4j user for production.
- [x] Use the locked Cairo arrival-processing question for semantic retrieval.
- [x] Display vector rank, score, source filename, complete Chunk text, top-k,
  approximate context size, and missing requested fields.
- [x] Display hybrid results beside the `60611` vector results with the same
  top-k, exact-term hits, source filenames, scores, and complete text.
- [x] Use the locked Cairo amenities-and-rating question for Vector-Cypher.
- [x] Return `hotel_name`, `hotel_id`, `guest_rating`, `source_filename`,
  amenities, source Chunk, semantic score, relationship types, and field
  provenance as named fields.
- [x] Compare requested-field coverage and approximate context size between the
  vector and Vector-Cypher results.
- [x] Add the reviewed fixed Chicago AND-filter query as the deterministic
  structured demonstration. Do not make generated Text2Cypher the acceptance
  path.
- [x] Keep Text2Cypher optional, schema-pinned, planner-validated,
  database-scoped, and time-bounded. Display its generated query and errors.
  Reuse the workshop credential, and document a read-only user for production.
- [x] Add deterministic assertions for every locked expected result without
  asserting one model-generated answer wording.
- [x] Add the closing decision table and explicitly select
  `search_hotel_knowledge` for Module 3.

**Validation:** The notebook fails when a required source, field, provenance
path, Chicago candidate, qualifier, exclusion, or index contract is absent. Every
section proves its lesson from retrieved evidence. Model wording can vary without
changing the learning outcome.

**Validation result:** Complete for offline implementation. At Phase 3
completion, the full offline suite passed 187 tests, including focused fixture
and notebook-contract gates. The current post-Phase 6 suite passes 220 tests.
The repository checker, notebook JSON validation, code-cell compilation, Cypher
review, prose-style scan, and whitespace checks pass. Live Neo4j and Bedrock
execution was not run because it requires external credentials and may incur
cost. Phase 8 retains the live semantic acceptance gate.

### Phase 4: Simplify Module 3 and repair downstream references

**Status: Complete**

**Outcome:** Module 3 contains the grounded booking agent only, and later modules
refer to the new numbering accurately.

**Checklist:**

- [x] Retitle Module 3 around the grounded booking agent.
- [x] Update the notebook introduction to treat Module 2 as the retrieval-pattern
  comparison.
- [x] Keep the fixed Hybrid-Cypher implementation and retrieval contract.
- [x] Keep abstention, guest-limit enforcement, and idempotent retry lessons.
- [x] Update Module 4 references to the retrieval comparison and booking agent.
- [x] Update Module 5 references to the booking agent and reservation command.
- [x] Update shared helper docstrings and fixture messages by meaning.
- [x] Update every `Module 3.1` and `Module 3.2` reference after manual review.

**Validation:** Complete. Modules 3 through 5 describe one consistent lineage
from the retrieval comparison in Module 2.1, to the local booking agent in
Module 3.1, to managed tools in Module 4, to the deployed runtime in Module 5.
The audit found and repaired two stale `Module 3.2` comments in the deployed
runtime, including an obsolete model configuration explanation. No active
tracked `Module 3.2` reference remains. Fifty-nine focused tests and the
repository checker pass for the audited scope.

### Phase 5: Rewrite learner content and diagrams

**Status: Complete**

**Outcome:** Notebook prose, READMEs, workshop pages, navigation, and diagrams all
teach the connected-context story.

**Checklist:**

- [x] Rewrite the Module 2 README and workshop page.
- [x] Rewrite the Module 3 README and workshop page.
- [x] Update the root README, workshop index, summary page, wrap-up page, and
  Module 1 next link.
- [x] Remove or live-render the fixed graph counts still present in the Module 1
  notebook and workshop page.
- [x] Remove the Module 1 claim that Module 2 creates two competing agents and
  demonstrates a retrieval failure.
- [x] Correct the Module 1 handoff so Module 2, not Module 3, introduces the
  combined retrieval patterns.
- [x] Replace one-hop uses of the term multi-hop with accurate traversal language.
- [x] Update the editable Module 2 decision tree so structured filtering, not
  counting, is the Text2Cypher example.
- [x] Replace or archive `02-retrieval-patterns-comparison.png`, which contains
  unsupported speed and accuracy ratings and lacks an editable source.
- [x] Add a semantic-entry and graph-expansion diagram when that relationship is
  not already clear in the revised decision tree.
- [x] Synchronize the existing `03-agentcore-architecture.png` export between
  both image trees.
- [x] Add editable sources and synchronized exports for every active diagram
  in both image trees.
- [x] Use `Chunk` only for graph `Chunk` nodes and `document` for whole documents.
- [x] Remove deterministic claims about model answers.
- [x] Explain that graph results reflect the extracted graph rather than an
  independent source of truth.
- [x] Explain how Module 2 selects the retriever applied in Module 3.

**Validation:** Learner-facing surfaces contain no hallucination promise, false
schema element, unsupported performance rating, false count, stale agent contest,
incorrect one-hop terminology, or stale module number. Every active diagram has
matching editable source and synchronized exports.

**Validation result:** Complete. Eleven focused content and diagram contract
tests pass. The unsupported comparison image is absent from both active image
trees. The replacement Excalidraw source and 1600 by 900 PNG export are
byte-identical across both trees and passed visual review. The complete offline
suite passes 220 tests. The repository checker, notebook parsing and
compilation, prose scans, shell syntax, and whitespace validation pass.

### Phase 6: Resolve legacy FAISS and Phase 1.5 assets

**Status: Complete for offline implementation. The optional benchmark remains
unexecuted.**

**Outcome:** Every retained artifact has a documented purpose and active test
owner.

**Checklist:**

- [x] Inventory the current consumers of the FAISS index, manifest, documents,
  loader, rebuild script, tests, Phase 1.5 harness, and live-evidence runner.
- [x] Decide that the optional 240-trial benchmark remains supported.
- [x] Designate FAISS as a facilitator-only
  evaluation baseline. Keep it outside the learner path.
- [x] Record that the retirement branch was not selected and preserve the active
  harness and its supported consumers.
- [x] Keep the manifest and rebuild tests because the optional benchmark retains
  FAISS.
- [x] Decide which compact reports belong in Git and state that raw evidence
  requires an immutable external URI and checksum before publication.
- [x] State clearly which evidence is tracked, externally retained, or local-only.
- [x] Update relocated reports that still name `setup/release-evidence/` paths.
- [x] Mark the earlier Phase 1.5 reports as historical and their grounding labels
  as invalid until a repaired rescore exists.
- [x] Prevent judge evidence loss or mark affected
  grounding trials invalid.
- [x] Validate judge JSON against an allowed label schema and handle fenced,
  prefixed, malformed, and extra-field responses explicitly.
- [x] Treat unresolved vote ties as unscored instead of selecting the first sample.
- [x] Select a rationale that corresponds to each winning label and preserve all
  sample rationales.
- [x] Fix report arithmetic so trials per cell includes question, arm, and prompt
  condition dimensions.
- [x] Add focused tests for evidence budgeting, parser behavior, tie handling,
  rationale selection, report divisors, and evidence-gate rejection.
- [x] Confirm every retained FAISS and Phase 1.5 consumer still uses the paths
  established by the final retention policy.
- [x] Audit assets for orphaned consumers. No retained FAISS asset qualified for
  removal.
- [x] Gate the optional benchmark behind the repaired evaluator tests. Do not run
  the paid benchmark during this phase.
- [x] Require future benchmark reports to separate raw counts and rates
  from statistical claims and account for repeated observations by question and
  evaluation cell.

**Validation:** No orphaned artifact or test remains, no supported workflow
depends on a retired path, and another clone can locate every retained compact
artifact. If the benchmark remains active, synthetic evaluator tests pass before
any paid run and no invalid grounding label enters the report.

**Validation result:** Complete for offline implementation. Fifty focused
evaluator, retention, FAISS, rebuild, and release-workflow tests pass. The full
offline suite passes 220 tests. The repository checker, Python compilation,
retention boundary checks, and whitespace validation pass. No paid or live
benchmark ran. Historical raw evidence and the retired notebook remain
local-only because they have no durable external URI. They cannot support a
release or publication claim.

### Phase 7: Fix the remaining Module 1 cleanup defect

**Status: Pending**

**Outcome:** The optional unpinned demo always removes only its own temporary data.

**Checklist:**

- [ ] Give the demo a filename that cannot collide with a held-out document.
- [ ] Pass that filename through document metadata.
- [ ] Clear the distinct demo filename in the cleanup block.
- [ ] Make the notebook prose and code agree about whether temporary demo data is
  removed.
- [ ] Add a focused regression test that runs cleanup after participant data
  exists and proves the real held-out source remains unchanged.
- [ ] Re-run the demo after a completed build and verify that real hotel data
  remains unchanged.
- [ ] Restore the learner-facing cleanup promise after validation.

**Validation:** The demo creates and removes its own nodes and cannot delete a
participant-built hotel when rerun.

### Phase 8: Integrate and validate the workshop path

**Status: Pending**

**Outcome:** The redesigned workshop runs from graph build through grounded agent
without stale references or hidden retrieval failures.

**Checklist:**

- [x] Establish the current offline baseline: 220 tests pass, notebook code cells
  compile, repository integrity passes, shell syntax passes, and whitespace
  validation passes.
- [x] Add semantic contract gates for required Module 2 questions, evidence
  fields, provenance, Chicago selection, stale claims, and diagram ownership.
- [ ] Validate notebook JSON structure and compile every code cell after all
  redesign edits.
- [ ] Run focused graph preparation, retrieval, fixture, path, evaluator, cleanup,
  and content-contract tests.
- [ ] Execute Modules 1 through 3 in order against the configured environment.
- [ ] Smoke-check the Module 4 and Module 5 handoff references.
- [ ] Verify the semantic, hybrid, Vector-Cypher, and structured-filter evidence.
- [ ] Verify that every displayed structured fact includes provenance.
- [ ] Check all internal links, notebook paths, and workshop navigation.
- [ ] Search learner-facing files for the old title and retired test claims.
- [ ] Exclude `defects*.md` and the final Phase 6 historical evidence location
  from that search gate. Do not exclude active harness or learner files.
- [ ] Confirm both diagram trees contain matching exports and editable sources.
- [ ] Record live service versions, graph counts, model ID, region, and execution
  time with the final validation report.
- [ ] Update `clean-graph-final-state.md` so it names only artifacts that exist,
  records the actual commit and publication state, and states that clean-graph
  completion does not complete this redesign.
- [ ] Update current test totals in release summaries. Preserve clearly labeled
  historical totals when they describe an earlier phase result.
- [ ] Verify the published static dump size and SHA-256 independently from local
  candidate or evidence directories.

**Validation:** All focused tests pass, Modules 1 through 3 execute successfully,
later-module handoffs resolve, the deterministic evidence matches the locked
learner-facing claims, and release documents describe the same artifact,
evidence-retention, version-control, and completion state.

## Completion criteria

- Module 2 is titled **From Similarity Search to Connected Context**.
- Module 2 compares retrieval evidence rather than trying to induce hallucination.
- Semantic search, hybrid search, graph enrichment, and structured filtering each
  have one clear role.
- Vector-Cypher is the main demonstration of semantic entry plus connected graph
  context.
- Module 3 contains the grounded booking agent and protected write path without a
  duplicate retriever survey.
- Module 4 and Module 5 accurately identify the earlier source of each retrieval
  and write component.
- Every retained FAISS or Phase 1.5 asset has a documented purpose and passing
  validation.
- Every retained evidence artifact has a durable location and a stated tracking
  or external-retention policy.
- The optional Module 1 demo cleans up only its own data.
- All notebooks use shared environment, model, database, schema, and path
  contracts.
- Learner-facing content contains no unsupported hallucination guarantee.
- New diagrams show the real graph schema and have editable sources.
- Modules 1 through 3 run end to end with deterministic evidence for every core
  lesson.
- `clean-graph-final-state.md` reports the deterministic graph release as complete
  without reporting this redesign as complete.
- Release documentation names only artifacts that exist and reports the current
  commit, publication, and test state accurately.
- No Phase 1.5 grounding rate or comparative benchmark claim is published from
  an evaluator with unresolved evidence, parser, voting, rationale, or arithmetic
  defects.
