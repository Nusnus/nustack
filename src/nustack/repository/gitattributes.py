"""`.gitattributes`, down to the lines that set attributes.

Git skips blank lines and comments, and splits each line on whitespace:
https://git-scm.com/docs/gitattributes#_description
"""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import ClassVar
from typing import Self


@dataclass(frozen=True)
class GitAttributes:
    """`.gitattributes`, by its lines that set attributes, each with single spaces."""

    PATH: ClassVar[PurePosixPath] = PurePosixPath(".gitattributes")
    lines: tuple[str, ...]

    @classmethod
    def parse(cls, content: bytes) -> Self:
        return cls(
            tuple(
                " ".join(fields)
                for line in content.decode().splitlines()
                if (fields := line.split()) and not fields[0].startswith("#")
            )
        )
