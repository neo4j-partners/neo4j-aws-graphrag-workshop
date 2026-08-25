# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline tests for the additive and notebook-smoke operations."""

from __future__ import annotations

from pathlib import Path

import pytest
import run_additive_validation
import run_notebook_smoke

ADDITIVE_WRAPPER = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "release"
    / "run_additive_validation.sh"
)


def test_additive_contract_requires_exact_before_after_and_delta() -> None:
    before = dict(run_additive_validation.PREBUILT_COUNTS)
    after = dict(run_additive_validation.FULL_COUNTS)

    assert (
        run_additive_validation.comparison_problems(
            before, run_additive_validation.PREBUILT_COUNTS, "before"
        )
        == []
    )
    delta = run_additive_validation.count_delta(before, after)
    assert delta == run_additive_validation.HELD_OUT_DELTA


def test_additive_contract_reports_each_mismatch() -> None:
    actual = dict(run_additive_validation.FULL_COUNTS)
    actual["documents"] = 299
    actual["amenity_assertions"] = 1631

    problems = run_additive_validation.comparison_problems(
        actual, run_additive_validation.FULL_COUNTS, "after"
    )

    assert problems == [
        "after documents: found 299, expected 300",
        "after amenity_assertions: found 1631, expected 1632",
    ]


def test_notebook_smoke_defaults_to_affected_modules(tmp_path: Path) -> None:
    args = run_notebook_smoke.build_parser().parse_args(["--output-dir", str(tmp_path)])
    assert args.modules == "1-3"
    assert args.timeout == 1800


def test_output_directories_refuse_to_replace_evidence(tmp_path: Path) -> None:
    (tmp_path / "additive-validation.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        run_additive_validation.prepare_output_dir(tmp_path)

    notebook_dir = tmp_path / "notebooks"
    notebook_dir.mkdir()
    (notebook_dir / "summary.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError, match="already exists"):
        run_notebook_smoke.prepare_output_dir(notebook_dir)


def test_additive_wrapper_restores_locally_and_can_retain_result() -> None:
    script = ADDITIVE_WRAPPER.read_text(encoding="utf-8")

    assert 'if [[ "${1:-}" == "--retain" ]]' in script
    assert "neo4j-admin database load" in script
    assert "tools/release/validate_prebuilt_candidate.py" in script
    assert "run_additive_validation.py" in script
    assert "NEO4J_PLUGINS" in script
    assert 'docker volume rm "$VOLUME"' in script
    assert 'if [[ "$RETAIN" == true ]]' in script
    assert '"password": password' not in script
    assert '"credential_note"' in script


def test_additive_wrapper_help_needs_no_candidate_or_docker() -> None:
    result = __import__("subprocess").run(
        [str(ADDITIVE_WRAPPER), "--help"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "[--retain] [candidate.dump] [output-dir]" in result.stdout
