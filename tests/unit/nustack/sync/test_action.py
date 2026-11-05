"""The sync decides what its pull request needs from what GitHub and Git report."""

import pytest

from nustack.sync.action import Close
from nustack.sync.action import Compare
from nustack.sync.action import Keep
from nustack.sync.action import Open
from nustack.sync.action import Update
from nustack.sync.action import Withdraw
from nustack.sync.action import action


class TestCompare:
    """A pull request whose branch already proposes the staged copy is kept."""

    @pytest.mark.parametrize(
        ("proposed", "expected"), [(True, Keep(7)), (False, Update(7))]
    )
    def test_keeps_a_pull_request_that_proposes_the_copy_and_updates_any_other(
        self, *, proposed: bool, expected: Keep | Update
    ) -> None:
        assert Compare(7).settled(proposed=proposed) == expected


class TestAction:
    """A staged copy opens the pull request or compares it with the copy.

    No change withdraws it.
    """

    @pytest.mark.parametrize(
        ("pull", "staged", "expected"),
        [
            (None, False, Withdraw()),
            (None, True, Open()),
            (7, False, Close(7)),
            (7, True, Compare(7)),
        ],
    )
    def test_acts_on_the_pull_request_the_copy_needs(
        self,
        pull: int | None,
        *,
        staged: bool,
        expected: Withdraw | Close | Compare | Open,
    ) -> None:
        assert action(pull, staged=staged) == expected
