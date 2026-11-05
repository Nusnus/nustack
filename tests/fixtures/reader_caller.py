"""A caller of the YAML reader, for the tests of where its warnings land."""

import inspect
import warnings
from dataclasses import dataclass
lazy from collections.abc import Callable

from nustack import yaml_reader
from nustack.yaml_reader import read_yaml


@dataclass(frozen=True)
class Caller:
    """A reader, called from one line of the caller's, keeping each warning it raised.

    deeper's reader stands in for one more frame of the reader's between the caller
    and the warning, since it is compiled as part of the reader's file.
    """

    reader: Callable[[str], object]

    @classmethod
    def deeper(cls) -> Caller:
        found: dict[str, Callable[[str], object]] = {}
        exec(  # noqa: S102 -- a fixed function in the reader's file, no outside input
            compile(
                "def deeper(text):\n    return read_yaml(text)\n",
                yaml_reader.__file__,
                "exec",
            ),
            {"read_yaml": read_yaml},
            found,
        )
        return cls(found["deeper"])

    def read(self, text: str) -> tuple[int, list[warnings.WarningMessage]]:
        with warnings.catch_warnings(record=True) as heard:
            warnings.simplefilter("always")
            line = inspect.stack()[0].lineno + 1
            self.reader(text)
        return line, heard
