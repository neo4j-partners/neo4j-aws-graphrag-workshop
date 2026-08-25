# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Lambda entry point for the semantic Gateway target.

The retrieval itself is ``workshop.hybrid_retrieval.search_hotel_knowledge``,
the same function Module 3 calls in-process. Everything below is the Lambda
boundary: unwrap the event, hand back a JSON-serializable result. The
deployment package installs the shared ``workshop`` package rather than
flat-copying its files, so this import resolves here exactly as it does in the
notebook.

This tool reads. It runs reviewed, static Cypher and never writes.
"""

from typing import Any, Mapping

from workshop.hybrid_retrieval import search_hotel_knowledge


def handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Return grounded hotel evidence for the Gateway's ``query`` input."""
    del context
    query = (event or {}).get("query")
    if not isinstance(query, str) or not query:
        return {"error": "query must be a non-empty string"}
    try:
        return {"evidence": search_hotel_knowledge(query)}
    except ValueError as error:
        return {"error": str(error)}


__all__ = ["handler"]
