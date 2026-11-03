"""The fake gh logs no call before the first."""

lazy from pathlib import Path

from tests.fixtures.gh import FakeGh


class TestFakeGh:
    """A fake gh just installed has logged no call."""

    def test_has_logged_no_call_before_the_first(self, tmp_path: Path) -> None:
        assert FakeGh.install(tmp_path / "gh").calls == []
