# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline tests for prebuilt candidate provenance manifests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RELEASE_DIR = Path(__file__).resolve().parents[1] / "tools" / "release"
sys.path.insert(0, str(RELEASE_DIR))

import write_prebuilt_manifest


def test_start_snapshot_captures_git_state_and_critical_hashes(
    tmp_path: Path, monkeypatch
) -> None:
    critical = tmp_path / "builder.py"
    critical.write_text("build input\n", encoding="utf-8")
    monkeypatch.setattr(
        write_prebuilt_manifest,
        "CRITICAL_FILES",
        {"graph_builder": Path("builder.py")},
    )

    def fake_git(repo_root: Path, *args: str) -> str:
        assert repo_root == tmp_path
        if args[0] == "status":
            return " M builder.py\n?? notes.txt"
        return "0123456789abcdef"

    monkeypatch.setattr(write_prebuilt_manifest, "_git", fake_git)

    snapshot = write_prebuilt_manifest.start_snapshot(
        tmp_path,
        started_at="2026-08-23T10:00:00Z",
        started_epoch=100,
        resume_mode=True,
    )

    assert snapshot["build"] == {
        "started_at": "2026-08-23T10:00:00Z",
        "started_epoch": 100,
        "resume_mode": True,
    }
    assert snapshot["git"] == {
        "commit": "0123456789abcdef",
        "dirty": True,
        "status_porcelain": [" M builder.py", "?? notes.txt"],
    }
    assert snapshot["critical_files"]["graph_builder"] == {
        "path": "builder.py",
        "sha256": write_prebuilt_manifest.sha256_file(critical),
    }


def test_final_manifest_is_complete_and_never_overwrites(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.dump"
    candidate.write_bytes(b"neo4j candidate")
    snapshot = {
        "manifest_version": 1,
        "build": {
            "started_at": "2026-08-23T10:00:00Z",
            "started_epoch": 100,
            "resume_mode": False,
        },
        "git": {"commit": "abc", "dirty": False, "status_porcelain": []},
        "critical_files": {},
    }

    manifest = write_prebuilt_manifest.final_manifest(
        snapshot,
        candidate,
        completed_at="2026-08-23T10:02:03Z",
        completed_epoch=223,
        image_tag="neo4j:latest",
        image_id="sha256:image-id",
        image_repo_digests=["neo4j@sha256:repo-digest"],
    )
    output = tmp_path / "candidate.manifest.json"
    write_prebuilt_manifest.write_json_exclusive(output, manifest)

    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["final_success"] is True
    assert written["build"]["duration_seconds"] == 123
    assert written["build"]["resume_mode"] is False
    assert written["docker_image"] == {
        "requested_tag": "neo4j:latest",
        "id": "sha256:image-id",
        "repo_digests": ["neo4j@sha256:repo-digest"],
    }
    assert written["candidate"] == {
        "path": candidate.name,
        "byte_size": len(b"neo4j candidate"),
        "sha256": write_prebuilt_manifest.sha256_file(candidate),
    }

    with pytest.raises(FileExistsError):
        write_prebuilt_manifest.write_json_exclusive(output, {"final_success": False})
    assert json.loads(output.read_text(encoding="utf-8")) == written


def test_recovered_manifest_separates_evidence_from_current_state(
    tmp_path: Path, monkeypatch
) -> None:
    candidate = tmp_path / "candidate.dump"
    candidate.write_bytes(b"recovered neo4j candidate")
    build_log = tmp_path / "build.log"
    gate_lines = list(write_prebuilt_manifest.RECOVERY_GATES.values())
    build_log.write_text(
        "old failed run\n"
        "Starting disposable Neo4j with neo4j:latest...\n"
        + "\n".join(gate_lines)
        + "\ntools/release/build_prebuilt_graph.sh: line 101: "
        "syntax error near "
        "unexpected token `then'\n"
        "real 10729.83\n",
        encoding="utf-8",
    )
    critical = tmp_path / "builder.py"
    critical.write_text("recovery-time input\n", encoding="utf-8")
    monkeypatch.setattr(
        write_prebuilt_manifest,
        "CRITICAL_FILES",
        {"graph_builder": Path("builder.py")},
    )

    def fake_git(repo_root: Path, *args: str) -> str:
        assert repo_root == tmp_path
        if args[0] == "status":
            return " M builder.py"
        return "recovery-commit"

    monkeypatch.setattr(write_prebuilt_manifest, "_git", fake_git)
    manifest = write_prebuilt_manifest.recovered_manifest(
        tmp_path,
        candidate,
        build_log,
        recovered_at="2026-08-23T23:30:00Z",
        image_tag="neo4j:latest",
    )

    assert manifest["provenance"]["capture_mode"] == "recovered_after_build"
    assert manifest["build"]["duration_seconds"] == 10729.83
    assert manifest["build"]["wrapper_exit_status"] == "failed_after_graph_readiness"
    assert "wrapper itself did not exit successfully" in manifest["success_scope"]
    assert manifest["git"]["commit"] is None
    assert manifest["critical_files"]["files"] is None
    assert manifest["docker_image"]["id"] is None
    assert manifest["candidate"]["sha256"] == (
        write_prebuilt_manifest.sha256_file(candidate)
    )
    assert manifest["evidence"]["successful_run_start_line"] == 2
    assert manifest["evidence"]["timing"]["duration_seconds"] == 10729.83
    assert manifest["recovery_environment"]["git"]["commit"] == "recovery-commit"
    assert manifest["recovery_environment"]["critical_files"]["graph_builder"] == {
        "path": "builder.py",
        "sha256": write_prebuilt_manifest.sha256_file(critical),
    }


def test_recovered_manifest_rejects_incomplete_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    candidate = tmp_path / "candidate.dump"
    candidate.write_bytes(b"candidate")
    build_log = tmp_path / "build.log"
    build_log.write_text(
        "Starting disposable Neo4j with neo4j:latest...\n"
        "BUILD COMPLETE (295/295 ingests acknowledged)\n"
        "real 1.0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(write_prebuilt_manifest, "CRITICAL_FILES", {})
    monkeypatch.setattr(write_prebuilt_manifest, "_git", lambda *_: "")

    with pytest.raises(ValueError, match="document_count"):
        write_prebuilt_manifest.recovered_manifest(
            tmp_path,
            candidate,
            build_log,
            recovered_at="2026-08-23T23:30:00Z",
            image_tag="neo4j:latest",
        )
