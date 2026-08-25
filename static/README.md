# Static Assets

## `/neo4j-hotel-graph.dump`

Neo4j database dump with the hotel knowledge graph pre-built. It does not contain the vector or full-text index; Module 1 creates those. Participants download this file during Setup and restore it into their own Neo4j AuraDB Free instance, so they start from a built graph instead of watching the extraction run.

## `/images/`

Architecture diagrams for workshop content pages.

`03-agentcore-architecture.png` and its `.drawio` source are stale. They still draw Neo4j on ECS Fargate, which was the topology when the workshop ran on AWS Workshop Studio. The database is Neo4j AuraDB Free now. The content page alt text already says AuraDB, so the diagram is the only thing left to redraw.

## Retired

`iam_policy.json` and `cfn/` are gitignored and are not part of any setup path. They held the participant IAM policy and the CloudFormation templates that stood up a Code Editor instance with Neo4j on ECS Fargate. The workshop is hosted on Vocareum now, and each participant creates their own Neo4j AuraDB Free database.
