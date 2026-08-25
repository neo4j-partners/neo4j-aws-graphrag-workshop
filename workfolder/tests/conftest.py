# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Make repository scripts importable by maintenance tests outside `setup/`.

`setup/` is a directory of scripts rather than a package, so these tests import
`check_repo`, `verify_setup`, and `run_notebooks` by name. The shared
`workshop` package is added the same way the scripts and notebooks add it, so a
test can import a fixture constant without an installed distribution.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_DIR = REPO_ROOT / "setup"
QUALITY_DIR = REPO_ROOT / "workfolder" / "maintenance" / "quality"
RELEASE_DIR = REPO_ROOT / "workfolder" / "maintenance" / "release"
NOTEBOOKS = REPO_ROOT / "notebooks"

for entry in (SETUP_DIR, QUALITY_DIR, RELEASE_DIR, NOTEBOOKS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
