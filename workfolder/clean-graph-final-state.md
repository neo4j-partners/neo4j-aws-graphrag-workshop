# Clean graph final state

**Status: Complete as of 2026-08-23.** All required implementation, artifact,
restore, additive-ingestion, live-evidence, notebook-smoke, and offline test
gates in [`clean-graph.md`](clean-graph.md) are complete. The accepted dump was
committed at `3ce32f87bca0368a68b3184f297fed506ee09eb6` and is present at
`static/neo4j-hotel-graph.dump`. This file is a local author note rather than a
required release record.

## Overview of what was wrong and the problem

The original graph build asked the LLM to invent identity for amenity values
that were already available as a structured list in every source document.
That made shared amenity identity inconsistent, allowed extraction failures to
look successful, and let global name matching merge unrelated hotels. The
release checks counted graph structures but did not fully reconcile each
source document and amenity assertion to the resulting graph.

- **Unstable amenity identity:** The LLM could turn the same authored amenity
  into different names, producing 83 generated Amenity names from a corpus
  containing 65 exact labels.
- **Silent extraction loss:** The historical build produced 300 Document and
  Chunk nodes but only 292 Hotel nodes because four documents failed to
  produce a Hotel and the build continued.
- **Incorrect hotel merging:** Global exact-name entity resolution collapsed
  four pairs of same-named hotels located in different cities, accounting for
  four more missing Hotel identities.
- **Incorrect positive facts:** Free-form extraction converted one explicit
  statement that a pool was unavailable into a positive Pool amenity.
- **Incomplete release validation:** Earlier readiness checks did not require
  exactly one Hotel per source or compare the complete set of source filename
  and amenity pairs with the graph.
- **Shared defect across build paths:** Both the 295-document prebuilt graph
  and the five documents ingested during the workshop used the same
  generative amenity path, so repairing only the dump would not have fixed the
  participant workflow.
- **Fragile long-running release process:** Initial release attempts exposed a
  missing APOC dependency, a local container-runtime interruption, and a shell
  syntax failure caused by editing a script while its long-running process was
  still reading it.

## What was fixed, built, and implemented

The graph now uses a clear deterministic boundary: the LLM extracts genuinely
unstructured prose, while a shared parser reads the authoritative
`## Hotel Amenities` bullet list exactly as written. The same parser,
materializer, provenance rules, and readiness contracts now protect the full,
prebuilt, and learner-additive paths.

- **Deterministic amenity parser:** A shared parser locates exactly one amenity
  section, reads only its bullets, preserves the authored labels, and rejects
  missing, repeated, empty, or malformed sections.
- **Source-backed graph materialization:** Amenity nodes are merged by their
  canonical source names, `OFFERS_AMENITY` relationships retain source
  provenance, writes are idempotent, and every source must resolve to exactly
  one Hotel before amenities are attached.
- **Safer LLM boundary:** Amenity nodes and relationships were removed from the
  LLM extraction schema, global exact-name entity resolution was disabled, and
  extraction component errors now fail the affected document visibly.
- **Exact readiness and reconciliation:** Validators now reject missing,
  orphaned, duplicated, or cross-source Hotel identities and compare the exact
  filename-to-amenity projection against the committed corpus instead of
  relying on counts alone.
- **Reusable release automation:** The release scripts now provide isolated
  local Neo4j startup, an APOC prerequisite check, bounded memory, clean
  shutdown, labeled checkpoint volumes, resume support, staged artifact
  publication, manifest generation, candidate restore validation, additive
  validation, and live-evidence execution.
- **Recoverable and faster extraction:** Facilitator builds default to three
  concurrent Bedrock extractions, accept a bounded concurrency of one through
  eight, and can resume from complete source-provenance checkpoints without
  repeating successful document extractions. Participant ingestion remains
  sequential by default.
- **Completed prebuilt artifact:** All 295 required Bedrock extractions
  completed with no unresolved document failure. The candidate contains 295
  Documents, 295 Chunks, 295 Hotels, 65 Amenities, 1,606 amenity assertions,
  and 172 pool-listing sources.
- **Completed learner-additive path:** The five held-out documents add exactly
  five Documents, five Hotels, 26 amenity assertions, and three pool-listing
  sources. The resulting graph contains 300 Documents, 300 Hotels, 65
  Amenities, 1,632 amenity assertions, and 175 pool-listing sources, matching
  the complete corpus projection exactly.
- **Accepted replacement dump:** `static/neo4j-hotel-graph.dump` is 6,542,982
  bytes and has SHA-256
  `a6eeecc3305acbbffe46e0ef7531db34c5a62d62db200c5574c3946102e29f02`.
- **Live and notebook evidence:** The release smoke covered six questions,
  two retrieval arms, and two prompt conditions for 24 unique scored cells,
  with no tool errors or unscored trials. Modules 1 and 2 passed in the
  combined notebook run, and Module 3 passed all nine cells after its
  negation-sensitive test assertion was corrected.
- **Regression protection:** The pinned offline setup suite passes. Repository
  integrity, shell syntax, Ruff lint and formatting, and whitespace validation
  also pass.
- **Scoped execution and cleanup:** The work used local disposable Neo4j only,
  did not modify shared Aura, created no AWS infrastructure, and removed all
  disposable release containers and volumes after saving their evidence.

## What work remains and what else needs to be done

No required technical work remains for the clean-graph release checklist. The
items below are handoff choices, optional analysis, or future-run improvements;
none blocks the accepted local artifact.

- **Version-control handoff:** The dump is committed. Normal branch review and
  merge remain repository workflow rather than a separate graph-release gate.
- **Future native provenance:** The accepted candidate has an honest recovered
  manifest because its original wrapper failed after graph readiness. The
  build-start Git state, critical-file hashes, and immutable image identity
  were unavailable and are recorded as null. A future fresh build will use the
  completed start/finish manifest path and capture those fields natively.
- **External deployment:** If the replacement dump must be published outside
  this repository or loaded into a shared Neo4j environment, perform that as a
  separately approved deployment. The completed work intentionally did not
  modify shared Aura or other external infrastructure.
- **Routine maintenance:** Rerun the reusable build and validation workflows
  when the corpus, graph contract, model configuration, or release dependencies
  change.
