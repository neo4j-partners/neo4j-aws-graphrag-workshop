# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Keep every participant-facing chat-model reference on the validated pin."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = "us.anthropic.claude-sonnet-4-6"
RETIRED_MODEL_ID = "us.anthropic.claude-sonnet-5"

PROVIDER = REPO_ROOT / "notebooks" / "workshop" / "bedrock_providers.py"
MODULE_3_NOTEBOOK = (
    REPO_ROOT
    / "notebooks"
    / "03-grounded-booking-agent"
    / "3.1_grounded_booking_agent.ipynb"
)

# Surfaces that name the model outright, so the literal has to be current.
LITERAL_MODEL_SURFACES = (
    REPO_ROOT / "README.md",
    PROVIDER,
    REPO_ROOT / "site" / "content" / "setup" / "index.en.md",
    REPO_ROOT / "site" / "content" / "setup" / "own-account-setup" / "index.en.md",
)

# Every surface above, plus those that resolve the model through the provider.
ACTIVE_MODEL_SURFACES = LITERAL_MODEL_SURFACES + (MODULE_3_NOTEBOOK,)


def test_active_surfaces_use_the_validated_sonnet_model() -> None:
    for path in LITERAL_MODEL_SURFACES:
        assert MODEL_ID in path.read_text(encoding="utf-8"), path


def test_no_active_surface_names_the_retired_model() -> None:
    for path in ACTIVE_MODEL_SURFACES:
        assert RETIRED_MODEL_ID not in path.read_text(encoding="utf-8"), path


def test_provider_default_is_the_validated_sonnet_model() -> None:
    provider = PROVIDER.read_text(encoding="utf-8")
    assert f'DEFAULT_MODEL_ID = "{MODEL_ID}"' in provider


def test_module_3_resolves_its_model_through_the_provider() -> None:
    """Module 3 names no model itself, so its pin must come from the provider."""
    notebook = MODULE_3_NOTEBOOK.read_text(encoding="utf-8")
    assert "from workshop.bedrock_providers import default_model_id" in notebook
    assert "MODEL_ID = default_model_id()" in notebook
    assert "model_id=MODEL_ID" in notebook


def test_ingest_prints_the_complete_bedrock_error() -> None:
    builder = (
        REPO_ROOT / "notebooks" / "02-connected-context" / "graph_builder.py"
    ).read_text(encoding="utf-8")
    assert 'print(f"{prefix}... ❌ {exc}", flush=True)' in builder
    assert "str(exc)[:80]" not in builder
