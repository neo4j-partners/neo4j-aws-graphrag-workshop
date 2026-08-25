# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Keep every participant-facing chat-model reference on the validated pin."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
RETIRED_MODEL_ID = "us.anthropic.claude-sonnet-5"

ACTIVE_MODEL_SURFACES = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "notebooks" / "workshop" / "bedrock_providers.py",
    REPO_ROOT
    / "notebooks"
    / "03-grounded-booking-agent"
    / "3.1_grounded_booking_agent.ipynb",
    REPO_ROOT / "site" / "content" / "setup" / "index.en.md",
    REPO_ROOT
    / "site"
    / "content"
    / "setup"
    / "own-account-setup"
    / "index.en.md",
)


def test_active_surfaces_use_the_validated_sonnet_model() -> None:
    for path in ACTIVE_MODEL_SURFACES:
        text = path.read_text(encoding="utf-8")
        assert MODEL_ID in text, path
        assert RETIRED_MODEL_ID not in text, path


def test_provider_default_is_the_validated_sonnet_model() -> None:
    provider = ACTIVE_MODEL_SURFACES[1].read_text(encoding="utf-8")
    assert f'DEFAULT_MODEL_ID = "{MODEL_ID}"' in provider


def test_ingest_prints_the_complete_bedrock_error() -> None:
    builder = (
        REPO_ROOT / "notebooks" / "02-connected-context" / "graph_builder.py"
    ).read_text(encoding="utf-8")
    assert 'print(f"{prefix}... ❌ {exc}", flush=True)' in builder
    assert "str(exc)[:80]" not in builder
