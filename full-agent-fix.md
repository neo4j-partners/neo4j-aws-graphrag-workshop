# Proposal: Let the Module 3 Agent Choose Its Own Tool

## 1. The problem, the goal, and the real lesson

### The problem

Module 3 gives the agent one tool and then removes every decision the agent could make about it.

* **The prompt gives an order:** The system prompt says "Call `search_hotel_knowledge_tool` before answering any hotel question." That sentence tells the model what to do. The model never reads the tools and picks one.
* **A model subclass forces the call:** `grounded_bedrock_model.py` overrides `stream()` and sets `tool_choice={"any": {}}` on every fresh user turn. `any` means "call some tool." One tool is registered, so `any` means "call this tool."
* **The forcing ignores the question:** The gate checks one thing. It asks whether the last message came from the user and carries no tool result. A message like "thanks, that is all" gets a forced retrieval call too.
* **The second read path stays hidden:** `hybrid_retrieval.py` also defines `graph_query`. That function sends model-generated read-only Cypher to Neo4j. Module 3 never registers it. Module 4 deploys it to the Gateway, and the participant meets it there with no introduction.
* **The tool description says nothing about routing:** The docstring is one line. It reads "Search grounded hotel context and return bounded JSON facts." Strands turns that line into the whole tool specification. The line describes the return value and never says when to use the tool.
* **The abstention test reads the model's wording:** Cell 11 matches 7 forbidden phrases and 9 required phrases against the answer text. Section 3 shows why that test cannot fail for the right reason.
* **Module 5 already dropped the forcing:** `runtime_app/booking_agent.py` builds the same kind of agent on a plain `BedrockModel` with free tool choice. Module 3 teaches forced retrieval, Module 5 abandons it, and no page explains the change.

### The goal

* **Give the decision to the model:** The model reads the question and the two tool descriptions, then picks. No code rewrites the request.
* **Register both read paths in Module 3:** The agent gets the semantic tool and the structured tool. Choosing becomes a real decision with a right answer and a wrong answer.
* **Measure grounding instead of dictating it:** The notebook checks which tool ran and what that tool returned. It stops checking the shape of the model's sentences.
* **Use one name and one description per tool everywhere:** Modules 2 through 5, both Lambdas, the Gateway schema, the site pages, and the slides all say the same thing.

### What the lab is really trying to teach

Module 3 sits between a retrieval module and a deployment module. Its subject is agent design.

* **A graph gives an agent two different read paths:** Semantic search returns the best few passages of text. Generated Cypher computes over every matching record. Those two answers fit different questions.
* **The tool description is the routing logic:** The developer writes prose. The model routes on that prose. A weak description is a bug that produces a confident wrong answer and no error.
* **Grounding is a property you verify:** The deployed agent in Module 5 runs with free tool choice. Trust comes from watching the tool calls and reading the tool results. Forcing the call proves nothing about the deployed agent.
* **Top-k search cannot compute an average:** Module 2 already asks "What is the average guest rating of hotels in Paris?" Semantic search returns 5 passages. Averaging 5 of 40 Paris hotels gives a confident wrong number. Generated Cypher sends `avg()` to the database and covers every match. This one comparison is the workshop's strongest argument for a graph behind an agent, and Module 3 cannot make it today.

---

## 2. Tool names and descriptions

No students are using the workshop right now, so this proposal renames both tools and every deployed resource. Nothing is kept for backward compatibility.

### The names

| Current | New | Why |
|---|---|---|
| `search_hotel_knowledge` | `search_hotel_documents` | "Knowledge" is vague. It reads as everything the system knows, which includes the stored fields the other tool computes over. That overlap is a routing hazard. "Documents" tells the model this path returns passages of written text. |
| `search_hotel_knowledge_tool` | `search_hotel_documents` | The `_tool` suffix carries no meaning. Every entry in `tools=[...]` is a tool. The suffix also makes Module 3 advertise a different name than the Gateway and Module 5. |
| `graph_query` | `query_hotel_records` | `graph_query` names the mechanism. Both tools query the graph, so the name gives the model nothing to route on. "Query" also reads as a general-purpose escape hatch, which invites the model to try it first. "Records" points at stored fields. |

* **Why the pair works:** The two nouns carry the routing signal on their own. Documents hold prose. Records hold fields. A model that reads only the names already leans the right way, and the descriptions then make the boundary exact.
* **Why not `query_hotel_aggregates`:** That name covers counts and averages and excludes the rest. The tool also answers multi-condition filters and relationship traversals. A narrow name would push those questions to the text tool, which is the exact failure this proposal removes.
* **The one weakness of `search_hotel_documents`:** The tool returns document text plus reviewed graph facts such as `hotel_id` and `guest_rating`. The name undersells the graph facts. The docstring covers that in one sentence, and the trade is worth it because the name's job is routing.
* **Keep the Python name separate from the model-visible name:** Use `@tool(name="search_hotel_documents")` over a local function. Module 5 already does this with `@tool(name=RETRIEVAL_TOOL)`.

### The descriptions

Each description states four things. It says what the tool does. It says when to use it. It says when to use the other tool. It says what an empty result means.

```python
@tool(name="search_hotel_documents")
def search_hotel_documents_tool(query: str) -> str:
    """Read what hotel documents say about a specific hotel or need.

    Use this when the answer is text about one hotel or a few hotels.
    Examples are amenities, room types, cancellation policies, services, and
    location descriptions. This returns the 5 best-matching passages. Each
    passage carries the reviewed graph facts for its hotel, including the
    stable hotel_id.

    Do not use this for a number computed across many hotels. Counting or
    averaging these results gives a wrong answer, because this returns 5
    matches and not the full set. Send those questions to
    query_hotel_records.

    The graph stores published hotel knowledge. The graph stores no live room
    inventory. Nothing this returns proves a room is available.

    Args:
        query: The guest's question in their own words.

    Returns:
        JSON list of passages. Each passage has chunk_text, combined_score,
        exact_terms, hotel_id, hotel_name, address, guest_rating, and
        amenities. An empty list means no hotel document matched.
    """
```

```python
@tool(name="query_hotel_records")
def query_hotel_records_tool(query: str) -> str:
    """Compute an answer from the stored fields of every matching hotel.

    Use this when the answer comes from the whole set rather than from a few
    passages. Examples are how many hotels offer a spa, the average guest
    rating in Paris, the highest-rated hotel with a pool, and hotels that
    have both a gym and parking. The database runs the calculation, so the
    answer covers every matching hotel.

    Do not use this to read what a document says about one hotel. Send those
    questions to search_hotel_documents. This returns stored fields only and
    returns no source passages.

    This tool reads and never writes. It returns the generated Cypher next to
    its rows, so you can see what the database was asked.

    Args:
        query: The question to compute, in the guest's own words.

    Returns:
        JSON with "cypher", "records", and "error". Empty records means the
        graph holds no matching data. A non-empty error means the question
        cannot be expressed against the graph schema. In both cases the graph
        does not answer the question. Say so and do not retry the same
        question.
    """
```

* **Each description names the other tool:** Two-tool routing gets accurate when the boundary is stated twice, once from each side. Nothing in the repository does this today.
* **Each description states its negative case:** The model learns which questions to send away. Positive-only descriptions leave that to chance.
* **The structured tool explains an empty result:** `graph_query` returns `{cypher, records}` today with no failure field. Empty records means either "no matching data" or "the generated Cypher was wrong." The model cannot tell those apart, so the description and the return value both have to.
* **Developer commentary moves to the module docstring:** `graph_query`'s current docstring opens with "This is the one place in the workshop where the database executes a statement no human wrote." That reads well for a developer. It wastes tokens in a tool specification. The model is the first audience of a `@tool` docstring.

### Where the canonical text lives

`tools.json` is the wrong single source, and reading the text at runtime is worse. Both options lose the lesson.

* **Strands reads the docstring, so the docstring has to stay literal:** Setting `func.__doc__ = tool_description("search_hotel_documents")` would leave the participant looking at a `@tool` function with no visible description. Module 3 teaches that the docstring is the only thing the model sees. Hiding the docstring destroys that lesson.
* **`tools.json` sits in the wrong module:** It lives under `notebooks/04-production-agent/`. Participants reach Module 3 first. Importing a Module 4 deployment artifact into Module 3 inverts the module order and confuses the reading path.
* **The fix is deliberate duplication with an enforced match:** Write the text once in `notebooks/workshop/tool_specs.py` as the reviewed source. Copy it literally into the Module 3 docstrings, the Module 5 docstrings, and `tools.json`. Add a test that compares every copy to `tool_specs.py` byte for byte and names the file to edit when they differ.
* **Why this beats a generator:** A generator adds a build step, a generated file to review, and a way for a stale checked-in copy to pass review. A test gives the same guarantee, fails on the exact line that drifted, and adds no build step.
* **The Lambdas need no description:** `lambda_tools/*/lambda_function.py` unwraps `event["query"]` and calls the shared function. The Gateway supplies descriptions from `tools.json`.

### Alignment across modules

* **The test to add is `tests/test_tool_contract.py`:** It asserts that every model-visible tool name appears in `tools.json`, that every docstring copy equals the `tool_specs.py` text, and that the strings `graph_query` and `search_hotel_knowledge` appear nowhere in the repository.
* **The last check is what makes a full rename safe:** A repo-wide absence check catches a missed slide, a missed site page, and a missed Lambda folder in one run.

---

## 3. Fixing the Module 3 agent

### Let the agent choose

**Delete `notebooks/03-grounded-booking-agent/grounded_bedrock_model.py`.** Its own docstring calls it "a workaround for a Strands library quirk, not the `Agent` / `BedrockModel` / `@tool` usage the module's README teaches." The file exists to force the decision the module is supposed to teach.

Module 3 then builds the agent the way Module 4 already builds one.

```python
grounded_agent = Agent(
    model=BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION),
    tools=[search_hotel_documents_tool, query_hotel_records_tool],
    system_prompt=SYSTEM_PROMPT,
    hooks=[ToolTraceHook(), ToolResultRecorder()],
)
```

Three supports replace the forcing.

* **`ToolTraceHook` shows every call:** The hook already exists in `notebooks/workshop/workshop_utils.py`, and Module 4 already uses it. It prints each tool name, its input, and its result while the agent runs. The participant watches the routing decision happen.
* **A check proves retrieval ran:** The notebook reads the tool metrics off the result and reports through the shared helper.

  ```python
  response = grounded_agent(HERO_QUESTION)
  report_problems(
      tool_choice_problems(response, expected="search_hotel_documents"),
      "The agent chose the document tool for a document question.",
  )
  ```

  This checks the behavior that will hold in Module 5's container, where nothing rewrites the request.
* **A routing table tests the descriptions:** Add one cell that runs 5 questions and reports the tool each one chose.

| Question | Expected tool |
|---|---|
| What amenities does AnyCompany Cairo Nile View have? | `search_hotel_documents` |
| What is the average guest rating of hotels in Paris? | `query_hotel_records` |
| How many hotels offer a spa? | `query_hotel_records` |
| What is the cancellation policy at AnyCompany Cairo Nile View? | `search_hotel_documents` |
| Does AnyCompany Cairo Nile View guarantee availability next weekend? | either tool, then abstain |

This cell is the evidence that the descriptions work. It also fails loudly when a description regresses.

**The risk and the answer to it.** Free tool choice lets the model answer from memory and skip both tools. `tool_choice_problems` catches that and reports it. A silent wrong answer is the outcome worth preventing, and this check prevents it. Module 5 already runs with free choice, so the workshop carries this risk today and hides it.

### Fix the system prompt

The new prompt states the routing boundary and the policy. It names no library mechanic and orders no specific call. `GROUNDING_INSTRUCTIONS` already carries the abstention rule and the availability rule, so the prompt appends it instead of restating it.

```python
SYSTEM_PROMPT = (
    "You are a hotel-information assistant for AnyCompany Hotels.\n\n"
    "Answer hotel questions only from what your tools return. You have two "
    "ways to read the hotel graph:\n"
    "- search_hotel_documents reads hotel documents. Use it for what a "
    "particular hotel offers.\n"
    "- query_hotel_records computes over every matching hotel. Use it for "
    "counts, averages, rankings, and multi-condition filters.\n\n"
    "Pick the one that fits the question. Use both when a question needs "
    "both.\n\n"
    + GROUNDING_INSTRUCTIONS
)
```

* **Why the prompt lists the tools:** Repeating the boundary in the prompt raises routing accuracy above the docstrings alone. The prompt states the rule once, and each docstring states its own side.
* **Why the prompt orders no call:** The model has to be able to answer "thanks, that is all" with no tool call. A blanket order breaks that turn.

### Make the structured tool fail cleanly

* **The retriever raises, it does not return:** `Text2CypherRetriever` runs `EXPLAIN` on the generated Cypher and raises `Text2CypherRetrievalError` when the planner reports anything other than read-only. It also raises when execution fails. `graph_query` catches nothing.
* **What an uncaught raise costs:** In Module 3 the raise becomes a Strands tool error, and the model sees a stack message it cannot act on. In the Module 4 Lambda the raise becomes a 500 and the Gateway returns a generic failure.
* **The fix:** Catch `Text2CypherRetrievalError` in the tool wrapper. Return `{"cypher": ..., "records": [], "error": "<short reason>"}`. Add `error` to the result type. The model then abstains with a reason instead of retrying blindly.
* **Add a demonstration cell:** Ask the tool something the schema cannot express, such as a question about room inventory. Show the returned error and show the agent abstaining. This teaches the failure path in the module that teaches abstention.

### Fix the abstention check

**The property is real. The test is not.** The workshop should check that the agent refuses to assert live availability. Cell 11 does not check that. It checks the model's vocabulary.

* **The positive check is invalid:** It requires one of 9 phrases such as "cannot determine" and "cannot confirm". A correct refusal like "The hotel graph holds no live room inventory, so I have no way to check next weekend" contains none of them and fails the cell. The test punishes correct behavior phrased differently.
* **The negative check is a weak proxy:** It forbids 7 specific phrasings such as "yes, rooms are available". A fabricated answer like "You can book that weekend" passes untouched. The check cannot catch the failure it exists to catch.
* **The test cannot fail for the right reason:** Both lists are inline in a notebook cell. Nothing can feed the check a fabricated answer and confirm it objects. `tests/test_module3_availability_assertion.py` executes the cell with a stub agent, so it proves the phrase list matched one canned string. It proves nothing about the check's power.
* **The bad design produced the bad test:** A forced single-tool agent gives the notebook no structured signal to assert on. String matching on prose was the only option left. This is a forced test, not a real one.
* **Free tool choice makes it worse:** Routing can send the availability question to either tool, and the refusal wording shifts with it. The 9-phrase list gets more fragile, not less.
* **Module 3 also breaks its sibling module's rule:** `tests/test_module2_notebook_contract.py` forbids bare asserts in Module 2 teaching cells, because "a bare `assert` in a teaching cell is a test the learner has to read past." Module 2 routes acceptance through shared `*_problems` helpers reported by `report_problems`. Module 3 carries 12 bare asserts across 3 cells.

**The right fix separates three things the current cell blends into one.**

* **Layer 1 checks the data, with no model involved:** Assert against `GRAPH_SCHEMA` that no `Hotel` property holds room inventory. This is the reason abstention is correct, and it never flakes. Put it in `schema_gap_problems()`.
* **Layer 2 checks what the tool returned, with no model judgment:** The grounding verdict reports `answerable`, `missing_fact`, `supported_facts`, and `available_fields`. Code computes it from the question and the returned records. This has a real failure mode. It fails when retrieval starts claiming to answer inventory, and it fails when the verdict logic breaks.
* **Layer 3 checks what the model said, and stays honest about being a heuristic:** Keep one negative check for fabricated availability claims. Drop the 9-phrase positive list entirely. Label the negative list a heuristic in a comment, because prose matching cannot prove absence of a claim.
* **Move all three into `workshop/grounding.py` as `grounding_problems()`:** The notebook then calls `report_problems(grounding_problems(question, verdict, answer_text), "...")`, matching Module 2's convention exactly.
* **This is what makes the check testable:** `tests/` can call `grounding_problems` directly. Feed it a fabricated answer and assert it reports a problem. Feed it a correct refusal worded three different ways and assert it reports none. The check gains a real failure mode, which the inline version never had.
* **Rewrite `tests/test_module3_availability_assertion.py` around the function:** Assert that the notebook calls `report_problems(grounding_problems(...))`, then unit-test `grounding_problems` in both directions. The current test extracts a cell and matches strings, which is the weakest available form of this test.
* **The production answer for layer 3 is a model-graded check:** A separate model call asking "does this answer assert that rooms are available?" catches paraphrases that string matching misses. Keep it out of the notebook, because it adds a Bedrock call and a nondeterministic result to a teaching cell. State it in one line of prose as the production pattern.
* **Leave the reservation asserts alone:** Cells 13 and 15 assert on deterministic Python return values, not on model prose. They are correct tests. Converting them to the `*_problems` convention is a consistency improvement outside this fix.

### Move the shared grounding code out of Module 5

* **Move the verdict:** `_grounding_result` lives inside `runtime_app/booking_agent.py` today. Move it to `notebooks/workshop/grounding.py` so Module 3, Module 5, and both Lambdas share one copy. Module 3 teaches abstention, so the verdict belongs where the lesson is.
* **Move the recorder hook:** `ToolResultRecorder` and `_tool_payload` move with it, because Module 3 now needs them to read the verdict.
* **Extend the verdict to the structured path:** Report `answerable: false` when `records` is empty or `error` is set, and include the generated Cypher in the verdict.
* **Name the keyword list in `contracts.py`:** `_grounding_result` matches "availability", "available", "vacancy", "vacancies", and "inventory" against the question. Call it `UNSUPPORTED_QUESTION_TERMS` in `contracts.py` with a comment saying what it is. A teaching guardrail hidden in a private function inside a deployment file is the part to fix.
* **Add the schema fields the graph can supply:** Render `available_fields` from `GRAPH_SCHEMA` into the verdict. The model then sees that no inventory property exists, instead of relying on a keyword match. The keyword list keeps the layer 2 check deterministic, and the schema list generalizes past the 5 words.

---

## 4. What needs fixing in Modules 2, 4, 5, and 6

### Module 2

Module 2 is the reason Module 3 has one tool. It presents Text2Cypher as an optional extra.

* **The retriever table calls the path optional:** The "Use in this workshop" cell reads "Optional query with a safety check." Change it to say that Module 3 registers this path as the agent's second tool.
* **The handoff line names one retriever:** The notebook sets `selected_module_3_retriever = search_hotel_knowledge`. Make it two named selections, one per question shape. `tests/test_module2_notebook_contract.py:212` asserts the current string and changes with it.
* **Add the failure comparison:** Module 2 already runs `run_optional_text2cypher(CHICAGO_QUESTION)`. Add the Paris average-rating question and run both paths on it. Semantic search returns 5 passages. Generated Cypher returns the real average. Module 3 then repeats this comparison with an agent doing the routing.
* **Rename the diagram node:** `site/images/DIAGRAM_PROMPTS.md` names node 8 `optional-text2cypher`, and `tests/test_module2_diagrams.py:58` asserts that identifier. Change both.
* **Update the site page:** `site/content/02-connected-context/index.en.md` says the Text2Cypher path "remains optional" and says Module 3 exposes one tool.

### Module 4

Module 4 already has the target design. It uses a plain `BedrockModel`, passes both Gateway tools, leaves tool choice free, and traces calls with `ToolTraceHook`. Module 3 moves to match Module 4.

* **Apply the full rename:** The sites are `tool_schemas/tools.json`, both `TOOLS` keys, both `TARGETS` entries, both `lambda_tools/` folders, the deployed Lambda function names, the Gateway target names, and the `call("graph_query", ...)` verification.
* **Delete stale deployed resources:** The notebook creates a Gateway target by name and reuses an existing one. Any account that already ran Module 4 keeps the old targets next to the new ones, and the Gateway then advertises 4 tools. Add a step that deletes any target whose name is absent from `tools.json`, and do the same for the old Lambda functions. No students are affected, so this step exists for the development and rehearsal accounts.
* **Strengthen the prompt:** The current prompt says "Use the available retrieval tools for every hotel question." It gives no routing guidance. Replace it with the Module 3 prompt so both modules teach one rule.
* **Add an aggregate question to the demo:** Cell 24 asks for an address and a guest rating, which routes to search every time. Add the Paris average-rating question so the participant watches the Gateway route to the second tool.
* **Confirm the Lambda role:** The structured tool's Lambda already calls Bedrock to generate Cypher, so `bedrock:InvokeModel` is already granted. Confirm this during the pass rather than assuming it.

### Module 5

* **Register the structured tool in the container:** `runtime_app/booking_agent.py` imports the semantic path only. The deployed agent therefore answers aggregate questions with top-k passages, which is the exact failure Module 3 now teaches participants to spot. Add `query_hotel_records` next to `create_reservation`.
* **Import the shared grounding code:** After the move, this file imports the verdict and the recorder instead of defining them.
* **Update `RETRIEVAL_TOOL`:** The constant holds the old name and feeds `@tool(name=...)`.
* **State the tool-choice story:** Add a sentence saying the deployed agent uses free tool choice, the same as Module 3. This closes the gap where Module 3 forces tool use and Module 5 silently stops.
* **Fix the stale model comment:** The file says "The shared workshop model is claude-sonnet-5." `tests/test_bedrock_model_contract.py` pins the validated model to `us.anthropic.claude-sonnet-4-6` and marks Sonnet 5 as retired.

### Module 6

* **Module 6 registers no tools:** The notebook calls the `neo4j-agent-memory` library and raw Cypher across 18 cells. It builds no Strands agent. The rename and the tool-choice fix do not reach it.
* **One optional item would close the workshop's arc:** Module 6 stores a guest preference and never hands it to an agent. One added cell could build the Module 3 agent, inject the recalled preference, and ask a hotel question. The participant would see memory change which tool the agent picks. Treat this as a separate proposal, outside this fix.

### The dependency floor is a real safety gap

* **The read-only guard is new:** `Text2CypherRetriever` plans the generated Cypher with `EXPLAIN` and refuses anything the planner does not report as read-only. That guard first shipped in neo4j-graphrag 1.16.0.
* **The declared floor predates the guard:** `notebooks/workshop/pyproject.toml:11` declares `neo4j-graphrag>=1.6.0`. Versions 1.6.0 through 1.15.x run model-generated Cypher with no read-only check.
* **The lock file hides the risk:** `notebooks/workshop/uv.lock` resolves to 1.18.0, so a `uv sync` participant is safe today. Anyone who installs from the specifier, or refreshes the resolver, can land on an unguarded version.
* **This fix raises the stakes:** Today the structured path runs only from an optional Module 2 cell. After this fix an agent calls it freely in Module 3, in the Gateway, and inside the deployed container.
* **Raise the floor to `>=1.18.0`:** That matches the lock and removes the gap. `>=1.16.0` is the minimum that carries the guard.

### Cross-cutting surfaces

* **Site content:** Update `site/content/02-connected-context/`, `03-grounded-booking-agent/`, `04-production-agent/`, `05-agentcore-deploy/`, `foundations/`, `summary/`, `production-path/`, and `index.en.md`.
* **The Module 3 page needs the largest rewrite:** It says "`search_hotel_knowledge` tool: The agent's only tool." It also says "A small `BedrockModel` subclass forces one tool call for every new hotel question, so the model cannot skip retrieval." Both statements become false. Its four-step list starts "The model calls `search_hotel_knowledge_tool` with the user's question," which becomes false too. The page's own "Strands Agent Basics" section already says the model "decides which tool to call," which the code contradicts today.
* **Slides:** Update `slides/overview-agent/`, `overview-mcp-gateway/`, `overview-graphrag/`, `overview-architecture/`, and `overview-agentcore-runtime/`.
* **Diagrams:** `site/images/03-grounded-agent-overview.svg` draws one tool, and its caption says the agent "reads hotel facts from Neo4j through one tool." `DIAGRAM_PROMPTS.md` holds the prompt behind it. Both need a two-tool version.
* **Tests:** Update `test_module3_availability_assertion.py`, `test_module2_notebook_contract.py`, `test_module2_diagrams.py`, `test_phase5_content_contract.py`, and `test_bedrock_model_contract.py`. Add `test_tool_contract.py`. `test_phase5_content_contract.py` and `test_module2_notebook_contract.py` both assert the literal string `search_hotel_knowledge`, so the rename reaches them.
* **Environment check:** `environment/verify.py` should confirm both read paths work before the workshop starts. The structured path makes an extra Bedrock call that the semantic path does not, so it can fail on its own.

---

## 5. Phased implementation plan

Every phase ends with a green test run. Phase 1 gates all other work, because every later phase writes against the contract it defines.

### Phase 1: define the contract

**One agent, no parallel work.**

* **Write the canonical text:** Put both names and both descriptions in `notebooks/workshop/tool_specs.py`.
* **Update the Gateway schema:** Copy the text into `tool_schemas/tools.json` and rename both entries.
* **Create the shared grounding module:** Put the verdict, the recorder hook, the payload parser, `grounding_problems`, `schema_gap_problems`, and `tool_choice_problems` in `notebooks/workshop/grounding.py`.
* **Add the keyword constant:** Put `UNSUPPORTED_QUESTION_TERMS` in `contracts.py`.
* **Raise the dependency floor:** Set `neo4j-graphrag>=1.18.0` in `notebooks/workshop/pyproject.toml` and refresh the lock.
* **Add the contract test:** Write `tests/test_tool_contract.py`, including the repo-wide absence check for `graph_query` and `search_hotel_knowledge`.
* **Unit-test the new checks:** Test `grounding_problems` in both directions before any notebook depends on it.

### Phase 2: rename and rewire the code

**Agent A runs alone first. Agents B and C then run together.**

| Agent | Owns | Work |
|---|---|---|
| A: retrieval package | `notebooks/workshop/hybrid_retrieval.py` | Rename both functions and every helper, constant, and result type. Add the `error` field and catch `Text2CypherRetrievalError`. Move the developer commentary to the module docstring. |
| B: Module 3 | `notebooks/03-grounded-booking-agent/` | Delete `grounded_bedrock_model.py`. Register both tools with the canonical descriptions. Replace the system prompt. Add both hooks. Add the routing table, the layered grounding check through `report_problems`, and the schema-failure cell. |
| C: Modules 4 and 5 | `notebooks/04-production-agent/`, `notebooks/05-agentcore-deploy/` | Rename both Lambda folders, both `TOOLS` keys, both `TARGETS` entries, and the verification call. Add stale-resource cleanup. Replace the Module 4 prompt. Add the aggregate demo question. Register the structured tool in `booking_agent.py`. Import the shared grounding code. Fix the stale model comment. |

* **Why A runs alone:** B and C import from `hybrid_retrieval.py`. Land A's rename in one commit, then let B and C rebase onto it.

### Phase 3: Module 2 framing and the tests

**Two agents in parallel.**

| Agent | Owns | Work |
|---|---|---|
| D: Module 2 | `notebooks/02-connected-context/`, the Module 2 diagram identifier | Change the retriever table. Make the handoff name two selections. Add the Paris comparison. Rename the diagram node. |
| E: tests | `tests/` | Update the 5 existing test files. Rewrite `test_module3_availability_assertion.py` around `grounding_problems`. Confirm the new cell shapes execute under the stubs. |

* **Timing:** D can start as soon as Phase 1 lands. E needs Phase 2 to land first.

### Phase 4: prose, slides, and diagrams

**Three agents in parallel.**

| Agent | Owns | Work |
|---|---|---|
| F: site content | `site/content/` | Rewrite the 8 pages. The Module 3 page carries the largest change. |
| G: slides | `slides/` | Update the 5 decks. |
| H: diagrams | `site/images/` | Produce the two-tool `03-grounded-agent-overview.svg` and update `DIAGRAM_PROMPTS.md`. |

* **Why these three run together:** They touch separate trees. Route any shared prose file through the existing Track F prose agent, which already owns those files.

### Phase 5: live verification

**One agent, holding the environment.**

* **Run every notebook end to end:** Use the shared Neo4j graph and the shared AWS account. The existing `env-holder` agent already holds both.
* **Run the routing table 5 times:** Free tool choice is a model decision, so confirm the routing is stable before shipping.
* **Deploy Module 4 twice:** The second run proves the cleanup works and that the Gateway advertises exactly 2 tools.
* **Deploy and invoke Module 5:** Confirm the container answers an aggregate question with the structured tool.
* **Save the evidence:** Write the executed notebooks to `workfolder/evidence/release-evidence/`, matching the existing convention.

### Parallel structure at a glance

* **Serial gates:** Phase 1 gates everything. Agent A gates B and C. Phase 2 gates agent E and Phase 5.
* **Parallel groups:** The groups are (B, C), (D, E), and (F, G, H).
* **One owner per file:** Assign each file to exactly one agent for the whole run. Two agents editing one notebook produces a JSON merge conflict that costs more than the edit.
* **Shortest path:** Run Phase 1, then A, then B and C, then D and E, then F and G and H, then Phase 5.

---

## 6. What this adds beyond the original outline

Your outline covered the names, the descriptions, the cross-module alignment, the Module 3 design, the system prompt, Modules 2 through 6, and the phased plan. Seven items sit inside those sections that the outline did not name.

* **The abstention check is a forced test, not a real one:** It requires 9 specific phrases and forbids 7 others, so it fails correct refusals worded differently and passes fabrications worded differently. Section 3 replaces it with three layers and moves it into a function that can be tested in both directions.
* **Module 3 breaks the rule Module 2 enforces:** Module 2's test forbids bare asserts in teaching cells. Module 3 has 12 of them across 3 cells.
* **`grounded_bedrock_model.py` has to go:** The prompt is the weaker half of the forcing. Fixing the prompt alone leaves `tool_choice={"any": {}}` injected on every fresh user turn.
* **The structured tool raises instead of returning:** `Text2CypherRetriever` raises when the planned Cypher is not read-only or when execution fails, and `graph_query` catches nothing. An agent tool needs a structured failure it can reason about.
* **The dependency floor predates the read-only guard:** The guard shipped in 1.16.0, and the workshop declares `>=1.6.0`. This matters much more once an agent calls the tool freely in 3 places.
* **Tests, slides, and diagrams pin the current design:** 5 test files, 5 slide decks, 1 SVG, and 1 prompt file assert or draw one tool and a forced call. Two test files assert the old tool name as a literal string.
* **Module 6 stays out of scope:** It builds no agent. The memory-plus-agent cell is a separate proposal.
