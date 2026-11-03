"""A limit on how long a block may take, for the tests of input that could loop."""

import signal

import pytest


class Deadline:
    """A limit on how long a block may take, so a test that loops fails."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    def __enter__(self) -> None:
        signal.signal(signal.SIGALRM, self.expire)
        signal.setitimer(signal.ITIMER_REAL, self.seconds)

    def __exit__(self, *_: object) -> None:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)

    def expire(self, *_: object) -> None:
        pytest.fail(f"took over {self.seconds} seconds")
