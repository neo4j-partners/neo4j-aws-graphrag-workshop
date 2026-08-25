# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Neo4j connection settings shared by every module that opens a driver.

`NEO4J_USERNAME` defaults to `"neo4j"`, which is what Aura provisions; the older
`NEO4J_USER` spelling is not read. There is no default for `NEO4J_URI` or for
`NEO4J_PASSWORD`. Both are required, and `require_neo4j_env()` raises when either
is missing: a baked-in default password sends a bad credential to the right host,
and a baked-in `bolt://127.0.0.1:7687` sends a good credential to a host that is
not listening, which surfaces as a connection timeout that reads like an Aura
outage.

That check used to run at import. It now runs when a caller asks for it, because
importing a module must not depend on the environment. An import-time raise means
the reservation Lambda dies during cold start rather than inside its handler where
the error can be caught and logged, a missing variable surfaces as an `ImportError`
from a module several imports away from the one being read, and nothing that only
needs a constant can load at all. Callers that cannot proceed without Neo4j call
`require_neo4j_env()` in their setup cell, so a participant still finds out
immediately and sees the check happen instead of it being hidden in an import.
Module 3.1's notebook instead reads the same variables itself and skips its live
cells when they are unset, because it is written to be readable without a
database.

Values are read at call time rather than bound at import, so a `.env` the caller
loads after importing this module is still honoured.
"""

import os

# Aura's default database is always `neo4j`, and a participant whose .env omits
# the name should not get a different failure in Module 2 than in Module 1. The
# build path defaults it, so the read and write paths default it the same way.
DEFAULT_NEO4J_DATABASE = "neo4j"

# The two with no safe default. `NEO4J_USERNAME` is absent because it has one,
# and `NEO4J_DATABASE` because `graph_database()` defaults it.
REQUIRED_ENV_VARS = ("NEO4J_URI", "NEO4J_PASSWORD")


def require_neo4j_env() -> None:
    """Raise if a required Neo4j setting is missing. Call once during setup.

    Call this from a notebook or script that cannot proceed without Neo4j. Do not
    call it at module scope: a helper that raises on missing credentials makes
    itself unimportable to the Lambda and to anything running offline.
    """
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing required Neo4j environment values: {', '.join(missing)}. "
            "Set them (see .env.example) before running the workshop modules. Neither "
            "has a default, so a missing one fails loudly here instead of sending a "
            "bad credential to Neo4j or a good one to a localhost that is not "
            "listening."
        )


def neo4j_uri() -> str:
    """Return the Neo4j URI, or the empty string when it is unset."""
    return os.environ.get("NEO4J_URI", "")


def neo4j_auth() -> tuple[str, str]:
    """Return the (username, password) pair for the Neo4j driver."""
    return (
        os.environ.get("NEO4J_USERNAME", "neo4j"),
        os.environ.get("NEO4J_PASSWORD", ""),
    )


def graph_database() -> str:
    """Return the Neo4j database every workshop session should open.

    Anything that opens a session or creates an index goes through this, because
    a driver left on its home database while the build writes elsewhere puts the
    data in one place and the indexes in another, and that reads back as empty
    results with no error.
    """
    return os.environ.get("NEO4J_DATABASE") or DEFAULT_NEO4J_DATABASE
