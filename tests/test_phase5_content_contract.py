"""Focused content gates for the connected-context learner story."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

LEARNER_FILES = (
    Path("README.md"),
    Path("notebooks/01-build-graph/README.md"),
    Path("notebooks/01-build-graph/1.1_build_graph.ipynb"),
    Path("notebooks/02-connected-context/README.md"),
    Path("notebooks/02-connected-context/2.1_connected_context.ipynb"),
    Path("notebooks/03-grounded-booking-agent/README.md"),
    Path("notebooks/03-grounded-booking-agent/3.1_grounded_booking_agent.ipynb"),
    Path("notebooks/04-production-agent/4.1_agentcore_gateway.ipynb"),
    Path("notebooks/04-production-agent/tool_schemas/tools.json"),
    Path("site/content/01-build-graph/index.en.md"),
    Path("site/content/02-connected-context/index.en.md"),
    Path("site/content/03-grounded-booking-agent/index.en.md"),
    Path("site/content/04-production-agent/index.en.md"),
    Path("site/content/summary/index.en.md"),
    Path("site/content/wrap-up/index.en.md"),
)


def learner_text(path: Path) -> str:
    """Return learner prose while excluding executable notebook code."""
    full_path = REPO_ROOT / path
    if full_path.suffix != ".ipynb":
        return full_path.read_text(encoding="utf-8")

    notebook = json.loads(full_path.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", []))
        if isinstance(cell.get("source", []), list)
        else cell.get("source", "")
        for cell in notebook["cells"]
        if cell.get("cell_type") == "markdown"
    )


def all_learner_text() -> str:
    """Join the active learner-facing surfaces covered by Phase 5."""
    return "\n".join(learner_text(path) for path in LEARNER_FILES)


def test_retired_agent_contest_and_one_hop_labels_are_absent() -> None:
    text = all_learner_text().casefold()
    retired_claims = (
        "module 2 creates two agents",
        "module 2 demonstrates this failure",
        "module 3 combines the two",
        "competing agents",
        "multi-hop",
        "multihop",
    )
    assert all(claim not in text for claim in retired_claims)


def test_module_1_hands_retrieval_comparison_to_module_2() -> None:
    notebook = learner_text(
        Path("notebooks/01-build-graph/1.1_build_graph.ipynb")
    )
    readme = learner_text(Path("notebooks/01-build-graph/README.md"))
    page = learner_text(
        Path("site/content/01-build-graph/index.en.md")
    )

    for text in (notebook, readme, page):
        assert "Module 2" in text
        assert "Module 3" in text
        assert "retrieval comparison" in text


def test_module_3_owns_the_strands_agent_basics() -> None:
    module_1_surfaces = (
        learner_text(Path("notebooks/01-build-graph/README.md")),
        learner_text(Path("notebooks/01-build-graph/1.1_build_graph.ipynb")),
        learner_text(Path("site/content/01-build-graph/index.en.md")),
    )
    module_3_surfaces = (
        learner_text(Path("notebooks/03-grounded-booking-agent/README.md")),
        learner_text(
            Path(
                "notebooks/03-grounded-booking-agent/"
                "3.1_grounded_booking_agent.ipynb"
            )
        ),
        learner_text(
            Path("site/content/03-grounded-booking-agent/index.en.md")
        ),
    )

    assert all("Strands" not in text for text in module_1_surfaces)
    for text in module_3_surfaces:
        assert "Strands" in text
        assert "**Brief overview**" in text
        assert "`Agent`" in text
        assert "`BedrockModel`" in text
        assert "`@tool`" in text
        assert "—" not in text


def test_module_2_states_extraction_and_application_boundaries() -> None:
    module_2_surfaces = (
        learner_text(Path("notebooks/02-connected-context/README.md")),
        learner_text(
            Path("notebooks/02-connected-context/2.1_connected_context.ipynb")
        ),
        learner_text(
            Path("site/content/02-connected-context/index.en.md")
        ),
    )

    boundary_claims = (
        "reflect the facts that extraction placed",
        "reflects what extraction placed",
        "returns facts written during extraction",
    )
    for text in module_2_surfaces:
        assert any(claim in text for claim in boundary_claims)
        assert "HybridCypherRetriever" in text
        assert "search_hotel_knowledge" in text
        assert "Module 3" in text


def test_model_wording_is_separate_from_fixed_contracts() -> None:
    text = all_learner_text().casefold()
    assert "model wording can" in text
    assert "fixed model id ensures" not in text
    assert "deterministic workshop results" not in text
    assert "same model when comparing outputs" not in text


def test_vague_chunk_terms_are_absent_from_retrieval_prose() -> None:
    text = all_learner_text().casefold()
    ambiguous_terms = (
        "candidate chunks",
        "relevant source chunks",
        "source chunk, graph fields",
    )
    assert all(term not in text for term in ambiguous_terms)
