"""What the sync's pull request needs, decided from what GitHub and Git report.

The sync takes one of these actions: withdraw the branch, close the pull request, keep
it, open one or update it. No change withdraws the branch or closes the pull request.
A staged copy opens one, or first compares the open one with it, so action decides
that pull request as Compare, a decision still pending: Git saying its branch already
proposes the copy keeps it, and otherwise updates it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Withdraw:
    """No pull request, and nothing to propose: the sync branch goes."""


@dataclass(frozen=True)
class Close:
    """A pull request that proposes nothing any more: it closes, and its branch goes."""

    pull: int


@dataclass(frozen=True)
class Keep:
    """A pull request that already proposes this copy on the base's head."""

    pull: int


@dataclass(frozen=True)
class Open:
    """No pull request, and a copy to propose: the branch is pushed and one opens."""


@dataclass(frozen=True)
class Update:
    """A pull request whose copy is stale: the branch is pushed and it is updated."""

    pull: int


@dataclass(frozen=True)
class Compare:
    """A pull request with a staged copy: kept if its branch proposes it, or updated."""

    pull: int

    def settled(self, *, proposed: bool) -> Keep | Update:
        return Keep(self.pull) if proposed else Update(self.pull)


def action(pull: int | None, *, staged: bool) -> Withdraw | Close | Compare | Open:
    match pull:
        case None:
            return Open() if staged else Withdraw()
        case number if not staged:
            return Close(number)
        case number:
            return Compare(number)
