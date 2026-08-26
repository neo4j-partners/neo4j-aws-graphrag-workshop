---
marp: true
theme: default
paginate: true
---

<style>
section {
  --marp-auto-scaling-code: false;
}

li {
  opacity: 1 !important;
  animation: none !important;
  visibility: visible !important;
}

/* Disable all fragment animations */
.marp-fragment {
  opacity: 1 !important;
  visibility: visible !important;
}

ul > li,
ol > li {
  opacity: 1 !important;
}
</style>

# Deploying to AgentCore Runtime

The whole agent becomes a service someone else can call

<!--
The hinge is slide 7, what to cache and what to rebuild, because it is the one
decision in this deck that is genuinely easy to get wrong and produces a
correctness bug rather than a performance one.

The other thing to protect is slide 8. This module connects to Neo4j directly
and does not use the Gateway from Module 4. That is deliberate, and if you do
not name it, half the room will assume you skipped a step.
-->

---

## Where We Left Off

The tools ran in Lambda. The agent still ran in your notebook. Now the agent moves too.

> Which Chicago hotel has both a spa and a swimming pool, what is its cancellation policy, and can I hold it for four guests?

Third deployment, same question, same answer.

<!--
Recall line, plus the one-sentence framing of the module.

The hero question has now crossed three boundaries: a notebook process, a
Gateway and a Lambda, and a container invoked over an API. The answer has not
changed once, and that is the claim this module has to earn.
-->

---

<style scoped>
/* Four rows of two-column prose. */
section { font-size: 25px; }
</style>

## What Changes When the Agent Moves

| Module 3 | Module 5 |
|---|---|
| Runs in your kernel | Runs in a container AgentCore starts |
| The notebook environment holds the Neo4j password | The Runtime holds it, injected at launch |
| Reachable only from Jupyter | Invoked through `InvokeAgentRuntime` by authorized AWS clients |
| The session is your kernel's memory | Each invocation carries a caller-provided session ID |

Same retrieval, same reservation rule. Only the request handling is new.

<!--
Row four is the interesting one and it comes back on slide 9. In a notebook the
conversation lives in your kernel because there is exactly one caller. A
service has many, and it needs to be told which conversation a request belongs
to.

One difference from Module 3 worth naming: there, the reservation command was
plain Python the notebook called directly. Here both operations are exposed as
tools, and the guest-limit rule is still enforced by Neo4j inside the write
transaction.
-->

---

## What Runtime Provides

- **Session isolation:** each session gets its own microVM, with its own CPU, memory, and file system
- **Session lifetime:** a session ends after 15 idle minutes, or 8 total hours
- **Scaling:** AWS starts and stops containers, picks the instance size, and patches the hosts
- **Invocation API:** clients call `InvokeAgentRuntime` with an ARN, a session ID, and a JSON payload
- **Access control:** IAM decides who may invoke. Runtime also accepts OAuth 2.0 bearer tokens
- **Versions:** each update creates a new version, and the `DEFAULT` endpoint moves to it

<!--
Per-session microVM isolation is a stronger boundary than the usual container
story, and it is worth a beat. One caller's session is not sharing a process
with another caller's.

The versions bullet has a practical consequence: rerunning the notebook ships a
new version behind the same ARN, so callers do not change anything.

Runtime also supports up to 8-hour invocations and streaming over server-sent
events or a WebSocket. This agent returns one JSON object instead, which keeps
the smoke tests simple.
-->

---

![bg contain](../images/05-agentcore-runtime-architecture.svg)

<!--
Trace one invocation. An authorized AWS client calls InvokeAgentRuntime. The
Runtime box runs GraphRagBookingAgent. Inside, booking_agent.py holds three
parts: the search_hotel_knowledge tool, the create_reservation tool, and the
BedrockModel connection.

Both tools reach Neo4j directly from inside the container. The retrieval tool
runs the hybrid retriever. The reservation tool runs the write that enforces
the guest limit inside its own transaction. BedrockModel calls Claude, which
reasons over what the tools returned.

Point at what is absent: there is no Gateway and no MCP server anywhere in this
picture. Slide 8 explains why.
-->

---

## The Container Contract

Runtime talks to the container over HTTP, and the contract is fixed.

```python
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload, context=None):
    ...
    return {"response": ..., "request_id": ..., "tools_used": ...}

if __name__ == "__main__":
    app.run()
```

- **Port 8080 on `0.0.0.0`.** Runtime posts every request to `/invocations`
- **`linux/arm64`.** Runtime runs ARM64 images
- **`BedrockAgentCoreApp`** serves the contract, so the agent code has no routing
- **`app.run()`** is the container start command, and it runs the agent locally too

<!--
The last bullet is the one that saves debugging. The same line that serves the
container serves it on your laptop, so you can exercise the entry point before
any of the deployment machinery is involved.

The entry point returns a dictionary and Runtime hands it back to the caller as
JSON. Note what is in it besides the response text: the request id, the tools
the model actually used, the grounding result, and the command result. The
smoke tests assert on those structured fields rather than on prose.
-->

---

## Building for arm64

Docker copies only from its build context, and the agent depends on two things outside it.

- **`notebooks/workshop/`**, the shared retrieval package, staged and built as a wheel
- **`reservation_command.py`** from Module 3, staged beside it
- **`BUILD_INFO.txt`** records the git commit and working-tree status inside the image
- **CodeBuild** produces the `linux/arm64` image and pushes it to ECR

The staged copies are git-ignored and replaced on every run. The originals stay the source of truth.

<!--
Staging rather than restructuring the repository is the pragmatic choice, and
the thing that keeps it honest is that the copies are ignored and rewritten
every run. Nobody edits the copy by accident and wonders why the fix did not
land.

Building in CodeBuild rather than locally is not about speed. Native Python
packages have to match the container's processor architecture, and most people
in the room are not building on arm64.

BUILD_INFO.txt is a small habit worth stealing. When a deployed agent
misbehaves, the first question is what source it was built from.
-->

---

## What to Cache and What to Rebuild

AgentCore keeps the microVM warm between invocations. Split your code accordingly.

- **Cache:** the Neo4j drivers and the hybrid retriever, so connection pools survive
- **Rebuild every request:** the Strands `Agent` and its message history

A Strands `Agent` accumulates conversation state as it runs. One shared across callers leaks one caller's messages into another's.

<!--
The hinge, and the one bug in this deck that is a correctness bug rather than a
latency one.

The instinct that causes it is good instinct. Creating the Agent once at module
level looks like exactly the optimization the warm container invites, and it
works perfectly in testing with one caller. It fails in production, silently,
by mixing conversations.

The rule that generalizes: cache what is stateless and expensive, rebuild what
carries state. Connection pools are stateless and expensive. Conversation
history is the state itself.
-->

---

## Direct to Neo4j, No Gateway

This deployment does not use the Module 4 Gateway. Both tools call Neo4j from the same process that received the request.

| Choose Gateway when | Choose Runtime-direct when |
|---|---|
| Several agents share one set of tools | The agent is the unit you deploy |
| The tools belong to a different team | One team owns the whole thing |
| You want tool calls governed centrally | You want one network hop, not three |

Two patterns. Neither one is the mature version of the other.

<!--
Say this clearly, because the run order makes Module 5 look like the sequel to
Module 4 and it is not.

Module 4's chain is agent, Gateway, Lambda, Neo4j. Module 5's is agent, Neo4j,
from inside one container. Fewer hops and less to operate, at the cost of the
tools not being reusable by anything else.

Both are real production shapes. The question to ask is whether the tools or
the agent is the thing other people need to call.
-->

---

## Sessions and Request IDs

Two identifiers, doing two different jobs.

- **Session ID:** supplied by the caller, routes invocations to the same container, and scopes the conversation
- **`request_id`:** supplied by the caller, carries idempotency for the reservation write

A hook requires the reservation tool to use the caller's exact UUID. A retry returns the first result and the graph keeps one node.

Each smoke test gets its own session ID, so every test starts clean.

<!--
Attendees conflate these. Session is about conversation continuity. request_id
is about write safety. A session can contain many requests, and a request_id
can outlive a session when a client retries after a disconnect.

The hook matters because without it the model could generate its own UUID on
the retry, which would produce a second reservation for the same intent. This
is the same idempotency guarantee Module 3 built, carried across the network
boundary.
-->

---

<style scoped>
/* Five rows of two-column prose plus framing. */
section { font-size: 24px; }
</style>

## The Five Smoke Tests

| Test | What it proves |
|---|---|
| Hotel details | Retrieval returns the recorded address, `789 Corniche el-Nil, Cairo 11519, Egypt` |
| Unknown hotel | The request is rejected, and Neo4j records nothing |
| Availability question | `answerable: false`, `missing_fact: live_room_availability` |
| 15-guest request | `status: rejected`, and no node is written |
| 10-guest request, sent twice | One node created, the retry returns `duplicate=true` |

Each test asserts on structured tool results, not on the model's prose.

<!--
The order is deliberate. Hotel details runs first because a broken retriever
makes the agent decline every question, and a refusal test that passes for the
wrong reason is worse than no test.

That is the general lesson here: confirm the positive path before you assert on
refusals. Otherwise "the agent correctly declined" and "the agent is broken"
produce the same green check.

Asserting on structured fields rather than response text is what makes these
stable. Model prose varies between calls. answerable: false does not.
-->

---

## Observability

The container starts under `opentelemetry-instrument`, and AgentCore sends telemetry to CloudWatch.

- **Metrics, on by default:** invocations, sessions, latency, throttles, user errors, system errors
- **Traces and spans:** one span per step of the agent loop, a model call or a tool call, with timing
- **Logs:** a start line and a completion line per invocation, with the tools used and the command status
- **The failure log records the exception type only**, so connection details and credentials stay out of CloudWatch

Use `request_id` to connect every entry for one reservation.

<!--
The failure-log rule is a small decision with real consequences. Exception
messages routinely carry connection strings and occasionally credentials, and
CloudWatch is read by more people than your database console. Logging the type
and re-raising gives AgentCore what it needs to report the failure without
spilling the details.

Enable CloudWatch Transaction Search once per account to see spans. The GenAI
observability dashboard then draws the execution path, token usage, and an
error breakdown per session.
-->

---

![bg contain](../images/wrap-up-architectures.svg)

<!--
Three deployments, one design. This is synthesis, not restatement, so do not
walk the modules again.

The same hybrid_retrieval.py ran in all three. The retriever, the traversal,
and the result contract never changed. What changed was where the code executed
and who was allowed to invoke it.

Ask the room which of the three they would ship. There is no right answer, and
the discussion surfaces what they actually care about: reuse, blast radius,
operational surface.

What is deliberately left out of this deployment: OAuth inbound auth, secrets
read at call time instead of injected as environment variables, named endpoints
for staging, and streaming responses. Those are the four things a production
version adds.

Next: Module 6 gives the agent memory.
-->
