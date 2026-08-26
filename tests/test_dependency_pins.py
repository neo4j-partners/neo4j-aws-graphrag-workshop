# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Guard the three pinned dependencies against drifting apart across the repo.

Four files declare what the workshop installs, and a participant can run code
against all four in one sitting:

* `notebooks/requirements.txt` is the kernel a participant builds Module 3 in.
* `notebooks/workshop/pyproject.toml` is the shared `workshop` package that
  every module imports.
* `notebooks/04-production-agent/lambda_tools/requirements.txt` is what the
  retrieval Lambdas deploy behind the Gateway.
* `notebooks/05-agentcore-deploy/runtime_app/agent_requirements.txt` is the
  image the Runtime answers every invocation from.

Strands builds the tool specification the model reads, and neo4j-graphrag
supplies the Text2Cypher path that refuses a plan the database does not report
as read-only. If those versions differ between the notebook and the deployment,
the agent a participant built stops being the agent that got deployed, and
nothing in the notebook output says so.

These tests assert consistency rather than literals. They do not know that the
agreed version is 1.53.0 or 1.19.0, so a deliberate upgrade that touches every
file stays green and an upgrade that misses one file fails. What is fixed is the
shape: each package is pinned with `==`, each file that is expected to declare a
package still declares it, and `requires-python` still admits the Python the
hosted lab runs.

Nothing here imports the workshop package or any of its dependencies, so these
checks run in an interpreter that has pytest and nothing else installed.

Run them with:

    uv run --with pytest pytest tests/test_dependency_pins.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10, which the hosted lab runs.
    tomllib = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = REPO_ROOT / "notebooks"

REQUIREMENTS = NOTEBOOKS / "requirements.txt"
PYPROJECT = NOTEBOOKS / "workshop" / "pyproject.toml"
LAMBDA_REQUIREMENTS = (
    NOTEBOOKS / "04-production-agent" / "lambda_tools" / "requirements.txt"
)
RUNTIME_REQUIREMENTS = (
    NOTEBOOKS / "05-agentcore-deploy" / "runtime_app" / "agent_requirements.txt"
)

DECLARATION_FILES = (
    REQUIREMENTS,
    PYPROJECT,
    LAMBDA_REQUIREMENTS,
    RUNTIME_REQUIREMENTS,
)

PINNED_PACKAGES = ("strands-agents", "neo4j", "neo4j-graphrag")

# Which file is expected to declare which package, written from what the files
# hold today. Consistency alone passes vacuously when a file drops a pin
# outright, because whatever is left still agrees with itself. This map is what
# catches a deletion. It carries no version numbers, so an upgrade never has to
# touch it. The retrieval Lambdas call Neo4j directly and never build an agent,
# which is why strands-agents is absent there rather than missing.
EXPECTED_DECLARATIONS = {
    REQUIREMENTS: {"strands-agents", "neo4j", "neo4j-graphrag"},
    PYPROJECT: {"strands-agents", "neo4j", "neo4j-graphrag"},
    LAMBDA_REQUIREMENTS: {"neo4j", "neo4j-graphrag"},
    RUNTIME_REQUIREMENTS: {"strands-agents", "neo4j", "neo4j-graphrag"},
}

# The Python floor the hosted lab image ships. A package that asks for more than
# this cannot be installed in the lab at all.
EXPECTED_REQUIRES_PYTHON = ">=3.10"

# `name[extra,extra] <operator> version`, which is as much of PEP 508 as these
# four files use. The extras bracket is captured so it can be discarded: the
# Runtime declares `strands-agents[otel]`, and that is the same package as the
# `strands-agents` the notebook kernel installs.
DEPENDENCY = re.compile(
    r"^(?P<name>[A-Za-z0-9._-]+)"
    r"(?:\[(?P<extras>[^\]]*)\])?"
    r"\s*(?P<operator>[=<>!~]=|[<>])?"
    r"\s*(?P<version>[^;\s]+)?"
)


def parse_declaration(line: str) -> tuple[str, str, str] | None:
    """Split one dependency line into its normalized name, operator, version.

    Returns None for anything that is not a dependency, such as a comment or a
    blank line. The name is lowercased and its extras are dropped, so
    `strands-agents[otel]` and `strands-agents` compare equal.
    """
    stripped = line.strip().strip(",").strip('"').strip("'")
    if not stripped or stripped.startswith("#"):
        return None
    match = DEPENDENCY.match(stripped)
    if match is None:
        return None
    return (
        match.group("name").lower(),
        match.group("operator") or "",
        match.group("version") or "",
    )


def read_pyproject_dependencies() -> list[str]:
    """Read the `project.dependencies` list out of the workshop pyproject.

    Uses `tomllib` where the interpreter has it. On Python 3.10 it falls back to
    slicing the `dependencies = [...]` block out of the text, which is enough
    for a file this repository writes and reviews by hand.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    if tomllib is not None:
        return list(tomllib.loads(text)["project"]["dependencies"])
    block = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", text, re.DOTALL | re.MULTILINE)
    assert block is not None, f"{PYPROJECT} has no project.dependencies list"
    return [line for line in block.group(1).splitlines() if line.strip()]


def read_requires_python() -> str:
    """Read `project.requires-python` out of the workshop pyproject."""
    text = PYPROJECT.read_text(encoding="utf-8")
    if tomllib is not None:
        return str(tomllib.loads(text)["project"]["requires-python"])
    match = re.search(r'^requires-python\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None, f"{PYPROJECT} has no project.requires-python"
    return match.group(1)


def declarations(path: Path) -> dict[str, tuple[str, str]]:
    """Map every package a file declares to its operator and version."""
    if path == PYPROJECT:
        lines = read_pyproject_dependencies()
    else:
        lines = path.read_text(encoding="utf-8").splitlines()
    parsed = {}
    for line in lines:
        entry = parse_declaration(line)
        if entry is not None:
            parsed[entry[0]] = (entry[1], entry[2])
    return parsed


def pins_for(package: str) -> dict[Path, str]:
    """Collect the version every file pins one package to."""
    found = {}
    for path in DECLARATION_FILES:
        entry = declarations(path).get(package)
        if entry is not None:
            found[path] = entry[1]
    return found


def file_id(path: Path) -> str:
    """Name a parametrized case after its file, which two of them share."""
    return f"{path.parent.name}/{path.name}"


@pytest.mark.parametrize("path", DECLARATION_FILES, ids=file_id)
def test_every_declaration_file_is_still_where_the_tests_expect_it(path: Path) -> None:
    assert path.is_file(), f"{path} is missing, so its pins cannot be checked"


@pytest.mark.parametrize("package", PINNED_PACKAGES)
def test_a_package_is_pinned_to_one_version_everywhere_it_appears(package: str) -> None:
    """The point of the pins is that four installs resolve to one version."""
    found = pins_for(package)
    versions = set(found.values())
    assert len(versions) == 1, (
        f"{package} is pinned to more than one version: "
        + ", ".join(f"{path.name} pins {version}" for path, version in found.items())
    )


@pytest.mark.parametrize("package", PINNED_PACKAGES)
def test_a_package_is_pinned_exactly_rather_than_floated(package: str) -> None:
    """A range resolves differently next Tuesday with no change in the repo."""
    for path in DECLARATION_FILES:
        entry = declarations(path).get(package)
        if entry is None:
            continue
        operator, version = entry
        assert operator == "==", (
            f"{path.name} declares {package} with '{operator or 'no operator'}"
            f"{version}'. It has to be pinned with '==' so every install of the "
            "workshop resolves to the same version."
        )


@pytest.mark.parametrize(
    ("path", "expected"),
    tuple(EXPECTED_DECLARATIONS.items()),
    ids=[file_id(path) for path in EXPECTED_DECLARATIONS],
)
def test_a_file_still_declares_every_package_it_is_responsible_for(
    path: Path, expected: set[str]
) -> None:
    """A dropped pin leaves the remaining files agreeing with each other."""
    missing = expected - set(declarations(path))
    assert not missing, (
        f"{path.name} no longer declares {', '.join(sorted(missing))}. Add the "
        "pin back, or update EXPECTED_DECLARATIONS if the file genuinely stopped "
        "needing it."
    )


def test_the_workshop_package_still_installs_on_the_python_the_lab_runs() -> None:
    """The hosted lab image ships Python 3.10 and cannot be changed."""
    requires_python = read_requires_python()
    assert requires_python == EXPECTED_REQUIRES_PYTHON, (
        f"{PYPROJECT.name} asks for Python {requires_python}. The hosted lab runs "
        f"3.10, so this has to stay {EXPECTED_REQUIRES_PYTHON}."
    )
