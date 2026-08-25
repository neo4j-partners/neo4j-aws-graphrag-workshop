"""Contracts for the optional Module 1 unpinned extraction demo."""

from __future__ import annotations

import json
import sys
from pathlib import Path


CONNECTED_CONTEXT = (
    Path(__file__).resolve().parents[2] / "notebooks" / "02-connected-context"
)
sys.path.insert(0, str(CONNECTED_CONTEXT))

import graph_builder  # noqa: E402 - script module path is added above


NOTEBOOK = (
    Path(__file__).resolve().parents[2]
    / "notebooks"
    / "01-build-graph"
    / "1.1_build_graph.ipynb"
)
DEMO_SOURCE = "demo-unpinned-schema-comparison.txt"


def _demo_cell() -> str:
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    return next(
        "".join(cell["source"])
        if isinstance(cell["source"], list)
        else cell["source"]
        for cell in cells
        if DEMO_SOURCE
        in (
            "".join(cell["source"])
            if isinstance(cell["source"], list)
            else cell["source"]
        )
    )


def test_demo_uses_reserved_metadata_and_guaranteed_scoped_cleanup() -> None:
    source = _demo_cell()

    assert f'UNPINNED_DEMO_SOURCE_FILENAME = "{DEMO_SOURCE}"' in source
    assert "document_metadata={" in source
    assert '"source_filename": UNPINNED_DEMO_SOURCE_FILENAME' in source
    assert "finally:" in source
    assert "clear_document(driver, UNPINNED_DEMO_SOURCE_FILENAME)" in source
    assert "clear_document(driver, sample.name)" not in source


def test_scoped_demo_cleanup_preserves_participant_data_after_success_and_failure(
) -> None:
    participant_source = "hotel-tokyo-002.txt"
    graph = {participant_source: "Participant Hotel"}

    class FakeTransaction:
        def run(self, _query: str, *, filename: str):
            graph.pop(filename, None)
            return type("Result", (), {"consume": lambda self: None})()

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute_write(self, work):
            return work(FakeTransaction())

    class FakeDriver:
        def session(self, *, database: str):
            assert database
            return FakeSession()

    driver = FakeDriver()
    for demo_hotel in ("Successful Demo Hotel", "Partial Failure Hotel"):
        graph[DEMO_SOURCE] = demo_hotel

        graph_builder.clear_document(driver, DEMO_SOURCE)

        assert graph == {participant_source: "Participant Hotel"}
