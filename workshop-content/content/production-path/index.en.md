---
title: "Production Path"
weight: 85
---

## Move from a Workshop to an Operated System

The workshop optimizes for learning. It uses a small corpus, one AuraDB Free
instance, shared workshop credentials, and notebooks that create resources on
demand. A production system must optimize for reliability, security, measurable
quality, cost, and change over time.

The core architecture can remain the same. The work is to harden each boundary
and establish an operating process around it.

---

## Harden the Graph

Treat Neo4j as part of the application's production data plane:

- Choose an Aura tier and capacity that fit the graph, vector indexes, query load, recovery objectives, and availability requirements.
- Use separate Neo4j identities for retrieval and writes. Give retrieval services read-only access, and grant the reservation command only the permissions it requires.
- Store credentials in a managed secret store. Rotate them and remove `CONFIG.txt` from every deployed path.
- Apply the network controls supported by the selected Aura tier and AWS architecture.
- Configure backups, restore testing, query monitoring, and capacity alerts.
- Version the graph schema, constraints, indexes, and migrations with the application.

The application-level `EXPLAIN` check around Text2Cypher is useful, but it is
not the final authorization boundary. A read-only Neo4j identity ensures the
database independently rejects a generated write.

---

## Grow the Ingestion Pipeline

Module 1 extracts a fixed set of documents under a pinned schema. A production
pipeline must handle new, changed, and deleted sources without rebuilding all
data:

- Give every source, entity, and chunk a stable identity so ingestion can use idempotent `MERGE` operations.
- Record the source version, extraction model, embedding model, schema version, and ingestion time with each run.
- Validate extracted labels, relationships, required properties, and provenance before publishing new data to retrieval.
- Add entity resolution rules for alternate names while preserving cases where identical names describe different entities.
- Re-embed a chunk whenever its text or embedding contract changes.
- Plan index migrations so readers never depend on a partially populated index.
- Define how source deletions remove derived facts without damaging shared entities.

Keep deterministic parsing for fields that already have reliable structure.
Use model extraction where the source requires language understanding, and test
that boundary with held-out documents.

---

## Evaluate Retrieval and Answers Separately

Retrieval quality sets the evidence ceiling for the answer. Build an evaluation
set from representative user questions and include each question shape from the
workshop:

| Question shape | Evidence behavior to measure |
|---|---|
| Paraphrased description | The vector arm finds relevant source text |
| Exact name or identifier | The full-text arm preserves the exact match |
| Connected question | The graph expansion returns the required fields and provenance |
| Structured filter or aggregation | Cypher selects the correct database records |
| Unsupported question | The tool returns an explicit evidence gap and the agent abstains |

Measure retrieval first. Check whether the required source and graph fields were
returned, how highly they ranked, and how much irrelevant context accompanied
them. Measure generation separately. Check whether the answer used the returned
evidence, preserved important values, cited its source, and declined unsupported
claims.

Track these results when changing chunking, embedding models, fusion behavior,
top-k values, traversal Cypher, prompts, or foundation models. A single final
answer score cannot show whether a regression came from retrieval or generation.

---

## Operate Gateway Tools and the Runtime

Instrument both production patterns built in the workshop:

- Record request and correlation identifiers across the caller, AgentCore, Lambda, Bedrock, and Neo4j.
- Capture tool names, durations, result counts, retries, throttles, model usage, and failures without logging secrets or unnecessary user content.
- Alert on latency, error rate, repeated empty results, Lambda concurrency, Runtime failures, and cost changes.
- Keep a positive retrieval control alongside negative controls. Empty results are expected for some questions, but they can also signal a broken index or credential.
- Define timeouts and retry behavior at every network boundary.
- Make every write idempotent so a caller or service retry cannot create duplicate work.
- Pin and inventory the deployed source, dependencies, model identifiers, prompts, and tool schemas.

Module 4 and Module 5 remain separate patterns. If a production design combines
Runtime with Gateway, evaluate the added network hop, authorization boundary,
latency, and operational ownership explicitly.

---

## Add Security and Guardrails in Layers

Use independent controls so one failed check does not expose the full system:

- Validate tool inputs before database or API calls.
- Keep generated Cypher on a read-only path and restrict procedures that a retrieval identity can call.
- Limit IAM roles to the required models, secrets, functions, gateways, and runtimes.
- Apply Bedrock Guardrails where prompt and response policy requires them.
- Separate read tools from commands that change business state.
- Enforce business rules and uniqueness constraints inside the write transaction.
- Review what source text, prompts, tool results, and memory records may appear in logs.

The model can propose an action. The command and database decide whether that
action is valid and authorized.

---

## Govern Memory

Cross-session memory creates durable user data. Define its lifecycle before
expanding beyond the workshop preference:

- Bind actor and session identifiers to authenticated callers.
- Authorize every recall against the selected actor rather than trusting an identifier supplied in the prompt.
- Define retention, deletion, correction, and export workflows.
- Preserve the source message and application version that produced each durable record.
- Record confidence or review state when a model extracts memory automatically.
- Limit which domain nodes a memory record may reference.
- Monitor growth and decide when to summarize, archive, or remove old conversations.

Neo4j graph memory is useful when records need explicit provenance, correction,
and relationships to domain data. AgentCore Memory is useful when managed
extraction and AWS-operated recall better fit the application. A production
system can use each for a different class of memory.

---

## Keep the Portable Contracts

Several workshop decisions should survive the move to production:

1. **Pinned graph schema:** extraction writes a vocabulary that applications can query consistently.
2. **Source provenance:** every derived fact can be inspected against the material that produced it.
3. **Fixed retrieval interface:** callers receive one bounded result shape instead of configuring retrieval for each request.
4. **Grounded answer policy:** missing evidence produces abstention rather than invention.
5. **Transactional command:** rule enforcement, idempotency, and the write occur behind one reviewed boundary.
6. **Actor-scoped memory:** recall starts from an authenticated actor and follows explicit relationships.

These contracts turn the workshop demonstrations into components that can be
tested, deployed, and operated independently.

## Next

Head to [Wrap-up](../wrap-up/).
