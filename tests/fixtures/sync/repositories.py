"""Real Git repositories shaped like the sync's upstream and nustack's checkout."""

from dataclasses import dataclass
from typing import ClassVar

lazy from nustack.sha import Sha
lazy from tests.fixtures.git_repository import GitRepository


@dataclass(frozen=True)
class Sync:
    """An upstream skill that moved on once, and a checkout copying its first state.

    The skill's folder name is a glob pattern, so Git reading it as a pattern
    instead of a path shows.
    """

    SOURCE_FOLDER: ClassVar[str] = "skills/*"
    FOLDER: ClassVar[str] = "copy"
    upstream: GitRepository
    checkout: GitRepository
    first: Sha
    second: Sha
