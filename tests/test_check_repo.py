# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Prove the offline gate fails on the defects it was written for.

`check_repo.py` was probed with throwaway files when it was written. These
tests make that probing permanent, because a gate that stops catching anything
looks exactly like a gate with nothing to catch. Each test builds a two-tree
repository under `tmp_path`, points the module's roots at it, and asserts the
clean version is silent and the defective version is not.

Run them with:

    uv run --with pytest pytest tests/test_check_repo.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import check_repo


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch) -> Path:
    """A minimal notebooks/ and content/ tree with the module roots repointed."""
    notebooks = tmp_path / "notebooks"
    content = tmp_path / "site" / "content"
    (notebooks / "01-build-graph").mkdir(parents=True)
    (content / "01-build-graph").mkdir(parents=True)

    monkeypatch.setattr(check_repo, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_repo, "NOTEBOOKS", notebooks)
    monkeypatch.setattr(check_repo, "CONTENT", content)
    monkeypatch.setattr(check_repo, "SWEPT_TREES", (notebooks, content))
    return tmp_path


def page(fake_repo: Path, body: str, folder: str = "01-build-graph") -> Path:
    """Write a content page into the fake repository and return its path."""
    path = fake_repo / "site" / "content" / folder / "index.en.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Banned patterns
# --------------------------------------------------------------------------


CLEAN_PAGE = """---
title: "Module 1: Build the Graph"
weight: 20
---

Open the notebook and run the cells in order.
"""


def test_a_clean_page_reports_nothing(fake_repo: Path) -> None:
    page(fake_repo, CLEAN_PAGE)
    assert check_repo.banned_patterns_absent() == []


@pytest.mark.parametrize(
    "body",
    [
        "Head to Demo 3 next.",
        "This was Lab 4.",
        "Module 7 covers deployment.",
        "The customer-service-lookup function.",
        "Run the build (20 minutes) and wait.",
        "This is a 30-minute exercise.",
    ],
)
def test_retired_numbering_and_timing_are_caught(fake_repo: Path, body: str) -> None:
    page(fake_repo, CLEAN_PAGE + body)
    assert check_repo.banned_patterns_absent() != []


@pytest.mark.parametrize(
    "body",
    [
        "The graph holds 292 hotels.",
        "All 300 hotel documents are loaded.",
        "A diagram of 300 hotels.",
    ],
)
def test_a_graph_count_in_prose_is_caught(fake_repo: Path, body: str) -> None:
    page(fake_repo, CLEAN_PAGE + body)
    assert check_repo.banned_patterns_absent() != []


def test_a_count_in_a_shared_module_comment_is_allowed(fake_repo: Path) -> None:
    """Counts are banned from what a participant reads, not from engineering."""
    module = fake_repo / "notebooks" / "graph_builder.py"
    module.write_text("# Deletes the 292 documents this build owns.\n", encoding="utf-8")
    assert check_repo.banned_patterns_absent() == []


@pytest.mark.parametrize(
    "retired_name",
    [
        "02-graphrag-fixes-it",
        "02-vector-rag-hallucinates",
        "03-retrieval-patterns",
        "2.1_vector_rag_hallucinates.ipynb",
        "3.1_retrieval_patterns.ipynb",
        "3.2_grounded_booking_agent.ipynb",
    ],
)
def test_a_retired_name_is_caught(fake_repo: Path, retired_name: str) -> None:
    page(fake_repo, CLEAN_PAGE + f"See `{retired_name}`.")
    assert any("retired name" in problem for problem in check_repo.banned_patterns_absent())


# --------------------------------------------------------------------------
# Named paths
# --------------------------------------------------------------------------


def test_a_named_file_that_exists_is_accepted(fake_repo: Path) -> None:
    (fake_repo / "notebooks" / "01-build-graph" / "1.1_build_graph.ipynb").write_text(
        "{}", encoding="utf-8"
    )
    page(fake_repo, CLEAN_PAGE + "Open `notebooks/01-build-graph/1.1_build_graph.ipynb`.")
    assert check_repo.named_paths_exist() == []


def test_a_named_file_that_does_not_exist_is_caught(fake_repo: Path) -> None:
    page(fake_repo, CLEAN_PAGE + "Open `notebooks/01-build-graph/1.9_missing.ipynb`.")
    assert check_repo.named_paths_exist() != []


def test_a_cd_into_a_directory_that_does_not_exist_is_caught(fake_repo: Path) -> None:
    """The phrase is split on whitespace, so `cd cdk/` is two tokens."""
    page(fake_repo, CLEAN_PAGE + "Run `cd cdk/` first.")
    assert check_repo.named_paths_exist() != []


def test_a_url_is_not_treated_as_a_path(fake_repo: Path) -> None:
    page(fake_repo, CLEAN_PAGE + "See `https://neo4j.com/docs/index.html`.")
    assert check_repo.named_paths_exist() == []


# --------------------------------------------------------------------------
# Structure
# --------------------------------------------------------------------------


def test_a_notebook_folder_without_a_page_is_caught(fake_repo: Path) -> None:
    (fake_repo / "notebooks" / "07-orphan").mkdir()
    assert check_repo.module_folders_have_pages() != []


def test_a_module_with_both_trees_is_accepted(fake_repo: Path) -> None:
    assert check_repo.module_folders_have_pages() == []


def test_two_pages_claiming_one_weight_are_caught(fake_repo: Path) -> None:
    page(fake_repo, CLEAN_PAGE)
    page(fake_repo, CLEAN_PAGE, folder="02-connected-context")
    assert check_repo.content_weights_unique() != []


def test_a_page_with_no_weight_is_caught(fake_repo: Path) -> None:
    page(fake_repo, "---\ntitle: \"No weight\"\n---\n")
    assert check_repo.content_weights_unique() != []


def test_a_link_to_a_missing_page_is_caught(fake_repo: Path) -> None:
    page(fake_repo, CLEAN_PAGE + "Head to [Module 9](../09-nowhere/).")
    assert check_repo.content_references_resolve() != []


def test_a_link_to_a_real_page_is_accepted(fake_repo: Path) -> None:
    page(fake_repo, CLEAN_PAGE + "Head to [Setup](../01-build-graph/).")
    assert check_repo.content_references_resolve() == []


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def notebook(fake_repo: Path, source: str) -> None:
    """Write a one-cell notebook into the fake repository's Module 1 folder."""
    path = fake_repo / "notebooks" / "01-build-graph" / "1.1_probe.ipynb"
    cell = {"cell_type": "code", "source": [source], "metadata": {}, "outputs": []}
    path.write_text(json.dumps({"cells": [cell]}), encoding="utf-8")


def test_a_parseable_cell_is_accepted(fake_repo: Path) -> None:
    notebook(fake_repo, "import os\nprint(os.getcwd())")
    assert check_repo.notebook_cells_parse() == []


def test_a_shell_escape_cell_is_not_treated_as_python(fake_repo: Path) -> None:
    notebook(fake_repo, "!uv pip install boto3")
    assert check_repo.notebook_cells_parse() == []


def test_a_top_level_await_cell_is_accepted(fake_repo: Path) -> None:
    notebook(fake_repo, "result = await pipeline.run_async()")
    assert check_repo.notebook_cells_parse() == []


def test_an_unparseable_cell_is_caught(fake_repo: Path) -> None:
    notebook(fake_repo, "def broken(:\n    pass")
    assert check_repo.notebook_cells_parse() != []


def test_a_python_file_that_does_not_compile_is_caught(fake_repo: Path) -> None:
    (fake_repo / "notebooks" / "broken.py").write_text("def f(:\n", encoding="utf-8")
    assert check_repo.python_files_compile() != []


# --------------------------------------------------------------------------
# RETIRED_NAMES / BANNED_PATTERNS staleness
# --------------------------------------------------------------------------
#
# Both lists are maintained by hand, unlike the module registry in
# `run_notebooks.py`, which `test_every_module_with_a_notebook_folder_is_registered`
# cross-checks against the notebook folders actually on disk. These two tests
# apply the same idea here: they read the real `notebooks/` tree (not
# `fake_repo`), because what they are proving stale is the list itself, not
# any behavior of `banned_patterns_absent()`.


def _current_module_folders() -> set[str]:
    return {path.name for path in check_repo.NOTEBOOKS.glob("[0-9]*") if path.is_dir()}


def test_retired_names_do_not_shadow_a_current_module_folder() -> None:
    """A retired name that now names a live folder would ban linking to it."""
    stale = _current_module_folders() & set(check_repo.RETIRED_NAMES)
    assert stale == set(), (
        f"RETIRED_NAMES still bans current module folder(s): {sorted(stale)}. "
        "Remove the stale entry from RETIRED_NAMES in check_repo.py."
    )


def test_banned_module_number_pattern_stays_ahead_of_the_current_module_count() -> None:
    """The retired 'Module 7/8' pattern must not start flagging a real module."""
    highest = max(int(name[:2]) for name in _current_module_folders())
    for number in range(1, highest + 1):
        text = f"Module {number} covers something."
        flagged = [
            reason
            for pattern, reason in check_repo.BANNED_PATTERNS
            if pattern.search(text)
        ]
        assert flagged == [], (
            f"BANNED_PATTERNS flags current Module {number}: {flagged}. "
            "Update the retired-numbering pattern in check_repo.py to stay "
            "ahead of the current module count."
        )
