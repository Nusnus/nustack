/**
 * Markdown as GitHub renders it, read by one CommonMark parser, micromark, with its GitHub Flavored Markdown and YAML
 * frontmatter extensions, into frozen values: the top-level blocks, a skill's frontmatter among them as a yaml block,
 * and their headings; each link and image with its destination; each link reference definition; and a heading's
 * section. The check and the release read Markdown only through these values, so each reads it as GitHub's renderer
 * does.
 */
import type { Nodes, RootContent } from "mdast"
import { fromMarkdown } from "mdast-util-from-markdown"
import { frontmatterFromMarkdown } from "mdast-util-frontmatter"
import { gfmFromMarkdown } from "mdast-util-gfm"
import { frontmatter } from "micromark-extension-frontmatter"
import { gfm } from "micromark-extension-gfm"

/** Where a value sits in its text: the offset of its first character and of the one after its last. */
export type Span = Readonly<{ start: number; end: number }>

/** A link reference definition, `[label]: destination`, wherever it sits, a blockquote or a list item included. */
export type Definition = Span & Readonly<{ label: string; identifier: string; destination: string }>

/**
 * A link or image as the page renders it: inline, an autolink or a reference, full, collapsed or shortcut. A
 * reference's label is the one it names, its definition the first that label matches, in any case, and its destination
 * that definition's; an inline link or an autolink has neither.
 */
export type Link = Span &
  Readonly<{
    image: boolean
    destination: string
    label: string | undefined
    definition: Definition | undefined
  }>

/**
 * A heading at the top level, ATX or setext. Its text is its content as written, its atx the line an ATX heading of its
 * level writes for it, such as `## B` for a setext B, and its lines the lines it fills, the line break after them
 * included. Its reference is the label of the reference link it opens with, such as `0.0.1` in `## [0.0.1] - <date>`.
 */
export type Heading = Span &
  Readonly<{
    type: "heading"
    depth: number
    text: string
    atx: string
    reference: string | undefined
    lines: Span
  }>

/** A block at the top level of the text, outside any blockquote or list. */
export type Block = Heading | (Span & Readonly<{ type: Exclude<RootContent["type"], "heading"> }>)

/** One parse of a Markdown text. */
export type Markdown = Readonly<{
  text: string
  blocks: readonly Block[]
  headings: readonly Heading[]
  links: readonly Link[]
  definitions: readonly Definition[]
}>

/** The text under a heading, up to the line before the next heading of its level or higher, or to the end. */
export type Section = Span & Readonly<{ heading: Heading; body: string; next: Heading | undefined }>

export function markdown(text: string): Markdown {
  const root = fromMarkdown(text, {
    extensions: [frontmatter(), gfm()],
    mdastExtensions: [frontmatterFromMarkdown(), gfmFromMarkdown()],
  })
  const definitions: Definition[] = []
  // A label matches the first definition of its normalized form: https://spec.commonmark.org/0.31.2/#matches
  const defined = new Map<string, Definition>()
  const written: Nodes[] = []
  walk(root, (node) => {
    if (node.type === "definition") {
      const label = node.label ?? node.identifier
      const definition = Object.freeze({
        ...spanOf(node),
        label,
        identifier: node.identifier,
        destination: node.url,
      })
      definitions.push(definition)
      if (!defined.has(node.identifier)) defined.set(node.identifier, definition)
    } else written.push(node)
  })
  const linkOf = (node: Nodes): Link | undefined => {
    const span = spanOf(node)
    const image = node.type === "image" || node.type === "imageReference"
    if (node.type === "link" || node.type === "image")
      return Object.freeze({
        ...span,
        image,
        destination: node.url,
        label: undefined,
        definition: undefined,
      })
    if (node.type !== "linkReference" && node.type !== "imageReference") return undefined
    const definition = defined.get(node.identifier)
    // micromark makes a reference only of a label a definition matches.
    if (definition === undefined)
      throw new Error(`a reference at offset ${span.start} matches no definition`)
    const label = node.label ?? node.identifier
    return Object.freeze({ ...span, image, destination: definition.destination, label, definition })
  }
  const blocks = root.children.map((node) => blockOf(text, node))
  return Object.freeze({
    text,
    blocks: Object.freeze(blocks),
    headings: Object.freeze(blocks.filter((block) => block.type === "heading")),
    links: Object.freeze(written.flatMap((node) => linkOf(node) ?? [])),
    definitions: Object.freeze(definitions),
  })
}

export function section(read: Markdown, heading: string): Section | undefined {
  const at = read.headings.findIndex(
    ({ atx }) => atx === heading || atx.startsWith(`${heading} - `),
  )
  const found = read.headings[at]
  if (found === undefined) return undefined
  const next = read.headings.slice(at + 1).find(({ depth }) => depth <= found.depth)
  const start = found.lines.end
  const end = Math.max(
    start,
    next === undefined ? read.text.length : lineBreakBefore(read.text, next.lines.start),
  )
  return Object.freeze({ start, end, heading: found, body: read.text.slice(start, end), next })
}

export function within(inner: Span, outer: Span): boolean {
  return inner.start >= outer.start && inner.end <= outer.end
}

function blockOf(text: string, node: RootContent): Block {
  const span = spanOf(node)
  if (node.type !== "heading") return Object.freeze({ ...span, type: node.type })
  const [first, last] = [node.children[0], node.children.at(-1)]
  const content =
    first === undefined || last === undefined
      ? ""
      : text.slice(spanOf(first).start, spanOf(last).end)
  const opener = first?.type === "linkReference" ? (first.label ?? first.identifier) : undefined
  const { start, column } = pointOf(node, "start")
  const lineEnd = span.end + lineBreakAt(text, span.end)
  return Object.freeze({
    ...span,
    type: "heading",
    depth: node.depth,
    text: content,
    atx: `${"#".repeat(node.depth)} ${content}`,
    reference: opener,
    lines: Object.freeze({ start: start - (column - 1), end: lineEnd }),
  })
}

// The length of the line break at an offset, 0 at the text's end: https://spec.commonmark.org/0.31.2/#line-ending
function lineBreakAt(text: string, offset: number): number {
  if (text.startsWith("\r\n", offset)) return 2
  return text[offset] === "\n" || text[offset] === "\r" ? 1 : 0
}

// lineStart follows a line break, and a CRLF counts as one, starting at its CR.
function lineBreakBefore(text: string, lineStart: number): number {
  return lineStart - (text.endsWith("\r\n", lineStart) ? 2 : 1)
}

function walk(node: Nodes, visit: (node: Nodes) => void): void {
  visit(node)
  if ("children" in node) for (const child of node.children) walk(child, visit)
}

function spanOf(node: Nodes): Span {
  return Object.freeze({ start: pointOf(node, "start").start, end: pointOf(node, "end").start })
}

// mdast-util-from-markdown gives every node it builds a position with offsets.
function pointOf(node: Nodes, edge: "start" | "end"): { start: number; column: number } {
  const point = node.position?.[edge]
  if (point?.offset === undefined) throw new Error(`a ${node.type} node has no ${edge} offset`)
  return { start: point.offset, column: point.column }
}
