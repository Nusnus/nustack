"""Upstream's history as the sync reads it, found by the files the workflow copies.

The copied revision is identified by those paths, the base's by its record, and
each commit is read from Git's NUL-framed log with its subject kept as untrusted
text, and refused unless Git names it by its SHA-1.
"""

from dataclasses import dataclass

from nustack.sha import Sha


@dataclass(frozen=True)
class Commit:
    """An upstream revision and its untrusted subject from Git's NUL-framed log."""

    sha: Sha
    subject: str

    @classmethod
    def from_log(cls, log: bytes) -> tuple[Commit, ...]:
        records = log.decode(errors="surrogateescape").split("\0")[:-1]
        fields = (record.split(" ", 1) for record in records)
        return tuple(cls(Sha(sha), subject) for sha, subject in fields)


@dataclass(frozen=True)
class History:
    """The copied revision, the one the base's record names, and the commits since.

    The copied revision is the newest first-parent revision of upstream's head that
    changed the copied paths, or the head itself when none did, so the description
    names the same commit until upstream changes what the sync copies. The baseline
    is absent when the record names no commit, or one upstream's head no longer
    holds.
    """

    copied: Sha
    baseline: Sha | None
    commits: tuple[Commit, ...]
