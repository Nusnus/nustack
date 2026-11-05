"""A MAJOR.MINOR.PATCH version, and the order versions compare in."""

from typing import Annotated

from pydantic import Field

from nustack.validation import Pattern

type Version = Annotated[str, Field(pattern=Pattern.VERSION.value)]


def version_order(version: Version) -> tuple[tuple[int, str], ...]:
    # Each part orders by its length, then its digits, since int() refuses a part
    # longer than Python's digit limit:
    # https://docs.python.org/3/library/stdtypes.html#int-max-str-digits
    return tuple((len(part), part) for part in version.split("."))
