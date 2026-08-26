# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Idempotent self-paced rebuild of the workshop graph and its indexes.

The from-scratch path, for a facilitator or a self-paced participant who has no
dump to restore. It calls `graph_builder.run_build`, which wipes first. The
in-session path is `graph_builder.run_additive_build`, which Module 1's notebook
calls to extend a restored graph without deleting anything.
"""

import argparse
import asyncio
import os
import sys
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
NOTEBOOKS_ROOT = SCRIPT_DIR.parent
REPO_ROOT = NOTEBOOKS_ROOT.parent

# Add notebooks/ root to path so the workshop package can be found. `insert`
# rather than `append`: the notebooks bootstrap the same way, and a single
# convention is one less thing that behaves differently between the two.
sys.path.insert(0, str(NOTEBOOKS_ROOT))


os.environ["OTEL_SDK_DISABLED"] = "true"

from dotenv import load_dotenv

load_dotenv(NOTEBOOKS_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env")
load_dotenv(REPO_ROOT / "CONFIG.txt")

from graph_builder import connect, graph_database, report, run_build
from graph_config import HELD_OUT_DOCUMENTS, select_lite_files
from neo4j import Driver
from workshop.fixtures import (
    apply_reservation_fixtures,
    load_manifest,
    readiness_problems,
)
from workshop.retrieval_setup import (
    ReadinessError,
    ensure_retrieval_indexes,
    graph_counts,
    report_readiness,
    verify_retrieval_indexes,
)

DATA_DIR = SCRIPT_DIR / "data"
CORPUS_ZIP = NOTEBOOKS_ROOT / "shared" / "hotel-faqs.zip"
LITE_DOCUMENTS = 30
EXPECTED_CORPUS_DOCUMENTS = 300


class SourceSelectionError(ValueError):
    """Raised when a release build does not see the complete committed corpus."""


def ensure_corpus_extracted(data_dir: Path = DATA_DIR) -> int:
    """Extract the committed corpus zip when no documents are present yet.

    `data/` is gitignored, so a fresh clone has only the committed corpus zip
    in `notebooks/shared/`. The notebook's first cell extracts it, and the
    script path has to do the same or a participant who starts here stops at
    an empty directory. Returns the number of source documents now on disk.
    """
    extracted = sorted(data_dir.glob("*.txt"))
    if extracted or not CORPUS_ZIP.exists():
        return len(extracted)

    with zipfile.ZipFile(CORPUS_ZIP) as archive:
        archive.extractall(data_dir)
    extracted = sorted(data_dir.glob("*.txt"))
    print(f"Extracted {len(extracted)} source documents into {data_dir}/")
    return len(extracted)


def selected_paths(mode: str) -> list[Path]:
    """Return the deterministic source paths for the requested build mode."""
    if mode == "lite":
        names = select_lite_files(DATA_DIR, LITE_DOCUMENTS)
        return [DATA_DIR / name for name in names]
    if mode not in {"full", "prebuilt"}:
        raise SourceSelectionError(f"unknown graph build mode: {mode}")

    paths = sorted(DATA_DIR.glob("*.txt"))
    if len(paths) != EXPECTED_CORPUS_DOCUMENTS:
        raise SourceSelectionError(
            f"found {len(paths)} source documents in {DATA_DIR.resolve()}, "
            f"expected {EXPECTED_CORPUS_DOCUMENTS} from the committed corpus"
        )

    if mode == "prebuilt":
        held_out = set(HELD_OUT_DOCUMENTS)
        missing_held_out = sorted(held_out - {path.name for path in paths})
        if missing_held_out:
            raise SourceSelectionError(
                "committed corpus is missing held-out documents: "
                + ", ".join(missing_held_out)
            )
        return [path for path in paths if path.name not in held_out]
    return paths


def booking_agent_problems(driver: Driver, *, apply_fixtures: bool) -> list[str]:
    """Return what still stands between this graph and the Module 3.1 agent.

    Step 7 of the notebook seeds the fixture hotel IDs, the three `demo06_*`
    constraints, and the `max_guests` rule. The script path has to do the same,
    or a facilitator who builds here hands Module 3.1 a graph that cannot run.
    The seed is `MERGE` and `SET` throughout, so repeating it changes nothing.
    """
    database = graph_database()
    manifest = load_manifest()
    if apply_fixtures:
        blockers = apply_reservation_fixtures(driver, database, manifest)
        if blockers:
            return blockers
    return readiness_problems(driver, database, manifest)


def seed_booking_agent_fixtures() -> int:
    """Apply and verify the graph-owned data the Module 3.1 booking agent reads.

    `run_build` closes its own driver, so this opens a fresh one after the
    build and leaves the graph in the same state the notebook's step 7 does.
    """
    print("\nSeeding the fixtures the Module 3.1 booking agent depends on...")
    driver = connect()
    try:
        problems = booking_agent_problems(driver, apply_fixtures=True)
    finally:
        driver.close()

    if problems:
        print("\n❌ The graph is not ready for Module 3.1:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(
        "✅ Fixture hotel IDs, the demo06_* constraints, and the maximum-guests "
        "rule are in the graph"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild and verify the workshop graph and its retrieval indexes."
    )
    parser.add_argument(
        "--mode",
        choices=("lite", "full", "prebuilt"),
        default="lite",
        help=(
            "lite builds the 30-document sample; "
            "full builds all 300; prebuilt omits the five documents that "
            "participants extract live. Default: lite."
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Report readiness without rebuilding an incomplete graph.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Explicitly permit a from-scratch build and whole-graph clearing.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume a retained prebuilt checkpoint, reusing only sources whose "
            "content, build contract, and graph provenance are exact."
        ),
    )
    args = parser.parse_args()
    if args.check_only and (args.rebuild or args.resume):
        # --check-only writes nothing and --rebuild discards the graph, so a
        # run carrying both used to silently honour --rebuild alone.
        parser.error(
            "--check-only cannot be combined with --rebuild or --resume: "
            "--check-only reports readiness without writing"
        )
    if args.rebuild and args.resume:
        parser.error("--rebuild and --resume cannot be combined")
    if args.resume and args.mode != "prebuilt":
        parser.error("--resume is supported only with --mode prebuilt")
    return args


def main() -> int:
    args = parse_args()
    ensure_corpus_extracted()
    try:
        paths = selected_paths(args.mode)
    except SourceSelectionError as exc:
        print(f"❌ Source selection failed: {exc}")
        return 1
    if not paths:
        print(f"No source documents found in {DATA_DIR.resolve()}.")
        return 1

    driver = connect()
    explicit_build = args.rebuild or args.resume
    problems: list[str] = []
    observed_documents = 0
    observed_chunks = 0
    observed_hotels = 0
    try:
        # The index contract is checked before the build decision, never after
        # it. An index that exists at the wrong dimension cannot serve the
        # vectors a build writes, and --rebuild used to skip this check and
        # surface the same failure fifteen minutes later.
        if not explicit_build:
            try:
                verify_retrieval_indexes(driver)
            except ReadinessError as exc:
                problems.append(str(exc))
        else:
            try:
                ensure_retrieval_indexes(driver)
            except ReadinessError as exc:
                print(f"\n❌ {exc}")
                return 1
        if not explicit_build:
            observed_documents, observed_chunks, labels, _ = graph_counts(driver)
            observed_hotels = labels.get("Hotel", 0)
            problems.extend(report_readiness(driver, expected_documents=len(paths)))
            problems.extend(booking_agent_problems(driver, apply_fixtures=False))
            # The acceptance queries print whether or not a build runs, so a
            # ready graph still shows what Module 2 will be asking it.
            if not problems:
                report(driver)
    finally:
        driver.close()

    if not explicit_build and not problems:
        print("\n✅ The workshop graph is ready; no rebuild needed.")
        return 0
    if not explicit_build:
        print("\n❌ Graph readiness check failed; no graph data was changed.")
        print(
            "Observed graph size: "
            f"{observed_documents} Documents, {observed_chunks} Chunks, "
            f"{observed_hotels} Hotels. "
            f"Expected {len(paths)} of each for --mode {args.mode}."
        )
        for problem in problems:
            print(f"  - {problem}")
        print(
            "Run again with --check-only after correcting the reported issue. "
            "To discard and rebuild the whole graph from scratch, explicitly add "
            "--rebuild."
        )
        return 1

    titles = {
        "lite": "🚀 LITE BUILD",
        "full": "FULL BUILD",
        "prebuilt": "PREBUILT GRAPH BUILD",
    }
    title = titles[args.mode]
    exit_code = asyncio.run(run_build(paths, title, resume=args.resume))
    if exit_code != 0:
        return exit_code
    return seed_booking_agent_fixtures()


if __name__ == "__main__":
    sys.exit(main())
