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
    TOO_DEEP: ClassVar[str] = "nests too deeply to read; flatten it"
    where: Path
    what: str

    def __str__(self) -> str:
        return f"{self.where}: {self.what}"
