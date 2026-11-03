"""The changelog the release publishes its notes from.

Each entry is titled with a version and a real day. Entries run newest first, below
an optional `[Unreleased]` section, and the top one, the plugin version's, stands
alone as the release's notes.
"""

import re
from dataclasses import dataclass
from datetime import date
from functools import cached_property
from itertools import pairwise
from typing import ClassVar

from nustack.problem import Problem
from nustack.validation import Pattern
from nustack.validation import version_order
lazy from nustack.markdown.document import Document
lazy from nustack.markdown.document import Section


@dataclass(frozen=True)
class Changelog:
    """The changelog's entries, newest first, each titled with its version and day."""

    UNRELEASED: ClassVar[str] = "[Unreleased]"
    ENTRY: ClassVar[re.Pattern[str]] = re.compile(
        rf"\[(?P<version>{Pattern.VERSION.unanchored})\] - "
        r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
    )
    document: Document

    @cached_property
    def releases(self) -> tuple[Section, ...]:
        sections = self.document.sections
        if sections and sections[0].title.casefold() == self.UNRELEASED.casefold():
            return sections[1:]
        return sections

    @property
    def release_notes(self) -> str:
        return self.releases[0].body

    def problems(self, version: str | None) -> list[Problem]:
        path = self.document.path
        parsed = [
            (section.title, self.ENTRY.fullmatch(section.title))
            for section in self.releases
        ]
        sections = self.document.sections
        problems: list[Problem] = []
        if self.releases != sections and sections[0].title != self.UNRELEASED:
            problems.append(
                Problem(
                    path,
                    f"titles its {self.UNRELEASED} section {sections[0].title!r}; "
                    f"spell it {self.UNRELEASED}",
                )
            )
        problems += [
            Problem(
                path,
                f"has an {self.UNRELEASED} section below a release; "
                "move it above the releases",
            )
            if title.casefold() == self.UNRELEASED.casefold()
            else Problem(
                path,
                f"has an entry titled {title!r}; "
                "title it '[<version>] - <YYYY-MM-DD>' with the release's version",
            )
            if entry is None
            else Problem(
                path,
                f"has an entry dated {entry['date']}, which is no real day; "
                "date it with the release day",
            )
            for title, entry in parsed
            if entry is None or not is_date(entry["date"])
        ]
        listed = [entry for _, entry in parsed if entry is not None]
        versions = [entry["version"] for entry in listed]
        problems += [
            Problem(path, f"has more than one entry for {each}; merge them into one")
            for each in sorted({each for each in versions if versions.count(each) > 1})
        ]
        problems += [
            Problem(
                path,
                f"has the entry for {above['version']} above the one for "
                f"{below['version']}; list releases newest first, by version",
            )
            for above, below in pairwise(listed)
            if version_order(above["version"]) < version_order(below["version"])
        ]
        problems += [
            Problem(
                path,
                f"has the entry dated {above['date']} above the one dated "
                f"{below['date']}; list releases newest first, by date",
            )
            for above, below in pairwise(listed)
            if above["date"] < below["date"]
        ]
        if version is None:
            return problems
        top = parsed[0][1] if parsed else None
        if top is None and problems:
            return problems
        if top is None or top["version"] != version:
            return [
                *problems,
                Problem(
                    path,
                    f"does not open with the entry for {version}; "
                    + self.opening(version),
                ),
            ]
        if not self.document.shows(self.release_notes):
            problems.append(
                Problem(
                    path,
                    f"has an empty entry for {version}; "
                    "list what the release changes under it",
                )
            )
        if not self.document.stands_alone(self.release_notes):
            problems.append(
                Problem(
                    path,
                    f"has an entry for {version} that reads differently on its own: "
                    "a reference it uses is defined elsewhere in the changelog; "
                    "define it inside the entry",
                )
            )
        return problems

    def opening(self, version: str) -> str:
        if self.releases != self.document.sections:
            return (
                f"retitle its {self.UNRELEASED} section '[{version}] - <release date>'"
            )
        return f"add a '## [{version}] - <release date>' section above the releases"

    def link_problems(self, repository: str) -> list[Problem]:
        versions = [
            entry["version"]
            for entry in map(self.ENTRY.fullmatch, (s.title for s in self.releases))
            if entry is not None
        ]
        # markdown-it keys each link reference by its label in upper case, and a
        # version holds no letter:
        # https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/markdown_it/common/utils.py
        targets = {
            version: f"{repository}/releases/tag/v{version}" for version in versions
        }
        if versions and self.releases != self.document.sections:
            targets["UNRELEASED"] = f"{repository}/compare/v{versions[0]}...HEAD"
        references = self.document.references
        return [
            Problem(
                self.document.path,
                f"has no link for [{shown}]; add '[{shown}]: {target}' above the"
                " first ## heading",
            )
            if label not in references
            else Problem(
                self.document.path,
                f"links [{shown}] to {references[label]}; link it to {target}",
            )
            for label, target in targets.items()
            if references.get(label) != target
            for shown in ["Unreleased" if label == "UNRELEASED" else label]
        ]


def is_date(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True
