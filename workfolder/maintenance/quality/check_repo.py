# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Static checks that need no AWS account and no Neo4j instance.

Used for: a maintainer's quick offline review of notebooks and workshop content.

Every check here is one that has already caught a real defect in this repository,
and every one runs offline in a couple of seconds. That is the whole selection
rule. Checks that would need credentials belong in a smoke test, and checks that
would need a live graph belong in the readiness report inside the build.

The last three checks were deliberately left out of the first version as too
large for their value. The Phase 1 review changed that arithmetic: instructions
pointing at files that do not exist, retired numbering, timing stamps, and a
hardcoded hotel count were four of the eleven defects it found, and all four are
mechanical. They are in now, scoped to `notebooks/` and `workshop-content/`.
Planning documents are excluded on purpose, because recording a retired name is
what they are for.

Run from anywhere:

    python workfolder/maintenance/quality/check_repo.py
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTEBOOKS = REPO_ROOT / "notebooks"
CONTENT = REPO_ROOT / "workshop-content" / "content"

# Cells beginning with a shell escape or a line magic are not Python and never
# parse. Cells using top-level `await` are valid in ipykernel but not in
# `ast.parse`, so they are retried wrapped in a coroutine.
NON_PYTHON_PREFIXES = ("!", "%")


def notebook_cells_parse() -> list[str]:
    """Every code cell in every module notebook must be parseable Python."""
    problems: list[str] = []
    for path in sorted(NOTEBOOKS.glob("*/[0-9]*.ipynb")):
        cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
        for index, cell in enumerate(cells):
            if cell["cell_type"] != "code":
                continue
            source = "".join(cell["source"])
            if not source.strip() or source.lstrip().startswith(NON_PYTHON_PREFIXES):
                continue
            try:
                ast.parse(source)
            except SyntaxError:
                indented = "\n".join(
                    f"    {line}" for line in source.splitlines()
                )
                try:
                    ast.parse(f"async def _wrapper():\n{indented}")
                except SyntaxError as exc:
                    rel = path.relative_to(REPO_ROOT)
                    problems.append(f"{rel} cell {index} does not parse: {exc.msg}")
    return problems


def python_files_compile() -> list[str]:
    """Every tracked .py file must byte-compile."""
    problems: list[str] = []
    for path in sorted(REPO_ROOT.rglob("*.py")):
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            problems.append(f"{path.relative_to(REPO_ROOT)} does not compile: {exc.msg}")
    return problems


def contracts_import_without_neo4j() -> list[str]:
    """`import workshop.contracts` must succeed with the Neo4j environment unset.

    A module that raises at import time when a credential is missing makes itself
    unimportable to the reservation Lambda and to anything running offline, and
    turns a missing variable into an ImportError from several modules away.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEO4J_")}
    env["PYTHONPATH"] = str(NOTEBOOKS)
    result = subprocess.run(
        [sys.executable, "-c", "import workshop.contracts, workshop.aws_region"],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        tail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "?"
        return [f"workshop.contracts does not import with Neo4j env unset: {tail}"]
    return []


LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")
SRC_PATTERN = re.compile(r'src="([^"]+)"')


def content_references_resolve() -> list[str]:
    """Every relative markdown link and image src in the content tree must exist."""
    problems: list[str] = []
    for path in sorted(CONTENT.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        targets = LINK_PATTERN.findall(text) + SRC_PATTERN.findall(text)
        for target in targets:
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            if not resolved.exists():
                rel = path.relative_to(REPO_ROOT)
                problems.append(f"{rel} references missing path: {target}")
    return problems


WEIGHT_PATTERN = re.compile(r"^weight:\s*(\d+)\s*$", re.MULTILINE)


def content_weights_unique() -> list[str]:
    """Two pages sharing a weight order unpredictably on the published site."""
    problems: list[str] = []
    seen: dict[int, str] = {}
    for path in sorted(CONTENT.glob("*/index.en.md")):
        match = WEIGHT_PATTERN.search(path.read_text(encoding="utf-8"))
        if match is None:
            problems.append(f"{path.relative_to(REPO_ROOT)} has no weight in its frontmatter")
            continue
        weight = int(match.group(1))
        folder = path.parent.name
        if weight in seen:
            problems.append(f"weight {weight} is used by both {seen[weight]} and {folder}")
        else:
            seen[weight] = folder
    return problems


def module_folders_have_pages() -> list[str]:
    """Every numbered notebook folder needs a content page of the same name.

    Only in that direction. The content tree also carries setup, summary, wrap-up
    and cleanup pages, and none of those has a notebook.
    """
    problems: list[str] = []
    for path in sorted(NOTEBOOKS.glob("[0-9]*/")):
        if not (CONTENT / path.name).is_dir():
            problems.append(f"notebooks/{path.name} has no page at content/{path.name}")
    return problems


IMAGE_TREES = (REPO_ROOT / "static" / "images", REPO_ROOT / "workshop-content" / "images")


def image_trees_identical() -> list[str]:
    """The two image trees ship the same files, byte for byte.

    A page renders from `workshop-content/images/` and the repository documents
    `static/images/`. A diagram updated in one and not the other is invisible
    until someone opens the published page.
    """
    left, right = IMAGE_TREES
    problems: list[str] = []
    left_names = {path.name for path in left.iterdir() if path.is_file()}
    right_names = {path.name for path in right.iterdir() if path.is_file()}
    for name in sorted(left_names - right_names):
        problems.append(f"{name} is in static/images/ but not workshop-content/images/")
    for name in sorted(right_names - left_names):
        problems.append(f"{name} is in workshop-content/images/ but not static/images/")
    for name in sorted(left_names & right_names):
        if (left / name).read_bytes() != (right / name).read_bytes():
            problems.append(f"{name} differs between the two image trees")
    return problems


# Each pattern is a defect the Phase 1 review actually found. The message says
# what to do instead, because the person who trips it is usually not the person
# who wrote the rule.
BANNED_PATTERNS = (
    (re.compile(r"\bDemos?\s+\d", re.IGNORECASE), "retired 'Demo N' numbering"),
    (re.compile(r"\bLabs?\s+\d", re.IGNORECASE), "retired 'Lab N' numbering"),
    (re.compile(r"\bModules?\s+[78]\b"), "retired 'Module 7/8' numbering"),
    (re.compile(r"customer-service-"), "retired e-commerce resource prefix"),
    (re.compile(r"\(\s*\d+\s*(?:min|minutes|hours?)\s*\)", re.IGNORECASE), "timing stamp"),
    (re.compile(r"\b\d+\s*(?:-|\s)\s*(?:minute|hour)\b", re.IGNORECASE), "timing estimate"),
)

# Applied to notebooks and content pages only. "Counts stay out of prose" is a
# rule about what the participant reads, not about engineering comments in a
# shared module explaining why a query is keyed the way it is.
PROSE_PATTERNS = (
    (re.compile(r"\b(?:287|292|295)\b"), "graph count in prose, read it from the graph"),
    # "300 hotels" was the original pattern and it missed "300 hotel documents"
    # in an image alt text, which is the same claim about the same graph.
    (re.compile(r"\b300\s+hotel\w*", re.IGNORECASE), "graph count in prose, read it from the graph"),
)
PROSE_SUFFIXES = (".ipynb", ".md")

# Folder and file names that moved or were deleted. Any survivor is a link or an
# instruction pointing at something that is not there.
RETIRED_NAMES = (
    "01-graphrag-vs-rag",
    "01-vectorial-rag-hallucinates",
    "02-vector-rag-hallucinates",
    "02-graphrag-fixes-it",
    "03-retrieval-patterns",
    "03-production-agent",
    "04-neo4j-memory",
    "09-neo4j-mcp-demo",
    "03_hybrid_retrieval.ipynb",
    "03b_agentcore_memory.ipynb",
    "04_neo4j_memory.ipynb",
    "2.1_vector_rag_hallucinates.ipynb",
    "3.1_retrieval_patterns.ipynb",
    "3.2_grounded_booking_agent.ipynb",
    "test_graphrag.ipynb",
    "load_vector_data.py",
    "setup_local_graph.py",
    "deployment-tools",
    "advanced-deployment",
)

SWEPT_TREES = (NOTEBOOKS, CONTENT)
SWEPT_SUFFIXES = (".py", ".ipynb", ".md")


def swept_files() -> list[Path]:
    """Notebooks, shared modules, and content pages. Not the planning documents."""
    files: list[Path] = []
    for tree in SWEPT_TREES:
        for path in sorted(tree.rglob("*")):
            if path.suffix not in SWEPT_SUFFIXES or not path.is_file():
                continue
            if ".venv" in path.parts or "__pycache__" in path.parts:
                continue
            files.append(path)
    return files


def banned_patterns_absent() -> list[str]:
    """No retired numbering, no timing stamp, and no graph count in prose."""
    problems: list[str] = []
    for path in swept_files():
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text(encoding="utf-8")
        patterns = BANNED_PATTERNS
        if path.suffix in PROSE_SUFFIXES:
            patterns += PROSE_PATTERNS
        for pattern, reason in patterns:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{rel}:{line} {reason}: {match.group(0)!r}")
        for name in RETIRED_NAMES:
            if name in text:
                line = text.count("\n", 0, text.index(name)) + 1
                problems.append(f"{rel}:{line} retired name: {name}")
    return problems


PATH_SUFFIXES = frozenset(
    {
        ".py", ".ipynb", ".json", ".md", ".txt", ".zip", ".yaml", ".yml",
        ".png", ".drawio", ".index", ".csv", ".sh", ".toml", ".cfg", ".dump",
    }
)
QUOTED = re.compile(r"[`\"\']([^`\"\'\n]{1,200})[`\"\']")
PATH_WORD = re.compile(r"^[\w./-]+$")
NON_LOCAL_PREFIXES = ("http://", "https://", "s3://", "arn:", "/", "~", "-")

# Named on purpose and correctly absent. Each entry says why, because an
# allowlist nobody can justify is how a gate stops meaning anything.
PATH_ALLOWLIST = {
    ".env": "an optional local override; the participant fills in CONFIG.txt",
    "Lab_5_Agent_Memory/lib/memory_utils.py": "cites the upstream sample this module came from",
}
SCRIPT_SUFFIXES = (".py", ".ipynb")


def _sibling_module_dirs(path: Path) -> tuple[Path, ...]:
    """Resolve a module's two trees against each other.

    A module is a notebook folder and a content folder sharing one name, so a
    content page naturally names a file by its path inside the notebook folder:
    `runtime_app/`, not `notebooks/05-agentcore-deploy/runtime_app/`. Without
    this, writing the natural thing fails the check, and the check teaches
    people to write unnatural prose to satisfy it.
    """
    for tree, sibling in ((CONTENT, NOTEBOOKS), (NOTEBOOKS, CONTENT)):
        try:
            module = path.relative_to(tree).parts[0]
        except (ValueError, IndexError):
            continue
        return (tree / module, sibling / module)
    return ()


def repo_basenames() -> set[str]:
    """Every filename in the repository, for resolving a script named without a path."""
    return {
        path.name
        for path in REPO_ROOT.rglob("*")
        if path.is_file() and ".venv" not in path.parts and ".git" not in path.parts
    }


def named_paths_exist() -> list[str]:
    """Every repository path named in code or prose resolves to something.

    `2.1` shelled out to a script that was not there and `4.1` told the
    participant to `cd` into a directory that has never existed. Both read fine.
    """
    problems: list[str] = []
    basenames = repo_basenames()
    for path in swept_files():
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text(encoding="utf-8")
        for match in QUOTED.finditer(text):
            for token in match.group(1).split():
                if PATH_WORD.match(token) is None:
                    continue
                if token in PATH_ALLOWLIST or token.startswith(NON_LOCAL_PREFIXES):
                    continue
                suffix = Path(token).suffix
                written_as_path = "/" in token
                is_dir_token = token.endswith("/") and not suffix
                if not written_as_path and suffix not in SCRIPT_SUFFIXES:
                    continue
                if suffix not in PATH_SUFFIXES and not is_dir_token:
                    continue
                if not written_as_path and token in basenames:
                    continue
                bases = (REPO_ROOT, path.parent, NOTEBOOKS, CONTENT)
                bases += _sibling_module_dirs(path)
                if any((base / token).exists() for base in bases):
                    continue
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{rel}:{line} names a path that does not exist: {token}")
    return problems


CHECKS = (
    ("notebook code cells parse", notebook_cells_parse),
    ("python files compile", python_files_compile),
    ("workshop.contracts imports offline", contracts_import_without_neo4j),
    ("content references resolve", content_references_resolve),
    ("content weights are unique", content_weights_unique),
    ("module folders have content pages", module_folders_have_pages),
    ("image trees are identical", image_trees_identical),
    ("banned patterns are absent", banned_patterns_absent),
    ("named paths exist", named_paths_exist),
)


def main() -> int:
    failures = 0
    for name, check in CHECKS:
        problems = check()
        if problems:
            failures += len(problems)
            print(f"FAIL  {name}")
            for problem in problems:
                print(f"        {problem}")
        else:
            print(f"ok    {name}")
    print()
    if failures:
        print(f"{failures} problem(s) found.")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
