# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Capture and finalize provenance for a prebuilt graph candidate.

Used for: recording reproducible provenance while a maintainer builds a dump.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CRITICAL_FILES = {
    "graph_builder": Path("notebooks/02-connected-context/graph_builder.py"),
    "graph_config": Path("notebooks/02-connected-context/graph_config.py"),
    "prepare_graph": Path("notebooks/02-connected-context/prepare_graph.py"),
    "amenities": Path("notebooks/workshop/amenities.py"),
    "contracts": Path("notebooks/workshop/contracts.py"),
    "graph_schema_contract": Path("notebooks/workshop/graph_schema.py"),
    "retrieval_contract": Path("notebooks/workshop/retrieval_contract.py"),
    "corpus": Path("notebooks/shared/hotel-faqs.zip"),
    "uv_lock": Path("notebooks/workshop/uv.lock"),
    "build_script": Path("tools/release/build_prebuilt_graph.sh"),
    "manifest_writer": Path("tools/release/write_prebuilt_manifest.py"),
}

RECOVERY_GATES = {
    "build_complete": "BUILD COMPLETE (295/295 ingests acknowledged)",
    "document_count": ":Document nodes: 295 (expected 295)",
    "chunk_count": ":Chunk nodes: 295 (expected 295, one chunk per document)",
    "amenity_assertions": "✅ Materialized 1606 amenity assertions",
    "retrieval_indexes": (
        "✅ Retrieval indexes are online and match the embedding contract"
    ),
    "module_readiness": "  documents: 295 (expected 295)",
    "pool_sources": "  Counting  hotels with a pool: 172",
    "booking_fixtures": (
        "✅ Fixture hotel IDs, the demo06_* constraints, and the "
        "maximum-guests rule are in the graph"
    ),
}


def sha256_file(path: Path) -> str:
    """Return a file's SHA-256 without loading the full artifact into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.rstrip("\n")


def start_snapshot(
    repo_root: Path,
    *,
    started_at: str,
    started_epoch: int,
    resume_mode: bool,
) -> dict[str, Any]:
    """Capture immutable build inputs before the long-running work starts."""
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=normal")
    critical_files = {}
    for name, relative_path in CRITICAL_FILES.items():
        path = repo_root / relative_path
        critical_files[name] = {
            "path": relative_path.as_posix(),
            "sha256": sha256_file(path),
        }

    return {
        "manifest_version": 1,
        "build": {
            "started_at": started_at,
            "started_epoch": started_epoch,
            "resume_mode": resume_mode,
        },
        "git": {
            "commit": _git(repo_root, "rev-parse", "HEAD"),
            "dirty": bool(status),
            "status_porcelain": status.splitlines(),
        },
        "critical_files": critical_files,
    }


def final_manifest(
    snapshot: dict[str, Any],
    candidate: Path,
    *,
    completed_at: str,
    completed_epoch: int,
    image_tag: str,
    image_id: str,
    image_repo_digests: list[str],
) -> dict[str, Any]:
    """Add output identity and completion facts to a start snapshot."""
    manifest = dict(snapshot)
    build = dict(snapshot["build"])
    build.update(
        {
            "completed_at": completed_at,
            "completed_epoch": completed_epoch,
            "duration_seconds": completed_epoch - build["started_epoch"],
        }
    )
    manifest.update(
        {
            "build": build,
            "docker_image": {
                "requested_tag": image_tag,
                "id": image_id,
                "repo_digests": image_repo_digests,
            },
            "candidate": {
                "path": candidate.name,
                "byte_size": candidate.stat().st_size,
                "sha256": sha256_file(candidate),
            },
            "final_success": True,
        }
    )
    return manifest


def _recovery_evidence(build_log: Path, image_tag: str) -> dict[str, Any]:
    """Extract direct evidence from the final run in an appended build log."""
    lines = build_log.read_text(encoding="utf-8").splitlines()
    start_text = f"Starting disposable Neo4j with {image_tag}..."
    start_indexes = [index for index, line in enumerate(lines) if line == start_text]
    if not start_indexes:
        raise ValueError(f"build log does not contain {start_text!r}")
    start_index = start_indexes[-1]
    successful_run = lines[start_index:]

    gates = {}
    for name, expected_text in RECOVERY_GATES.items():
        matches = [
            index
            for index, line in enumerate(successful_run, start=start_index)
            if line == expected_text
        ]
        if len(matches) != 1:
            raise ValueError(
                f"final build-log run contains {len(matches)} {name!r} gates; "
                "expected exactly one"
            )
        gates[name] = {
            "line": matches[0] + 1,
            "text": expected_text,
        }

    duration_matches = []
    for index, line in enumerate(successful_run, start=start_index):
        match = re.fullmatch(r"real ([0-9]+(?:\.[0-9]+)?)", line)
        if match:
            duration_matches.append((index, float(match.group(1)), line))
    if len(duration_matches) != 1:
        raise ValueError(
            "final build-log run must contain exactly one 'real <seconds>' timing"
        )
    duration_index, duration_seconds, duration_text = duration_matches[0]

    failure_matches = [
        (index, line)
        for index, line in enumerate(successful_run, start=start_index)
        if "syntax error near unexpected token" in line
    ]
    if len(failure_matches) != 1:
        raise ValueError(
            "final build-log run must contain exactly one recorded wrapper "
            "syntax failure"
        )
    failure_index, failure_text = failure_matches[0]

    return {
        "path": build_log.name,
        "sha256": sha256_file(build_log),
        "successful_run_start_line": start_index + 1,
        "successful_run_end_line": duration_index + 1,
        "gates": gates,
        "timing": {
            "line": duration_index + 1,
            "text": duration_text,
            "duration_seconds": duration_seconds,
        },
        "wrapper_failure": {
            "line": failure_index + 1,
            "text": failure_text,
        },
    }


def recovered_manifest(
    repo_root: Path,
    candidate: Path,
    build_log: Path,
    *,
    recovered_at: str,
    image_tag: str,
) -> dict[str, Any]:
    """Recover honest provenance when the build-start snapshot was not written."""
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=normal")
    recovery_files = {}
    for name, relative_path in CRITICAL_FILES.items():
        recovery_files[name] = {
            "path": relative_path.as_posix(),
            "sha256": sha256_file(repo_root / relative_path),
        }

    artifact_time = datetime.fromtimestamp(
        candidate.stat().st_mtime,
        tz=timezone.utc,
    ).isoformat()
    evidence = _recovery_evidence(build_log, image_tag)
    return {
        "manifest_version": 1,
        "provenance": {
            "capture_mode": "recovered_after_build",
            "recovered_at": recovered_at,
            "limitations": [
                "The build-start snapshot was not written before execution.",
                (
                    "The build-start Git commit, dirty state, and critical-file "
                    "hashes are unavailable because files changed while the build "
                    "process was running."
                ),
                (
                    "The successful container's immutable image ID and repository "
                    "digest were not preserved."
                ),
                (
                    "The wrapper failed after graph readiness; the candidate was "
                    "captured separately, and restore validation is outside this "
                    "manifest."
                ),
            ],
        },
        "build": {
            "started_at": None,
            "started_epoch": None,
            "completed_at": None,
            "completed_epoch": None,
            "duration_seconds": evidence["timing"]["duration_seconds"],
            "resume_mode": None,
            "wrapper_exit_status": "failed_after_graph_readiness",
        },
        "git": {
            "commit": None,
            "dirty": None,
            "status_porcelain": None,
            "availability": "unavailable_at_build_start",
        },
        "critical_files": {
            "availability": "unavailable_at_build_start",
            "files": None,
        },
        "docker_image": {
            "requested_tag": image_tag,
            "id": None,
            "repo_digests": None,
            "availability": "tag_from_successful_run_log; identity_unavailable",
        },
        "candidate": {
            "path": candidate.name,
            "byte_size": candidate.stat().st_size,
            "sha256": sha256_file(candidate),
            "artifact_modified_at": artifact_time,
        },
        "evidence": evidence,
        "recovery_environment": {
            "note": "Captured during recovery; these are not build inputs.",
            "git": {
                "commit": _git(repo_root, "rev-parse", "HEAD"),
                "dirty": bool(status),
                "status_porcelain": status.splitlines(),
            },
            "critical_files": recovery_files,
        },
        "success_scope": (
            "The final graph-readiness gates and candidate identity are recorded; "
            "the wrapper itself did not exit successfully."
        ),
        "final_success": True,
    }


def write_json_exclusive(path: Path, value: dict[str, Any]) -> None:
    """Publish JSON atomically without replacing an existing manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(value, temporary, indent=2, sort_keys=True)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.link(temporary_path, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Capture build-start provenance.")
    start.add_argument("--repo-root", type=Path, required=True)
    start.add_argument("--output", type=Path, required=True)
    start.add_argument("--started-at", required=True)
    start.add_argument("--started-epoch", type=int, required=True)
    start.add_argument("--resume", action="store_true")

    finish = subparsers.add_parser("finish", help="Write the final manifest.")
    finish.add_argument("--snapshot", type=Path, required=True)
    finish.add_argument("--candidate", type=Path, required=True)
    finish.add_argument("--manifest", type=Path, required=True)
    finish.add_argument("--completed-at", required=True)
    finish.add_argument("--completed-epoch", type=int, required=True)
    finish.add_argument("--image-tag", required=True)
    finish.add_argument("--image-id", required=True)
    finish.add_argument("--image-repo-digests-json", required=True)

    recover = subparsers.add_parser(
        "recover",
        help="Recover explicit provenance after a completed build lost its snapshot.",
    )
    recover.add_argument("--repo-root", type=Path, required=True)
    recover.add_argument("--candidate", type=Path, required=True)
    recover.add_argument("--build-log", type=Path, required=True)
    recover.add_argument("--manifest", type=Path, required=True)
    recover.add_argument("--recovered-at", required=True)
    recover.add_argument("--image-tag", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "start":
        snapshot = start_snapshot(
            args.repo_root.resolve(),
            started_at=args.started_at,
            started_epoch=args.started_epoch,
            resume_mode=args.resume,
        )
        args.output.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0

    if args.command == "recover":
        manifest = recovered_manifest(
            args.repo_root.resolve(),
            args.candidate.resolve(),
            args.build_log.resolve(),
            recovered_at=args.recovered_at,
            image_tag=args.image_tag,
        )
        write_json_exclusive(args.manifest, manifest)
        return 0

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    repo_digests = json.loads(args.image_repo_digests_json)
    if not isinstance(repo_digests, list) or not all(
        isinstance(item, str) for item in repo_digests
    ):
        raise ValueError("image repo digests must be a JSON list of strings")
    manifest = final_manifest(
        snapshot,
        args.candidate,
        completed_at=args.completed_at,
        completed_epoch=args.completed_epoch,
        image_tag=args.image_tag,
        image_id=args.image_id,
        image_repo_digests=repo_digests,
    )
    write_json_exclusive(args.manifest, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
