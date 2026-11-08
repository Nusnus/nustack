/** Markdown read as GitHub renders it: each kind of heading and its section, each kind of link and each definition. */
import { describe, expect, test } from "bun:test"
import { markdown, section } from "../../../scripts/markdown.ts"

const destinations = (text: string) => markdown(text).links.map(({ destination }) => destination)
const labels = (text: string) => markdown(text).links.map(({ label }) => label)
const atx = (text: string) => markdown(text).headings.map((heading) => heading.atx)
const body = (text: string, heading: string) => section(markdown(text), heading)?.body

describe("headings", () => {
  test("reads an ATX heading with its level and its text", () => {
    expect(markdown("### B ###\n").headings).toMatchObject([{ depth: 3, text: "B", atx: "### B" }])
  })

  test("reads a setext heading as the ATX heading of its level", () => {
    expect(atx("A\n===\n\nB\n---\n")).toEqual(["# A", "## B"])
  })

  test("reads a heading indented one to three spaces", () => {
    expect(atx("   ## B\n")).toEqual(["## B"])
  })

  test("reads a heading whose marker a tab follows", () => {
    expect(atx("##\tB\n")).toEqual(["## B"])
  })

  test("reads a bare ## as an empty heading", () => {
    expect(markdown("##\n").headings).toMatchObject([{ depth: 2, text: "" }])
  })

  test("reads no heading in indented code, fenced code or HTML", () => {
    expect(atx("    ## B\n\n```\n## C\n```\n\n<div>\n## D\n</div>\n")).toEqual([])
  })

  test("reads a heading in a blockquote as no heading of the text's own", () => {
    expect(atx("> ## B\n")).toEqual([])
  })

  test("names the label of the reference a heading opens with", () => {
    const read = markdown("## [0.0.1] - d\n\n## [0.0.2]\n\n[0.0.1]: https://h\n")
    expect(read.headings.map(({ reference }) => reference)).toEqual(["0.0.1", undefined])
  })

  test("names a heading's reference by its label as written, not its normalized form", () => {
    expect(markdown("## [ABC] - d\n\n[abc]: https://h\n").headings[0]?.reference).toBe("ABC")
  })

  test("ends the lines of a heading at the text's end, where no line break follows", () => {
    expect(markdown("## A").headings[0]?.lines).toEqual({ start: 0, end: 4 })
  })
})

describe("section", () => {
  test("ends a section with CRLF line breaks before the break that precedes the next heading", () => {
    expect(section(markdown("## a\r\n\r\nx\r\n## b\r\n"), "## a")?.body).toBe("\r\nx")
  })

  test("ends a heading's line at a lone carriage return, a CommonMark line ending too", () => {
    expect(body("## a\rx\r## b\r", "## a")).toBe("x")
  })

  test("gives an empty section that ends where it starts under a heading the next one follows at once", () => {
    expect(section(markdown("## a\n## b\n"), "## a")).toMatchObject({ start: 5, end: 5, body: "" })
  })

  const text =
    "# T\n\n## A - more\n\n```\n# code\n```\n\n<div>\n# html\n</div>\n\n### deeper\n\na\n\n## B\n\nb"

  test("cuts a section to the next heading of its level or higher, past code, HTML and deeper headings", () => {
    const found = section(markdown(text), "## A")
    expect(found?.body).toBe("\n```\n# code\n```\n\n<div>\n# html\n</div>\n\n### deeper\n\na\n")
    expect(found?.next?.atx).toBe("## B")
  })

  test("cuts the last section to the end, and finds no heading the text lacks or holds only in code", () => {
    expect(section(markdown(text), "## B")).toMatchObject({ body: "\nb", next: undefined })
    expect(section(markdown(text), "## C")).toBeUndefined()
    expect(section(markdown("```\n## C\n```\n"), "## C")).toBeUndefined()
  })

  test("finds a heading by its exact text or that text before - , not by a heading it only starts", () => {
    expect(section(markdown("## Ab\n\n## A - b\n\nx\n"), "## A")?.heading.atx).toBe("## A - b")
  })

  test("ends a section at a setext heading", () => {
    expect(body("## A\n\na\n\nB\n-\n\nb\n", "## A")).toBe("\na\n")
  })

  test("ends a section at an indented heading", () => {
    expect(body("## A\n\na\n\n  ## B\n\nb\n", "## A")).toBe("\na\n")
  })

  test("ends a section at a heading whose marker a tab follows", () => {
    expect(body("## A\n\na\n\n##\tB\n\nb\n", "## A")).toBe("\na\n")
  })

  test("ends a section at a bare ##", () => {
    expect(body("## A\n\na\n\n##\n\nb\n", "## A")).toBe("\na\n")
  })

  test("runs a section past indented code that looks like a heading", () => {
    expect(body("## A\n\na\n\n    ## B\n\nb\n", "## A")).toBe("\na\n\n    ## B\n\nb\n")
  })

  test("finds a setext heading by its ATX form", () => {
    expect(body("A\n-\n\na\n", "## A")).toBe("\na\n")
  })

  test("gives an empty body to a heading the next one follows at once", () => {
    expect(body("## A\n## B\n", "## A")).toBe("")
  })
})

describe("links", () => {
  test("reads an inline link, an image, an angled destination and a titled one", () => {
    expect(destinations("[a](x.md) ![i](i.png) [b](<y z.md>) [c](w.md 'title')")).toEqual([
      "x.md",
      "i.png",
      "y z.md",
      "w.md",
    ])
  })

  test("reads a full, a collapsed and a shortcut reference, in any case, by their definition", () => {
    const text = "[a][X] [x][] [X]\n\n[x]: https://h\n"
    expect(destinations(text)).toEqual(["https://h", "https://h", "https://h"])
    expect(labels(text)).toEqual(["X", "x", "X"])
  })

  test("reads an image reference by its definition", () => {
    expect(markdown("![i][x]\n\n[x]: i.png\n").links).toMatchObject([
      { image: true, destination: "i.png", label: "x" },
    ])
  })

  test("reads an autolink and a GFM literal autolink", () => {
    expect(destinations("<https://a> www.b.com")).toEqual(["https://a", "http://www.b.com"])
  })

  test("reads the inner link of a nested label, as the outer brackets stay text", () => {
    expect(markdown("[[d][x]](y.md)\n\n[x]: https://x\n").links).toMatchObject([
      { destination: "https://x", label: "x" },
    ])
  })

  test("reads a nested label whose reference is undefined as text inside the outer link", () => {
    expect(markdown("[[d][x]](y.md)\n").links).toMatchObject([
      { destination: "y.md", label: undefined },
    ])
  })

  test("reads no link in a code span", () => {
    expect(destinations("`[a](x.md)`")).toEqual([])
  })

  test("reads no link in indented code", () => {
    expect(destinations("    [a](x.md)\n")).toEqual([])
  })

  test("reads no link in fenced code", () => {
    expect(destinations("```\n[a](x.md)\n```\n")).toEqual([])
  })

  test("reads no link between escaped brackets", () => {
    expect(destinations("\\[a\\](x.md)\n")).toEqual([])
  })

  test("reads no link in an HTML comment", () => {
    expect(destinations("<!-- [a](x.md) -->\n")).toEqual([])
  })

  test("reads a task-list marker as no reference, even where a definition names it", () => {
    expect(destinations("- [ ] a\n- [x] b\n\n[x]: x.md\n[ ]: y.md\n")).toEqual([])
  })

  test("reads no reference whose label no definition names", () => {
    expect(destinations("[a][missing] [shortcut]\n")).toEqual([])
  })

  test("marks an inline image as an image, and an inline link as none", () => {
    expect(markdown("![i](i.png) [l](l.md)\n").links.map(({ image }) => image)).toEqual([
      true,
      false,
    ])
  })
})

describe("definitions", () => {
  test("reads a definition at the top level, in a blockquote and in a list", () => {
    const read = markdown("[a]: https://a\n\n> [b]: b.md\n\n- [c]: <c d.md> 'title'\n\n[b] [c]\n")
    expect(read.definitions.map(({ label, destination }) => [label, destination])).toEqual([
      ["a", "https://a"],
      ["b", "b.md"],
      ["c", "c d.md"],
    ])
    expect(read.links.map(({ destination }) => destination)).toEqual(["b.md", "c d.md"])
  })

  test("resolves a label to its first definition", () => {
    expect(destinations("[x]\n\n[x]: first.md\n[X]: second.md\n")).toEqual(["first.md"])
  })

  test("keeps a definition's label as written, and its identifier normalized", () => {
    expect(markdown("[A]: a.md\n").definitions).toMatchObject([{ label: "A", identifier: "a" }])
  })
})

describe("footnotes", () => {
  test("reads a footnote call with the first definition its label matches, in any case", () => {
    const text = "See[^Note].\n\n[^note]: First.\n\n[^NOTE]: Second.\n"
    const read = markdown(text)
    expect(read.footnotes.map(({ label }) => label)).toEqual(["Note"])
    const [footnote] = read.footnotes
    expect(text.slice(footnote?.definition.start, footnote?.definition.end)).toBe("[^note]: First.")
  })

  test("reads a footnote label no definition matches as text, not a call", () => {
    expect(markdown("See[^none].\n").footnotes).toEqual([])
  })

  test("lists each footnote definition, one whose label repeats an earlier one's included", () => {
    expect(markdown("See[^a].\n\n[^a]: n\n\n[^A]: m\n").notes).toEqual([
      { start: 10, end: 17, identifier: "a" },
      { start: 19, end: 26, identifier: "a" },
    ])
  })
})

describe("rows", () => {
  test("lists each table row's cells and the links in each, the header row first", () => {
    const read = markdown(
      "| [a](a.md) | b |\n| --- | --- |\n| [c](c.md) [d](d.md) | `[e](e.md)` |\n",
    )
    expect(
      read.rows.map((row) => row.map((cell) => cell.map(({ destination }) => destination))),
    ).toEqual([
      [["a.md"], []],
      [["c.md", "d.md"], []],
    ])
  })

  test("reads lines of pipes with no delimiter row as no table", () => {
    expect(markdown("| [a](a.md) | b |\n").rows).toEqual([])
  })
})

describe("html", () => {
  test("reads each block of raw HTML and each inline tag as written, an HTML comment included", () => {
    expect(markdown("<!-- c -->\n\na <b>x</b>\n").html).toEqual([
      { start: 0, end: 10, value: "<!-- c -->" },
      { start: 14, end: 17, value: "<b>" },
      { start: 18, end: 22, value: "</b>" },
    ])
  })
})

test("freezes every value it gives", () => {
  const read = markdown(
    "## A\n\n| [a](a.md) |\n| - |\n\n[x]: https://h\n\n<!-- c -->\n\nSee[^1].\n\n[^1]: n\n",
  )
  for (const value of [
    read,
    read.notes,
    read.notes[0],
    read.footnotes,
    read.footnotes[0],
    section(read, "## A"),
    read.blocks,
    read.headings[0],
    read.headings[0]?.lines,
    read.links,
    read.links[0],
    read.definitions[0],
    read.html[0],
    read.rows,
    read.rows[0],
    read.rows[0]?.[0],
  ])
    expect(Object.isFrozen(value)).toBe(true)
})
