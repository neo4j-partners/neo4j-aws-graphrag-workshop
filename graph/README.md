# Graph Assets

## `neo4j-hotel-graph.dump`

Neo4j database dump with the hotel knowledge graph pre-built. It does not
contain the vector or full-text index; Module 1 creates those. Participants
download this file during Setup and restore it into their own Neo4j AuraDB Free
instance, so they start from a built graph instead of watching the extraction
run.

The dump is a release artifact, not something to edit by hand. It is produced
and gated by `tools/release/`; see `tools/README.md` for the build and
validation path.
