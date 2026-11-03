"""The whole plugin installs alike on every host, with each break a Problem.

No check reads outside plugin/, which holds only what nustack ships. Its manifests
agree, its mode indexes every skill, its playbook steps end on done conditions, its
skill text stays true without false alarms, and every link resolves.
"""

from pathlib import PurePosixPath

import pytest

from nustack.plugin.plugin import Plugin
from nustack.problem import Problem
from nustack.tree import Entry
from nustack.tree import Missing
from nustack.tree import NotAFolder
from nustack.tree import Special
from nustack.tree import Symlink
from nustack.tree import Unopened
from nustack.tree import Unreadable
from tests.fixtures.repository import ModelRepository


class TestPluginSafety:
    """No check reads through an entry that could lead outside plugin/."""

    @pytest.mark.parametrize(
        ("path", "entry", "what"),
        [
            (
                "plugin/skills/principle-naming/SKILL.md",
                Symlink(),
                (
                    "is a symlink, which the check never reads through, so it stops"
                    " here; put the file itself here, or close the editor whose lock"
                    " file it is"
                ),
            ),
            (
                "plugin",
                NotAFolder(),
                (
                    "is not a folder, so the check stops here; replace it with the"
                    " plugin folder"
                ),
            ),
            (
                "plugin",
                Missing(),
                (
                    "is missing, so the check stops here; restore the plugin folder"
                    " from the repository"
                ),
            ),
            (
                "plugin/skills",
                Unopened(
                    "cannot be opened (Permission denied); give the folder read and"
                    " execute permission"
                ),
                (
                    "cannot be opened (Permission denied); give the folder read and"
                    " execute permission"
                ),
            ),
        ],
    )
    def test_stops_every_other_check_at_an_unsafe_entry(
        self, repository: ModelRepository, path: str, entry: Entry, what: str
    ) -> None:
        repository.put(path, entry)
        repository.remove("CHANGELOG.md")
        assert repository.problems() == [Problem(repository.where(path), what)]

    def test_reports_every_unsafe_entry_in_path_order(
        self, repository: ModelRepository
    ) -> None:
        repository.put("plugin/skills/z", Symlink())
        repository.put("plugin/a", Symlink())
        what = (
            "is a symlink, which the check never reads through, so it stops here;"
            " put the file itself here, or close the editor whose lock file it is"
        )
        assert repository.problems() == [
            Problem(repository.where("plugin/a"), what),
            Problem(repository.where("plugin/skills/z"), what),
        ]


class TestPluginManifests:
    """Manifests agree; valid ones still set the metadata beside a broken one.

    One that differs from Devin's is named, nothing compares when none is valid, and
    Claude's manifest stands in when Devin's is broken. A missing manifest, a folder
    in a manifest's place, a file where the manifests folder belongs and a manifest
    that cannot be read are each named.
    """

    DEVIN = "plugin/.devin-plugin/plugin.json"
    CLAUDE = "plugin/.claude-plugin/plugin.json"
    CURSOR = "plugin/.cursor-plugin/plugin.json"

    def test_agree_in_the_model_repository(self, repository: ModelRepository) -> None:
        assert repository.problems() == []

    def test_names_one_manifest_only_while_all_agree(
        self, repository: ModelRepository
    ) -> None:
        agreeing = Plugin(repository.snapshot().plugin).manifest
        repository.edit(self.CURSOR, '"A kit."', '"Another kit."')
        assert (agreeing is None, Plugin(repository.snapshot().plugin).manifest) == (
            False,
            None,
        )

    def test_reports_a_manifest_that_differs_from_devins(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.CURSOR, '"A kit."', '"Another kit."')
        repository.edit(self.CURSOR, '"Ada"', '"Grace"')
        assert repository.problems() == [
            Problem(
                repository.where(self.CURSOR),
                "differs from the Devin manifest in description, author; make it"
                " identical to the Devin manifest",
            )
        ]

    def test_compares_no_manifest_when_none_is_valid(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/.devin-plugin/plugin.json", "[]")
        repository.write("plugin/.claude-plugin/plugin.json", "[]")
        repository.write("plugin/.cursor-plugin/plugin.json", "[]")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/.devin-plugin/plugin.json"),
                "is invalid: the file: make it an object of keys and values",
            ),
            Problem(
                repository.where("plugin/.claude-plugin/plugin.json"),
                "is invalid: the file: make it an object of keys and values",
            ),
            Problem(
                repository.where("plugin/.cursor-plugin/plugin.json"),
                "is invalid: the file: make it an object of keys and values",
            ),
        ]

    def test_peers_compare_with_claudes_when_devins_is_broken(
        self, repository: ModelRepository
    ) -> None:
        repository.write(self.DEVIN, "{")
        repository.edit(self.CURSOR, '"A kit."', '"Another kit."')
        assert repository.problems() == [
            Problem(
                repository.where(self.DEVIN),
                "is invalid: the file: fix the JSON (EOF while parsing an object at"
                " line 1 column 1)",
            ),
            Problem(
                repository.where(self.CURSOR),
                "differs from the Claude Code manifest in description; make it"
                " identical to the Claude Code manifest",
            ),
        ]

    @pytest.mark.parametrize("path", [DEVIN, CLAUDE, CURSOR])
    def test_reports_a_missing_manifest(
        self, repository: ModelRepository, path: str
    ) -> None:
        repository.remove(path)
        assert repository.problems() == [
            Problem(
                repository.where(path),
                "is missing; add it, since its host installs the plugin from it",
            )
        ]

    def test_reports_a_folder_in_place_of_a_manifest(
        self, repository: ModelRepository
    ) -> None:
        repository.remove(self.CLAUDE)
        repository.write(f"{self.CLAUDE}/a.md", "# A\n")
        assert repository.problems() == [
            Problem(
                repository.where(self.CLAUDE),
                "is a folder where a file belongs; move the folder, then add the file",
            ),
            Problem(
                repository.where(f"{self.CLAUDE}/a.md"),
                "is neither a skill's SKILL.md nor a playbook; move it into the"
                " mode's playbooks folder or out of the plugin",
            ),
        ]

    def test_reports_a_file_in_place_of_a_manifests_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.remove(self.CLAUDE)
        repository.write("plugin/.claude-plugin", "x")
        folder = repository.where("plugin/.claude-plugin")
        assert repository.problems() == [
            Problem(
                repository.where(self.CLAUDE),
                f"cannot be read, since {folder} is a file where a folder belongs;"
                " move the file, then add the folder",
            ),
            Problem(folder, "is not Markdown; remove it or move it out of the plugin"),
        ]

    def test_reports_a_manifest_that_cannot_be_read(
        self, repository: ModelRepository
    ) -> None:
        repository.put(
            self.CURSOR,
            Unreadable("cannot be read (Permission denied); make it readable"),
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.CURSOR),
                "cannot be read (Permission denied); make it readable",
            )
        ]


class TestPluginFiles:
    """plugin/ holds only the files nustack ships, each readable where it belongs.

    A missing loader, hook config or hook script is named with any test it orphans,
    and a folder, file, pipe or unreadable entry where the license, loader or skills
    folder belongs is named. Neither a missing skills folder nor a value YAML cannot
    read hides another problem, and an entry that is neither a file nor a folder, or
    a file it cannot read, is named. A file that is not Markdown, Markdown that is
    neither a skill nor a playbook, and Markdown that is not UTF-8 are named.
    """

    @pytest.fixture
    def skillless(self, repository: ModelRepository) -> None:
        skill_files = [
            file for file in repository.files if file.is_relative_to("plugin/skills")
        ]
        for skill_file in skill_files:
            repository.remove(skill_file.as_posix())

    def test_reports_a_missing_loader_and_its_orphaned_test(
        self, repository: ModelRepository
    ) -> None:
        repository.remove("plugin/opencode.ts")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/opencode.ts"),
                "is missing; restore it from the repository, so OpenCode can load"
                " the plugin",
            ),
            Problem(
                repository.where("tests/unit/plugin/opencode.test.ts"),
                "mirrors plugin/opencode.ts or plugin/opencode.sh, which does not"
                " exist; move it to mirror the source it tests, or remove it",
            ),
        ]

    def test_reports_a_missing_hook_config(self, repository: ModelRepository) -> None:
        repository.remove("plugin/hooks/hooks.json")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/hooks/hooks.json"),
                "is missing; restore it from the repository, so Claude Code reloads"
                " the mode after a summarization",
            )
        ]

    def test_reports_a_missing_hook_script_and_its_orphaned_test(
        self, repository: ModelRepository
    ) -> None:
        repository.remove("plugin/hooks/reload-nus-mode.sh")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/hooks/reload-nus-mode.sh"),
                "is missing; restore it from the repository, so Claude Code reloads"
                " the mode after a summarization",
            ),
            Problem(
                repository.where(
                    "tests/integration/plugin/hooks/reload-nus-mode.test.ts"
                ),
                "mirrors plugin/hooks/reload-nus-mode.ts or"
                " plugin/hooks/reload-nus-mode.sh, which does not exist; move it to"
                " mirror the source it tests, or remove it",
            ),
        ]

    def test_reports_a_folder_in_place_of_the_license(
        self, repository: ModelRepository
    ) -> None:
        repository.remove("plugin/LICENSE")
        repository.write("plugin/LICENSE/a.md", "# A\n")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/LICENSE"),
                "is a folder where a file belongs; move the folder, then add the file",
            ),
            Problem(
                repository.where("plugin/LICENSE/a.md"),
                "is neither a skill's SKILL.md nor a playbook; move it into the"
                " mode's playbooks folder or out of the plugin",
            ),
        ]

    def test_reports_a_folder_in_place_of_the_loader(
        self, repository: ModelRepository
    ) -> None:
        repository.remove("plugin/opencode.ts")
        repository.write("plugin/opencode.ts/a.md", "# A\n")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/opencode.ts"),
                "is a folder where a file belongs; move the folder, then add the file",
            ),
            Problem(
                repository.where("plugin/opencode.ts/a.md"),
                "is neither a skill's SKILL.md nor a playbook; move it into the"
                " mode's playbooks folder or out of the plugin",
            ),
            Problem(
                repository.where("tests/unit/plugin/opencode.test.ts"),
                "mirrors plugin/opencode.ts or plugin/opencode.sh, which does not"
                " exist; move it to mirror the source it tests, or remove it",
            ),
        ]

    @pytest.mark.usefixtures("skillless")
    def test_reports_a_file_in_place_of_the_skills_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/skills", "x")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills"),
                "is a file where a folder belongs; move the file, then add the folder",
            ),
            Problem(
                repository.where("plugin/skills"),
                "holds 0 modes, where it needs exactly 1; keep one skill folder"
                " without the 'principle-' or 'language-' prefix",
            ),
        ]

    @pytest.mark.usefixtures("skillless")
    def test_reports_a_pipe_in_place_of_the_skills_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.put("plugin/skills", Special())
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills"),
                "is neither a file nor a folder; remove it, then add the folder",
            ),
            Problem(
                repository.where("plugin/skills"),
                "holds 0 modes, where it needs exactly 1; keep one skill folder"
                " without the 'principle-' or 'language-' prefix",
            ),
        ]

    @pytest.mark.usefixtures("skillless")
    def test_reports_an_unreadable_entry_in_place_of_the_skills_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.put(
            "plugin/skills",
            Unreadable("cannot be read (Permission denied); make it readable"),
        )
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills"),
                "is a file where a folder belongs; move the file, then add the folder",
            ),
            Problem(
                repository.where("plugin/skills"),
                "cannot be read (Permission denied); make it readable",
            ),
            Problem(
                repository.where("plugin/skills"),
                "holds 0 modes, where it needs exactly 1; keep one skill folder"
                " without the 'principle-' or 'language-' prefix",
            ),
        ]

    @pytest.mark.usefixtures("skillless")
    def test_reports_every_other_problem_beside_a_missing_skills_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.remove("plugin/LICENSE")
        repository.remove("LICENSE")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/LICENSE"),
                "is missing; copy the repository's LICENSE here",
            ),
            Problem(
                repository.where("plugin/skills"),
                "is missing; add it with the plugin's skills",
            ),
            Problem(
                repository.where("plugin/skills"),
                "holds 0 modes, where it needs exactly 1; keep one skill folder"
                " without the 'principle-' or 'language-' prefix",
            ),
            Problem(
                repository.where("LICENSE"), "is missing; add the project's license"
            ),
        ]

    def test_reports_every_other_problem_beside_a_value_its_tag_cannot_build(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "plugin/skills/language-python/SKILL.md",
            "description: Python.",
            "description: !!int canary",
        )
        repository.edit(
            "plugin/skills/principle-naming/SKILL.md",
            "description: Naming.",
            "description: !!int canary",
        )
        repository.remove("plugin/LICENSE")
        repository.edit(
            "plugin/skills/nus-mode/SKILL.md", "Ship.", "Ship [it](missing.md)."
        )
        missing = repository.where("plugin/skills/nus-mode/missing.md")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/LICENSE"),
                "is missing; copy the repository's LICENSE here",
            ),
            Problem(
                repository.where("plugin/skills/language-python/SKILL.md"),
                "frontmatter is invalid: it holds a value on line 3 that YAML cannot"
                " build as its type; fix the value, or remove its tag or merge key",
            ),
            Problem(
                repository.where("plugin/skills/principle-naming/SKILL.md"),
                "frontmatter is invalid: it holds a value on line 3 that YAML cannot"
                " build as its type; fix the value, or remove its tag or merge key",
            ),
            Problem(
                repository.where("plugin/skills/nus-mode/SKILL.md"),
                f"links to {missing}, which is not a file inside"
                f" {repository.where('plugin')}; link to a file inside it, or to a"
                " full URL",
            ),
        ]

    def test_reports_an_entry_that_is_neither_a_file_nor_a_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.put("plugin/fifo", Special())
        assert repository.problems() == [
            Problem(
                repository.where("plugin/fifo"),
                "is neither a file nor a folder; remove it",
            )
        ]

    @pytest.mark.parametrize(
        "path",
        [
            "plugin/LICENSE",
            "plugin/package.json",
            "plugin/.claude-plugin/plugin.json",
        ],
    )
    def test_reports_a_pipe_in_place_of_a_file_it_needs(
        self, repository: ModelRepository, path: str
    ) -> None:
        repository.put(path, Special())
        assert repository.problems() == [
            Problem(
                repository.where(path),
                "is neither a file nor a folder; remove it, then add the file",
            )
        ]

    def test_reports_a_file_that_cannot_be_read(
        self, repository: ModelRepository
    ) -> None:
        repository.put(
            "plugin/opencode.ts",
            Unreadable("cannot be read (Permission denied); make it readable"),
        )
        assert repository.problems() == [
            Problem(
                repository.where("plugin/opencode.ts"),
                "cannot be read (Permission denied); make it readable",
            )
        ]

    def test_reports_an_unreadable_file_the_plugin_does_not_hold(
        self, repository: ModelRepository
    ) -> None:
        repository.put(
            "plugin/notes.txt",
            Unreadable("cannot be read (Permission denied); make it readable"),
        )
        assert repository.problems() == [
            Problem(
                repository.where("plugin/notes.txt"),
                "is not Markdown; remove it or move it out of the plugin",
            ),
            Problem(
                repository.where("plugin/notes.txt"),
                "cannot be read (Permission denied); make it readable",
            ),
        ]

    @pytest.mark.parametrize("content", ["x", b"\xff"])
    def test_reports_a_file_that_is_not_markdown(
        self, repository: ModelRepository, content: str | bytes
    ) -> None:
        repository.write("plugin/notes.txt", content)
        assert repository.problems() == [
            Problem(
                repository.where("plugin/notes.txt"),
                "is not Markdown; remove it or move it out of the plugin",
            )
        ]

    @pytest.mark.parametrize(
        "path", ["plugin/skills/nus-mode/notes.md", "plugin/skills/notes.md"]
    )
    def test_reports_markdown_that_is_neither_skill_nor_playbook(
        self, repository: ModelRepository, path: str
    ) -> None:
        repository.write(path, "# Notes\n")
        assert repository.problems() == [
            Problem(
                repository.where(path),
                "is neither a skill's SKILL.md nor a playbook; move it into the"
                " mode's playbooks folder or out of the plugin",
            )
        ]

    def test_accepts_markdown_in_utf8_beyond_ascii(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "plugin/skills/nus-mode/playbooks/new-project.md", "\n", " Café.\n"
        )
        assert repository.problems() == []

    def test_reports_markdown_that_is_not_utf8(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/skills/nus-mode/playbooks/new-project.md", b"\xff")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills/nus-mode/playbooks/new-project.md"),
                "is not valid UTF-8; save it as UTF-8",
            )
        ]


class TestPluginMode:
    """The one mode indexes every skill and playbook under its heading.

    A folder or pipe named SKILL.md is named, a missing SKILL.md is reported once,
    the title may follow blank lines, and no folder counts as a playbook.
    """

    MODE = "plugin/skills/nus-mode/SKILL.md"
    NAMING = "plugin/skills/principle-naming/SKILL.md"

    @pytest.fixture
    def padding(self, repository: ModelRepository) -> int:
        text = repository.files[PurePosixPath(self.MODE)].decode()
        return (
            Plugin.HOOK_OUTPUT
            - Plugin.HOOK_ROOM
            - len(text.split("---\n", 2)[2].strip())
        )

    def test_reports_a_folder_named_skill_md(self, repository: ModelRepository) -> None:
        repository.remove(self.NAMING)
        repository.write(f"{self.NAMING}/a.md", "# A\n")
        assert repository.problems() == [
            Problem(
                repository.where(f"{self.NAMING}/a.md"),
                "is neither a skill's SKILL.md nor a playbook; move it into the"
                " mode's playbooks folder or out of the plugin",
            ),
            Problem(
                repository.where(self.NAMING),
                "is a folder where a file belongs; move the folder, then add the file",
            ),
            Problem(
                repository.where(self.MODE),
                f"links to {repository.where(self.NAMING)}, which is not a file inside"
                f" {repository.where('plugin')}; link to a file inside it, or to a"
                " full URL",
            ),
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 19 linking"
                " plugin/skills/principle-naming/SKILL.md, which is no skill's"
                " SKILL.md; link a skill's SKILL.md, or remove the row",
            ),
        ]

    def test_reports_a_pipe_named_skill_md(self, repository: ModelRepository) -> None:
        repository.put(self.NAMING, Special())
        assert repository.problems() == [
            Problem(
                repository.where(self.NAMING),
                "is neither a file nor a folder; remove it, then add the file",
            ),
            Problem(
                repository.where(self.MODE),
                f"links to {repository.where(self.NAMING)}, which is not a file inside"
                f" {repository.where('plugin')}; link to a file inside it, or to a"
                " full URL",
            ),
            Problem(
                repository.where("README.md"),
                "has a skills table row on line 19 linking"
                " plugin/skills/principle-naming/SKILL.md, which is no skill's"
                " SKILL.md; link a skill's SKILL.md, or remove the row",
            ),
        ]

    def test_reports_a_second_mode(self, repository: ModelRepository) -> None:
        repository.write(
            "plugin/skills/other/SKILL.md",
            "---\nname: other\ndescription: Another.\n---\n\n# Other\n",
        )
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills"),
                "holds 2 modes, where it needs exactly 1; keep one skill folder"
                " without the 'principle-' or 'language-' prefix",
            )
        ]

    def test_reports_a_mode_without_skill_md_once(
        self, repository: ModelRepository
    ) -> None:
        repository.remove(self.MODE)
        repository.remove("plugin/skills/nus-mode/playbooks/new-project.md")
        repository.write("plugin/skills/nus-mode/notes/a.txt", "x")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills/nus-mode/notes/a.txt"),
                "is not Markdown; remove it or move it out of the plugin",
            ),
            Problem(
                repository.where("plugin/skills/nus-mode"),
                "has no SKILL.md; add one or remove the folder",
            ),
        ]

    def test_reports_a_skill_folder_without_skill_md_once(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/skills/principle-tests/a.txt", "x")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills/principle-tests/a.txt"),
                "is not Markdown; remove it or move it out of the plugin",
            ),
            Problem(
                repository.where("plugin/skills/principle-tests"),
                "has no SKILL.md; add one or remove the folder",
            ),
        ]

    def test_reports_a_body_that_does_not_open_with_its_title(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.MODE, "\n# nus-mode\n", "\n# The mode\n")
        assert repository.problems() == [
            Problem(
                repository.where(self.MODE),
                "does not open its body with the line '# nus-mode'; restore it,"
                " since the Claude Code hook finds the mode in a transcript by it",
            )
        ]

    def test_accepts_a_title_after_blank_lines(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.MODE, "\n# nus-mode\n", "\n\n\n# nus-mode\n")
        assert repository.problems() == []

    def test_accepts_a_body_that_fits_the_hook_output(
        self, repository: ModelRepository, padding: int
    ) -> None:
        repository.edit(self.MODE, "Ship.", "Ship." + "x" * padding)
        assert repository.problems() == []

    def test_reports_a_body_too_long_for_the_hook_output(
        self, repository: ModelRepository, padding: int
    ) -> None:
        repository.edit(self.MODE, "Ship.", "Ship." + "x" * (padding + 1))
        assert repository.problems() == [
            Problem(
                repository.where(self.MODE),
                "has a body of 9001 characters, over the 9000 that leave the Claude"
                " Code hook room for its preamble and the mode's folder within the"
                " 10000 characters Claude Code passes on"
                " (https://code.claude.com/docs/en/hooks#json-output); shorten it",
            )
        ]

    def test_reports_a_principle_the_mode_does_not_index(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            "plugin/skills/principle-scope/SKILL.md",
            f"---\nname: principle-scope\ndescription: More.\n"
            f"{ModelRepository.HIDDEN}# More\n\nKeep it.\n",
        )
        repository.list_skill("principle-scope", "More.")
        scope = repository.where("plugin/skills/principle-scope/SKILL.md")
        assert repository.problems() == [
            Problem(
                repository.where(self.MODE),
                f"does not index {scope} under ## Principles; add a link to it there"
                " with when it applies",
            )
        ]

    def test_reports_a_language_skill_the_mode_does_not_index(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            "plugin/skills/language-rust/SKILL.md",
            f"---\nname: language-rust\ndescription: More.\n"
            f"{ModelRepository.HIDDEN}# More\n\nKeep it.\n",
        )
        repository.list_skill("language-rust", "More.")
        rust = repository.where("plugin/skills/language-rust/SKILL.md")
        assert repository.problems() == [
            Problem(
                repository.where(self.MODE),
                f"does not index {rust} under ## Languages; add a link to it there"
                " with when it applies",
            )
        ]

    def test_reports_a_playbook_the_mode_does_not_index(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            "plugin/skills/nus-mode/playbooks/review.md",
            "# Review\n\n1. **Read it.** Done when every file is read.\n",
        )
        playbook_path = repository.where("plugin/skills/nus-mode/playbooks/review.md")
        assert repository.problems() == [
            Problem(
                repository.where(self.MODE),
                f"does not index {playbook_path} under ## Playbooks; add a link to it"
                " there with when it applies",
            )
        ]

    def test_lists_each_unindexed_file_in_path_order(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            "plugin/skills/principle-scope/SKILL.md",
            "---\nname: principle-scope\ndescription: More.\n"
            f"{ModelRepository.HIDDEN}# More\n\nKeep it.\n",
        )
        repository.list_skill("principle-scope", "More.")
        repository.write(
            "plugin/skills/nus-mode/playbooks/review.md",
            "# Review\n\n1. **Read it.** Done when every file is read.\n",
        )
        playbook_path = repository.where("plugin/skills/nus-mode/playbooks/review.md")
        skill_path = repository.where("plugin/skills/principle-scope/SKILL.md")
        assert repository.problems() == [
            Problem(
                repository.where(self.MODE),
                f"does not index {playbook_path} under ## Playbooks; add a link to it"
                " there with when it applies",
            ),
            Problem(
                repository.where(self.MODE),
                f"does not index {skill_path} under ## Principles; add a link to it"
                " there with when it applies",
            ),
        ]

    def test_reports_a_skill_indexed_under_another_heading(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.MODE, "## Principles\n\n", "")
        assert repository.problems() == [
            Problem(
                repository.where(self.MODE),
                f"does not index {repository.where(self.NAMING)}"
                " under ## Principles; add a link to it there with when it applies",
            )
        ]

    def test_takes_no_playbook_from_a_folder_named_like_one(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/skills/principle-naming/playbooks/a.md", "# A\n")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills/principle-naming/playbooks/a.md"),
                "is neither a skill's SKILL.md nor a playbook; move it into the"
                " mode's playbooks folder or out of the plugin",
            )
        ]

    def test_reports_a_file_in_playbooks_that_is_not_markdown(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/skills/nus-mode/playbooks/notes.txt", "x")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills/nus-mode/playbooks/notes.txt"),
                "is not Markdown; remove it or move it out of the plugin",
            )
        ]

    def test_takes_no_playbook_from_a_folder_under_playbooks(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/skills/nus-mode/playbooks/old/a.md", "# A\n")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/skills/nus-mode/playbooks/old/a.md"),
                "is neither a skill's SKILL.md nor a playbook; move it into the"
                " mode's playbooks folder or out of the plugin",
            )
        ]

    def test_reports_another_mode_name_in_a_document(
        self, repository: ModelRepository
    ) -> None:
        path = "plugin/skills/principle-naming/SKILL.md"
        repository.edit(path, "Name each part", "In fast-mode, name each part")
        assert repository.problems() == [
            Problem(
                repository.where(path),
                "names a mode other than nus-mode; call the mode by its folder's name",
            )
        ]


class TestPluginPlaybooks:
    """An agent can tell when each playbook step is done."""

    PLAYBOOK = "plugin/skills/nus-mode/playbooks/new-project.md"

    def test_reports_a_step_without_a_done_condition(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            self.PLAYBOOK, "Done when its terms are written down.", "Read it."
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.PLAYBOOK),
                "has step 1 with no done condition; end it with a sentence that"
                " starts 'Done when' and names what an agent can check",
            )
        ]


class TestPluginSkillText:
    """Skill text stays true on every host and every day, without false alarms.

    Only skill text is held to the rule, and a word that only looks like a host or a
    date passes.
    """

    PATH = "plugin/skills/principle-naming/SKILL.md"
    HOST = (
        "line 11 names an agent host, a model or a host's folder; state the rule"
        " for every host"
    )
    DATE = (
        "line 11 holds a date or a year; state the rule without it, since skill"
        " text outlives any date"
    )

    @pytest.mark.parametrize(
        ("text", "what"),
        [
            ("Claude names each part.", HOST),
            ("Keep names in .cursor/rules.", HOST),
            ("Since 2026-01-02, name each part.", DATE),
            ("Since 1999, name each part.", DATE),
        ],
    )
    def test_reports_a_host_or_a_date(
        self, repository: ModelRepository, text: str, what: str
    ) -> None:
        repository.edit(self.PATH, "Name each part for what it does.", text)
        assert repository.problems() == [Problem(repository.where(self.PATH), what)]

    def test_reports_each_skill_file_that_names_a_host_or_a_date(
        self, repository: ModelRepository
    ) -> None:
        playbook_path = "plugin/skills/nus-mode/playbooks/new-project.md"
        repository.edit(self.PATH, "Name each part for what it does.", "Claude, 2026.")
        repository.edit(
            playbook_path,
            "Done when its terms are written down.",
            "Done when its terms are written down in 1999.",
        )
        assert repository.problems() == [
            Problem(
                repository.where(playbook_path),
                "line 3 holds a date or a year; state the rule without it, since"
                " skill text outlives any date",
            ),
            Problem(repository.where(self.PATH), self.HOST),
            Problem(repository.where(self.PATH), self.DATE),
        ]

    def test_holds_only_skill_text_to_the_rule(
        self, repository: ModelRepository
    ) -> None:
        repository.write("plugin/notes.md", "# Claude, 2026\n")
        assert repository.problems() == [
            Problem(
                repository.where("plugin/notes.md"),
                "is neither a skill's SKILL.md nor a playbook; move it into the"
                " mode's playbooks folder or out of the plugin",
            )
        ]

    @pytest.mark.parametrize(
        "text",
        ["Name each part in kit.cursor files.", "Keep 12345 parts.", "Read claude."],
    )
    def test_accepts_a_word_that_only_looks_like_one(
        self, repository: ModelRepository, text: str
    ) -> None:
        repository.edit(self.PATH, "Name each part for what it does.", text)
        assert repository.problems() == []


class TestPluginLinks:
    """Each link reaches a file in the plugin by a relative path, or is a full URL.

    An anchor that names no heading, and a malformed link, are reported.
    """

    PATH = "plugin/skills/principle-naming/SKILL.md"
    PLAYBOOK = "plugin/skills/nus-mode/playbooks/new-project.md"

    def test_reports_a_link_to_a_missing_file(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.PATH, "what it does.", "what it does: [see](missing.md).")
        missing = repository.where("plugin/skills/principle-naming/missing.md")
        assert repository.problems() == [
            Problem(
                repository.where(self.PATH),
                f"links to {missing}, which is not a file inside"
                f" {repository.where('plugin')}; link to a file inside it, or to a"
                " full URL",
            )
        ]

    def test_reports_a_link_to_a_file_outside_the_plugin(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            self.PATH, "what it does.", "what it does: [see](../../../LICENSE)."
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.PATH),
                f"links to {repository.where('LICENSE')}, which is not a file inside"
                f" {repository.where('plugin')}; link to a file inside it, or to a"
                " full URL",
            )
        ]

    def test_lists_each_broken_link_once_in_target_order(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            self.PATH,
            "what it does.",
            "what it does: [z](z.md), [a](a.md), [z again](z.md).",
        )
        folder = repository.where("plugin/skills/principle-naming")
        plugin_path = repository.where("plugin")
        assert repository.problems() == [
            Problem(
                repository.where(self.PATH),
                f"links to {folder / 'a.md'}, which is not a file inside {plugin_path};"
                " link to a file inside it, or to a full URL",
            ),
            Problem(
                repository.where(self.PATH),
                f"links to {folder / 'z.md'}, which is not a file inside {plugin_path};"
                " link to a file inside it, or to a full URL",
            ),
        ]

    def test_reports_a_link_to_a_file_by_its_absolute_path(
        self, repository: ModelRepository
    ) -> None:
        target = repository.where("plugin/skills/nus-mode/SKILL.md")
        repository.edit(
            self.PATH,
            "what it does.",
            f"what it does: [mode](../nus-mode/SKILL.md), [again]({target}).",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.PATH),
                f"links to the absolute path {str(target)!r}, which breaks once the"
                " plugin moves; link to it by its path from this file",
            )
        ]

    def test_accepts_a_link_to_a_full_url(self, repository: ModelRepository) -> None:
        repository.edit(
            self.PATH, "what it does.", "what it does: [see](https://example.com)."
        )
        assert repository.problems() == []

    def test_reports_an_anchor_that_names_no_heading(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.PLAYBOOK, "../SKILL.md#goal", "../SKILL.md#aim")
        assert repository.problems() == [
            Problem(
                repository.where(self.PLAYBOOK),
                f"links to {repository.where('plugin/skills/nus-mode/SKILL.md')}#aim,"
                " which names no heading there; link to a heading's anchor, or drop"
                " the part after #",
            )
        ]

    def test_reports_a_malformed_link(self, repository: ModelRepository) -> None:
        repository.edit(self.PATH, "what it does.", "what it does: [see](a%00.md).")
        assert repository.problems() == [
            Problem(
                repository.where(self.PATH),
                "has a malformed link 'a%00.md'; write it as a full URL or a path"
                " to a file",
            )
        ]
