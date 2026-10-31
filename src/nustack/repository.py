"""The rules that tie the plugin to the files released beside it."""

import re
from dataclasses import dataclass
from datetime import date
from functools import cached_property
from itertools import pairwise
from pathlib import Path
from typing import ClassVar

from nustack.document import Document
from nustack.document import Section
from nustack.manifest import SEMVER
from nustack.manifest import ClaudeMarketplace
from nustack.manifest import CursorMarketplace
from nustack.manifest import InvalidMetadataError
from nustack.manifest import Manifest
from nustack.manifest import Marketplace
from nustack.manifest import Package
from nustack.plugin import Plugin
from nustack.problem import Problem
from nustack.problem import cannot_read
from nustack.pyproject import InvalidPyprojectError
from nustack.pyproject import Pyproject


@dataclass
class Repository:
    """The nustack repository: the plugin and the files released with it."""

    ENTRY: ClassVar[re.Pattern[str]] = re.compile(
        r"\[(?P<version>" + SEMVER + r")\] - (?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})"
    )

    MARKETPLACES: ClassVar[tuple[tuple[str, type[Marketplace], str], ...]] = (
        (".claude-plugin/marketplace.json", ClaudeMarketplace, "./plugin"),
        (".cursor-plugin/marketplace.json", CursorMarketplace, "plugin"),
    )
    root: Path

    @cached_property
    def plugin(self) -> Plugin:
        return Plugin(self.root / "plugin")

    @property
    def changelog_path(self) -> Path:
        return self.root / "CHANGELOG.md"

    @cached_property
    def changelog(self) -> Document:
        return Document(self.changelog_path)

    @property
    def releases(self) -> list[Section]:
        sections = self.changelog.sections
        if sections and sections[0].title == "[Unreleased]":
            return sections[1:]
        return sections

    @property
    def pyproject_path(self) -> Path:
        return self.root / "pyproject.toml"

    @property
    def license_path(self) -> Path:
        return self.root / Plugin.LICENSE

    def problems(self) -> list[Problem]:
        plugin_problems = self.plugin.problems()
        if self.plugin.is_unsafe_to_read:
            return plugin_problems
        manifest = None if self.plugin.manifest_problems else self.plugin.manifest
        return [
            *plugin_problems,
            *[
                *self.marketplace_problems(self.root / relative, kind, source, manifest)
                for relative, kind, source in self.MARKETPLACES
            ],
            *self.changelog_problems(manifest),
            *self.pyproject_problems(manifest),
            *self.package_problems(manifest),
            *self.license_problems(),
        ]

    def marketplace_problems(
        self,
        path: Path,
        kind: type[Marketplace],
        source: str,
        manifest: Manifest | None,
    ) -> list[Problem]:
        if not path.is_file():
            return [
                Problem(
                    path, "is missing; add it, since its host lists the plugin from it"
                )
            ]
        try:
            marketplace = kind.read(path)
        except InvalidMetadataError as error:
            return [Problem(path, f"is invalid: {error}")]
        if len(marketplace.plugins) != 1:
            return [
                Problem(
                    path,
                    f"lists {len(marketplace.plugins)} plugins, where it needs "
                    "exactly 1; list only this plugin",
                )
            ]
        (entry,) = marketplace.plugins
        expected = {"source": source}
        if manifest is not None:
            expected |= {"name": manifest.name, "description": manifest.description}
        differing = [
            field for field, value in expected.items() if getattr(entry, field) != value
        ]
        if differing:
            return [
                Problem(
                    path,
                    f"lists the plugin with a different {', '.join(differing)}; "
                    f"use the plugin manifest's name and description, "
                    f"and the source {source!r}",
                )
            ]
        return []

    def changelog_problems(self, manifest: Manifest | None) -> list[Problem]:
        if not self.changelog_path.is_file():
            return [
                Problem(
                    self.changelog_path,
                    "is missing; add it with an entry for each release",
                )
            ]
        if (reason := self.changelog.unreadable) is not None:
            return [Problem(self.changelog_path, reason)]
        titles = [section.title for section in self.releases]
        entries = [self.ENTRY.fullmatch(title) for title in titles]
        problems = [
            Problem(
                self.changelog_path,
                f"has an entry titled {title!r}; "
                "title it '[<version>] - <YYYY-MM-DD>' with the release's version",
            )
            if entry is None
            else Problem(
                self.changelog_path,
                f"has an entry dated {entry['date']}, which is no real day; "
                "date it with the release day",
            )
            for title, entry in zip(titles, entries, strict=True)
            if entry is None or not self.is_date(entry["date"])
        ]
        versions = [entry["version"] for entry in entries if entry is not None]
        problems += [
            Problem(
                self.changelog_path,
                f"has more than one entry for {version}; merge them into one",
            )
            for version in sorted(
                {each for each in versions if versions.count(each) > 1}
            )
        ]
        listed = [entry for entry in entries if entry is not None]
        problems += [
            Problem(
                self.changelog_path,
                f"has the entry for {above['version']} above the one for "
                f"{below['version']}; list releases newest first, by version",
            )
            for above, below in pairwise(listed)
            if self.version_order(above["version"])
            < self.version_order(below["version"])
        ]
        problems += [
            Problem(
                self.changelog_path,
                f"has the entry dated {above['date']} above the one dated "
                f"{below['date']}; list releases newest first, by date",
            )
            for above, below in pairwise(listed)
            if above["date"] < below["date"]
        ]
        if manifest is None:
            return problems
        version = manifest.version
        top = entries[0] if entries else None
        if top is None and problems:
            return problems
        if top is None or top["version"] != version:
            return [
                *problems,
                Problem(
                    self.changelog_path,
                    f"does not open with the entry for {version}; "
                    f"add a '## [{version}] - <release date>' section "
                    "above the other releases",
                ),
            ]
        notes = self.release_notes()
        if not notes.strip():
            problems.append(
                Problem(
                    self.changelog_path,
                    f"has an empty entry for {version}; "
                    "list what the release changes under it",
                )
            )
        if not self.changelog.stands_alone(notes):
            problems.append(
                Problem(
                    self.changelog_path,
                    f"has an entry for {version} that reads differently on its own: "
                    "a reference it uses is defined elsewhere in the changelog; "
                    "define it inside the entry",
                )
            )
        return problems

    @staticmethod
    def is_date(text: str) -> bool:
        try:
            date.fromisoformat(text)
        except ValueError:
            return False
        return True

    @staticmethod
    def version_order(version: str) -> tuple[tuple[int, str], ...]:
        # Each part orders by its length, then its digits, since int() refuses a part
        # longer than Python's digit limit:
        # https://docs.python.org/3/library/stdtypes.html#int-max-str-digits
        return tuple((len(part), part) for part in version.split("."))

    def release_notes(self) -> str:
        return self.releases[0].body

    def pyproject_problems(self, manifest: Manifest | None) -> list[Problem]:
        if not self.pyproject_path.is_file():
            return [
                Problem(
                    self.pyproject_path, "is missing; add it with the harness's project"
                )
            ]
        try:
            version = Pyproject.read(self.pyproject_path).project.version
        except InvalidPyprojectError as error:
            return [Problem(self.pyproject_path, f"is invalid: {error}")]
        if manifest is None:
            return []
        if version != manifest.version:
            return [
                Problem(
                    self.pyproject_path,
                    "has a version that differs from the plugin manifests; "
                    "use the manifests' version",
                )
            ]
        return []

    def package_problems(self, manifest: Manifest | None) -> list[Problem]:
        path = self.plugin.root / "package.json"
        if not path.is_file():
            return [
                Problem(
                    path,
                    "is missing; add it with the plugin's name and version, "
                    "so OpenCode can load the plugin",
                )
            ]
        try:
            package = Package.read(path)
        except InvalidMetadataError as error:
            return [Problem(path, f"is invalid: {error}")]
        if manifest is None or (package.name, package.version) == (
            manifest.name,
            manifest.version,
        ):
            return []
        fields = " and ".join(
            field
            for field in ("name", "version")
            if getattr(package, field) != getattr(manifest, field)
        )
        return [
            Problem(
                path,
                f"has a {fields} that {'differ' if ' and ' in fields else 'differs'} "
                "from the plugin manifests; "
                f"use the manifests' {fields}",
            )
        ]

    def license_problems(self) -> list[Problem]:
        if not self.license_path.is_file():
            return [Problem(self.license_path, "is missing; add the project's license")]
        copy = self.plugin.root / Plugin.LICENSE
        try:
            differs = copy.is_file() and (
                copy.read_bytes() != self.license_path.read_bytes()
            )
        except OSError as error:
            return [Problem(Path(error.filename), cannot_read(error))]
        if differs:
            return [
                Problem(
                    copy,
                    "differs from the repository's LICENSE; "
                    "copy the repository's LICENSE over it",
                )
            ]
        return []
