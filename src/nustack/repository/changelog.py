"""The changelog the release publishes its notes from.

Each entry is titled with a version and a real day. Entries run newest first, below an
optional `[Unreleased]` section. The top one, the plugin version's, is the body of the
release page and resolves each reference label it uses the same on its own as in the
file. It gives each link and image a full URL, and holds an optional lead, then its
changes, grouped under Keep a Changelog's types of change in the order that format
lists them, each type once and each group showing something. The release below it is
the one the page compares with. The changelog links each release and the plugin
version to its tag's page, and `[Unreleased]`, while that section exists, to the
changes since the plugin version. A bump takes an `[Unreleased]` section that lists
changes, and titles them with the release's version and day below a new empty one,
with the links of `[Unreleased]` and every release set.
"""

import re
from dataclasses import dataclass
from dataclasses import replace
from datetime import date
from enum import StrEnum
from functools import cached_property
from itertools import pairwise
from typing import ClassVar
from typing import Literal

from nustack.problem import Problem
from nustack.release.tag import Tag
from nustack.repository.page import PagePart
from nustack.validation import Pattern
from nustack.version import Version
from nustack.version import version_order
lazy from nustack.github.name import RepositoryUrl
lazy from nustack.markdown.document import Document
lazy from nustack.markdown.document import Section


class ChangeType(StrEnum):
    """A type of change Keep a Changelog groups an entry by, in the order it lists them.

    https://keepachangelog.com/en/1.1.0/#how
    """

    ADDED = "Added"
    CHANGED = "Changed"
    DEPRECATED = "Deprecated"
    REMOVED = "Removed"
    FIXED = "Fixed"
    SECURITY = "Security"

    @classmethod
    def listed(cls, conjunction: Literal["and", "or"]) -> str:
        *rest, last = cls
        return f"{', '.join(rest)} {conjunction} {last}"


@dataclass(frozen=True)
class Entry:
    """A release's entry: an optional lead, then its changes under third-level groups.

    The entry is read in the changelog it sits in, so its text is the changelog's.
    The lead is the text above the first group.
    """

    changelog: Document
    release: Section

    @property
    def body(self) -> str:
        return self.release.body

    @cached_property
    def groups(self) -> tuple[Section, ...]:
        return tuple(
            each for each in self.changelog.headed(3) if self.release.holds(each.start)
        )

    @cached_property
    def split(self) -> int:
        return self.groups[0].start if self.groups else self.release.end

    @property
    def lead(self) -> str:
        return self.changelog.text_between(self.release.body_start, self.split)

    @property
    def changes(self) -> str:
        return self.changelog.text_between(self.split, self.release.end)


@dataclass(frozen=True)
class Changelog:
    """The changelog's entries, newest first, each titled with its version and day."""

    UNRELEASED_NAME: ClassVar[str] = "Unreleased"
    UNRELEASED: ClassVar[str] = f"[{UNRELEASED_NAME}]"
    UNRELEASED_FOLDED: ClassVar[str] = UNRELEASED.casefold()
    # markdown-it keys each link reference by its label in upper case:
    # https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/markdown_it/common/utils.py#L253-L301
    UNRELEASED_LABEL: ClassVar[str] = UNRELEASED_NAME.upper()
    ENTRY: ClassVar[re.Pattern[str]] = re.compile(
        rf"\[(?P<version>{Pattern.VERSION.unanchored})\] - "
        r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
    )
    document: Document

    @cached_property
    def releases(self) -> tuple[Section, ...]:
        sections = self.document.sections
        if sections and self.is_unreleased(sections[0].title):
            return sections[1:]
        return sections

    @cached_property
    def titles(self) -> tuple[tuple[str, re.Match[str] | None], ...]:
        return tuple(
            (section.title, self.ENTRY.fullmatch(section.title))
            for section in self.releases
        )

    @cached_property
    def titled(self) -> tuple[re.Match[str], ...]:
        return tuple(entry for _, entry in self.titles if entry is not None)

    @cached_property
    def top(self) -> re.Match[str] | None:
        return self.titles[0][1] if self.titles else None

    @cached_property
    def versions(self) -> tuple[Version, ...]:
        return tuple(entry["version"] for entry in self.titled)

    @property
    def previous(self) -> Version | None:
        return self.versions[1] if len(self.versions) > 1 else None

    @cached_property
    def entry(self) -> Entry:
        return Entry(self.document, self.releases[0])

    def problems(self, version: Version | None) -> list[Problem]:
        path = self.document.path
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
        first_release = next(
            (
                index
                for index, (title, _) in enumerate(self.titles)
                if not self.is_unreleased(title)
            ),
            len(self.titles),
        )
        if first_release:
            problems.append(
                Problem(
                    path,
                    f"has more than one {self.UNRELEASED} section; merge them into one",
                )
            )
        problems += [
            Problem(
                path,
                f"has an {self.UNRELEASED} section below a release; "
                "move it above the releases",
            )
            if self.is_unreleased(title)
            else Problem(
                path,
                f"has an entry titled {title!r}; "
                "title it '[<version>] - <YYYY-MM-DD>' with the release's version"
                + (
                    f", or spell it {self.UNRELEASED} if no release is due"
                    if index == 0 and self.releases == sections
                    else ""
                ),
            )
            if entry is None
            else Problem(
                path,
                f"has an entry dated {entry['date']}, which is no real day; "
                "date it with the release day",
            )
            for index, (title, entry) in enumerate(self.titles)
            if index >= first_release and (entry is None or not is_date(entry["date"]))
        ]
        problems += [
            Problem(path, f"has more than one entry for {each}; merge them into one")
            for each in sorted(
                {each for each in self.versions if self.versions.count(each) > 1}
            )
        ]
        problems += [
            Problem(
                path,
                f"has the entry for {above['version']} above the one for "
                f"{below['version']}; list releases newest first, by version",
            )
            for above, below in pairwise(self.titled)
            if version_order(above["version"]) < version_order(below["version"])
        ]
        problems += [
            Problem(
                path,
                f"has the entry dated {above['date']} above the one dated "
                f"{below['date']}; list releases newest first, by date",
            )
            for above, below in pairwise(self.titled)
            if above["date"] < below["date"]
        ]
        if version is None:
            return problems
        if self.top is None and problems and not self.newer(version):
            return problems
        if not self.opens_with(version):
            return [
                *problems,
                Problem(
                    path,
                    f"does not open with the entry for {version}; "
                    + self.opening(version),
                ),
            ]
        part = self.entry_part(version)
        problems += part.problems
        if part.shows:
            problems += self.group_problems(version)
        return problems

    def opens_with(self, version: Version) -> bool:
        return self.top is not None and self.top["version"] == version

    def opening(self, version: Version) -> str:
        if self.newer(version):
            return (
                "set the newest entry's version in every file whose version "
                f"nustack check compares, or remove the entries newer than {version}"
            )
        if version in self.versions:
            return f"move the entry for {version} above the other releases"
        if self.releases != self.document.sections:
            return (
                f"retitle its {self.UNRELEASED} section '[{version}] - <release date>'"
            )
        return f"add a '## [{version}] - <release date>' section above the releases"

    def newer(self, version: Version) -> bool:
        return any(
            version_order(listed) > version_order(version) for listed in self.versions
        )

    def entry_part(self, version: Version) -> PagePart:
        return PagePart(
            self.document,
            self.entry.release,
            f"the entry for {version}",
            "list what the release changes under it, which the release page copies",
        )

    def group_problems(self, version: Version) -> list[Problem]:
        path = self.document.path
        groups = self.entry.groups
        if not groups:
            return [
                Problem(
                    path,
                    f"lists the changes in the entry for {version} under no group; "
                    f"group them under '### <type>' headings, each one of "
                    f"{ChangeType.listed('or')}, as Keep a Changelog does",
                )
            ]
        types = list(ChangeType)
        known = [
            ChangeType(group.title) for group in groups if group.title in ChangeType
        ]
        return [
            *(
                Problem(
                    path,
                    f"has a group titled {group.title!r} in the entry for {version}; "
                    f"title it {ChangeType.listed('or')}, as Keep a Changelog does",
                )
                for group in groups
                if group.title not in ChangeType
            ),
            *(
                Problem(
                    path,
                    f"has more than one {title} group in the entry for {version}; "
                    "merge them into one",
                )
                for title in sorted(
                    {each for each in known if known.count(each) > 1}, key=types.index
                )
            ),
            *(
                Problem(
                    path,
                    f"has the {above} group above the {below} group in the entry for "
                    f"{version}; order the groups {ChangeType.listed('and')}, as Keep a"
                    " Changelog lists them",
                )
                for above, below in dict.fromkeys(pairwise(known))
                if types.index(above) > types.index(below)
            ),
            *(
                Problem(
                    path,
                    f"shows nothing in the {group.title} group of the entry for"
                    f" {version}; list its changes under it, or remove it",
                )
                for group in groups
                if not self.document.shows(group.body)
            ),
        ]

    def link_problems(
        self, repository_url: RepositoryUrl, version: Version
    ) -> list[Problem]:
        if not self.releases:
            return []
        # A version holds no letter, so upper-casing it, as markdown-it does
        # (UNRELEASED_LABEL's comment), leaves its label the version itself.
        targets = {
            (each, each): target
            for each, target in self.release_links(repository_url, version).items()
        }
        if (unreleased := self.unreleased_link(repository_url, version)) is not None:
            targets[self.UNRELEASED_LABEL, self.UNRELEASED_NAME] = unreleased
        references = self.document.references
        problems = [
            Problem(
                self.document.path,
                f"has no link for [{name}]; add '[{name}]: {target}' above the"
                " first ## heading",
            )
            if label not in references
            else Problem(
                self.document.path,
                f"links [{name}] to {references[label]}; link it to {target}",
            )
            for (label, name), target in targets.items()
            if references.get(label) != target
        ]
        if self.UNRELEASED_LABEL in references and not any(
            self.is_unreleased(section.title) for section in self.document.sections
        ):
            problems.append(
                Problem(
                    self.document.path,
                    f"links {self.UNRELEASED} but has no {self.UNRELEASED} section;"
                    " add the section above the releases if changes await a release,"
                    " or remove the link",
                )
            )
        return problems

    def release_links(
        self, repository_url: RepositoryUrl, version: Version
    ) -> frozendict[Version, str]:
        return frozendict(
            (each, f"{repository_url}/releases/tag/{Tag(each)}")
            for each in (*self.versions, version)
        )

    def unreleased_link(
        self, repository_url: RepositoryUrl, version: Version
    ) -> str | None:
        if self.releases == self.document.sections:
            return None
        return f"{repository_url}/compare/{Tag(version)}...HEAD"

    def bump(self, version: Version | None) -> Unreleased | list[Problem]:
        path = self.document.path
        problems = []
        if self.releases == self.document.sections:
            problems.append(
                Problem(
                    path,
                    f"has no {self.UNRELEASED} section to release; add it above the"
                    " releases, with each change since the last release",
                )
            )
        elif not self.document.shows(self.document.sections[0].body):
            problems.append(
                Problem(
                    path,
                    f"lists no change under {self.UNRELEASED}; list each change since"
                    " the last release there, as AGENTS.md's Pull requests says",
                )
            )
        if version is not None and (self.newer(version) or version in self.versions):
            latest = max(self.versions, key=version_order)
            problems.append(
                Problem(
                    version,
                    f"is not newer than {latest}, the changelog's latest release; give"
                    " a newer version",
                )
            )
        if problems:
            return problems
        return Unreleased(self, self.document.sections[0])

    def relinked(self, repository_url: RepositoryUrl, version: Version) -> str:
        document = self.document
        links = self.release_links(repository_url, version)
        managed = {*links, self.UNRELEASED_LABEL}
        spans = [
            definition
            for definition in document.definition_lines
            if definition.label in managed
        ]
        first_heading = document.sections[0].start
        block = [
            f"{self.UNRELEASED}: {self.unreleased_link(repository_url, version)}\n",
            *(f"[{each}]: {target}\n" for each, target in links.items()),
        ]
        lines = list(document.body_lines)
        for span in reversed(spans):
            del lines[span.start : span.end]
        at = min(first_heading, *(span.start for span in spans))
        lines[at:at] = [*block, "\n"] if at == first_heading else block
        frontmatter = document.text_lines[: document.frontmatter_lines]
        return "".join((*frontmatter, *lines))

    def is_unreleased(self, title: str) -> bool:
        return title.casefold() == self.UNRELEASED_FOLDED


@dataclass(frozen=True)
class Unreleased:
    """A changelog's `[Unreleased]` section, which lists changes, to title as a release.

    Its release keeps the section's changes under the release's title, opens an empty
    `[Unreleased]` section above them, and writes the links of `[Unreleased]` and
    every release as one block, where the first of them stood above the first `##`
    heading, or else directly above that heading.
    """

    changelog: Changelog
    section: Section

    def released(
        self, repository_url: RepositoryUrl, version: Version, day: date
    ) -> str:
        document = self.changelog.document
        lines = list(document.body_lines)
        heading = lines[self.section.start]
        ending = heading.removeprefix(heading.splitlines()[0])
        lines[self.section.start : self.section.body_start] = [
            f"## {Changelog.UNRELEASED}{ending}",
            ending,
            f"## [{version}] - {day.isoformat()}{ending}",
        ]
        frontmatter = document.text_lines[: document.frontmatter_lines]
        titled = Changelog(replace(document, text="".join((*frontmatter, *lines))))
        return titled.relinked(repository_url, version)


def is_date(text: str) -> bool:
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True
