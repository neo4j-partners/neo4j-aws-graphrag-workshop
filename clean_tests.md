# Test cleanup checklist

## Brief overview

The test suite has 24 files, 282 collected tests, and about 4,200 lines. A large share of those lines check the words and shape of notebooks, markdown pages, and one SVG file. Those tests break every time someone edits a sentence, renames a variable, or reorders a cell. No GitHub workflow runs pytest today, so these tests only run locally and they only cost author time.

**Suite status as of 2026-08-26: 278 passed, 4 failed.** That is the count on CPython 3.10.14, the Vocareum interpreter, which now collects and runs the same 282 tests as a 3.13 interpreter does. All four failures are in `tests/test_module3_availability_assertion.py`, which is on the delete list below and is intentionally left red until Phase 3. Every other file passes. Nothing on this checklist has been executed yet: all five delete-candidate files still exist, and every individual test named below is still present. The counts and per-file statuses here are current; the checkboxes are all still open.

The rule for this cleanup is one question per test. **Does the test open a notebook, a markdown page, or an SVG and assert what words or structure it contains?** Delete it. **Does the test call a script or a helper function and check what it returns?** Keep it.

Once a notebook or a page has been written and run once, that is enough proof. It does not need a permanent word check.

---

## Delete these whole files

- [ ] **tests/test_module2_notebook_contract.py** (12 tests, all passing): Delete the file. It pins exact question strings, variable names, cell order, and the number of times `report_problems(` appears. Every edit to the notebook breaks it. `test_the_notebook_carries_no_inline_assertions` is the clearest example. It is a style rule enforced as a test.

- [ ] **tests/test_phase5_content_contract.py** (6 tests, all passing): Delete the file. It greps README files, site pages, and notebook markdown for phrases such as `"retrieval comparison"` and `"reflect the facts that extraction placed"`. Editing prose breaks the build.

- [ ] **tests/test_module2_diagrams.py** (4 tests, all passing): Delete the file. It parses an SVG and asserts the label text inside eight named groups. Redrawing the diagram breaks it.

- [ ] **tests/test_bedrock_model_contract.py** (5 tests, all passing): Delete the file. It greps four files for a model ID string and greps `graph_builder.py` for one exact `print()` line. A model bump means editing the test and the code in lockstep.

- [ ] **tests/test_module3_availability_assertion.py** (4 tests, all failing): Delete the file. It finds a notebook cell by searching for a string, then runs that cell with `exec`. Moving or rewording the cell breaks it. That is exactly what happened. The Module 3 notebook no longer contains a `fabricated_availability_claims` cell, because phrase grading was replaced with reading the returned verdict, so all four tests now fail with `StopIteration` at the `next(...)` lookup. This is the suite's only red file and it is left red on purpose. It retires in Phase 3 of `full-agent-fix.md`. Do not repair it.

---

## Delete part of these files

`tests/test_module1_demo_cleanup.py` still holds both tests and both pass.

- [ ] **tests/test_module1_demo_cleanup.py** → `test_demo_uses_reserved_metadata_and_guaranteed_scoped_cleanup`: Delete this test. It asserts six exact source lines inside a notebook cell.

- [ ] **tests/test_module1_demo_cleanup.py** → `test_scoped_demo_cleanup_preserves_participant_data_after_success_and_failure`: Keep this test. It calls `graph_builder.clear_document` with a fake driver and checks the result.

---

## Trim this file

`tests/test_module2_checks.py` tests real helper functions, so keep the file. It collects 19 tests today and all of them pass, and every test named below is still present and untrimmed. It currently asserts exact error message text, and that is the brittle part. Change each test to check that a clean input returns no problems and a broken input returns at least one problem. Stop asserting the wording of the message.

- [ ] **test_the_right_source_without_its_terms_is_still_a_defect**: Delete this test, as called out by the user. The case it covers is already covered by the missing-source test.
- [ ] **test_a_source_missing_from_the_results_is_named_with_what_was_returned**: Keep the test. Assert `len(problems) == 1` and drop the two filename checks.
- [ ] **test_extra_terms_are_checked_without_being_pinned_to_the_fixture**: Keep the test. Assert the problem list is non-empty and drop the exact string compare.
- [ ] **test_a_duplicated_source_is_reported_rather_than_silently_first_wins**: Keep the test. Assert one problem and drop the `"expected one graph record for ..."` string.
- [ ] **test_a_wrong_locked_field_names_both_the_observed_and_expected_value**: Keep the test. Assert one problem and drop the three `repr()` checks.
- [ ] **test_a_severed_amenity_relationship_names_the_missing_amenity**: Keep the test. Assert one problem and drop the exact string.
- [ ] **test_an_unscored_record_is_a_defect**: Keep the test. Assert one problem and drop the exact string.
- [ ] **test_a_field_with_no_provenance_path_is_named**: Keep the test. Assert one problem and drop the exact string.
- [ ] **test_no_problems_prints_one_pass_line**: Delete this test. It asserts the exact text of a print statement.

---

## Keep these files as they are

These files call scripts and library functions and check behavior. They do not read notebook prose. Every file in this section passes today.

- [ ] **tests/test_check_repo.py** (34 tests, passing): Keep. It builds a fake repo and proves the repo gate catches real defects.
- [ ] **tests/test_verify.py** (30 tests, passing): Keep. It proves each setup check passes on good input and fails on bad input.
- [ ] **tests/test_run_notebooks.py** (22 tests, passing): Keep. It tests the notebook runner script.
- [ ] **tests/test_path_contract.py** (16 tests, passing): Keep. It proves notebooks find their files from every supported launch location.
- [ ] **tests/test_amenities.py** (19 tests, passing): Keep. It tests the amenity parser and materializer.
- [ ] **tests/test_graph_builder_amenities.py** (17 tests, passing): Keep. It tests the build pipeline and its readiness gates.
- [ ] **tests/test_graph_builder_concurrency.py** (4 tests, passing): Keep. It tests parallel ingest behavior.
- [ ] **tests/test_graph_builder_resume.py** (4 tests, passing): Keep. It tests resume and provenance logic.
- [ ] **tests/test_module2_fixtures.py** (11 tests, passing): Keep. It tests fixture selection and readiness functions with fake records.
- [ ] **tests/test_module4_secret_recovery.py** (1 test, passing): Keep. It tests secret rotation with a fake client.
- [ ] **tests/test_prebuilt_manifest.py** (4 tests, passing): Keep. It tests manifest capture and recovery.
- [ ] **tests/test_prepare_graph_safety.py** (5 tests, passing): Keep. It stops an accidental graph wipe.
- [ ] **tests/test_build_prebuilt_script.py** (4 tests, passing): Keep. It tests the prebuilt build script.
- [ ] **tests/test_validate_prebuilt_candidate.py** (4 tests, passing): Keep. It tests the release validator.
- [ ] **tests/test_release_workflows.py** (6 tests, passing): Keep. It tests the release scripts.
- [ ] **tests/test_agent_tools.py** (36 tests, passing): Keep. New since this checklist was written and not previously tracked here. It drives both read tools and the shared grounding contract with a stubbed retrieval function, with no Neo4j, no AWS, and no network. It reads no notebook, no markdown, and no SVG, so it sits on the keep side of this document's rule.

---

## What the deletions cost

Nothing structural is lost. `tools/quality/check_repo.py` already parses every notebook code cell and every Python file, so notebook syntax stays covered after `test_notebook_code_cells_parse` is deleted. The Module 2 notebook runs live in CI-style smoke runs through `run_notebooks.py`, and its own `report_problems` calls fail the run when the graph is wrong. That live run is the real gate. The word checks were a second copy of it.

## Result

None of this has been done yet. Deleting the five files removes about 590 lines and 31 of the 282 collected tests, and it returns the suite to green because the only four failures live in `test_module3_availability_assertion.py`. Trimming `test_module2_checks.py` and `test_module1_demo_cleanup.py` removes about 60 more lines. The suite drops from 23 files to 18 and keeps every test that proves a script or a function works.
