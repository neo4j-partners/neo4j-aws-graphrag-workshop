# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Prove every `verify_setup` judgement in both directions.

A setup check is only worth running if it fails when the environment is wrong.
These tests hand each judgement the value a healthy service returns and assert
silence, then hand it the values a broken one returns and assert a specific
complaint. No credentials, no network, no graph.

Run them with:

    uv run --with pytest --with neo4j --with python-dotenv pytest workfolder/tests/
"""

from __future__ import annotations

import pytest

import verify_setup
from workshop.fixtures import HERO_ADDRESS, HERO_NAME


# --------------------------------------------------------------------------
# Interpreter
# --------------------------------------------------------------------------


def test_current_interpreter_is_accepted() -> None:
    assert verify_setup.python_problems() == []


def test_old_interpreter_is_rejected() -> None:
    problems = verify_setup.python_problems((3, 9))
    assert len(problems) == 1
    assert "3.9" in problems[0]


# --------------------------------------------------------------------------
# Dependencies
# --------------------------------------------------------------------------


def test_importable_module_produces_no_problem() -> None:
    assert verify_setup.import_problems((("json", "the standard library"),)) == []


def test_missing_module_names_its_distribution() -> None:
    problems = verify_setup.import_problems(
        (("no_such_workshop_module", "a package that does not exist"),)
    )
    assert len(problems) == 1
    assert "no_such_workshop_module" in problems[0]
    assert "a package that does not exist" in problems[0]


def test_every_module_the_workshop_needs_is_declared() -> None:
    """The declared list is the one the notebooks actually import."""
    declared = {name for name, _ in verify_setup.REQUIRED_MODULES}
    assert {"boto3", "dotenv", "neo4j", "workshop.contracts"} <= declared


# --------------------------------------------------------------------------
# Neo4j settings
# --------------------------------------------------------------------------


def test_complete_settings_are_accepted() -> None:
    env = {"NEO4J_URI": "neo4j+s://example", "NEO4J_PASSWORD": "secret"}
    assert verify_setup.settings_problems(env) == []


@pytest.mark.parametrize("missing", ["NEO4J_URI", "NEO4J_PASSWORD"])
def test_each_required_setting_is_missed_when_absent(missing: str) -> None:
    env = {"NEO4J_URI": "neo4j+s://example", "NEO4J_PASSWORD": "secret"}
    env.pop(missing)
    problems = verify_setup.settings_problems(env)
    assert len(problems) == 1
    assert missing in problems[0]


def test_empty_setting_counts_as_missing() -> None:
    env = {"NEO4J_URI": "", "NEO4J_PASSWORD": "secret"}
    assert verify_setup.settings_problems(env) != []


# --------------------------------------------------------------------------
# AWS identity
# --------------------------------------------------------------------------


GOOD_IDENTITY = {
    "Account": "123456789012",
    "Arn": "arn:aws:sts::123456789012:assumed-role/workshop/participant",
    "UserId": "AROAEXAMPLE:participant",
}


def test_real_identity_is_accepted() -> None:
    assert verify_setup.identity_problems(GOOD_IDENTITY) == []


def test_absent_identity_is_rejected() -> None:
    assert verify_setup.identity_problems(None) != []
    assert verify_setup.identity_problems({}) != []


def test_short_account_id_is_rejected() -> None:
    identity = GOOD_IDENTITY | {"Account": "12345"}
    assert any("12 digits" in problem for problem in verify_setup.identity_problems(identity))


def test_non_arn_caller_is_rejected() -> None:
    identity = GOOD_IDENTITY | {"Arn": "not-an-arn"}
    assert any("arn:aws" in problem for problem in verify_setup.identity_problems(identity))


# --------------------------------------------------------------------------
# The hero hotel. This is the check the whole script exists for.
# --------------------------------------------------------------------------


HERO_RECORD = {"name": HERO_NAME, "address": HERO_ADDRESS}


def test_restored_graph_is_accepted() -> None:
    assert verify_setup.hero_problems([HERO_RECORD]) == []


def test_empty_graph_is_rejected() -> None:
    """The failure this check exists for: a dump that never restored."""
    problems = verify_setup.hero_problems([])
    assert len(problems) == 1
    assert HERO_NAME in problems[0]


def test_wrong_address_is_rejected() -> None:
    """A graph holding a different corpus under the same hotel name."""
    record = HERO_RECORD | {"address": "1 Somewhere Else, Cairo, Egypt"}
    problems = verify_setup.hero_problems([record])
    assert len(problems) == 1
    assert HERO_ADDRESS in problems[0]


def test_missing_address_property_is_rejected() -> None:
    problems = verify_setup.hero_problems([{"name": HERO_NAME}])
    assert len(problems) == 1


def test_duplicated_hero_is_rejected() -> None:
    """Two nodes with one name means the build ran twice, not that it worked."""
    problems = verify_setup.hero_problems([HERO_RECORD, HERO_RECORD])
    assert len(problems) == 1
    assert "expected 1" in problems[0]


# --------------------------------------------------------------------------
# Bedrock
# --------------------------------------------------------------------------


def test_correct_chat_answer_is_accepted() -> None:
    assert verify_setup.chat_problems("4") == []


def test_wrong_chat_answer_is_rejected() -> None:
    assert verify_setup.chat_problems("5") != []


@pytest.mark.parametrize("text", [None, "", "   "])
def test_empty_chat_answer_is_rejected(text: str | None) -> None:
    assert verify_setup.chat_problems(text) != []


def test_contract_width_embedding_is_accepted() -> None:
    assert verify_setup.embedding_problems("model", [0.1] * 1024, 1024) == []


def test_wrong_width_embedding_is_rejected() -> None:
    problems = verify_setup.embedding_problems("model", [0.1] * 512, 1024)
    assert len(problems) == 1
    assert "512" in problems[0] and "1024" in problems[0]


def test_absent_embedding_is_rejected() -> None:
    assert verify_setup.embedding_problems("model", None, 1024) != []
    assert verify_setup.embedding_problems("model", [], 1024) != []


def test_non_numeric_embedding_is_rejected() -> None:
    vector = [0.1] * 1023 + ["nan"]
    assert verify_setup.embedding_problems("model", vector, 1024) != []


# --------------------------------------------------------------------------
# The runner around the checks
# --------------------------------------------------------------------------


def test_an_unexpected_exception_becomes_a_reported_problem() -> None:
    """A traceback out of a setup script hides every check after it."""

    def explode() -> list[str]:
        raise RuntimeError("the socket closed")

    problems = verify_setup.run_check(explode)
    assert problems == ["RuntimeError: the socket closed"]


def test_a_blocking_failure_stops_the_run(capsys, monkeypatch) -> None:
    """Checks after a blocking failure report as not run, not as passing."""
    monkeypatch.setattr(verify_setup, "load_environment", list)
    monkeypatch.setattr(
        verify_setup,
        "CHECKS",
        (
            ("first", lambda: ["broken"], True),
            ("second", lambda: [], False),
        ),
    )
    assert verify_setup.main() == 1
    output = capsys.readouterr().out
    assert "FAIL  first" in output
    assert "----  second (not run" in output
    assert "ok    second" not in output


def test_a_clean_run_exits_zero(capsys, monkeypatch) -> None:
    monkeypatch.setattr(verify_setup, "load_environment", list)
    monkeypatch.setattr(verify_setup, "CHECKS", (("only", lambda: [], False),))
    assert verify_setup.main() == 0
    assert "ok    only" in capsys.readouterr().out
