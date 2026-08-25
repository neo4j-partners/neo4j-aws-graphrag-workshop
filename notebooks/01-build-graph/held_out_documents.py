# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""The five hotel documents held out of the shipped dump.

The dump ships every source document except these five. Module 1 extracts them
live, so a participant's own work joins the graph and stays there for the rest
of the workshop. Nothing collides, because the dump has never seen them, and
nothing has to be deleted afterwards to make room.

They were chosen because no authored file in either repository names their
cities, none appear in the lite sample `graph_config.select_lite_files` builds,
and each of those cities keeps its `-001` hotel in the dump. The Cairo fixture
hotel is deliberately not among them: Module 3's hero question targets it, and
that question must not depend on a participant's extraction having succeeded.

Until this file existed the list lived only in the planning record, which meant
the one fact Module 1 cannot be written without was not in the tree at all.
"""

from pathlib import Path
from zipfile import ZipFile

from graph_config import HELD_OUT_DOCUMENTS

# Resolve both paths from this helper, not from the process working directory.
# That keeps the notebook, the setup loader, and tests on the same files when
# they start at the repository root, notebooks/, or this module directory.
MODULE_DIR = Path(__file__).resolve().parent
NOTEBOOKS_ROOT = MODULE_DIR.parent
CORPUS_ARCHIVE = NOTEBOOKS_ROOT / "02-connected-context" / "hotel-faqs.zip"
DATA_DIR = MODULE_DIR / "data"


def extract_held_out(
    archive: Path = CORPUS_ARCHIVE,
    data_dir: Path = DATA_DIR,
) -> list[Path]:
    """Unpack the five held-out documents and return their paths in order."""
    if not archive.exists():
        raise FileNotFoundError(
            f"The source corpus is missing: {archive.resolve()}. It ships in "
            "the repository next to prepare_graph.py."
        )

    data_dir.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive) as corpus:
        available = set(corpus.namelist())
        missing = [name for name in HELD_OUT_DOCUMENTS if name not in available]
        if missing:
            raise FileNotFoundError(
                f"{archive} does not contain {', '.join(missing)}. The held-out "
                "list and the shipped corpus have drifted apart."
            )
        for name in HELD_OUT_DOCUMENTS:
            (data_dir / name).write_bytes(corpus.read(name))

    return [data_dir / name for name in HELD_OUT_DOCUMENTS]
