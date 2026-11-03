"""A Markdown file, read as CommonMark into the parts the checks inspect.

Those are its lines as an editor numbers them, its second-level sections, the
anchors and links a reader follows, its fenced code blocks and a playbook's steps,
and whether a part lifted out keeps every reference it uses. A file that is not
UTF-8 text is refused with its reason.
"""

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

from markdown_it import MarkdownIt
lazy from markdown_it.token import Token
lazy from markdown_it.utils import EnvType

from nustack.markdown.frontmatter import FrontmatterBlock
from nustack.problem import Problem
from nustack.tree import Absent
from nustack.tree import File
from nustack.tree import Read
from nustack.tree import Unreadable
from nustack.validation import Pattern


class UnmappedTokenError(ValueError):
    """A block token the Markdown parser gave no line range."""


@dataclass(frozen=True)
class Lines:
    """Text split into lines, each keeping its own line ending."""

    LINE: ClassVar[re.Pattern[str]] = re.compile(r".*?(?:\r\n|\r|\n)|.+\Z", re.DOTALL)
    CRLF_OR_CR: ClassVar[re.Pattern[str]] = re.compile(r"\r\n?")
    text: str

    @cached_property
    def lines(self) -> tuple[str, ...]:
        return tuple(self.LINE.findall(self.text))

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
class Section:
    """A second-level heading's title, and the lines under it up to the next one.

    Line breaks in the body are line feeds, whatever the file's line endings.
    """

    title: str
    body: str
    start: int
    end: int

    def holds(self, line: int) -> bool:
        return self.start <= line < self.end


@dataclass(frozen=True)
class Link:
    """A link or image in a document: where it points, and the line it sits on."""

    href: str
    target: Path | None
    fragment: str
    line: int


@dataclass(frozen=True)
class Fence:
    """A fenced code block: its info string and its content."""

    info: str
    content: str


class Sight(HTMLParser):
    """What a reader sees of rendered HTML: text that is not blank, or a shown tag.

    Character references are decoded first, so a non-breaking space shows nothing,
    and a comment or any other tag shows nothing of itself.
    """

    # Of the elements GitHub keeps, only an image shows without text:
    # https://github.com/gjtorikian/html-pipeline/blob/v2.14.3/lib/html/pipeline/sanitization_filter.rb
    # GitHub shows each tag GFM disallows as text:
    # https://github.github.com/gfm/#disallowed-raw-html-extension-
    SHOWN: ClassVar[frozenset[str]] = frozenset(
        {
            "img",
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
    """A Markdown file's path and text, read as CommonMark."""

    MARKDOWN: ClassVar[MarkdownIt] = MarkdownIt()
    SLUG_DROPS: ClassVar[re.Pattern[str]] = re.compile(r"[^\w\- ]")
    path: Path
    text: str

    @cached_property
    def body(self) -> str:
        return FrontmatterBlock.body_of(self.text)

    @cached_property
    def tokens(self) -> tuple[Token, ...]:
        return tuple(self.MARKDOWN.parse(self.body))

    @cached_property
    def sections(self) -> tuple[Section, ...]:
        headings = [
            (self.tokens[index + 1].content, Lines.span(token))
            for index, token in enumerate(self.tokens)
            if token.type == "heading_open" and token.tag == "h2" and token.level == 0
        ]
        lines = Lines(self.body).lines
        starts = [start for _, (start, _) in headings]
        ends = [*starts[1:], len(lines)][: len(headings)]
        return tuple(
            Section(
                title,
                Lines.CRLF_OR_CR.sub(
                    "\n", "".join(lines[body_start:end]).strip("\r\n")
                ),
                start,
                end,
            )
            for (title, (start, body_start)), end in zip(headings, ends, strict=True)
        )

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
        lines = Lines(self.body).lines
        depth = 0
        found: list[str] = []
        for token in self.tokens:
            if token.type == "ordered_list_open":
                depth += 1
            elif token.type == "ordered_list_close":
                depth -= 1
            elif token.type == "list_item_open" and depth == 1 and token.level == 1:
                start, end = Lines.span(token)
                found.append("".join(lines[start:end]))
        return tuple(found)

    @cached_property
    def definitions(self) -> frozendict[str, frozendict[str, str]]:
        found: EnvType = {}
        self.MARKDOWN.parse(self.body, found)
        return frozendict(
            (label, frozendict(href=definition["href"], title=definition["title"]))
            for label, definition in found.get("references", {}).items()
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

    def line_at(self, index: int) -> int:
        return self.text[:index].count("\n") + 1

    def slug(self, inline: Token) -> str:
        text = "".join(
            child.content
            for child in inline.children or ()
            if child.type in {"text", "code_inline"}
        )
        return self.SLUG_DROPS.sub("", text.lower()).replace(" ", "-")

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

    def shows(self, text: str) -> bool:
        return Sight.of(self.MARKDOWN.render(text))

    def stands_alone(self, text: str) -> bool:
        defined = {"references": dict(self.definitions)}
        return self.MARKDOWN.render(text, defined) == self.MARKDOWN.render(text)


def local_path(parts: SplitResult) -> str | None:
    return None if parts.scheme or parts.netloc else unquote(parts.path)
