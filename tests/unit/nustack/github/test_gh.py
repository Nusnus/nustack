"""A gh error's text is nustack's message for it, and each gh command has a minute."""

from datetime import timedelta

from nustack.github.gh import GitHub
from nustack.github.gh import GitHubError
from nustack.github.name import NameWithOwner


class TestGitHubError:
    """A gh failure's text is nustack's message for it."""

    def test_gives_its_message_as_its_text(self) -> None:
        assert str(GitHubError("gh api exited 1; fix the cause gh printed")) == (
            "gh api exited 1; fix the cause gh printed"
        )


class TestGitHub:
    """Each gh command GitHub runs has a time limit."""

    def test_gives_each_command_a_minute_by_default(self) -> None:
        assert (
            GitHub(NameWithOwner("o", "r")).timeout
            == timedelta(minutes=1).total_seconds()
        )
