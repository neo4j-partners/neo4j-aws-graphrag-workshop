# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Make repository scripts importable by the maintenance tests.

`environment/` and `tools/` are directories of scripts rather than packages, so
these tests import `check_repo`, `verify`, and `run_notebooks` by name. The
shared `workshop` package is added the same way the scripts and notebooks add
it, so a test can import a fixture constant without an installed distribution.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_DIR = REPO_ROOT / "environment"
QUALITY_DIR = REPO_ROOT / "tools" / "quality"
RELEASE_DIR = REPO_ROOT / "tools" / "release"
NOTEBOOKS = REPO_ROOT / "notebooks"

for entry in (ENVIRONMENT_DIR, QUALITY_DIR, RELEASE_DIR, NOTEBOOKS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))
