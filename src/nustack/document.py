"""Reading the Markdown that skills, playbooks and the changelog are written in."""

import re
import warnings
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any
from typing import ClassVar
from typing import NamedTuple
from typing import TypedDict
from urllib.parse import unquote
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from ruamel.yaml import YAML
from ruamel.yaml import YAMLError
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import MarkedYAMLError
from ruamel.yaml.error import ReusedAnchorWarning
from ruamel.yaml.nodes import CollectionNode
from ruamel.yaml.nodes import MappingNode
from ruamel.yaml.nodes import ScalarNode

from nustack.problem import Problem
from nustack.problem import cannot_read

FIRST_HEADER_LINE = 2


class InvalidFrontmatterError(ValueError):
    """Frontmatter that nustack refuses, with the reason and the fix."""


class Reference(TypedDict):
    """A link reference definition, as the Markdown parser holds it."""

    href: str
    title: str


class Section(NamedTuple):
    """A second-level heading's title, and the text under it up to the next one."""

    title: str
    body: str


@dataclass
class Document:
    """A Markdown file: its frontmatter, its sections and its relative links."""

    FRONTMATTER: ClassVar[re.Pattern[str]] = re.compile(
        r"\A---\r?\n(.*?)^---(?:\r?\n|\Z)", re.DOTALL | re.MULTILINE
    )
    LINE: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:[A-Za-z][\w-]*:(?: [^\r\n]*)?| *- [^\r\n]+)\r?"
    )
    MARKDOWN: ClassVar[MarkdownIt] = MarkdownIt("commonmark")
    path: Path

    @cached_property
    def text(self) -> str:
        return self.path.read_text(encoding="utf-8", newline="")

    @cached_property
    def unreadable(self) -> str | None:
        try:
            self.path.read_bytes().decode("utf-8")
        except OSError as error:
            return cannot_read(error)
        except UnicodeDecodeError:
            return "is not valid UTF-8; save it as UTF-8"
        return None

    @cached_property
    def body(self) -> str:
        return self.FRONTMATTER.sub("", self.text, count=1)

    @cached_property
    def frontmatter(self) -> dict[str, object] | None:
        match = self.FRONTMATTER.prefixmatch(self.text)
        if match is None:
            if self.text.partition("\n")[0].rstrip("\r") == "---":
                msg = "it opens with --- and never closes; end it with a --- line"
                raise InvalidFrontmatterError(msg)
            return None
        header = match.group(1)
        # Some hosts end frontmatter at the first --- anywhere, which drops the
        # fields after it: https://github.com/anthropics/claude-code/issues/103059
        if (index := header.find("---")) != -1:
            msg = (
                f"line {line_at(header, index)} holds ---, which some hosts read as"
                " the end of the frontmatter; reword it"
            )
            raise InvalidFrontmatterError(msg)
        # Hosts read directives, markers and wrapped values differently, and one
        # then drops every field, so each field and list entry keeps to one line:
        # https://github.com/anthropics/claude-code/issues/94301
        for number, line in enumerate(header.split("\n")[:-1], start=FIRST_HEADER_LINE):
            if not self.LINE.fullmatch(line):
                msg = (
                    f"line {number} is not a field (a key that starts with a letter,"
                    " then a colon, and a space before any value) or a list entry"
                    " (spaces, then a dash and a space), the only lines nustack"
                    " accepts; put each field on one line, and delete any other line"
                )
                raise InvalidFrontmatterError(msg)
        # YAML 1.1 reads these as line breaks and YAML 1.2 as text, so readers
        # disagree: https://yaml.org/spec/1.2.2/#54-line-break-characters
        if found := re.search("[\x85\u2028\u2029]", header):
            msg = (
                f"line {line_at(header, found.start())} holds a Unicode line or"
                " paragraph separator, which hosts read differently and most"
                " editors hide; delete it"
            )
            raise InvalidFrontmatterError(msg)
        data = read_yaml(header)
        if (reason := value_problem(header)) is not None:
            raise InvalidFrontmatterError(reason)
        check_shape(data)
        # The line rule lets through only fields and list entries, so what is not
        # a mapping here is a list.
        if not isinstance(data, dict | None):
            msg = "it is a list, not key: value fields; write each field as key: value"
            raise InvalidFrontmatterError(msg)
        return {} if data is None else data

    @cached_property
    def sections(self) -> list[Section]:
        tokens = self.MARKDOWN.parse(self.body)
        headings = [
            (tokens[index + 1].content, token.map or [0, 0])
            for index, token in enumerate(tokens)
            if token.type == "heading_open" and token.tag == "h2" and token.level == 0
        ]
        lines = lines_of(self.body)
        ends = [*(start for _, (start, _) in headings[1:]), len(lines)]
        return [
            Section(title, "".join(lines[body_start:end]).strip("\n"))
            for (title, (_, body_start)), end in zip(headings, ends, strict=False)
        ]

    @cached_property
    def references(self) -> frozendict[str, Reference]:
        env: dict[str, Any] = {}
        self.MARKDOWN.parse(self.body, env)
        return frozendict(env.get("references", {}))

    @cached_property
    def hrefs(self) -> list[str]:
        return [
            str(child.attrs["href" if child.type == "link_open" else "src"])
            for token in self.MARKDOWN.parse(self.body)
            for child in token.children or []
            if child.type in {"link_open", "image"}
        ]

    @cached_property
    def malformed(self) -> list[str]:
        return [href for href in self.hrefs if not self.parses(href)]

    @cached_property
    def targets(self) -> frozenset[Path]:
        return frozenset(
            target
            for href in self.hrefs
            if href not in self.malformed and (target := self.target(href)) is not None
        )

    def link_problems(self, root: Path) -> list[Problem]:
        return [
            *(
                Problem(
                    self.path,
                    f"has a malformed link {href!r}; "
                    "write it as a full URL or a path to a file",
                )
                for href in self.malformed
            ),
            *(
                Problem(
                    self.path,
                    f"links to {target}, which is not a file inside {root}; "
                    "link to a file inside it, or to a full URL",
                )
                for target in sorted(self.targets)
                if not target.is_file() or not target.is_relative_to(root.resolve())
            ),
        ]

    def parses(self, href: str) -> bool:
        try:
            self.target(href)
        except ValueError:
            return False
        return True

    def target(self, href: str) -> Path | None:
        link = urlsplit(href)
        if link.scheme or link.netloc or not link.path:
            return None
        return (self.path.parent / unquote(link.path)).resolve()

    def stands_alone(self, text: str) -> bool:
        inside = self.MARKDOWN.render(text, {"references": dict(self.references)})
        return inside == self.MARKDOWN.render(text)


def read_yaml(header: str) -> object:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", ReusedAnchorWarning)
            data = YAML(typ="safe", pure=True).load(header)
    except ReusedAnchorWarning as error:
        msg = "it reuses an anchor name; give each anchor its own name"
        raise InvalidFrontmatterError(msg) from error
    except DuplicateKeyError as error:
        msg = f"it repeats a key{on_line(error)}; keep one"
        raise InvalidFrontmatterError(msg) from error
    except MarkedYAMLError as error:
        msg = f"it is not valid YAML{on_line(error)}; fix it"
        raise InvalidFrontmatterError(msg) from error
    except RecursionError as error:
        msg = "it nests too deeply to read; flatten it"
        raise InvalidFrontmatterError(msg) from error
    except TypeError as error:
        msg = "it holds a key that is not text; write each key as plain text"
        raise InvalidFrontmatterError(msg) from error
    except (YAMLError, ValueError, LookupError) as error:
        msg = (
            "it holds a value YAML cannot read; quote it, fix or remove its tag, "
            "or delete any control character"
        )
        raise InvalidFrontmatterError(msg) from error
    return data


def check_shape(data: object) -> None:
    reason = shape_problem(data)
    if reason is not None:
        raise InvalidFrontmatterError(reason)


def shape_problem(data: object) -> str | None:
    done: set[int] = set()
    entered: set[int] = set()
    pending: list[tuple[object, bool]] = [(data, False)]
    while pending:
        item, leaving = pending.pop()
        if leaving:
            done.add(id(item))
            continue
        if isinstance(item, bytes):
            return "it holds binary data; write it as text"
        if not isinstance(item, dict | list) or id(item) in done:
            continue
        if id(item) in entered:
            return "it holds an alias that contains itself; remove the loop"
        if isinstance(item, dict) and not all(isinstance(key, str) for key in item):
            return "it holds a key that is not text; write each key as plain text"
        entered.add(id(item))
        pending.append((item, True))
        children = item.values() if isinstance(item, dict) else item
        pending.extend((child, False) for child in reversed(list(children)))
    return None


def value_problem(header: str) -> str | None:
    nodes = [YAML(typ="safe", pure=True).compose(header)]
    seen: set[int] = set()
    while nodes:
        node = nodes.pop()
        if node is None or id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, ScalarNode) or (
            isinstance(node, CollectionNode) and node.flow_style
        ):
            number = node.start_mark.line + FIRST_HEADER_LINE
            if isinstance(node, ScalarNode) and node.style in {"|", ">"}:
                return (
                    f"line {number} opens a | or > block value; write the value on"
                    " that line, after its key"
                )
            # A wrapped value's next line can look like a field of its own.
            if node.start_mark.line != node.end_mark.line:
                return (
                    f"line {number} wraps a value onto the next line; put it on one"
                    " line"
                )
            # YAML needs a space before a comment, so Bun refuses a # right after a
            # quote or bracket, which other readers take as a comment or as part of
            # the value: https://yaml.org/spec/1.2.2/#66-comments
            if header.startswith("#", node.end_mark.index):
                return (
                    f"line {number} has a # right after a quote or bracket, which"
                    " some hosts refuse; put a space before the #"
                )
        elif isinstance(node, MappingNode):
            nodes.extend(reversed([part for pair in node.value for part in pair]))
        else:
            nodes.extend(reversed(node.value))
    return None


def line_at(header: str, index: int) -> int:
    return header.count("\n", 0, index) + FIRST_HEADER_LINE


def on_line(error: MarkedYAMLError) -> str:
    mark = error.problem_mark
    return "" if mark is None else f" on line {mark.line + FIRST_HEADER_LINE}"


def lines_of(text: str) -> list[str]:
    return re.findall(r".*?(?:\r\n|\r|\n)|.+\Z", text, re.DOTALL)
