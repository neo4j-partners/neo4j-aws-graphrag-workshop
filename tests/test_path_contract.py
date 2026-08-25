# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline checks for the workshop's supported notebook launch locations."""

from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS_ROOT = REPO_ROOT / "notebooks"
NOTEBOOKS = (
    NOTEBOOKS_ROOT / "01-build-graph" / "1.1_build_graph.ipynb",
    NOTEBOOKS_ROOT / "02-connected-context" / "2.1_connected_context.ipynb",
    NOTEBOOKS_ROOT
    / "03-grounded-booking-agent"
    / "3.1_grounded_booking_agent.ipynb",
    NOTEBOOKS_ROOT / "04-production-agent" / "4.1_agentcore_gateway.ipynb",
    NOTEBOOKS_ROOT / "05-agentcore-deploy" / "5.1_deploy.ipynb",
    NOTEBOOKS_ROOT / "06-neo4j-memory" / "6.1_neo4j_memory.ipynb",
)


def code_cells(path: Path) -> list[str]:
    """Return normalized code-cell sources from one notebook."""
    document = json.loads(path.read_text(encoding="utf-8"))
    return [
        "".join(cell["source"])
        if isinstance(cell["source"], list)
        else cell["source"]
        for cell in document["cells"]
        if cell["cell_type"] == "code"
    ]


def locator(path: Path):
    """Load only a notebook's locator function, without live dependencies."""
    source = next(
        cell for cell in code_cells(path) if "def locate_notebooks_root" in cell
    )
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "locate_notebooks_root"
    )
    namespace = {"os": os, "Path": Path}
    exec(compile(ast.Module([function], []), str(path), "exec"), namespace)
    return namespace["locate_notebooks_root"]


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda path: path.stem)
def test_notebook_locator_uses_the_same_root_from_supported_launches(
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WORKSHOP_NOTEBOOKS_DIR", raising=False)
    find_root = locator(path)
    for launch_dir in (REPO_ROOT, NOTEBOOKS_ROOT, path.parent):
        monkeypatch.chdir(launch_dir)
        assert find_root() == NOTEBOOKS_ROOT


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda path: path.stem)
def test_notebook_locator_validates_the_override(
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    find_root = locator(path)
    monkeypatch.setenv("WORKSHOP_NOTEBOOKS_DIR", str(NOTEBOOKS_ROOT))
    monkeypatch.chdir(tmp_path)
    assert find_root() == NOTEBOOKS_ROOT

    monkeypatch.setenv("WORKSHOP_NOTEBOOKS_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="must contain the workshop package"):
        find_root()


def test_locator_does_not_require_generated_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A fresh clone needs module folders and workshop code, not data caches."""
    fake_notebooks = tmp_path / "notebooks"
    (fake_notebooks / "workshop").mkdir(parents=True)
    fake_module = fake_notebooks / "03-grounded-booking-agent"
    fake_module.mkdir()
    find_root = locator(NOTEBOOKS[0])

    monkeypatch.delenv("WORKSHOP_NOTEBOOKS_DIR", raising=False)
    for launch_dir in (tmp_path, fake_notebooks, fake_module):
        monkeypatch.chdir(launch_dir)
        assert find_root() == fake_notebooks


def test_module_assets_are_anchored_to_the_located_root() -> None:
    sources = {path.name: "\n".join(code_cells(path)) for path in NOTEBOOKS}
    assert 'MODULE_DIR = NOTEBOOKS_ROOT / "03-grounded-booking-agent"' in sources[
        "3.1_grounded_booking_agent.ipynb"
    ]
    assert 'LAMBDA_SRC = MODULE_DIR / "lambda_tools"' in sources[
        "4.1_agentcore_gateway.ipynb"
    ]
    assert 'DEPLOY_DIR = MODULE_DIR / "runtime_app"' in sources["5.1_deploy.ipynb"]
    assert 'MODULE_DIR = NOTEBOOKS_ROOT / "06-neo4j-memory"' in sources[
        "6.1_neo4j_memory.ipynb"
    ]


def test_held_out_defaults_are_anchored_to_the_helper_file() -> None:
    module_1 = NOTEBOOKS_ROOT / "01-build-graph"
    module_2 = NOTEBOOKS_ROOT / "02-connected-context"
    original_path = list(sys.path)
    try:
        for path in (module_1, module_2):
            sys.path.insert(0, str(path))
        import held_out_documents

        assert held_out_documents.CORPUS_ARCHIVE == module_2 / "hotel-faqs.zip"
        assert held_out_documents.DATA_DIR == module_1 / "data"
    finally:
        sys.path[:] = original_path


def test_prepare_graph_paths_are_anchored_to_the_script() -> None:
    source = (NOTEBOOKS_ROOT / "02-connected-context" / "prepare_graph.py").read_text(
        encoding="utf-8"
    )
    assert "SCRIPT_DIR = Path(__file__).resolve().parent" in source
    assert 'DATA_DIR = SCRIPT_DIR / "data"' in source
    assert 'CORPUS_ZIP = SCRIPT_DIR / "hotel-faqs.zip"' in source
    assert 'load_dotenv(NOTEBOOKS_ROOT / ".env")' in source
    assert 'load_dotenv(REPO_ROOT / ".env")' in source
    assert 'load_dotenv(REPO_ROOT / "CONFIG.txt")' in source
