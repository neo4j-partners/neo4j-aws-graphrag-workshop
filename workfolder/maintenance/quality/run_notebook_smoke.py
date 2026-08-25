# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Run selected workshop notebooks into an explicit evidence directory.

Used for: maintainer release smoke checks that retain executed notebook evidence.

This wrapper reuses ``run_notebooks.py`` for registry selection, kernel
isolation, execution, and result reporting. Deployment notebooks remain
excluded because this release smoke check must not create AWS resources.

Usage:

    cd notebooks
    uv run python ../workfolder/maintenance/quality/run_notebook_smoke.py \
        --modules 1-3 \
        --output-dir ../evidence/live/notebooks
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_notebooks


def build_parser() -> argparse.ArgumentParser:
    """Build the explicit-output notebook smoke CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--modules",
        default="1-3",
        help="Modules to run. Default: 1-3.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="New directory for executed notebooks and summary.json.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Per-cell timeout in seconds. Default: 1800.",
    )
    return parser


def prepare_output_dir(path: Path) -> Path:
    """Create a new output location without replacing prior smoke evidence."""
    output_dir = path.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    if (output_dir / "summary.json").exists():
        raise FileExistsError(
            f"{output_dir / 'summary.json'} already exists; choose a new --output-dir"
        )
    return output_dir


def result_record(result: run_notebooks.Result) -> dict[str, Any]:
    """Convert the shared runner's result into stable JSON evidence."""
    return {
        "module": result.notebook.module,
        "notebook": str(result.notebook.path.relative_to(run_notebooks.REPO_ROOT)),
        "status": result.status,
        "reason": result.reason,
        "detail": result.detail,
    }


def main() -> int:
    """Execute the selected non-deployment notebooks and retain all output."""
    parser = build_parser()
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    try:
        modules = run_notebooks.parse_modules(args.modules)
    except ValueError as exc:
        parser.error(str(exc))
    if modules.intersection({"4", "5"}):
        parser.error("release smoke checks do not run deployment modules 4 or 5")

    try:
        output_dir = prepare_output_dir(args.output_dir)
    except FileExistsError as exc:
        raise SystemExit(str(exc)) from exc
    run_notebooks.require_execution_packages()
    plan = run_notebooks.select_notebooks(modules, include_deploy=False)

    started = datetime.now(timezone.utc).isoformat()
    results: list[run_notebooks.Result] = []
    with (
        tempfile.TemporaryDirectory(prefix="release_notebooks_") as temp_dir,
        run_notebooks.temporary_kernel(Path(temp_dir)),
    ):
        for notebook, skip_reason in plan:
            if skip_reason is not None:
                results.append(
                    run_notebooks.Result(notebook, "SKIP", reason=skip_reason)
                )
                continue
            results.append(
                run_notebooks.run_notebook(notebook, output_dir, args.timeout)
            )

    run_notebooks.print_summary(results, output_dir)
    summary = {
        "started_utc": started,
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "modules": sorted(modules, key=int),
        "timeout_seconds": args.timeout,
        "results": [result_record(result) for result in results],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 1 if any(result.status != "PASS" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
