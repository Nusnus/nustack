"""What changed in one copied file, as a reviewer's evidence and never a verdict.

That is its line edits, whether its frontmatter and its mode changed and so how
hosts load it, the outside links it adds, and the added lines a reviewer should
read, those naming a rule, an invocation field, a command or a URL. Text that is
not UTF-8 is left for review, never counted as unchanged.
"""

import posixpath
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import ClassVar
from typing import Literal
from urllib.parse import urlsplit

from nustack.markdown.document import Document
from nustack.markdown.document import local_path
from nustack.markdown.frontmatter import FrontmatterBlock
from nustack.plugin.skill import Skill
lazy from nustack.sync.tree import Mode


@dataclass(frozen=True)
class Blob:
    """The bytes and mode that a checked-out file would have."""

    data: bytes
    mode: Mode


class Comparison(StrEnum):
    """How a part of a file compares across a change: binary when a side is not text."""

    CHANGED = "changed"
    UNCHANGED = "unchanged"
    BINARY = "binary"


@dataclass(frozen=True)
class Edit:
    """A removed or added line, numbered on its own side of the comparison."""

    side: Literal["+", "-"]
    number: int
    text: str


@dataclass(frozen=True)
class FileChange:
    """Compares one copied file's base and proposed blobs into a reviewer's evidence.

    A side is absent when the file is added or removed.
    """

    POLICIES: ClassVar[str] = "agents/"
    LOADING: ClassVar[str] = (
        r"disable-model-invocation|allow_implicit_invocation|triggers"
    )
    LOADING_FIELD: ClassVar[re.Pattern[str]] = re.compile(rf"\b(?:{LOADING})\b")
    MARKERS: ClassVar[re.Pattern[str]] = re.compile(
        rf"\b(?:AGENTS\.md|CLAUDE\.md|REVIEW\.md|nus-mode|nustack|{LOADING}|"
        r"git (?:push|commit)|curl|sudo)\b|\bhttps?://",
        re.IGNORECASE,
    )
    LINE: ClassVar[re.Pattern[str]] = re.compile(r"[^\n]*\n|[^\n]+\Z")
    path: str
    before: Blob | None
    after: Blob | None

    @property
    def status(self) -> Literal["added", "removed", "changed"]:
        if self.before is None:
            return "added"
        if self.after is None:
            return "removed"
        return "changed"

    @property
    def modes(self) -> str:
        match self.before, self.after:
            case Blob(mode=before), Blob(mode=after) if before != after:
                return f", mode {before} to {after}"
            case None, Blob(mode=after) if after != Mode.REGULAR:
                return f", mode {after}"
            case _:
                return ""

    @cached_property
    def texts(self) -> tuple[Document, Document] | None:
        old = self.before.data if self.before else b""
        new = self.after.data if self.after else b""
        if b"\0" in old or b"\0" in new:
            return None
        try:
            return Document(Path(self.path), old.decode()), Document(
                Path(self.path), new.decode()
            )
        except UnicodeDecodeError:
            return None

    @cached_property
    def frontmatter_comparison(self) -> Comparison:
        if self.texts is None:
            return Comparison.BINARY
        old, new = self.texts
        same = FrontmatterBlock.fenced_of(old.text) == FrontmatterBlock.fenced_of(
            new.text
        )
        return Comparison.UNCHANGED if same else Comparison.CHANGED

    @cached_property
    def outside_links(self) -> tuple[tuple[str, int], ...]:
        if self.texts is None:
            return ()
        old, new = self.texts
        added = Counter(new.every_href) - Counter(old.every_href)
        return tuple(
            (href, count) for href, count in sorted(added.items()) if self.leaves(href)
        )

    @cached_property
    def edits(self) -> tuple[Edit, ...]:
        if self.texts is None:
            return ()
        old, new = (self.lines_of(text.text) for text in self.texts)
        edits: list[Edit] = []
        matcher = SequenceMatcher(a=old, b=new, autojunk=False)
        for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
            if tag != "equal":
                edits.extend(
                    Edit("-", number, line.rstrip("\r\n"))
                    for number, line in enumerate(old[old_start:old_end], old_start + 1)
                )
                edits.extend(
                    Edit("+", number, line.rstrip("\r\n"))
                    for number, line in enumerate(new[new_start:new_end], new_start + 1)
                )
        return tuple(edits)

    @property
    def policy(self) -> bool:
        return self.path.startswith(self.POLICIES)

    @cached_property
    def loading_lines(self) -> tuple[Edit, ...]:
        if self.texts is None:
            return ()
        headers = {
            side: len(self.lines_of(FrontmatterBlock.fenced_of(text.text)))
            for side, text in zip(("-", "+"), self.texts, strict=True)
        }
        return tuple(
            line
            for line in self.edits
            if self.policy
            or (self.path == Skill.FILE and line.number <= headers[line.side])
        )

    @property
    def loading(self) -> Comparison:
        if self.texts is None:
            return Comparison.BINARY
        changed = any(
            self.LOADING_FIELD.search(line.text) for line in self.loading_lines
        )
        return Comparison.CHANGED if changed else Comparison.UNCHANGED

    @cached_property
    def marked_lines(self) -> tuple[Edit, ...]:
        loading = frozenset(self.loading_lines)
        return tuple(
            line
            for line in self.edits
            if line in loading or (line.side == "+" and self.MARKERS.search(line.text))
        )

    def leaves(self, href: str) -> bool:
        path = local_path(urlsplit(href))
        if path is None or posixpath.isabs(path):
            return True
        target = posixpath.normpath(posixpath.join(posixpath.dirname(self.path), path))
        return target == ".." or target.startswith("../")

    @classmethod
    def lines_of(cls, text: str) -> tuple[str, ...]:
        return tuple(cls.LINE.findall(text))
