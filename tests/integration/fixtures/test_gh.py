"""The fake gh replays each reply a test gives, as gh prints it, and logs each call."""

import subprocess
lazy from pathlib import Path

import pytest

lazy from tests.fixtures.gh import FakeGh


class TestFakeGh:
    """A test reads what gh printed and exited with, and the calls the harness made.

    A call no reply matches succeeds silently, a departure from gh kept for the
    commands that change GitHub, whose output the harness never reads, and the last
    reply repeats once the others are used.
    """

    @pytest.mark.usefixtures("gh")
    def test_succeeds_silently_on_a_call_no_reply_matches(self) -> None:
        run = subprocess.run(
            ["gh", "pr", "edit", "1"],  # noqa: S607 -- the fake gh on PATH
            capture_output=True,
            text=True,
            # Ruff asks for check; the test reads the exit status itself:
            # https://docs.astral.sh/ruff/rules/subprocess-run-without-check/
            check=False,
        )
        assert (run.stdout, run.stderr, run.returncode) == ("", "", 0)

    def test_replays_a_reply_with_its_output_and_status(self, gh: FakeGh) -> None:
        gh.reply("api", "x", stdout="12\n", stderr="slow\n", code=1)
        run = subprocess.run(
            ["gh", "api", "x"],  # noqa: S607 -- the fake gh on PATH
            capture_output=True,
            text=True,
            # Ruff asks for check; the test reads the exit status itself:
            # https://docs.astral.sh/ruff/rules/subprocess-run-without-check/
            check=False,
        )
        assert (run.stdout, run.stderr, run.returncode) == ("12\n", "slow\n", 1)

    def test_replays_a_recorded_reply(self, gh: FakeGh, tmp_path: Path) -> None:
        recording = tmp_path / "reply.json"
        recording.write_text(
            '{"argv": ["api", "y"], "stdout": "12\\n", "stderr": "slow\\n", "code": 1}'
        )
        printed = gh.replay("api", "x", recording=recording)
        run = subprocess.run(
            ["gh", "api", "x"],  # noqa: S607 -- the fake gh on PATH
            capture_output=True,
            text=True,
            # Ruff asks for check; the test reads the exit status itself:
            # https://docs.astral.sh/ruff/rules/subprocess-run-without-check/
            check=False,
        )
        assert (printed, run.stdout, run.stderr, run.returncode) == (
            "12\n",
            "12\n",
            "slow\n",
            1,
        )

    def test_replays_replies_in_order_then_keeps_the_last(self, gh: FakeGh) -> None:
        gh.reply("api", "x", stdout="1\n")
        gh.reply("api", "x", stdout="2\n")
        outputs = [
            subprocess.run(
                ["gh", "api", "x"],  # noqa: S607 -- the fake gh on PATH
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            for _ in range(3)
        ]
        assert outputs == ["1\n", "2\n", "2\n"]

    def test_logs_each_call_with_its_input_in_order(self, gh: FakeGh) -> None:
        for argv, stdin in [(["a"], "one"), (["b", "c"], "")]:
            subprocess.run(  # noqa: S603 -- the test's own arguments
                ["gh", *argv],  # noqa: S607 -- the fake gh on PATH
                input=stdin,
                text=True,
                check=True,
            )
        assert gh.calls == [(("a",), "one"), (("b", "c"), "")]
