"""A command runs within its time limit.

A stall or an interrupt stops the command's process group.
"""

import os
import signal
import subprocess
import sys
import threading
lazy from collections.abc import Iterator
lazy from pathlib import Path

import pytest

from nustack import process_group
from tests.fixtures.processes import Ready
from tests.fixtures.processes import alive


class TestRun:
    """A command reads its input, and returns its status and output.

    Input given as text reads the output as text. A command that outlasts its limit, or
    is interrupted, stops with its process group, which holds every process it started
    unless one left it: SIGTERM first, and a wait for the whole group, so each can clean
    up, even after the command's own process ends, then SIGKILL for one that does not
    end, even when a second interrupt cuts the wait short, and a group that already
    ended is left alone.
    """

    # A shell without job control starts each background job ignoring SIGINT, so a
    # runner started that way raises no KeyboardInterrupt until the test restores it:
    # https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap02.html#tag_19_12
    @pytest.fixture
    def interruptible(self) -> Iterator[None]:
        previous = signal.signal(signal.SIGINT, signal.default_int_handler)
        yield
        _ = signal.signal(signal.SIGINT, previous)

    def test_returns_the_status_and_output_for_the_input(self, tmp_path: Path) -> None:
        completed = process_group.run(
            ["sh", "-c", 'cat; echo err >&2; pwd; echo "$X"; exit 3'],
            timeout=5,
            stdin=b"in\n",
            stderr=subprocess.PIPE,
            cwd=tmp_path,
            env={"PATH": "/bin:/usr/bin", "X": "set"},
        )
        assert (
            completed.args,
            completed.returncode,
            completed.stdout,
            completed.stderr,
        ) == (
            ["sh", "-c", 'cat; echo err >&2; pwd; echo "$X"; exit 3'],
            3,
            f"in\n{tmp_path.resolve()}\nset\n".encode(),
            b"err\n",
        )

    def test_reads_text_for_text_input(self) -> None:
        completed = process_group.run(
            ["cat"], timeout=5, stdin="a\r\nb", stderr=None, cwd=None, env=None
        )
        assert completed.stdout == "a\nb"

    @pytest.mark.timeout(5)
    @pytest.mark.usefixtures("interruptible")
    def test_stops_the_process_group_of_an_interrupted_command(
        self, tmp_path: Path, ready: Ready
    ) -> None:
        pid_file = tmp_path / "pid"
        interrupt = threading.Timer(0.5, os.kill, [os.getpid(), signal.SIGINT])
        ready.timers.append(interrupt)
        try:
            with pytest.raises(KeyboardInterrupt):
                _ = process_group.run(
                    [
                        "sh",
                        "-c",
                        f"sleep 30 & echo $! > {pid_file}; echo > {ready.path}; wait",
                    ],
                    timeout=60,
                    stdin=b"",
                    stderr=None,
                    cwd=None,
                    env=None,
                )
        finally:
            ready.stop()
        assert not alive(int(pid_file.read_text()))

    def test_reraises_the_timeout_when_the_group_ended_before_the_signals(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def ended(pid: int, signal: int) -> None:
            raise ProcessLookupError(pid, signal)

        monkeypatch.setattr(process_group.os, "killpg", ended)
        with pytest.raises(subprocess.TimeoutExpired):
            _ = process_group.run(
                ["sleep", "0.2"],
                timeout=0.1,
                stdin=b"",
                stderr=None,
                cwd=None,
                env=None,
            )

    @pytest.mark.timeout(5)
    def test_lets_a_stalled_command_clean_up_before_it_stops(
        self, tmp_path: Path, ready: Ready
    ) -> None:
        cleaned = tmp_path / "cleaned"
        with pytest.raises(subprocess.TimeoutExpired):
            _ = process_group.run(
                [
                    "sh",
                    "-c",
                    (
                        f"trap 'touch {cleaned}; exit 1' TERM; sleep 30 &"
                        f" echo > {ready.path}; wait"
                    ),
                ],
                timeout=1,
                stdin=b"",
                stderr=None,
                cwd=None,
                env=None,
            )
        assert cleaned.exists()

    @pytest.mark.timeout(5)
    def test_lets_the_process_group_of_a_stalled_command_clean_up(
        self, tmp_path: Path, ready: Ready
    ) -> None:
        cleaned = tmp_path / "cleaned"
        # The child cleans up only once run has reaped the command's own process, so
        # the clean-up ends only if the wait outlasts that process.
        child = (
            "trap 'while kill -0 \\$PPID 2>/dev/null; do sleep 0.05; done;"
            f" touch {cleaned}; exit 0' TERM;"
            f" echo > {ready.path}; while :; do sleep 0.05; done"
        )
        with pytest.raises(subprocess.TimeoutExpired):
            _ = process_group.run(
                ["sh", "-c", f'sh -c "{child}" & wait'],
                timeout=1,
                stdin=b"",
                stderr=None,
                cwd=None,
                env=None,
            )
        assert cleaned.exists()

    @pytest.mark.timeout(5)
    def test_kills_a_stalled_command_that_ignores_the_signal_to_clean_up(
        self, tmp_path: Path, ready: Ready, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(process_group, "GRACE", 0.2)
        pid_file = tmp_path / "pid"
        with pytest.raises(subprocess.TimeoutExpired):
            _ = process_group.run(
                [
                    "sh",
                    "-c",
                    (
                        f"trap '' TERM; sleep 30 & echo $! > {pid_file};"
                        f" echo > {ready.path}; wait"
                    ),
                ],
                timeout=1,
                stdin=b"",
                stderr=None,
                cwd=None,
                env=None,
            )
        assert not alive(int(pid_file.read_text()))

    @pytest.mark.timeout(5)
    @pytest.mark.usefixtures("interruptible")
    def test_kills_a_command_interrupted_again_while_it_cleans_up(
        self, tmp_path: Path, ready: Ready
    ) -> None:
        pid_file = tmp_path / "pid"
        first = threading.Timer(0.5, os.kill, [os.getpid(), signal.SIGINT])
        interrupted_again = threading.Event()

        def interrupt_again() -> None:
            interrupted_again.set()
            os.kill(os.getpid(), signal.SIGINT)

        second = threading.Timer(1.0, interrupt_again)
        ready.timers.extend((first, second))
        try:
            with pytest.raises(KeyboardInterrupt):
                _ = process_group.run(
                    [
                        "sh",
                        "-c",
                        (
                            f"trap '' TERM; sleep 30 & echo $! > {pid_file};"
                            f" echo > {ready.path}; wait"
                        ),
                    ],
                    timeout=60,
                    stdin=b"",
                    stderr=None,
                    cwd=None,
                    env=None,
                )
        finally:
            ready.stop()
        assert (interrupted_again.is_set(), alive(int(pid_file.read_text()))) == (
            True,
            False,
        )


class TestWaitForGroup:
    """The wait for a stopped group ends once the group is gone or the grace runs out.

    The wait for the command's own process counts against the grace.
    """

    @pytest.mark.timeout(5)
    def test_counts_the_wait_for_the_command_against_the_grace(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        process = subprocess.Popen([sys.executable, "-c", ""], start_new_session=True)
        process.wait()
        now = [0.0]
        probes: list[tuple[int, int]] = []

        def clock() -> float:
            return now[0]

        def stalled(timeout: float) -> int:
            now[0] += timeout / 2
            raise subprocess.TimeoutExpired(process.args, timeout)

        def nap(_seconds: float) -> None:
            now[0] += process_group.GRACE / 2

        def probe(pid: int, signal: int) -> None:
            probes.append((pid, signal))

        monkeypatch.setattr(process_group.time, "monotonic", clock)
        monkeypatch.setattr(process_group.time, "sleep", nap)
        monkeypatch.setattr(process_group.os, "killpg", probe)
        monkeypatch.setattr(process, "wait", stalled)
        process_group.wait_for_group(process)
        assert probes == [(process.pid, 0)]

    @pytest.mark.timeout(5)
    def test_stops_waiting_for_the_group_once_the_clock_reaches_the_deadline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        process = subprocess.Popen([sys.executable, "-c", ""], start_new_session=True)
        process.wait()
        readings = iter([0.0, 0.0, process_group.GRACE])
        probes: list[tuple[int, int]] = []

        def clock() -> float:
            return next(readings)

        def probe(pid: int, signal: int) -> None:
            probes.append((pid, signal))

        monkeypatch.setattr(process_group.time, "monotonic", clock)
        monkeypatch.setattr(process_group.os, "killpg", probe)
        process_group.wait_for_group(process)
        assert probes == [(process.pid, 0)]

    @pytest.mark.timeout(5)
    def test_ends_the_grace_once_the_process_group_is_gone(
        self, tmp_path: Path, ready: Ready, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(process_group, "GRACE", 30)
        pid_file = tmp_path / "pid"
        with pytest.raises(subprocess.TimeoutExpired):
            _ = process_group.run(
                [
                    "sh",
                    "-c",
                    f"sleep 30 & echo $! > {pid_file}; echo > {ready.path}; wait",
                ],
                timeout=1,
                stdin=b"",
                stderr=None,
                cwd=None,
                env=None,
            )
        assert not alive(int(pid_file.read_text()))
