import { execFileSync } from 'node:child_process'
import { cp, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const siteDirectory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repositoryDirectory = path.resolve(siteDirectory, '..')
const sourceDirectory = path.join(repositoryDirectory, 'workshop-content', 'content')
const imageDirectory = path.join(repositoryDirectory, 'workshop-content', 'images')
const generatedModuleDirectory = path.join(siteDirectory, 'modules', 'ROOT')
const pagesDirectory = path.join(generatedModuleDirectory, 'pages')
const generatedImagesDirectory = path.join(generatedModuleDirectory, 'images')

const files = []
async function collectMarkdown(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const entryPath = path.join(directory, entry.name)
    if (entry.isDirectory()) await collectMarkdown(entryPath)
    else if (entry.name.endsWith('.md')) files.push(entryPath)
  }
}

function pagePathFor(sourcePath) {
  const relative = path.relative(sourceDirectory, sourcePath)
  return relative.replace(/index\.en\.md$/, 'index.adoc')
}

function titleAndBody(markdown) {
  const match = markdown.match(/^---\s*\n([\s\S]*?)\n---\s*\n?/)
  if (!match) return { title: 'Workshop', body: markdown }
  const title = match[1].match(/^title:\s*["']?(.+?)["']?\s*$/m)?.[1] ?? 'Workshop'
  return { title, body: markdown.slice(match[0].length) }
}

function normaliseInline(markdown, sourcePath, replacements) {
  let value = markdown.replace(/\\:/g, ':')
  value = value.replace(/:link\[([^\]]+)]\{href="([^"]+)"[^}]*}/g, '[$1]($2)')
  value = value.replace(/:image\[([^\]]*)]\{src="([^"]+)"(?:\s+width=(\d+))?[^}]*}/g, (_, alt, source, width) => {
    const token = `SITETOKENIMAGE${replacements.length}END`
    replacements.push({ token, value: `image::${path.basename(source)}[alt="${alt}"${width ? `,width=${width}` : ''}]` })
    return token
  })
  value = value.replace(/\[([^\]]+)]\((\.{1,2}\/[^)]+\/)\)/g, (_, label, href) => {
    const targetMarkdown = path.resolve(path.dirname(sourcePath), href, 'index.en.md')
    const target = pagePathFor(targetMarkdown)
    const token = `SITETOKENXREF${replacements.length}END`
    replacements.push({ token, value: `xref:${target}[${label}]` })
    return token
  })
  return value.replace(/^::children\{[^}]*}\s*$/gm, '')
}

function replaceBlocks(markdown, replacements) {
  let value = markdown
  const blockPattern = /:::(alert|code|expand)\{([^}]*)}\n([\s\S]*?)\n:::/g
  value = value.replace(blockPattern, (_, kind, attributes, body) => {
    const token = `SITETOKENBLOCK${replacements.length}END`
    const header = attributes.match(/header="([^"]+)"/)?.[1]
    const language = attributes.match(/language=([^\s}]+)/)?.[1] ?? 'text'
    replacements.push({ token, kind, header, language, body })
    return token
  })
  return value
}

function promoteOrphanedHeadings(markdown) {
  const firstHeading = markdown.match(/^#{2,}\s+/m)?.[0]
  return firstHeading?.startsWith('###') ? markdown.replace(/^###\s+/gm, '## ') : markdown
}

function pandoc(markdown) {
  return execFileSync('pandoc', ['--from', 'markdown', '--to', 'asciidoc', '--wrap=none'], {
    input: markdown,
    encoding: 'utf8',
  }).trim()
}

function renderBlock(block) {
  if (block.kind === 'code') return `[source,${block.language}]\n----\n${block.body}\n----`
  const content = pandoc(block.body)
  if (block.kind === 'alert') {
    const style = block.header ? `.${block.header}\n` : ''
    return `${style}[${block.header?.toLowerCase().includes('warning') ? 'WARNING' : 'NOTE'}]\n====\n${content}\n====`
  }
  return `.${block.header ?? 'Details'}\n[%collapsible]\n====\n${content}\n====`
}

await rm(generatedModuleDirectory, { recursive: true, force: true })
await mkdir(pagesDirectory, { recursive: true })
await cp(imageDirectory, generatedImagesDirectory, { recursive: true, filter: source => !source.endsWith('.drawio') && !source.endsWith('.excalidraw') && !source.endsWith('DIAGRAM_PROMPTS.md') })

await collectMarkdown(sourceDirectory)
for (const sourcePath of files) {
  const markdown = await readFile(sourcePath, 'utf8')
  const { title, body } = titleAndBody(markdown)
  const replacements = []
  const normalised = normaliseInline(promoteOrphanedHeadings(body), sourcePath, replacements)
  const placeholderMarkdown = replaceBlocks(normalised, replacements)
  const converted = pandoc(placeholderMarkdown).replace(/^={3,}/gm, heading => heading.slice(1))
  let asciidoc = `= ${title}\n\n${converted}\n`
  for (const replacement of replacements) {
    const rendered = replacement.kind ? renderBlock(replacement) : replacement.value
    asciidoc = asciidoc.replace(replacement.token, rendered)
  }
  const destination = path.join(pagesDirectory, pagePathFor(sourcePath))
  await mkdir(path.dirname(destination), { recursive: true })
  await writeFile(destination, asciidoc)
}

console.log(`Prepared ${files.length} workshop pages for Antora.`)
