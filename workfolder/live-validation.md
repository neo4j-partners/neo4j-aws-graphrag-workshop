# Live validation

Date: 2026-08-23 (America/Denver)

Code under test: `b1e268473de738767faf851ef2ea63972fedd932`

Environment: Neo4j Aura Enterprise 5.27, database `neo4j`, AWS Region
`us-east-1`, model `us.anthropic.claude-sonnet-5`.

The prebuilt graph started with 295 Documents, 295 Hotels, 65 Amenities, and
1,606 amenity assertions. Module 1 added the five held-out hotel sources and
the graph ended with 300 Documents, 300 Hotels, 65 Amenities, and 1,632 amenity
assertions. The post-patch full re-run held those four counts at the learner-
complete values.

| Module | Notebook | Result |
| --- | --- | --- |
| 1 | `1.1_build_graph.ipynb` | passed |
| 2 | `2.1_connected_context.ipynb` | passed |
| 3 | `3.1_grounded_booking_agent.ipynb` | passed |

The full gate reported 3 passed, 0 failed, and 0 skipped. Module 2's optional
Text2Cypher supporting check reported `passed: EXPLAIN query_type=r`. Module 3
confirmed availability abstention, rejected an over-limit guest request, and
returned an idempotent duplicate result for the repeated reservation request.

The focused Module 2 notebook contract test passed (11 tests). The full offline
suite passed 214 tests, and the repository checker passed after the live run.

## Modules 4--6

Date: 2026-08-23 (America/Denver)

Code under test: `6e06c3268aac1d71c9709c368ee6476f081d7e0f`

Environment: AWS account `159878781974`, Region `us-east-1`, model
`us.anthropic.claude-sonnet-5`, and the same live Neo4j `neo4j` database used by
Modules 1--3. The graph prerequisite held at 300 Documents, 300 Hotels, 65
Amenities, and 1,632 amenity assertions.

| Module | Notebook | Result |
| --- | --- | --- |
| 4 | `4.1_agentcore_gateway.ipynb` | passed |
| 4 | `4.2_agentcore_memory.ipynb` | passed |
| 5 | `5.1_deploy.ipynb` | passed |
| 6 | `6.1_neo4j_memory.ipynb` | passed |

The Modules 4--5 gate reported 3 passed, 0 failed, and 0 skipped. Module 4.1
created and called both Lambda-backed Gateway tools. Module 4.2 recalled a
preference in a new session. Module 5 deployed the Runtime, returned grounded
hotel facts, refused an ungrounded hotel ID, abstained on live availability,
enforced the 10-guest rule, wrote one accepted reservation request, and returned
`duplicate=true` when that request was replayed.

The Module 6 gate reported 1 passed, 0 failed, and 0 skipped. It wrote real
Neo4j memory records, recalled the correct actor's preference in a fresh
session, withheld it from another actor, displayed source-message provenance,
linked the preference to the real hotel, and tagged the records for scoped
cleanup.

Cleanup deleted the Module 6 records and the Module 5 reservation request while
preserving all 300 Hotel nodes. It deleted the test Gateway and targets, two
Lambda functions, ECR repository, CodeBuild project, and workshop IAM roles;
deleted the tested Runtime and AgentCore memory; and scheduled the retrieval
secret for recoverable deletion. The unrelated supplier Gateway and Runtime
were verified separately and left untouched.
