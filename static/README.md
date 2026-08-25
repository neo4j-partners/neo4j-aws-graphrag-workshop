# Static Assets

## `/iam_policy.json`

IAM policy for workshop participants. Grants least-privilege access to:
- Amazon Bedrock (model invocation, AgentCore control plane)
- AWS Lambda (`hotel-booking-*` prefix)
- Amazon ECR (`workshop-*` repos only; `GetAuthorizationToken` on `*`)
- AWS Secrets Manager (`workshop-*`, `neo4j-ws-*`, `bedrock-agentcore-*` prefixes)
- Amazon DynamoDB (`workshop-*` tables)
- Amazon S3 (`workshop-*`, `bedrock-agentcore-*` buckets)
- IAM roles (`workshop-*`, `AmazonBedrockAgentCoreSDK*` prefixes)
- CloudWatch Logs, CodeBuild, EC2 Describe

Uses Workshop Studio magic variables: `{{.AccountId}}`.

## `/cfn/`

| Template | Purpose |
|---|---|
| `code-editor.yaml` | VPC + Code Editor EC2 (ARM) + Neo4j on ECS Fargate. **Main participant template.** |
| `neo4j-foundation.yaml` | Secret, S3 dump bucket, IAM roles, Security Group, ECS Cluster. Deploy first. |
| `neo4j-service.yaml` | NLB + single Fargate task that restores from S3 dump and serves Bolt. |
| `neo4j-build.yaml` | One-shot ECS task that builds the graph from FAQs and saves a dump to S3. |
| `central-neo4j.yaml` | Facilitator-account template: shared Neo4j instance for multi-participant events. |

## `/neo4j-hotel-graph.dump`

Neo4j database dump with the hotel knowledge graph pre-built. It does not contain the vector or full-text index; Module 1 creates those. Loaded by the Fargate init container at startup, so participants start from a built graph instead of watching the extraction run.

## `/images/`

Architecture diagrams for workshop content pages.
