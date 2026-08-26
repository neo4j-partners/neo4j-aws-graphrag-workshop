# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Regression coverage for Module 3's availability abstention check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# These tests drive a Module 3 notebook cell that no longer exists. The old
# notebook graded the wording of the model's answer and kept that check in a
# cell containing `fabricated_availability_claims`. Phase 1 replaced it: the
# notebook now reads the structured `grounding_result` returned by the read
# tools and asserts on `missing_fact == "live_room_availability"`, so the
# abstention check no longer depends on which phrase the model chose. There is
# no cell left for `availability_assertion_source` to find, so every test in
# this file raises `StopIteration` out of that helper when it runs. The live
# coverage for the new verdict lives in `tests/test_agent_tools.py`. Do not
# repair this file: it is scheduled for removal in Phase 3.
pytestmark = pytest.mark.skip(
    reason=(
        "Module 3 no longer grades the model's answer wording. The availability "
        "abstention assertion moved to the structured grounding verdict "
        "(grounding_result with missing_fact == 'live_room_availability'), so the "
        "notebook cell these tests execute no longer exists. This file is "
        "scheduled for removal in Phase 3; delete it rather than fixing it."
    )
)

NOTEBOOK = (
    Path(__file__).parents[1]
    / "notebooks"
    / "03-grounded-booking-agent"
    / "3.1_grounded_booking_agent.ipynb"
)


def availability_assertion_source() -> str:
    """Load the participant-facing availability assertion cell."""
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return next(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
        and "fabricated_availability_claims" in "".join(cell["source"])
    )


def run_availability_assertion(response: str) -> None:
    """Execute the notebook assertion with a deterministic agent response."""
    namespace = {
        "AVAILABILITY_QUESTION": "Are rooms available next weekend?",
        "RETRIEVAL_READY": True,
        "grounded_agent": lambda _question: response,
    }
    exec(availability_assertion_source(), namespace)  # noqa: S102


@pytest.mark.parametrize(
    "response",
    (
        "I cannot confirm or guarantee that rooms are available next weekend.",
        "It cannot be determined whether rooms are available next weekend.",
        "Room availability cannot be confirmed for next weekend.",
    ),
)
def test_availability_assertion_allows_negated_claim(response: str) -> None:
    run_availability_assertion(response)


def test_availability_assertion_rejects_explicit_affirmative_claim() -> None:
    with pytest.raises(AssertionError):
        run_availability_assertion(
            "Yes, rooms are available next weekend, although I cannot confirm inventory."
        )
