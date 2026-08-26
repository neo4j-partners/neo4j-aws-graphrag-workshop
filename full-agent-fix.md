# Plan: Teach a Model-Driven Strands Agent in Module 3

## Goal

Module 3 will teach the normal Strands agent pattern. A plain Strands agent will read two tool specifications, choose the best tool for each hotel question, inspect the result, and answer from that evidence.

The lesson will stay small enough for a workshop. It will avoid production cleanup systems, model-based grading, large contract frameworks, and unrelated Module 6 work.

## Status

- **Plan:** Updated after an in-depth design and consistency review.

- **Dependency floor:** Superseded by exact pins. The notebook requirements no longer carry a `neo4j-graphrag>=1.18.0` floor. The three packages the lesson depends on, `strands-agents`, `neo4j`, and `neo4j-graphrag`, are pinned with `==` in every site that declares them, so none of them resolves a range at install time. The remaining floors, on `numpy`, `pyarrow`, `boto3`, `botocore`, and the AgentCore and MCP packages, stay as they are.

- **Version pinning:** Applied. All four declaration sites pin `strands-agents==1.53.0`, `neo4j==6.2.0`, and `neo4j-graphrag==1.19.0`. The Runtime image declares Strands as `strands-agents[otel]==1.53.0`, and the retrieval Lambdas declare only `neo4j` and `neo4j-graphrag`, because they run no Strands agent. There is no deployed Runtime to match, so the versions were chosen and verified rather than inherited. Python 3.10 support is a hard gate because Vocareum runs 3.10, and all three pins clear it. `strands-agents==1.52.0` and `neo4j-graphrag==1.18.0` were held as the known-good fallback and were not needed.

- **Agent changes:** Done. Module 3 builds a plain Strands agent with automatic tool choice. The forced `tool_choice` and the custom model subclass are gone, `grounded_bedrock_model.py` is deleted, and the agent now reads two tool specifications and picks between them. The two read tools, `search_hotel_passages` and `query_hotel_records`, share one grounding contract in `workshop/grounding.py`, and their wrappers live in `workshop/agent_tools.py`.

- **Workshop content changes:** Partly done. Module 3's notebook and README are rewritten around the routing lesson, and the few-shot overlap in the routing table is disclosed in the notebook. Modules 2, 4, and 5 and the shared prose surfaces are untouched and belong to Phases 2 and 3.

- **Live verification:** Done for Modules 1 through 3. A clean Python 3.10.19 environment built from `notebooks/requirements.txt` resolved every pin with no dependency conflicts and no source builds, and executed `1.0_verify_environment`, `1.1_build_graph`, `2.1_connected_context`, and `3.1_grounded_booking_agent` end to end with no errors. Bedrock ran over SigV4 with an SSO profile rather than the revoked bearer token, which is written up in `aws-sso-validation.md`. The routing table scored 3 of 4, and the availability question returned `missing_fact: live_room_availability` as designed. Modules 4 and 5 are not verified and belong to Phases 2 and 3.

## Assumptions

- **Audience:** Participants are learning Strands, GraphRAG, Neo4j, and AgentCore. They need a clear agent loop more than a production architecture.

- **Deployment state:** No AgentCore Runtime is deployed and no students use the workshop. A complete fresh deploy follows this work. Model-visible tool names can change freely, with no aliases and no migration path.

- **Graph data:** The graph stores hotel text, hotel facts, room descriptions, and total room capacity. It does not store live room inventory.

- **Structured queries:** `Text2CypherRetriever` uses a second model call to generate Cypher. Neo4j plans the generated query with `EXPLAIN` and runs it only when the plan is read-only.

- **Installation:** The supported workshop setup installs `notebooks/requirements.txt`. Four files declare these dependencies: that file, `notebooks/workshop/pyproject.toml`, `notebooks/04-production-agent/lambda_tools/requirements.txt`, and `notebooks/05-agentcore-deploy/runtime_app/agent_requirements.txt`. Pin the same exact versions in all four before validation. Update comments that currently say participant dependencies float on purpose.

## Core teaching outcome

- **Agent loop:** The user asks a question. The model reads the tool specifications. The model chooses a tool. Strands runs the tool. The result returns to the model. The model writes the final answer.

- **Tool specification:** The model sees each tool name, description, and input schema. The docstring supplies important metadata, but it is not the complete tool specification.

- **Tool policy:** The system prompt states when hotel facts require tool evidence. Tool specifications explain which tool fits each question.

- **Grounding:** The answer uses only facts returned by tools. The agent states what is missing when the tools do not support an answer.

- **Observability:** A trace shows the chosen tool, its input, its status, and its bounded result.

- **GraphRAG choice:** Passage search answers text questions. Structured graph queries answer questions that require counts, averages, rankings, filters, or relationship logic.

## Problems in the current Module 3 design

- **Forced tool use:** `GroundedBedrockModel` inserts `tool_choice={"any": {}}` for each fresh user turn.

- **Single choice:** Module 3 registers one tool, so the model has no meaningful routing decision.

- **Question blindness:** A social message such as “thanks” also triggers retrieval.

- **Hidden structured path:** Module 4 introduces `graph_query` even though Module 3 never teaches the agent when to use it.

- **Weak local description:** The Module 3 tool description says what the tool returns but gives little routing guidance.

- **Brittle answer check:** The availability cell grades a small list of model phrases instead of checking tool selection and tool evidence.

- **Module mismatch:** Module 5 already uses a plain `BedrockModel` with automatic tool selection.

## Design decisions

### Use the standard Strands agent

- **Decision:** Delete `notebooks/03-grounded-booking-agent/grounded_bedrock_model.py`.

- **Decision:** Build Module 3 with `Agent`, `BedrockModel`, two `@tool` functions, a system prompt, and `ToolTraceHook`.

- **Reason:** This is the model-driven Strands pattern that the workshop claims to teach.

- **Boundary:** The model keeps automatic tool choice. The system prompt requires tool evidence before the model states hotel facts.

- **Social turns:** Greetings, thanks, and other messages with no hotel facts can receive a direct response with no tool call.

### Register two read tools

- **Passage tool:** Use `search_hotel_passages` as the Python name and the model-visible name.

- **Structured tool:** Use `query_hotel_records` as the Python name and the model-visible name.

- **Naming rule:** Keep the Python wrapper name and model-visible name identical in participant code.

- **Internal functions:** Keep existing internal retrieval function names when they are implementation details. Rename participant-facing wrappers, schemas, and Runtime tools. This keeps the lesson consistent without forcing unrelated internal changes.

- **Passage meaning:** The passage tool returns up to five relevant text passages plus linked hotel facts.

- **Record meaning:** The structured tool returns rows from model-generated read-only Cypher.

- **Physical resources:** Because the deploy is fresh, name the new Lambda functions after the new tools so the physical name and the model-visible base name agree. Delete the tool-name to physical-name indirection instead of preserving it.

### Make tool descriptions short and complete

- **First paragraph:** Put the full routing rule in the first paragraph of each docstring.

- **Passage description:** State that the tool finds up to five hotel passages and linked facts. State that it fits amenities, rooms, policies, services, and location details for one or a few hotels.

- **Passage boundary:** Direct counts, averages, rankings, and filters across many hotels to `query_hotel_records`.

- **Availability boundary:** State that neither read tool has live room availability.

- **Record description:** State that the tool runs model-generated read-only Cypher over stored hotel facts.

- **Record uses:** State that it fits counts, averages, rankings, filters, and relationship questions.

- **Record boundary:** Direct questions that need source wording from hotel text to `search_hotel_passages`.

- **Result limit:** State that aggregates can cover all matching records and list results return at most 25 rows.

- **Empty result:** State that empty records mean the generated query returned no rows. They do not prove that the graph lacks the requested fact.

- **Input schema:** Describe `query` as the guest’s natural-language hotel question and require a non-empty value.

- **Local validation:** Make both decorated wrappers reject empty and whitespace-only queries when they run. Do not rely on the generated Strands schema to express minimum length.

- **Cross-tool names:** Keep tool names out of the system prompt. Allow each tool description to name the other tool when that makes the boundary clear.

### Show the actual tool specifications

- **Inspection cell:** Add a short Module 3 cell that prints the final `tool_spec` for both decorated tools.

- **Definition order:** Define both decorated tools without requiring live Neo4j or AWS credentials. Require credentials only when a tool runs.

- **Teaching point:** Explain that the model sees a name, a description, and an input schema.

- **Version safety:** Confirm that all routing text appears in the printed description. This avoids relying on undocumented docstring parsing details.

- **Test scope:** Check the final tool specifications instead of comparing raw docstrings byte for byte.

### Keep the Gateway schema and Lambda contract aligned

- **Schema owner:** `notebooks/04-production-agent/tool_schemas/tools.json` owns the model-visible tool metadata for the AgentCore Gateway.

- **Lambda role:** The Lambda handlers do not define model-visible tool schemas. They implement the input and output contract advertised by the Gateway.

- **Gateway names:** Replace both old tool names in `tools.json` with `search_hotel_passages` and `query_hotel_records`.

- **Gateway descriptions:** Give each Gateway tool the same routing meaning as its Module 3 tool. Exact whitespace and docstring formatting can differ.

- **Source schema:** Keep one required `query` string in `tools.json`. Keep the minimum-length and extra-property rules there as the complete workshop contract.

- **Registered schema:** Pass only the schema fields supported by AgentCore when the Gateway target is created. Do not claim that AgentCore enforces fields removed by `gateway_input_schema`.

- **Handler input:** Make both Lambda handlers read the same `query` field and reject missing, non-string, empty, whitespace-only, and extra values. The handlers enforce rules that the registered Gateway schema cannot express.

- **Common success envelope:** Return `ok`, `grounding_result`, and the tool-specific data from both read tools.

- **Passage output:** Return bounded passage records under `passages` and the small grounding verdict used by the agent.

- **Structured output:** Return generated Cypher under `cypher`, bounded rows under `records`, and the same small grounding verdict after a successful query.

- **Error output:** Return `ok: false` with a short error code and message for expected Lambda validation and Text2Cypher failures.

- **Output schema:** Do not add a formal Gateway output schema unless AgentCore requires one. Test the Lambda return shapes directly.

- **Lambda naming:** Name the fresh Lambda functions after the new tools and remove the mapping layer that existed only to bridge a model-visible name to a differently named function.

- **Rerun conflicts:** Keep the `ConflictException` handling, which fires when a participant re-runs a cell even in a brand-new account. State plainly that it skips rather than updates an existing target, which is correct for a fresh deploy.

- **Gateway prefix:** Explain that AgentCore prefixes the base tool name with its target name. Normalize that prefix in verification and compare base names.

- **Contract test:** Compare the common supported schema fields. Check the base name, routing meaning, query type, and required field. Test minimum length and extra-property rejection at the Lambda boundary.

### Use a cross-tool system prompt

- **Role:** Identify the agent as an AnyCompany hotel-information assistant.

- **Evidence rule:** Require an available tool before the agent states hotel facts.

- **Selection rule:** Tell the model to choose from the tool names, descriptions, and input schemas.

- **Grounding rule:** Allow only facts returned by tools.

- **Abstention rule:** Tell the model to state what is missing when results do not support the answer.

- **Conversation rule:** Allow direct replies to greetings, thanks, and other turns that require no hotel fact.

- **Composition rule:** Allow more than one tool when one question needs more than one kind of evidence.

- **Routing boundary:** Keep question-specific routing rules in tool descriptions. Keep shared behavior in the system prompt.

- **Module reuse:** Share the base grounding policy across Modules 3, 4, and 5. Let Module 5 add its reservation and hotel-identity policy because it also has a write tool.

- **Reservation exception:** Keep read-routing names out of the base prompt. Let the Module 5 extension name `search_hotel_passages` because that tool must supply the stable `hotel_id` before a write.

### Return clear tool results

- **Success status:** Use a normal Strands success result for completed tool calls.

- **Structured content:** Return bounded JSON data that keeps numbers as numbers and fields as named fields. Use the common success envelope for both read tools.

- **Local content:** Return native JSON content from local Strands tool results. A plain dict does not achieve this. `_wrap_tool_result` in `strands/tools/decorator.py` passes a dict through only when it carries both `status` and `content`, and otherwise serializes it into a text block, so a tool must return `{"status": "success", "content": [{"json": {...}}]}`. `ToolResultContent` supports a `json` field. `ToolTraceHook` reads only text blocks today and must be extended to read json blocks.

- **Error status:** Keep tool execution errors separate from successful empty results.

- **Local behavior:** Rely on the Strands decorator to convert unexpected local exceptions into error tool results.

- **Bounded errors:** Catch the full expected failure set in the decorated local tool and return a short Strands error result. `Text2CypherRetriever` catches only `CypherSyntaxError` itself, so three failures reach the caller: the read-only `EXPLAIN` guard raises `Text2CypherRetrievalError`, valid Cypher with invalid semantics raises `neo4j.exceptions.ClientError`, and query generation failures raise `LLMGenerationError`.

- **Gateway behavior:** Convert the same expected query failure at the Lambda boundary into valid JSON with `ok: false`. Treat this as an application error payload, not a Strands transport error status.

- **Unexpected failures:** Let unexpected infrastructure failures remain visible. Do not convert an outage into an unsupported-fact verdict.

- **Error meaning:** Describe a query error as a failed query generation or execution attempt. Do not claim that every error proves a schema limitation.

- **Cypher evidence:** Return generated Cypher on successful structured calls so participants can inspect what the database ran.

- **Empty result meaning:** Keep empty records as a successful query with zero returned rows.

### Explain the nested model call

- **First model decision:** The Strands agent model chooses which tool to call.

- **Second model decision:** `query_hotel_records` asks a model to generate Cypher inside the tool.

- **Database step:** Neo4j plans the generated Cypher and runs it only when the plan is read-only.

- **Review step:** The participant inspects the generated Cypher and returned rows.

- **Accuracy statement:** A valid query can still express the wrong meaning. The workshop should present generated Cypher as inspectable evidence, not as proof of correctness.

### Keep grounding checks small

- **Verdict and evidence are different things:** The verdict says whether the question can be answered from the graph. The evidence is what a tool returned. The verdict is shared because it describes the question against the graph rather than the retrieval mechanism, and both tools read the same graph, so live room availability is unsupported on either path. The evidence differs by tool, and that difference is the lesson.

- **Shared helper:** Create the shared verdict in `notebooks/workshop/grounding.py` before Module 3 uses it. Reuse it in Modules 3, 4, and 5.

- **Verdict fields:** The verdict is exactly `answerable` and `missing_fact`. Nothing else. That uniformity is what lets both Lambda handlers return one `grounding_result` and lets the Runtime iterate `grounding_results` without inspecting types.

- **Evidence fields:** The passage tool returns `hotel_ids` and `top_result`. The structured tool returns `cypher`, `records`, and `row_count`. Evidence sits beside the verdict in the payload, not inside it.

- **Existing fields:** `hotel_ids` and `top_result` keep their current shape and position. They are reclassified as passage evidence, not restructured, so the Module 5 deploy checks that read them, including the `top_result` address control, keep working unchanged.

- **Unsupported fact:** Represent live room inventory as an explicit unsupported fact. Do not infer this limitation from field names alone.

- **Detection mechanism:** Set `missing_fact` from the small casefolded query-term check that `booking_agent.py` already uses, lifted into `notebooks/workshop/grounding.py` as the shared implementation. Module 5's refactor has to reproduce today's verdict for the availability question, so reuse it rather than invent a replacement. The large keyword contract this plan excludes is the per-fact contract machinery, not this check.

- **Excluded machinery:** Skip generated `available_fields`, `schema_gap_problems`, a large keyword contract, and model-based answer grading.

- **Final prose:** Do not grade the final answer against a required phrase list.

- **Notebook check:** Report whether a tool ran and whether its structured grounding verdict marks live availability as unsupported.

- **Detection language:** Say that notebook checks detect a bad choice during the lab. Do not say they prevent bad behavior in a deployed agent.

### Use simple observability

- **Trace hook:** Add `ToolTraceHook` to Module 3 as the visible teaching aid. Module 3 has never used it and does not import `workshop_utils` today. Module 4 already uses it.

- **JSON display:** Extend the hook to accept native JSON content and JSON text content. Gateway results may still arrive as text.

- **Routing evidence:** Read selected tool names from the invocation result metrics.

- **Result evidence:** Extend `ToolTraceHook` with a small in-memory call list that records each tool name, status, and complete bounded payload. Truncate only the displayed trace.

- **Fresh trace:** Create a fresh trace hook for each routing case so recorded calls cannot leak between examples.

- **Runtime recorder:** Extend `ToolResultRecorder` to record every read-tool result. Return them as a small `grounding_results` list so a request can use both read tools.

- **Scope:** Avoid telemetry exporters, dashboards, and production monitoring systems.

## Workshop demonstrations

### Required examples

- **Passage question:** Ask what amenities and guest rating AnyCompany Cairo Nile View has. Expect `search_hotel_passages`.

- **Aggregate question:** Ask for the average guest rating of hotels in Paris. Expect `query_hotel_records`.

- **Count question:** Ask how many hotels offer a spa. Expect `query_hotel_records`.

- **Few-shot overlap:** Resolved by disclosure. Both structured questions above appear verbatim in `GRAPH_QUERY_EXAMPLES` in `notebooks/workshop/hybrid_retrieval.py`. The routing lesson still holds, but the generated Cypher shown is recall rather than generalization. The Module 3 routing-table markdown now states this directly: it names the two overlapping questions, says they are there because they show the routing rule cleanly rather than because they are hard, and invites the participant to swap in a structured question of their own.

- **Policy question:** Ask for the source wording of the cancellation policy at AnyCompany Cairo Nile View. Expect `search_hotel_passages`.

- **Unsupported question:** Ask whether AnyCompany Cairo Nile View guarantees availability next weekend. Require a tool call and an unsupported live-inventory verdict. Keep this case outside the routing score because either read path may recognize the limitation.

- **No-tool question:** Send “thanks, that is all.” Expect no tool call.

- **Call count:** Use these routing examples as the main demonstration. Do not repeat the same questions in separate teaching cells.

### Routing table rules

- **Fresh context:** Build a fresh agent for each routing-table question so earlier messages cannot influence later choices.

- **One student pass:** Run each routing case once in the participant notebook.

- **Visible outcome:** Show the question, expected tool, observed tool, and a short success or warning message.

- **No hard failure:** Print a pass or warning line for each case and let the cell finish. Do not use `report_problems`, which raises `ReadinessError`. A raising check over nondeterministic routing would intermittently break the clean-kernel run that Phase 1 validation depends on.

- **Release repetition:** Run the routing table five times during release rehearsal only. Record any unstable question or description.

- **Fix order:** Improve the tool name or description first when routing is unstable. Add prompt routing only when the shared policy truly needs it.

## Scope by module

### Module 2

- **Retriever table:** Present Text2Cypher as the structured path that Module 3 will register as a second tool.

- **Handoff:** Name both Module 3 read paths instead of selecting one retriever.

- **Comparison:** Run the Paris average question through passage search and Text2Cypher.

- **Lesson:** Show that five passages cannot produce a reliable average across the full matching set.

- **Diagram:** Present Text2Cypher as a selected structured path instead of an optional side path.

### Module 3

- **Model:** Replace `GroundedBedrockModel` with a plain `BedrockModel`.

- **Tools:** Register `search_hotel_passages` and `query_hotel_records`.

- **Tool setup:** Define both tools before checking live credentials. Keep credential checks inside the invocation path.

- **Specifications:** Print both final tool specifications before invoking the agent.

- **Prompt:** Apply the shared cross-tool grounding policy.

- **Trace:** Show each tool call and bounded result.

- **Routing:** Add the isolated routing table and the no-tool social turn.

- **Grounding:** Replace phrase matching with structured tool and verdict checks.

- **Failure lesson:** Explain query errors and empty results. Do not depend on a natural-language question to produce a deterministic Text2Cypher error.

- **Write lesson:** Keep the deterministic reservation rule checks unchanged.

### Module 4

- **Gateway tools:** Update the base names, descriptions, and supported input schemas.

- **Gateway names:** Explain the target prefix in the full model-visible name. Show the normalized base name in comparisons.

- **Lambda naming:** Name the new Lambda functions after the new tools and remove the tool-name to physical-name indirection in `4.1` cells 10 and 20.

- **Rerun safety:** Keep `ConflictException` handling for a participant who re-runs a cell, and document that it deliberately skips rather than updates.

- **Agent pattern:** Keep the plain `BedrockModel`, runtime tool loading, and automatic tool choice.

- **Prompt:** Use the shared grounding policy without hard-coded tool names.

- **Demonstration:** Add the Paris average question so the Gateway agent uses the structured tool.

- **Error boundary:** Return a valid bounded application error payload from the structured Lambda when Text2Cypher rejects or cannot execute its query.

- **IAM check:** Confirm that the structured Lambda role can invoke the configured Bedrock model.

- **Resource cleanup:** Not applicable. A fresh deploy leaves no stale workshop resources to clean.

### Module 5

- **Tool set:** Register both read tools beside `create_reservation`.

- **Prompt:** Reuse the shared grounding policy and add the existing reservation policy.

- **Grounding results:** Reuse the small shared verdict and record every read-tool result in `grounding_results`.

- **Reservation identity:** Require `search_hotel_passages` to supply a stable `hotel_id` before `create_reservation` runs. Use it after a structured lookup when the structured result does not contain a verified ID.

- **Tool choice:** State that the deployed agent uses the same automatic tool selection as Module 3.

- **Aggregate test:** Confirm that an aggregate question uses `query_hotel_records`.

- **Model comment:** Replace the stale Sonnet 5 comment with the configured workshop model information.

### Module 6

- **Scope:** Make no changes for this proposal.

- **Future idea:** Treat a memory-aware agent example as a separate workshop improvement.

## Tests

- **Tool specification test:** Import the tool definitions and check both base names, descriptions, and required `query` fields. Avoid exact description phrase checks.

- **Gateway schema test:** Check both entries in `tools.json` for the new base names, non-empty descriptions, and complete one-field input contract.

- **Schema alignment test:** Compare normalized base names and the schema fields supported by both Strands and AgentCore. Compare the query type and required field.

- **Lambda input test:** Confirm that both handlers accept a valid query and reject missing, non-string, empty, whitespace-only, and extra values.

- **Lambda output test:** Confirm the common success envelope, passage data, structured data, empty structured result, validation error payload, and expected Text2Cypher error payload.

- **Target mapping test:** Confirm that every Gateway schema base name resolves to one physical Lambda target. Confirm that target updates replace stale descriptions and schemas.

- **Targeted scope:** Check participant-facing wrappers, Gateway schemas, and Runtime tools. Avoid a repository-wide ban on old strings.

- **Related test plan:** `clean_tests.md` in the repository root covers overlapping test-removal work. Reconcile the two before deleting anything so the same files are not planned twice.

- **Current coverage:** No tests exist today for Module 3, Module 5, `tools.json`, the Lambda handlers, `hybrid_retrieval`, or `contracts`. Treat the tests in this section as new work rather than edits.

- **No CI:** `.github/workflows/` contains only `deploy-site.yml`, so pytest never runs in CI and every validation below is local.

- **Routing helper test:** Test tool-name extraction from fixed result metrics without calling a live model.

- **Grounding verdict test:** Confirm that live availability is unsupported for both read paths.

- **Empty result test:** Confirm that empty rows remain distinct from a tool error.

- **Error result test:** Confirm that an expected Text2Cypher failure becomes a Strands error result locally and an `ok: false` application payload through Lambda.

- **Notebook validation:** Run the notebook from a clean kernel. Do not add tests that inspect notebook cells, markdown wording, or exact cell structure.

- **Module alignment test:** Import shared definitions where practical and confirm the same two base read-tool names. Normalize the AgentCore target prefix.

- **Content tests:** Keep behavior tests. Remove tests that grep prose, notebook cells, SVG text, or exact routing phrases.

- **Dependency test:** Confirm that the four declaration sites agree with each other rather than that they match a version literal written into the test. `tests/test_dependency_pins.py` checks that `strands-agents`, `neo4j`, and `neo4j-graphrag` are pinned with `==`, that every site declaring a package resolves it to the same version as the others, that each site still declares the packages it is responsible for, and that the `workshop` package still admits the Python the hosted lab runs. A deliberate upgrade that touches every site stays green. An upgrade that misses one site fails.

- **Routing quality:** Verify description quality with the repeated live routing rehearsal. Do not encode natural-language routing quality as exact string assertions.

## Documentation, slides, and diagrams

- **Module 3 page:** Replace the one-tool and forced-call explanation with the two-tool automatic-selection loop.

- **Module 2 page:** Show why passage search and structured queries answer different question shapes.

- **Module 4 page:** Show the same two tools behind the Gateway.

- **Module 5 page:** Show both read tools plus the reservation write tool.

- **Foundations page:** Explain that the model receives tool names, descriptions, and input schemas.

- **Two prose trees:** Every page above exists twice, as Hugo `site/content/*/index.en.md` and as Antora `site/modules/ROOT/pages/*/index.adoc`. Update both.

- **Module READMEs:** Update the per-module READMEs. `notebooks/03-grounded-booking-agent/README.md` documents the deleted `grounded_bedrock_model.py`, and `tools/quality/check_repo.py` fails when prose names a path that does not exist.

- **Affected decks:** The retired names appear in `slides/overview-agent`, `slides/overview-mcp-gateway`, `slides/overview-agentcore-runtime`, `slides/overview-graphrag`, and `slides/overview-architecture`.

- **Slides:** Update agent, GraphRAG, Gateway, architecture, and Runtime decks where they show one tool or the old names.

- **Agent diagram:** Draw the model choosing between the passage tool and the record tool.

- **Structured path:** Show the nested model call inside `query_hotel_records` before Neo4j plans and runs Cypher.

- **Captions:** State that traces show the chosen path and returned evidence.

- **Diagram files:** Review `02-select-retriever.svg`, `03-grounded-agent-overview.svg`, `03-agentcore-architecture.svg`, `05-agentcore-runtime-architecture.svg`, `foundations-grounded-request-flow.svg`, and `DIAGRAM_PROMPTS.md`. Each SVG exists in several copies, under `site/images/`, `site/modules/ROOT/images/`, `site/modules/ROOT/attachments/slides/images/`, and `site/build/`. `DIAGRAM_PROMPTS.md` exists only under `site/images/`.

- **Visual checks:** Review changed diagrams visually. Do not add tests that search SVG text.

## Risks

- **Routing variation:** Automatic selection can vary between runs. Use clear tool boundaries, fresh contexts, and release rehearsal.

- **Generated query meaning:** Read-only Cypher can still answer the wrong question. Return the query and teach participants to inspect it.

- **Empty results:** A zero-row result can come from missing data or a poor generated query. Keep the wording honest.

- **Live inventory confusion:** `total_rooms` describes capacity. It does not describe current availability.

- **Extra latency:** The structured tool makes an additional Bedrock call before it queries Neo4j.

- **SDK parsing changes:** Print and test the final tool specifications instead of assuming how docstrings are parsed.

- **Rerun conflicts:** A participant who re-runs a Gateway cell hits `ConflictException` even in a fresh account, and the cell skips rather than updates. That is acceptable here, but it should be stated rather than left as a surprise.

- **Transport differences:** Local Strands, AgentCore Gateway, and Lambda represent names, schemas, and errors differently. Teach one shared contract and state each transport difference.

- **Version drift:** Open-ended dependency versions can change tool specifications or Text2Cypher behavior. Choose exact pins, verify them against Python 3.10, apply them to all four declaration sites, and run the full rehearsal with them.

- **Driver split:** Resolved. All four sites pin `neo4j==6.2.0`. The old notebook floor of `>=5.24.0` was below `neo4j-graphrag`'s own `>=5.28.4` requirement, so it was already understating what the notebooks need.

## Implementation phases

### Phase 1: Fix the Module 3 teaching design

**Status:** Done. Every checklist item below is complete and the end-to-end verification run has reported and passed: Modules 1 through 3 execute clean on Python 3.10.19 against a live Bedrock and Aura session, and routing reaches the expected tool on 4 of 4 sample questions.

The closing review turned up three things worth recording, all fixed. The routing tally first read 3 of 4 because the check asked `chosen == [expected]` while the system prompt tells the agent to call more than one tool when a question needs more than one kind of evidence. The agent obeyed the prompt on the first question and the check scored it a miss, so the ruler was wrong rather than the agent; it now asks `expected in chosen` and prints the tools actually used instead of the expected one. Separately, `MAX_CONTEXT_CHARS` capped every passage at 1,200 characters against documents of roughly 7,200, which cut mid-word inside the Cancellation Policy section and made the fourth question's request to quote recorded wording impossible to satisfy; the cap is now 8,000 and the agent quotes the policy in full. Module 2's driver was the one connection in the repo not suppressing Neo4j server notices, which put roughly 6.5KB of deprecation text in front of participants; it now matches the other three.

**Outcome:** Module 3 shows a plain Strands agent making a visible choice between two read tools.

**New files:**

- [x] **`notebooks/workshop/grounding.py`:** The shared verdict helper and the common success envelope. Write this first, because both tools depend on it.

- [x] **`notebooks/workshop/agent_tools.py`:** The two decorated wrappers, `search_hotel_passages` and `query_hotel_records`. One definition of each, imported by Module 3 now and by Module 5 in Phase 2, so the routing docstrings exist in exactly one place.

- [x] **`notebooks/workshop/prompts.py`:** The shared base grounding policy.

**Shared contract:**

- [x] **Verdict:** Exactly `answerable` as a bool and `missing_fact` as a string or none. The same two fields from both tools.

- [x] **Passage evidence:** `hotel_ids` and `top_result`, keeping their current shape and position so the Module 5 checks keep passing.

- [x] **Structured evidence:** `cypher`, `records` capped at 25 rows, and `row_count`.

- [x] **Success envelope:** `ok`, the verdict, and the tool-specific evidence beside the verdict rather than inside it.

- [x] **Result form:** Return `{"status": "success", "content": [{"json": ...}]}` so Strands keeps the payload as native JSON instead of serializing it into a text block.

**Module 3 notebook:**

- [x] **Standard model:** Delete `notebooks/03-grounded-booking-agent/grounded_bedrock_model.py` and use `BedrockModel` directly. Update the `README.md` reference to that file so `tools/quality/check_repo.py` still passes.

- [x] **Tool import:** Import both wrappers from the shared module. Define no agent code in a cell that needs live credentials.

- [x] **Credential boundary:** Confirm both tool specifications build with no live Neo4j or AWS access. `hybrid_retrieval.py` already builds embeddings and the LLM lazily inside `_get_retriever()`, so hoist the agent definitions out of the `if not RETRIEVAL_READY:` guard in cell 10 and keep the credential check on the invocation path.

- [x] **Tool specifications:** Print each tool's final `tool_spec` as JSON, and print the wrapper source with `inspect.getsource` so participants see the decorated function even though it lives in a module.

- [x] **System prompt:** Apply the shared policy with its evidence, selection, grounding, abstention, conversation, and composition rules.

- [x] **Trace:** Add `ToolTraceHook`, which Module 3 does not use today, and extend it to read json content blocks as well as text. Record each complete bounded payload and truncate only the display.

- [x] **Local input:** Reject empty and whitespace-only queries inside both wrappers.

- [x] **Bounded errors:** Catch `Text2CypherRetrievalError`, `LLMGenerationError`, and `neo4j.exceptions.ClientError`, and return short Strands error results. Keep errors distinct from empty results.

- [x] **Nested model explanation:** Explain how Text2Cypher adds a second model call inside the structured tool before Neo4j plans and runs the query.

- [x] **Routing table:** Run the four clear routing questions with a fresh agent for each case. Print a pass or warning line per case.

- [x] **Unsupported question:** Check the live-inventory verdict without grading exact model wording.

- [x] **Social turn:** Show that a closing thanks produces no tool call.

- [x] **Reservation checks:** Keep the deterministic reservation examples working. Verified in the live run: the over-limit request is rejected, one reservation is created and replayed idempotently, and the read-back cell confirms it in Neo4j.

**Dependency pins:**

- [x] **Choose versions:** Pick exact versions and verify them. Python 3.10 support is a hard gate because Vocareum runs 3.10. `strands-agents==1.52.0` and `neo4j-graphrag==1.18.0` are installed in `notebooks/.venv` and both support 3.10, so they are the known-good fallback if a newer release fails.

- [x] **Verified 3.10 floors:** Checked against PyPI metadata. `neo4j==6.2.0` declares `requires_python >=3.10`. `neo4j-graphrag` 1.18.0 and 1.19.0 both declare `>=3.10,<3.15`. `strands-agents` 1.53.0 declares `>=3.10`. Every candidate clears the gate, so the gate constrains future bumps rather than this one.

- [x] **Apply everywhere:** Pin the same versions in all four declaration sites, not only `notebooks/requirements.txt`.

- [x] **Standardize the driver:** Pin `neo4j==6.2.0` in all four sites, moving the notebooks off `>=5.24.0`. Both `neo4j-graphrag` 1.18.0 and 1.19.0 allow `neo4j<7.0.0`, so 6.2.0 is in range for either. Run the Module 1 and Module 2 graph work under the 6.x driver during validation, since that is the code most likely to depend on 5.x behavior.

- [x] **Comments:** Update the comment in `agent_requirements.txt` that says dependencies float on purpose.

**Deliberately not in this phase:**

- [x] **Module 5:** Do not touch `booking_agent.py` or its `_grounding_result`. Two verdict implementations coexist in the tree until Phase 2 refactors Module 5.

- [x] **AWS:** Every deployment change starts in Phase 2.

**Validation:**

- [x] **Unit tests:** Write and run new tests for the verdict helper, the success envelope, both tool specifications, tool-name extraction from fixed result metrics, and the error and empty-result shapes. None of this surface has tests today.

- [x] **Import check:** Done in a throwaway environment holding exactly `strands-agents==1.53.0`, `neo4j==6.2.0`, and `neo4j-graphrag==1.19.0`. Every API Phase 1 uses imports: `Agent`, `BedrockModel`, the hook events, `Text2CypherRetriever`, `HybridCypherRetriever`, both graphrag exceptions, `neo4j.exceptions.ClientError`, and all three new workshop modules.

- [x] **Notebook run:** Executed end to end from a clean kernel under the pinned environment, against live Neo4j and live Bedrock. All 12 code cells ran with zero error outputs. Reading the printed checks rather than only the error stream: the routing table reported 3 of 4 questions reaching the expected tool, the unsupported question returned `answerable: false` with `missing_fact: live_room_availability`, and the closing thanks produced no tool call. The one routing warning is the compound amenities-and-rating question, where the model called both tools instead of the single expected one. The run created one `ReservationRequest` node, which is what this notebook is designed to do.

- [x] **Known red suite:** Resolved by an explicit skip. One file was red: `tests/test_module3_availability_assertion.py`, 4 tests, all failing with `StopIteration`. No test imported the deleted model subclass, so that stated cause was wrong. The real cause is this phase's design change: the file searches the notebook for the `fabricated_availability_claims` phrase-grading cell, and this phase deliberately replaced phrase grading with reading the returned verdict. The file now carries a module-level `pytest.mark.skip` whose reason names the replacement check, points at `tests/test_agent_tools.py` for the live coverage, and says to delete the file rather than repair it. The four tests therefore report as skipped rather than quietly passing, and the file stays on the `clean_tests.md` retirement list to be removed in Phase 3. The suite is 293 passed, 4 skipped, and no failures. The passing count moved up from the 265 recorded earlier as tests were added after that count was taken, including the 15 checks in `tests/test_dependency_pins.py`.

- [x] **Review:** Confirm that every visible behavior supports the agent-loop lesson. Routing reads 4 of 4 and names the real tools used, passages arrive whole so a grounded quote is quotable, and Module 2 no longer buries its output in server notices.

### Phase 2: Align Modules 2, 4, and 5

**Status:** Pending

**Outcome:** The same two read tools and the same selection lesson continue from retrieval through Gateway and Runtime deployment.

**Checklist:**

- [ ] **Module 2 comparison:** Add the Paris average comparison and hand off both read paths.

- [ ] **Gateway schema:** Update both entries in `tools.json` with the new names, routing descriptions, and one-field query schemas.

- [ ] **Registered schema:** Pass only the AgentCore-supported schema fields when targets are created. Keep the complete contract in `tools.json`.

- [ ] **Lambda input contract:** Align both handlers with the required non-empty `query` field. Reject whitespace-only and extra values at the handler boundary.

- [ ] **Lambda output contract:** Return the common success envelope, including the shared verdict. Both handlers import the shared helper, so Module 4 is a consumer of it alongside Modules 3 and 5. Return `ok: false` application payloads for expected validation and Text2Cypher errors.

- [ ] **Passage field rename:** Rename the passage payload field from `context` to `passages` at every call site: `4.1` cells 13 and 22, both Lambda handlers, `booking_agent.py`, and the code samples in both prose trees. Grep for the old name before closing this item.

- [ ] **Lambda naming:** Name the fresh Lambda functions after the new tools and delete the tool-name to physical-name indirection in `4.1` cells 10 and 20.

- [ ] **Rerun conflicts:** Keep `ConflictException` handling for a participant who re-runs a cell, and document that it skips rather than updates.

- [ ] **Gateway prefix:** Normalize the target prefix when direct checks compare Gateway names with local names.

- [ ] **Gateway agent:** Use the shared grounding policy and add the aggregate demonstration.

- [ ] **Lambda error:** Return a bounded application error payload from the structured tool boundary. Keep unexpected infrastructure failures visible.

- [ ] **Runtime tools:** Register both read tools beside the reservation tool.

- [ ] **Runtime prompt:** Reuse the base grounding policy. Add the reservation rule that requires a passage result with a stable `hotel_id` before a write.

- [ ] **Runtime recording:** Record every read-tool verdict in a bounded `grounding_results` list.

- [ ] **Runtime response:** Update the deployment notebook and Runtime response checks to read `grounding_results` instead of one singular `grounding_result`.

- [ ] **Model comment:** Correct the stale model comment in the Runtime agent.

- [ ] **IAM check:** Confirm Bedrock access for the structured Lambda.

**Validation:**

- [ ] **Module tests:** Run the Module 2 behavior, Gateway schema, Lambda contract, Runtime, and model tests.

- [ ] **Direct tools:** Call both Lambda tools and inspect their success, empty, and application error shapes.

- [ ] **Gateway route:** Confirm one passage question and one aggregate question use different tools.

- [ ] **Runtime route:** Confirm the deployed agent uses the structured tool for an aggregate question.

- [ ] **Reservation handoff:** Confirm that a structured hotel choice receives a verified stable `hotel_id` before `create_reservation` runs.

- [ ] **Review:** Confirm that Module 5 adds reservation behavior while preserving the two read-tool lesson.

**Notes:**

- **Resource safety:** Do not delete shared AWS resources from a participant cell.

### Phase 3: Update teaching content and complete release verification

**Status:** Pending

**Outcome:** Notebooks, tests, pages, slides, and diagrams tell one accurate story and pass a full workshop rehearsal.

**Checklist:**

- [ ] **Site content:** Update Modules 2 through 5, foundations, summary, production path, and workshop index pages in both the Hugo `site/content/` tree and the Antora `site/modules/ROOT/pages/` tree.

- [ ] **Module READMEs:** Update the per-module READMEs so `tools/quality/check_repo.py` passes.

- [ ] **Slides:** Update every deck that shows the old names, one read tool, or forced tool choice.

- [ ] **Diagrams:** Draw the two-tool agent path and the nested Text2Cypher model call.

- [ ] **Diagram review:** Update and visually review every named SVG and `DIAGRAM_PROMPTS.md` entry that shows the old tool story.

- [ ] **Targeted tests:** Keep importable behavior tests for tool definitions, handlers, result envelopes, mapping, and Runtime behavior.

- [ ] **Retired tests:** Remove required-phrase, notebook-cell, markdown, and SVG text tests. Remove any test that depends on the deleted model subclass, which is what returns the suite to green. Reconcile this list with `clean_tests.md` first.

- [ ] **Vocareum starter code:** Bump the Vocareum starter-code pin so the hosted lab picks up this work. Recent commits do this by hand, which is why it needs to be a named release step rather than remembered.

- [ ] **Passage chunking:** Replace the raise-the-ceiling fix in `workshop/hybrid_retrieval.py` with section-sized chunks. `graph_config.CHUNK_SIZE` is 12000 against a 7,442 byte largest document, so one document is one `Chunk`, and `MAX_CONTEXT_CHARS` was raised from 1,200 to 8,000 so a whole document survives the trip to the model. That unblocked Module 3's request to quote recorded wording, which the 1,200 bound cut mid-word inside the Cancellation Policy section, but it makes every passage hit spend a full document of context. Split documents on their `###` section headings so a cancellation question retrieves the cancellation section, then lower `MAX_CONTEXT_CHARS` to fit a section. Do this last: it needs a graph rebuild, a regenerated prebuilt manifest, `tools/release` revalidation, and a re-run of Modules 2 and 3 against the new chunk shape.

- [ ] **Environment check:** Confirm that both read paths work before a workshop starts.

- [ ] **Plain language:** Shorten explanations, lead with purpose, and state technical cause and effect directly.

**Validation:**

- [ ] **Full test run:** Run the complete local test suite.

- [ ] **Notebook sequence:** Run Modules 2 through 5 in workshop order.

- [ ] **Routing stability:** Run the isolated routing table five times during release rehearsal.

- [ ] **Gateway rehearsal:** Deploy Module 4 and confirm that exactly two model-visible read tools appear.

- [ ] **Runtime rehearsal:** Deploy Module 5 and test passage search, aggregate query, unsupported availability, and reservation enforcement.

- [ ] **Visual review:** Check every changed page, slide, and diagram for the same names and behavior.

- [ ] **Final review:** Confirm that the workshop teaches standard Strands construction without production-only machinery.

**Notes:**

- **Evidence:** Save executed notebooks and concise release evidence in the existing evidence location.

## Completion criteria

- **Agent construction:** Module 3 uses a plain `BedrockModel` and normal Strands automatic tool selection.

- **Meaningful choice:** The agent has two read tools with clear and different purposes.

- **Visible specification:** Participants can see the actual name, description, and input schema sent to the model in each module.

- **Correct policy:** The prompt requires tool evidence for hotel facts and permits direct social replies.

- **Correct semantics:** Empty records, tool errors, unsupported facts, and successful results remain distinct.

- **Inspectability:** Structured results include generated Cypher on success.

- **Stable examples:** Passage, aggregate, count, policy, availability, and no-tool examples behave as described during rehearsal.

- **Cross-module consistency:** Modules 2 through 5 use the same two base read-tool names and routing story. Module 4 explains and normalizes the AgentCore target prefix.

- **Gateway contract:** `tools.json` advertises the same base names, routing boundaries, and query meaning as the local Strands tools. Gateway registration uses the supported schema subset.

- **Lambda contract:** Each handler enforces the complete input contract and returns the documented success, empty, and application error shapes.

- **Grounding contract:** Both read tools return the same two-field verdict, with their own evidence beside it rather than folded into it. Module 5 records every read-tool verdict used by one request.

- **Reservation safety:** Module 5 receives a verified stable `hotel_id` from `search_hotel_passages` before it calls the reservation tool.

- **Test design:** Automated tests check importable behavior and stable contracts. Live rehearsal checks routing quality and notebook flow.

- **Reproducible setup:** All four dependency declaration sites carry the same exact versions, those versions support Python 3.10, and the full rehearsal passes with them.

- **Small workshop scope:** The implementation adds no automatic cloud cleanup, model grader, telemetry system, or Module 6 extension.

- **Green validation:** The full test suite and end-to-end notebook rehearsal pass.

## Out of scope

- **Production authorization:** The plan does not add a dedicated read-only Neo4j user or a production permission model.

- **Production observability:** The plan does not add telemetry exporters, dashboards, alerting, or long-term trace storage.

- **Model grading:** The plan does not add a second model call to judge final answer wording.

- **Automatic cleanup:** The plan does not delete stale AWS resources from participant notebooks.

- **Module 6 agent:** The plan does not add a memory-aware Strands agent to Module 6.

- **Compatibility aliases:** The plan does not preserve old model-visible tool names. No students and no deployed resources depend on them.
