"""The skip for tests that need a path's permission bits to refuse access."""

import os

import pytest

# pytest shares a skipif marker between modules as a module-level object that each test
# module imports:
# https://github.com/pytest-dev/pytest/blob/9.2.0/doc/en/how-to/skipping.rst?plain=1#L100-L128
SKIP_AS_ROOT = pytest.mark.skipif(
    os.geteuid() == 0, reason="root ignores permission bits, so no path refuses it"
)
