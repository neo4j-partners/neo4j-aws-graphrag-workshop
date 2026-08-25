# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Offline tests for the one-command candidate validation workflow."""

from __future__ import annotations

import subprocess
from pathlib import Path

import validate_prebuilt_candidate

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "workfolder"
    / "maintenance"
    / "release"
    / "validate_prebuilt_candidate.sh"
)


def _passing_facts() -> dict[str, object]:
    return {
        "counts": dict(validate_prebuilt_candidate.EXPECTED_COUNTS),
        "invalid_documents": [],
        "invalid_hotels": [],
        "invalid_offers": [],
        "historical_sources": [
            {"filename": filename, "document_count": 1, "hotel_count": 1}
            for filename in (
                validate_prebuilt_candidate.HISTORICAL_MISSING_HOTEL_SOURCES
            )
        ],
        "duplicate_names": [
            {
                "name": name,
                "expected_filenames": list(filenames),
                "hotel_count": 2,
                "actual_filenames": list(filenames),
            }
            for name, filenames in (
                validate_prebuilt_candidate.CROSS_CITY_DUPLICATE_HOTEL_NAMES.items()
            )
        ],
        "chicago_wifi": [
            {
                "filename": filename,
                "hotel_count": 1,
                "wifi_element_ids": ["shared-wifi-id"],
            }
            for filename in validate_prebuilt_candidate.CHICAGO_SOURCES
        ],
    }


def test_release_contract_accepts_all_expected_facts() -> None:
    assert (
        validate_prebuilt_candidate.candidate_contract_problems(_passing_facts()) == []
    )


def test_release_contract_reports_counts_provenance_and_identity_defects() -> None:
    facts = _passing_facts()
    facts["counts"]["documents"] = 294
    facts["invalid_documents"] = [
        {"filename": "broken.txt", "chunk_count": 1, "hotel_count": 0}
    ]
    facts["invalid_hotels"] = [
        {
            "hotel": "Orphan",
            "document_count": 0,
            "source_filenames": [],
        }
    ]
    facts["invalid_offers"] = [
        {
            "relationship_id": "offer-id",
            "source_labels": [],
            "target_labels": ["Amenity"],
            "offer_source": None,
            "document_count": 0,
            "source_filenames": [],
        }
    ]
    facts["historical_sources"][0]["hotel_count"] = 0
    facts["duplicate_names"][0]["hotel_count"] = 1
    facts["chicago_wifi"][1]["wifi_element_ids"] = ["other-wifi-id"]

    problems = validate_prebuilt_candidate.candidate_contract_problems(facts)

    assert any("documents is 294" in problem for problem in problems)
    assert any(
        "broken.txt has 1 Chunks and 0 Hotels" in problem for problem in problems
    )
    assert any("Orphan resolves to 0 Documents" in problem for problem in problems)
    assert any("OFFERS_AMENITY offer-id" in problem for problem in problems)
    assert any("historical source hotel-austin-002.txt" in p for p in problems)
    assert any("duplicate-name pair 'Riverside Crossing Suites'" in p for p in problems)
    assert any("expected one shared node" in problem for problem in problems)


def test_shell_command_exposes_offline_help_without_candidate_or_docker() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "[candidate.dump]" in result.stdout
    assert "NEO4J_IMAGE" in result.stdout


def test_shell_contract_uses_isolated_resources_and_both_validators() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'RUN_ID="candidate-validate-$$"' in script
    assert "-p 127.0.0.1::7687" in script
    assert 'docker volume rm "$VOLUME"' in script
    assert 'validate_graph_amenities.py" --mode prebuilt' in script
    assert "validate_prebuilt_candidate.py" in script
    assert "prepare_graph.py" not in script
    assert "BEDROCK" not in script
