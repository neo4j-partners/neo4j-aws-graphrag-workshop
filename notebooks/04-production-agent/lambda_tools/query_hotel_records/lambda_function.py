# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Lambda entry point for the structured-record Gateway target.

The retrieval itself is ``workshop.hybrid_retrieval.graph_query``, the same
``Text2CypherRetriever`` pattern Module 2 compares in-process. Everything
below is the Lambda boundary: validate the advertised one-field input and
return the shared read-tool envelope.

This tool reads. ``Text2CypherRetriever`` plans generated Cypher with
``EXPLAIN`` and refuses to run anything the planner does not report as read-
only. The workshop reuses its ordinary Neo4j credential to keep participant
setup small. A production deployment should use a read-only Neo4j user as an
independent database boundary.
"""

from collections.abc import Mapping
from typing import Any

from workshop import grounding
from workshop.hybrid_retrieval import EXPECTED_QUERY_ERRORS, graph_query


def _validated_query(event: object) -> str | None:
    """Return the nonblank query from the exact one-field input contract.

    The nonblank-string half is ``grounding.validated_query``, shared with the
    Module 3 Strands tools. The exact-keys half is this boundary's alone: the
    Gateway registers a schema without ``additionalProperties``, so an event
    carrying anything besides ``query`` is refused here or nowhere.
    """
    if not isinstance(event, Mapping) or set(event) != {"query"}:
        return None
    return grounding.validated_query(event["query"])


def handler(event: Mapping[str, Any], context: Any) -> dict[str, Any]:
    """Return generated Cypher and bounded records for the ``query`` input."""
    del context
    query = _validated_query(event)
    if query is None:
        return grounding.error_payload(
            grounding.INVALID_QUERY,
            grounding.INVALID_QUERY_MESSAGE,
        )

    try:
        result = graph_query(query)
    except EXPECTED_QUERY_ERRORS as error:
        return grounding.error_payload(
            grounding.QUERY_FAILED,
            f"{type(error).__name__}: {error}",
        )

    payload = grounding.record_payload(query, result["cypher"], result["records"])
    return dict(payload)


__all__ = ["handler"]
