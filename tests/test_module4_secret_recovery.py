"""Regression coverage for the Module 4 Secrets Manager recovery fallback."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = (
    REPO_ROOT
    / "notebooks"
    / "04-production-agent"
    / "4.1_agentcore_gateway.ipynb"
)


class ScheduledSecretClient:
    """Model a stale secret that the current role is not allowed to restore."""

    def create_secret(self, *, Name: str, **_: str) -> dict[str, str]:
        if Name == "neo4j-ws-retrieval":
            raise ClientError(
                {
                    "Error": {
                        "Code": "InvalidRequestException",
                        "Message": "The secret is scheduled for deletion.",
                    }
                },
                "CreateSecret",
            )
        return {"ARN": f"arn:aws:secretsmanager:us-east-1:123:secret:{Name}"}

    def restore_secret(self, **_: str) -> dict[str, str]:
        raise ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
            "RestoreSecret",
        )


def secret_cell_tree() -> ast.Module:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    source = next(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if "def upsert_secret" in "".join(cell.get("source", []))
    )
    return ast.parse(source)


def test_scheduled_secret_uses_deterministic_replacement_without_restore() -> None:
    tree = secret_cell_tree()
    helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    fallback_statements = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "SECRET_ARN"
                for target in node.targets
            )
        )
        or isinstance(node, ast.For)
    ]
    executable = ast.fix_missing_locations(
        ast.Module(body=[helper, *fallback_statements], type_ignores=[])
    )
    namespace = {
        "ClientError": ClientError,
        "PREFERRED_SECRET_NAME": "neo4j-ws-retrieval",
        "WORKSHOP_TAGS_KV": [
            {"Key": "WorkshopResource", "Value": "graphrag-with-neo4j"}
        ],
        "secret_value": "{}",
        "secrets": ScheduledSecretClient(),
    }

    exec(compile(executable, str(NOTEBOOK), "exec"), namespace)

    assert namespace["SECRET_NAME"] == "neo4j-ws-retrieval-2"
    assert namespace["SECRET_ARN"].endswith(":secret:neo4j-ws-retrieval-2")
