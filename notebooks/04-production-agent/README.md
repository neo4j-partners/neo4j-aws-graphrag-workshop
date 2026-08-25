[< Back to the workshop README](../../README.md)

# Module 4: Production Agent with AgentCore

The Module 3 booking agent calls Python tools in the same notebook kernel. This
module deploys the retrieval tools behind a managed MCP endpoint. A compact
Strands example then passes the resolved MCP tools to an agent through the same
`tools` interface used for local functions.

**At a Glance**

- **Problems addressed:** remote access to retrieval tools and IAM authentication.
- **Neo4j:** The Lambda tools are intended for retrieval. The fixed search uses reviewed Cypher, while the Text2Cypher tool uses a planning guard to reject writes.
- **AWS:** AgentCore Gateway, AWS Lambda, IAM SigV4, and Secrets Manager for the Neo4j credential.
- **You'll build:** Lambda functions under the `hotel-booking-*` prefix, one Gateway, and IAM roles under `workshop-*`.

---

## The Notebook

| Notebook | What it demonstrates |
|---|---|
| [`4.1_agentcore_gateway.ipynb`](4.1_agentcore_gateway.ipynb) | Deploy the shared search function and a reusable Text2Cypher function, call both over IAM-authenticated MCP, and give the tools to a Strands agent |

The notebook can be launched from the repository root, `notebooks/`, or this
module directory. It always packages the `lambda_tools/` tree from this
folder.

## Deploy Retrieval Tools

The Lambda functions expose retrieval interfaces. `search_hotel_knowledge` uses
reviewed static Cypher. `graph_query` relies on the Text2Cypher planning guard to
reject writes. The reservation command from Module 3 remains outside the
Gateway. The workshop reuses the same Neo4j credential here to keep setup
simple. In production, connect both functions with a read-only Neo4j user for a
database-enforced boundary.

`mcp-proxy-for-aws` authenticates with IAM SigV4 and signs each request with the
caller's AWS credentials. This connection does not require an API key.

:warning: The participant IAM policy grants access by ARN prefix. Name Lambda
functions `hotel-booking-*`, IAM roles `workshop-*` or
`AmazonBedrockAgentCoreSDK*`, and secrets `workshop-*`, `neo4j-ws-*`, or
`bedrock-agentcore-*`. Resources outside these prefixes return `AccessDenied`
for participants whose permissions use the workshop policy.

After verifying both tools directly over MCP, the notebook gives the resolved
Gateway tools to a Strands agent. A trace shows the agent selecting a remote
tool and using its evidence in the answer. Module 6 later provides the
workshop's hands-on cross-session memory lab.

## Files in This Folder

| File | Purpose |
|---|---|
| `4.1_agentcore_gateway.ipynb` | Gateway, Lambda tools, IAM-authenticated MCP, and a Gateway-backed Strands agent |
| `lambda_tools/` | One directory per Lambda handler, plus the shared requirements |

## The workshop page

`site/content/04-production-agent/index.en.md`
