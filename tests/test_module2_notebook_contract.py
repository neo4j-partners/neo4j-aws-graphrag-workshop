"""Offline contract checks for the evidence-first Module 2 notebook."""

from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK = (
    Path(__file__).resolve().parents[1]
    / "notebooks"
    / "02-connected-context"
    / "2.1_connected_context.ipynb"
)


def notebook_sources() -> tuple[str, str]:
    """Return all notebook text and executable code as stable strings."""
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    all_text = "\n".join("".join(cell["source"]) for cell in cells)
    code = "\n".join(
        "".join(cell["source"])
        for cell in cells
        if cell["cell_type"] == "code"
    )
    return all_text, code


def notebook_code_cells() -> list[str]:
    """Return code cells as independent source strings."""
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    return [
        "".join(cell["source"])
        for cell in cells
        if cell["cell_type"] == "code"
    ]


def test_notebook_code_cells_parse() -> None:
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    for index, cell in enumerate(cells):
        if cell["cell_type"] != "code":
            continue
        ast.parse("".join(cell["source"]), filename=f"cell-{index}")


def test_locked_questions_and_evidence_fields_are_present() -> None:
    text, code = notebook_sources()
    assert (
        "When does standard arrival processing begin at "
        "AnyCompany Cairo Nile View?"
    ) in text
    assert "What is the cancellation policy for the hotel at 60611?" in text
    assert (
        "What amenities and guest rating does AnyCompany Cairo Nile View have?"
    ) in text
    assert "Which hotels in Chicago offer both a spa and a swimming pool?" in text

    for field in (
        "hotel_name",
        "hotel_id",
        "guest_rating",
        "source_filename",
        "amenities",
        "source_chunk",
        "semantic_score",
        "relationship_types",
        "field_provenance",
        "missing_requested_fields",
        "structured_context_chars",
        "source_text_chars",
    ):
        assert field in code


def test_notebook_consumes_shared_readiness_and_chicago_contracts() -> None:
    _, code = notebook_sources()
    for shared_name in (
        "source_fixture_problems",
        "chicago_filter_records",
        "chicago_filter_problems",
        "CHICAGO_FILTER_QUERY",
        "CHICAGO_SOURCE_FILES",
        "CHICAGO_QUALIFIER",
        "CHICAGO_EXCLUSION",
    ):
        assert shared_name in code

    assert "hotel_schema =" not in code
    assert "Tell me about the hotel at 789 Avenue" not in code
    assert "Parameters: city=" in code
    assert "CHICAGO_CITY" in code
    assert "Parameters: source_filenames" not in code


def test_readiness_runs_before_any_retriever_is_created() -> None:
    _, code = notebook_sources()

    assert code.index("source_fixture_problems(driver)") < code.index(
        "vector_retriever = VectorRetriever("
    )


def test_result_provenance_is_resolved_per_result_without_a_corpus_map() -> None:
    _, code = notebook_sources()

    assert "def source_for_chunk_text(chunk):" in code
    assert "source_by_chunk" not in code
    assert "MATCH (matched:Chunk {text: $chunk})" in code


def test_context_measurement_counts_values_once_without_repr_punctuation() -> None:
    nodes: list[ast.stmt] = []
    for source in notebook_code_cells():
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef) and node.name in {
                "context_value_chars",
                "context_char_counts",
            }:
                nodes.append(node)
    namespace: dict[str, object] = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "context", "exec"), namespace)

    counts = namespace["context_char_counts"](
        {"hotel": "Cairo", "amenities": ["Spa", "Pool"]},
        "source text",
    )

    assert counts == (len("CairoSpaPool"), len("source text"))


def test_fixed_chicago_evidence_fields_are_built_behaviorally() -> None:
    wanted_assignments = {"CHICAGO_REQUESTED_FIELDS", "CHICAGO_PROVENANCE"}
    nodes: list[ast.stmt] = []
    for source in notebook_code_cells():
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef) and node.name in {
                "context_value_chars",
                "context_char_counts",
                "fixed_cypher_context",
            }:
                nodes.append(node)
            elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in wanted_assignments
                for target in node.targets
            ):
                nodes.append(node)
    namespace: dict[str, object] = {}
    module = ast.Module(body=nodes, type_ignores=[])
    exec(compile(module, "evidence", "exec"), namespace)
    record = {
        "hotel_name": "Lakeview Horizon Suites",
        "guest_rating": 4.4,
        "amenities": ["Full-Service Spa", "Outdoor Swimming Pool"],
        "source_filename": "hotel-chicago-002.txt",
        "source_chunk": "authored Chicago source",
        "qualifies": True,
        "missing_required_amenities": [],
    }

    context = namespace["fixed_cypher_context"](record)

    assert context["missing_requested_fields"] == []
    assert context["source_text_chars"] == len("authored Chicago source")
    assert context["structured_context_chars"] > 0
    assert context["field_provenance"]["source_filename"].endswith(
        "[:FROM_DOCUMENT]->(:Document)"
    )


def test_cairo_vector_search_precedes_vector_cypher_comparison() -> None:
    _, code = notebook_sources()
    vector_search = code.index(
        "graph_vector_result = vector_retriever.search(\n"
        "    query_text=CAIRO_GRAPH_QUESTION"
    )
    graph_search = code.index(
        "graph_result = vector_cypher_retriever.search(\n"
        "    query_text=CAIRO_GRAPH_QUESTION"
    )
    assert vector_search < graph_search
    assert "source_filename: '(:Chunk)-[:FROM_DOCUMENT]->(:Document)'" in code


def test_shared_credentials_and_optional_text2cypher_boundaries_are_visible() -> None:
    text, code = notebook_sources()
    assert code.count("neo4j_database=DATABASE") >= 3
    assert "default_access_mode=READ_ACCESS" in code
    assert "pinned_schema_text()" in code
    assert "EXPLAIN {cypher}" in code
    assert "TEXT2CYPHER_TIMEOUT_SECONDS = 15" in code
    # Participants configure one Neo4j credential for the whole workshop. The
    # optional Text2Cypher cell adds an EXPLAIN guard instead of a second login,
    # while the prose recommends database-enforced read-only access in production.
    assert "NEO4J_READ_USERNAME" not in code
    assert "NEO4J_READ_PASSWORD" not in code
    assert "SHOW CURRENT USER" not in code
    assert "with driver.session(" in code
    assert "generated_cypher" in code
    assert "read_only_validation" in code
    assert "result_count" in code
    assert "displayed_count" in code
    assert "execution_error" in code
    assert "Fixed Cypher remains the acceptance path" in code
    assert "same workshop credentials as every other cell" in text
    assert "read-only Neo4j user in production" in text


def test_module3_handoff_and_prose_style_are_explicit() -> None:
    text, code = notebook_sources()
    assert "selected_module_3_retriever = search_hotel_knowledge" in code
    assert "Selected for Module 3" in code
    assert "Result count:" in code
    assert "Candidate count:" in code
    assert "\u2014" not in text


def test_every_acceptance_assertion_has_an_actionable_message() -> None:
    for cell_index, source in enumerate(notebook_code_cells()):
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Assert):
                assert node.msg is not None, f"cell {cell_index} has a bare assertion"
