[< Back to the workshop README](../../README.md)

# Module 4: Production Agent with AgentCore

The Module 3 booking agent calls Python tools in the same notebook kernel and
keeps conversation state only for that session. This module deploys the
retrieval tools behind a managed MCP endpoint and adds memory that persists
across sessions. Strands passes both local functions and resolved MCP tools to
the agent through its `tools` interface.

**At a Glance**

- **Problems addressed:** remote access to retrieval tools, IAM authentication, and cross-session memory.
- **Neo4j:** The Lambda tools are intended for retrieval. The fixed search uses reviewed Cypher, while the Text2Cypher tool uses a planning guard to reject writes.
- **AWS:** AgentCore Gateway, AWS Lambda, IAM SigV4, Secrets Manager for the Neo4j credential, and AgentCore Memory.
- **You'll build:** Lambda functions under the `hotel-booking-*` prefix, one Gateway, the IAM roles under `workshop-*`, and one AgentCore Memory resource.

---

## The Two Notebooks

| Notebook | What it demonstrates |
|---|---|
| [`4.1_agentcore_gateway.ipynb`](4.1_agentcore_gateway.ipynb) | Deploy the shared search function and a reusable Text2Cypher function, then call both over IAM-authenticated MCP |
| [`4.2_agentcore_memory.ipynb`](4.2_agentcore_memory.ipynb) | Store a preference in one session and recall it in another session with no conversation history |

Run `4.1` first. `4.2` connects to the Gateway `4.1` created.

Both notebooks can be launched from the repository root, `notebooks/`, or this
module directory. Module 4.1 always packages the `lambda_tools/` tree from this
folder.

## Part 1: Deploy Retrieval Tools

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

## Part 2: Add Managed Memory

AgentCore Memory runs two extraction strategies over the raw transcript:
`SEMANTIC` for facts and `USER_PREFERENCE` for preferences. Both run
asynchronously. Notebook `4.2` waits for extraction and reads the records from
the Memory service before opening another session. This shows both the
extracted content and its processing delay.

The second session uses the same actor ID but has no conversation history. The
Gateway has no preferences tool, so the agent retrieves the room preference
from long-term memory.

The recalled preference arrives through a service API without a link to its source message or the related `Hotel` node. This workshop does not provide an in-place editing workflow for managed memories. Module 6 demonstrates direct inspection and correction with Cypher.

## Files in This Folder

| File | Purpose |
|---|---|
| `4.1_agentcore_gateway.ipynb` | Gateway, Lambda tools, IAM-authenticated MCP |
| `4.2_agentcore_memory.ipynb` | AgentCore Memory across two sessions |
| `lambda_tools/` | One directory per Lambda handler, plus the shared requirements |

## The workshop page

`workshop-content/content/04-production-agent/index.en.md`
