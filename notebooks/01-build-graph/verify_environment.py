"""Setup helpers for ``1.0_verify_environment.ipynb``.

Split out of the notebook so its Step 1 cell reads as validation rather
than as environment bootstrapping. ``locate_notebooks_root()`` stays
inline in the notebook rather than moving here: it is the same function
``1.1_build_graph.ipynb`` (and every other module's ``*.1`` notebook)
defines inline, and ``tests/test_path_contract.py`` extracts it verbatim
from each of those notebooks. Only the genuinely separable bearer-token
and dotenv-loading pieces live here.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BEARER_VARIABLE = "AWS_BEARER_TOKEN_BEDROCK"


def load_environment_files(notebooks_root: Path, repo_root: Path) -> None:
    """Load the three .env-shaped files the workshop reads configuration from."""
    load_dotenv(notebooks_root / ".env")
    load_dotenv(repo_root / ".env")
    load_dotenv(repo_root / "CONFIG.txt")


def check_bearer_token(bearer_variable: str = BEARER_VARIABLE) -> None:
    """Print whether a Bedrock bearer token is set, and stop on an empty one.

    An empty value is worse than an absent one: botocore stops falling back
    to the account's own credentials once the variable exists at all, so a
    ``CONFIG.txt`` line uncommented with nothing pasted after the equals
    sign silently breaks every Bedrock call the notebook makes next.
    """
    bearer_token = os.environ.get(bearer_variable)
    if bearer_token is None:
        print(f"{bearer_variable} is not set.")
        print("Bedrock calls will use this account's own credentials.")
    elif not bearer_token.strip():
        raise RuntimeError(
            f"{bearer_variable} is set to an empty value. The CONFIG.txt line was "
            "uncommented but no key was pasted in. Paste the Bedrock API key after "
            "the equals sign, or comment the line back out. An empty value is "
            "worse than no value at all, because botocore stops falling back to "
            "this account's normal credentials once the variable exists."
        )
    else:
        print(
            f"{bearer_variable} is set: {len(bearer_token)} characters, "
            f"ending {bearer_token[-4:]}."
        )
        print("Bedrock calls will use this key instead of this account's credentials.")
