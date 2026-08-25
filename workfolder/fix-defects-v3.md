# Remaining workshop fixes

Date: 2026-08-23
Branch: `restructure-modules-02-03`
Status: live validation open

This tracked file lists only work that is still open. The notebooks are the
specification and the tests are the enforcement. Files under `workfolder/` are
local author notes, not release records and not required in a fresh clone.

## Already complete

The deterministic graph build, the amenity parser, and the published dump are
finished. The tracked artifact is `static/neo4j-hotel-graph.dump`; its identity
is recorded in Item 3 below.
The Module 2 and Module 3 restructure is implemented. That work covered safe graph
preparation that refuses to clear a populated graph without an explicit rebuild
request, a self-cleaning optional Module 1 demo, the locked Cairo and Chicago
readiness contracts, separate structured and source-text context sizes, one tested
base-path contract for every notebook and helper, and the removal of FAISS along
with the Phase 1.5 benchmark harness. The offline suite and `setup/check_repo.py`
pass. Details are in git history.

## Item 1: Correct the learner-facing diagram and prose

Offline work. No credentials needed.

- [x] The Module 2 decision tree sends the Chicago spa-and-pool question to
  Text2Cypher, but the notebook answers it with reviewed fixed Cypher. Give fixed
  Cypher its own branch carrying that example, and label Text2Cypher optional.
- [x] Export the corrected PNG into `workshop-content/images/` and
  `static/images/` so both trees stay identical.
- [x] Change `setup/test_module2_diagrams.py` so it checks which pattern owns the
  Chicago example instead of only checking that both labels appear.
- [x] Add reviewed fixed Cypher to the Module 2 content table and mark
  Text2Cypher optional.
- [x] Module 3 prose says Module 2 compares the Hybrid-Cypher configuration.
  Module 2 only selects it. Correct that sentence.
- [x] Delete `01-rag-vs-graphrag-problem.png` from both image trees. No active
  page references it.
- [x] Correct the image path in `DIAGRAM_PROMPTS.md` in both image trees.

The optional editable source for `03-grounded-agent-architecture.png` is
deferred and does not block this workshop. For this small workshop, a maintained
PNG plus its authoring prompt is sufficient. Automatic discovery of every
learner page is also deferred; the small explicit `LEARNER_FILES` list remains
the intentionally simple contract and must be updated when a page is added.

**Done when:** the offline suite passes, `setup/check_repo.py` image parity and
content-reference checks pass, and no active page references a deleted image.

**Result:** Complete. The setup suite passes 214 tests, the repository checker
passes, both image trees are byte-identical, and the deleted image has no active
reference.

## Item 2: Run Modules 1 through 3 live once

This is the release blocker. It spends Bedrock calls and writes to the shared
Neo4j graph. It creates no AWS resources.

### The command

Run the whole gate through the existing harness rather than by hand. It reads
each notebook into memory, executes it, and never modifies the source file.

```bash
cd notebooks
uv pip install nbconvert nbformat ipykernel
uv run python ../setup/run_notebooks.py --modules 1-3 --keep-output
```

Without `--include-deploy` the harness refuses to run any notebook that creates
AWS resources, so this selection cannot reach Modules 4 or 5 by accident.

### Status

Fill this in as the run proceeds. One row per notebook, because a module can
pass one notebook and fail the next.

| Module | Notebook | Status | Commit | Date | Note |
| --- | --- | --- | --- | --- | --- |
| 1 | `1.1_build_graph.ipynb` | passed | `b1e2684` | 2026-08-23 | Live additive and idempotence paths passed. |
| 2 | `2.1_connected_context.ipynb` | passed | `b1e2684` | 2026-08-23 | Neo4j 5.27-compatible ordering passed live. |
| 3 | `3.1_grounded_booking_agent.ipynb` | passed | `b1e2684` | 2026-08-23 | Abstention, guest limit, and retry assertions passed. |

Status values are `not run`, `passed`, `failed`, and `stale`. Use `stale` when a
notebook passed and a later change re-opened it under the re-run rule below.

### Before the run

- [ ] Start from a clean committed revision and record that commit as the code
  under test. The offline suite and `setup/check_repo.py` pass at that commit.
- [ ] Read `.env` and confirm the non-secret Neo4j host and database identify the
  intended workshop environment. Do this before any write.
- [ ] Record the starting graph identity. The accepted prebuilt artifact holds
  295 Documents, 295 Hotels, 65 Amenities, and 1,606 amenity assertions.

### During the run

- [ ] Run Module 1, then Module 2, then Module 3 in order against the same
  environment.
- [ ] Confirm the notebooks' own assertions pass. They already check the Cairo
  arrival time, the Chicago postal code and cancellation policy, the enriched
  Cairo record and its provenance, and the Chicago candidate, qualifier, and
  exclusion.
- [ ] Confirm Module 1 adds the five held-out sources, producing 300 Documents,
  300 Hotels, 65 Amenities, and 1,632 amenity assertions.
- [ ] Confirm the optional Module 1 demo itself leaves the graph counts
  unchanged and does not affect the five participant sources.
- [ ] Confirm Module 3 abstention, guest-limit enforcement, and idempotent
  reservation retries pass.
- [ ] Confirm the optional Module 2 Text2Cypher cell uses the same Neo4j
  credentials as the rest of the workshop and reports
  `passed: EXPLAIN query_type=r`. The workshop intentionally avoids a second
  reader credential: `EXPLAIN` is the application guard here, while production
  deployments should use a read-only Neo4j user as an independent database
  boundary. Its output is supporting evidence, so a failure does not fail the
  deterministic Module 2 gate.

### After the run

- [ ] Record the ending graph counts and confirm the expected transition from
  the 295-document prebuilt graph to the 300-document learner-complete graph.
- [ ] Write the result to the tracked root file `live-validation.md`: commit,
  date, starting and ending graph counts, model ID, region, database, and pass or
  fail for each notebook.
- [ ] Update the status table above and mark this item complete.
- [ ] If a Module 1 through 3 notebook, shared helper, fixture, graph artifact,
  or dependency lock changes after the run, set the affected rows to `stale` and
  repeat that acceptance. Editing only the validation record does not require
  another run.

**Done when:** all three rows read `passed` at one commit and the record is
committed.

**Result:** Complete. The offline suite (214 tests), repository checker, and
full live Modules 1--3 gate passed for `b1e2684`. See `live-validation.md`.

## Item 3: Keep one simple tracked artifact record

- [x] Delete the "Optional 240-trial benchmark" section. It documents
  `setup/run_live_evidence.py`, which no longer exists.
- [x] Delete "Optional statistical benchmark" from the remaining-work list for
  the same reason.
- [x] Remove the fixed 153-test total. The suite reports its own count, and three
  documents currently claim three different numbers.
- [x] Confirm the published dump independently. `static/neo4j-hotel-graph.dump` is
  6,542,982 bytes with SHA-256
  `a6eeecc3305acbbffe46e0ef7531db34c5a62d62db200c5574c3946102e29f02`, verified
  2026-08-23.
- [x] Record that the dump entered Git in commit
  `3ce32f87bca0368a68b3184f297fed506ee09eb6`.
- [x] Keep `workfolder/clean-graph-final-state.md` as an optional local author
  note. Do not require it, `workfolder/defects-v2.md`, or a separate publication
  dossier in a fresh clone.

The only additional tracked record will be the short `live-validation.md`
created by Item 2. That is enough for a simple workshop: the repository contains
the artifact and tests, while the small record says which commit was run live.

## Item 4: Run Modules 4 through 6 live

Not a release blocker for Modules 1 through 3, and worth doing before the
workshop runs in front of participants. Modules 4 and 5 create real AWS
resources, so this item carries a cost and a cleanup obligation that Item 2 does
not.

The last full attempt was 2026-08-20. It failed on Modules 4 and 5 for
three root causes, and all three are now fixed in tracked source. Confirming
those fixes live is the point of this item.

### Prerequisite

Item 2 passes first. Module 5's smoke tests assert against `hotel_id` and the
`Rule` nodes that Module 3 relies on, so a graph missing the dump repairs fails
Module 5 for a reason that has nothing to do with Module 5.

- [x] Item 2 is complete at the commit under test.
- [x] `setup/repair_dump.py` has been applied to the graph, or the restore is
  known to already carry the repairs.

### The command

```bash
cd notebooks
uv run python ../setup/run_notebooks.py --modules 4,5 --include-deploy --keep-output
uv run python ../setup/run_notebooks.py --modules 6 --keep-output
```

Module 6 needs no `--include-deploy`. It writes memory nodes to Neo4j and creates
nothing in AWS.

### Status

| Module | Notebook | Creates AWS resources | Status | Commit | Date | Note |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | `4.1_agentcore_gateway.ipynb` | yes | passed | `6e06c32` | 2026-08-23 | Both Lambda tools and both Gateway targets passed live. |
| 5 | `5.1_deploy.ipynb` | yes | passed | `6e06c32` | Deploy, grounding, refusal, policy, write, and idempotency checks passed. |
| 6 | `6.1_neo4j_memory.ipynb` | no | passed | `6e06c32` | Wrote real memory data; isolation, recall, provenance, and tagging passed. |

### Confirm the three 2026-08-20 fixes

- [x] Module 4.1's Lambda execution role can invoke Bedrock. The notebook's own
  positive-control smoke test failed with `AccessDeniedException` before the
  role gained `bedrock:InvokeModel` on the embedding model and on inference
  profiles. That grant is now in the notebook's role cell.
- [x] Module 6 does real work rather than skipping every live cell.
  `memory_helpers.load_config()` reached `notebooks/` instead of the repo root, so
  it never found `NEO4J_PASSWORD` and the harness reported a pass on a notebook
  that validated nothing. Confirm the memory nodes are actually written.

### Cleanup

Modules 4 and 5 leave resources running. Nothing tears them down automatically.

- [x] Module 6: run `notebooks/06-neo4j-memory/cleanup_memory.py`.
- [x] Module 5: find its resources by the `WorkshopResource` tag it applies, then
  delete the Runtime, the ECR repository, the CodeBuild project, and the
  execution role.
- [x] Module 4: delete by name. Its notebook does not tag or delete anything, so
  this list is the only record. The 2026-08-20 run created Lambda functions
  `hotel-booking-search-hotel-knowledge` and `hotel-booking-graph-query`, IAM role
  `workshop-hotel-lambda-role`, and secret `neo4j-ws-retrieval`.
- [x] Check for leftovers from the 2026-08-20 run before creating new ones. That
  run was never torn down, so a re-run may reuse or collide with its resources.

The missing teardown path in Module 4 is a genuine gap for participants running
outside a Workshop Studio account, which reclaims the account when the event
ends. Fixing it is out of scope here.

**Done when:** all four rows read `passed` at one commit, the result is added to
`live-validation.md`, and the cleanup checklist is closed.

**Result:** Complete. The Modules 4--5 gate reported 3 passed, 0 failed, and 0
skipped; the Module 6 gate reported 1 passed, 0 failed, and 0 skipped. Cleanup
removed the test graph records and the exact workshop AWS resources without
touching the unrelated supplier Gateway or Runtime. See `live-validation.md`.

This ordered run is sufficient for basic workshop testing. It verifies that the
participant notebooks can create their resources, call their main paths, assert
their expected results, and clean up. It is not a production load, penetration,
disaster-recovery, or long-duration reliability test.

## Constraints that still bind

- The locked Module 2 facts live in `notebooks/workshop/retrieval_setup.py` as
  `REQUIRED_SOURCE_FILES`, `SOURCE_FIXTURES`, `CAIRO_HOTEL_ID`,
  `CHICAGO_QUALIFIER`, and `CHICAGO_EXCLUSION`. The four locked questions and the
  evidence display fields live in `setup/test_module2_notebook_contract.py`.
  Changing any of them means re-running the live acceptance in Item 2.
- `static/neo4j-hotel-graph.dump` is the starting artifact. Rebuild the graph only
  when a readiness check proves the artifact violates the contract.
- `prepare_graph.py` requires `--rebuild` before any whole-graph clear, including
  a clear against an empty graph. `--resume` carries the same destructive intent
  for the checkpoint workflow.
- The workshop intentionally uses a small explicit learner-page inventory.
  Adding a learner page means adding it to `LEARNER_FILES` in
  `setup/test_phase5_content_contract.py`.
- Executed notebooks under `setup/notebook-output/` are local diagnostics and stay
  untracked. Do not publish detailed logs.
- Keep the unrelated working-tree changes intact.

## Risks

- The live run writes to the shared graph. Compare counts before and after.
- The live run reads `.env`. Keep credentials and secret values out of the record.

## Completion

The workshop is releasable when Items 1 through 3 are closed and the offline
suite plus `setup/check_repo.py` pass. Item 4 covers Modules 4 through 6 and is
not a release blocker for the first three modules.
