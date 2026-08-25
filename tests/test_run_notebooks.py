# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Prove the notebook runner reports a failure, not just a success.

The runner's whole value is that a broken notebook comes back red. So the two
tests that matter here execute a real kernel against a synthetic notebook: one
that succeeds and one that raises, asserting PASS and FAIL respectively. The
rest cover selection, which is what decides whether a notebook gets run at all
and therefore what decides whether a green run means anything.

Run them with:

    uv run --with pytest --with nbconvert --with nbformat --with ipykernel \
        pytest tests/test_run_notebooks.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import run_notebooks

nbformat = pytest.importorskip("nbformat", reason="run_notebooks needs nbformat")
pytest.importorskip("nbconvert", reason="run_notebooks needs nbconvert")
pytest.importorskip("ipykernel", reason="run_notebooks needs ipykernel")


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------


def test_registry_is_in_module_order() -> None:
    """Run order is registry order, and Module 1 writes what Module 2 reads."""
    modules = [notebook.module for notebook in run_notebooks.NOTEBOOKS_REGISTRY]
    assert modules == sorted(modules)


def test_every_registered_notebook_lives_under_its_module_folder() -> None:
    for notebook in run_notebooks.NOTEBOOKS_REGISTRY:
        folder = notebook.path.parent.name
        assert folder.startswith(f"0{notebook.module}-"), notebook.path


def test_every_module_with_a_notebook_folder_is_registered() -> None:
    """A new module folder that nobody registered is a module nobody runs."""
    registered = {notebook.path.parent.name for notebook in run_notebooks.NOTEBOOKS_REGISTRY}
    on_disk = {path.name for path in run_notebooks.NOTEBOOKS.glob("[0-9]*") if path.is_dir()}
    assert on_disk - registered == set()


# --------------------------------------------------------------------------
# Module selection
# --------------------------------------------------------------------------


def test_no_selection_runs_every_module() -> None:
    assert run_notebooks.parse_modules(None) == set(run_notebooks.KNOWN_MODULES)


def test_a_single_module_is_selected() -> None:
    assert run_notebooks.parse_modules("3") == {"3"}


def test_a_list_is_selected() -> None:
    assert run_notebooks.parse_modules("1,3,6") == {"1", "3", "6"}


def test_a_range_is_selected() -> None:
    assert run_notebooks.parse_modules("1-3") == {"1", "2", "3"}


@pytest.mark.parametrize("spec", ["9", "1-9", "two", "", ","])
def test_an_unusable_selection_is_refused(spec: str) -> None:
    with pytest.raises(ValueError):
        run_notebooks.parse_modules(spec)


def test_a_backwards_range_is_refused() -> None:
    with pytest.raises(ValueError, match="start exceeds end"):
        run_notebooks.parse_modules("3-1")


# --------------------------------------------------------------------------
# What gets skipped, and why
# --------------------------------------------------------------------------


def test_resource_creating_notebooks_are_opt_in() -> None:
    plan = run_notebooks.select_notebooks({"4", "5"}, include_deploy=False)
    assert plan
    assert all(reason == "creates AWS resources; pass --include-deploy" for _, reason in plan)


def test_include_deploy_selects_them() -> None:
    plan = run_notebooks.select_notebooks({"4", "5"}, include_deploy=True)
    assert plan
    assert all(reason is None for _, reason in plan)


def test_a_registered_notebook_that_moved_is_a_skip_not_a_failure(monkeypatch) -> None:
    """A module being renamed by its owner must not turn the run red."""
    ghost = run_notebooks.Notebook("2", run_notebooks.NOTEBOOKS / "02-x" / "gone.ipynb")
    monkeypatch.setattr(run_notebooks, "NOTEBOOKS_REGISTRY", (ghost,))
    plan = run_notebooks.select_notebooks({"2"}, include_deploy=False)
    assert plan == [(ghost, "notebook file not found")]


# --------------------------------------------------------------------------
# Install magics
# --------------------------------------------------------------------------


def test_install_magics_are_commented_out() -> None:
    document = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell("%pip install requests\nimport os"),
            nbformat.v4.new_code_cell("!uv pip install boto3"),
            nbformat.v4.new_markdown_cell("%pip install not-code"),
        ]
    )
    assert run_notebooks.neutralize_install_magics(document) == 2
    assert document.cells[0].source.startswith("# [run_notebooks] disabled:")
    assert "import os" in document.cells[0].source
    assert document.cells[1].source.startswith("# [run_notebooks] disabled:")
    assert document.cells[2].source == "%pip install not-code"


def test_ordinary_code_is_left_alone() -> None:
    document = nbformat.v4.new_notebook(
        cells=[nbformat.v4.new_code_cell("pip_version = 1\nprint(pip_version)")]
    )
    assert run_notebooks.neutralize_install_magics(document) == 0


# --------------------------------------------------------------------------
# Execution, in both directions
# --------------------------------------------------------------------------


def execute(monkeypatch, source: str) -> run_notebooks.Result:
    """Run a one-cell notebook through the real kernel and return its result."""
    with tempfile.TemporaryDirectory(prefix="run_notebooks_test_") as raw:
        work_dir = Path(raw).resolve()
        # The runner reports paths relative to the repository root, so the
        # probe notebook needs a root it actually sits under.
        monkeypatch.setattr(run_notebooks, "REPO_ROOT", work_dir)
        notebook_path = work_dir / "probe.ipynb"
        document = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell(source)])
        nbformat.write(document, notebook_path)
        registered = run_notebooks.Notebook("0", notebook_path)
        with run_notebooks.temporary_kernel(work_dir / "jupyter"):
            return run_notebooks.run_notebook(
                registered, work_dir / "output", timeout=120
            )


def test_a_working_notebook_passes(monkeypatch) -> None:
    result = execute(monkeypatch, "assert 2 + 2 == 4\nprint('ok')")
    assert result.status == "PASS"


def test_a_broken_notebook_fails_with_the_reason(monkeypatch) -> None:
    """The test the runner exists for: a cell that raises comes back red."""
    result = execute(monkeypatch, "raise ValueError('the helper was renamed')")
    assert result.status == "FAIL"
    assert "the helper was renamed" in result.detail


def test_execution_directory_is_the_notebook_folder(
    monkeypatch, tmp_path: Path
) -> None:
    """The runner passes the module folder to nbconvert explicitly."""
    import nbconvert.preprocessors

    module_dir = tmp_path / "03-probe"
    module_dir.mkdir()
    notebook_path = module_dir / "probe.ipynb"
    nbformat.write(nbformat.v4.new_notebook(), notebook_path)
    notebook = run_notebooks.Notebook("3", notebook_path)
    observed = {}

    class RecordingExecutor:
        def __init__(self, **kwargs):
            pass

        def preprocess(self, document, resources):
            observed.update(resources)

    monkeypatch.setattr(
        nbconvert.preprocessors, "ExecutePreprocessor", RecordingExecutor
    )
    monkeypatch.setattr(run_notebooks, "REPO_ROOT", tmp_path)

    result = run_notebooks.run_notebook(notebook, tmp_path / "output", 60)

    assert result.status == "PASS"
    assert observed == {"metadata": {"path": str(module_dir)}}


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------


def test_deploy_and_keep_output_are_opt_in() -> None:
    parser = run_notebooks.build_parser()
    defaults = parser.parse_args([])
    assert defaults.include_deploy is False
    assert defaults.keep_output is False
    assert defaults.modules is None
    assert parser.parse_args(["--include-deploy"]).include_deploy is True
