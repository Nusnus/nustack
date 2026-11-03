"""YAML read safely into plain data and into values that know where they sit.

Every refusal, from a tag it cannot build to a repeated key, a reused anchor or a
nesting too deep, is an error of the reader's own, with the line where one applies.
"""

import warnings
from contextlib import contextmanager
from dataclasses import dataclass
lazy from collections.abc import Generator
lazy from collections.abc import Iterator

from ruamel.yaml import YAML
from ruamel.yaml import YAMLError
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import MarkedYAMLError
from ruamel.yaml.error import ReusedAnchorWarning
from ruamel.yaml.nodes import CollectionNode
from ruamel.yaml.nodes import MappingNode
from ruamel.yaml.nodes import Node
from ruamel.yaml.nodes import ScalarNode


class YamlError(ValueError):
    """YAML the reader refuses: a value it cannot build, or a reason below."""


class YamlAnchorReusedError(YamlError):
    """YAML that gives two anchors one name."""


class YamlNestingError(YamlError):
    """YAML that nests too deeply to read."""


class YamlUnhashableKeyError(YamlError):
    """YAML with a key that no mapping can hold, such as a list."""


class YamlLineError(YamlError):
    """YAML refused at one line of the text, counted from 0."""

    def __init__(self, line: int) -> None:
        self.line = line


class YamlDuplicateKeyError(YamlLineError):
    """YAML that repeats a key in one mapping."""


class YamlInvalidError(YamlLineError):
    """YAML that does not parse, or names a tag the reader cannot build."""


@dataclass(frozen=True)
class YamlValue:
    """A scalar or flow collection, by where it sits in the text.

    Lines count from 0, and `end_index` is the character just after the value.
    """

    start_line: int
    end_line: int
    end_index: int
    block: bool


def read_yaml(text: str | bytes) -> object:
    with translated_errors():
        return yaml_loader().load(text)


def yaml_values(text: str) -> Iterator[YamlValue]:
    with translated_errors():
        root = yaml_loader().compose(text)
    pending: list[Node] = [] if root is None else [root]
    seen: set[int] = set()
    while pending:
        node = pending.pop()
        if id(node) not in seen:
            seen.add(id(node))
            match node:
                case ScalarNode() | CollectionNode(flow_style=True):
                    yield placed_value(node)
                case MappingNode():
                    pending.extend(
                        reversed([part for pair in node.value for part in pair])
                    )
                case _:
                    pending.extend(reversed(node.value))


# `pure=True` keeps ruamel on its Python parser. uv.lock holds no
# ruamel.yaml.clib, so ruamel takes that parser anyway and no input tells the
# argument from its default.
def yaml_loader() -> YAML:
    return YAML(
        typ="safe",
        pure=True,  # pragma: no mutate
    )


def placed_value(node: Node) -> YamlValue:
    return YamlValue(
        start_line=node.start_mark.line,
        end_line=node.end_mark.line,
        end_index=node.end_mark.index,
        block=isinstance(node, ScalarNode) and node.style in {"|", ">"},
    )


@contextmanager
def translated_errors() -> Generator[None]:
    try:
        with warnings.catch_warnings():
            # The suite fails on every warning, so no test tells this filter
            # from one that raises them all.
            warnings.simplefilter("error", ReusedAnchorWarning)  # pragma: no mutate
            yield
    except ReusedAnchorWarning as error:
        raise YamlAnchorReusedError from error
    except DuplicateKeyError as error:
        raise YamlDuplicateKeyError(error.problem_mark.line) from error
    except MarkedYAMLError as error:
        raise YamlInvalidError(error.problem_mark.line) from error
    except RecursionError as error:
        raise YamlNestingError from error
    except TypeError as error:
        raise YamlUnhashableKeyError from error
    except (YAMLError, ValueError, LookupError, OverflowError) as error:
        raise YamlError from error
