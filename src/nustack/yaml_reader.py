"""YAML read safely into plain data and into values that know where they sit.

The reader builds only the core schema's tags, plus merge keys, and reads an untagged
value by the document's %YAML version, so a date reads as text. Every refusal, from a
tag outside that schema, a %YAML version other than 1.1 or 1.2 or a value it cannot
build to a repeated key, a reused anchor or a nesting too deep, is an error of the
reader's own, with the line where one applies. A YAML 1.1 float with no dot in its
mantissa earns the reader's own warning, naming its line and the fix.
"""

import contextlib
import sys
import warnings
from dataclasses import dataclass
from typing import ClassVar
lazy import re
lazy from collections.abc import Generator
lazy from collections.abc import Iterator

from ruamel.yaml import YAML
from ruamel.yaml import YAMLError
from ruamel.yaml.constructor import ConstructorError
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.constructor import SafeConstructor
from ruamel.yaml.error import MantissaNoDotYAML1_1Warning
from ruamel.yaml.error import MarkedYAMLError
from ruamel.yaml.error import ReusedAnchorWarning
from ruamel.yaml.error import YAMLWarning
from ruamel.yaml.nodes import CollectionNode
from ruamel.yaml.nodes import MappingNode
from ruamel.yaml.nodes import Node
from ruamel.yaml.nodes import ScalarNode
from ruamel.yaml.resolver import VersionedResolver
from ruamel.yaml.scanner import Scanner
lazy from ruamel.yaml.tokens import DirectiveToken

from nustack.problem import Problem


class YamlError(ValueError):
    """YAML the reader refuses for a reason below, or for a character it cannot read."""

    REASON: ClassVar[str] = (
        "it holds a character YAML cannot read; delete any control character, or"
        " fix the escape that writes one"
    )

    def reason(self, first_line: int) -> str:  # noqa: ARG002 -- a line error reads it
        return self.REASON


class YamlAnchorReusedError(YamlError):
    """YAML that gives two anchors one name."""

    REASON: ClassVar[str] = "it reuses an anchor name; give each anchor its own name"


class YamlNestingError(YamlError):
    """YAML that nests too deeply to read."""

    REASON: ClassVar[str] = f"it {Problem.TOO_DEEP}"


class YamlUnhashableKeyError(YamlError):
    """YAML with a key that no mapping can hold, such as a mapping."""

    REASON: ClassVar[str] = (
        "it holds a key that is not text; write each key as plain text"
    )


class YamlLineError(YamlError):
    """YAML refused at one line of the text, counted from 0."""

    def __init__(self, line: int) -> None:
        self.line = line

    def reason(self, first_line: int) -> str:
        return self.REASON.format(line=self.line_from(first_line))

    def line_from(self, first_line: int) -> int:
        return self.line + first_line


class YamlDuplicateKeyError(YamlLineError):
    """YAML that repeats a key in one mapping."""

    REASON: ClassVar[str] = "it repeats a key on line {line}; keep one"


class YamlInvalidError(YamlLineError):
    """YAML that does not parse."""

    WHERE: ClassVar[str] = "it is not valid YAML on line {line}"
    REASON: ClassVar[str] = f"{WHERE}; fix it"


class YamlNumberTooLongError(YamlLineError):
    """YAML holding an integer with more digits than Python converts from text."""

    REASON: ClassVar[str] = f"it {Problem.NUMBER_TOO_LONG} on line {{line}}; shorten it"


class YamlTagError(YamlLineError):
    """YAML that names a tag outside the core schema, such as !!binary or !!set."""

    REASON: ClassVar[str] = (
        "it uses a tag on line {line} that nustack does not read; remove the tag"
    )


class YamlUnbuildableError(YamlLineError):
    """YAML holding a value it cannot build as its type, such as !!str on a list."""

    REASON: ClassVar[str] = (
        "it holds a value on line {line} that YAML cannot build as its type; fix the"
        " value, or remove its tag or merge key"
    )


class YamlVersionError(YamlLineError):
    """YAML whose %YAML directive names a version other than 1.1 or 1.2."""

    REASON: ClassVar[str] = (
        "it names a YAML version other than 1.1 or 1.2 on line {line}; set it to 1.2"
    )


class YamlWarning(UserWarning):
    """YAML that reads but holds a YAML 1.1 float with no dot in its mantissa."""

    # ruamel counts lines from 0, where an editor counts from 1. Only YamlConfig, whose
    # YAML opens on its file's first line, can hear this warning: Frontmatter refuses
    # each line that is no field, %YAML among them, before it reads.
    FIRST_LINE: ClassVar[int] = 1

    @classmethod
    def mantissa_without_dot(cls, line: int, source: str | None) -> YamlWarning:
        where = f"line {line + cls.FIRST_LINE}"
        if source is not None:
            where = f"{where} of {source}"
        return cls(
            f"{where} holds a YAML 1.1 float with no dot in its mantissa; add one,"
            " such as 1.0e3, or declare %YAML 1.2"
        )


@dataclass(frozen=True)
class YamlValue:
    """A scalar or flow collection, by where it sits in the text.

    Lines count from 0, and `end_index` is the character just after the value.
    """

    start_line: int
    end_line: int
    end_index: int
    block: bool

    @classmethod
    def of(cls, node: Node) -> YamlValue:
        return cls(
            start_line=node.start_mark.line,
            end_line=node.end_mark.line,
            end_index=node.end_mark.index,
            block=isinstance(node, ScalarNode) and node.style in {"|", ">"},
        )


class CoreScanner(Scanner):
    """Refuses a %YAML version other than 1.1 or 1.2 by its directive's line."""

    # ruamel checks the version with assert, which raises AssertionError, and which
    # python -O drops.
    def scan_directive(self) -> DirectiveToken:
        token = super().scan_directive()
        if token.name == "YAML" and token.value not in {(1, 1), (1, 2)}:
            raise YamlVersionError(token.start_mark.line)
        return token


class CoreResolver(VersionedResolver):
    """Reads an untagged value as a core schema type or a merge key, never a date."""

    # https://yaml.org/spec/1.2.2/#103-core-schema
    TAG_FORMAT: ClassVar[str] = "tag:yaml.org,2002:{}"
    CORE_TAGS: ClassVar[frozenset[str]] = frozenset(
        map(TAG_FORMAT.format, ("null", "bool", "int", "float", "str", "seq", "map"))
    )
    # A merge key folds one mapping into another before anything is built.
    MERGE_TAG: ClassVar[str] = TAG_FORMAT.format("merge")

    def add_version_implicit_resolver(
        self, version: object, tag: str, regexp: re.Pattern[str], first: object
    ) -> None:
        if tag in self.CORE_TAGS or tag == self.MERGE_TAG:
            super().add_version_implicit_resolver(version, tag, regexp, first)


class CoreConstructor(SafeConstructor):
    """Builds the core schema's types, refusing by line other tags and bad values.

    A mapping used as a key is refused like a list holding a list, since no mapping
    can hold either.
    """

    # https://sourceforge.net/p/ruamel-yaml/code/ci/0.19.1/tree/constructor.py#l135
    def construct_object(self, node: Node, deep: bool = False) -> object:  # noqa: FBT001, FBT002 -- ruamel's signature
        if node.tag not in CoreResolver.CORE_TAGS:
            raise YamlTagError(node.start_mark.line)
        if isinstance(node, MappingNode) and any(
            isinstance(key, MappingNode) for key, _ in node.value
        ):
            raise YamlUnhashableKeyError
        try:
            return super().construct_object(node, deep)
        except YamlError:
            raise
        except (ValueError, LookupError) as error:
            if self.too_long(node):
                raise YamlNumberTooLongError(node.start_mark.line) from error
            raise YamlUnbuildableError(node.start_mark.line) from error

    # Python converts text of at most sys.get_int_max_str_digits() decimal digits to
    # an int, not counting underscores, and 0 sets no limit:
    # https://docs.python.org/3/library/stdtypes.html#int-max-str-digits
    # So a value is too long when it builds once each run of digits is cut to the
    # limit, which only an integer can, since no other type has the limit. Only a
    # scalar gets here: ruamel refuses a collection under a scalar's tag with its own
    # error.
    def too_long(self, node: Node) -> bool:
        limit = sys.get_int_max_str_digits()
        if not limit:
            return False
        cut = re.sub(rf"(\d{{{limit}}})\d+", r"\1", node.value.replace("_", ""))
        try:
            super().construct_object(ScalarNode(node.tag, cut))
        except ValueError, LookupError:
            return False
        return True


def read_yaml(text: str, source: str | None = None) -> object:
    with translated_errors(source):
        return yaml_loader().load(text)


def yaml_values(text: str) -> Iterator[YamlValue]:
    with translated_errors(None):
        root = yaml_loader().compose(text)
    pending: list[Node] = [] if root is None else [root]
    seen: set[int] = set()
    while pending:
        node = pending.pop()
        if id(node) not in seen:
            seen.add(id(node))
            match node:
                case ScalarNode() | CollectionNode(flow_style=True):
                    yield YamlValue.of(node)
                case MappingNode():
                    pending.extend(
                        reversed([part for pair in node.value for part in pair])
                    )
                # ruamel's Node is an open hierarchy, so no match over it is
                # exhaustive; the composer builds no node but a scalar, a mapping
                # or a sequence, and only a sequence is left.
                case _:
                    pending.extend(reversed(node.value))


# The scanner, resolver and constructor set below replace what `typ` picks, so it
# picks only the parser. The round-trip one differs in comments, which this scanner
# never yields, and in keeping a tag's handle, which the constructor resolves alike,
# so no input tells YAML(typ=None) from this. mutmut skips every mutant of a
# statement that spans a pragma's line, so this one also skips loader = None and the
# typ strings "XXsafeXX" and "SAFE", which every test kills, since ruamel raises
# NotImplementedError for a typ it does not know.
def yaml_loader() -> YAML:
    loader = YAML(typ="safe")  # pragma: no mutate
    loader.Scanner = CoreScanner
    loader.Resolver = CoreResolver
    loader.Constructor = CoreConstructor
    return loader


# A refusal stays the refusal even where warnings are errors, so each warning heard
# before it becomes a note on it if passing it on raises.
@contextlib.contextmanager
def translated_errors(source: str | None) -> Generator[None]:
    heard: list[warnings.WarningMessage] = []
    try:
        with refused_as_yaml(heard):
            yield
    except Exception as refusal:
        for each in heard:
            try:
                pass_on([each], source)
            except Warning as warning:
                refusal.add_note(f"{type(warning).__name__}: {warning}")
        raise
    pass_on(heard, source)


@contextlib.contextmanager
def refused_as_yaml(heard: list[warnings.WarningMessage]) -> Generator[None]:
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", YAMLWarning)
            warnings.simplefilter("error", ReusedAnchorWarning)
            try:
                yield
            finally:
                heard.extend(caught)
    except YamlError:
        raise
    except ReusedAnchorWarning as error:
        raise YamlAnchorReusedError from error
    except DuplicateKeyError as error:
        raise YamlDuplicateKeyError(error.problem_mark.line) from error
    except ConstructorError as error:
        raise YamlUnbuildableError(error.problem_mark.line) from error
    except MarkedYAMLError as error:
        # A block scalar whose later line is more indented than its first fails with
        # only a context mark, where ruamel's scan of the block's indentation stopped.
        mark = error.problem_mark or error.context_mark
        raise YamlInvalidError(mark.line) from error
    except RecursionError as error:
        raise YamlNestingError from error
    except TypeError as error:
        raise YamlUnhashableKeyError from error
    except (YAMLError, ValueError) as error:
        raise YamlError from error


# A YAML 1.1 float with no dot in its mantissa earns the reader's own warning, which
# names the line that called the reader, past every frame in this file and
# contextlib's, however many there are. Any other warning is not the reader's, so it
# passes on as the same warning, at its own line.
# https://docs.python.org/3/library/warnings.html#warnings.warn
def pass_on(heard: list[warnings.WarningMessage], source: str | None) -> None:
    for each in heard:
        if isinstance(each.message, MantissaNoDotYAML1_1Warning):
            warnings.warn(
                YamlWarning.mantissa_without_dot(
                    each.message.node.start_mark.line, source
                ),
                skip_file_prefixes=(__file__, contextlib.__file__),
            )
        else:
            # A WarningMessage holds the Warning instance, so warn_explicit passes on
            # that same warning and ignores the category it requires, which no test
            # can tell from any other. The pragma's line holds that argument alone,
            # so it also skips dropping it, which the test kills, since warn_explicit
            # requires it.
            # https://docs.python.org/3/library/warnings.html#warnings.warn_explicit
            warnings.warn_explicit(
                each.message,
                each.category,  # pragma: no mutate
                each.filename,
                each.lineno,
            )
