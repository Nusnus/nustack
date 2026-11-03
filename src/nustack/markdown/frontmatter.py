"""The YAML block that opens a `SKILL.md`, held to the lines every host reads alike.

The block is found, stripped from the body a host shows, and read into one-line fields
and list entries, frozen all the way down. Any line or value a host might read
differently is refused with its fix, by line where it has one; a key that is not text,
an alias that contains itself, nesting too deep, a reused anchor and a character YAML
cannot read have no line of their own. The sync still reads a block whose close an edit
broke.
"""

import re
from dataclasses import dataclass
from functools import cached_property
from typing import ClassVar
lazy from collections.abc import Iterator

from nustack.yaml_reader import YamlError
from nustack.yaml_reader import YamlInvalidError
from nustack.yaml_reader import YamlUnhashableKeyError
from nustack.yaml_reader import YamlValue
from nustack.yaml_reader import read_yaml
from nustack.yaml_reader import yaml_values


class InvalidFrontmatterError(ValueError):
    """Frontmatter that nustack refuses, with each reason and its fix."""

    def __init__(self, *reasons: str) -> None:
        super().__init__(*reasons)
        self.reasons = reasons


@dataclass(frozen=True)
class FrontmatterBlock:
    """The text between a file's opening `---` line and the next one.

    A file's first line is `---`, so the block's first line is the file's line 2.
    """

    FIRST_LINE: ClassVar[int] = 2
    OPENING: ClassVar[re.Pattern[str]] = re.compile(
        r"\A---\r?\n(.*?)^---(?:\r?\n|\Z)", re.DOTALL | re.MULTILINE
    )
    FIELD_OR_ENTRY: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:[A-Za-z][\w-]*:(?: [^\r\n]*)?| *- [^\r\n]+)\r?"
    )
    LINE_SEPARATOR: ClassVar[re.Pattern[str]] = re.compile("[\x85\u2028\u2029]")
    text: str

    @cached_property
    def fields(self) -> frozendict[str, object]:
        self.refuse_ambiguous_lines()
        data = self.load()
        self.refuse_ambiguous_values()
        self.refuse_unreadable_shapes(data)
        match data:
            case None:
                return frozendict()
            case dict():
                return frozen(data)
            case _:
                msg = (
                    "it is a list, not key: value fields;"
                    " write each field as key: value"
                )
                raise InvalidFrontmatterError(msg)

    @classmethod
    def of(cls, file_text: str) -> FrontmatterBlock | None:
        match = cls.OPENING.prefixmatch(file_text)
        if match is not None:
            return cls(match.group(1))
        if file_text.partition("\n")[0].removesuffix("\r") == "---":
            msg = "it opens with --- and never closes; end it with a --- line"
            raise InvalidFrontmatterError(msg)
        return None

    @classmethod
    def body_of(cls, file_text: str) -> str:
        return cls.OPENING.sub("", file_text)

    @classmethod
    def fenced_of(cls, file_text: str) -> str:
        if match := cls.OPENING.prefixmatch(file_text):
            return match.group(0)
        return (
            file_text
            if file_text.partition("\n")[0].removesuffix("\r") == "---"
            else ""
        )

    def refuse_ambiguous_lines(self) -> None:
        lines = self.text.split("\n")[:-1]
        if reasons := [
            reason
            for number, line in enumerate(lines, start=self.FIRST_LINE)
            for reason in self.line_reasons(number, line)
        ]:
            raise InvalidFrontmatterError(*reasons)

    def line_reasons(self, number: int, line: str) -> Iterator[str]:
        # Some hosts end frontmatter at the first --- anywhere, which drops the
        # fields after it: https://github.com/anthropics/claude-code/issues/103059
        if "---" in line:
            yield (
                f"line {number} holds ---, which some hosts read as the end of the"
                " frontmatter; reword it"
            )
        # Hosts read directives, markers and wrapped values differently, and one
        # then drops every field: https://github.com/anthropics/claude-code/issues/94301
        if not self.FIELD_OR_ENTRY.fullmatch(line):
            yield (
                f"line {number} is not a field (a key that starts with a letter,"
                " then a colon, and a space before any value) or a list entry"
                " (spaces, then a dash and a space), the only lines nustack"
                " accepts; put each field on one line, and delete any other line"
            )
        # YAML 1.1 reads these as line breaks and YAML 1.2 as text, so readers
        # disagree: https://yaml.org/spec/1.2.2/#54-line-break-characters
        if self.LINE_SEPARATOR.search(line):
            yield (
                f"line {number} holds a Unicode line or paragraph separator, which"
                " hosts read differently and most editors hide; delete it"
            )

    def load(self) -> object:
        try:
            return read_yaml(self.text)
        except YamlError as error:
            # YAML 1.2 lets a tab sit in a plain value, but ruamel refuses one:
            # https://yaml.org/spec/1.2.2/#733-plain-style
            if (
                isinstance(error, YamlInvalidError)
                and "\t" in self.text.split("\n")[error.line]
            ):
                where = YamlInvalidError.WHERE.format(
                    line=error.line_from(self.FIRST_LINE)
                )
                msg = (
                    f"{where}, which holds a tab outside quotes; replace the tab with"
                    " a space, or quote the value"
                )
                raise InvalidFrontmatterError(msg) from error
            raise InvalidFrontmatterError(error.reason(self.FIRST_LINE)) from error

    def refuse_ambiguous_values(self) -> None:
        if reasons := [
            reason
            for value in yaml_values(self.text)
            for reason in self.value_reasons(value)
        ]:
            raise InvalidFrontmatterError(*reasons)

    def value_reasons(self, value: YamlValue) -> Iterator[str]:
        number = value.start_line + self.FIRST_LINE
        if value.block:
            yield (
                f"line {number} opens a | or > block value; write the value on"
                " that line, after its key"
            )
        elif value.start_line != value.end_line:
            yield f"line {number} wraps a value onto the next line; put it on one line"
        # YAML needs a space before a comment, so Bun refuses a # right after a
        # quote or bracket, which other readers take as a comment or as part of
        # the value: https://yaml.org/spec/1.2.2/#66-comments
        if self.text.startswith("#", value.end_index):
            yield (
                f"line {value.end_line + self.FIRST_LINE} has a # right after a"
                " quote or bracket, which some hosts refuse; put a space before the #"
            )

    @classmethod
    def refuse_unreadable_shapes(cls, data: object) -> None:
        done: set[int] = set()
        entered: set[int] = set()
        pending: list[tuple[object, bool]] = [(data, False)]
        while pending:
            item, leaving = pending.pop()
            if leaving:
                done.add(id(item))
            elif isinstance(item, dict | list) and id(item) not in done:
                if id(item) in entered:
                    msg = "it holds an alias that contains itself; remove the loop"
                    raise InvalidFrontmatterError(msg)
                if isinstance(item, dict) and not all(
                    isinstance(key, str) for key in item
                ):
                    raise InvalidFrontmatterError(YamlUnhashableKeyError.REASON)
                entered.add(id(item))
                pending.append((item, True))
                children = item.values() if isinstance(item, dict) else item
                pending.extend((child, False) for child in reversed(list(children)))


def frozen(fields: dict[str, object]) -> frozendict[str, object]:
    order: list[dict[object, object] | list[object]] = []
    entered: set[int] = set()
    pending: list[tuple[object, bool]] = [(child, False) for child in fields.values()]
    while pending:
        item, leaving = pending.pop()
        if not isinstance(item, dict | list):
            continue
        if leaving:
            order.append(item)
        elif id(item) not in entered:
            entered.add(id(item))
            pending.append((item, True))
            children = item.values() if isinstance(item, dict) else item
            pending.extend((child, False) for child in children)
    made: dict[int, object] = {}
    for item in order:
        made[id(item)] = (
            frozendict((key, made.get(id(child), child)) for key, child in item.items())
            if isinstance(item, dict)
            else tuple(made.get(id(child), child) for child in item)
        )
    return frozendict(
        (key, made.get(id(child), child)) for key, child in fields.items()
    )
