"""The deadline fails a block that outlasts it and passes one that ends in time."""

import signal
import time

import pytest

from tests.fixtures.deadline import Deadline


class TestDeadline:
    """A hung subprocess fails its test instead of stalling the suite.

    A block that ends in time passes, and its timer stops.
    """

    def test_fails_a_block_that_outlasts_it(self) -> None:
        with (
            pytest.raises(pytest.fail.Exception, match=r"^took over 0\.01 seconds$"),
            Deadline(0.01),
        ):
            time.sleep(1)

    def test_lets_a_block_that_ends_in_time_pass_and_stops_its_timer(self) -> None:
        with Deadline(1):
            pass
        assert (
            signal.getitimer(signal.ITIMER_REAL),
            signal.getsignal(signal.SIGALRM),
        ) == ((0.0, 0.0), signal.SIG_DFL)
