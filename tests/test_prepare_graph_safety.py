"""Offline safety regressions for the destructive graph preparation wrapper."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

CONNECTED_CONTEXT = (
    Path(__file__).resolve().parents[1] / "notebooks" / "02-connected-context"
)
sys.path.insert(0, str(CONNECTED_CONTEXT))

import prepare_graph


def _arguments(**overrides: object) -> Namespace:
    values = {
        "mode": "lite",
        "check_only": False,
        "rebuild": False,
        "resume": False,
    }
    values.update(overrides)
    return Namespace(**values)


def _patch_main_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    arguments: Namespace,
    graph_counts: tuple[int, int, dict[str, int], dict[str, int]],
    readiness_problems: list[str],
) -> tuple[Mock, AsyncMock]:
    driver = Mock()
    run_build = AsyncMock(return_value=0)
    monkeypatch.setattr(prepare_graph, "parse_args", Mock(return_value=arguments))
    monkeypatch.setattr(prepare_graph, "ensure_corpus_extracted", Mock())
    monkeypatch.setattr(
        prepare_graph,
        "selected_paths",
        Mock(return_value=[Path("one.txt"), Path("two.txt")]),
    )
    monkeypatch.setattr(prepare_graph, "connect", Mock(return_value=driver))
    monkeypatch.setattr(prepare_graph, "verify_retrieval_indexes", Mock())
    monkeypatch.setattr(prepare_graph, "ensure_retrieval_indexes", Mock())
    monkeypatch.setattr(
        prepare_graph, "graph_counts", Mock(return_value=graph_counts)
    )
    monkeypatch.setattr(
        prepare_graph,
        "report_readiness",
        Mock(return_value=readiness_problems),
    )
    monkeypatch.setattr(
        prepare_graph,
        "booking_agent_problems",
        Mock(return_value=[]),
    )
    monkeypatch.setattr(prepare_graph, "report", Mock())
    monkeypatch.setattr(prepare_graph, "run_build", run_build)
    monkeypatch.setattr(
        prepare_graph, "seed_booking_agent_fixtures", Mock(return_value=0)
    )
    return driver, run_build


@pytest.mark.parametrize("check_only", [False, True])
def test_incomplete_populated_graph_never_builds_without_explicit_intent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    check_only: bool,
) -> None:
    driver, run_build = _patch_main_dependencies(
        monkeypatch,
        arguments=_arguments(check_only=check_only),
        graph_counts=(1, 1, {"Hotel": 1}, {}),
        readiness_problems=["document count is 1, expected 2"],
    )

    assert prepare_graph.main() == 1

    run_build.assert_not_awaited()
    prepare_graph.ensure_retrieval_indexes.assert_not_called()
    prepare_graph.booking_agent_problems.assert_called_once_with(
        driver, apply_fixtures=False
    )
    output = capsys.readouterr().out
    assert "no graph data was changed" in output
    assert "1 Documents, 1 Chunks, 1 Hotels" in output
    assert "Expected 2 of each" in output
    driver.close.assert_called_once_with()


def test_empty_graph_requires_rebuild_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, run_build = _patch_main_dependencies(
        monkeypatch,
        arguments=_arguments(),
        graph_counts=(0, 0, {}, {}),
        readiness_problems=["document count is 0, expected 2"],
    )

    assert prepare_graph.main() == 1
    run_build.assert_not_awaited()


@pytest.mark.parametrize(
    ("arguments", "expected_resume"),
    [
        (_arguments(rebuild=True), False),
        (_arguments(mode="prebuilt", resume=True), True),
    ],
)
def test_rebuild_and_resume_are_explicit_build_intent(
    monkeypatch: pytest.MonkeyPatch,
    arguments: Namespace,
    expected_resume: bool,
) -> None:
    _, run_build = _patch_main_dependencies(
        monkeypatch,
        arguments=arguments,
        graph_counts=(0, 0, {}, {}),
        readiness_problems=[],
    )

    assert prepare_graph.main() == 0
    run_build.assert_awaited_once()
    assert run_build.await_args.kwargs["resume"] is expected_resume
    prepare_graph.report_readiness.assert_not_called()
