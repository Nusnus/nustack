"""A command runs within its time limit.

A stall or an interrupt stops the command's process group.
"""

import contextlib
import os
import signal
import subprocess
import sys
lazy from functools import partial
lazy from pathlib import Path

import pytest

from nustack import process_group
from tests.fixtures.processes import Ready
from tests.fixtures.processes import alive


@pytest.mark.usefixtures("unhurried")
class TestRun:
    """A command reads its input, and returns its status and output.

    Input given as text reads the output as text. A command that outlasts its limit, or
    is interrupted, stops with its process group, which holds every process it started
    unless one left it: SIGTERM first, and a wait for the whole group, so each can clean
    up, even after the command's own process ends, then SIGKILL for one that does not
    end, even when a second interrupt cuts the wait short, and a group that already
    ended is left alone.
    """

    def test_returns_the_status_and_output_for_the_input(
        self, tmp_path: Path, per_test_limit: float
    ) -> None:
        completed = process_group.run(
            ["sh", "-c", 'cat; echo err >&2; pwd; echo "$X"; exit 3'],
            timeout=per_test_limit,
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

    def test_reads_text_for_text_input(self, per_test_limit: float) -> None:
        completed = process_group.run(
            ["cat"],
            timeout=per_test_limit,
            stdin="a\r\nb",
            stderr=None,
            cwd=None,
            env=None,
        )
        assert completed.stdout == "a\nb"

    @pytest.mark.usefixtures("interruptible")
    def test_stops_the_process_group_of_an_interrupted_command(
        self, tmp_path: Path, ready: Ready, stall: str, per_test_limit: float
    ) -> None:
        pid_file = tmp_path / "pid"
        ready.actions.append(partial(signal.raise_signal, signal.SIGINT))
        with pytest.raises(KeyboardInterrupt):
            _ = process_group.run(
                [
                    "sh",
                    "-c",
                    f"{stall} & echo $! > {pid_file}; echo > {ready.path}; wait",
                ],
                timeout=per_test_limit,
                stdin=b"",
                stderr=None,
                cwd=None,
                env=None,
            )
        assert not alive(int(pid_file.read_text()))

    def test_reraises_the_timeout_when_the_group_ended_before_the_signals(
        self, monkeypatch: pytest.MonkeyPatch, stall: str
    ) -> None:
        killpg = os.killpg

        def ended(pid: int, signum: int) -> None:
            with contextlib.suppress(ProcessLookupError):
                killpg(pid, signal.SIGKILL)
            raise ProcessLookupError(pid, signum)

        monkeypatch.setattr(process_group.os, "killpg", ended)
        with pytest.raises(subprocess.TimeoutExpired):
            _ = process_group.run(
                ["sh", "-c", stall],
                timeout=0.1,
                stdin=b"",
                stderr=None,
                cwd=None,
                env=None,
            )

    def test_lets_a_stalled_command_clean_up_before_it_stops(
        self, tmp_path: Path, ready: Ready, stall: str
    ) -> None:
        cleaned = tmp_path / "cleaned"
        with pytest.raises(subprocess.TimeoutExpired):
            _ = process_group.run(
                [
                    "sh",
                    "-c",
                    (
                        f"trap 'touch {cleaned}; exit 1' TERM; {stall} &"
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

    def test_lets_the_process_group_of_a_stalled_command_clean_up(
        self, tmp_path: Path, ready: Ready, stall: str
    ) -> None:
        cleaned = tmp_path / "cleaned"
        # The child cleans up only once run has reaped the command's own process, so
        # the clean-up ends only if the wait outlasts that process.
        child = (
            "trap 'while kill -0 \\$PPID 2>/dev/null; do sleep 0.05; done;"
            f" touch {cleaned}; exit 0' TERM;"
            f" echo > {ready.path}; {stall}"
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

    # The command's own shell ends on SIGTERM, so only the clock holds the wait for
    # the process that ignores it, and the fake clock lets the grace run out at once.
    def test_kills_a_stalled_command_that_ignores_the_signal_to_clean_up(
        self, tmp_path: Path, ready: Ready, stall: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        readings = iter([0.0])

        def clock() -> float:
            return next(readings, process_group.GRACE)

        monkeypatch.setattr(process_group.time, "monotonic", clock)
        pid_file = tmp_path / "pid"
        with pytest.raises(subprocess.TimeoutExpired):
            _ = process_group.run(
                [
                    "sh",
                    "-c",
                    (
                        f"sh -c \"trap '' TERM; echo \\$\\$ > {pid_file};"
                        f' echo > {ready.path}; exec {stall}" & wait'
                    ),
                ],
                timeout=1,
                stdin=b"",
                stderr=None,
                cwd=None,
                env=None,
            )
        assert not alive(int(pid_file.read_text()))

    # The second interrupt lands the moment the wait for the group reads the clock.
    @pytest.mark.usefixtures("interruptible")
    def test_kills_a_command_interrupted_again_while_it_cleans_up(
        self,
        tmp_path: Path,
        ready: Ready,
        stall: str,
        per_test_limit: float,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        pid_file = tmp_path / "pid"
        interrupts: list[int] = []

        # raise_signal runs the SIGINT handler before it returns, so the clock read
        # ends in KeyboardInterrupt and the wait reads the clock only once.
        def interrupt_again() -> None:
            interrupts.append(signal.SIGINT)
            signal.raise_signal(signal.SIGINT)

        monkeypatch.setattr(process_group.time, "monotonic", interrupt_again)
        ready.actions.append(partial(signal.raise_signal, signal.SIGINT))
        with pytest.raises(KeyboardInterrupt):
            _ = process_group.run(
                [
                    "sh",
                    "-c",
                    (
                        f"trap '' TERM; {stall} & echo $! > {pid_file};"
                        f" echo > {ready.path}; wait"
                    ),
                ],
                timeout=per_test_limit,
                stdin=b"",
                stderr=None,
                cwd=None,
                env=None,
            )
        assert (len(interrupts), alive(int(pid_file.read_text()))) == (1, False)


@pytest.mark.usefixtures("unhurried")
class TestWaitForGroup:
    """The wait for a stopped group ends once the group is gone or the grace runs out.

    The wait for the command's own process counts against the grace.
    """

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

    def test_stops_waiting_for_the_group_once_the_clock_reaches_the_deadline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        process = subprocess.Popen([sys.executable, "-c", ""], start_new_session=True)
        process.wait()
        readings = iter([0.0, 0.0, process_group.GRACE])
        probes: list[tuple[int, int]] = []

        def clock() -> float:
            return next(readings)

        def nap(_seconds: float) -> None:
            pass

        def probe(pid: int, signal: int) -> None:
            probes.append((pid, signal))

        monkeypatch.setattr(process_group.time, "monotonic", clock)
        monkeypatch.setattr(process_group.time, "sleep", nap)
        monkeypatch.setattr(process_group.os, "killpg", probe)
        process_group.wait_for_group(process)
        assert probes == [(process.pid, 0)]

    def test_ends_the_grace_once_the_process_group_is_gone(
        self, tmp_path: Path, ready: Ready, stall: str
    ) -> None:
        pid_file = tmp_path / "pid"
        with pytest.raises(subprocess.TimeoutExpired):
            _ = process_group.run(
                [
                    "sh",
                    "-c",
                    f"{stall} & echo $! > {pid_file}; echo > {ready.path}; wait",
                ],
                timeout=1,
                stdin=b"",
                stderr=None,
                cwd=None,
                env=None,
            )
        assert not alive(int(pid_file.read_text()))
