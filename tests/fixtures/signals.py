"""The SIGINT handler that a test interrupting its own code needs, in every tier."""

import signal
lazy from collections.abc import Iterator

import pytest


# A shell without job control starts each background job ignoring SIGINT, so a
# runner started that way raises no KeyboardInterrupt until the test restores it:
# https://pubs.opengroup.org/onlinepubs/9799919799/utilities/V3_chap02.html#tag_19_12
@pytest.fixture
def interruptible() -> Iterator[None]:
    previous = signal.signal(signal.SIGINT, signal.default_int_handler)
    yield
    _ = signal.signal(signal.SIGINT, previous)
