# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Load the five held-out hotels without opening Module 1's notebook.

Used for: maintainer-only preparation of a restored graph for Modules 2–6.

The shipped dump omits five hotel documents so Module 1 can extract them live
and show a participant a real `SimpleKGPipeline` run. That is the right
experience in a workshop room, but it is friction everywhere else: restoring
the dump for a live test of Modules 2 through 6, or for CI, means either
running Module 1's notebook end to end just to get its side effect, or the
graph is left five hotels short of what those modules expect and every later
check that counts documents or looks up a held-out hotel fails for a reason
that has nothing to do with what is actually being tested.

This script is that side effect on its own. It calls the exact same
`extract_held_out()` and `run_additive_build()` that Module 1's notebook cells
7 and 13 call, so there is one build path, not two that can drift apart. Like
the notebook cell, it clears any prior copy of the five documents before
ingesting, so re-running it against a graph it already loaded is harmless.

This is not a substitute for running Module 1's notebook. It reuses Module
1's build machinery but not Module 1's own notebook cells, so it cannot catch
a regression in the notebook itself, only in the machinery underneath it. Use
it to get a freshly restored graph ready for Modules 2 through 6 without
paying for a live extraction on every run; use the notebook when what you are
actually testing is Module 1.

Run it after installing the workshop requirements:

    cd notebooks
    uv venv && uv pip install -r requirements.txt
    uv run python ../tools/release/load_held_out_hotels.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = REPO_ROOT / "notebooks"
MODULE_1 = NOTEBOOKS / "01-build-graph"
MODULE_2 = NOTEBOOKS / "02-connected-context"

# Mirrors notebook cell 2's sys.path setup: the shared `workshop` package lives
# at the `notebooks/` root, and `graph_builder.py`/`graph_config.py` live in
# Module 2's folder because Module 1 builds the graph that Module 2 first
# queries. `held_out_documents.py` lives in Module 1's own folder. The
# notebook gets all three for free from its own working directory; a script
# run from anywhere has to add them explicitly.
for _path in (NOTEBOOKS, MODULE_2, MODULE_1):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")

    from workshop.graph_connection import require_neo4j_env

    require_neo4j_env()

    from graph_builder import run_additive_build
    from held_out_documents import extract_held_out

    paths = extract_held_out()

    return asyncio.run(
        run_additive_build(paths, "Loading the five held-out hotels")
    )


if __name__ == "__main__":
    raise SystemExit(main())
