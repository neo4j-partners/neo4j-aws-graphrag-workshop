# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Load and reconcile the five held-out hotels against a prebuilt graph.

Used for: maintainer release validation of the learner-additive graph path.

This is the reusable release operation for the learner-additive path. It first
proves that the configured graph has the exact 295-document prebuilt shape,
then invokes ``load_held_out_hotels.py`` so the write path is identical
to Module 1. It records the resulting counts and runs the authoritative full
source-to-amenity reconciliation.

No Bedrock call is made unless the before snapshot matches the prebuilt
contract. Evidence is retained in ``--output-dir`` even when a later stage
fails.

Usage from the workshop environment:

    cd notebooks
    uv run python ../tools/release/run_additive_validation.py \
        --output-dir ../evidence/additive-20260823
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
if str(NOTEBOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(NOTEBOOKS_DIR))

from workshop.graph_connection import (
    graph_database,
    neo4j_auth,
    neo4j_uri,
    require_neo4j_env,
)

RELEASE_DIR = REPO_ROOT / "tools" / "release"
LOADER = RELEASE_DIR / "load_held_out_hotels.py"
VALIDATOR = RELEASE_DIR / "validate_graph_amenities.py"

COUNTS_QUERY = """
CYPHER 25
CALL () {
  MATCH (document:Document)
  RETURN count(document) AS documents
}
CALL () {
  MATCH (hotel:Hotel)
  RETURN count(DISTINCT hotel) AS hotels
}
CALL () {
  MATCH (amenity:Amenity)
  RETURN count(amenity) AS amenities
}
CALL () {
  MATCH ()-[offer:OFFERS_AMENITY]->(amenity:Amenity)
  WITH DISTINCT offer.source_filename AS source, amenity.name AS amenity
  RETURN count(*) AS amenity_assertions
}
CALL () {
  MATCH ()-[offer:OFFERS_AMENITY]->(amenity:Amenity)
  WHERE toLower(amenity.name) CONTAINS 'pool'
  RETURN count(DISTINCT offer.source_filename) AS pool_sources
}
RETURN documents, hotels, amenities, amenity_assertions, pool_sources
""".strip()

PREBUILT_COUNTS = {
    "documents": 295,
    "hotels": 295,
    "amenities": 65,
    "amenity_assertions": 1606,
    "pool_sources": 172,
}

FULL_COUNTS = {
    "documents": 300,
    "hotels": 300,
    "amenities": 65,
    "amenity_assertions": 1632,
    "pool_sources": 175,
}

HELD_OUT_DELTA = {
    "documents": 5,
    "hotels": 5,
    "amenities": 0,
    "amenity_assertions": 26,
    "pool_sources": 3,
}


def utc_now() -> str:
    """Return an evidence-friendly UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def write_report(path: Path, report: dict[str, Any]) -> None:
    """Persist the current state so a failed stage still leaves evidence."""
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def graph_counts() -> dict[str, int]:
    """Read the five exact release metrics from the configured graph."""
    with (
        GraphDatabase.driver(neo4j_uri(), auth=neo4j_auth()) as driver,
        driver.session(database=graph_database()) as session,
    ):
        record = session.run(COUNTS_QUERY).single()
    if record is None:
        raise RuntimeError("the graph count query returned no row")
    return {name: int(record[name]) for name in FULL_COUNTS}


def comparison_problems(
    actual: dict[str, int], expected: dict[str, int], label: str
) -> list[str]:
    """Describe every count that differs from an exact contract."""
    return [
        f"{label} {name}: found {actual.get(name)!r}, expected {value}"
        for name, value in expected.items()
        if actual.get(name) != value
    ]


def count_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    """Return the additive change for every release metric."""
    return {name: after[name] - before[name] for name in FULL_COUNTS}


def run_logged(command: list[str], log_path: Path) -> int:
    """Run one established release script and retain its complete output."""
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    """Build the additive release-operation CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="New directory for the JSON report and stage logs.",
    )
    return parser


def prepare_output_dir(path: Path) -> Path:
    """Create a new evidence directory without overwriting an earlier run."""
    output_dir = path.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "additive-validation.json"
    if report_path.exists():
        raise FileExistsError(
            f"{report_path} already exists; choose a new --output-dir"
        )
    return output_dir


def main() -> int:
    """Run the guarded additive load and all exact reconciliation gates."""
    args = build_parser().parse_args()
    try:
        output_dir = prepare_output_dir(args.output_dir)
    except FileExistsError as exc:
        raise SystemExit(str(exc)) from exc

    report_path = output_dir / "additive-validation.json"
    report: dict[str, Any] = {
        "started_utc": utc_now(),
        "status": "running",
        "neo4j_uri": None,
        "neo4j_database": None,
        "expected": {
            "before": PREBUILT_COUNTS,
            "after": FULL_COUNTS,
            "delta": HELD_OUT_DELTA,
        },
        "stages": {},
        "problems": [],
    }
    write_report(report_path, report)

    load_dotenv(REPO_ROOT / ".env")
    require_neo4j_env()
    report["neo4j_uri"] = neo4j_uri()
    report["neo4j_database"] = graph_database()

    before = graph_counts()
    before_problems = comparison_problems(before, PREBUILT_COUNTS, "before")
    report["stages"]["before"] = {
        "completed_utc": utc_now(),
        "counts": before,
        "passed": not before_problems,
    }
    report["problems"].extend(before_problems)
    write_report(report_path, report)
    if before_problems:
        report["status"] = "failed"
        report["completed_utc"] = utc_now()
        write_report(report_path, report)
        print("Prebuilt count gate failed; the held-out loader was not run.")
        return 1

    loader_log = output_dir / "load-held-out.log"
    loader_command = [sys.executable, str(LOADER)]
    loader_returncode = run_logged(loader_command, loader_log)
    report["stages"]["load_held_out"] = {
        "completed_utc": utc_now(),
        "command": loader_command,
        "log": str(loader_log),
        "returncode": loader_returncode,
        "passed": loader_returncode == 0,
    }

    after = graph_counts()
    delta = count_delta(before, after)
    after_problems = comparison_problems(after, FULL_COUNTS, "after")
    delta_problems = comparison_problems(delta, HELD_OUT_DELTA, "delta")
    report["stages"]["after"] = {
        "completed_utc": utc_now(),
        "counts": after,
        "delta": delta,
        "passed": not after_problems and not delta_problems,
    }
    if loader_returncode != 0:
        report["problems"].append(
            f"held-out loader exited with status {loader_returncode}"
        )
    report["problems"].extend(after_problems)
    report["problems"].extend(delta_problems)
    write_report(report_path, report)

    validator_log = output_dir / "full-reconciliation.log"
    validator_command = [sys.executable, str(VALIDATOR), "--mode", "full"]
    validator_returncode = run_logged(validator_command, validator_log)
    report["stages"]["full_reconciliation"] = {
        "completed_utc": utc_now(),
        "command": validator_command,
        "log": str(validator_log),
        "returncode": validator_returncode,
        "passed": validator_returncode == 0,
    }
    if validator_returncode != 0:
        report["problems"].append(
            f"full source reconciliation exited with status {validator_returncode}"
        )

    report["completed_utc"] = utc_now()
    report["status"] = "passed" if not report["problems"] else "failed"
    write_report(report_path, report)
    print(f"Additive validation {report['status']}: {report_path}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
