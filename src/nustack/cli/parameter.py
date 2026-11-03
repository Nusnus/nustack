"""The parsers of the `nustack` command's values, which refuse an empty one.

Typer passes an option given as '' as an empty string, not as absent, so each
parser refuses it rather than run on with an empty path or name:
https://github.com/fastapi/typer/blob/0.27.3/typer/core.py#L136
"""

from pathlib import Path

import typer


def path(value: str) -> Path:
    return Path(path_text(value))


def path_text(value: str) -> str:
    return nonempty(value, "path")


def text(value: str) -> str:
    return nonempty(value, "value")


def nonempty(value: str, noun: str) -> str:
    if not value:
        message = f"give a {noun}, not an empty string"
        raise typer.BadParameter(message)
    return value
