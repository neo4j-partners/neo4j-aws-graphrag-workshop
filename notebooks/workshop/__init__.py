# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Code shared by more than one workshop module.

A file belongs here when two or more modules consume it. A file used by exactly
one module lives in that module's folder and is imported flat, so the import
style tells a reader which tier they are in: `from workshop.graph_schema import
GRAPH_SCHEMA` is shared and editing it affects other modules, while `from
reservation_command import ...` is that module's own file.

Import submodules directly, for example::

    from workshop.contracts import MAX_GUESTS
    from workshop.graph_connection import neo4j_auth, require_neo4j_env

This package deliberately re-exports nothing. `bedrock_providers`, `fixtures`,
`hybrid_retrieval`, and `retrieval_setup` all build AWS or Neo4j clients, and
`workshop_utils` imports the Strands SDK. A convenience re-export here would drag
every one of those into `import workshop`, and `contracts` promises the
reservation Lambda that it can be imported without touching credentials or the
network. Keeping this file empty of imports is what makes that promise true.

No module in this package raises at import. `graph_connection` used to, when
`NEO4J_PASSWORD` was unset; that check now lives in `require_neo4j_env()`, which
a caller invokes when it cannot proceed without a database.
"""
