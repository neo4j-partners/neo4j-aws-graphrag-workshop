# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Build-time settings that belong to Module 1 alone.

Chunk sizing, the extraction token ceiling, and the lite document sample only
matter while the graph is being built, so they stay here rather than in the
shared `workshop` package. The things later modules also need moved out:

* the pinned extraction schema is `workshop.graph_schema`
* the Neo4j connection is `workshop.graph_connection`
* the embedding and index names are `workshop.retrieval_contract`

Import those from `workshop` directly. This module deliberately does not
re-export them, so there is one obvious place each name comes from.
"""

from collections import defaultdict
from pathlib import Path

from workshop.retrieval_setup import REQUIRED_SOURCE_FILES

# Source documents top out at ~7.4 KB. A chunk this size keeps each hotel in a
# single chunk, so the hotel's name, address and rating are extracted together
# with its rooms, policies, and services instead of being split across prompts.
CHUNK_SIZE = 12000
CHUNK_OVERLAP = 0

# A whole hotel in one chunk produces a large extraction payload. The 4096
# default truncates the JSON mid-object and the chunk is dropped.
EXTRACTION_MAX_TOKENS = 16000


# ---------------------------------------------------------------------------
# Document selection
# ---------------------------------------------------------------------------

# These documents are extracted live by Module 1 and therefore must not be in
# the prebuilt graph artifact. This build-time module is the source of truth
# for both facilitator selection and the learner-facing extraction helper.
HELD_OUT_DOCUMENTS: tuple[str, ...] = (
    "hotel-tokyo-002.txt",
    "hotel-sydney-002.txt",
    "hotel-riodejaneiro-002.txt",
    "hotel-capetown-002.txt",
    "hotel-prague-002.txt",
)


def _city_of(filename: str) -> str:
    """Extract the city from a `hotel-<city>-<nnn>.txt` filename."""
    parts = Path(filename).stem.split("-")
    return "-".join(parts[1:-1]) if len(parts) > 2 else Path(filename).stem


def select_lite_files(data_dir: str | Path, max_docs: int) -> list[str]:
    """Return a city-stratified sample of `max_docs` FAQ filenames.

    Every source in the shared retrieval contract comes first. The remainder
    is filled round-robin across cities, so the sample spans the corpus while
    preserving the exact document count.
    """
    by_city: dict[str, list[str]] = defaultdict(list)
    for path in sorted(Path(data_dir).glob("*.txt")):
        by_city[_city_of(path.name)].append(path.name)

    available = {name for names in by_city.values() for name in names}
    missing = sorted(set(REQUIRED_SOURCE_FILES) - available)
    if missing:
        raise ValueError("required lite sources are missing: " + ", ".join(missing))
    if max_docs < len(REQUIRED_SOURCE_FILES):
        raise ValueError(
            f"lite sample size {max_docs} is smaller than the "
            f"{len(REQUIRED_SOURCE_FILES)} required sources"
        )

    picked = list(REQUIRED_SOURCE_FILES)
    picked_set = set(picked)

    depth = max((len(names) for names in by_city.values()), default=0)
    for i in range(depth):
        for city in sorted(by_city):
            if len(picked) >= max_docs:
                return picked[:max_docs]
            names = by_city[city]
            if i < len(names) and names[i] not in picked_set:
                picked.append(names[i])
                picked_set.add(names[i])

    raise ValueError(
        f"lite sample found only {len(picked)} source documents, "
        f"expected {max_docs}"
    )
