// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
//
// Renders the Marp decks in `slides/` to HTML and publishes them through Antora.
//
// Ordering matters. `prepare-content.mjs` removes `site/modules/ROOT` on every
// run, so this script has to run after it and before Antora. `site/package.json`
// chains the three in that order.
//
// Marp writes relative image paths into the generated HTML verbatim and never
// copies the file itself. Every deck therefore references images as
// `../images/NAME.svg` and nothing else, and this script copies each referenced
// file into a single `attachments/slides/images/` directory at that one depth.
// A reference that does not resolve is a build failure rather than a broken
// image in a room full of people.

import { execFileSync } from 'node:child_process'
import { access, cp, mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const siteDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repoRoot = path.resolve(siteDirectory, '..')
const slidesDirectory = path.join(repoRoot, 'slides')
const slideImageDirectory = path.join(slidesDirectory, 'images')
const siteImageDirectory = path.join(siteDirectory, 'images')
const moduleDirectory = path.join(siteDirectory, 'modules', 'ROOT')
const attachmentsDirectory = path.join(moduleDirectory, 'attachments', 'slides')
const pagesDirectory = path.join(moduleDirectory, 'pages', 'slides')

// Run-of-show order. `pairsWith` is the workshop page a presenter shows next,
// and `page` is the generated Antora page that carries the reverse link.
const DECKS = [
  {
    key: 'overview-business-story',
    source: '01-business-case-slides.md',
    title: 'The Business Case for Grounded Agents',
    covers: 'Why retrieval alone is not grounding, and the hero question',
    pairsWith: 'Opening',
    page: null,
  },
  {
    key: 'overview-architecture',
    source: '01-architecture-roadmap-slides.md',
    title: 'The Hotel Booking Assistant',
    covers: 'The dataset, the environment, and who owns which control',
    pairsWith: 'Setup',
    page: 'setup/index.adoc',
  },
  {
    key: 'overview-knowledge-graph',
    source: '01-knowledge-graph-foundations-slides.md',
    title: 'Knowledge Graphs and AuraDB',
    covers: 'The property graph model, Cypher, and Neo4j Aura',
    pairsWith: 'Foundations',
    page: 'foundations/index.adoc',
  },
  {
    key: 'overview-documents-to-graph',
    source: '01-documents-to-graph-slides.md',
    title: 'From Documents to a Knowledge Graph',
    covers: 'Extraction, schema drift, and the indexes that power search',
    pairsWith: 'Module 1',
    page: '01-build-graph/index.adoc',
  },
  {
    key: 'overview-graphrag',
    source: '01-graphrag-retrieval-slides.md',
    title: 'GraphRAG Retrieval',
    covers: 'Vector, full-text, hybrid, and graph-enriched retrieval',
    pairsWith: 'Module 2',
    page: '02-connected-context/index.adoc',
  },
  {
    key: 'overview-agent',
    source: '01-grounded-agent-slides.md',
    title: 'The Grounded Booking Agent',
    covers: 'Strands, one fixed tool, abstention, and the write path',
    pairsWith: 'Module 3',
    page: '03-grounded-booking-agent/index.adoc',
  },
  {
    key: 'overview-mcp-gateway',
    source: '01-mcp-gateway-slides.md',
    title: 'MCP and AgentCore Gateway',
    covers: 'Moving the retrieval tools out of the notebook process',
    pairsWith: 'Module 4',
    page: '04-production-agent/index.adoc',
  },
  {
    key: 'overview-agentcore-runtime',
    source: '01-agentcore-runtime-slides.md',
    title: 'Deploying to AgentCore Runtime',
    covers: 'The container contract, sessions, and observability',
    pairsWith: 'Module 5',
    page: '05-agentcore-deploy/index.adoc',
  },
  {
    key: 'overview-agent-memory',
    source: '01-agent-memory-slides.md',
    title: 'Agent Memory with Neo4j',
    covers: 'Preference memory with provenance and actor-scoped recall',
    pairsWith: 'Module 6',
    page: '06-neo4j-memory/index.adoc',
  },
]

const IMAGE_PATTERN = /!\[[^\]]*]\(([^)]+)\)/g

async function exists(target) {
  try {
    await access(target)
    return true
  } catch {
    return false
  }
}

// Decks reference `../images/NAME.svg`. Slide-only art lives in `slides/images/`
// and wins; everything else falls through to the workshop diagrams the site
// pages already use.
async function resolveImage(reference, deckKey) {
  const name = path.basename(reference)
  const subdirectory = path.dirname(reference).replace(/^\.\.\/images\/?/, '')
  const relative = subdirectory && subdirectory !== '.' ? path.join(subdirectory, name) : name
  for (const root of [slideImageDirectory, siteImageDirectory]) {
    const candidate = path.join(root, relative)
    if (await exists(candidate)) return { relative, absolute: candidate }
  }
  throw new Error(
    `${deckKey} references ${reference}, which is in neither slides/images/ nor site/images/`,
  )
}

async function buildDeck(deck) {
  const deckDirectory = path.join(slidesDirectory, deck.key)
  const output = path.join(attachmentsDirectory, deck.key, deck.source.replace(/\.md$/, '.html'))
  await mkdir(path.dirname(output), { recursive: true })
  execFileSync(
    'npx',
    ['marp', '--allow-local-files', path.join(deckDirectory, deck.source), '-o', output],
    { cwd: siteDirectory, stdio: 'inherit' },
  )
  return output
}

async function copyImagesFor(deck) {
  const markdown = await readFile(path.join(slidesDirectory, deck.key, deck.source), 'utf8')
  const references = [...markdown.matchAll(IMAGE_PATTERN)].map(match => match[1].trim())
  for (const reference of new Set(references)) {
    if (/^[a-z]+:/i.test(reference)) continue
    if (!reference.startsWith('../images/')) {
      throw new Error(
        `${deck.key} references ${reference}. Decks may only reference images as ../images/NAME.ext`,
      )
    }
    const { relative, absolute } = await resolveImage(reference, deck.key)
    const destination = path.join(attachmentsDirectory, 'images', relative)
    await mkdir(path.dirname(destination), { recursive: true })
    await cp(absolute, destination)
  }
  return references.length
}

function wrapperPage(deck) {
  const html = `${deck.source.replace(/\.md$/, '.html')}`
  const attachment = `{attachmentsdir}/slides/${deck.key}/${html}`
  const reverse = deck.page
    ? `\n\nxref:${deck.page}[Open the ${deck.pairsWith} page]`
    : ''
  return `= ${deck.title} (Slides)

++++
<iframe src="_attachments/slides/${deck.key}/${html}"
  style="width:100%;aspect-ratio:16/9;border:1px solid var(--panel-border-color,#e1e1e1);border-radius:4px;"
  title="${deck.title}"
  allowfullscreen>
</iframe>
++++

link:${attachment}[Open full screen^] | xref:slides/index.adoc[All decks]${reverse}
`
}

function indexPage() {
  const rows = DECKS.map(
    (deck, position) =>
      `| ${position + 1}\n| xref:slides/${deck.key}/index.adoc[${deck.title}]\n| ${deck.covers}\n| ${deck.pairsWith}\n`,
  ).join('\n')
  return `= Workshop Slides

Presenter decks for the workshop, in run-of-show order. Each deck carries its
narration in speaker notes. Press kbd:[P] in the full-screen view to open the
presenter window.

[cols="1,3,4,2",options="header"]
|===
| # | Deck | Covers | Pairs with

${rows}
|===
`
}

await mkdir(attachmentsDirectory, { recursive: true })
await mkdir(pagesDirectory, { recursive: true })

for (const deck of DECKS) {
  const images = await copyImagesFor(deck)
  await buildDeck(deck)
  await mkdir(path.join(pagesDirectory, deck.key), { recursive: true })
  await writeFile(path.join(pagesDirectory, deck.key, 'index.adoc'), wrapperPage(deck), 'utf8')
  console.log(`slides: built ${deck.key} with ${images} image reference(s)`)
}

await writeFile(path.join(pagesDirectory, 'index.adoc'), indexPage(), 'utf8')
console.log(`slides: wrote ${DECKS.length} wrapper pages and the deck index`)
