"""The parsers of the `nustack` command's values.

Each refuses an empty value, and a repository name, a release tag or a commit of the
wrong form, with the fix for its form.

Typer passes an option given as '' as an empty string, not as absent, so each
parser refuses it rather than run on with an empty path or name:
https://github.com/fastapi/typer/blob/0.27.3/typer/core.py#L136
"""

from pathlib import Path
lazy from collections.abc import Callable

import typer

from nustack.github.name import GitHubNameError
from nustack.github.name import NameWithOwner
from nustack.release.tag import Tag
from nustack.release.tag import TagError
from nustack.sha import Sha
from nustack.sha import ShaError


def path(value: str) -> Path:
    return Path(path_text(value))


def name_with_owner(value: str) -> NameWithOwner:
    return read_with(NameWithOwner.parse, value)


def tag(value: str) -> Tag:
    return read_with(Tag.parse, value)


def commit(value: str) -> Sha:
    return read_with(Sha.parse, value)


def read_with[T](parse: Callable[[str], T], value: str) -> T:
    try:
        return parse(text(value))
    except (GitHubNameError, ShaError, TagError) as error:
        raise typer.BadParameter(str(error)) from error


def path_text(value: str) -> str:
    return nonempty(value, "path")


def text(value: str) -> str:
    return nonempty(value, "value")


def nonempty(value: str, noun: str) -> str:
    if not value:
        message = f"give a {noun}, not an empty string"
        raise typer.BadParameter(message)
    return value
