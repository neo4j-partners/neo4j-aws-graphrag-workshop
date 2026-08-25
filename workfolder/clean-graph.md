# Workshop plan for deterministic amenities

**Status: Complete. The rebuilt candidate, isolated restore, five-document
additive path, 24-cell agent smoke, Modules 1 through 3 notebook smoke, release
automation, and replacement static artifact in the working tree have passed
their release gates.**

For a concise final summary, see
[`clean-graph-final-state.md`](clean-graph-final-state.md).

## Current progress

**Snapshot: 2026-08-23**

- Offline implementation and documentation work is complete.
- The focused Phase 1 through Phase 3 suite passes 36 tests.
- The complete offline setup suite passes 153 tests with one intentional
  environment-dependent skip.
- The first real release canary exposed a missing APOC dependency in the
  disposable `neo4j:latest` image. The strict Hotel provenance gate rejected
  that canary, the graph was cleared, and no artifact was produced from it.
- The rebuild was restarted in a fresh disposable local Neo4j image with APOC.
  Its three-document canary passed with three distinct conforming Hotels.
- The APOC-enabled retry completed 192 documents successfully. During document
  193, the local OrbStack VM stopped servicing the Docker API and Neo4j Bolt
  connection. Documents 194 and 195 then failed with connection refusals, so
  the build was stopped before more unusable Bedrock calls were made.
- Neo4j logged no internal database failure, Docker reported no container OOM,
  and no candidate dump was emitted. OrbStack required a graceful service
  restart before Docker became responsive again.
- The failed disposable container and volume were removed after their state,
  logs, image ID, start time, commit, and critical-file hashes were captured.
- The next retry bounds the Neo4j container to 4 GiB, with a 1.5 GiB maximum
  heap and 1 GiB page cache, to keep the local container VM from exhausting
  host memory during the long build.
- The memory-bounded retry completed all 295 Bedrock extractions without an
  unresolved document failure. Final readiness passed with 295 Documents, 295
  Hotels, 295 Chunks, 65 Amenities, and 1,606 amenity assertions.
- A stopped read-only guard container preserved the completed Neo4j volume
  after the wrapper failure, allowing a clean recovery shutdown and export
  without repeating a Bedrock extraction.
- Future facilitator builds default to three concurrent Bedrock extractions;
  `GRAPH_BUILD_CONCURRENCY` accepts a bounded value from 1 through 8. Module 1
  remains sequential by default.
- Candidate construction used local Neo4j only and did not connect to Aura.
  It did not replace `static/neo4j-hotel-graph.dump` until after the candidate
  passed the restore, additive, live-evidence, and publication-review gates.
  The recovered 6.2 MiB candidate is
  `evidence/build/neo4j-hotel-graph-prebuilt.dump`, with SHA-256
  `a6eeecc3305acbbffe46e0ef7531db34c5a62d62db200c5574c3946102e29f02`.
- The long-running shell read a concurrently updated copy of its script after
  graph readiness and stopped on a syntax error before export. The guarded
  volume preserved the completed graph. A clean recovery shutdown and dump
  succeeded without another Bedrock call, and the candidate passed an isolated
  restore validation against every prebuilt contract gate.
- The isolated learner-additive validation passed the exact transition from
  295 to 300 Documents and Hotels, from 1,606 to 1,632 amenity assertions, and
  from 172 to 175 pool sources. Its complete 300-source projection reconciled
  exactly.
- `setup/build_prebuilt_graph.sh` now enables APOC explicitly, checks for
  `apoc.merge.relationship` before the canary, and reports an actionable
  prerequisite failure. The exact startup configuration passed against a
  throwaway `neo4j:latest` container.
- The 24-cell release smoke covered all six questions, both retrieval arms,
  and both prompt conditions. It recorded 24 scored trials with no tool errors;
  the optional 240-trial statistical benchmark was deliberately deferred.
- Modules 1 and 2 passed in the complete live notebook run. Module 3 exposed a
  negation-sensitive availability assertion; after the assertion was repaired,
  its finalized notebook passed all nine cells in a clean rerun.
- The accepted candidate was copied to `static/neo4j-hotel-graph.dump` in the
  repository working tree; both files have SHA-256
  `a6eeecc3305acbbffe46e0ef7531db34c5a62d62db200c5574c3946102e29f02`.
- The completed changes, evidence, candidate, and replacement static dump are
  not yet committed or pushed. That version-control handoff is separate from
  the completed technical release checklist.
- All disposable prebuilt, recovery, additive, and final-validation Neo4j
  containers and volumes were removed after their artifacts and evidence were
  saved.

Investigated 2026-08-21 against the current repository, the upstream
`sample-stop-ai-agent-hallucinations-workshop` repository, its historical full
build log, the committed hotel corpus, and the live Aura staging graph.

## Goal

Fix shared amenity identity with the smallest approach that is reliable and
easy to explain in a four-hour introductory workshop.

The workshop lesson should be:

> Use the LLM for genuinely unstructured extraction. When a source already
> contains a structured list, parse that list directly and use its values as
> graph identity.

This is a workshop implementation, not a general-purpose master-data or entity
governance system.

## Workshop scope decisions

- The `## Hotel Amenities` bullet list is the authoritative amenity source.
- The exact trimmed bullet text is the canonical `Amenity.name`.
- All 65 author-declared labels are retained. Grouping them into broader
  concepts is outside this fix.
- The LLM no longer extracts Amenity nodes or `OFFERS_AMENITY` relationships.
- The graph is rebuilt from the committed source data. No legacy migration,
  alias catalog, rollback manifest, or compatibility layer is required.
- The same parser runs for the prebuilt graph and the five learner-ingested
  documents.
- Shared Amenity nodes contain only their canonical name. Hotel-specific
  descriptions, fees, hours, or availability are not placed on the shared
  node.
- Global name-based entity resolution is disabled so two hotels with the same
  display name cannot collapse into one Hotel.
- Every source document must produce exactly one Hotel before its amenities are
  attached.

## What the upstream repository showed

### How the graph is built

The upstream repository extracts `01-graph-build/hotel-faqs.zip`, selects a
30-document lite build or all 300 documents, and sends each whole document to
`SimpleKGPipeline`.

The shared build path already centralizes useful behavior in
`01-graph-build/graph_builder.py`:

- The notebook and preparation script call the same builder.
- A scoped wipe removes only nodes owned by the workshop build.
- A three-document canary runs before the full extraction.
- Failed documents receive one retry after their partial graph is cleared.
- `Document.source_filename` records which source file produced a document.
- Document, Chunk, and entity provenance relationships make source
  reconciliation possible.
- Retrieval indexes and downstream fixtures are prepared and checked in one
  flow.
- Lite and full build modes give facilitators a fast diagnostic path and a
  complete release path.

These patterns are worth reusing. The current repository already carries newer
versions of much of this machinery, so the fix should extend the shared builder
instead of adding a second graph-build path.

### Where the build went wrong

The extraction step uses Claude through a custom Bedrock adapter. That adapter
returns prompt-generated text which is then repaired and parsed as JSON. It
does not use provider-enforced structured output.

The pinned graph schema closes node labels, relationship types, and graph
patterns. It does not constrain `Amenity.name`. The model can therefore turn
the same source line into `WiFi`, `High-Speed WiFi`, or another paraphrase.

The pipeline then runs exact same-label, same-name entity resolution over all
entities. That cannot reunite paraphrased amenities, and it can merge distinct
hotels that happen to share a display name.

The historical full-build log shows extraction parse errors followed by
successful-looking document messages. The completed build contained 300
Document nodes and 300 Chunk nodes but only 292 Hotel nodes. The default error
behavior allowed partial extraction to continue, while readiness checks proved
only that at least one Hotel conformed to the schema.

Four documents failed to produce a Hotel. Four additional Hotel nodes were
lost when exact-name resolution merged these cross-city pairs:

- Riverside Crossing Suites in Dallas and Windsor.
- Riverside Lodge in Boise and Calgary.
- Riverway Lodge in Minneapolis and Saskatoon.
- Waterway Inn in Houston and Kitchener.

Those eight losses reconcile 300 source documents to 292 Hotel nodes.

The pool evidence exposes three different failure classes. The corpus contains
175 hotels whose authoritative amenity list includes a pool, while the graph
returned 168 Hotel identities. Four pool-bearing documents did not produce a
Hotel, two duplicate-name pairs affected the pool result, and one document that
explicitly said no pool was turned into a positive Pool amenity.

The dump process copied the resulting Aura graph and checked structural counts.
It did not normalize amenities or reconcile extracted facts to source. The
current dump repair adds missing source filenames, hotel IDs, and Rule data,
but it does not repair amenity identity.

Five documents are omitted from the prebuilt graph and extracted live by the
learner. They use the same generative path, so changing only a dump would allow
the defect to return during the workshop.

## Corpus evidence

The source already provides a simple deterministic contract:

| Measure | Observed value |
|---|---:|
| Hotel FAQ documents | 300 |
| Documents with exactly one `## Hotel Amenities` section | 300 |
| Amenity bullet rows | 1,632 |
| Distinct amenity labels | 65 |

The most frequent source labels are already identical across documents:

| Source label | Occurrences |
|---|---:|
| `On-Site Restaurant` | 300 |
| `Complimentary High-Speed Wifi` | 300 |
| `24-Hour Fitness Center` | 274 |
| `Outdoor Swimming Pool` | 175 |
| `Full-Service Spa` | 162 |
| `Lounge Bar` | 130 |

The graph has 83 generated amenity names even though the complete source corpus
has 65 explicit labels. The LLM introduced variation into a field that did not
need generation.

Views, tours, a hammam, architecture, and other low-frequency labels are not
extraction mistakes. The source authors explicitly placed them in the amenity
list. Reclassifying them may be a reasonable future content decision, but it is
not required to repair graph identity.

## Why the earlier proposed fixes are not the answer

### Enum in `GRAPH_SCHEMA`

The installed `neo4j-graphrag` property model accepts a property name, Neo4j
type, description, and required flag. An added enum member is ignored. The
custom Bedrock wrapper also does not enforce an output schema, so putting
allowed values in a prompt would remain probabilistic.

Provider-enforced structured output is useful for other unstructured fields,
but it adds no value to an amenity list that can be parsed directly.

### Fuzzy or semantic resolution

Similarity is not identity. Tested fuzzy clusters incorrectly joined
restaurant with bar, fitness center with business center, valet with
self-parking, view types with river cruise, and a hammam with architecture.
Transitive merging makes a single bridging phrase capable of collapsing
otherwise distinct concepts.

This is too risky for automatic graph mutation and too complicated for the
workshop problem.

### Full-text indexing

A full-text index can improve name lookup. It cannot make two Hotel
relationships point to the same Amenity node, so it does not repair traversal.

### Reviewed merge map or governed catalog

A reviewed alias map and stable concept catalog would be appropriate if many
independent producers supplied changing vocabularies. This workshop has one
fixed corpus whose amenity values are already explicit and consistent.

Adding catalog versions, lifecycle states, alias approval, quarantine, and
migration tooling would obscure the introductory lesson without solving a
problem the workshop actually has.

### Legacy migration

The source corpus is committed and the graph is disposable. Rebuilding it with
the corrected pipeline is simpler and easier to verify than migrating the
LLM-generated amenity slice in place.

## Recommended implementation

### Deterministic amenity parser

Add a small shared parser that:

- Locates the single `## Hotel Amenities` section.
- Reads only its bullet list and stops before the following subsection.
- Trims formatting while preserving the authored label.
- Rejects a missing, repeated, or malformed section.
- Returns the source filename and labels needed for provenance.

The parser should not interpret later prose. This avoids turning sentences such
as “Pool facilities are not available” into positive amenities and keeps the
workshop contract easy to state.

### Simple graph materialization

For every parsed label:

- Match the Hotel through its Document and Chunk provenance.
- Require exactly one Hotel for the source document.
- Merge one shared Amenity by its canonical source name.
- Merge one `OFFERS_AMENITY` relationship from that Hotel.
- Keep source filename or Chunk provenance so the result remains inspectable.

Create a uniqueness constraint on `Amenity.name`. No `amenity_id`, alias file,
category hierarchy, or catalog version is needed for this fixed corpus.

### Safer LLM extraction boundary

Use a schema for the LLM pipeline that excludes Amenity and
`OFFERS_AMENITY`. Keep those types in the overall workshop graph contract and
write them only through the deterministic materializer.

Disable the pipeline's global exact-name resolver. For this workshop, keeping
Policy and Service nodes document-scoped is safer and simpler than teaching
type-specific entity-resolution policy. Shared Amenity nodes still provide the
connected-context traversal the workshop is meant to demonstrate.

Change extraction failure handling so a parse error cannot be printed as a
successful document. Require each Document to resolve to exactly one Hotel
before the build or learner ingestion succeeds.

### Rebuild rather than migrate

Run the corrected full build from the committed corpus and generate a new
prebuilt graph artifact. Keep the five held-out documents out of that artifact
and let the existing additive build process ingest them during the workshop.
The additive path must invoke the same amenity parser and materializer.

The rebuild is facilitator and release work. Participants should not spend
workshop time rebuilding hundreds of documents or learning migration mechanics.

## Test strategy during implementation

Testing should progress from fast source-contract checks to one release rebuild.
Each implementation slice starts with a failing regression test, adds the
smallest change that makes it pass, and runs the broader phase gate before work
moves forward.

### Gate 1: Parser unit tests

These tests use committed text fixtures and require no Neo4j, AWS credentials,
or Bedrock calls.

- Confirm all 300 documents contain exactly one authoritative amenity section.
- Confirm the complete corpus yields 1,632 bullet assertions and 65 distinct
  names.
- Confirm both Chicago documents return the exact authored WiFi label.
- Confirm parsing stops before later subsections, so explicit pool-negation
  prose cannot become an amenity.
- Confirm missing, repeated, empty, and malformed sections fail with the source
  filename in the error.
- Confirm parsing the same document twice returns identical ordered results.

**Pass condition:** The parser reproduces the measured corpus inventory exactly
and all malformed fixtures fail before any graph interaction.

### Gate 2: Materializer unit and integration tests

Most materializer tests should use a fake transaction or recorded write plan.
One focused integration test should run against a disposable local Neo4j
database.

- Confirm writes are parameterized and match Amenities by canonical source name.
- Confirm a second materialization creates no duplicate Amenity nodes or
  `OFFERS_AMENITY` relationships.
- Confirm the uniqueness constraint rejects duplicate canonical names.
- Confirm zero or multiple Hotels for one source document stops the write.
- Confirm source filename or Chunk provenance is retained for every assertion.
- Confirm shared Amenity nodes contain no hotel-specific fee, hours,
  description, or availability values.
- Confirm the two Chicago Hotels point to one WiFi node by node identity.

**Pass condition:** The small integration graph is source-reconciled,
idempotent, and unchanged by a second run.

### Gate 3: Builder regression tests

These tests use mocked LLM responses and repository configuration. They should
not call Bedrock during the normal test suite.

- Confirm the schema passed to `SimpleKGPipeline` excludes Amenity and
  `OFFERS_AMENITY` while the overall graph contract still includes them.
- Confirm global entity resolution is disabled.
- Confirm malformed LLM output makes the document fail visibly rather than
  print success.
- Confirm final readiness requires exactly one Hotel for every source
  Document.
- Confirm all four duplicate cross-city Hotel pairs remain separate.
- Confirm both full and additive builders invoke the same amenity parser and
  materializer.

**Pass condition:** Mocked extraction cannot write an Amenity, silently lose a
Hotel, or merge Hotels by display name.

### Gate 4: Lite build acceptance

Run the existing deterministic lite selection before spending time on a full
release build.

- Derive expected Hotel and amenity assertions directly from the selected
  source filenames.
- Reconcile graph rows to the exact source pairs of filename and amenity name.
- Confirm there are no missing or extra Hotel-to-amenity assertions.
- Confirm repeating the amenity step changes no counts.
- Run the existing setup test suite and notebook smoke checks affected by the
  graph contract.

**Pass condition:** The lite graph exactly matches its selected source files and
all repository regression tests pass.

### Gate 5: Release rebuild acceptance

The expensive full build is a release gate, not a per-change developer test.

- Confirm 300 source Documents resolve to 300 distinct Hotels.
- Confirm the final graph contains 65 Amenity nodes and 1,632
  `OFFERS_AMENITY` assertions.
- Compare the complete set of source pairs, filename plus amenity label, with
  graph pairs reached through provenance. Require exact equality rather than
  checking counts alone.
- Confirm the 295-document prebuilt graph plus the five additive documents has
  the same final amenity projection as the complete 300-document build.
- Confirm Chicago shared WiFi, the 175 pool-listing sources, the pool-negation
  case, and all four duplicate Hotel-name pairs.
- Re-run affected Phase 1.5 reference facts, evaluation trials, and notebook
  smoke tests before publishing the graph artifact.

**Pass condition:** Source reconciliation is exact, the prebuilt-plus-live path
equals the complete path, and all workshop acceptance evidence passes.

### Test ownership and cadence

- Put fast amenity tests in `setup/test_amenities.py` so they run with the
  existing pytest-based setup suite.
- Reuse the upstream Bedrock-provider mocking style for extraction-error tests.
- Run focused tests after each small code change and the full offline setup
  suite at the end of every phase.
- Run the lite build when integration behavior changes.
- Run the complete rebuild only after all earlier gates pass and before a new
  workshop artifact is published.
- Record source-versus-graph reconciliation totals in the build report so a
  facilitator can diagnose a failed release without inspecting the graph by
  hand.

## Implementation plan

### Phase 1: Add deterministic amenity handling

**Status: Complete**

**Outcome:** The same source list always produces the same shared Amenity nodes.

**Checklist:**

- [x] Add the shared amenity-section parser under `notebooks/workshop`.
- [x] Add the idempotent Amenity and `OFFERS_AMENITY` materializer.
- [x] Add the uniqueness constraint for `Amenity.name`.
- [x] Resolve each Hotel through Document and Chunk provenance rather than its
  generated display name.
- [x] Reject missing, repeated, or malformed amenity sections.
- [x] Reject a source document that does not resolve to exactly one Hotel.
- [x] Keep hotel-specific amenity qualifiers off the shared Amenity node.

**Validation:** All 300 documents parse to 1,632 amenity assertions and 65
distinct names. A repeated run produces no duplicate nodes or relationships.

**Completion criteria:** Amenity identity is completely independent of LLM
wording and every edge can be traced to a source document.

**Validation result:** The focused amenity suite reproduces all 300
documents, 1,632 assertions, and 65 names. It also verifies malformed-input
failures, parameterized provenance lookup, idempotent `MERGE` writes, source
provenance on `OFFERS_AMENITY`, and ambiguous-Hotel rejection. The complete
offline setup suite passes. The local Neo4j candidate and its isolated restore
passed the exact prebuilt contract, and the additive graph passed the complete
300-source contract. No shared Aura graph was modified.

### Phase 2: Integrate the corrected build and rebuild the graph

**Status: Complete**

**Outcome:** Full, prebuilt, and learner-additive paths use the same extraction
boundary.

**Checklist:**

- [x] Separate the overall graph contract from the schema passed to the LLM.
- [x] Exclude Amenity and `OFFERS_AMENITY` from LLM extraction.
- [x] Disable global exact-name entity resolution.
- [x] Make component failures fail the affected document visibly.
- [x] Require one Hotel per source document in canary and final readiness
  checks.
- [x] Invoke deterministic amenity materialization from both full and additive
  build flows.
- [x] Finish the running rebuild from the committed source corpus.
- [x] Generate and restore the new prebuilt candidate artifact with the five
  held-out documents omitted.

**Required release validation:** The complete build has 300 distinct Hotels,
65 Amenity nodes, and 1,632 `OFFERS_AMENITY` assertions. The prebuilt graph plus
five live documents produces the same final amenity projection as the complete
build.

**Completion criteria:** No supported build path can create an Amenity name or
merge a Hotel identity through LLM output.

**Validation result:** The LLM-only schema excludes Amenity and
`OFFERS_AMENITY`; the pipeline raises component errors, disables global entity
resolution, and uses the configured Neo4j database. Both build flows parse
amenities before graph mutation, require one distinct Hotel per source, and
materialize the authored lists only after extraction retries finish. The
builder then reconciles the exact filename-and-amenity pairs rather than
trusting counts alone. Shared readiness rejects Documents without exactly one
Hotel, Hotel nodes shared across source Documents, orphan Hotels, and any
Hotel-count mismatch. The overall graph contract now exposes only `name` on a
shared Amenity, matching the deterministic write model. The focused Phase 1
through Phase 3 suite passes 36 tests, and the final complete offline setup
suite passes 153 tests with one intentional environment-dependent skip. Ruff
lint, formatting, and release-script syntax checks pass.
The `prebuilt` build mode validates the complete 300-document corpus before
selecting 295 documents. The release script isolates the build from Aura,
enables and verifies APOC, and writes a candidate without replacing the
repository's existing static artifact. The real build completed all 295
sources; the candidate then passed an isolated restore, the five-document
additive path, and final
publication review. The accepted candidate is now the replacement static dump
in the repository working tree.

### Phase 3: Add focused tests and update the workshop story

**Status: Complete**

**Outcome:** The fix is protected without adding participant-facing complexity.

**Checklist:**

- [x] Test parser boundaries, corpus totals, idempotence, and source provenance.
- [x] Add regressions for Chicago shared WiFi, 175 pool-listing documents, the
  explicit pool negation, the four missing Hotels, and the four cross-city
  duplicate names.
- [x] Update readiness checks so Document and Chunk counts cannot substitute
  for one distinct Hotel per source.
- [x] Add artifact-wide amenity relationship reconciliation for a restored
  prebuilt graph, where the source files are not passed to the build function.
- [x] Re-run affected Phase 1.5 source reference facts offline.
- [x] Re-run the affected graph and agent evaluation evidence against the
  rebuilt artifact.
- [x] Update the Module 1 notebook, README, and workshop content with the
  deterministic extraction boundary.
- [x] Demonstrate against the rebuilt artifact that both Chicago hotels
  traverse to the same authored WiFi node.
- [x] Keep catalog governance, migration, and entity-resolution theory out of
  the required four-hour participant path.

**Required release validation:** Tests fail on the old graph defects and pass
on both the full build and the prebuilt-plus-live build.

**Completion criteria:** A participant can explain the implementation in one
sentence and inspect the source-to-graph evidence without learning a production
governance system.

**Validation result:** The participant story now uses one boundary: use the LLM
for prose, and parse a structured list directly when the source already
provides one. The Module 1 notebook includes the query that will show both
Chicago Hotels traversing to the same `Complimentary High-Speed Wifi` node. The
post-build validator in `setup/validate_graph_amenities.py` compares the exact
prebuilt or full source contract and its filename-and-amenity pairs with the
committed archive. It also detects missing Documents, orphaned or duplicate
relationships, incorrect relationship provenance, extra or missing Amenity
names, and multiple nodes for one canonical name. Offline regressions reproduce
300 documents, 1,632 assertions, 65 names, 175 pool-listing sources, the four
historical missing-Hotel sources, the explicit Austin pool negation, and the
four cross-city duplicate-name pairs. The same source check verifies that the
295-document prebuilt subset contains 1,606 assertions, 65 names, and 172
pool-listing sources; the five held-out files add 26 assertions and 3 pool
listings. The focused Phase 1 to Phase 3 suite passes 36 tests. The final
complete offline setup suite passes 153 tests with one intentional
environment-dependent skip. Both edited notebooks pass JSON parsing and Python
cell compilation, and Ruff lint and format checks pass. Live graph facts and
the approved 24-cell release smoke are recorded in
`evidence/phase15/PHASE-1.5-AMENITY-RECHECK.md`. Modules 1 and 2 passed together;
the finalized Module 3 notebook passed all nine cells after its
negation-sensitive availability assertion was corrected.

## Next steps

### 1. Finish and capture the prebuilt candidate

**Status: Complete with recovered provenance**

**Checkpoint note:** The release script now snapshots its own executable and
manifest writer before the long run, labels and retains failed volumes, prints
an exact provenance-checked resume command, stops Neo4j cleanly, and stages and
verifies the dump and manifest before atomic publication. This prevents a
concurrent source edit from changing later shell commands and preserves
completed extraction work across recoverable failures.

- [x] Complete all 295 Bedrock extractions without an unresolved document
  failure.
- [x] Require the final build readiness gates to pass before dumping Neo4j.
- [x] Generate `evidence/build/neo4j-hotel-graph-prebuilt.dump` without replacing the
  repository's existing static artifact during candidate construction.
- [x] Record an honest recovered manifest with the directly evidenced duration,
  candidate size and checksum, final readiness gates, wrapper failure, and
  explicit unavailable build-start commit, critical-file hashes, and immutable
  image identity.

### 2. Restore and validate the candidate

**Status: Complete**

- [x] Restore the candidate into a fresh disposable local Neo4j instance.
- [x] Run `setup/validate_graph_amenities.py --mode prebuilt` against the
  restored graph.
- [x] Confirm exactly 295 Documents, 295 distinct Hotels, 65 Amenity nodes,
  1,606 distinct source-to-amenity assertions, and 172 pool-listing sources.
- [x] Confirm every `OFFERS_AMENITY` relationship has one Hotel source and a
  matching `source_filename`, with no duplicate or orphan relationships.
- [x] Confirm the four historical missing-Hotel sources each resolve to one
  Hotel and all four cross-city duplicate-name pairs remain distinct.
- [x] Confirm both Chicago Hotels traverse to one shared
  `Complimentary High-Speed Wifi` node by node identity.

### 3. Make the release build reproducible

**Status: Complete**

- [x] Update `setup/build_prebuilt_graph.sh` so its disposable Neo4j image has
  APOC available before the canary begins.
- [x] Add a fast APOC prerequisite check with an actionable failure message.
- [x] Re-run shell syntax and offline repository checks after the script
  change.

**Validation result:** The script passes `bash -n` and diff checks. Its exact
APOC environment starts `neo4j:latest` with
`apoc.merge.relationship` available. The repository integrity check passes,
the focused changed-Python Ruff lint and format checks pass, and the complete
offline setup suite passes 153 tests with one intentional skip. After the
container-runtime failure, a second throwaway runtime
probe also confirmed the configured 4 GiB container cap, 512 MiB initial heap,
1.5 GiB maximum heap, 1 GiB page cache, and APOC procedure before the retry.

### 4. Validate the learner-additive path

**Status: Complete**

- [x] Add the five held-out documents to the restored candidate through the
  same Module 1 path used by participants.
- [x] Confirm the five documents add 26 amenity assertions and 3 pool-listing
  sources.
- [x] Confirm the combined graph has exactly 300 Documents, 300 distinct
  Hotels, 65 Amenity nodes, 1,632 source-to-amenity assertions, and 175
  pool-listing sources.
- [x] Confirm the combined projection exactly equals the complete 300-document
  source projection.

### 5. Complete live evidence and publication review

**Status: Complete**

**Release-evidence scope:** Run one trial for every combination of six
questions, two retrieval arms, and two prompt conditions: 24 trials across 24
cells. This is the release smoke gate for complete path coverage. The
10-trials-per-cell, 240-trial run is an optional statistical benchmark and is
not required to publish the graph artifact.

- [x] Re-run the affected Phase 1.5 graph facts against the accepted graph.
- [x] Run the 24-cell agent evaluation smoke against the accepted graph and
  require one scored trial per question, retrieval arm, and prompt condition,
  with no tool errors or unscored results.
- [x] Run the affected notebook live smoke checks against the accepted graph.
- [x] Update the Phase 2, Phase 3, and overall completion checklists with the
  recorded evidence.
- [x] Review the candidate before replacing or publishing
  `static/neo4j-hotel-graph.dump`.
- [x] Replace the repository's tracked static artifact in the working tree
  after the instruction to complete the entire release checklist, then verify
  its checksum matches the candidate.

### 6. Make every release operation reusable

**Status: Complete**

- [x] Persist the disposable Neo4j volume and release state after an
  interrupted build.
- [x] Add a resume command that skips only sources with exactly one Document,
  Chunk, and Hotel through provenance, clears incomplete sources, and runs the
  same final gates over all 295 sources.
- [x] Add a one-command candidate restore and validation wrapper.
- [x] Add a one-command five-document additive and before/after reconciliation
  wrapper.
- [x] Add a live-evidence wrapper for the Phase 1.5 harness and affected
  notebook smoke checks.
- [x] Write one release manifest containing the image digest, commit,
  critical-file hashes, duration, candidate size, checksum, and every gate
  result.

**Validation result:** `setup/validate_prebuilt_candidate.sh` now
restores and validates a candidate in isolated disposable Neo4j. The additive
and live-evidence Python entry points record explicit JSON manifests and stage
logs. `setup/build_prebuilt_graph.sh --resume` retains a labeled checkpoint and
reuses only current-source, current-contract documents with exactly one Chunk
and one globally unshared Hotel through provenance. Candidate creation writes
an atomic manifest with build, Git, Docker image, critical-file, size, and
checksum evidence. Facilitator builds use bounded three-way extraction by
default while participant ingestion remains sequential. Their final combined
offline gate passes 153 setup tests with one intentional skip, shell syntax,
repository integrity, and focused Ruff lint and formatting. The reusable live
runner supports a bounded question-partitioned worker count, records every
worker and merge command, and rejects incomplete, duplicate, tool-error, or
unscored evidence.

The completed candidate predates that manifest hook because its long-running
shell had already loaded the earlier script. The reusable
`write_prebuilt_manifest.py recover` command therefore wrote
`evidence/build/neo4j-hotel-graph-prebuilt.manifest.json` from the surviving successful
run log and artifact. It records the 10,729.83-second duration, all final
readiness gates, artifact timestamp, size and SHA-256, plus the later shell
syntax failure. It records unavailable build-start Git, file-hash, and image
identity fields as null. Current Git and critical-file hashes are labeled only
as the recovery environment, not as build inputs. Future runs use the normal
start/finish path and will not need recovery.

## Overall completion criteria

- [x] The same 300 documents always produce 300 distinct Hotels, 65 Amenity
  nodes, and 1,632 hotel-to-amenity assertions.
- [x] Both Chicago hotels share the same `Complimentary High-Speed Wifi` node.
- [x] An explicit negative statement outside the authoritative list cannot
  become a positive amenity.
- [x] Duplicate Hotel display names in different cities remain distinct.
- [x] The prebuilt and learner paths use the same deterministic amenity logic.
- [x] The graph is rebuilt from source rather than migrated from legacy
  generated values.
- [x] The participant-facing explanation remains appropriate for an
  introductory four-hour workshop.

## Final review

**Status: Complete**

The plan was audited again on 2026-08-23 against the saved artifacts and
release evidence. Every required checklist item is complete, and no required
technical release work remains.

- The candidate and replacement static dump are both 6,542,982 bytes and have
  SHA-256
  `a6eeecc3305acbbffe46e0ef7531db34c5a62d62db200c5574c3946102e29f02`.
- The additive evidence records an exact transition from 295 to 300 Documents
  and Hotels, from 1,606 to 1,632 amenity assertions, and from 172 to 175 pool
  sources, with no reconciliation problems.
- The live-evidence gate records six questions, 24 unique evaluation cells,
  no tool errors, and no unscored trials. The successful Module 3 rerun records
  a pass after the assertion defect was corrected.
- The pinned offline setup suite passes 153 tests with one intentional skip.
  Repository integrity, shell syntax, Ruff lint and formatting, and diff
  whitespace checks also pass.
- No shared Aura graph was modified, and all disposable Neo4j containers and
  volumes used by the release work were removed.

The only remaining actions are non-blocking handoff choices: commit and push
the working-tree changes if they are approved, optionally run the 240-trial
statistical benchmark if comparative rate claims are needed, and use a future
fresh build to capture native build-start provenance instead of the honest
recovered provenance attached to this candidate.
