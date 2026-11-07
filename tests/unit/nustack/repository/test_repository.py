"""The plugin's release agrees with every file released and configured beside it.

Each required file is present and readable, every source and test folder lists, the
marketplaces, versions, package and license agree with the plugin, the README activates
nus-mode as its playbook says, its skills table lists each skill under its link and
description, it holds the install and use steps the release page copies, those steps and
the changelog entry resolve each reference label the same on the page that joins them as
on their own, and only a repository every check passes yields a release.
"""

import json
from pathlib import PurePosixPath

import pytest

from nustack.problem import Problem
from nustack.repository.repository import Release
from nustack.repository.repository import Repository
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Missing
from nustack.tree import Special
from nustack.tree import Unopened
from nustack.tree import Unreadable
lazy from tests.fixtures.repository import ModelRepository


class TestRepositoryRelease:
    """What the release workflow ships comes from a repository every check passes."""

    def test_releases_the_plugin_its_manifest_and_its_notes(
        self, repository: ModelRepository
    ) -> None:
        release = Repository(repository.snapshot()).release()
        assert isinstance(release, Release)
        assert (
            release.tree.read(PurePosixPath("LICENSE")),
            release.manifest.version,
            release.notes,
        ) == (
            File(b"MIT License\n"),
            "1.2.3",
            (
                "> **[kit](https://example.com/nus/kit)** · A kit.\n\n"
                "## 🆕 What's new\n\n### Added\n\n- Adds the kit.\n\n"
                "## 🚀 Quick start\n\n### 1️⃣ Install\n\nRun `kit add`.\n\n"
                "### 2️⃣ Use\n\nRun `kit`.\n\n"
                "**Full changelog:** [`v1.2.2...v1.2.3`]"
                "(https://example.com/nus/kit/compare/v1.2.2...v1.2.3)"
            ),
        )

    def test_releases_nothing_while_a_check_fails(
        self, repository: ModelRepository
    ) -> None:
        repository.remove("README.md")
        assert Repository(repository.snapshot()).release() == [
            Problem(
                repository.where("README.md"),
                "is missing; add it with the plugin's guide",
            )
        ]


class TestRepositoryFiles:
    """Each required file and listed record is present and readable.

    Versions compare where valid, and vendored/ holds only records the sync reads.
    """

    UNREADABLE = "cannot be read (Permission denied); make it readable"

    @pytest.mark.parametrize(
        ("path", "what"),
        [
            ("CHANGELOG.md", "is missing; add it with an entry for each release"),
            ("pyproject.toml", "is missing; add it with the harness's project"),
            ("LICENSE", "is missing; add the project's license"),
            ("README.md", "is missing; add it with the plugin's guide"),
            (
                ".claude-plugin/marketplace.json",
                "is missing; add it, since its host lists the plugin from it",
            ),
        ],
    )
    def test_reports_a_missing_file(
        self, repository: ModelRepository, path: str, what: str
    ) -> None:
        repository.remove(path)
        assert repository.problems() == [Problem(repository.where(path), what)]

    @pytest.mark.parametrize(
        "path",
        [
            "CHANGELOG.md",
            "pyproject.toml",
            "LICENSE",
            "README.md",
            ".cursor-plugin/marketplace.json",
            ".pre-commit-config.yaml",
            ".gitattributes",
        ],
    )
    def test_reports_a_file_that_cannot_be_read(
        self, repository: ModelRepository, path: str
    ) -> None:
        repository.fail_read(path, Unreadable(self.UNREADABLE))
        assert repository.problems() == [
            Problem(repository.where(path), self.UNREADABLE)
        ]

    @pytest.mark.parametrize(
        "path",
        [
            "CHANGELOG.md",
            "pyproject.toml",
            "LICENSE",
            "README.md",
            ".cursor-plugin/marketplace.json",
            ".pre-commit-config.yaml",
            ".gitattributes",
        ],
    )
    def test_reports_a_folder_in_place_of_a_file(
        self, repository: ModelRepository, path: str
    ) -> None:
        repository.fail_read(path, Folder())
        assert repository.problems() == [
            Problem(
                repository.where(path),
                "is a folder where a file belongs; move the folder, then add the file",
            )
        ]

    @pytest.mark.parametrize(
        "path", ["CHANGELOG.md", "pyproject.toml", ".claude-plugin/marketplace.json"]
    )
    def test_reports_a_pipe_in_place_of_a_file(
        self, repository: ModelRepository, path: str
    ) -> None:
        repository.fail_read(path, Special())
        assert repository.problems() == [
            Problem(
                repository.where(path),
                "is neither a file nor a folder; remove it, then add the file",
            )
        ]

    @pytest.mark.parametrize("path", ["CHANGELOG.md", "README.md"])
    def test_reports_markdown_that_is_not_utf8(
        self, repository: ModelRepository, path: str
    ) -> None:
        repository.write(path, b"\xff")
        assert repository.problems() == [
            Problem(repository.where(path), "is not valid UTF-8; save it as UTF-8")
        ]

    def test_compares_versions_with_the_valid_manifests_beside_an_invalid_one(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/.devin-plugin/plugin.json", "[]")
        repository.edit("pyproject.toml", '"1.2.3"', '"9.9.9"')
        assert repository.problems() == [
            Problem(
                repository.where("plugin/.devin-plugin/plugin.json"),
                "is invalid: the file: make it an object of keys and values",
            ),
            Problem(
                repository.where("plugin/.claude-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " pyproject.toml's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("plugin/.cursor-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " pyproject.toml's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("plugin/package.json"),
                "has version 1.2.3, older than"
                " pyproject.toml's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
        ]

    def test_compares_versions_while_the_valid_manifests_disagree(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/.devin-plugin/plugin.json", "[]")
        repository.edit("plugin/.cursor-plugin/plugin.json", '"1.2.3"', '"9.9.9"')
        repository.edit("pyproject.toml", '"1.2.3"', '"9.9.9"')
        assert repository.problems() == [
            Problem(
                repository.where("plugin/.devin-plugin/plugin.json"),
                "is invalid: the file: make it an object of keys and values",
            ),
            Problem(
                repository.where("plugin/.claude-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " the Cursor manifest's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("plugin/package.json"),
                "has version 1.2.3, older than"
                " the Cursor manifest's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
        ]

    def test_reports_a_listed_record_that_is_gone(
        self, repository: ModelRepository
    ) -> None:
        repository.fail_read("vendored/copy.json", Missing())
        assert repository.problems() == [
            Problem(
                repository.where("vendored/copy.json"),
                "is missing; restore the record from the repository",
            )
        ]

    def test_reports_a_record_whose_file_path_holds_a_character_outside_the_set(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            "vendored/copy.json",
            json.dumps(
                {
                    "upstream": "https://github.com/up/skills",
                    "source": "skills",
                    "folder": ".agents/skills",
                    "skills": ["vendored"],
                    "commit": "c" * 40,
                    "files": {
                        "vendored/LICENSE": "1" * 40,
                        "vendored/SKILL.md": "2" * 40,
                        "vendored/a b.md": "3" * 40,
                    },
                }
            ),
        )
        assert repository.problems() == [
            Problem(
                repository.where("vendored/copy.json"),
                "is invalid: files: for each key, write each part of the path in"
                " letters, digits, ., _ and - alone",
            )
        ]

    @pytest.mark.parametrize(
        "path",
        [
            "vendored/README.md",
            "vendored/copy.JSON",
            "vendored/sub/copy.json",
            "vendored/.hidden.json",
            "vendored/Foo Bar.json",
        ],
    )
    def test_reports_a_file_in_the_records_folder_that_the_sync_never_reads(
        self, repository: ModelRepository, path: str
    ) -> None:
        repository.write(path, "Notes.\n")
        assert repository.problems() == [
            Problem(
                repository.where(path),
                "is no record the sync reads; name it vendored/<copy>.json, with"
                " <copy> in kebab case such as obsidian-skills, or move it out of"
                " vendored/",
            )
        ]

    @pytest.mark.parametrize("path", [".pre-commit-config.yaml", ".gitattributes"])
    def test_reports_a_missing_config(
        self, repository: ModelRepository, path: str
    ) -> None:
        repository.remove(path)
        assert repository.problems() == [
            Problem(
                repository.where(path), "is missing; restore it from the repository"
            )
        ]

    def test_reports_attributes_that_are_not_utf_8(
        self, repository: ModelRepository
    ) -> None:
        repository.write(".gitattributes", b"plugin/** text eol=lf\n\xff\n")
        assert repository.problems() == [
            Problem(
                repository.where(".gitattributes"),
                "is not valid UTF-8; save it as UTF-8",
            )
        ]


class TestRepositoryMarketplaces:
    """Each marketplace lists the one plugin, as its manifests describe it.

    A file where the marketplaces folder belongs is named, a description that differs
    only in spaces differs, and an entry's source is checked beside broken manifests.
    """

    CLAUDE = ".claude-plugin/marketplace.json"
    CURSOR = ".cursor-plugin/marketplace.json"

    def test_reports_a_file_in_place_of_a_marketplaces_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.remove(self.CLAUDE)
        repository.write(".claude-plugin", "x")
        assert repository.problems() == [
            Problem(
                repository.where(self.CLAUDE),
                f"cannot be read, since {repository.where('.claude-plugin')} is a file"
                " where a folder belongs; move the file, then add the folder",
            )
        ]

    def test_reports_an_invalid_marketplace(self, repository: ModelRepository) -> None:
        repository.write(
            self.CLAUDE,
            json.dumps(ModelRepository.CLAUDE_MARKETPLACE_FIELDS | {"plugins": "kit"}),
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.CLAUDE),
                "is invalid: plugins: make it a list",
            )
        ]

    def test_reports_cursor_without_its_metadata(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.CURSOR, '"metadata": {"description": "Ada\'s kit."}, ', "")
        assert repository.problems() == [
            Problem(
                repository.where(self.CURSOR),
                "is invalid: metadata: add it",
            )
        ]

    @pytest.mark.parametrize(
        ("count", "what"),
        [
            (0, "lists 0 plugins, where it needs exactly 1; list only this plugin"),
            (2, "lists 2 plugins, where it needs exactly 1; list only this plugin"),
        ],
    )
    def test_reports_a_marketplace_that_lists_other_than_one_plugin(
        self, repository: ModelRepository, count: int, what: str
    ) -> None:
        entry = {"name": "kit", "source": "./plugin", "description": "A kit."}
        repository.write(
            self.CLAUDE,
            json.dumps(
                ModelRepository.CLAUDE_MARKETPLACE_FIELDS | {"plugins": [entry] * count}
            ),
        )
        assert repository.problems() == [Problem(repository.where(self.CLAUDE), what)]

    def test_names_each_field_an_entry_differs_in(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            self.CLAUDE,
            json.dumps(
                ModelRepository.CLAUDE_MARKETPLACE_FIELDS
                | {
                    "plugins": [
                        {"name": "kat", "source": "plugin", "description": "A kat."}
                    ]
                }
            ),
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.CLAUDE),
                "lists the plugin with a different description, name, source; use"
                " the plugin manifest's name and description, and the source"
                " './plugin'",
            )
        ]

    def test_counts_a_description_that_differs_only_in_spaces_as_different(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            self.CLAUDE, '"description": "A kit."', '"description": "A kit. "'
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.CLAUDE),
                "lists the plugin with a different description; use the plugin"
                " manifest's name and description, and the source './plugin'",
            )
        ]

    def test_checks_an_entry_source_beside_broken_manifests(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/.devin-plugin/plugin.json", "[]")
        repository.edit(self.CURSOR, '"source": "plugin"', '"source": "./plugin"')
        assert repository.problems() == [
            Problem(
                repository.where("plugin/.devin-plugin/plugin.json"),
                "is invalid: the file: make it an object of keys and values",
            ),
            Problem(
                repository.where(self.CURSOR),
                "lists the plugin with a different source; use the plugin manifest's"
                " name and description, and the source 'plugin'",
            ),
        ]

    @pytest.mark.parametrize(
        ("change", "what"),
        [
            (
                {"name": "kat"},
                (
                    "has a different name from the Claude Code marketplace; use one"
                    " name for both"
                ),
            ),
            (
                {"description": "Bo's kit."},
                (
                    "has a different description from the Claude Code marketplace; use"
                    " one description for both"
                ),
            ),
            (
                {"name": "kat", "description": "Bo's kit."},
                (
                    "has a different name and description from the Claude Code"
                    " marketplace; use one name and description for both"
                ),
            ),
        ],
    )
    def test_reports_marketplaces_that_disagree(
        self, repository: ModelRepository, change: dict[str, object], what: str
    ) -> None:
        repository.write(
            self.CLAUDE, json.dumps(ModelRepository.CLAUDE_MARKETPLACE_FIELDS | change)
        )
        assert repository.problems() == [Problem(repository.where(self.CURSOR), what)]

    def test_reports_an_owner_other_than_the_author(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            self.CLAUDE,
            json.dumps(
                ModelRepository.CLAUDE_MARKETPLACE_FIELDS | {"owner": {"name": "Bo"}}
            ),
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.CLAUDE),
                "names an owner other than the plugin manifests' author; make the"
                " owner the manifests' author",
            )
        ]


class TestRepositoryVersions:
    """The changelog and the harness carry the plugin's version.

    commitizen's version_files lists each other file whose version is compared, by its
    path, with or without a pattern, and its tag_format names a release's tag as
    v$version, as the release workflow's push tags filter does with v*; a missing
    [tool.commitizen] table breaks both commitizen settings. Nothing compares when no
    file holds a readable version. The changelog's links are checked against the
    plugin version and reported beside its entry's problems. A changelog without
    `[Unreleased]` is asked no link to it, and a repository URL's trailing slash is
    dropped.
    """

    def test_reports_a_harness_version_that_differs(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("pyproject.toml", '"1.2.3"', '"9.9.9"')
        assert repository.problems() == [
            Problem(
                repository.where("plugin/.devin-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " pyproject.toml's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("plugin/.claude-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " pyproject.toml's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("plugin/.cursor-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " pyproject.toml's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("plugin/package.json"),
                "has version 1.2.3, older than"
                " pyproject.toml's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
        ]

    def test_compares_no_version_when_no_file_holds_a_readable_one(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/.devin-plugin/plugin.json", "[]")
        repository.write("plugin/.claude-plugin/plugin.json", "[]")
        repository.write("plugin/.cursor-plugin/plugin.json", "[]")
        repository.write("plugin/package.json", "[]")
        repository.write("pyproject.toml", "[project\n")
        assert Repository(repository.snapshot()).version_problems() == []

    def test_names_each_file_behind_a_version_one_manifest_bumped(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("plugin/.claude-plugin/plugin.json", '"1.2.3"', '"1.2.4"')
        assert repository.problems() == [
            Problem(
                repository.where("plugin/.devin-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " the Claude Code manifest's 1.2.4; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("plugin/.cursor-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " the Claude Code manifest's 1.2.4; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("pyproject.toml"),
                "has version 1.2.3, older than"
                " the Claude Code manifest's 1.2.4; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("plugin/package.json"),
                "has version 1.2.3, older than"
                " the Claude Code manifest's 1.2.4; set every file nustack check"
                " compares to the release's version",
            ),
        ]

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            ('  "plugin/package.json:version",\n', ""),
            (
                '  "plugin/package.json:version",\n',
                '  "plugin/package.json:version",\n  "plugin/LICENSE",\n',
            ),
            (
                '  "plugin/package.json:version",\n',
                '  "plugin/package.json:version",\n  "plugin/package.json",\n',
            ),
        ],
        ids=["missing", "extra", "twice"],
    )
    def test_reports_version_files_that_differ_from_the_compared_files(
        self, repository: ModelRepository, old: str, new: str
    ) -> None:
        repository.edit("pyproject.toml", old, new)
        assert repository.problems() == [
            Problem(
                repository.where("pyproject.toml"),
                "has a [tool.commitizen] version_files that differs from the other"
                " files whose version nustack check compares; list each of"
                " plugin/.claude-plugin/plugin.json, plugin/.cursor-plugin/plugin.json,"
                " plugin/.devin-plugin/plugin.json, plugin/package.json once, so cz"
                " bump sets the version in each",
            )
        ]

    def test_accepts_a_version_file_listed_with_no_pattern(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "pyproject.toml", '"plugin/package.json:version"', '"plugin/package.json"'
        )
        assert repository.problems() == []

    def test_reports_a_missing_commitizen_table(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("pyproject.toml", "[tool.commitizen]\n", "[tool.other]\n")
        assert repository.problems() == [
            Problem(
                repository.where("pyproject.toml"),
                "has a [tool.commitizen] version_files that differs from the other"
                " files whose version nustack check compares; list each of"
                " plugin/.claude-plugin/plugin.json, plugin/.cursor-plugin/plugin.json,"
                " plugin/.devin-plugin/plugin.json, plugin/package.json once, so cz"
                " bump sets the version in each",
            ),
            Problem(
                repository.where("pyproject.toml"),
                "has no [tool.commitizen] tag_format; set it to v$version, so cz bump"
                " finds the last release",
            ),
        ]

    @pytest.mark.parametrize(
        ("old", "new", "what"),
        [
            (
                'tag_format = "v$version"\n',
                "",
                (
                    "has no [tool.commitizen] tag_format; set it to v$version, so cz"
                    " bump finds the last release"
                ),
            ),
            (
                'tag_format = "v$version"',
                'tag_format = "$version"',
                (
                    "has a [tool.commitizen] tag_format other than the release tags'"
                    " form; set it to v$version, so cz bump finds the last release"
                ),
            ),
        ],
        ids=["missing", "other"],
    )
    def test_reports_a_tag_format_missing_or_other_than_the_release_tags(
        self, repository: ModelRepository, old: str, new: str, what: str
    ) -> None:
        repository.edit("pyproject.toml", old, new)
        assert repository.problems() == [
            Problem(repository.where("pyproject.toml"), what)
        ]

    @pytest.mark.parametrize(
        ("triggers", "what"),
        [
            (
                "on:\n  push:\n    branches: [main]\n",
                (
                    'has no push tags filter; set on.push.tags to ["v*"], so each'
                    " release tag starts it"
                ),
            ),
            (
                "on:\n  workflow_dispatch:\n",
                (
                    'has no push tags filter; set on.push.tags to ["v*"], so each'
                    " release tag starts it"
                ),
            ),
            (
                'on:\n  push:\n    tags: ["*"]\n',
                (
                    "has a push tags filter other than the release tags' form; set"
                    ' on.push.tags to ["v*"], so each release tag starts it'
                ),
            ),
            (
                'on:\n  push:\n    tags: ["v*", "w*"]\n',
                (
                    "has a push tags filter other than the release tags' form; set"
                    ' on.push.tags to ["v*"], so each release tag starts it'
                ),
            ),
        ],
        ids=["no-tags", "no-push", "other", "extra"],
    )
    def test_reports_a_push_tags_filter_missing_or_other_than_the_release_tags(
        self, repository: ModelRepository, triggers: str, what: str
    ) -> None:
        repository.write(".github/workflows/release.yml", triggers)
        assert repository.problems() == [
            Problem(repository.where(".github/workflows/release.yml"), what)
        ]

    def test_reports_both_tag_forms_when_each_differs(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "pyproject.toml", 'tag_format = "v$version"', 'tag_format = "$version"'
        )
        repository.edit(".github/workflows/release.yml", '"v*"', '"*"')
        assert repository.problems() == [
            Problem(
                repository.where("pyproject.toml"),
                "has a [tool.commitizen] tag_format other than the release tags'"
                " form; set it to v$version, so cz bump finds the last release",
            ),
            Problem(
                repository.where(".github/workflows/release.yml"),
                "has a push tags filter other than the release tags' form; set"
                ' on.push.tags to ["v*"], so each release tag starts it',
            ),
        ]

    def test_reports_a_missing_release_workflow(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "pyproject.toml", 'tag_format = "v$version"', 'tag_format = "$version"'
        )
        repository.remove(".github/workflows/release.yml")
        assert repository.problems() == [
            Problem(
                repository.where("pyproject.toml"),
                "has a [tool.commitizen] tag_format other than the release tags'"
                " form; set it to v$version, so cz bump finds the last release",
            ),
            Problem(
                repository.where(".github/workflows/release.yml"),
                "is missing; restore it from the repository",
            ),
        ]

    def test_reports_a_release_workflow_that_does_not_parse(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "pyproject.toml", 'tag_format = "v$version"', 'tag_format = "$version"'
        )
        repository.write(".github/workflows/release.yml", "jobs: {}\n")
        assert repository.problems() == [
            Problem(
                repository.where("pyproject.toml"),
                "has a [tool.commitizen] tag_format other than the release tags'"
                " form; set it to v$version, so cz bump finds the last release",
            ),
            Problem(
                repository.where(".github/workflows/release.yml"),
                "is invalid: on: add it",
            ),
        ]

    def test_reports_a_release_workflow_whose_on_reads_as_true(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            ".github/workflows/release.yml",
            '%YAML 1.1\n---\non:\n  push:\n    tags: ["v*"]\n',
        )
        assert repository.problems() == [
            Problem(
                repository.where(".github/workflows/release.yml"),
                "is invalid: %YAML 1.1 reads its on key as true; drop the"
                ' %YAML 1.1 directive, or quote the key as "on"',
            ),
        ]

    def test_reports_a_changelog_that_opens_with_another_version(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("CHANGELOG.md", "## [1.2.3]", "## [1.2.4]")
        assert repository.problems() == [
            Problem(
                repository.where("CHANGELOG.md"),
                "does not open with the entry for 1.2.3; set the newest entry's"
                " version in every file whose version nustack check compares, or"
                " remove the entries newer than 1.2.3",
            ),
            Problem(
                repository.where("CHANGELOG.md"),
                "has no link for [1.2.4]; add"
                " '[1.2.4]: https://example.com/nus/kit/releases/tag/v1.2.4' above the"
                " first ## heading",
            ),
        ]

    def test_reports_a_missing_link_beside_an_ungrouped_entry(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("CHANGELOG.md", "### Added\n\n", "")
        repository.edit(
            "CHANGELOG.md",
            "[1.2.3]: https://example.com/nus/kit/releases/tag/v1.2.3\n",
            "",
        )
        assert repository.problems() == [
            Problem(
                repository.where("CHANGELOG.md"),
                "lists the changes in the entry for 1.2.3 under no group; group them"
                " under '### <type>' headings, each one of Added, Changed, Deprecated,"
                " Removed, Fixed or Security, as Keep a Changelog does",
            ),
            Problem(
                repository.where("CHANGELOG.md"),
                "has no link for [1.2.3]; add"
                " '[1.2.3]: https://example.com/nus/kit/releases/tag/v1.2.3' above the"
                " first ## heading",
            ),
        ]

    def test_reports_only_a_bad_top_title_beside_right_links(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("CHANGELOG.md", "## [1.2.3] - 2026-01-02", "## [1.2.3]")
        assert repository.problems() == [
            Problem(
                repository.where("CHANGELOG.md"),
                "has an entry titled '[1.2.3]'; title it '[<version>] - <YYYY-MM-DD>'"
                " with the release's version",
            )
        ]

    def test_reports_a_release_link_to_another_target_than_the_manifests_repository(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "[1.2.3]: https://example.com/nus/kit/releases/tag/v1.2.3",
            "[1.2.3]: https://example.com/nus/kit",
        )
        assert repository.problems() == [
            Problem(
                repository.where("CHANGELOG.md"),
                "links [1.2.3] to https://example.com/nus/kit;"
                " link it to https://example.com/nus/kit/releases/tag/v1.2.3",
            )
        ]

    def test_asks_no_unreleased_link_of_a_changelog_without_that_section(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("CHANGELOG.md", "## [Unreleased]\n\n", "")
        repository.edit(
            "CHANGELOG.md",
            "[Unreleased]: https://example.com/nus/kit/compare/v1.2.3...HEAD\n",
            "",
        )
        assert repository.problems() == []

    def test_refuses_a_repository_url_that_ends_in_a_slash(
        self, repository: ModelRepository
    ) -> None:
        for path in (
            "plugin/.devin-plugin/plugin.json",
            "plugin/.claude-plugin/plugin.json",
            "plugin/.cursor-plugin/plugin.json",
        ):
            repository.edit(
                path,
                '"repository": "https://example.com/nus/kit"',
                '"repository": "https://example.com/nus/kit/"',
            )
        assert repository.problems() == [
            Problem(
                repository.where(path),
                "is invalid: repository: give the repository's URL as"
                " https://<host>/<owner>/<name>, with no user, password, port, query"
                " or fragment",
            )
            for path in (
                "plugin/.devin-plugin/plugin.json",
                "plugin/.claude-plugin/plugin.json",
                "plugin/.cursor-plugin/plugin.json",
            )
        ]

    def test_reports_an_invalid_pyproject_once(
        self, repository: ModelRepository
    ) -> None:
        repository.write("pyproject.toml", "[project\n")
        repository.edit(".github/workflows/release.yml", '"v*"', '"*"')
        assert repository.problems() == [
            Problem(
                repository.where(".github/workflows/release.yml"),
                "has a push tags filter other than the release tags' form; set"
                ' on.push.tags to ["v*"], so each release tag starts it',
            ),
            Problem(
                repository.where("pyproject.toml"),
                "is invalid: it is not valid TOML on line 1; fix it",
            ),
        ]

    @pytest.mark.parametrize(
        ("table", "key", "message"),
        [
            (
                "[tool.nustack]",
                "mutaton = 1",
                (
                    "is invalid: tool.nustack.an unknown key: rename it or remove it;"
                    " nustack allows only mutation here"
                ),
            ),
            (
                "[tool.nustack.mutation]",
                "read = []",
                (
                    "is invalid: tool.nustack.mutation.an unknown key: rename it or"
                    " remove it; nustack allows only reads here"
                ),
            ),
        ],
    )
    def test_reports_an_unknown_key_in_nustacks_own_tables(
        self, repository: ModelRepository, table: str, key: str, message: str
    ) -> None:
        repository.edit(
            "pyproject.toml", "[tool.ruff]\n", f"{table}\n{key}\n\n[tool.ruff]\n"
        )
        assert repository.problems() == [
            Problem(repository.where("pyproject.toml"), message)
        ]

    def test_reports_a_harness_version_that_is_no_release_version(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("pyproject.toml", '"1.2.3"', '"999"')
        assert repository.problems() == [
            Problem(
                repository.where("pyproject.toml"),
                "is invalid: project.version: use MAJOR.MINOR.PATCH without leading"
                " zeros, such as 0.0.1",
            )
        ]


class TestRepositoryPackage:
    """The loader's package is present, valid and agrees with the manifests.

    A package it cannot read is reported once.
    """

    PATH = "plugin/package.json"

    def test_reports_a_missing_package(self, repository: ModelRepository) -> None:
        repository.remove(self.PATH)
        assert repository.problems() == [
            Problem(
                repository.where(self.PATH),
                "is missing; add it with the plugin's name and version, so OpenCode"
                " can load the plugin",
            )
        ]

    def test_reports_a_folder_in_place_of_the_package(
        self, repository: ModelRepository
    ) -> None:
        repository.remove(self.PATH)
        repository.put(self.PATH, Folder())
        assert repository.problems() == [
            Problem(
                repository.where(self.PATH),
                "is a folder where a file belongs; move the folder, then add the file",
            )
        ]

    def test_reports_an_invalid_package(self, repository: ModelRepository) -> None:
        repository.edit(self.PATH, '"type": "module"', '"type": "commonjs"')
        assert repository.problems() == [
            Problem(
                repository.where(self.PATH),
                "is invalid: type: set it to 'module'",
            )
        ]

    def test_reports_a_package_that_cannot_be_read_once(
        self, repository: ModelRepository
    ) -> None:
        repository.put(
            self.PATH,
            Unreadable("cannot be read (Permission denied); make it readable"),
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.PATH),
                "cannot be read (Permission denied); make it readable",
            )
        ]

    def test_reports_a_package_name_that_differs(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.PATH, '"name": "kit"', '"name": "kat"')
        assert repository.problems() == [
            Problem(
                repository.where(self.PATH),
                "has a name that differs from the plugin manifests; use the manifests'"
                " name",
            )
        ]

    def test_names_each_file_behind_a_bumped_package_version(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.PATH, '"1.2.3"', '"9.9.9"')
        assert repository.problems() == [
            Problem(
                repository.where("plugin/.devin-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " plugin/package.json's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("plugin/.claude-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " plugin/package.json's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("plugin/.cursor-plugin/plugin.json"),
                "has version 1.2.3, older than"
                " plugin/package.json's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
            Problem(
                repository.where("pyproject.toml"),
                "has version 1.2.3, older than"
                " plugin/package.json's 9.9.9; set every file nustack check"
                " compares to the release's version",
            ),
        ]


class TestRepositoryLicense:
    """plugin/ ships the repository's license unchanged.

    A missing plugin license is reported once.
    """

    def test_reports_a_plugin_license_that_differs(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/LICENSE", "Other License\n")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/LICENSE"),
                "differs from the repository's LICENSE; copy the repository's"
                " LICENSE over it",
            )
        ]

    def test_reports_a_missing_plugin_license_once(
        self, repository: ModelRepository
    ) -> None:
        repository.remove("plugin/LICENSE")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/LICENSE"),
                "is missing; copy the repository's LICENSE here",
            )
        ]


class TestRepositoryActivation:
    """The README activates nus-mode the way its playbook says.

    Without the playbook, there is nothing to compare.
    """

    def test_reports_a_readme_activation_line_that_differs(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", "Work in nus-mode.", "Use nus-mode.")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has an activation line that differs from the new-project playbook's;"
                " copy the playbook's markdown block into it",
            )
        ]

    def test_reports_a_readme_without_the_block(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", "```markdown\nWork in nus-mode.\n```\n", "")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has an activation line that differs from the new-project playbook's;"
                " copy the playbook's markdown block into it",
            )
        ]

    def test_compares_nothing_without_the_playbook(
        self, repository: ModelRepository
    ) -> None:
        repository.remove("plugin/skills/nus-mode/playbooks/new-project.md")
        repository.edit(
            "plugin/skills/nus-mode/SKILL.md",
            "## Playbooks\n\n- [new project](playbooks/new-project.md): start one.\n\n",
            "",
        )
        repository.edit("README.md", "```markdown\nWork in nus-mode.\n```\n", "")
        assert repository.problems() == []


class TestRepositorySkillTable:
    """README's skills table gives each skill hidden from the model its description.

    Every table headed Skill and What it holds counts, read as it renders, so one in
    the frontmatter does not, and each such skill's row links its SKILL.md, by the
    path the link reaches past any query or fragment, under the skill's name. When
    some skill needs a row and no such table exists, one Problem asks for the table.
    A row linking anything but a skill's SKILL.md file, and a second row for one
    skill, are Problems naming their lines in the whole file, as are a row's link text
    other than its skill's name and a description other than its skill's. The mode,
    which the model may load, and a skill whose frontmatter or SKILL.md cannot be
    read, need no row, and the skills after it still need theirs. A skill a record
    copies into the plugin keeps its row while its folder is gone.
    """

    ROW = "| [language-python](plugin/skills/language-python/SKILL.md) | Python. |\n"

    def test_reports_a_missing_row_beside_a_differing_activation_line(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", "Work in nus-mode.", "Use nus-mode.")
        repository.edit("README.md", " Python. |", " Go. |")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has an activation line that differs from the new-project playbook's;"
                " copy the playbook's markdown block into it",
            ),
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 20 whose description differs from"
                " language-python's; copy the description from"
                " plugin/skills/language-python/SKILL.md into it",
            ),
        ]

    @pytest.mark.parametrize(
        "wrapped",
        ["\n```\n| Skill | What it holds |\n| --- | --- |\n{}```\n", "\n<!--\n{}-->\n"],
    )
    def test_reads_no_row_that_never_renders(
        self, repository: ModelRepository, wrapped: str
    ) -> None:
        repository.edit("README.md", self.ROW, "")
        repository.edit(
            "README.md", " Naming. |\n", " Naming. |\n" + wrapped.format(self.ROW)
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has no skills table row for language-python; add one that links"
                " plugin/skills/language-python/SKILL.md under its name and copies its"
                " description",
            )
        ]

    def test_reads_the_body_row_beside_a_table_in_the_frontmatter(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "README.md",
            "# kit\n",
            "---\nx: |\n  | Skill | What it holds |\n  | --- | --- |\n  "
            + self.ROW
            + "---\n# kit\n",
        )
        assert repository.problems() == []

    def test_reads_no_row_in_the_frontmatter(self, repository: ModelRepository) -> None:
        repository.edit("README.md", self.ROW, "")
        repository.edit(
            "README.md",
            "# kit\n",
            "---\nx: |\n  | Skill | What it holds |\n  | --- | --- |\n  "
            + self.ROW
            + "---\n# kit\n",
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has no skills table row for language-python; add one that links"
                " plugin/skills/language-python/SKILL.md under its name and copies its"
                " description",
            )
        ]

    def test_reads_the_rows_of_every_table_headed_its_way(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", self.ROW, "")
        repository.edit(
            "README.md",
            " Naming. |\n",
            " Naming. |\n\n| Skill | What it holds |\n| --- | --- |\n" + self.ROW,
        )
        assert repository.problems() == []

    def test_reads_no_table_headed_another_way(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", "| Skill | What it holds |", "| Skill | Holds |")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has no table headed Skill and What it holds; add one with a row"
                " giving each principle and language skill's description",
            )
        ]

    def test_asks_for_a_table_with_a_row_for_each_vendored_skill(
        self, repository: ModelRepository
    ) -> None:
        repository.vendor_into_plugin()
        repository.edit("README.md", "| Skill | What it holds |", "| Skill | Holds |")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has no table headed Skill and What it holds; add one with a row"
                " giving each principle and language skill's description, and a row"
                " for each vendored skill",
            )
        ]

    def test_keeps_the_row_of_a_vendored_skill_whose_folder_is_gone(
        self, repository: ModelRepository
    ) -> None:
        repository.vendor_into_plugin()
        repository.remove("plugin/skills/vendored/LICENSE")
        repository.remove("plugin/skills/vendored/SKILL.md")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills/vendored"),
                "is missing; rerun the sync workflow, or restore the copy from the"
                " commit the record vendored/copy.json names",
            )
        ]

    def test_reports_a_vendored_row_whose_link_text_is_not_its_name(
        self, repository: ModelRepository
    ) -> None:
        repository.vendor_into_plugin()
        repository.edit(
            "README.md",
            "| [vendored](plugin/skills/vendored/SKILL.md)",
            "| [other](plugin/skills/vendored/SKILL.md)",
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 19 whose link text is not vendored;"
                " make it vendored",
            )
        ]

    def test_reports_a_readme_without_a_vendored_skills_row(
        self, repository: ModelRepository
    ) -> None:
        repository.vendor_into_plugin()
        repository.edit(
            "README.md",
            "| [vendored](plugin/skills/vendored/SKILL.md) | Words. |\n",
            "",
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has no skills table row for vendored; add one that links"
                " plugin/skills/vendored/SKILL.md under its name and says when it"
                " applies",
            )
        ]

    def test_reports_a_missing_vendored_skills_row_beside_a_second_row(
        self, repository: ModelRepository
    ) -> None:
        repository.vendor_into_plugin()
        repository.edit("README.md", self.ROW, self.ROW + self.ROW)
        repository.edit(
            "README.md",
            "| [vendored](plugin/skills/vendored/SKILL.md) | Words. |\n",
            "",
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has more than one skills table row for language-python, on lines 20,"
                " 21; keep the first and remove the rest",
            ),
            Problem(
                repository.where("README.md"),
                "has no skills table row for vendored; add one that links"
                " plugin/skills/vendored/SKILL.md under its name and says when it"
                " applies",
            ),
        ]

    def test_asks_no_row_of_a_skill_whose_skill_file_cannot_be_read(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", " Python. |", " Go. |")
        repository.edit("README.md", " Naming. |", " Names. |")
        repository.put(
            "plugin/skills/language-python/SKILL.md",
            Unreadable("cannot be read (Permission denied); make it readable"),
        )
        assert Repository(repository.snapshot()).skill_table_problems() == [
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 19 whose description differs from"
                " principle-naming's; copy the description from"
                " plugin/skills/principle-naming/SKILL.md into it",
            ),
        ]

    def test_asks_no_row_of_a_skill_whose_frontmatter_is_refused(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", " Python. |", " Go. |")
        repository.edit("README.md", " Naming. |", " Names. |")
        repository.edit(
            "plugin/skills/language-python/SKILL.md", "name: language-python\n", ""
        )
        assert Repository(repository.snapshot()).skill_table_problems() == [
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 19 whose description differs from"
                " principle-naming's; copy the description from"
                " plugin/skills/principle-naming/SKILL.md into it",
            ),
        ]

    def test_asks_no_table_when_no_skill_needs_a_row(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", "| Skill | What it holds |", "| Skill | Holds |")
        repository.write("plugin/skills/language-python/SKILL.md", b"\xff")
        repository.write("plugin/skills/principle-naming/SKILL.md", b"\xff")
        assert Repository(repository.snapshot()).skill_table_problems() == []

    def test_reports_a_row_linking_a_skill_folder_without_its_skill_file(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/skills/principle-gone/notes.md", b"Gone.\n")
        repository.edit(
            "README.md",
            self.ROW,
            self.ROW
            + "| [principle-gone](plugin/skills/principle-gone/SKILL.md) | Gone. |\n",
        )
        assert Repository(repository.snapshot()).skill_table_problems() == [
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 21 linking"
                " plugin/skills/principle-gone/SKILL.md, which is no skill's"
                " SKILL.md; link a skill's SKILL.md, or remove the row",
            )
        ]

    @pytest.mark.parametrize("entry", [Folder(), Special()])
    def test_reports_a_row_linking_a_skill_file_that_is_no_file(
        self, repository: ModelRepository, entry: Folder | Special
    ) -> None:
        repository.put("plugin/skills/language-python/SKILL.md", entry)
        assert Repository(repository.snapshot()).skill_table_problems() == [
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 20 linking"
                " plugin/skills/language-python/SKILL.md, which is no skill's"
                " SKILL.md; link a skill's SKILL.md, or remove the row",
            )
        ]

    @pytest.mark.parametrize(
        "href",
        [
            "./plugin/skills/language-python/SKILL.md",
            "plugin/skills/language-python/SKILL.md#python",
            "plugin/skills/language-python/SKILL.md?plain=1",
            "plugin/skills/language%2Dpython/SKILL.md",
        ],
    )
    def test_reads_a_link_by_the_path_it_reaches(
        self, repository: ModelRepository, href: str
    ) -> None:
        repository.edit(
            "README.md", "](plugin/skills/language-python/SKILL.md)", f"]({href})"
        )
        assert repository.problems() == []

    @pytest.mark.parametrize(
        ("row", "what"),
        [
            (
                ROW + "| Gone | Gone. |\n",
                (
                    "has a skills table row on line 24 whose first cell links no skill;"
                    " start it with a link to the skill's SKILL.md, or remove the row"
                ),
            ),
            (
                ROW + "| [gone](plugin/skills/principle-gone/SKILL.md) | Gone. |\n",
                (
                    "has a skills table row on line 24 linking"
                    " plugin/skills/principle-gone/SKILL.md, which is no skill's"
                    " SKILL.md; link a skill's SKILL.md, or remove the row"
                ),
            ),
            (
                ROW + ROW,
                (
                    "has more than one skills table row for language-python, on"
                    " lines 23, 24; keep the first and remove the rest"
                ),
            ),
            (
                ROW.replace("[language-python]", "[language-go]"),
                (
                    "has a skills table row on line 23 whose link text is not"
                    " language-python; make it language-python"
                ),
            ),
            (
                ROW.replace("Python.", "Go."),
                (
                    "has a skills table row on line 23 whose description differs from"
                    " language-python's; copy the description from"
                    " plugin/skills/language-python/SKILL.md into it"
                ),
            ),
        ],
        ids=["no link", "no skill", "second row", "link text", "description"],
    )
    def test_counts_a_rows_line_past_the_frontmatter(
        self, repository: ModelRepository, row: str, what: str
    ) -> None:
        repository.edit("README.md", "# kit\n", "---\nx: 1\n---\n# kit\n")
        repository.edit("README.md", self.ROW, row)
        assert repository.problems() == [Problem(repository.where("README.md"), what)]

    @pytest.mark.parametrize(
        ("row", "what"),
        [
            (
                "| [gone](plugin/skills/principle-gone/SKILL.md) | Gone. |\n",
                (
                    "has a skills table row on line 21 linking"
                    " plugin/skills/principle-gone/SKILL.md, which is no skill's"
                    " SKILL.md; link a skill's SKILL.md, or remove the row"
                ),
            ),
            (
                "| Gone | Gone. |\n",
                (
                    "has a skills table row on line 21 whose first cell links no"
                    " skill; start it with a link to the skill's SKILL.md, or remove"
                    " the row"
                ),
            ),
        ],
    )
    def test_reports_a_row_that_links_no_skill(
        self, repository: ModelRepository, row: str, what: str
    ) -> None:
        repository.edit("README.md", self.ROW, self.ROW + row)
        assert repository.problems() == [Problem(repository.where("README.md"), what)]

    @pytest.mark.parametrize("second", ["Python.", "Go."])
    def test_reports_a_second_row_for_one_skill(
        self, repository: ModelRepository, second: str
    ) -> None:
        repository.edit(
            "README.md", self.ROW, self.ROW + self.ROW.replace("Python.", second)
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has more than one skills table row for language-python, on lines 20,"
                " 21; keep the first and remove the rest",
            )
        ]

    def test_reports_each_skills_row_after_one_with_no_row(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", self.ROW, "")
        repository.edit("README.md", " Naming. |", " Names. |")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has no skills table row for language-python; add one that links"
                " plugin/skills/language-python/SKILL.md under its name and copies its"
                " description",
            ),
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 19 whose description differs from"
                " principle-naming's; copy the description from"
                " plugin/skills/principle-naming/SKILL.md into it",
            ),
        ]

    def test_reports_a_row_whose_link_text_is_not_the_skills_name(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", "[language-python](plugin", "[language-go](plugin")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 20 whose link text is not"
                " language-python; make it language-python",
            ),
        ]

    def test_reads_an_escaped_pipe_as_part_of_the_description(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "plugin/skills/language-python/SKILL.md",
            "description: Python.",
            "description: Python | uv.",
        )
        repository.edit("README.md", " Python. |", " Python \\| uv. |")
        assert repository.problems() == []

    def test_reports_a_row_whose_description_differs(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", " Naming. |", " Names. |")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 19 whose description differs from"
                " principle-naming's; copy the description from"
                " plugin/skills/principle-naming/SKILL.md into it",
            )
        ]

    @pytest.mark.parametrize(
        "cell", ["Python \\*and\\* more.", "Python &#42;and&#42; more."]
    )
    def test_takes_a_description_by_the_text_its_cell_renders(
        self, repository: ModelRepository, cell: str
    ) -> None:
        repository.edit(
            "plugin/skills/language-python/SKILL.md",
            "description: Python.",
            "description: Python *and* more.",
        )
        repository.edit("README.md", " Python. |", f" {cell} |")
        assert repository.problems() == []

    def test_reports_a_description_cell_that_renders_other_text(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "plugin/skills/language-python/SKILL.md",
            "description: Python.",
            "description: Python *and* more.",
        )
        repository.edit("README.md", " Python. |", " Python *and* more. |")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 20 whose description differs from"
                " language-python's; copy the description from"
                " plugin/skills/language-python/SKILL.md into it",
            ),
        ]


class TestRepositoryPageSteps:
    """The README holds the one install and one use section the release page copies.

    Only a heading that is the step's whole title counts. The page copies each section
    outside the repository, so each shows something, gives each link and image a full
    URL and defines each reference it uses. Once a step has several sections, each is
    numbered, and each after the first is asked to go.

    Labels are compared with the changelog's entry even while a step breaks another
    rule, once each step has one section and the entry is the plugin version's. A label
    that resolves differently is reported on the part whose text changes, which for the
    entry is CHANGELOG.md; a label the parts define with one target passes; and labels
    are reported in page order.
    """

    INSTALL = "### 1️⃣ Install\n\nRun `kit add`.\n"

    def test_reports_a_readme_without_the_install_section(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", self.INSTALL, "")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has no '### 1️⃣ Install' section, which the release page copies;"
                " add one",
            )
        ]

    def test_reports_a_readme_without_the_use_section(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", "### 2️⃣ Use", "### Usage")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has no '### 2️⃣ Use' section, which the release page copies; add one",
            )
        ]

    def test_reports_a_heading_that_only_starts_with_a_step(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", "### 1️⃣ Install", "### 1️⃣ Install from source")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has no '### 1️⃣ Install' section, which the release page copies;"
                " add one",
            )
        ]

    def test_reports_a_section_that_shows_nothing(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", "Run `kit add`.", "<!-- none -->")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "shows nothing in its '### 1️⃣ Install' section; write the steps the"
                " release page copies from it",
            )
        ]

    def test_reports_a_foreign_reference_before_a_relative_link(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", "Run `kit add`.", "See [x] and [a](a.md).")
        repository.edit("README.md", "# kit\n", "# kit\n\n[x]: https://x.io\n")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "uses a reference in its '### 1️⃣ Install' section that is defined"
                " elsewhere in the file, so it reads differently on the release page;"
                " define it inside its '### 1️⃣ Install' section, under a label no"
                " other definition in the file uses",
            ),
            Problem(
                repository.where("README.md"),
                "links a.md from its '### 1️⃣ Install' section, which the release"
                " page copies, where a relative link breaks; link it by its full URL",
            ),
        ]

    def test_reports_a_relative_link(self, repository: ModelRepository) -> None:
        repository.edit("README.md", "Run `kit add`.", "See [a](a.md), [b](b.md).")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "links a.md from its '### 1️⃣ Install' section, which the release"
                " page copies, where a relative link breaks; link it by its full URL",
            ),
            Problem(
                repository.where("README.md"),
                "links b.md from its '### 1️⃣ Install' section, which the release"
                " page copies, where a relative link breaks; link it by its full URL",
            ),
        ]

    def test_reports_a_relative_image(self, repository: ModelRepository) -> None:
        repository.edit("README.md", "Run `kit add`.", "See ![a logo](logo.png).")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "links logo.png from its '### 1️⃣ Install' section, which the release"
                " page copies, where a relative link breaks; link it by its full URL",
            )
        ]

    def test_accepts_a_full_url_image(self, repository: ModelRepository) -> None:
        repository.edit(
            "README.md", "Run `kit add`.", "See ![a logo](https://x.io/logo.png)."
        )
        assert repository.problems() == []

    def test_accepts_full_urls_and_references_defined_inside(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "README.md",
            "Run `kit add`.",
            "See [a](https://x.io/a.md) and [b].\n\n[b]: https://x.io/b.md",
        )
        assert repository.problems() == []

    def test_reports_a_readme_with_two_sections(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", self.INSTALL, self.INSTALL + "\n" + self.INSTALL)
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has 2 '### 1️⃣ Install' sections, where the release page copies"
                " one; merge them into one",
            )
        ]

    def test_checks_each_of_two_sections(self, repository: ModelRepository) -> None:
        repository.edit(
            "README.md",
            self.INSTALL,
            "### 1️⃣ Install\n\nSee [a](a.md).\n\n### 1️⃣ Install\n\nSee [x].\n",
        )
        repository.edit("README.md", "# kit\n", "# kit\n\n[x]: https://x.io\n")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "links a.md from its '### 1️⃣ Install' section 1 of 2, which the"
                " release page copies, where a relative link breaks; link it by its"
                " full URL",
            ),
            Problem(
                repository.where("README.md"),
                "uses a reference in its '### 1️⃣ Install' section 2 of 2 that is"
                " defined elsewhere in the file, so it reads differently on the"
                " release page; define it inside its '### 1️⃣ Install' section 2 of 2,"
                " under a label no other definition in the file uses",
            ),
            Problem(
                repository.where("README.md"),
                "has 2 '### 1️⃣ Install' sections, where the release page copies"
                " one; merge them into one",
            ),
        ]

    def test_asks_to_fill_the_first_of_two_sections(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("README.md", self.INSTALL, "### 1️⃣ Install\n\n" + self.INSTALL)
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "shows nothing in its '### 1️⃣ Install' section 1 of 2; write the steps"
                " the release page copies from it",
            ),
            Problem(
                repository.where("README.md"),
                "has 2 '### 1️⃣ Install' sections, where the release page copies"
                " one; merge them into one",
            ),
        ]

    def test_numbers_three_sections_asks_later_ones_to_go_and_names_links_once(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "README.md",
            self.INSTALL,
            "### 1️⃣ Install\n\nRun [a](a.md) and [a](a.md).\n"
            "\n### 1️⃣ Install\n\n### 1️⃣ Install\n",
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "links a.md from its '### 1️⃣ Install' section 1 of 3, which the"
                " release page copies, where a relative link breaks; link it by its"
                " full URL",
            ),
            Problem(
                repository.where("README.md"),
                "shows nothing in its '### 1️⃣ Install' section 2 of 3; remove it, since"
                " the release page copies one",
            ),
            Problem(
                repository.where("README.md"),
                "shows nothing in its '### 1️⃣ Install' section 3 of 3; remove it, since"
                " the release page copies one",
            ),
            Problem(
                repository.where("README.md"),
                "has 3 '### 1️⃣ Install' sections, where the release page copies"
                " one; merge them into one",
            ),
        ]

    def test_compares_labels_beside_another_problem_in_a_step(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "- Adds the kit.\n",
            "- Adds the [kit][docs].\n\n[docs]: https://a.example\n",
        )
        repository.edit(
            "README.md",
            "Run `kit`.",
            "Run [kit][docs] as [a](docs/a.md) says.\n\n[docs]: https://b.example",
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "links docs/a.md from its '### 2️⃣ Use' section, which the release"
                " page copies, where a relative link breaks; link it by its full URL",
            ),
            Problem(
                repository.where("README.md"),
                "uses a reference label in its '### 2️⃣ Use' section that another part"
                " of the release page defines, so it reads differently on the page,"
                " which joins them; define the reference inside its '### 2️⃣ Use'"
                " section, under a label no other part of the page defines",
            ),
        ]

    def test_compares_no_labels_while_a_step_has_two_sections(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "- Adds the kit.\n",
            "- Adds the [kit][docs].\n\n[docs]: https://a.example\n",
        )
        repository.edit(
            "README.md",
            "Run `kit`.",
            "Run [kit][docs].\n\n[docs]: https://b.example\n\n### 2️⃣ Use\n\nRun `kit`.",
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has 2 '### 2️⃣ Use' sections, where the release page copies one;"
                " merge them into one",
            )
        ]

    def test_compares_no_labels_while_a_step_has_no_section(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "- Adds the kit.\n",
            "- Adds the [kit][docs].\n\n[docs]: https://a.example\n",
        )
        repository.edit("README.md", self.INSTALL, "")
        repository.edit(
            "README.md", "Run `kit`.", "Run [kit][docs].\n\n[docs]: https://b.example"
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "has no '### 1️⃣ Install' section, which the release page copies;"
                " add one",
            )
        ]

    def test_compares_no_labels_with_an_older_entry_on_top(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "## [1.2.3] - 2026-01-02\n\n### Added\n\n- Adds the kit.\n\n",
            "",
        )
        repository.edit(
            "CHANGELOG.md",
            "- Starts.\n",
            "- Starts the [kit][docs].\n\n[docs]: https://a.example\n",
        )
        repository.edit(
            "README.md", "Run `kit`.", "Run [kit][docs].\n\n[docs]: https://b.example"
        )
        assert repository.problems() == [
            Problem(
                repository.where("CHANGELOG.md"),
                "does not open with the entry for 1.2.3; retitle its [Unreleased]"
                " section '[1.2.3] - <release date>'",
            )
        ]

    def test_compares_no_labels_without_a_release(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "## [1.2.3] - 2026-01-02\n\n### Added\n\n- Adds the kit.\n\n"
            "## [1.2.2] - 2026-01-01\n\n- Starts.\n",
            "- Adds the [kit][docs].\n\n[docs]: https://a.example\n",
        )
        repository.edit(
            "README.md", "Run `kit`.", "Run [kit][docs].\n\n[docs]: https://b.example"
        )
        assert repository.problems() == [
            Problem(
                repository.where("CHANGELOG.md"),
                "does not open with the entry for 1.2.3; retitle its [Unreleased]"
                " section '[1.2.3] - <release date>'",
            )
        ]

    def test_reports_a_label_the_entry_uses_and_a_step_defines(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md", "- Adds the kit.\n", "- Adds the [kit][docs].\n"
        )
        repository.edit(
            "README.md", "Run `kit`.", "Run [kit][docs].\n\n[docs]: https://b.example"
        )
        assert repository.problems() == [
            Problem(
                repository.where("CHANGELOG.md"),
                "uses a reference label in the entry for 1.2.3 that another part of"
                " the release page defines, so it reads differently on the page, which"
                " joins them; define the reference inside the entry for 1.2.3, under a"
                " label no other part of the page defines",
            )
        ]

    def test_accepts_a_label_the_entry_uses_and_defines_as_a_step_does(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "- Adds the kit.\n",
            "- Adds the [kit][docs].\n\n[docs]: https://b.example\n",
        )
        repository.edit(
            "README.md", "Run `kit`.", "Run [kit][docs].\n\n[docs]: https://b.example"
        )
        assert repository.problems() == []

    def test_accepts_a_label_the_entry_lead_defines_as_a_step_does(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "## [1.2.3] - 2026-01-02\n\n",
            "## [1.2.3] - 2026-01-02\n\nSee the [kit][docs].\n\n"
            "[docs]: https://a.example\n\n",
        )
        repository.edit(
            "README.md", "Run `kit`.", "Run [kit][docs].\n\n[docs]: https://a.example"
        )
        assert repository.problems() == []

    def test_reports_a_label_the_install_step_also_defines(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "- Adds the kit.\n",
            "- Adds the [kit][docs].\n\n[docs]: https://a.example\n",
        )
        repository.edit(
            "README.md",
            "Run `kit add`.",
            "Run [kit][docs].\n\n[docs]: https://b.example",
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "uses a reference label in its '### 1️⃣ Install' section that another"
                " part of the release page defines, so it reads differently on the"
                " page, which joins them; define the reference inside its '### 1️⃣"
                " Install' section, under a label no other part of the page defines",
            )
        ]

    def test_reports_a_label_the_changelog_entry_also_defines(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "- Adds the kit.\n",
            "- Adds the [kit][docs].\n\n[docs]: https://a.example\n",
        )
        repository.edit(
            "README.md", "Run `kit`.", "Run [kit][docs].\n\n[docs]: https://b.example"
        )
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "uses a reference label in its '### 2️⃣ Use' section that another part"
                " of the release page defines, so it reads differently on the page,"
                " which joins them; define the reference inside its '### 2️⃣ Use'"
                " section, under a label no other part of the page defines",
            )
        ]

    def test_accepts_labels_the_changelog_entry_leaves_free(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "- Adds the kit.\n",
            "- Adds the [kit][docs].\n\n[docs]: https://a.example\n",
        )
        repository.edit(
            "README.md",
            "Run `kit`.",
            "Run [kit][use] since [1.2.2].\n\n[use]: https://b.example\n"
            "[1.2.2]: https://c.example",
        )
        assert repository.problems() == []

    def test_reports_a_label_a_step_uses_and_the_entry_defines(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "- Adds the kit.\n",
            "- Adds the [kit][docs].\n\n[docs]: https://a.example\n",
        )
        repository.edit("README.md", "Run `kit`.", "Run [kit][docs].")
        assert repository.problems() == [
            Problem(
                repository.where("README.md"),
                "uses a reference label in its '### 2️⃣ Use' section that another part"
                " of the release page defines, so it reads differently on the page,"
                " which joins them; define the reference inside its '### 2️⃣ Use'"
                " section, under a label no other part of the page defines",
            )
        ]

    @pytest.mark.parametrize(
        "step", ["Run `kit add`.", "Run `kit`."], ids=["install", "use"]
    )
    def test_accepts_a_label_both_define_with_one_target(
        self, repository: ModelRepository, step: str
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "- Adds the kit.\n",
            "- Adds the [kit][docs].\n\n[docs]: https://a.example\n",
        )
        repository.edit(
            "README.md", step, "Run [kit][docs].\n\n[docs]: https://a.example"
        )
        assert repository.problems() == []

    def test_reports_the_entry_lead_and_both_steps_in_page_order(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "## [1.2.3] - 2026-01-02\n\n",
            "## [1.2.3] - 2026-01-02\n\nSee the [kit][docs].\n\n"
            "[guide]: https://a.example\n\n",
        )
        repository.edit(
            "README.md",
            "Run `kit add`.",
            "Run [kit][guide].\n\n[docs]: https://b.example",
        )
        repository.edit("README.md", "Run `kit`.", "Run [kit][guide].")
        assert repository.problems() == [
            Problem(
                repository.where("CHANGELOG.md"),
                "uses a reference label in the entry for 1.2.3 that another part of"
                " the release page defines, so it reads differently on the page, which"
                " joins them; define the reference inside the entry for 1.2.3, under a"
                " label no other part of the page defines",
            ),
            Problem(
                repository.where("README.md"),
                "uses a reference label in its '### 1️⃣ Install' section that another"
                " part of the release page defines, so it reads differently on the"
                " page, which joins them; define the reference inside its '### 1️⃣"
                " Install' section, under a label no other part of the page defines",
            ),
            Problem(
                repository.where("README.md"),
                "uses a reference label in its '### 2️⃣ Use' section that another part"
                " of the release page defines, so it reads differently on the page,"
                " which joins them; define the reference inside its '### 2️⃣ Use'"
                " section, under a label no other part of the page defines",
            ),
        ]


class TestRepositoryListing:
    """The suite's checks see every source and test, or name the folder hiding some."""

    def test_reports_a_folder_that_would_not_list(
        self, repository: ModelRepository
    ) -> None:
        repository.fail_listing("tests/unit/shut", Unopened("cannot be opened"))
        assert repository.problems() == [
            Problem(repository.where("tests/unit/shut"), "cannot be opened")
        ]
