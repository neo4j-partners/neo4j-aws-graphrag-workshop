"""Protect the active Module 2 retrieval diagram contract."""

from __future__ import annotations

import json
import struct
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IMAGES = REPO_ROOT / "site" / "images"
CONTENT_ROOT = REPO_ROOT / "site" / "content"
NOTEBOOKS_ROOT = REPO_ROOT / "notebooks"
SOURCE_NAME = "02-retrieval-decision-tree.excalidraw"
EXPORT_NAME = "02-retrieval-decision-tree.png"


def _source_text() -> str:
    return (IMAGES / SOURCE_NAME).read_text(encoding="utf-8")


def test_decision_tree_ships_both_the_source_and_the_export() -> None:
    """The published image tree carries the editable source and its PNG export."""
    for name in (SOURCE_NAME, EXPORT_NAME):
        assert (IMAGES / name).is_file()


def test_decision_tree_has_one_authoritative_editable_source() -> None:
    """The retired drawio file must not compete with the Excalidraw source."""
    assert not (IMAGES / "02-retrieval-decision-tree.drawio").exists()
    sources = list(IMAGES.glob("02-retrieval-decision-tree.*"))
    editable = [path for path in sources if path.suffix != ".png"]
    assert [path.name for path in editable] == [SOURCE_NAME]


def test_unsupported_retrieval_comparison_is_not_active() -> None:
    """Unsupported speed and accuracy ratings stay out of the active image tree."""
    assert not (IMAGES / "02-retrieval-patterns-comparison.png").exists()


def test_decision_tree_assigns_the_chicago_example_to_fixed_cypher() -> None:
    """The workshop query belongs to reviewed Cypher, not Text2Cypher."""
    document = json.loads(_source_text())
    text_by_id = {
        element["id"]: element["text"].replace("\n", " ")
        for element in document["elements"]
        if element["type"] == "text"
    }
    chicago_owners = {
        element_id
        for element_id, text in text_by_id.items()
        if "Chicago hotels with a spa and pool" in text
    }

    assert chicago_owners == {"fixed-cypher-card-body"}
    assert text_by_id["fixed-cypher-card-title"] == "Reviewed fixed Cypher"
    assert "Reviewed Cypher and database records" in text_by_id[
        "fixed-cypher-card-body"
    ]
    assert text_by_id["optional-text2cypher-text"].startswith(
        "Optional: Text2CypherRetriever"
    )
    assert "Chicago hotels" not in text_by_id["optional-text2cypher-text"]


def test_decision_tree_teaches_the_locked_retrieval_roles() -> None:
    """The editable source must state the learner-facing retrieval contract."""
    document = json.loads(_source_text())
    diagram_text = " ".join(
        element["text"].replace("\n", " ")
        for element in document["elements"]
        if element["type"] == "text"
    )
    required_text = (
        "VectorRetriever",
        "HybridRetriever",
        "VectorCypherRetriever",
        "Text2CypherRetriever",
        "Semantic match finds a Chunk node",
        "Reviewed traversal expands the graph",
        "Named fields include provenance",
        "Reviewed structured filtering",
        "Application-owned query over named fields",
        "Model-generated read-only Cypher for flexible questions",
        "Chicago hotels with a spa and pool",
    )
    for phrase in required_text:
        assert phrase in diagram_text

    forbidden_text = (
        "Count or aggregate",
        "how many hotels have a pool",
        "Flexible structured filtering",
        "Generated read-only Cypher and records",
        "Speed:",
        "Accuracy:",
    )
    for phrase in forbidden_text:
        assert phrase not in diagram_text


def test_decision_tree_uses_clean_excalidraw_styles() -> None:
    """The editable source follows the repository's Excalidraw conventions."""
    document = json.loads(_source_text())
    assert document["type"] == "excalidraw"
    assert document["version"] == 2
    assert document["appState"]["currentItemFontFamily"] == 5
    assert document["appState"]["currentItemRoughness"] == 0
    assert document["appState"]["exportBackground"] is True
    for element in document["elements"]:
        assert element["roughness"] == 0
        assert element["fillStyle"] == "solid"
        if element["type"] == "text":
            assert element["fontFamily"] == 5


def test_module_2_table_marks_text2cypher_optional() -> None:
    """The module table mirrors the fixed-query ownership in the diagram."""
    content = (
        CONTENT_ROOT / "02-connected-context" / "index.en.md"
    ).read_text(encoding="utf-8")

    assert "| Reviewed fixed Cypher | Known structured questions |" in content
    assert "| `Text2CypherRetriever` (optional) |" in content


def test_module_3_says_module_2_selected_the_application_path() -> None:
    """Module 3 must not claim Module 2 compared the application configuration."""
    content = (
        CONTENT_ROOT / "03-grounded-booking-agent" / "index.en.md"
    ).read_text(encoding="utf-8")
    notebook = json.loads(
        (
            NOTEBOOKS_ROOT
            / "03-grounded-booking-agent"
            / "3.1_grounded_booking_agent.ipynb"
        ).read_text(encoding="utf-8")
    )
    notebook_markdown = " ".join(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "markdown"
    )

    assert "Module 2 selected a fixed Hybrid-Cypher path" in content
    assert "Module 2 compared retrieval patterns" not in content
    assert "selects this fixed Hybrid-Cypher pattern" in notebook_markdown
    assert "compares this configuration" not in notebook_markdown
    assert "compares vector, hybrid" not in notebook_markdown


def test_retired_problem_image_and_stale_prompt_path_are_absent() -> None:
    """The image tree keeps only active assets and teaches the content-relative path."""
    assert not (IMAGES / "01-rag-vs-graphrag-problem.png").exists()
    prompt = (IMAGES / "DIAGRAM_PROMPTS.md").read_text(encoding="utf-8")
    assert "01-rag-vs-graphrag-problem.png" not in prompt
    assert '../../images/FILENAME.png' in prompt
    assert '/static/images/FILENAME.png' not in prompt


def test_decision_tree_png_is_the_expected_canvas_size() -> None:
    """The checked-in export remains a 1600 by 900 PNG."""
    data = (IMAGES / EXPORT_NAME).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", data[16:24]) == (1600, 900)
