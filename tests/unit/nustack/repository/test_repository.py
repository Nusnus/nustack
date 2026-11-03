"""The plugin's release agrees with every file released and configured beside it.

Each required file is present and readable, every source and test folder lists,
the marketplaces, versions, package and license agree with the plugin, the README
activates nus-mode as its playbook says, and only a repository every check passes
yields a release.
"""

import json
from pathlib import PurePosixPath

import pytest

from nustack.problem import Problem
from nustack.repository.repository import Release
from nustack.repository.repository import Repository
from nustack.tree import File
from nustack.tree import Folder
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
        ) == (File(b"MIT License\n"), "1.2.3", "- Adds the kit.")

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
    """Each required file is present and readable; versions compare where valid."""

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
            *(
                Problem(
                    repository.where(path),
                    "has version 1.2.3, older than"
                    " pyproject.toml's 9.9.9; set every file nustack check"
                    " compares to the release's version",
                )
                for path in (
                    "plugin/.claude-plugin/plugin.json",
                    "plugin/.cursor-plugin/plugin.json",
                    "plugin/package.json",
                )
            ),
        ]

    def test_compares_no_version_when_the_valid_manifests_disagree(
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
            *(
                Problem(
                    repository.where(path),
                    "has version 1.2.3, older than"
                    " the Cursor manifest's 9.9.9; set every file nustack check"
                    " compares to the release's version",
                )
                for path in ("plugin/.claude-plugin/plugin.json", "plugin/package.json")
            ),
        ]


class TestRepositoryMarketplaces:
    """Each marketplace lists the one plugin, as its manifests describe it.

    A description that differs only in spaces differs, an entry's source is checked
    beside broken manifests, and a file where the marketplaces folder belongs is
    named.
    """

    CLAUDE = ".claude-plugin/marketplace.json"
    CURSOR = ".cursor-plugin/marketplace.json"

    CLAUDE_FIELDS = frozendict(
        {
            "name": "kit",
            "description": "Ada's kit.",
            "owner": {"name": "Ada"},
            "plugins": [{"name": "kit", "source": "./plugin", "description": "A kit."}],
        }
    )

    def test_reports_an_invalid_marketplace(self, repository: ModelRepository) -> None:
        repository.write(
            self.CLAUDE, json.dumps(dict(self.CLAUDE_FIELDS) | {"plugins": "kit"})
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.CLAUDE),
                "is invalid: plugins: make it a list",
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
            json.dumps(dict(self.CLAUDE_FIELDS) | {"plugins": [entry] * count}),
        )
        assert repository.problems() == [Problem(repository.where(self.CLAUDE), what)]

    def test_names_each_field_an_entry_differs_in(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            self.CLAUDE,
            json.dumps(
                dict(self.CLAUDE_FIELDS)
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
        repository.write(self.CLAUDE, json.dumps(dict(self.CLAUDE_FIELDS) | change))
        assert repository.problems() == [Problem(repository.where(self.CURSOR), what)]

    def test_reports_an_owner_other_than_the_author(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            self.CLAUDE,
            json.dumps(dict(self.CLAUDE_FIELDS) | {"owner": {"name": "Bo"}}),
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.CLAUDE),
                "names an owner other than the plugin manifests' author; make the"
                " owner the manifests' author",
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


class TestRepositoryVersions:
    """The changelog and the harness carry the plugin's version.

    A changelog without [Unreleased] is asked no link to it, a repository URL's
    trailing slash is dropped, and nothing compares when no file holds a readable
    version.
    """

    def test_reports_a_changelog_that_opens_with_another_version(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("CHANGELOG.md", "[1.2.3]", "[1.2.4]")
        assert repository.problems() == [
            Problem(
                repository.where("CHANGELOG.md"),
                "does not open with the entry for 1.2.3; retitle its [Unreleased]"
                " section '[1.2.3] - <release date>'",
            )
        ]

    def test_reports_a_release_link_to_another_target_than_the_manifests_repository(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "[1.2.3]: https://example.com/kit/releases/tag/v1.2.3",
            "[1.2.3]: https://example.com/kit",
        )
        assert repository.problems() == [
            Problem(
                repository.where("CHANGELOG.md"),
                "links [1.2.3] to https://example.com/kit;"
                " link it to https://example.com/kit/releases/tag/v1.2.3",
            )
        ]

    def test_asks_no_unreleased_link_of_a_changelog_without_that_section(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("CHANGELOG.md", "## [Unreleased]\n\n", "")
        repository.edit(
            "CHANGELOG.md",
            "[Unreleased]: https://example.com/kit/compare/v1.2.3...HEAD\n",
            "",
        )
        assert repository.problems() == []

    @pytest.mark.parametrize(
        ("url", "whats"),
        [
            ("https://example.com/kit/", []),
            (
                "https://example.com/kit//",
                [
                    (
                        "links [1.2.3] to https://example.com/kit/releases/tag/v1.2.3;"
                        " link it to https://example.com/kit//releases/tag/v1.2.3"
                    ),
                    (
                        "links [1.2.2] to https://example.com/kit/releases/tag/v1.2.2;"
                        " link it to https://example.com/kit//releases/tag/v1.2.2"
                    ),
                    (
                        "links [Unreleased] to"
                        " https://example.com/kit/compare/v1.2.3...HEAD; link it to"
                        " https://example.com/kit//compare/v1.2.3...HEAD"
                    ),
                ],
            ),
        ],
    )
    def test_drops_one_slash_a_repository_url_ends_in(
        self, repository: ModelRepository, url: str, whats: list[str]
    ) -> None:
        for path in (
            "plugin/.devin-plugin/plugin.json",
            "plugin/.claude-plugin/plugin.json",
            "plugin/.cursor-plugin/plugin.json",
        ):
            repository.edit(
                path,
                '"repository": "https://example.com/kit"',
                f'"repository": "{url}"',
            )
        assert repository.problems() == [
            Problem(repository.where("CHANGELOG.md"), what) for what in whats
        ]

    def test_reports_an_invalid_pyproject_once(
        self, repository: ModelRepository
    ) -> None:
        repository.write("pyproject.toml", "[project\n")
        assert repository.problems() == [
            Problem(
                repository.where("pyproject.toml"),
                "is invalid: it is not valid TOML on line 1; fix it",
            )
        ]

    def test_reports_a_harness_version_that_differs(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("pyproject.toml", '"1.2.3"', '"9.9.9"')
        assert repository.problems() == [
            *(
                Problem(
                    repository.where(path),
                    "has version 1.2.3, older than"
                    " pyproject.toml's 9.9.9; set every file nustack check"
                    " compares to the release's version",
                )
                for path in (
                    "plugin/.devin-plugin/plugin.json",
                    "plugin/.claude-plugin/plugin.json",
                    "plugin/.cursor-plugin/plugin.json",
                    "plugin/package.json",
                )
            ),
        ]

    def test_reports_a_harness_version_that_is_no_release_version(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("pyproject.toml", '"1.2.3"', '"999"')
        assert repository.problems() == [
            Problem(
                repository.where("pyproject.toml"),
                "is invalid: needs a MAJOR.MINOR.PATCH version, such as 0.0.1, in its"
                " [project] table, and a list of strings as any [tool.ruff]"
                " extend-exclude",
            )
        ]

    def test_compares_no_version_when_no_file_holds_a_readable_one(
        self, repository: ModelRepository
    ) -> None:
        for path in (
            "plugin/.devin-plugin/plugin.json",
            "plugin/.claude-plugin/plugin.json",
            "plugin/.cursor-plugin/plugin.json",
            "plugin/package.json",
        ):
            repository.write(path, "[]")
        repository.write("pyproject.toml", "[project\n")
        assert Repository(repository.snapshot()).version_problems() == []

    def test_names_each_file_behind_a_version_one_manifest_bumped(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("plugin/.claude-plugin/plugin.json", '"1.2.3"', '"1.2.4"')
        assert repository.problems() == [
            *(
                Problem(
                    repository.where(path),
                    "has version 1.2.3, older than"
                    " the Claude Code manifest's 1.2.4; set every file nustack check"
                    " compares to the release's version",
                )
                for path in (
                    "plugin/.devin-plugin/plugin.json",
                    "plugin/.cursor-plugin/plugin.json",
                    "pyproject.toml",
                    "plugin/package.json",
                )
            ),
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
            *(
                Problem(
                    repository.where(path),
                    "has version 1.2.3, older than"
                    " plugin/package.json's 9.9.9; set every file nustack check"
                    " compares to the release's version",
                )
                for path in (
                    "plugin/.devin-plugin/plugin.json",
                    "plugin/.claude-plugin/plugin.json",
                    "plugin/.cursor-plugin/plugin.json",
                    "pyproject.toml",
                )
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
        repository.write("README.md", "# kit\n")
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
        repository.write("README.md", "# kit\n")
        assert repository.problems() == []


class TestRepositoryListing:
    """The suite's checks see every source and test, or name the folder hiding some."""

    def test_reports_a_folder_that_would_not_list(
        self, repository: ModelRepository
    ) -> None:
        repository.fail_listing("tests/unit/shut", Unopened("cannot be opened"))
        assert repository.problems() == [
            Problem(repository.where("tests/unit/shut"), "cannot be opened")
        ]
