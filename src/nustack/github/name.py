"""A GitHub repository's name with its owner, and the https URL that gives one.

A name or URL given as text that GitHub would not take is refused with the fix. A
refused URL is never repeated, so a token it holds stays out of the message.
"""

import re
from dataclasses import dataclass
from typing import ClassVar
from urllib.parse import urlsplit

from nustack.validation import Pattern


class GitHubNameError(ValueError):
    """A repository's name or URL is not of the form GitHub gives it."""


@dataclass(frozen=True)
class NameWithOwner:
    """A repository's name with its owner, written `<owner>/<name>`."""

    ASK: ClassVar[str] = "give the repository as GitHub names it"
    FIX: ClassVar[str] = (
        f"for <owner>, {Pattern.OWNER.fix}; for <name>, {Pattern.REPOSITORY.fix}"
    )
    owner: str
    name: str

    @classmethod
    def parse(cls, value: str) -> NameWithOwner:
        match value.split("/"):
            case [owner, name] if owner and name:
                try:
                    return cls(owner, name)
                except GitHubNameError:
                    message = f"{cls.ASK}, not {value}; {cls.FIX}"
                    raise GitHubNameError(message) from None
            case _:
                message = f"give the repository as <owner>/<name>, not {value}"
                raise GitHubNameError(message)

    def __post_init__(self) -> None:
        if not (
            re.fullmatch(Pattern.OWNER, self.owner)
            and re.fullmatch(Pattern.REPOSITORY, self.name)
        ):
            message = f"{self.ASK}; {self.FIX}"
            raise GitHubNameError(message)

    def __str__(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(frozen=True)
class RepositoryUrl:
    """A repository's https URL on its host, written `https://<host>/<owner>/<name>`."""

    host: str
    name_with_owner: NameWithOwner

    @classmethod
    def parse(cls, value: str) -> RepositoryUrl:
        url = urlsplit(value)
        form = (
            "give the repository's URL as https://<host>/<owner>/<name>, with no user,"
            " password, port, query or fragment"
        )
        match url.path.split("/"):
            case ["", owner, name] if (
                url.scheme == "https"
                and owner
                and name
                and not url.query
                and not url.fragment
            ):
                try:
                    name_with_owner = NameWithOwner(owner, name)
                except GitHubNameError:
                    message = (
                        "give the repository's URL with an owner and name GitHub would"
                        f" take; {NameWithOwner.FIX}"
                    )
                    raise GitHubNameError(message) from None
                try:
                    repository_url = cls(url.netloc, name_with_owner)
                except GitHubNameError:
                    raise GitHubNameError(form) from None
                # urlsplit drops tabs and line breaks, and an empty query or
                # fragment, so a URL it read is taken only as it reads back.
                if str(repository_url) != value:
                    raise GitHubNameError(form)
                return repository_url
            case _:
                raise GitHubNameError(form)

    def __post_init__(self) -> None:
        if not re.fullmatch(Pattern.HOST, self.host):
            message = f"give the host as a host name; {Pattern.HOST.fix}"
            raise GitHubNameError(message)

    def __str__(self) -> str:
        return f"https://{self.host}/{self.name_with_owner}"
