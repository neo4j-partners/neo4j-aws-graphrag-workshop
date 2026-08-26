# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""One call that gets a workshop notebook ready to run.

Every module notebook opens the same way: find `notebooks/`, put it and the
module's own folder on the import path, read the three `.env`-shaped files,
and quiet the third-party SDK loggers. That was thirty lines of identical
setup at the top of seven notebooks, and it had already drifted apart between
them. It lives here now, so a notebook opens with one call::

    NOTEBOOKS_ROOT, REPO_ROOT, MODULE_DIR = start_module("03-grounded-booking-agent")

The notebook still needs a few lines above that call to find this file before
it can import it, because `workshop` is a directory on `sys.path` rather than
an installed distribution. Those lines are identical in every notebook.

This module stays importable with nothing configured: standard library plus
`python-dotenv`, no AWS or Neo4j client, and nothing that reads a credential
at import. That is why it quiets the loggers itself instead of calling
`workshop.workshop_utils.quiet_logs`: that file imports the Strands SDK at
module scope, and every notebook calls `start_module`, including the one that
checks the environment before anything is installed and the one whose only
dependency is the memory library.

The file is deliberately not named setup.py. This directory is the
distribution root that `pyproject.toml` describes and Module 5 builds into a
wheel, and setuptools would try to execute a file with that name if it
found one here.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv


# The SDKs that log at INFO during ordinary use. Their output buries the
# teaching output in a notebook. `workshop.workshop_utils.quiet_logs` holds the
# same list for code that imports it directly; the two are kept apart on
# purpose, so this file does not pull in that file's Strands import.
NOISY_LOGGERS = (
    "botocore",
    "boto3",
    "neo4j",
    "httpx",
    "opentelemetry",
    "strands",
    "urllib3",
    "anthropic",
)


class ModulePaths(NamedTuple):
    """The three directories a notebook refers to after setup.

    Unpacks in the order the notebooks name them::

        NOTEBOOKS_ROOT, REPO_ROOT, MODULE_DIR = start_module("01-build-graph")
    """

    notebooks_root: Path
    repo_root: Path
    module_dir: Path


def locate_notebooks_root() -> Path:
    """Return the `notebooks/` directory that holds the `workshop` package.

    Supports the three launch directories the workshop documents: the module
    folder, `notebooks/`, and the repository root. `WORKSHOP_NOTEBOOKS_DIR`
    overrides the search for anyone running from somewhere else.

    Raises:
        RuntimeError: if the override does not contain the package, or if no
            supported launch directory does.
    """
    override = os.environ.get("WORKSHOP_NOTEBOOKS_DIR")
    if override:
        candidate = Path(override).expanduser().resolve()
        if (candidate / "workshop").is_dir():
            return candidate
        raise RuntimeError(
            "WORKSHOP_NOTEBOOKS_DIR must contain the workshop package"
        )

    start = Path.cwd().resolve()
    for candidate in (start, start / "notebooks", start.parent):
        if (candidate / "workshop").is_dir():
            return candidate
    raise RuntimeError(
        "Run from the repository root, notebooks/, or this module "
        "directory; or set WORKSHOP_NOTEBOOKS_DIR."
    )


def load_environment(notebooks_root: Path, repo_root: Path) -> None:
    """Read the three `.env`-shaped files the workshop configures itself from.

    `load_dotenv` never overwrites a variable that is already set, so the
    order is the precedence: a value in the environment beats `notebooks/.env`,
    which beats the repository root `.env`, which beats `CONFIG.txt`.
    """
    load_dotenv(notebooks_root / ".env")
    load_dotenv(repo_root / ".env")
    load_dotenv(repo_root / "CONFIG.txt")


def quiet_third_party_logs() -> None:
    """Hold the noisy SDK loggers at WARNING for the rest of the session."""
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.root.setLevel(logging.WARNING)


def start_module(
    module: str,
    *,
    extra_import_dirs: Sequence[str] = (),
    load_env: bool = True,
    quiet_logs: bool = True,
) -> ModulePaths:
    """Prepare the kernel for one module notebook and return its directories.

    Args:
        module: the module folder's name under `notebooks/`, for example
            `"03-grounded-booking-agent"`.
        extra_import_dirs: other module folders this notebook imports from,
            named the same way. Module 1 passes `"02-connected-context"`,
            which holds the extraction code both modules share. A directory
            listed here takes import precedence over the module's own folder,
            which is the order the notebooks had before this file existed.
        load_env: read the `.env`-shaped files. Module 1.0 turns this off
            because loading them is the step it is teaching.
        quiet_logs: hold the third-party SDK loggers at WARNING so notebook
            output stays readable.

    Returns:
        The notebooks root, the repository root, and this module's folder.

    Raises:
        RuntimeError: if `notebooks/` cannot be found, or if `module` names a
            folder that is not there.
    """
    notebooks_root = locate_notebooks_root()
    repo_root = notebooks_root.parent
    module_dir = notebooks_root / module
    if not module_dir.is_dir():
        raise RuntimeError(f"No module folder named {module} in {notebooks_root}")

    extra_dirs = [notebooks_root / name for name in extra_import_dirs]
    missing = [str(path) for path in extra_dirs if not path.is_dir()]
    if missing:
        raise RuntimeError("No module folder named " + ", ".join(missing))

    # Inserted at the front one after another, so the last one inserted is
    # searched first: extras, then the module's own folder, then the shared
    # package. Module 1 relies on that order to import `graph_builder` from
    # `02-connected-context`.
    for path in (notebooks_root, module_dir, *extra_dirs):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))

    if load_env:
        load_environment(notebooks_root, repo_root)

    if quiet_logs:
        quiet_third_party_logs()

    return ModulePaths(notebooks_root, repo_root, module_dir)
