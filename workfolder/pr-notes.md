## Summary

This branch restructures the middle of the workshop around connected context,
makes the graph build deterministic, and validates every module against live
Neo4j and Amazon Bedrock. The changes come out of running the workshop end to
end and are meant to make it hold up in front of a room.

## Why these changes

Running the full path surfaced a few things worth addressing before the next
delivery.

- **Amenity identity was generated rather than read.** Amenities came out of
  free-text LLM extraction, though every source document already lists them
  under a fixed heading. The model could name the same authored amenity
  differently between runs, so one label became several nodes and no two builds
  produced the same graph.
- **Some sources did not reach the graph.** 300 source documents produced 292
  hotels. A few extractions returned no hotel and the build continued past them,
  and global exact-name resolution merged hotels that share a name across
  cities. Free-text extraction also read one document that states a pool is
  unavailable as offering one.
- **The readiness checks measured shape rather than content.** They compared
  node and relationship counts, which a partial build can still satisfy.
- **The same extraction path runs during the lab.** Participants extract five
  documents live on the path used to build the shipped dump, so repairing the
  dump alone would leave the behavior in the classroom.
- **Module 2's lesson was hard to demonstrate reliably.** It stated up front
  that vector RAG hallucinates, then asked four stochastic agent runs to show
  it. On the repaired graph those runs did not land consistently. The vector
  arm's more common limitation was missing evidence rather than fabrication, and
  graph enrichment sometimes returned the less useful context. The underlying
  point survives, and it is sturdier when taught as complementary retrieval than
  as a contest.

## Curriculum restructure

Module 2 becomes **From Similarity Search to Connected Context**. It teaches
that semantic search, exact-term search, graph traversal, and structured Cypher
contribute different signals, and that a retrieval design combines them
according to the question. The comparison runs vector retrieval against
Vector-Cypher retrieval on the same questions. The notebooks now claim only what
the runs show reliably.

Module 3 collapses to a single notebook on the grounded booking agent. It picks
up the retrieval function selected in Module 2 and teaches grounded answers,
abstention, and the protected reservation command.

Every retrieval block shows its evidence before any generated answer: rank,
score, source file, the fields and relationships used, and context size. The
questions, fixtures, and expected answers these lessons depend on are pinned in
shared workshop code rather than restated in each notebook, so a retrieval
change fails the tests instead of quietly diverging from the prose. Optional
Text2Cypher stays, governed by a pinned schema, a timeout, and a read-only
check.

Content routes, navigation, and the learner-facing claims across Modules 1
through 5 were updated to match.

## Deterministic graph build

Amenities move out of the LLM extraction schema. A shared parser reads the
authored amenity bullets exactly as written, rejects malformed sections, merges
amenities by their canonical source name, and keeps provenance on every
relationship. Global exact-name resolution is off, so same-named hotels in
different cities stay distinct. The LLM still handles the genuinely unstructured
prose, which is where it earns its place.

Extraction errors now fail their document rather than passing through. Each
source must resolve to exactly one hotel before amenities attach, and the
validators reconcile the graph against the corpus instead of counting nodes. The
build asks for an explicit rebuild flag before clearing a populated graph.

The shipped dump was rebuilt on this pipeline and reaches all 300 hotels once
Module 1's held-out documents are loaded.

## Other module fixes

- The optional Module 1 demo now cleans up after itself, leaving the graph
  counts and the participant source documents unchanged.
- The Module 4 Lambda role needed `bedrock:InvokeModel` on the embedding model
  to pass the notebook's own smoke test. That grant is now in the role cell.
- Module 6 resolved its base path to the notebooks directory rather than the
  repository root, so it did not find credentials and its live cells were
  skipped. They run now.
- The Runtime build context excludes local files such as `.env`, notebooks, and
  toolkit state, so they stay out of the image.
- Every notebook shares one tested base-path contract, so the repository root, a
  notebook directory, and a module directory all resolve the same assets.

## Repository cleanup

FAISS and the benchmark harness left the learner path along with their
dependency. The setup directory is now the participant surface, with tests,
release automation, and dump repair moved into the ignored work tree. The Module
2 decision tree was rebuilt from an Excalidraw source, and images no longer
referenced by any page were removed.

## Live validation

Modules 1 through 3 passed against Neo4j Aura and Claude Sonnet on Bedrock, with
the graph growing from 295 to 300 hotels as expected. Modules 4 through 6 passed
on a later commit, covering both Gateway tools, cross-session recall, and the
deployed Runtime with its grounding, refusal, policy, write, and idempotency
checks. Cleanup removed the test records and the workshop AWS resources, leaving
all 300 hotels and unrelated resources untouched.

## Known gaps

Modules 4.1 and 5 have no teardown path. That affects only participants
running outside Workshop Studio, which reclaims the account when the event ends,
so fixing it is out of scope here.

## Squash merge message

Clear the prefilled commit subjects and use the following.

**Title**

```
restructure modules 2-3 and make the graph build deterministic
```

**Extended description**

```
Amenities came from free-text LLM extraction, though every source
document already lists them under a fixed heading, so no two builds
matched. A shared parser now reads those bullets as written, extraction
errors fail their document, and the validators reconcile the graph
against the corpus. The shipped dump was rebuilt on this pipeline.

Module 2 becomes From Similarity Search to Connected Context, teaching
complementary retrieval rather than a contest four stochastic agent
runs could not show reliably. Module 3 collapses to one grounded
booking agent notebook. Modules 1 through 6 passed live runs.
```
