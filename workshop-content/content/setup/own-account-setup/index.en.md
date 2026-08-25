---
title: "Own Account Setup"
weight: 2
---

## Prerequisites

- AWS account with admin or PowerUser access in **us-east-1**
- Bedrock model access enabled (step 1 below)
- Roughly $2 of AWS spend for the resources this workshop creates

---

## Step 1: Enable Bedrock Model Access

1. Open :link[Amazon Bedrock]{href="https://aws.amazon.com/bedrock/" external=true} in **us-east-1**
2. Go to **Model access → Manage model access**
3. Enable\:
   - **Amazon Nova 2 Multimodal Embeddings** (`amazon.nova-2-multimodal-embeddings-v1:0`)
   - **Claude Sonnet 5** (`us.anthropic.claude-sonnet-5`)
   - **Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`)
4. Click **Save changes**

---

## Step 2: Deploy the Workshop Stack

The `code-editor.yaml` template creates a VPC, Code Editor EC2 instance, and :link[Neo4j]{href="https://neo4j.com/" external=true} on ECS Fargate with the hotel graph pre-loaded.

:::alert{type="warning" header="Before deploying"}
The hotel graph dump (`neo4j-hotel-graph.dump`) must be uploaded to the Workshop Studio :link[Amazon S3]{href="https://aws.amazon.com/s3/" external=true} assets bucket first. If you are running self-paced without Workshop Studio, use the deploy command below with an S3 bucket you own.
:::

:::code{language=bash showCopyAction=true}
# Upload the dump to your S3 bucket first
aws s3 cp static/neo4j-hotel-graph.dump s3://YOUR-BUCKET/neo4j-graph.dump

# Deploy the stack
aws cloudformation create-stack \
  --stack-name graphrag-neo4j-workshop \
  --template-body file://static/cfn/code-editor.yaml \
  --parameters \
    ParameterKey=AssetsBucketName,ParameterValue=YOUR-BUCKET \
    ParameterKey=AssetsBucketPrefix,ParameterValue="" \
    ParameterKey=RepoUrl,ParameterValue="https://github.com/neo4j-partners/sample-stop-ai-agent-hallucinations-workshop" \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
:::

Wait for completion\:

:::code{language=bash showCopyAction=true}
aws cloudformation wait stack-create-complete \
  --stack-name graphrag-neo4j-workshop --region us-east-1
echo "Stack ready"
:::

---

## Step 3: Get Your Connection Details

:::code{language=bash showCopyAction=true}
aws cloudformation describe-stacks \
  --stack-name graphrag-neo4j-workshop \
  --query 'Stacks[0].Outputs' \
  --output table --region us-east-1
:::

Note the values for\: `CodeEditorURL`, `Neo4jURI`, `Neo4jUser`, `Neo4jPassword`.

---

## Step 4: Open Code Editor and Verify

1. Open **CodeEditorURL** in a browser
2. Open a terminal (**Terminal → New Terminal**)
3. Set environment variables, install the dependencies, and run `setup/verify_setup.py` (same as [Workshop Studio path](../workshop-studio-access/), Step 3 onward)

With every line of that script reporting `ok`, proceed to [Module 1](../../01-build-graph/).

---

## Cleanup

When finished, delete the stack to stop all charges\:

:::code{language=bash showCopyAction=true}
aws cloudformation delete-stack \
  --stack-name graphrag-neo4j-workshop --region us-east-1
:::
