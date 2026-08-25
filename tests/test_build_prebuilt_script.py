# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Focused offline contracts for the long-running prebuilt release script."""

from __future__ import annotations

from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "release"
    / "build_prebuilt_graph.sh"
)


def script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_build_executes_an_immutable_script_snapshot() -> None:
    script = script_text()

    assert 'if [[ -z "${PREBUILT_SCRIPT_SNAPSHOT:-}" ]]' in script
    assert 'cp "${BASH_SOURCE[0]}" "$PREBUILT_SCRIPT_SNAPSHOT"' in script
    assert 'exec bash "$PREBUILT_SCRIPT_SNAPSHOT" "$@"' in script
    assert (
        'cp "$REPO_ROOT/tools/release/write_prebuilt_manifest.py" '
        '"$MANIFEST_WRITER"' in script
    )
    assert script.count('python3 "$MANIFEST_WRITER"') == 2


def test_failed_build_retains_a_labeled_resumable_volume() -> None:
    script = script_text()

    assert script.count('docker volume create --label "$CHECKPOINT_LABEL=v1"') == 2
    assert 'if [[ "$BUILD_SUCCEEDED" == true ]]' in script
    assert "NEO4J_PREBUILT_VOLUME='$VOLUME'" in script


def test_cleanup_attempts_graceful_stop_before_forced_removal() -> None:
    script = script_text()

    graceful = script.index('docker stop --time "$SHUTDOWN_TIMEOUT"')
    forced = script.index('docker rm -f "$CONTAINER"')
    assert graceful < forced


def test_candidate_is_verified_before_pending_manifest_is_published() -> None:
    script = script_text()

    verify = script.rindex('verify_candidate_manifest "$PENDING_MANIFEST"')
    publish = script.index('mv "$PENDING_MANIFEST" "$MANIFEST"', verify)
    success = script.index("BUILD_SUCCEEDED=true", publish)
    assert verify < publish < success
