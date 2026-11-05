"""A commit's SHA, as Git and GitHub write it.

A name Git or GitHub gives a commit that is not its SHA-1 is refused; the caller names
where it came from. A SHA given as text that is not one is refused with the fix.
"""

import re
from dataclasses import dataclass

from nustack.validation import Pattern


class ShaError(ValueError):
    """Text given as a commit's SHA that is not one."""


class NotSha1Error(ValueError):
    """A commit named by other than its SHA-1, the name nustack reads it by."""

    def __init__(self) -> None:
        super().__init__(
            "named a commit by other than its SHA-1; nustack reads only repositories"
            " whose commits Git names by SHA-1, so use one"
        )


@dataclass(frozen=True)
class Sha:
    """A commit's SHA-1, as Git and GitHub write it."""

    value: str

    @property
    def short(self) -> str:
        # GitHub shows a commit by the first 7 digits of its SHA.
        return self.value[:7]

    @classmethod
    def parse(cls, value: str) -> Sha:
        try:
            return cls(value)
        except NotSha1Error:
            message = f"give the commit as its SHA, not {value}; {Pattern.SHA.fix}"
            raise ShaError(message) from None

    def __post_init__(self) -> None:
        if not re.fullmatch(Pattern.SHA, self.value):
            raise NotSha1Error

    def __str__(self) -> str:
        return self.value
