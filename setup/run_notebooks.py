# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Execute the workshop notebooks end to end, in module order.

This is the check `check_repo.py` cannot be. That gate proves a notebook parses;
this one proves it runs. Everything that only shows up when the cells actually
execute -- a renamed helper, a changed function signature, an index one module
creates and the next one reads, a contract constant that moved -- is caught
here and nowhere else, which is why it is the command to run before saying a
module is finished.

Source notebooks are never modified. Each one is read into memory, executed
there, and written to a scratch directory that is discarded unless
`--keep-output` is passed.

Two things this deliberately does:

- **It writes to Neo4j.** Module 1 extracts five hotels into the graph, Module 3
  writes a reservation request, and Module 6 writes memory nodes. Running the
  workshop is what this script does, so point it at a graph you are willing to
  have written to.
- **It does not create AWS resources unless asked.** Modules 4 and 5 create
  Gateways, Lambda functions, IAM roles, secrets, and an ECR repository, and
  they are opt-in behind `--include-deploy` for that reason. Everything else
  only reads from Bedrock.

A notebook registered here that does not exist yet is reported as a skip rather
than a failure, so a module being renamed by whoever owns it does not turn this
into a red run for everybody else.

Usage:

    cd notebooks
    uv pip install nbconvert nbformat ipykernel
    uv run python ../setup/run_notebooks.py
    uv run python ../setup/run_notebooks.py --modules 1
    uv run python ../setup/run_notebooks.py --modules 1-3
    uv run python ../setup/run_notebooks.py --modules 4,5 --include-deploy
    uv run python ../setup/run_notebooks.py --list
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS = REPO_ROOT / "notebooks"
OUTPUT_ROOT = REPO_ROOT / "setup" / "notebook-output"
KERNEL_NAME = "graphrag-workshop"

INSTALL_HINT = (
    "run_notebooks needs nbformat, nbconvert, and ipykernel on top of the "
    "workshop requirements. From the notebooks directory:\n"
    "    uv pip install nbconvert nbformat ipykernel"
)

# A cell beginning with a shell escape or an install magic is not Python and
# installs into the kernel's environment mid-run. They are commented out in the
# in-memory copy rather than executed.
INSTALL_MAGIC = re.compile(r"^(\s*)[%!]\s*(pip|pip3|conda|uv)\b")


@dataclass(frozen=True)
class Notebook:
    """One notebook in the workshop run."""

    module: str
    path: Path
    creates_resources: bool = False


@dataclass(frozen=True)
class Result:
    """The outcome of one notebook execution."""

    notebook: Notebook
    status: str
    reason: str = ""
    detail: str = ""


# Registry order is run order, and it is module order on purpose. Module 1
# writes the graph and creates the indexes that Modules 2 and 3 read, so
# running them out of order reports failures that are artefacts of the runner
# rather than defects in the notebooks.
#
# Every notebook is registered whether or not it exists yet. A registered path
# that is missing is a skip with a reason, so a module can be renamed by its
# owner without every other author editing this tuple.
NOTEBOOKS_REGISTRY: tuple[Notebook, ...] = (
    Notebook("1", NOTEBOOKS / "01-build-graph" / "1.1_build_graph.ipynb"),
    Notebook(
        "2",
        NOTEBOOKS / "02-connected-context" / "2.1_connected_context.ipynb",
    ),
    Notebook(
        "3",
        NOTEBOOKS / "03-grounded-booking-agent" / "3.1_grounded_booking_agent.ipynb",
    ),
    Notebook(
        "4",
        NOTEBOOKS / "04-production-agent" / "4.1_agentcore_gateway.ipynb",
        creates_resources=True,
    ),
    Notebook(
        "4",
        NOTEBOOKS / "04-production-agent" / "4.2_agentcore_memory.ipynb",
        creates_resources=True,
    ),
    Notebook(
        "5",
        NOTEBOOKS / "05-agentcore-deploy" / "5.1_deploy.ipynb",
        creates_resources=True,
    ),
    Notebook("6", NOTEBOOKS / "06-neo4j-memory" / "6.1_neo4j_memory.ipynb"),
)

KNOWN_MODULES = tuple(dict.fromkeys(n.module for n in NOTEBOOKS_REGISTRY))


def parse_modules(spec: str | None) -> set[str]:
    """Parse one module, a comma-separated list, or a numeric range."""
    if spec is None:
        return set(KNOWN_MODULES)

    selected: set[str] = set()
    for raw_token in spec.split(","):
        token = raw_token.strip()
        if not token:
            continue
        if re.fullmatch(r"\d+-\d+", token):
            start, end = (int(value) for value in token.split("-"))
            if start > end:
                raise ValueError(f"invalid range '{token}': start exceeds end")
            selected.update(str(value) for value in range(start, end + 1))
        elif token.isdigit():
            selected.add(str(int(token)))
        else:
            raise ValueError(f"invalid module '{token}'")

    unknown = selected.difference(KNOWN_MODULES)
    if unknown:
        values = ", ".join(sorted(unknown, key=int))
        raise ValueError(f"unknown module(s): {values}")
    if not selected:
        raise ValueError("no modules selected")
    return selected


def neutralize_install_magics(document: Any) -> int:
    """Comment out package-install magics in an in-memory notebook copy."""
    count = 0
    for cell in document.cells:
        if cell.cell_type != "code":
            continue
        lines = []
        for line in cell.source.splitlines(keepends=True):
            match = INSTALL_MAGIC.match(line)
            if match is None:
                lines.append(line)
                continue
            newline = "\n" if line.endswith("\n") else ""
            lines.append(
                f"{match.group(1)}# [run_notebooks] disabled: "
                f"{line.strip()}{newline}"
            )
            count += 1
        cell.source = "".join(lines)
    return count


@contextmanager
def temporary_kernel(work_dir: Path) -> Iterator[None]:
    """Expose the runner's own interpreter as a throwaway Jupyter kernel.

    The notebooks put `notebooks/` on `sys.path` themselves, relative to their
    working directory, so the kernel needs the third-party packages and nothing
    else. Registering the runner's interpreter is what makes the run reproduce
    the environment a participant installed rather than whichever kernel
    happens to be registered on the machine.
    """
    kernel_dir = work_dir / "kernels" / KERNEL_NAME
    kernel_dir.mkdir(parents=True)
    kernel = {
        "argv": [
            sys.executable,
            "-m",
            "ipykernel_launcher",
            "-f",
            "{connection_file}",
        ],
        "display_name": "GraphRAG Workshop Runner",
        "language": "python",
    }
    (kernel_dir / "kernel.json").write_text(json.dumps(kernel), encoding="utf-8")

    previous_path = os.environ.get("JUPYTER_PATH")
    paths = [str(work_dir)]
    if previous_path:
        paths.append(previous_path)
    os.environ["JUPYTER_PATH"] = os.pathsep.join(paths)
    try:
        yield
    finally:
        if previous_path is None:
            os.environ.pop("JUPYTER_PATH", None)
        else:
            os.environ["JUPYTER_PATH"] = previous_path


def output_path(output_dir: Path, notebook: Notebook) -> Path:
    """Return an output path that preserves the source module directory."""
    module_dir = output_dir / notebook.path.parent.name
    module_dir.mkdir(parents=True, exist_ok=True)
    return module_dir / f"{notebook.path.stem}-executed.ipynb"


def cell_preview(cell: Any, limit: int = 100) -> str:
    """Return a compact one-line description of a notebook cell."""
    first_line = next(
        (line.strip() for line in cell.source.splitlines() if line.strip()),
        "<empty cell>",
    )
    if len(first_line) <= limit:
        return first_line
    return f"{first_line[: limit - 3]}..."


def print_cell_outputs(cell: Any) -> None:
    """Print the text a completed cell produced."""
    for output in cell.get("outputs", []):
        output_type = output.get("output_type")
        if output_type == "stream":
            text = output.get("text", "")
        elif output_type in {"display_data", "execute_result"}:
            text = output.get("data", {}).get("text/plain", "")
        elif output_type == "error":
            text = "\n".join(output.get("traceback", []))
        else:
            continue
        for line in str(text).rstrip().splitlines():
            print(f"    {line}", flush=True)


def run_notebook(notebook: Notebook, output_dir: Path, timeout: int) -> Result:
    """Execute one notebook, leaving its source file untouched."""
    import nbformat
    from nbconvert.preprocessors import ExecutePreprocessor

    relative_path = notebook.path.relative_to(REPO_ROOT)
    print(f"\nRunning {relative_path}", flush=True)
    print(f"  Execution directory: {notebook.path.parent}", flush=True)

    document = None
    try:
        document = nbformat.read(notebook.path, as_version=4)
        disabled = neutralize_install_magics(document)
        if disabled:
            print(f"  Disabled {disabled} package-install line(s)", flush=True)

        code_cell_indices = [
            index
            for index, cell in enumerate(document.cells)
            if cell.cell_type == "code" and cell.source.strip()
        ]
        positions = {
            index: position
            for position, index in enumerate(code_cell_indices, start=1)
        }
        started_at: dict[int, float] = {}

        def on_cell_execute(*, cell: Any, cell_index: int) -> None:
            started_at[cell_index] = time.monotonic()
            print(
                f"  Cell {positions[cell_index]}/{len(code_cell_indices)} "
                f"started: {cell_preview(cell)}",
                flush=True,
            )

        def on_cell_executed(
            *, cell: Any, cell_index: int, execute_reply: Any
        ) -> None:
            elapsed = time.monotonic() - started_at[cell_index]
            status = execute_reply.get("content", {}).get("status", "ok")
            print(
                f"  Cell {positions[cell_index]}/{len(code_cell_indices)} "
                f"{status} in {elapsed:.1f}s",
                flush=True,
            )
            print_cell_outputs(cell)

        executor = ExecutePreprocessor(
            timeout=timeout,
            kernel_name=KERNEL_NAME,
            allow_errors=False,
            on_cell_execute=on_cell_execute,
            on_cell_executed=on_cell_executed,
        )
        # Use the notebook's own folder explicitly. This is one of the three
        # supported interactive launch locations and keeps local side effects
        # beside the module that owns them.
        executor.preprocess(
            document, {"metadata": {"path": str(notebook.path.parent)}}
        )
        nbformat.write(document, output_path(output_dir, notebook))
    except Exception as exc:  # Report the failure and keep running the rest.
        if document is not None:
            nbformat.write(document, output_path(output_dir, notebook))
        detail = traceback.format_exc()
        message = next(
            (line.strip() for line in str(exc).splitlines() if line.strip()),
            "execution failed",
        )
        return Result(
            notebook, "FAIL", reason=f"{type(exc).__name__}: {message}", detail=detail
        )

    return Result(notebook, "PASS")


def select_notebooks(
    modules: set[str], include_deploy: bool
) -> list[tuple[Notebook, str | None]]:
    """Select notebooks and record why any of them will not be run."""
    selected: list[tuple[Notebook, str | None]] = []
    for notebook in NOTEBOOKS_REGISTRY:
        if notebook.module not in modules:
            continue
        reason = None
        if notebook.creates_resources and not include_deploy:
            reason = "creates AWS resources; pass --include-deploy"
        elif not notebook.path.exists():
            reason = "notebook file not found"
        selected.append((notebook, reason))
    return selected


def print_registry() -> None:
    """Print the registry without executing anything."""
    for notebook in NOTEBOOKS_REGISTRY:
        suffix = " (creates AWS resources)" if notebook.creates_resources else ""
        print(f"{notebook.module}: {notebook.path.relative_to(REPO_ROOT)}{suffix}")


def print_summary(results: list[Result], kept_output: Path | None) -> None:
    """Print the result table, then the detail for anything that failed."""
    print("\nResults")
    print("=" * 72)
    for result in results:
        path = result.notebook.path.relative_to(REPO_ROOT)
        suffix = f" ({result.reason})" if result.reason else ""
        print(f"{result.status:<4}  {path}{suffix}")

    passed = sum(result.status == "PASS" for result in results)
    failed = sum(result.status == "FAIL" for result in results)
    skipped = sum(result.status == "SKIP" for result in results)
    print(
        f"\nPassed: {passed}  Failed: {failed}  "
        f"Skipped: {skipped}  Total: {len(results)}"
    )

    for result in results:
        if result.status == "FAIL":
            path = result.notebook.path.relative_to(REPO_ROOT)
            print(f"\nFailure: {path}\n{result.detail.rstrip()}")

    if kept_output is not None:
        print(f"\nExecuted notebooks: {kept_output}")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--modules",
        help="Modules to run: '3', '1,3,6', or '1-3'. Default: all.",
    )
    parser.add_argument(
        "--include-deploy",
        action="store_true",
        help="Run the modules that create AWS resources (4 and 5).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,
        help="Per-cell timeout in seconds (default: 1800).",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Keep the executed copies under setup/notebook-output/.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List the registered notebooks and exit.",
    )
    return parser


def require_execution_packages() -> None:
    """Fail with the install command rather than an ImportError traceback."""
    try:
        import nbconvert  # noqa: F401
        import nbformat  # noqa: F401
    except ImportError as exc:
        raise SystemExit(f"{exc}\n\n{INSTALL_HINT}") from exc


def main() -> int:
    """Run the selected notebooks and return a shell-compatible status."""
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        print_registry()
        return 0
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    try:
        modules = parse_modules(args.modules)
    except ValueError as exc:
        parser.error(str(exc))

    # After argument validation, so a typo in --modules is reported as a typo
    # rather than as a missing package.
    require_execution_packages()

    plan = select_notebooks(modules, include_deploy=args.include_deploy)

    with tempfile.TemporaryDirectory(prefix="run_notebooks_") as temp_dir:
        work_dir = Path(temp_dir)
        kept_output = None
        if args.keep_output:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            kept_output = OUTPUT_ROOT / f"{stamp}-{os.getpid()}"
            kept_output.mkdir(parents=True)
            result_dir = kept_output
        else:
            result_dir = work_dir / "output"

        results: list[Result] = []
        with temporary_kernel(work_dir):
            for notebook, skip_reason in plan:
                if skip_reason is not None:
                    path = notebook.path.relative_to(REPO_ROOT)
                    print(f"\nSkipping {path}: {skip_reason}")
                    results.append(Result(notebook, "SKIP", reason=skip_reason))
                    continue
                results.append(run_notebook(notebook, result_dir, args.timeout))

        print_summary(results, kept_output)
        return 1 if any(result.status == "FAIL" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
