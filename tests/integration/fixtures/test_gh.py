"""The fake gh replays each reply a test gives, as gh prints it, and logs each call."""

lazy from pathlib import Path

import pytest

from tests.fixtures.processes import run_gh
lazy from tests.fixtures.gh import FakeGh


class TestFakeGh:
    """A test reads what gh printed and exited with, and the calls the harness made.

    A call no reply matches succeeds silently, a departure from gh kept for the
    commands that change GitHub, whose output the harness never reads, and the last
    reply repeats once the others are used.
    """

    @pytest.mark.usefixtures("gh")
    def test_succeeds_silently_on_a_call_no_reply_matches(self) -> None:
        run = run_gh("pr", "edit", "1")
        assert (run.stdout, run.stderr, run.returncode) == ("", "", 0)

    def test_replays_a_reply_with_its_output_and_status(self, gh: FakeGh) -> None:
        gh.reply("api", "x", stdout="12\n", stderr="slow\n", code=1)
        run = run_gh("api", "x")
        assert (run.stdout, run.stderr, run.returncode) == ("12\n", "slow\n", 1)

    def test_replays_a_recorded_reply(self, gh: FakeGh, tmp_path: Path) -> None:
        recording = tmp_path / "reply.json"
        recording.write_text(
            '{"argv": ["api", "y"], "stdout": "12\\n", "stderr": "slow\\n", "code": 1}'
        )
        printed = gh.replay("api", "x", recording=recording)
        run = run_gh("api", "x")
        assert (printed, run.stdout, run.stderr, run.returncode) == (
            "12\n",
            "12\n",
            "slow\n",
            1,
        )

    def test_replays_replies_in_order_then_keeps_the_last(self, gh: FakeGh) -> None:
        gh.reply("api", "x", stdout="1\n")
        gh.reply("api", "x", stdout="2\n")
        runs = [run_gh("api", "x") for _ in range(3)]
        assert [(run.stdout, run.returncode) for run in runs] == [
            ("1\n", 0),
            ("2\n", 0),
            ("2\n", 0),
        ]

    def test_logs_each_call_with_its_input_in_order(self, gh: FakeGh) -> None:
        codes = [
            run_gh(*argv, stdin=stdin).returncode
            for argv, stdin in [(("a",), "one"), (("b", "c"), "")]
        ]
        assert (codes, gh.calls) == ([0, 0], [(("a",), "one"), (("b", "c"), "")])
