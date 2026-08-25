---
title: "Production Path"
weight: 85
---

## Overview

The workshop uses a small dataset and simple setup. A production system needs
stronger security, testing, monitoring, and data management.

- **Graph:** Secure, size, back up, and monitor Neo4j.
- **Ingestion:** Process each source change as an incremental update.
- **Quality:** Test retrieval and generated answers separately.
- **Operations:** Monitor Gateway, Lambda, Runtime, Bedrock, and Neo4j.
- **Memory:** Control who can create, read, correct, and delete stored data.

---

## Harden the Graph

- **Capacity:** Choose an Aura tier that fits the graph, indexes, and query load.
- **Database access:** Use separate Neo4j identities for reads and writes.
- **Read tools:** Give retrieval services read-only database access.
- **Write commands:** Grant only the permissions required for each command.
- **Secrets:** Store credentials in a managed secret store and rotate them.
- **Network:** Apply the network controls supported by the selected Aura tier.
- **Recovery:** Configure backups and test the restore process.
- **Monitoring:** Track query speed, errors, storage, and memory use.
- **Schema:** Version constraints, indexes, and migrations with the application.
- **Text2Cypher:** Use `EXPLAIN` and a read-only Neo4j identity. The database then rejects generated writes.

---

## Grow the Ingestion Pipeline

Module 1 processes a fixed set of documents. A production pipeline must process
new, changed, and deleted sources.

- **Stable identity:** Give every source, entity, and chunk a stable key. Use that key with idempotent `MERGE` operations.
- **Run metadata:** Record the source version, models, schema version, and ingestion time.
- **Validation:** Check labels, relationships, required properties, and provenance before publishing data.
- **Entity resolution:** Merge alternate names while keeping different entities separate.
- **Embeddings:** Re-embed a chunk when its text or embedding settings change.
- **Indexes:** Populate and verify a new index before readers use it.
- **Deletion:** Remove facts from a deleted source and preserve shared entities.
- **Parsing:** Use code for reliable structured fields. Use model extraction for prose.
- **Testing:** Test extraction with held-out documents before release.

---

## Evaluate Retrieval and Answers Separately

Test retrieval before testing the final answer. This shows which layer caused a
failure.

- **Semantic question:** Confirm that vector search finds the correct source text.
- **Exact question:** Confirm that full-text search keeps the exact name or identifier.
- **Connected question:** Confirm that graph expansion returns the required fields and source.
- **Structured question:** Confirm that Cypher returns the correct records.
- **Unsupported question:** Confirm that the tool reports missing evidence and the agent abstains.
- **Retrieval quality:** Measure source coverage, field coverage, rank, and irrelevant context.
- **Answer quality:** Measure factual use of evidence, exact values, citations, and abstention.
- **Regression tracking:** Run the same tests after changes to chunks, models, retrieval settings, Cypher, or prompts.

---

## Operate Gateway Tools and the Runtime

- **Request tracking:** Pass one correlation ID through AgentCore, Lambda, Bedrock, and Neo4j.
- **Tool metrics:** Record tool name, duration, result count, retries, and failures.
- **Service alerts:** Track latency, errors, throttling, concurrency, Runtime failures, and cost.
- **Retrieval controls:** Test one known result and one empty result. A known result detects broken indexes and credentials.
- **Timeouts:** Set a timeout and retry policy for each network call.
- **Safe retries:** Make writes idempotent so retries cannot create duplicates.
- **Deployment record:** Record the source version, dependencies, model IDs, prompts, and tool schemas.
- **Sensitive data:** Keep secrets and unnecessary user content out of logs.

Module 4 and Module 5 show separate patterns. A design that connects Runtime to
Gateway adds another network call and access boundary. Measure the effect on
speed, cost, and operations.

---

## Add Security and Guardrails in Layers

- **Input validation:** Validate tool inputs before database or API calls.
- **Generated Cypher:** Run it with a read-only database identity.
- **IAM:** Grant access only to the required models, secrets, tools, and runtimes.
- **Bedrock Guardrails:** Apply prompt and response policies where required.
- **Tool separation:** Keep retrieval tools separate from write commands.
- **Database rules:** Enforce business rules and uniqueness in the write transaction.
- **Logging:** Review which prompts, results, and memory records may enter logs.

The model proposes an action. The command validates it. The database enforces
the final write rules.

---

## Govern Memory

Cross-session memory stores user data beyond one request. Define how the
application manages that data.

- **Identity:** Bind actor and session IDs to authenticated callers.
- **Authorization:** Check the actor before every memory read and write.
- **Lifecycle:** Define retention, deletion, correction, and export workflows.
- **Provenance:** Store the source message and application version for each record.
- **Review:** Record confidence or review state for model-extracted memory.
- **Domain links:** Limit which graph records a memory can reference.
- **Growth:** Define when to summarize, archive, or delete old conversations.
- **Neo4j memory:** Use it for explicit provenance, correction, and domain links.
- **AgentCore Memory:** Use it for managed extraction and AWS-operated recall.

---

## Keep the Portable Contracts

Keep these workshop contracts in production:

- **Pinned graph schema:** Use one queryable vocabulary for extracted data.
- **Source provenance:** Link each derived fact to its source.
- **Fixed retrieval interface:** Return one bounded result shape to callers.
- **Grounded answer policy:** State when the evidence cannot answer a question.
- **Transactional command:** Check rules, prevent duplicates, and write in one boundary.
- **Actor-scoped memory:** Start recall from an authenticated actor.

Test, deploy, and operate each contract as a separate component.

## Next

Head to [Wrap-up](../wrap-up/).
