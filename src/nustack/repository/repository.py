"""The rules that tie the plugin to the files released and configured beside it.

Every file a release needs is present and readable, and every source and test
folder lists. The marketplaces list the plugin as its manifests describe it, the
changelog and the harness carry its version, the loader's package agrees with it,
and it ships the repository's license unchanged. The vendored copy is left as
written, the test suite mirrors what it tests, and the README activates nus-mode as
its playbook says. A repository that keeps every rule yields what the release ships.
"""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar
from typing import assert_never

from nustack.markdown.document import Document
from nustack.plugin.manifest import ClaudeMarketplace
from nustack.plugin.manifest import CursorMarketplace
from nustack.plugin.manifest import InvalidMetadataError
from nustack.plugin.manifest import Manifest
from nustack.plugin.manifest import Marketplace
from nustack.plugin.manifest import Package
from nustack.plugin.plugin import Plugin
from nustack.problem import Problem
from nustack.repository.changelog import Changelog
from nustack.repository.pyproject import InvalidPyprojectError
from nustack.repository.pyproject import Pyproject
from nustack.repository.suite import Suite
from nustack.repository.vendored import Hooks
from nustack.repository.vendored import InvalidConfigError
from nustack.repository.vendored import VendoredCopy
from nustack.repository.vendored import Workflow
from nustack.tree import Absent
from nustack.tree import File
from nustack.tree import Snapshot
from nustack.tree import Tree
from nustack.tree import Unreadable
from nustack.validation import version_order


@dataclass(frozen=True)
class Release:
    """What a clean check releases: the plugin's files, its manifest and its notes."""

    tree: Tree
    manifest: Manifest
    notes: str


@dataclass(frozen=True)
class Repository:
    """The nustack repository: the plugin and the files released with it.

    A release sets the new version in every file that holds one, so each file still
    behind the newest is named, whichever was bumped. The changelog's links are
    checked once its entries are right, since a link's target names the newest
    release.
    """

    PLUGIN: ClassVar[PurePosixPath] = PurePosixPath("plugin")
    CHANGELOG: ClassVar[PurePosixPath] = PurePosixPath("CHANGELOG.md")
    LICENSE: ClassVar[PurePosixPath] = PurePosixPath("LICENSE")
    README: ClassVar[PurePosixPath] = PurePosixPath("README.md")
    CLAUDE_MARKETPLACE: ClassVar[PurePosixPath] = PurePosixPath(
        ".claude-plugin/marketplace.json"
    )
    CURSOR_MARKETPLACE: ClassVar[PurePosixPath] = PurePosixPath(
        ".cursor-plugin/marketplace.json"
    )
    MARKETPLACES: ClassVar[frozendict[PurePosixPath, tuple[type[Marketplace], str]]] = (
        frozendict(
            {
                CLAUDE_MARKETPLACE: (ClaudeMarketplace, f"./{PLUGIN}"),
                CURSOR_MARKETPLACE: (CursorMarketplace, str(PLUGIN)),
            }
        )
    )
    NEW_PROJECT: ClassVar[PurePosixPath] = PurePosixPath(
        "skills/nus-mode/playbooks/new-project.md"
    )
    ACTIVATION: ClassVar[str] = "markdown"
    FILES: ClassVar[tuple[PurePosixPath, ...]] = (
        CHANGELOG,
        LICENSE,
        README,
        *MARKETPLACES,
        VendoredCopy.PYPROJECT,
        VendoredCopy.HOOKS,
        VendoredCopy.WORKFLOW,
    )
    SOURCES: ClassVar[PurePosixPath] = Suite.PYTHON_SOURCES
    TESTS: ClassVar[PurePosixPath] = Suite.TESTS
    snapshot: Snapshot

    @property
    def root(self) -> Path:
        return self.snapshot.root

    @cached_property
    def plugin(self) -> Plugin:
        return Plugin(self.snapshot.plugin)

    @cached_property
    def changelog(self) -> Changelog | Problem:
        match self.document(
            self.CHANGELOG, "is missing; add it with an entry for each release"
        ):
            case Document() as document:
                return Changelog(document)
            case problem:
                return problem

    @cached_property
    def pyproject(self) -> Pyproject | Problem:
        match self.content(
            VendoredCopy.PYPROJECT, "is missing; add it with the harness's project"
        ):
            case bytes() as content:
                try:
                    return Pyproject.parse(content)
                except InvalidPyprojectError as error:
                    return Problem(
                        self.root / VendoredCopy.PYPROJECT, f"is invalid: {error}"
                    )
            case problem:
                return problem

    @cached_property
    def package(self) -> Package | Problem | None:
        path = self.plugin.root / Plugin.PACKAGE
        match self.plugin.tree.read(Plugin.PACKAGE):
            case File(content=content):
                try:
                    return Package.parse(content)
                except InvalidMetadataError as error:
                    return Problem(path, f"is invalid: {error}")
            case Absent() as absent:
                return Problem(
                    path,
                    absent.absence(
                        "is missing; add it with the plugin's name and version, "
                        "so OpenCode can load the plugin"
                    ),
                )
            case Unreadable():
                return None
            case unexpected:
                assert_never(unexpected)

    def release(self) -> Release | list[Problem]:
        problems = self.problems()
        manifest = self.plugin.manifest
        changelog = self.changelog
        match problems, manifest, changelog:
            case [], Manifest(), Changelog():
                return Release(self.plugin.tree, manifest, changelog.release_notes)
            case _:
                return problems

    def problems(self) -> list[Problem]:
        plugin_problems = self.plugin.problems()
        if self.plugin.unsafe:
            return plugin_problems
        manifest = self.plugin.manifest
        return [
            *plugin_problems,
            *self.marketplace_problems(manifest),
            *self.version_problems(),
            *self.changelog_problems(manifest),
            *self.pyproject_problems(),
            *self.package_problems(manifest),
            *self.license_problems(),
            *self.vendored_problems(),
            *self.activation_problems(),
            *(
                Problem(self.root / path, entry.reason)
                for path, entry in self.snapshot.unlisted.items()
            ),
            *Suite(
                self.root,
                frozenset(
                    (
                        *self.snapshot.sources,
                        *(
                            self.PLUGIN / path
                            for path, entry in self.plugin.tree.entries.items()
                            if isinstance(entry, File | Unreadable)
                        ),
                    )
                ),
                self.snapshot.tests,
            ).problems(),
        ]

    def marketplace_problems(self, manifest: Manifest | None) -> list[Problem]:
        problems: list[Problem] = []
        found: dict[PurePosixPath, Marketplace] = {}
        for path, (kind, source) in self.MARKETPLACES.items():
            match self.content(
                path, "is missing; add it, since its host lists the plugin from it"
            ):
                case bytes() as content:
                    try:
                        found[path] = kind.parse(content)
                    except InvalidMetadataError as error:
                        problems.append(
                            Problem(self.root / path, f"is invalid: {error}")
                        )
                    else:
                        problems += self.entry_problems(
                            path, found[path], source, manifest
                        )
                case problem:
                    problems.append(problem)
        if len(found) == len(self.MARKETPLACES):
            problems += self.agreement_problems(
                found[self.CLAUDE_MARKETPLACE], found[self.CURSOR_MARKETPLACE]
            )
        if manifest is not None:
            problems += [
                Problem(
                    self.root / marketplace_path,
                    "names an owner other than the plugin manifests' author; "
                    "make the owner the manifests' author",
                )
                for marketplace_path, marketplace in found.items()
                if marketplace.owner != manifest.author
            ]
        return problems

    def entry_problems(
        self,
        path: PurePosixPath,
        marketplace: Marketplace,
        source: str,
        manifest: Manifest | None,
    ) -> list[Problem]:
        if len(marketplace.plugins) != 1:
            return [
                Problem(
                    self.root / path,
                    f"lists {len(marketplace.plugins)} plugins, where it needs "
                    "exactly 1; list only this plugin",
                )
            ]
        (entry,) = marketplace.plugins
        differing = [] if entry.source == source else ["source"]
        if manifest is not None:
            differing += [
                field
                for field, (listed, declared) in {
                    "name": (entry.name, manifest.name),
                    "description": (entry.description, manifest.description),
                }.items()
                if listed != declared
            ]
        if not differing:
            return []
        return [
            Problem(
                self.root / path,
                f"lists the plugin with a different {', '.join(sorted(differing))}; "
                "use the plugin manifest's name and description, "
                f"and the source {source!r}",
            )
        ]

    def agreement_problems(
        self, claude: Marketplace, cursor: Marketplace
    ) -> list[Problem]:
        differing = [
            field
            for field, (left, right) in {
                "name": (claude.name, cursor.name),
                "description": (claude.description, cursor.description),
            }.items()
            if left != right
        ]
        if not differing:
            return []
        return [
            Problem(
                self.root / self.CURSOR_MARKETPLACE,
                f"has a different {' and '.join(differing)} from the Claude Code "
                f"marketplace; use one {' and '.join(differing)} for both",
            )
        ]

    def changelog_problems(self, manifest: Manifest | None) -> list[Problem]:
        changelog = self.changelog
        if isinstance(changelog, Problem):
            return [changelog]
        if manifest is None:
            return changelog.problems(None)
        return changelog.problems(manifest.version) or changelog.link_problems(
            str(manifest.repository).removesuffix("/")
        )

    def version_problems(self) -> list[Problem]:
        pyproject, package = self.pyproject, self.package
        versions = [
            *(
                (self.plugin.root / path, f"the {host} manifest", reading.version)
                # Both come from Plugin.MANIFESTS, so their lengths never differ and no
                # test tells strict from its default; Ruff asks for it:
                # https://docs.astral.sh/ruff/rules/zip-without-explicit-strict/
                for (path, host), reading in zip(
                    Plugin.MANIFESTS.items(),
                    self.plugin.manifest_readings,
                    strict=True,  # pragma: no mutate
                )
                if isinstance(reading, Manifest)
            ),
            *(
                [
                    (
                        self.root / VendoredCopy.PYPROJECT,
                        str(VendoredCopy.PYPROJECT),
                        pyproject.project.version,
                    )
                ]
                if isinstance(pyproject, Pyproject)
                else []
            ),
            *(
                [
                    (
                        self.plugin.root / Plugin.PACKAGE,
                        str(self.PLUGIN / Plugin.PACKAGE),
                        package.version,
                    )
                ]
                if isinstance(package, Package)
                else []
            ),
        ]
        if not versions:
            return []
        _, owner, newest = max(versions, key=lambda each: version_order(each[2]))
        return [
            Problem(
                path,
                f"has version {version}, older than {owner}'s {newest}; set every"
                " file nustack check compares to the release's version",
            )
            for path, _, version in versions
            if version != newest
        ]

    def pyproject_problems(self) -> list[Problem]:
        return [self.pyproject] if isinstance(self.pyproject, Problem) else []

    def package_problems(self, manifest: Manifest | None) -> list[Problem]:
        package = self.package
        if isinstance(package, Problem):
            return [package]
        if package is None or manifest is None or package.name == manifest.name:
            return []
        return [
            Problem(
                self.plugin.root / Plugin.PACKAGE,
                "has a name that differs from the plugin manifests; "
                "use the manifests' name",
            )
        ]

    def license_problems(self) -> list[Problem]:
        match self.content(self.LICENSE, "is missing; add the project's license"):
            case bytes() as content:
                pass
            case problem:
                return [problem]
        match self.plugin.tree.read(Plugin.LICENSE):
            case File(content=copied) if copied != content:
                return [
                    Problem(
                        self.plugin.root / Plugin.LICENSE,
                        "differs from the repository's LICENSE; "
                        "copy the repository's LICENSE over it",
                    )
                ]
            case _:
                return []

    def vendored_problems(self) -> list[Problem]:
        problems: list[Problem] = []
        configs: list[Hooks | Workflow] = []
        for path, kind in (
            (VendoredCopy.HOOKS, Hooks),
            (VendoredCopy.WORKFLOW, Workflow),
        ):
            match self.content(path, "is missing; restore it from the repository"):
                case bytes() as content:
                    try:
                        configs.append(kind.parse(content))
                    except InvalidConfigError as error:
                        problems.append(
                            Problem(self.root / path, f"is invalid: {error}")
                        )
                case problem:
                    problems.append(problem)
        match configs, self.pyproject:
            case [Hooks() as hooks, Workflow() as workflow], Pyproject() as pyproject:
                return VendoredCopy(self.root, hooks, workflow, pyproject).problems()
            case _:
                return problems

    def activation_problems(self) -> list[Problem]:
        match self.document(self.README, "is missing; add it with the plugin's guide"):
            case Document() as readme:
                pass
            case problem:
                return [problem]
        playbook = self.plugin.documents.get(self.NEW_PROJECT)
        if playbook is None or self.activation(readme) == self.activation(playbook):
            return []
        return [
            Problem(
                readme.path,
                "has an activation line that differs from the new-project playbook's;"
                f" copy the playbook's {self.ACTIVATION} block into it",
            )
        ]

    def activation(self, document: Document) -> tuple[str, ...]:
        return tuple(
            fence.content for fence in document.fences if fence.info == self.ACTIVATION
        )

    def document(self, path: PurePosixPath, missing: str) -> Document | Problem:
        return Document.of(self.root / path, self.snapshot.read(path), missing)

    def content(self, path: PurePosixPath, missing: str) -> bytes | Problem:
        match self.snapshot.read(path):
            case File(content=content):
                return content
            case Absent() as absent:
                return Problem(self.root / path, absent.absence(missing))
            case Unreadable(reason=reason):
                return Problem(self.root / path, reason)
            case unexpected:
                assert_never(unexpected)
