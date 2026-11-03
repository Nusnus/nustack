"""What every check reports: one place that breaks one rule, and the fix.

A Problem reads the same in every check's output.
"""

from dataclasses import dataclass
from typing import ClassVar
lazy from pathlib import Path


@dataclass(frozen=True)
class Problem:
    """One place that breaks one rule, and how it breaks it."""

    NOT_UTF8: ClassVar[str] = "is not valid UTF-8; save it as UTF-8"
    NOT_A_FOLDER: ClassVar[str] = "is not a folder, so the check stops here"
    NUMBER_TOO_LONG: ClassVar[str] = "holds a number too long to read"
    TOO_DEEP: ClassVar[str] = "nests too deeply to read; flatten it"
    where: Path | str
    what: str

    def __str__(self) -> str:
        return f"{self.where}: {self.what}"
