"""Regression checks for the participant-owned Module 4 resources."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from workshop.contracts import lambda_function_name

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = REPO_ROOT / "notebooks" / "04-production-agent"
NOTEBOOK = MODULE_DIR / "4.1_agentcore_gateway.ipynb"
SCHEMAS = MODULE_DIR / "tool_schemas" / "tools.json"
OWN_ACCOUNT_SETUP = (
    REPO_ROOT / "site" / "content" / "setup" / "own-account-setup" / "index.en.md"
)
MODULE_PAGE = REPO_ROOT / "site" / "content" / "04-production-agent" / "index.en.md"


def notebook_trees() -> list[ast.Module]:
    """Parse the notebook's ordinary Python cells for structural checks."""
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    trees = []
    for cell in cells:
        if cell["cell_type"] != "code":
            continue
        try:
            trees.append(ast.parse("".join(cell["source"])))
        except SyntaxError:
            # IPython shell/magic cells are outside this deployment contract.
            continue
    return trees


def string_assignments() -> dict[str, str]:
    """Return literal string constants declared by the Module 4 notebook."""
    assignments = {}
    for tree in notebook_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(
                node.value, ast.Constant
            ):
                continue
            if not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value.value
    return assignments


def client_calls(client: str, method: str) -> list[ast.Call]:
    """Find calls such as ``iam.create_role(...)`` in notebook code."""
    calls = []
    for tree in notebook_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != method or not isinstance(node.func.value, ast.Name):
                continue
            if node.func.value.id == client:
                calls.append(node)
    return calls


def keyword_references(call: ast.Call, keyword: str, variable: str) -> bool:
    """Report whether one call keyword uses the shared tag variable."""
    return any(
        item.arg == keyword
        and isinstance(item.value, ast.Name)
        and item.value.id == variable
        for item in call.keywords
    )


def keyword_name(call: ast.Call, keyword: str) -> str | None:
    """Return a simple name supplied to one keyword, if present."""
    for item in call.keywords:
        if item.arg == keyword and isinstance(item.value, ast.Name):
            return item.value.id
    return None


def tool_names() -> list[str]:
    """Return the tool names that drive Lambda and target creation."""
    return [entry["name"] for entry in json.loads(SCHEMAS.read_text())]


def test_own_account_cleanup_names_the_deployed_module4_inventory() -> None:
    """Cleanup must follow the same constants and schemas as deployment."""
    cleanup = OWN_ACCOUNT_SETUP.read_text(encoding="utf-8")
    constants = string_assignments()

    for constant in (
        "GATEWAY_NAME",
        "ROLE_NAME",
        "GATEWAY_ROLE_NAME",
        "PREFERRED_SECRET_NAME",
    ):
        assert constants[constant] in cleanup

    for tool_name in tool_names():
        function_name = lambda_function_name(tool_name)
        assert function_name in cleanup
        assert f"/aws/lambda/{function_name}" in cleanup
        assert tool_name.replace("_", "-") in cleanup


def test_cleanup_does_not_regress_to_one_lambda_or_idle_gateway_billing() -> None:
    cleanup = OWN_ACCOUNT_SETUP.read_text(encoding="utf-8")
    module_page = MODULE_PAGE.read_text(encoding="utf-8")

    assert "Lambda function Module 4 created" not in cleanup
    assert "Gateway and secret incur charges while they exist" not in module_page


def test_module4_uses_the_shared_workshop_tag_identity() -> None:
    assignments = string_assignments()

    assert assignments["WORKSHOP_TAG_KEY"] == "WorkshopResource"
    assert assignments["WORKSHOP_TAG_VALUE"] == "graphrag-with-neo4j"


def test_secret_is_tagged_when_created_and_when_reused() -> None:
    create_calls = client_calls("secrets", "create_secret")
    retag_calls = client_calls("secrets", "tag_resource")

    assert len(create_calls) == 1
    assert keyword_references(create_calls[0], "Tags", "WORKSHOP_TAGS_KV")
    assert retag_calls
    assert all(
        keyword_references(call, "Tags", "WORKSHOP_TAGS_KV")
        for call in retag_calls
    )


def test_both_iam_roles_are_tagged_when_created_and_when_reused() -> None:
    create_calls = client_calls("iam", "create_role")
    retag_calls = client_calls("iam", "tag_role")
    role_variables = {"ROLE_NAME", "GATEWAY_ROLE_NAME"}

    assert {keyword_name(call, "RoleName") for call in create_calls} == role_variables
    assert all(
        keyword_references(call, "Tags", "WORKSHOP_TAGS_KV")
        for call in create_calls
    )
    assert {keyword_name(call, "RoleName") for call in retag_calls} == role_variables
    assert all(
        keyword_references(call, "Tags", "WORKSHOP_TAGS_KV")
        for call in retag_calls
    )


def test_both_schema_driven_lambdas_are_tagged_on_create_and_update() -> None:
    create_calls = client_calls("lambda_client", "create_function")
    retag_calls = client_calls("lambda_client", "tag_resource")

    assert len(tool_names()) == 2
    assert len(create_calls) == 1
    assert keyword_references(create_calls[0], "Tags", "WORKSHOP_TAGS_MAP")
    assert retag_calls
    assert all(
        keyword_references(call, "Tags", "WORKSHOP_TAGS_MAP")
        for call in retag_calls
    )


def test_gateway_is_tagged_and_owns_its_untaggable_targets() -> None:
    create_calls = client_calls("control_client", "create_gateway")
    retag_calls = client_calls("control_client", "tag_resource")
    target_calls = client_calls("control_client", "create_gateway_target")

    assert len(create_calls) == 1
    assert keyword_references(create_calls[0], "tags", "WORKSHOP_TAGS_MAP")
    assert retag_calls
    assert all(
        keyword_references(call, "tags", "WORKSHOP_TAGS_MAP")
        for call in retag_calls
    )
    assert len(target_calls) == 1
    assert keyword_name(target_calls[0], "gatewayIdentifier") == "GATEWAY_ID"
    assert all(item.arg != "tags" for item in target_calls[0].keywords)
