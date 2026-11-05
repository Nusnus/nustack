"""The rules that tie the plugin to the files released and configured beside it.

Every file a release needs is present and readable, and every source and test
folder lists. The marketplaces list the plugin as its manifests describe it, the
changelog and the harness carry its version, the harness's commitizen settings name
every file that holds it and the form of its release tag, which the release
workflow's tag filter matches, the loader's package agrees with it, and it ships the
repository's license unchanged. The vendored copy is left as written, the test suite
mirrors what it tests, and the README activates nus-mode as its playbook says, gives
each principle and language skill its description, and holds the install and use
steps the release page copies. Joined on the page, those steps and the changelog
entry each resolve every reference label they use as they do on their own. A
repository that keeps every rule yields what the release ships: the plugin and its
release page.
"""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar
from typing import assert_never
lazy from collections.abc import Callable

from nustack.markdown.document import Document
from nustack.markdown.table import Tables
from nustack.plugin.manifest import ClaudeMarketplace
from nustack.plugin.manifest import CursorMarketplace
from nustack.plugin.manifest import InvalidMetadataError
from nustack.plugin.manifest import Manifest
from nustack.plugin.manifest import Marketplace
from nustack.plugin.manifest import Package
from nustack.plugin.plugin import Plugin
from nustack.plugin.skill import Frontmatter
from nustack.plugin.skill import Skill
from nustack.problem import Problem
from nustack.release.tag import Tag
from nustack.repository.changelog import Changelog
from nustack.repository.config import InvalidConfigError
from nustack.repository.notes import ReleaseNotes
from nustack.repository.page import PageSteps
from nustack.repository.pyproject import InvalidPyprojectError
from nustack.repository.pyproject import Pyproject
from nustack.repository.release_workflow import ReleaseWorkflow
from nustack.repository.suite import Suite
from nustack.repository.vendored import Hooks
from nustack.repository.vendored import SyncWorkflow
from nustack.repository.vendored import VendoredCopy
from nustack.tree import Absent
from nustack.tree import Blocked
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Missing
from nustack.tree import Snapshot
from nustack.tree import Special
from nustack.tree import Tree
from nustack.tree import Unreadable
from nustack.version import Version
from nustack.version import version_order


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
    checked beside its entries: each release's tag link against its own version, and
    `[Unreleased]` and the plugin version's own link against the plugin's version. So
    whoever drafts a release sees a missing link before the entry is correct, and never
    a fix that breaks a correct link.
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
    SKILL_TABLE: ClassVar[tuple[str, ...]] = ("Skill", "What it holds")
    RESTORE: ClassVar[str] = "is missing; restore it from the repository"
    FILES: ClassVar[tuple[PurePosixPath, ...]] = (
        CHANGELOG,
        LICENSE,
        README,
        *MARKETPLACES,
        Pyproject.PATH,
        Hooks.PATH,
        SyncWorkflow.PATH,
        ReleaseWorkflow.PATH,
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
    def readme(self) -> Document | Problem:
        return self.document(self.README, "is missing; add it with the plugin's guide")

    @cached_property
    def page_steps(self) -> PageSteps | Problem:
        readme = self.readme
        return readme if isinstance(readme, Problem) else PageSteps(readme)

    @cached_property
    def notes(self) -> ReleaseNotes | None:
        match self.plugin.manifest, self.changelog, self.page_steps:
            case (
                Manifest() as manifest,
                Changelog() as changelog,
                PageSteps(sections=frozendict() as steps),
            ) if changelog.opens_with(manifest.version):
                return ReleaseNotes(
                    manifest, changelog.entry, steps, changelog.previous
                )
            case _:
                return None

    @cached_property
    def pyproject(self) -> Pyproject | Problem:
        return self.parsed(
            Pyproject.PATH,
            "is missing; add it with the harness's project",
            Pyproject.parse,
            InvalidPyprojectError,
        )

    @cached_property
    def package(self) -> Package | Problem | None:
        path = self.plugin.root / Plugin.PACKAGE
        match self.plugin.tree.read(Plugin.PACKAGE):
            case File(content=content):
                return Problem.parsed(
                    path, content, Package.parse, InvalidMetadataError
                )
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
        match problems, self.notes:
            case [], ReleaseNotes() as notes:
                return Release(self.plugin.tree, notes.manifest, notes.text)
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
            *self.version_files_problems(),
            *self.tag_format_problems(),
            *self.release_workflow_problems(),
            *self.changelog_problems(manifest),
            *self.pyproject_problems(),
            *self.package_problems(manifest),
            *self.license_problems(),
            *self.vendored_problems(),
            *self.activation_problems(),
            *self.skill_table_problems(),
            *self.page_steps_problems(),
            *self.page_label_problems(),
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
            match self.parsed(
                path,
                "is missing; add it, since its host lists the plugin from it",
                kind.parse,
                InvalidMetadataError,
            ):
                case Problem() as problem:
                    problems.append(problem)
                case marketplace:
                    found[path] = marketplace
                    problems += self.entry_problems(path, marketplace, source, manifest)
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

    def version_problems(self) -> list[Problem]:
        versions = [
            (path, owner, version)
            for path, owner, version in self.versioned_files()
            if version is not None
        ]
        if not versions:
            return []
        _, owner, newest = max(versions, key=lambda each: version_order(each[2]))
        return [
            Problem(
                self.root / path,
                f"has version {version}, older than {owner}'s {newest}; set every"
                " file nustack check compares to the release's version",
            )
            for path, _, version in versions
            if version != newest
        ]

    def version_files_problems(self) -> list[Problem]:
        pyproject = self.pyproject
        if isinstance(pyproject, Problem):
            return []
        # commitizen's uv provider sets pyproject.toml's version, so version_files
        # lists only the other files:
        # https://commitizen-tools.github.io/commitizen/config/version_provider/#uv
        others = sorted(
            path for path, _, _ in self.versioned_files() if path != Pyproject.PATH
        )
        listed = sorted(
            PurePosixPath(entry.partition(":")[0])
            for entry in pyproject.tool.commitizen.version_files
        )
        if listed == others:
            return []
        return [
            Problem(
                self.root / Pyproject.PATH,
                "has a [tool.commitizen] version_files that differs from the other"
                " files whose version nustack check compares; list each of "
                f"{', '.join(map(str, others))} once, so cz bump sets the version in"
                " each",
            )
        ]

    def tag_format_problems(self) -> list[Problem]:
        # cz bump finds the last release by tag_format:
        # https://commitizen-tools.github.io/commitizen/config/bump/#tag_format
        pyproject = self.pyproject
        if isinstance(pyproject, Problem):
            return []
        tag_format = f"{Tag.PREFIX}$version"
        match pyproject.tool.commitizen.tag_format:
            case None:
                what = "has no [tool.commitizen] tag_format"
            case str(given) if given != tag_format:
                what = (
                    "has a [tool.commitizen] tag_format other than the release tags'"
                    " form"
                )
            case _:
                return []
        return [
            Problem(
                self.root / Pyproject.PATH,
                f"{what}; set it to {tag_format}, so cz bump finds the last release",
            )
        ]

    def release_workflow_problems(self) -> list[Problem]:
        # GitHub starts the release workflow for a pushed tag its push tags filter
        # matches:
        # https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushpull_requestpull_request_targetpathspaths-ignore
        tags = f"{Tag.PREFIX}*"
        match self.parsed(
            ReleaseWorkflow.PATH,
            self.RESTORE,
            ReleaseWorkflow.parse,
            InvalidConfigError,
        ):
            case Problem() as problem:
                return [problem]
            case workflow if workflow.on.push.tags == ():
                what = "has no push tags filter"
            case workflow if workflow.on.push.tags != (tags,):
                what = "has a push tags filter other than the release tags' form"
            case _:
                return []
        return [
            Problem(
                self.root / ReleaseWorkflow.PATH,
                f'{what}; set on.push.tags to ["{tags}"], so each release tag'
                " starts it",
            )
        ]

    def versioned_files(self) -> list[tuple[PurePosixPath, str, Version | None]]:
        pyproject, package = self.pyproject, self.package
        return [
            *(
                (
                    self.PLUGIN / path,
                    f"the {host} manifest",
                    reading.version if isinstance(reading, Manifest) else None,
                )
                # Both come from Plugin.MANIFESTS, so their lengths never differ and no
                # test tells strict from its default; Ruff asks for it:
                # https://docs.astral.sh/ruff/rules/zip-without-explicit-strict/
                # mutmut skips every mutant of a node that spans a pragma's line, so
                # this one also skips dropping manifest_readings from the zip, which
                # tests kill.
                for (path, host), reading in zip(
                    Plugin.MANIFESTS.items(),
                    self.plugin.manifest_readings,
                    strict=True,  # pragma: no mutate
                )
            ),
            (
                Pyproject.PATH,
                str(Pyproject.PATH),
                pyproject.project.version if isinstance(pyproject, Pyproject) else None,
            ),
            (
                self.PLUGIN / Plugin.PACKAGE,
                str(self.PLUGIN / Plugin.PACKAGE),
                package.version if isinstance(package, Package) else None,
            ),
        ]

    def changelog_problems(self, manifest: Manifest | None) -> list[Problem]:
        changelog = self.changelog
        if isinstance(changelog, Problem):
            return [changelog]
        if manifest is None:
            return changelog.problems(None)
        return [
            *changelog.problems(manifest.version),
            *changelog.link_problems(manifest.repository, manifest.version),
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
            case File() | Folder() | Special() | Missing() | Blocked() | Unreadable():
                return []
            case unexpected:
                assert_never(unexpected)

    def vendored_problems(self) -> list[Problem]:
        problems: list[Problem] = []
        configs: list[Hooks | SyncWorkflow] = []
        for kind in (Hooks, SyncWorkflow):
            match self.parsed(kind.PATH, self.RESTORE, kind.parse, InvalidConfigError):
                case Problem() as problem:
                    problems.append(problem)
                case config:
                    configs.append(config)
        match configs, self.pyproject:
            case (
                [Hooks() as hooks, SyncWorkflow() as workflow],
                Pyproject() as pyproject,
            ):
                return VendoredCopy(self.root, hooks, workflow, pyproject).problems()
            case _:
                return problems

    def activation_problems(self) -> list[Problem]:
        readme = self.readme
        if isinstance(readme, Problem):
            return []
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

    def skill_table_problems(self) -> list[Problem]:
        readme = self.readme
        if isinstance(readme, Problem):
            return []
        # GitHub shows frontmatter as a table of its keys, never as Markdown, so rows
        # count from the body, each named at its line in the whole file.
        tables = [
            table
            for table in Tables(readme).tables
            if tuple(cell.text for cell in table.header) == self.SKILL_TABLE
        ]
        hidden = self.hidden_descriptions()
        if hidden and not tables:
            return [
                Problem(
                    readme.path,
                    f"has no table headed {' and '.join(self.SKILL_TABLE)}; add one"
                    " with a row giving each principle and language skill's"
                    " description",
                )
            ]
        rows = [row for table in tables for row in table.body]
        files = {
            self.root / self.skill_file(skill.name): skill.name
            for skill in self.plugin.skills
            if isinstance(skill.read, File | Unreadable)
        }
        targets = {
            link.line: link.target
            for row in rows
            if (href := row.cells[0].href) is not None
            and (link := readme.link(href, row.line)) is not None
        }
        # Where plugin/skills/ is no folder, its own Problem says so, and no row is
        # stale for it.
        problems = [
            Problem(
                readme.path,
                f"has a skills table row on line {readme.file_line(row.line)} whose"
                " first cell links no skill; start it with a link to the skill's"
                " SKILL.md, or remove the row",
            )
            if row.cells[0].href is None
            else Problem(
                readme.path,
                f"has a skills table row on line {readme.file_line(row.line)} linking"
                f" {row.cells[0].href}, which is no skill's SKILL.md; link a skill's"
                " SKILL.md, or remove the row",
            )
            for row in rows
            if targets.get(row.line) not in files
            and isinstance(self.plugin.tree.entries.get(Plugin.SKILLS), Folder)
        ]
        for path, name in files.items():
            lines = [
                str(readme.file_line(row.line))
                for row in rows
                if targets.get(row.line) == path
            ]
            if len(lines) > 1:
                problems.append(
                    Problem(
                        readme.path,
                        f"has more than one skills table row for {name}, on lines"
                        f" {', '.join(lines)}; keep the first and remove the rest",
                    )
                )
        for skill, description in hidden:
            row = next(
                (
                    row
                    for row in rows
                    if targets.get(row.line) == self.root / self.skill_file(skill.name)
                ),
                None,
            )
            if row is None:
                problems.append(
                    Problem(
                        readme.path,
                        f"has no skills table row for {skill.name}; add one that links"
                        f" {self.skill_file(skill.name)} under its name and copies its"
                        " description",
                    )
                )
                continue
            if row.cells[0].label != skill.name:
                problems.append(
                    Problem(
                        readme.path,
                        f"has a skills table row on line {readme.file_line(row.line)}"
                        f" whose link text is not {skill.name}; make it {skill.name}",
                    )
                )
            if row.cells[1].text != description:
                problems.append(
                    Problem(
                        readme.path,
                        f"has a skills table row on line {readme.file_line(row.line)}"
                        f" whose description differs from {skill.name}'s; copy the"
                        f" description from {self.skill_file(skill.name)} into it",
                    )
                )
        return problems

    def hidden_descriptions(self) -> list[tuple[Skill, str]]:
        descriptions: list[tuple[Skill, str]] = []
        for skill in self.plugin.skills:
            document = skill.document
            if document is None:
                continue
            frontmatter = skill.read_frontmatter(document)
            if isinstance(frontmatter, Frontmatter) and frontmatter.hidden_from_model:
                descriptions.append((skill, frontmatter.description))
        return descriptions

    def skill_file(self, name: str) -> str:
        return f"{self.PLUGIN}/{Plugin.SKILLS}/{name}/{Skill.FILE}"

    def page_steps_problems(self) -> list[Problem]:
        page_steps = self.page_steps
        return [page_steps] if isinstance(page_steps, Problem) else page_steps.problems

    def page_label_problems(self) -> list[Problem]:
        match self.notes, self.changelog, self.page_steps:
            case (
                ReleaseNotes() as notes,
                Changelog() as changelog,
                PageSteps() as steps,
            ):
                definitions = Document.defined_in(notes.text)
                parts = (
                    changelog.entry_part(notes.manifest.version),
                    *(part for parts in steps.parts.values() for part in parts),
                )
                return [
                    problem
                    for part in parts
                    for problem in part.page_problems(definitions)
                ]
            case _:
                return []

    def document(self, path: PurePosixPath, missing: str) -> Document | Problem:
        return Document.of(self.root / path, self.snapshot.read(path), missing)

    def parsed[T](
        self,
        path: PurePosixPath,
        missing: str,
        parse: Callable[[bytes], T],
        invalid: type[ValueError],
    ) -> T | Problem:
        match self.content(path, missing):
            case bytes() as content:
                return Problem.parsed(self.root / path, content, parse, invalid)
            case problem:
                return problem

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
