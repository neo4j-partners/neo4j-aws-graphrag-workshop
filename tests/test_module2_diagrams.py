"""Contract for the Module 2 retrieval diagram.

Four gates cover the asset rather than the surrounding prose: the page renders
a diagram that exists, nothing competes with it, the diagram teaches the locked
retrieval order and roles, and it stays scalable.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IMAGES = REPO_ROOT / "site" / "images"
MODULE_2_PAGE = REPO_ROOT / "site" / "content" / "02-connected-context" / "index.en.md"
DIAGRAM = IMAGES / "02-select-retriever.svg"
GRAPH_STRUCTURE_DIAGRAM = IMAGES / "01-graph-structure.svg"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def diagram_labels(group_id: str | None = None) -> str:
    """Join the diagram's label text, either all of it or one named group's."""
    root = ElementTree.parse(DIAGRAM).getroot()
    scope = root if group_id is None else root.find(f".//{{{SVG_NAMESPACE}}}g[@id='{group_id}']")
    assert scope is not None, f"the diagram has no group '{group_id}'"
    return " ".join(
        "".join(node.itertext()) for node in scope.iter(f"{{{SVG_NAMESPACE}}}text")
    )


def test_the_page_renders_a_diagram_that_exists() -> None:
    """Module 2 renders this diagram, and the image tree carries it."""
    referenced = re.findall(
        r'src="\.\./\.\./images/([^"]+)"', MODULE_2_PAGE.read_text(encoding="utf-8")
    )
    assert referenced == [GRAPH_STRUCTURE_DIAGRAM.name, DIAGRAM.name]
    assert GRAPH_STRUCTURE_DIAGRAM.is_file()
    assert DIAGRAM.is_file()


def test_nothing_competes_with_the_diagram() -> None:
    """One source of truth: no retired export, editor file, or stale variant."""
    assert sorted(path.name for path in IMAGES.glob("02-*")) == [DIAGRAM.name]


def test_the_diagram_teaches_the_locked_retrieval_roles() -> None:
    """Three entry searches precede their Cypher-enriched retrieval paths."""
    labels = diagram_labels()
    ordered_groups = (
        ("branch-vector", "1 VectorRetriever"),
        ("branch-vector-cypher", "2 VectorCypherRetriever"),
        ("branch-fulltext", "3 Full-Text Search"),
        ("branch-fulltext-cypher", "4 Full-Text + Cypher"),
        ("branch-hybrid", "5 HybridRetriever"),
        ("branch-hybrid-cypher", "6 HybridCypherRetriever"),
        ("branch-fixed-cypher", "7 Cypher Templates"),
        ("optional-text2cypher", "8 Text2CypherRetriever"),
    )
    for group_id, expected in ordered_groups:
        assert expected in diagram_labels(group_id)

    assert "Chicago hotels" in diagram_labels("branch-fixed-cypher")
    assert "Chicago hotels" not in diagram_labels("optional-text2cypher")
    assert "No separate class name" in diagram_labels("branch-fulltext-cypher")

    for unsupported in ("Speed:", "Accuracy:"):
        assert unsupported not in labels


def test_the_diagram_scales_with_the_page() -> None:
    """Legibility depends on self-contained vector markup that the page can scale."""
    source = DIAGRAM.read_text(encoding="utf-8")
    assert "<image" not in source
    assert "data:image" not in source

    root = ElementTree.fromstring(source)
    assert root.get("viewBox") is not None
    assert root.get("width") is None
    assert root.get("height") is None
