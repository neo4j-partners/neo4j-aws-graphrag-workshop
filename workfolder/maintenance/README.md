# Maintainer tools

These local-only tools are intentionally outside `setup/`. They are useful for
maintaining workshop content or publishing graph artifacts, not for workshop
participants. Run commands from the repository root unless a script says
otherwise.

## Quick start

For a fast, offline content review:

```bash
python workfolder/maintenance/quality/check_repo.py
```

For the local maintenance test suite:

```bash
notebooks/.venv/bin/python -m pytest workfolder/tests -q
```

## Importance and frequency

### Use often

1. `quality/check_repo.py` — **high importance; after any notebook or content
   edit.** Fast offline checks for parse errors, broken links, image parity, and
   retired workshop terminology.

2. `quality/run_notebooks.py` — **high importance; before handing off a
   changed module.** Executes selected notebooks. It writes to Neo4j, and
   Modules 4 and 5 create AWS resources only with `--include-deploy`.

3. `quality/run_notebook_smoke.py` — **high importance; before a release or
   when retaining execution evidence.** A restricted wrapper around the
   notebook runner that excludes deployment notebooks.

### Use only when preparing or validating a graph release

4. `release/validate_prebuilt_candidate.sh` — **high importance; each time a
   prebuilt dump is proposed.** Restores the candidate locally and runs both
   artifact validators. This is the normal release gate.

5. `release/build_prebuilt_graph.sh` — **high importance; rarely.** Builds a
   fresh prebuilt dump with Docker, AWS credentials, and Bedrock access. It
   writes a candidate and provenance manifest for review, never the shipped
   dump directly.

6. `release/run_additive_validation.sh` — **high importance; rarely, after a
   candidate build.** Validates that the five Module 1 held-out hotels can be
   added correctly in a disposable local Neo4j instance.

7. `release/load_held_out_hotels.py` — **medium importance; only when a
   restored graph needs Modules 2–6 without running Module 1.** Uses the same
   additive build path as the Module 1 notebook.

### Helpers normally called by the release wrappers

8. `release/validate_graph_amenities.py` — validates source-to-amenity graph
   reconciliation. Called by both release validation wrappers.

9. `release/validate_prebuilt_candidate.py` — validates prebuilt graph shape
   and fixed release invariants. Called by `validate_prebuilt_candidate.sh`.

10. `release/run_additive_validation.py` — records and validates the
    before-and-after additive graph state. Called by its shell wrapper.

11. `release/write_prebuilt_manifest.py` — records candidate provenance.
    Called by `build_prebuilt_graph.sh`; do not run it independently unless
    recovering a build manifest.
