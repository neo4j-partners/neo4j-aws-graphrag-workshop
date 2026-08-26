# Workshop Slides

Presenter decks for the Neo4j and AWS GraphRAG workshop, written in
[Marp](https://marp.app/). Each deck carries its narration in speaker notes, so
the slide holds the fragments and the note holds what you say.

## Run of Show

| # | Deck | Covers | Pairs with |
|---|---|---|---|
| 1 | `overview-business-story` | Why retrieval alone is not grounding, and the hero question | Opening |
| 2 | `overview-architecture` | The dataset, the environment, and who owns which control | Setup |
| 3 | `overview-knowledge-graph` | The property graph model, Cypher, and Neo4j Aura | Foundations |
| 4 | `overview-documents-to-graph` | Extraction, schema drift, and the indexes that power search | Module 1 |
| 5 | `overview-graphrag` | Vector, full-text, hybrid, and graph-enriched retrieval | Module 2 |
| 6 | `overview-agent` | Strands, one fixed tool, abstention, and the write path | Module 3 |
| 7 | `overview-mcp-gateway` | Moving the retrieval tools out of the notebook process | Module 4 |
| 8 | `overview-agentcore-runtime` | The container contract, sessions, and observability | Module 5 |
| 9 | `overview-agent-memory` | Preference memory with provenance and actor-scoped recall | Module 6 |

Deck 5 is the longest and deck 1 is the only one that needs a live demo. If you
fall behind, demonstrate Modules 4 and 5 rather than having the room run them.

## Quick Start

Preview one deck with live reload:

```bash
npx @marp-team/marp-cli@latest slides/overview-graphrag --server
```

Press <kbd>P</kbd> in the browser to open the presenter view with speaker notes.

The workshop diagrams show as broken icons in that preview. Every deck
references them as `../images/NAME.svg`, and they live in `site/images/`, which
the build script resolves and the preview server does not. Build the deck and
open the generated HTML to check a diagram.

Build every deck the way the site does:

```bash
cd site && npm install && npm run build:slides
```

That writes the rendered HTML into `site/modules/ROOT/attachments/slides/` and
an Antora wrapper page per deck into `site/modules/ROOT/pages/slides/`. The full
`npm run build` runs content preparation, then the slides, then Antora.

> The GitHub Pages workflow pins Node 22 LTS. Newer releases work locally.

## Images

Reference every image as `../images/NAME.svg` and nothing else.
`site/scripts/build-slides.mjs` resolves each reference from `slides/images/`
first and `site/images/` second, then copies it into one flat attachments
directory at that depth. A reference it cannot resolve fails the build, which is
better than a broken image in front of a room. Marp writes relative paths into
the generated HTML verbatim and never copies the file itself, which is the
failure this rule exists to prevent.

## Adding or Changing a Deck

1. Copy the frontmatter and `<style>` block from any existing deck. They are
   byte-identical across all nine and disable Marp's fragment animations.
2. Add the deck to the `DECKS` array in `site/scripts/build-slides.mjs`. The
   array is in run-of-show order and drives the deck index page.
3. Add it to `site/nav.adoc` under the Slides entry.
4. Add a `Slides for this module` link to the paired page in `site/content/`.

## House Style

- Slides carry presenter-supporting fragments. Speaker notes carry the narration
- `**bold term:** definition` bullets, comparison tables over prose, ASCII
  diagrams where a picture would be one box and an arrow
- Descriptive noun-phrase titles. No emojis, no exclamation points, no em dashes
- No agenda, questions, or thank-you slides, and no summary that only restates
- Every deck opens with a one-line recall of the previous one and closes
  pointing at the next
- The hero question appears verbatim in decks 1, 5, 6, 7, and 8. Do not
  paraphrase it. The repetition is what makes the arc legible

Local Marp preview output (`slides/**/*.html`) is git-ignored. The published
HTML is generated into `site/modules/`, which is ignored with it.
