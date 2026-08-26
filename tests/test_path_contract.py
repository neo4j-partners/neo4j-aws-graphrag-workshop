# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline checks for the workshop's supported notebook launch locations.

The notebooks no longer carry their own copy of this logic. They open with an
identical shim that finds `notebooks/`, then hand the rest to
`workshop.bootstrap.start_module`, so the launch-location contract is tested
against that module and the notebooks are checked for using it.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

from workshop import bootstrap


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS_ROOT = REPO_ROOT / "notebooks"
NOTEBOOKS = (
    NOTEBOOKS_ROOT / "01-build-graph" / "1.0_verify_environment.ipynb",
    NOTEBOOKS_ROOT / "01-build-graph" / "1.1_build_graph.ipynb",
    NOTEBOOKS_ROOT / "02-connected-context" / "2.1_connected_context.ipynb",
    NOTEBOOKS_ROOT
    / "03-grounded-booking-agent"
    / "3.1_grounded_booking_agent.ipynb",
    NOTEBOOKS_ROOT / "04-production-agent" / "4.1_agentcore_gateway.ipynb",
    NOTEBOOKS_ROOT / "05-agentcore-deploy" / "5.1_deploy.ipynb",
    NOTEBOOKS_ROOT / "06-neo4j-memory" / "6.1_neo4j_memory.ipynb",
)
MODULE_FOLDER = {
    "1.0_verify_environment.ipynb": "01-build-graph",
    "1.1_build_graph.ipynb": "01-build-graph",
    "2.1_connected_context.ipynb": "02-connected-context",
    "3.1_grounded_booking_agent.ipynb": "03-grounded-booking-agent",
    "4.1_agentcore_gateway.ipynb": "04-production-agent",
    "5.1_deploy.ipynb": "05-agentcore-deploy",
    "6.1_neo4j_memory.ipynb": "06-neo4j-memory",
}
SHIM_LAST_LINE = "from workshop.bootstrap import start_module"


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


def opening_cell(path: Path) -> str:
    """Return the cell that puts the workshop package on the import path."""
    return next(cell for cell in code_cells(path) if SHIM_LAST_LINE in cell)


def shim(path: Path) -> str:
    """Return one notebook's bootstrap shim, up to the bootstrap import."""
    cell = opening_cell(path)
    return cell[: cell.index(SHIM_LAST_LINE) + len(SHIM_LAST_LINE)]


@pytest.fixture
def restore_sys_path():
    """Undo the import-path edits `start_module` makes."""
    original = list(sys.path)
    yield
    sys.path[:] = original


def test_locator_returns_the_same_root_from_supported_launches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WORKSHOP_NOTEBOOKS_DIR", raising=False)
    for launch_dir in (REPO_ROOT, NOTEBOOKS_ROOT, *(path.parent for path in NOTEBOOKS)):
        monkeypatch.chdir(launch_dir)
        assert bootstrap.locate_notebooks_root() == NOTEBOOKS_ROOT


def test_locator_validates_the_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("WORKSHOP_NOTEBOOKS_DIR", str(NOTEBOOKS_ROOT))
    monkeypatch.chdir(tmp_path)
    assert bootstrap.locate_notebooks_root() == NOTEBOOKS_ROOT

    monkeypatch.setenv("WORKSHOP_NOTEBOOKS_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="must contain the workshop package"):
        bootstrap.locate_notebooks_root()


def test_locator_does_not_require_generated_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A fresh clone needs module folders and workshop code, not data caches."""
    fake_notebooks = tmp_path / "notebooks"
    (fake_notebooks / "workshop").mkdir(parents=True)
    fake_module = fake_notebooks / "03-grounded-booking-agent"
    fake_module.mkdir()

    monkeypatch.delenv("WORKSHOP_NOTEBOOKS_DIR", raising=False)
    for launch_dir in (tmp_path, fake_notebooks, fake_module):
        monkeypatch.chdir(launch_dir)
        assert bootstrap.locate_notebooks_root() == fake_notebooks


@pytest.mark.parametrize(
    "path", NOTEBOOKS, ids=lambda path: path.stem
)
def test_start_module_returns_the_paths_each_notebook_names(
    path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restore_sys_path: None,
) -> None:
    monkeypatch.delenv("WORKSHOP_NOTEBOOKS_DIR", raising=False)
    monkeypatch.chdir(path.parent)
    paths = bootstrap.start_module(
        MODULE_FOLDER[path.name], load_env=False, quiet_logs=False
    )
    assert paths.notebooks_root == NOTEBOOKS_ROOT
    assert paths.repo_root == REPO_ROOT
    assert paths.module_dir == NOTEBOOKS_ROOT / MODULE_FOLDER[path.name]
    assert str(paths.module_dir) in sys.path
    assert str(NOTEBOOKS_ROOT) in sys.path


def test_start_module_searches_extra_directories_first(
    monkeypatch: pytest.MonkeyPatch,
    restore_sys_path: None,
) -> None:
    """Module 1 imports `graph_builder` from `02-connected-context`."""
    monkeypatch.delenv("WORKSHOP_NOTEBOOKS_DIR", raising=False)
    monkeypatch.chdir(NOTEBOOKS_ROOT)
    sys.path[:] = [entry for entry in sys.path if "notebooks" not in entry]
    bootstrap.start_module(
        "01-build-graph",
        extra_import_dirs=("02-connected-context",),
        load_env=False,
        quiet_logs=False,
    )
    order = [
        sys.path.index(str(NOTEBOOKS_ROOT / name))
        for name in ("02-connected-context", "01-build-graph")
    ]
    assert order == sorted(order)
    assert sys.path.index(str(NOTEBOOKS_ROOT)) > max(order)


def test_start_module_rejects_a_folder_that_is_not_there(
    monkeypatch: pytest.MonkeyPatch,
    restore_sys_path: None,
) -> None:
    monkeypatch.delenv("WORKSHOP_NOTEBOOKS_DIR", raising=False)
    monkeypatch.chdir(NOTEBOOKS_ROOT)
    with pytest.raises(RuntimeError, match="No module folder named 07-nothing"):
        bootstrap.start_module("07-nothing", load_env=False, quiet_logs=False)


@pytest.mark.parametrize(
    "launch", ("repo_root", "notebooks_root", "module_dir"), ids=str
)
def test_the_shim_finds_the_package_from_every_supported_launch(
    launch: str,
    monkeypatch: pytest.MonkeyPatch,
    restore_sys_path: None,
) -> None:
    """Run the notebooks' own opening lines, not just read them."""
    notebook = NOTEBOOKS_ROOT / "03-grounded-booking-agent"
    launch_dir = {
        "repo_root": REPO_ROOT,
        "notebooks_root": NOTEBOOKS_ROOT,
        "module_dir": notebook,
    }[launch]

    monkeypatch.delenv("WORKSHOP_NOTEBOOKS_DIR", raising=False)
    monkeypatch.chdir(launch_dir)
    sys.path[:] = [entry for entry in sys.path if "notebooks" not in entry]

    namespace: dict[str, object] = {}
    exec(shim(NOTEBOOKS[0]), namespace)

    assert sys.path[0] == str(NOTEBOOKS_ROOT)
    assert namespace["start_module"] is bootstrap.start_module


def test_starting_a_module_does_not_import_the_strands_sdk(
    monkeypatch: pytest.MonkeyPatch,
    restore_sys_path: None,
) -> None:
    """Module 1.0 runs before anything is installed; Module 6 has no Strands."""
    monkeypatch.delenv("WORKSHOP_NOTEBOOKS_DIR", raising=False)
    monkeypatch.chdir(NOTEBOOKS_ROOT)
    monkeypatch.setitem(sys.modules, "workshop.workshop_utils", None)
    monkeypatch.setitem(sys.modules, "strands", None)

    bootstrap.start_module("06-neo4j-memory", load_env=False)

    assert logging.getLogger("botocore").level == logging.WARNING


def test_every_notebook_opens_with_the_same_shim() -> None:
    shims = {path.name: shim(path) for path in NOTEBOOKS}
    assert len(set(shims.values())) == 1, "the bootstrap shim has drifted"
    assert "workshop" in next(iter(shims.values()))


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda path: path.stem)
def test_each_notebook_starts_its_own_module(path: Path) -> None:
    assert f'start_module(\n    "{MODULE_FOLDER[path.name]}"' in opening_cell(
        path
    ) or f'start_module("{MODULE_FOLDER[path.name]}")' in opening_cell(path)


def test_module_1_notebooks_pass_their_own_options() -> None:
    build_graph = opening_cell(
        NOTEBOOKS_ROOT / "01-build-graph" / "1.1_build_graph.ipynb"
    )
    assert 'extra_import_dirs=("02-connected-context",)' in build_graph

    verify = opening_cell(
        NOTEBOOKS_ROOT / "01-build-graph" / "1.0_verify_environment.ipynb"
    )
    assert "load_env=False" in verify
    assert "load_environment_files(NOTEBOOKS_ROOT, REPO_ROOT)" in verify


def test_module_assets_are_anchored_to_the_located_root() -> None:
    sources = {path.name: "\n".join(code_cells(path)) for path in NOTEBOOKS}
    assert 'LAMBDA_SRC = MODULE_DIR / "lambda_tools"' in sources[
        "4.1_agentcore_gateway.ipynb"
    ]
    assert 'DEPLOY_DIR = MODULE_DIR / "runtime_app"' in sources["5.1_deploy.ipynb"]


def test_notebooks_no_longer_carry_their_own_setup() -> None:
    """The duplicated locator and dotenv calls belong to `workshop.bootstrap`."""
    for path in NOTEBOOKS:
        source = "\n".join(code_cells(path))
        assert "def locate_notebooks_root" not in source, path.name
        if path.name != "1.0_verify_environment.ipynb":
            assert "load_dotenv(" not in source, path.name


def test_held_out_defaults_are_anchored_to_the_helper_file() -> None:
    module_1 = NOTEBOOKS_ROOT / "01-build-graph"
    module_2 = NOTEBOOKS_ROOT / "02-connected-context"
    original_path = list(sys.path)
    try:
        for path in (module_1, module_2):
            sys.path.insert(0, str(path))
        import held_out_documents

        assert (
            held_out_documents.CORPUS_ARCHIVE
            == NOTEBOOKS_ROOT / "shared" / "hotel-faqs.zip"
        )
        assert held_out_documents.DATA_DIR == module_1 / "data"
    finally:
        sys.path[:] = original_path


def test_prepare_graph_paths_are_anchored_to_the_script() -> None:
    source = (NOTEBOOKS_ROOT / "02-connected-context" / "prepare_graph.py").read_text(
        encoding="utf-8"
    )
    assert "SCRIPT_DIR = Path(__file__).resolve().parent" in source
    assert 'DATA_DIR = SCRIPT_DIR / "data"' in source
    assert 'CORPUS_ZIP = NOTEBOOKS_ROOT / "shared" / "hotel-faqs.zip"' in source
    assert 'load_dotenv(NOTEBOOKS_ROOT / ".env")' in source
    assert 'load_dotenv(REPO_ROOT / ".env")' in source
    assert 'load_dotenv(REPO_ROOT / "CONFIG.txt")' in source
