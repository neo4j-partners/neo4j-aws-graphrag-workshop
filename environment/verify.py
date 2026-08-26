# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Live checks that a participant's credentials actually reach the services.

Used for: the one required participant readiness check before Module 1.

`check_repo.py` is the offline gate and needs nothing. This is its counterpart:
it needs the environment, and it is the one command the setup page tells a
participant to run before opening the first notebook.

Every check here asserts a specific value comes back, never that no exception
was raised. A connectivity probe that passes because it found nothing to look
at is worse than no probe, because it converts an unusable environment into a
green tick. So the Neo4j check does not count nodes or ask whether a query ran;
it reads one known hotel out of the shipped dump and compares its address to
the fixture constant that Module 3 later depends on. The two Bedrock checks
compare the returned vector width to the frozen contract width, and the chat
check compares the answer to a question with one right answer.

The hero constants are imported from `workshop.fixtures` rather than restated.
A copy here would agree with the graph exactly until someone changed one of
them, and the whole point of this file is catching that kind of divergence
before a room of participants does.

Run it after installing the workshop requirements:

    cd notebooks
    uv venv && uv pip install -r requirements.txt
    uv run python ../environment/verify.py
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS = REPO_ROOT / "notebooks"

# The shared package is imported the way the notebooks import it, from the
# `notebooks/` directory, rather than installed. Putting it on the path here is
# what lets this script be run from anywhere in the tree.
if str(NOTEBOOKS) not in sys.path:
    sys.path.insert(0, str(NOTEBOOKS))

# The lowest interpreter the shared modules parse on. The Vocareum lab image
# runs CPython 3.10.14, so the shared modules stay clear of 3.11-only syntax
# and typing features.
MINIMUM_PYTHON = (3, 10)

# One question with one right answer, so the chat check asserts a value instead
# of asserting that some text came back. Any model capable of running this
# workshop answers it; a model the account cannot reach raises AccessDenied
# long before the answer is compared.
CHAT_PROBE = "What is 2 + 2? Reply with the digit only."
CHAT_EXPECTED_ANSWER = "4"

# The module names the workshop actually imports, with the distribution that
# provides each one. Import names and distribution names differ often enough
# that a participant reading `No module named 'dotenv'` needs to be told which
# line of `requirements.txt` did not land.
REQUIRED_MODULES: tuple[tuple[str, str], ...] = (
    ("boto3", "boto3"),
    ("dotenv", "python-dotenv"),
    ("neo4j", "neo4j"),
    ("neo4j_graphrag", "neo4j-graphrag"),
    ("strands", "strands-agents"),
    ("workshop.contracts", "the notebooks/workshop package in this repository"),
)

HERO_QUERY = """
MATCH (hotel:Hotel {name: $name})
RETURN hotel.name AS name, hotel.address AS address
""".strip()


# --------------------------------------------------------------------------
# Pure helpers. Each one takes what a service returned and decides whether it
# is the expected value, so the decision can be tested in both directions
# without credentials.
# --------------------------------------------------------------------------


def python_problems(version: tuple[int, ...] = sys.version_info[:2]) -> list[str]:
    """Report an interpreter older than the shared modules can be parsed by."""
    if tuple(version) < MINIMUM_PYTHON:
        wanted = ".".join(str(part) for part in MINIMUM_PYTHON)
        found = ".".join(str(part) for part in version)
        return [f"Python {wanted} or newer is required; this is {found}"]
    return []


def import_problems(
    modules: Sequence[tuple[str, str]] = REQUIRED_MODULES,
) -> list[str]:
    """Report every workshop dependency that will not import."""
    problems: list[str] = []
    for module_name, provided_by in modules:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # An ImportError, or a broken install of one.
            problems.append(
                f"cannot import {module_name} (provided by {provided_by}): {exc}"
            )
    return problems


def settings_problems(env: Mapping[str, str]) -> list[str]:
    """Report Neo4j settings that have no default and are not set.

    The required tuple is imported rather than restated so this script cannot
    accept a connection the notebooks reject, or reject one they accept.
    """
    from workshop import graph_connection

    missing = [name for name in graph_connection.REQUIRED_ENV_VARS if not env.get(name)]
    if missing:
        return [
            f"{', '.join(missing)} is not set; fill in CONFIG.txt at the "
            "repository root and re-run this script"
        ]
    return []


def identity_problems(identity: Mapping[str, Any] | None) -> list[str]:
    """Report an AWS identity that is absent or does not look like one."""
    if not identity:
        return ["AWS returned no caller identity"]
    problems: list[str] = []
    account = identity.get("Account")
    if not isinstance(account, str) or not account.isdigit() or len(account) != 12:
        problems.append(f"AWS account id is {account!r}, expected 12 digits")
    arn = identity.get("Arn")
    if not isinstance(arn, str) or not arn.startswith("arn:aws"):
        problems.append(f"AWS caller ARN is {arn!r}, expected an arn:aws value")
    return problems


def hero_problems(records: Sequence[Mapping[str, Any]]) -> list[str]:
    """Report a graph that does not hold the hero hotel at its known address.

    This is the check that makes the whole file worth running. The dump either
    restored or it did not, and the difference is one named hotel carrying one
    exact address, not a node count that is plausible at any value.
    """
    from workshop.fixtures import HERO_ADDRESS, HERO_NAME

    if not records:
        return [
            f"the graph has no hotel named {HERO_NAME!r}; the dump did not "
            "restore, or NEO4J_DATABASE names a different database"
        ]
    if len(records) > 1:
        return [
            f"the graph has {len(records)} hotels named {HERO_NAME!r}, expected 1"
        ]
    address = records[0].get("address")
    if address != HERO_ADDRESS:
        return [
            f"{HERO_NAME!r} is at {address!r}, expected {HERO_ADDRESS!r}; the "
            "restored dump is not the one this workshop was written against"
        ]
    return []


def chat_problems(text: str | None) -> list[str]:
    """Report a chat model whose answer is not the one right answer."""
    if not text or not text.strip():
        return ["the chat model returned no text"]
    if CHAT_EXPECTED_ANSWER not in text:
        return [
            f"the chat model answered {text.strip()!r} to {CHAT_PROBE!r}, "
            f"expected {CHAT_EXPECTED_ANSWER!r}"
        ]
    return []


def embedding_problems(
    model_id: str,
    vector: Sequence[float] | None,
    expected_dimensions: int,
) -> list[str]:
    """Report an embedding that is missing or not the contract width."""
    if not vector:
        return [f"{model_id} returned no embedding"]
    if len(vector) != expected_dimensions:
        return [
            f"{model_id} returned {len(vector)} dimensions, "
            f"expected {expected_dimensions}"
        ]
    if not all(isinstance(value, (int, float)) for value in vector):
        return [f"{model_id} returned an embedding that is not numeric"]
    return []


# --------------------------------------------------------------------------
# The checks themselves. Each one calls a service and hands what came back to
# a helper above.
# --------------------------------------------------------------------------


def load_environment() -> list[Path]:
    """Load the settings files the notebooks would find, nearest one winning.

    A notebook runs from inside its module folder, so `load_dotenv()` there
    finds `notebooks/.env` before anything at the repository root. Loading them
    in that order here, and never overriding an already-set value, makes this
    script read exactly the settings the notebooks will read.

    `CONFIG.txt` is last because it is the participant-facing file. A `.env`
    is a maintainer's own override, so it wins where both are present.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        # Reported properly by the dependency check, which runs before
        # anything reads a setting. Raising here would replace that report
        # with a traceback and hide every check after it.
        return []

    loaded: list[Path] = []
    for candidate in (
        NOTEBOOKS / ".env",
        REPO_ROOT / ".env",
        REPO_ROOT / "CONFIG.txt",
    ):
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            loaded.append(candidate)
    return loaded


def check_python() -> list[str]:
    """The interpreter is new enough for the shared modules."""
    return python_problems()


def check_imports() -> list[str]:
    """Every dependency the notebooks import is installed."""
    return import_problems()


def check_settings() -> list[str]:
    """The Neo4j settings with no default are set."""
    return settings_problems(os.environ)


def check_aws_credentials() -> list[str]:
    """AWS credentials resolve to a real account in the workshop region."""
    import boto3

    from workshop.aws_region import configure_aws_region

    region = configure_aws_region()
    client = boto3.client("sts", region_name=region)
    return identity_problems(client.get_caller_identity())


def check_neo4j_hero_hotel() -> list[str]:
    """Neo4j is reachable and holds the hero hotel at its known address."""
    from neo4j import GraphDatabase

    from workshop import graph_connection
    from workshop.fixtures import HERO_NAME

    driver = GraphDatabase.driver(
        graph_connection.neo4j_uri(),
        auth=graph_connection.neo4j_auth(),
        notifications_min_severity="OFF",
    )
    try:
        driver.verify_connectivity()
        with driver.session(database=graph_connection.graph_database()) as session:
            records = [
                record.data()
                for record in session.run(HERO_QUERY, name=HERO_NAME)
            ]
    finally:
        driver.close()
    return hero_problems(records)


def check_bedrock_chat_model() -> list[str]:
    """The workshop chat model is reachable and answers correctly."""
    import boto3

    from workshop.aws_region import aws_region
    from workshop.bedrock_providers import default_model_id

    client = boto3.client("bedrock-runtime", region_name=aws_region())
    response = client.converse(
        modelId=default_model_id(),
        messages=[{"role": "user", "content": [{"text": CHAT_PROBE}]}],
        inferenceConfig={"maxTokens": 16},
    )
    blocks = response["output"]["message"]["content"]
    # Reasoning models put a reasoningContent block ahead of the answer, so
    # take the first block that carries text rather than assuming index 0.
    text = next((block["text"] for block in blocks if "text" in block), None)
    return chat_problems(text)


def check_bedrock_chunk_embeddings() -> list[str]:
    """The chunk embedding model returns the frozen contract width.

    This goes through the workshop's own embedder rather than a hand-rolled
    request, so it proves the installed package can embed, not merely that the
    account can call Bedrock.
    """
    from workshop.bedrock_providers import BedrockEmbeddings
    from workshop.retrieval_contract import (
        EMBEDDING_DIMENSIONS,
        EMBEDDING_MODEL_ID,
    )

    vector = BedrockEmbeddings().embed_query("a hotel with a pool and a spa")
    return embedding_problems(EMBEDDING_MODEL_ID, vector, EMBEDDING_DIMENSIONS)


def check_bedrock_memory_embeddings() -> list[str]:
    """The memory embedding model Module 6 uses is reachable at its width."""
    import boto3

    from workshop.aws_region import aws_region
    from workshop.retrieval_contract import (
        MEMORY_EMBEDDING_DIMENSIONS,
        MEMORY_EMBEDDING_MODEL,
    )

    client = boto3.client("bedrock-runtime", region_name=aws_region())
    response = client.invoke_model(
        modelId=MEMORY_EMBEDDING_MODEL,
        body=json.dumps(
            {
                "inputText": "a guest who prefers a quiet room",
                "dimensions": MEMORY_EMBEDDING_DIMENSIONS,
                "normalize": True,
            }
        ),
        contentType="application/json",
        accept="application/json",
    )
    vector = json.loads(response["body"].read()).get("embedding")
    return embedding_problems(
        MEMORY_EMBEDDING_MODEL, vector, MEMORY_EMBEDDING_DIMENSIONS
    )


# A blocking check is one whose failure makes every later result meaningless.
# Without the packages installed nothing below can even import, and without the
# Neo4j settings the connection check would report a made-up problem.
Check = tuple[str, Callable[[], list[str]], bool]

CHECKS: tuple[Check, ...] = (
    ("python interpreter is supported", check_python, True),
    ("workshop dependencies import", check_imports, True),
    ("neo4j settings are present", check_settings, True),
    ("aws credentials resolve", check_aws_credentials, False),
    ("neo4j returns the hero hotel", check_neo4j_hero_hotel, False),
    ("bedrock chat model answers", check_bedrock_chat_model, False),
    ("bedrock chunk embeddings are 1024-wide", check_bedrock_chunk_embeddings, False),
    ("bedrock memory embeddings are 1024-wide", check_bedrock_memory_embeddings, False),
)


def run_check(check: Callable[[], list[str]]) -> list[str]:
    """Run one check, turning an unexpected exception into a reported problem.

    A traceback out of a setup script tells a participant nothing they can act
    on, and it hides every check that would have run after it.
    """
    try:
        return check()
    except Exception as exc:
        return [f"{type(exc).__name__}: {exc}"]


def main() -> int:
    loaded = load_environment()
    for path in loaded:
        print(f"      loaded {path.relative_to(REPO_ROOT)}")
    if not loaded:
        print(
            "      no CONFIG.txt or .env file found; reading settings from "
            "the environment"
        )

    failures = 0
    blocked = False
    for name, check, blocking in CHECKS:
        if blocked:
            print(f"----  {name} (not run; fix the failure above first)")
            continue
        problems = run_check(check)
        if problems:
            failures += len(problems)
            print(f"FAIL  {name}")
            for problem in problems:
                print(f"        {problem}")
            if blocking:
                blocked = True
        else:
            print(f"ok    {name}")

    print()
    if failures:
        print(f"{failures} problem(s) found. The workshop will not run until they are fixed.")
        return 1
    print("Your environment is ready. Open the Module 1 notebook.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
