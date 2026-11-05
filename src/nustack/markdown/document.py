"""A Markdown file, read as CommonMark with most of GFM's extensions.

It reads GFM's extensions as `Document.MARKDOWN`'s comment says.

The checks inspect the lines of its whole text and of its body below any frontmatter,
split where an editor breaks lines, and the line in its whole text that each offset, or
each body line, falls on; its headings and the sections under them; the anchors and
Markdown links a reader follows; its fenced code blocks; a playbook's steps; whether a
text shows anything to a reader; and whether a part lifted out keeps every reference it
uses. It also reads any text's reference definitions, and tells whether a text reads the
same beside given ones, as on a page that joins several parts. A path that holds no
readable UTF-8 file is refused with its reason.
"""

import bisect
import copy
import posixpath
import re
from dataclasses import dataclass
from functools import cached_property
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar
from typing import assert_never
from urllib.parse import SplitResult
from urllib.parse import unquote
from urllib.parse import urlsplit
lazy from collections.abc import Iterable

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin
lazy from markdown_it.token import Token
lazy from markdown_it.utils import EnvType

from nustack.markdown.frontmatter import FrontmatterBlock
from nustack.problem import Problem
from nustack.tree import Absent
from nustack.tree import File
from nustack.tree import Read
from nustack.tree import Unreadable
from nustack.validation import Pattern

type Definitions = frozendict[str, frozendict[str, str]]


class UnmappedTokenError(ValueError):
    """A block token the Markdown parser gave no line range."""


@dataclass(frozen=True)
class Lines:
    """Text split into lines, each keeping its own line ending."""

    BREAK: ClassVar[re.Pattern[str]] = re.compile(r"\r\n|\r|\n")
    LINE: ClassVar[re.Pattern[str]] = re.compile(
        rf".*?(?:{BREAK.pattern})|.+\Z", re.DOTALL
    )
    CRLF_OR_CR: ClassVar[re.Pattern[str]] = re.compile(r"\r\n?")
    text: str

    @cached_property
    def lines(self) -> tuple[str, ...]:
        return tuple(self.LINE.findall(self.text))

    @cached_property
    def break_ends(self) -> tuple[int, ...]:
        return tuple(found.end() for found in self.BREAK.finditer(self.text))

    def line_at(self, index: int) -> int:
        return 1 + bisect.bisect_right(self.break_ends, index)

    @staticmethod
    def span(token: Token) -> tuple[int, int]:
        match token.map:
            case [start, end]:
                return start, end
            case _:
                msg = (
                    f"markdown-it gave the {token.type} token no line range; pass"
                    " Lines.span only block tokens, which markdown-it maps to lines"
                )
                raise UnmappedTokenError(msg)


@dataclass(frozen=True)
class Heading:
    """A heading outside quotes and lists: its level, its title and its lines."""

    level: int
    title: str
    start: int
    body_start: int


@dataclass(frozen=True)
class Section:
    """A heading's title, and the lines under it up to the next heading as high.

    Line breaks in the body are line feeds, whatever the file's line endings. The
    body starts on the line after the heading, or after a setext heading's underline.
    """

    title: str
    body: str
    start: int
    body_start: int
    end: int

    def holds(self, line: int) -> bool:
        return self.start <= line < self.end

    def holds_in_body(self, line: int) -> bool:
        return self.body_start <= line < self.end


@dataclass(frozen=True)
class Link:
    """A link or image in a document: where it points, and the line it sits on."""

    href: str
    target: Path | None
    fragment: str
    line: int


@dataclass(frozen=True)
class DefinitionLines:
    """A reference definition's label, as markdown-it keys it, and its lines."""

    label: str
    start: int
    end: int


@dataclass(frozen=True)
class Fence:
    """A fenced code block: its info string and its content."""

    info: str
    content: str


class Sight(HTMLParser):
    """What rendered HTML shows: text, an image, or a tag GitHub shows as text.

    Character references are decoded first, so a no-break space shows nothing. A
    details element counts too, for the summary it always shows. A comment shows
    nothing, and nor does any other tag of itself, such as a thematic break, a task
    item's checkbox or an empty list item or table cell, though GitHub may draw it.
    """

    # Of the elements GitHub keeps, only an image shows without text:
    # https://github.com/gjtorikian/html-pipeline/blob/v2.14.3/lib/html/pipeline/sanitization_filter.rb
    # GitHub's GFM rendering gives a details element without a summary a "Details"
    # one, and a browser gives it its own:
    # https://html.spec.whatwg.org/multipage/interactive-elements.html#the-details-element
    # GitHub shows each tag GFM disallows as text:
    # https://github.github.com/gfm/#disallowed-raw-html-extension-
    SHOWN: ClassVar[frozenset[str]] = frozenset(
        {
            "img",
            "details",
            "title",
            "textarea",
            "style",
            "xmp",
            "iframe",
            "noembed",
            "noframes",
            "script",
            "plaintext",
        }
    )

    def __init__(self) -> None:
        super().__init__()
        self.seen = False

    @classmethod
    def of(cls, html: str) -> bool:
        sight = cls()
        sight.feed(html)
        sight.close()
        return sight.seen

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],  # noqa: ARG002 -- HTMLParser passes them
    ) -> None:
        self.seen |= tag in self.SHOWN

    def handle_data(self, data: str) -> None:
        self.seen |= re.search(Pattern.NON_BLANK, data) is not None


@dataclass(frozen=True)
class Document:
    """A Markdown file's path and text, and what the checks read from them."""

    # GitHub reads GFM's tables, each row on its own line, and its strikethrough, with
    # one tilde or two:
    # https://github.github.com/gfm/#tables-extension-
    # https://github.github.com/gfm/#strikethrough-extension-
    # GitHub's renderer departs from the spec's task-list rule in cases it does not
    # document, such as a no-break space or a line break after the marker, or a marker
    # that fills its paragraph with a block directly below:
    # https://github.github.com/gfm/#task-list-items-extension-
    # The task-list plugin reads the spec's whitespace after a marker, so shows reads a
    # marker as GitHub does where a space and then text follow it on its line, or where
    # nothing follows it in its list item. Elsewhere it may not: it finds nothing in
    # "- [x]\n  &nbsp;", where GitHub prints the marker, and something in
    # "- [ ]\u00a0&nbsp;" and "- [ ]\n  <!-- x -->", where GitHub draws a checkbox. And
    # the plugin draws a checkbox GitHub leaves out before a marker that a reference
    # definition turns into a link:
    # https://github.com/executablebooks/mdit-py-plugins/blob/v0.6.1/mdit_py_plugins/tasklists/__init__.py
    # markdown-it-py's own tasklists option draws a checkbox after a tab and keeps a
    # marker directly before a line break as text, as GitHub does, but turns a defined
    # marker into a checkbox and drops its link, so a task item GitHub shows as that
    # link would show nothing:
    # https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/markdown_it/rules_block/list.py
    # Bare URLs and email addresses stay text, and every_href leaves them out:
    # mdit-py-plugins' autolink plugin can hang on link text that holds a www.
    # address, and its other rules miss addresses the spec links, such as a.b-c_d@a.b:
    # https://github.com/executablebooks/mdit-py-plugins/issues/160
    # https://github.github.com/gfm/#autolinks-extension-
    MARKDOWN: ClassVar[MarkdownIt] = (
        MarkdownIt(options_update={"strikethrough_single_tilde": True})
        .enable(["table", "strikethrough"])
        .use(tasklists_plugin)
    )
    SLUG_DROPS: ClassVar[re.Pattern[str]] = re.compile(r"[^\w\- ]")
    # GitHub builds a heading's anchor from the heading's text nodes, and an image's
    # alt text is no text node, since it renders as the img element's alt attribute:
    # https://github.com/gjtorikian/html-pipeline/blob/v2.14.3/lib/html/pipeline/toc_filter.rb#L41-L45
    # https://github.com/sparklemotion/nokogiri/blob/v1.16.0/ext/nokogiri/xml_node.c#L721-L729
    SLUGGED: ClassVar[frozenset[str]] = frozenset({"text", "code_inline"})
    path: Path
    text: str

    @cached_property
    def whole_lines(self) -> Lines:
        return Lines(self.text)

    @cached_property
    def text_lines(self) -> tuple[str, ...]:
        return self.whole_lines.lines

    @cached_property
    def body(self) -> str:
        return FrontmatterBlock.body_of(self.text)

    @cached_property
    def body_lines(self) -> tuple[str, ...]:
        return Lines(self.body).lines

    @cached_property
    def frontmatter_lines(self) -> int:
        return len(self.text_lines) - len(self.body_lines)

    @cached_property
    def tokens(self) -> tuple[Token, ...]:
        return tuple(self.MARKDOWN.parse(self.body))

    @cached_property
    def headings(self) -> tuple[Heading, ...]:
        return tuple(
            Heading(
                int(token.tag.removeprefix("h")),
                self.tokens[index + 1].content,
                *Lines.span(token),
            )
            for index, token in enumerate(self.tokens)
            if token.type == "heading_open" and token.level == 0
        )

    @cached_property
    def sections(self) -> tuple[Section, ...]:
        return self.headed(2)

    @cached_property
    def anchors(self) -> frozenset[str]:
        seen: dict[str, int] = {}
        found: set[str] = set()
        for index, token in enumerate(self.tokens):
            if token.type == "heading_open":
                slug = self.slug(self.tokens[index + 1])
                repeats = seen.get(slug, 0)
                seen[slug] = repeats + 1
                found.add(f"{slug}-{repeats}" if repeats else slug)
        return frozenset(found)

    # markdown-it keeps raw HTML as html_inline and html_block tokens that hold the
    # tag as text, so no check reads a link written as an HTML tag, such as <a href>
    # or <img src>:
    # https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/markdown_it/rules_inline/html_inline.py
    # https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/markdown_it/rules_block/html_block.py
    @cached_property
    def hrefs(self) -> tuple[tuple[str, int], ...]:
        return tuple(
            (str(child.attrs["href" if child.type == "link_open" else "src"]), line)
            for token in self.tokens
            if token.type == "inline"
            for line in (Lines.span(token)[0],)
            for child in token.children or ()
            if child.type in {"link_open", "image"}
        )

    @cached_property
    def every_href(self) -> tuple[str, ...]:
        return tuple(
            str(child.attrs["href" if child.type == "link_open" else "src"])
            for token in self.MARKDOWN.parse(self.text)
            for child in token.children or ()
            if child.type in {"link_open", "image"}
        )

    @cached_property
    def absolute(self) -> tuple[str, ...]:
        return tuple(
            href
            for href, _ in self.hrefs
            if posixpath.isabs(local_path(urlsplit(href)) or "")
        )

    @cached_property
    def malformed(self) -> tuple[str, ...]:
        return tuple(
            href
            for href, line in self.hrefs
            if self.link(href, line) is None and href not in self.absolute
        )

    @cached_property
    def links(self) -> tuple[Link, ...]:
        return tuple(
            link
            for href, line in self.hrefs
            if (link := self.link(href, line)) is not None
        )

    @cached_property
    def fences(self) -> tuple[Fence, ...]:
        return tuple(
            Fence(token.info.strip(), token.content)
            for token in self.tokens
            if token.type == "fence"
        )

    @cached_property
    def steps(self) -> tuple[str, ...]:
        depth = 0
        found: list[str] = []
        for token in self.tokens:
            if token.type == "ordered_list_open":
                depth += 1
            elif token.type == "ordered_list_close":
                depth -= 1
            elif token.type == "list_item_open" and depth == 1 and token.level == 1:
                start, end = Lines.span(token)
                found.append("".join(self.body_lines[start:end]))
        return tuple(found)

    @cached_property
    def definitions(self) -> Definitions:
        return self.defined_in(self.body)

    # markdown-it-py, unlike markdown-it, gives each reference definition a token that
    # holds its lines once inline_definitions is set:
    # https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/markdown_it/rules_block/reference.py#L165-L174
    @cached_property
    def defining(self) -> MarkdownIt:
        parser = copy.copy(self.MARKDOWN)
        parser.options = copy.deepcopy(self.MARKDOWN.options)
        parser.options["inline_definitions"] = True
        return parser

    @cached_property
    def definition_lines(self) -> tuple[DefinitionLines, ...]:
        return tuple(
            DefinitionLines(token.meta["id"], *Lines.span(token))
            for token in self.defining.parse(self.body)
            if token.type == "definition"
        )

    @cached_property
    def references(self) -> frozendict[str, str]:
        return frozendict(
            (label, definition["href"])
            for label, definition in self.definitions.items()
        )

    @classmethod
    def of(cls, path: Path, read: Read, missing: str) -> Document | Problem:
        match read:
            case File(text=str() as text):
                return cls(path, text)
            case File():
                return Problem(path, Problem.NOT_UTF8)
            case Absent() as absent:
                return Problem(path, absent.absence(missing))
            case Unreadable(reason=reason):
                return Problem(path, reason)
            case unexpected:
                assert_never(unexpected)

    @classmethod
    def defined_in(cls, text: str) -> Definitions:
        found: EnvType = {}
        cls.MARKDOWN.parse(text, found)
        return frozendict(
            (label, frozendict(href=definition["href"], title=definition["title"]))
            for label, definition in found.get("references", {}).items()
        )

    def headed(self, level: int) -> tuple[Section, ...]:
        sections: list[Section] = []
        end = len(self.body_lines)
        for heading in reversed(self.headings):
            if heading.level == level:
                sections.append(
                    Section(
                        heading.title,
                        self.text_between(heading.body_start, end),
                        heading.start,
                        heading.body_start,
                        end,
                    )
                )
            if heading.level <= level:
                end = heading.start
        return tuple(reversed(sections))

    def text_between(self, start: int, end: int) -> str:
        text = "".join(self.body_lines[start:end])
        return Lines.CRLF_OR_CR.sub("\n", text).strip("\n")

    def line_at(self, index: int) -> int:
        return self.whole_lines.line_at(index)

    def file_line(self, body_line: int) -> int:
        return self.frontmatter_lines + body_line + 1

    def slug(self, inline: Token) -> str:
        text = self.inline_text(inline.children or (), self.SLUGGED)
        return self.SLUG_DROPS.sub("", text.lower()).replace(" ", "-")

    @staticmethod
    def inline_text(children: Iterable[Token], kinds: frozenset[str]) -> str:
        return "".join(child.content for child in children if child.type in kinds)

    def link(self, href: str, line: int) -> Link | None:
        parts = urlsplit(href)
        path = local_path(parts)
        if path is None:
            return Link(href, None, "", line)
        if "\0" in path or posixpath.isabs(path):
            return None
        target = (
            Path(posixpath.normpath(self.path.parent / path)) if path else self.path
        )
        return Link(href, target, unquote(parts.fragment), line)

    def relative_hrefs(self, section: Section) -> tuple[str, ...]:
        return tuple(
            href
            for href, line in self.hrefs
            if section.holds_in_body(line) and local_path(urlsplit(href)) is not None
        )

    def shows(self, text: str) -> bool:
        return Sight.of(self.MARKDOWN.render(text))

    def stands_alone(self, text: str) -> bool:
        return self.stands_alone_beside(text, self.definitions)

    @classmethod
    def stands_alone_beside(cls, text: str, definitions: Definitions) -> bool:
        defined = {"references": dict(definitions)}
        return cls.MARKDOWN.render(text, defined) == cls.MARKDOWN.render(text)


def local_path(parts: SplitResult) -> str | None:
    return None if parts.scheme or parts.netloc else unquote(parts.path)
