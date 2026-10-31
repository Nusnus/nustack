"""How every check reports what it finds."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Problem:
    """One place that breaks one rule, and how it breaks it."""

    where: Path
    what: str

    def __str__(self) -> str:
        return f"{self.where}: {self.what}"


def cannot_read(error: OSError) -> str:
    return f"cannot be read ({error.strerror}); make it readable"


def cannot_open(error: OSError) -> str:
    return (
        f"cannot be opened ({error.strerror}); "
        "give the folder read and execute permission"
    )
