# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Lambda entry point for the passage-search Gateway target.

The retrieval itself is ``workshop.hybrid_retrieval.search_hotel_knowledge``,
the same function Module 3 calls in-process. Everything below is the Lambda
boundary: validate the advertised one-field input and return the shared read-
tool envelope. The deployment package installs the shared ``workshop`` package
so its contract is identical in the notebook and Lambda.

This tool reads. It runs reviewed, static Cypher and never writes.
"""

from collections.abc import Mapping
from typing import Any

from workshop import grounding
from workshop.hybrid_retrieval import search_hotel_knowledge


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
    """Return bounded hotel passages for the Gateway's ``query`` input."""
    del context
    query = _validated_query(event)
    if query is None:
        return grounding.error_payload(
            grounding.INVALID_QUERY,
            grounding.INVALID_QUERY_MESSAGE,
        )

    passages = search_hotel_knowledge(query)
    return dict(grounding.passage_payload(query, passages))


__all__ = ["handler"]
