"""The tables of a document's body, read from the tokens its parser gives.

Only a table that renders counts, so one in a fenced block or an HTML comment holds
no rows, and an escaped pipe reads as part of its cell's text. Each row holds the
body line it starts on, counted from 0, and each cell its text and its first link.
"""

from dataclasses import dataclass
from functools import cached_property
from itertools import accumulate
from typing import ClassVar

lazy from markdown_it.token import Token

from nustack.markdown.document import Document
from nustack.markdown.document import Lines


@dataclass(frozen=True)
class Cell:
    """A cell's text as it renders, and its first link's target and text."""

    text: str
    href: str | None
    label: str | None


@dataclass(frozen=True)
class Row:
    """A table body row's line below any frontmatter, counted from 0, and its cells."""

    line: int
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class Table:
    """A table's header cells and its body rows."""

    header: tuple[Cell, ...]
    body: tuple[Row, ...]


@dataclass(frozen=True)
class Tables:
    """Every table in a document's body, in the order they appear."""

    # The inline tokens whose content shows as text: an image's content holds the
    # source of the alt text it shows, and markup such as emphasis or raw HTML shows
    # none of its own.
    PLAIN: ClassVar[frozenset[str]] = frozenset({"text", "code_inline", "image"})
    document: Document

    @cached_property
    def tables(self) -> tuple[Table, ...]:
        tables: list[list[Row]] = []
        opens = ""
        for token in self.document.tokens:
            if token.type == "table_open":
                tables.append([])
            elif token.type == "tr_open":
                start, _ = Lines.span(token)
                tables[-1].append(Row(start, ()))
            elif opens in {"th_open", "td_open"}:
                row = tables[-1][-1]
                tables[-1][-1] = Row(row.line, (*row.cells, self.cell(token)))
            opens = token.type
        return tuple(Table(header.cells, tuple(body)) for header, *body in tables)

    @classmethod
    def cell(cls, inline: Token) -> Cell:
        children = inline.children or []
        opens = [
            index for index, child in enumerate(children) if child.type == "link_open"
        ]
        if not opens:
            return Cell(Document.inline_text(children, cls.PLAIN), None, None)
        start = opens[0]
        # An autolink in a link's text opens a link inside it, so the first link ends
        # at the close that brings the depth back to 0.
        depths = accumulate(
            {"link_open": 1, "link_close": -1}.get(child.type, 0)
            for child in children[start:]
        )
        end = start + next(offset for offset, depth in enumerate(depths) if depth == 0)
        return Cell(
            Document.inline_text(children, cls.PLAIN),
            str(children[start].attrs["href"]),
            Document.inline_text(children[start + 1 : end], cls.PLAIN),
        )
