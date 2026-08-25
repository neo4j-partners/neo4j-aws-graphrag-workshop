# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Lambda entry point for the structured Gateway target.

The retrieval itself is ``workshop.hybrid_retrieval.graph_query``, the same
``Text2CypherRetriever`` pattern Module 2.1 compares in-process. Everything
below is the Lambda boundary. The deployment package installs the shared
``workshop`` package rather than flat-copying its files, so this import
resolves here exactly as it does in the notebook.

This tool reads. The Cypher is model-generated, and ``Text2CypherRetriever``
plans it with ``EXPLAIN`` and refuses to run anything the planner does not
report as read-only. The workshop reuses its ordinary Neo4j credential to keep
participant setup small; a production deployment should use a read-only Neo4j
user as an independent database boundary.
"""

from typing import Any, Mapping

from workshop.hybrid_retrieval import graph_query


def handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Return the generated Cypher and its records for the ``query`` input."""
    del context
    query = (event or {}).get("query")
    if not isinstance(query, str) or not query:
        return {"error": "query must be a non-empty string"}
    try:
        return dict(graph_query(query))
    except ValueError as error:
        return {"error": str(error)}


__all__ = ["handler"]
