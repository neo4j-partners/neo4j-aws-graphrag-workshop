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

# The Business Case for Grounded Agents

A guest asks for a Chicago hotel with a spa and a pool. The confident answer and the correct answer are not the same thing.

<!--
This deck sets up the whole workshop. The argument runs in a fixed order:
what is at stake, why the model alone fails, why retrieval alone fails, what
a graph adds, third-party evidence, and then the hero question the rest of
the day answers.

Do not explain retrievers here. Deck 5 owns that. This deck only has to make
the room want the graph.
-->

---

## The Enterprise AI Paradox

Modern models already out-reason most people on general knowledge, recall, and synthesis. So why is the booking assistant still wrong?

- **High intelligence** plus **missing operational context** equals confident, useless answers
- The gap is not model capability. It is what the model was never told

<!--
Open here rather than with the technology. Everyone in the room has watched a
capable model produce a fluent answer about their own business that was simply
untrue. Name that experience, then spend the deck explaining why it happens.

The second bullet is the thesis. Nothing in this workshop makes the model
smarter. Everything in it changes what the model is allowed to see.
-->

---

## The Stakes

A hotel group is putting agents in front of guests. Three failures cost real money, and they are different failures:

- **A wrong answer:** the agent promises a spa the hotel does not have. The chain pays for a refund and absorbs a bad review
- **A wrong action:** the agent holds a room for fifteen guests in a suite that sleeps ten. Someone on the property has to unwind the reservation by hand
- **An unexplainable answer:** nobody can say which document the claim came from

Retrieval addresses the first. A controlled write path addresses the second. Provenance addresses the third.

<!--
This is where the hotel domain earns its place. The stakes are lower drama
than aviation and higher frequency, which is the honest framing. Every
attendee has a system that answers questions and a system that writes rows,
and most of them have wired an agent to both.

Land the split now, because it is the spine of Module 3. Grounding a read and
constraining a write are two different engineering problems, and most GraphRAG
talks only cover the first.
-->

---

## Why LLMs Alone Fall Short

- **Hallucination:** the model generates the statistically probable answer, not the verified one. It describes an amenity that does not exist as confidently as one that does
- **No access to your data:** the model has never seen this chain's hotels, rates, or policies. Retraining on a newer snapshot of the public web does not change that
- **Relationship blindness:** it cannot connect a policy to the property it governs, or find every hotel that shares one amenity

Retrieval closes the first two gaps. Only a graph closes the third.

<!--
The closing line is the pivot the next two slides depend on. Say it slowly.

If someone pushes on hallucination as a solved problem, agree partly: a good
retrieval layer does reduce it a lot. Then point at the third bullet, which
no amount of chunk retrieval fixes, and which is the reason the day exists.
-->

---

## The Problem Vectors Do Not Solve

Vector search finds text that is **similar**. It cannot **traverse relationships** or **guarantee a condition**.

Three questions this workshop asks of its own hotel documents:

- **"The hotel at postal code 60611"** loses the answer. An embedding of `60611` sits near every other five-digit number, so similarity ranks the right chunk below prose that reads more like the question
- **"Chicago hotels with both a spa and a pool"** returns hotels with one of them. Nothing ties two conditions to the same property
- **"What does this chunk's hotel actually offer"** cannot be answered from the passage. The name, the rating, and the amenity list live in the graph, not in the text

Similar text is not the same as a connected fact.

<!--
These three are not hypotheticals. Module 2 runs all three. The room watches
vector search miss the 60611 chunk before hybrid retrieval finds it, and then
sees the spa-and-pool question answered by reviewed Cypher rather than by
similarity at all.

Postal code 60611 is the demo that changes minds fastest, because the fix is
not a graph at all, it is a full-text index. Being honest about that buys you
credibility for the spa-and-pool case, where a graph genuinely is the answer.
-->

---

<style scoped>
/* 5% under the default theme's 29px. A percentage here would resolve against
   the root, not the theme's section size, and shrink far more than 5%. */
section { font-size: 27.55px; }
</style>

## The Shift to GraphRAG

A knowledge graph stores each hotel as a record and stores the links between records. This amenity belongs to that hotel. That policy governs this room. This fact came from that document.

- **Connected, verifiable facts:** the graph stores facts you can check, not pattern-matched chunks
- **Traversal on top of similarity:** a traversal reaches context that a vector search cannot
- **Traceable:** every answer walks back to the document behind it
- **Fewer tokens:** the agent receives the facts the answer needs, not everything that looked similar
- **Governed retrieval:** the application fixes the traversal, and the model does not choose it

The agent answers from evidence the graph can defend.

<!--
The last bullet is the one that separates this workshop from a generic
GraphRAG talk, and it comes back on slide 8. In most demos the model decides
what to fetch. Here the application decides, once, and the model never gets
that choice.
-->

---

<style scoped>
/* Five bullets, a lead-in, a closing line, and a source line at the theme's 29px. */
section { font-size: 24px; }
</style>

## The Evidence

The UK's National Innovation Centre for Data ran 510 complex questions. Some needed hundreds of steps. Neo4j sponsored the study. NICD ran it.

- **80% more truthful:** 63 against 35 on the study's truthfulness score, which penalizes hallucination
- **Over 2x precision and recall:** precision 0.38 against 0.18, recall 0.35 against 0.15
- **Half the refusals:** vector-only declined 71% of the questions, and GraphRAG declined 35%
- **Fewer tokens per correct answer:** the retriever fetches sections, not whole documents
- **No ontology project:** the graph was built from the titles, sections, and links the documents already carried

An agent that declines two questions in three is as unusable as one that guesses.

<small>Source: [Independent study: GraphRAG makes AI agents 80% more truthful](https://neo4j.com/blog/agentic-ai/study-graphrag-ai-agents-80-percent-more-truthful/), Neo4j</small>

<!--
Full NICD report: neo4j.com/whitepapers/nicd-reducing-hallucinations-graphrag/

Two points to land in the room:

The refusal number is the one that changes minds. Vector-only RAG mostly fails
by declining, not by lying, so teams who have only measured hallucination rate
think their system is fine. Ask how useful an assistant is that shrugs at two
out of three real questions.

The last bullet answers the objection that always comes: a graph means a
six-month data modeling project. NICD hand-engineered nothing, and Module 1
does the same thing to the hotel documents with a pinned schema.
-->

---

## Grounding Is More Than Retrieval

Retrieval decides what the model sees. Grounding decides what it is allowed to do with it.

- **One fixed tool:** the application picks the retriever once, for every question
- **Answer from context only:** the model may not fill a gap from its training data
- **Abstain when the graph is silent:** "I don't have that" is a correct answer
- **Never write:** the model only proposes an action. Application code validates it, and the database enforces the rule inside the write transaction

<!--
This slide has no equivalent in most GraphRAG decks, and it is the one that
distinguishes this workshop. Everything after it is an implementation of these
four rules.

Point out that three of the four are constraints on the model, not features
added to it. Grounding is mostly subtraction.

Module 3 demonstrates all four in one notebook: the forced tool call, a
grounded answer, a refusal, and a rejected fifteen-guest reservation.
-->

---

## The Hero Question

> Which Chicago hotel has both a spa and a swimming pool, what is its cancellation policy, and can I hold it for four guests?

One sentence, three different mechanisms:

- **The spa and the pool:** a Cypher template tests both conditions on the same hotel. Similarity cannot guarantee it
- **The cancellation policy:** hybrid retrieval finds the passage, a graph traversal attaches the hotel and its source document
- **The hold for four guests:** a reservation command validates the guest count, and Neo4j enforces the limit in the write transaction

Add a fourth question, "is a room free tonight," and the correct answer is that the graph does not know.

<!--
This question runs through decks 5, 6, 7, and 8 word for word. Do not
paraphrase it later. The repetition is what makes the arc legible.

The fourth line matters as much as the first three. Every attendee has been
asked to build an agent that answers everything, and the useful discipline is
knowing which questions the data cannot support. Module 3 makes the agent
refuse this one on purpose.
-->

---

## What We Are Building Today

By the end of the workshop you will have built and deployed exactly this:

- A **knowledge graph** in your own Neo4j Aura instance, with five hotels you extract from source documents yourself
- A **Strands agent** on **Amazon Bedrock**, grounded in one fixed retrieval tool
- **Retrieval tools published through AgentCore Gateway** as IAM-authenticated MCP
- The **agent itself deployed to AgentCore Runtime** as an arm64 container
- **Preference memory** written back into the same graph, with provenance

Fully isolated: your own Aura instance and a workshop AWS account.

<!--
Five bullets, six modules. Module 2 is missing from this list on purpose,
because comparing retrievers produces understanding rather than an artifact.

Stress "your own." The most common workshop failure is a shared environment
where a participant's mistake is invisible to them. Here a broken graph load
shows up in the next module as an empty result, which is the point.
-->

---

## Neo4j and AWS

- **Joint focus:** both companies are working to ground enterprise AI agents in verified data and reduce hallucinations
- **Neo4j Aura** runs as a managed service on AWS. Aura Marketplace billing goes through your AWS account
- **AgentCore** gives the agent a managed home for its tools and its runtime

<!--
Instructor: replace these lines with the current, approved Neo4j and AWS
partnership talking points for your event. Keep forward-looking product claims
to what has been publicly announced.

A joint-customer proof table belongs here. It is left out rather than filled
with unapproved logos. Add one for your event if you have cleared the names
and the numbers.
-->

---

## Opening Demo

See the finished build answer the hero question live.

Then we look at what a knowledge graph actually is, and set up your Aura instance and your AWS environment.

<!--
Instructor run instructions:

Run the hero question against the pre-deployed Module 5 AgentCore Runtime
agent, deployed before the event against the instructor's own Aura instance:

"Which Chicago hotel has both a spa and a swimming pool, what is its
cancellation policy, and can I hold it for four guests?"

Show the tool calls, not just the answer, so the room sees the retrieval
happen. Then ask the availability question and let it refuse. The refusal
gets more comment than the answer, every time.

Keep the runtime live all day so attendees can invoke it during breaks. Point
back to this demo from each module: Module 1 builds the graph behind it,
Module 2 chooses its retriever, Module 3 grounds it, Modules 4 and 5 deploy
it, Module 6 gives it memory.
-->
