"""Upstream's history as the sync reads it, found by the files the workflow copies.

The copied revision is identified by those paths, and each commit is read from
Git's NUL-framed log with its subject kept as untrusted text.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Commit:
    """An upstream revision and its untrusted subject from Git's NUL-framed log."""

    sha: str
    subject: str

    @classmethod
    def from_log(cls, log: bytes) -> tuple[Commit, ...]:
        records = log.decode(errors="surrogateescape").split("\0")[:-1]
        return tuple(cls(*record.split(" ", 1)) for record in records)


@dataclass(frozen=True)
class History:
    """The copied revision, the newest one the base holds, and the commits since.

    The copied revision is the newest first-parent revision of upstream's head that
    changed the copied paths, or the head itself when none did, so the description
    names the same commit until upstream changes what the sync copies.
    """

    copied: str
    baseline: str | None
    commits: tuple[Commit, ...]
