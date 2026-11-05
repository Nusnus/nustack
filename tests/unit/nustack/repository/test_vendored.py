"""Each vendored copy holds what its record lists, and every rewriting tool skips it.

A record or config the check cannot read, or that lacks what it reads, is a Problem.
"""

import json
from dataclasses import replace
from pathlib import PurePosixPath

import pytest

from nustack.github.name import RepositoryUrl
from nustack.problem import Problem
from nustack.record import CopyRecord
from nustack.repository.hooks import Hooks
from nustack.repository.repository import Repository
from nustack.repository.vendored import VendoredCopies
from nustack.tree import Folder
from nustack.tree import NotAFolder
from nustack.tree import Special
from nustack.tree import Symlink
from nustack.tree import Unopened
from nustack.tree import Unreadable
lazy from tests.fixtures.repository import ModelRepository


class TestVendoredCopy:
    """Each copy holds exactly the files and bytes its record lists.

    A missing, extra, edited or non-file entry is named with its fix, as is a
    record that is invalid, unreadable or no file, a folder two records name, or a
    copy into the plugin outside its skills folder. A record of an authored skill
    leaves that skill authored, so its own problems still show. Every rewriting
    hook and Ruff skip each folder a record names, joined as one pattern; a missing
    rewriting hook, a hook that skips another pattern, a second hook that skips
    nothing, a config that does not parse or a missing config is a Problem.
    """

    HOOKS = ".pre-commit-config.yaml"
    RECORD = "vendored/copy.json"
    COPY = ".agents/skills/vendored"
    EXCLUDE = "        exclude: ^(?:\\.agents/skills/vendored)/\n"
    FIX = (
        "rerun the sync workflow, or restore the copy from the commit the record"
        " vendored/copy.json names"
    )
    PENDING = (
        "remove every folder the record vendored/copy.json names until the first sync"
    )
    AUTHORED = "plugin/skills/principle-naming/SKILL.md"
    NO_FOLDER = "no record names a vendored skill folder"
    LEFTOVER = (
        "holds a LICENSE as a vendored copy does, yet no record lists it; remove the"
        " folder, and to copy the skill, list it in a record with commit null and files"
        " {}, as AGENTS.md says, and rerun the sync workflow"
    )
    SELF_COPY = (
        "upstream: names this repository, whose skills its authors write; remove the"
        " record and keep the skills as authored ones"
    )

    def test_accepts_a_repository_with_no_record(
        self, repository: ModelRepository
    ) -> None:
        repository.remove(self.RECORD)
        repository.remove(f"{self.COPY}/LICENSE")
        repository.remove(f"{self.COPY}/SKILL.md")
        repository.write(
            self.HOOKS,
            repository.files[PurePosixPath(self.HOOKS)]
            .decode()
            .replace(self.EXCLUDE, ""),
        )
        repository.edit("pyproject.toml", '".agents/skills/vendored"', "")
        repository.edit(".gitattributes", ".agents/skills/vendored/** -text\n", "")
        assert repository.problems() == []

    def test_accepts_the_readme_row_of_a_plugin_skill_before_its_first_sync(
        self, repository: ModelRepository
    ) -> None:
        repository.vendor_into_plugin()
        repository.record_before_first_sync()
        repository.remove("plugin/skills/vendored/LICENSE")
        repository.remove("plugin/skills/vendored/SKILL.md")
        assert repository.problems() == []

    def test_reports_a_plugin_skill_with_no_readme_row_before_its_first_sync(
        self, repository: ModelRepository
    ) -> None:
        repository.vendor_into_plugin()
        repository.record_before_first_sync()
        repository.remove("plugin/skills/vendored/LICENSE")
        repository.remove("plugin/skills/vendored/SKILL.md")
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

    def test_reports_a_symlinked_record(self, repository: ModelRepository) -> None:
        repository.fail_read("vendored/link.json", Unreadable(CopyRecord.SYMLINK))
        assert repository.problems() == [
            Problem(
                repository.where("vendored/link.json"),
                "is a symlink, which the check never reads through; replace it with"
                " the record itself",
            )
        ]

    @pytest.mark.parametrize(
        ("content", "what"),
        [
            (
                "{",
                (
                    "is invalid: the file: fix the JSON (EOF while parsing an object"
                    " at line 1 column 1)"
                ),
            ),
            (
                json.dumps(
                    {
                        "upstream": "https://github.com/up/skills",
                        "source": "skills",
                        "folder": ".agents/skills",
                        "skills": ["vendored"],
                        "commit": "c" * 40,
                        "files": [],
                    }
                ),
                "is invalid: files: make it an object of keys and values",
            ),
            (
                json.dumps({"upstream": "https://github.com/up/skills"}),
                (
                    "is invalid: source: add it; folder: add it; skills: add it;"
                    " commit: add it; files: add it"
                ),
            ),
        ],
    )
    def test_reports_a_record_it_cannot_read(
        self, repository: ModelRepository, content: str, what: str
    ) -> None:
        repository.write(self.RECORD, content)
        assert repository.problems() == [Problem(repository.where(self.RECORD), what)]

    def test_reports_a_record_key_written_twice(
        self, repository: ModelRepository
    ) -> None:
        text = repository.record().text
        repository.write(
            self.RECORD, text.replace('"source": ', '"source": "x",\n  "source": ', 1)
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.RECORD),
                "is invalid: has the key 'source' more than once in the file; keep one",
            )
        ]

    def test_accepts_the_same_record_with_each_key_once(
        self, repository: ModelRepository
    ) -> None:
        repository.write(self.RECORD, repository.record().text)
        assert repository.problems() == []

    def test_reports_only_the_record_of_plugin_skills_it_cannot_read(
        self, repository: ModelRepository
    ) -> None:
        repository.vendor_into_plugin()
        repository.copy_file("references/NOTES.md", "Notes.\n")
        repository.write(self.RECORD, "{")
        assert repository.problems() == [
            Problem(
                repository.where(self.RECORD),
                "is invalid: the file: fix the JSON (EOF while parsing an object"
                " at line 1 column 1)",
            )
        ]

    def test_reports_a_record_the_disk_refuses(
        self, repository: ModelRepository
    ) -> None:
        repository.fail_read(self.RECORD, Unreadable("cannot be read; fix it"))
        assert repository.problems() == [
            Problem(repository.where(self.RECORD), "cannot be read; fix it")
        ]

    def test_reports_a_record_that_is_a_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.fail_read(self.RECORD, Folder())
        assert repository.problems() == [
            Problem(
                repository.where(self.RECORD),
                "is a folder where a file belongs; move the folder, then add the file",
            )
        ]

    def test_reports_a_folder_named_as_a_record(
        self, repository: ModelRepository
    ) -> None:
        repository.fail_read("vendored/folder.json", Folder())
        assert repository.problems() == [
            Problem(
                repository.where("vendored/folder.json"),
                "is a folder where a file belongs; move the folder, then add the file",
            )
        ]

    def test_reports_a_record_laid_out_other_than_the_sync_writes_it(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            self.RECORD,
            json.dumps(repository.record().model_dump(mode="json"), indent=4),
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.RECORD),
                "is laid out other than the sync writes it; write it as JSON indented"
                " by 2 spaces, with its keys in the order upstream, source, folder,"
                " skills, commit, files, its files sorted, every non-ASCII character"
                " escaped as \\uXXXX and one newline at the end",
            )
        ]

    def test_reports_a_folder_two_records_name(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            "vendored/again.json", repository.files[PurePosixPath(self.RECORD)]
        )
        assert repository.problems() == [
            Problem(
                repository.where("vendored/again.json"),
                "folder and skills: names a skill folder that vendored/copy.json names"
                " too, or one inside it or around it; give each skill folder one"
                " record",
            ),
            Problem(
                repository.where("vendored/copy.json"),
                "folder and skills: names a skill folder that vendored/again.json names"
                " too, or one inside it or around it; give each skill folder one"
                " record",
            ),
        ]

    def test_reports_only_the_overlap_of_records_that_name_one_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.write(
            "vendored/again.json", repository.files[PurePosixPath(self.RECORD)]
        )
        repository.write(f"{self.COPY}/SKILL.md", "edited\n")
        repository.write(f"{self.COPY}/extra.md", "extra\n")
        assert repository.problems() == [
            Problem(
                repository.where("vendored/again.json"),
                "folder and skills: names a skill folder that vendored/copy.json names"
                " too, or one inside it or around it; give each skill folder one"
                " record",
            ),
            Problem(
                repository.where("vendored/copy.json"),
                "folder and skills: names a skill folder that vendored/again.json names"
                " too, or one inside it or around it; give each skill folder one"
                " record",
            ),
        ]

    def test_accepts_records_that_name_different_folders(
        self, repository: ModelRepository
    ) -> None:
        record = repository.record()
        other = record.model_copy(update={"folder": PurePosixPath("plugin/skills")})
        vendored = VendoredCopies(
            repository.root,
            frozendict(
                {
                    PurePosixPath(self.RECORD): record,
                    PurePosixPath("vendored/b.json"): other,
                }
            ),
            frozendict(),
            (),
            None,
        )
        assert vendored.place_problems() == []

    def test_reports_a_copy_into_the_plugin_outside_its_skills_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.write_record(
            repository.record().model_copy(
                update={"folder": PurePosixPath("plugin/extra")}
            )
        )
        repository.remove(f"{self.COPY}/LICENSE")
        repository.remove(f"{self.COPY}/SKILL.md")
        repository.write("plugin/extra/vendored/LICENSE", "MIT\n")
        repository.write(
            "plugin/extra/vendored/SKILL.md",
            "---\nname: vendored\ndescription: Words.\n---\n",
        )
        repository.skip_in_hooks("^(?:plugin/extra/vendored)/")
        repository.edit(
            "pyproject.toml", '".agents/skills/vendored"', '"plugin/extra/vendored"'
        )
        assert repository.problems() == [
            Problem(
                repository.where("plugin/extra/vendored/LICENSE"),
                "is not Markdown; remove it or move it out of the plugin",
            ),
            Problem(
                repository.where("plugin/extra/vendored/SKILL.md"),
                "is neither a skill's SKILL.md nor a playbook; move it into the mode's"
                " playbooks folder or out of the plugin",
            ),
            Problem(
                repository.where(self.RECORD),
                "folder: names no skills folder a host reads; set it to"
                " .agents/skills or plugin/skills",
            ),
        ]

    def test_reports_a_record_that_copies_outside_every_skills_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.write_record(
            repository.record().model_copy(
                update={"folder": PurePosixPath("src/nustack")}
            )
        )
        repository.remove(f"{self.COPY}/LICENSE")
        repository.remove(f"{self.COPY}/SKILL.md")
        repository.write("src/nustack/vendored/LICENSE", "MIT\n")
        repository.write(
            "src/nustack/vendored/SKILL.md",
            "---\nname: vendored\ndescription: Words.\n---\n",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.RECORD),
                "folder: names no skills folder a host reads; set it to"
                " .agents/skills or plugin/skills",
            )
        ]

    def test_reports_records_whose_folders_nest(
        self, repository: ModelRepository
    ) -> None:
        repository.write_record(
            repository.record().model_copy(
                update={
                    "folder": PurePosixPath(".agents"),
                    "skills": ("skills",),
                    "commit": None,
                    "files": frozendict(),
                }
            ),
            "vendored/nested.json",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.RECORD),
                "folder and skills: names a skill folder that vendored/nested.json"
                " names too, or one inside it or around it; give each skill folder"
                " one record",
            ),
            Problem(
                repository.where("vendored/nested.json"),
                "folder and skills: names a skill folder that vendored/copy.json names"
                " too, or one inside it or around it; give each skill folder one"
                " record",
            ),
            Problem(
                repository.where("vendored/nested.json"),
                "folder: names no skills folder a host reads; set it to"
                " .agents/skills or plugin/skills",
            ),
        ]

    def test_reports_a_folder_with_a_license_that_no_record_names(
        self, repository: ModelRepository
    ) -> None:
        repository.write(".agents/skills/dropped/LICENSE", "MIT\n")
        repository.write(".agents/skills/dropped/SKILL.md", "dropped\n")
        assert repository.problems() == [
            Problem(repository.where(".agents/skills/dropped"), self.LEFTOVER)
        ]

    def test_accepts_a_folder_without_a_license_that_no_record_names(
        self, repository: ModelRepository
    ) -> None:
        repository.write(".agents/skills/authored/SKILL.md", "authored\n")
        assert repository.problems() == []

    def test_accepts_a_record_before_its_first_sync_whose_folders_are_missing(
        self, repository: ModelRepository
    ) -> None:
        repository.record_before_first_sync()
        repository.remove(f"{self.COPY}/LICENSE")
        repository.remove(f"{self.COPY}/SKILL.md")
        assert repository.problems() == []

    def test_reports_the_files_of_a_record_before_its_first_sync(
        self, repository: ModelRepository
    ) -> None:
        repository.record_before_first_sync()
        repository.remove(f"{self.COPY}/LICENSE")
        assert repository.problems() == [
            Problem(
                repository.where(f"{self.COPY}/SKILL.md"),
                "is not in the copy its record lists; remove it, or rerun the sync"
                f" workflow, or {self.PENDING}",
            )
        ]

    def test_reports_a_missing_folder_of_a_record_before_its_first_sync(
        self, repository: ModelRepository
    ) -> None:
        record = repository.record_a_first_skill()
        repository.write_record(
            record.model_copy(update={"commit": None, "files": frozendict()})
        )
        assert repository.problems() == [
            Problem(
                repository.where(".agents/skills/first"),
                f"is missing; rerun the sync workflow, or {self.PENDING}",
            ),
            Problem(
                repository.where(f"{self.COPY}/LICENSE"),
                "is not in the copy its record lists; remove it, or rerun the sync"
                f" workflow, or {self.PENDING}",
            ),
            Problem(
                repository.where(f"{self.COPY}/SKILL.md"),
                "is not in the copy its record lists; remove it, or rerun the sync"
                f" workflow, or {self.PENDING}",
            ),
        ]

    def test_reports_a_missing_an_extra_and_an_edited_file(
        self, repository: ModelRepository
    ) -> None:
        repository.remove(f"{self.COPY}/LICENSE")
        repository.write(f"{self.COPY}/notes/extra.md", "x\n")
        repository.write(f"{self.COPY}/SKILL.md", "edited\n")
        assert repository.problems() == [
            Problem(
                repository.where(f"{self.COPY}/LICENSE"),
                f"is missing from the copy; {self.FIX}",
            ),
            Problem(
                repository.where(f"{self.COPY}/notes/extra.md"),
                f"is not in the copy its record lists; remove it, or {self.FIX}",
            ),
            Problem(
                repository.where(f"{self.COPY}/SKILL.md"),
                f"differs from upstream's bytes its record lists; {self.FIX}",
            ),
        ]

    def test_reports_an_entry_that_is_no_file(
        self, repository: ModelRepository
    ) -> None:
        repository.put_in_copy(f"{self.COPY}/pipe", Special())
        assert repository.problems() == [
            Problem(
                repository.where(f"{self.COPY}/pipe"),
                f"is no file the copy can hold; remove it, or {self.FIX}",
            )
        ]

    def test_reports_an_entry_at_a_recorded_path_that_is_no_file_once(
        self, repository: ModelRepository
    ) -> None:
        repository.put_in_copy(f"{self.COPY}/SKILL.md", Special())
        assert repository.problems() == [
            Problem(
                repository.where(f"{self.COPY}/SKILL.md"),
                f"is no file the copy can hold; remove it, or {self.FIX}",
            )
        ]

    def test_reports_only_a_symlink_in_the_copy(
        self, repository: ModelRepository
    ) -> None:
        repository.put_in_copy(f"{self.COPY}/link", Symlink())
        assert repository.problems() == [
            Problem(
                repository.where(f"{self.COPY}/link"),
                f"is a symlink, which a copy cannot hold; remove it, then {self.FIX}",
            )
        ]

    def test_reports_a_file_it_cannot_read_once_with_its_reason(
        self, repository: ModelRepository
    ) -> None:
        repository.put_in_copy(
            f"{self.COPY}/LICENSE", Unreadable("cannot be read; fix it")
        )
        repository.remove(f"{self.COPY}/LICENSE")
        assert repository.problems() == [
            Problem(repository.where(f"{self.COPY}/LICENSE"), "cannot be read; fix it")
        ]

    def test_checks_the_skill_after_a_missing_one(
        self, repository: ModelRepository
    ) -> None:
        _ = repository.record_a_first_skill()
        repository.write(f"{self.COPY}/SKILL.md", "Edited\n")
        assert repository.problems() == [
            Problem(
                repository.where(".agents/skills/first"), f"is missing; {self.FIX}"
            ),
            Problem(
                repository.where(f"{self.COPY}/SKILL.md"),
                f"differs from upstream's bytes its record lists; {self.FIX}",
            ),
        ]

    def test_keeps_the_problems_before_a_missing_skill(
        self, repository: ModelRepository
    ) -> None:
        _ = repository.record_a_first_skill()
        repository.write(".agents/skills/first/LICENSE", "Edited\n")
        repository.write(
            ".agents/skills/first/SKILL.md",
            repository.files[PurePosixPath(self.COPY, "SKILL.md")],
        )
        repository.remove(f"{self.COPY}/LICENSE")
        repository.remove(f"{self.COPY}/SKILL.md")
        assert repository.problems() == [
            Problem(
                repository.where(".agents/skills/first/LICENSE"),
                f"differs from upstream's bytes its record lists; {self.FIX}",
            ),
            Problem(repository.where(self.COPY), f"is missing; {self.FIX}"),
        ]

    def test_reports_a_missing_folder_once(self, repository: ModelRepository) -> None:
        repository.remove(f"{self.COPY}/LICENSE")
        repository.remove(f"{self.COPY}/SKILL.md")
        assert repository.problems() == [
            Problem(repository.where(self.COPY), f"is missing; {self.FIX}")
        ]

    def test_reports_a_file_in_the_folders_place_once(
        self, repository: ModelRepository
    ) -> None:
        repository.put_in_copy(f"{self.COPY}/.", NotAFolder())
        assert repository.problems() == [
            Problem(
                repository.where(f"{self.COPY}/."),
                f"is not a folder, so the check stops here; remove it, then {self.FIX}",
            )
        ]

    def test_reports_only_a_folder_that_will_not_open(
        self, repository: ModelRepository
    ) -> None:
        repository.put_in_copy(
            f"{self.COPY}/notes", Unopened("cannot be opened; fix it")
        )
        assert repository.problems() == [
            Problem(repository.where(f"{self.COPY}/notes"), "cannot be opened; fix it")
        ]

    def test_reports_the_problems_of_every_skill_it_records(
        self, repository: ModelRepository
    ) -> None:
        _ = repository.record_a_first_skill()
        for name in ("LICENSE", "SKILL.md"):
            repository.write(
                f".agents/skills/first/{name}",
                repository.files[PurePosixPath(self.COPY, name)],
            )
        repository.write(".agents/skills/first/LICENSE", "Edited\n")
        repository.write(f"{self.COPY}/SKILL.md", "Edited\n")
        assert repository.problems() == [
            Problem(
                repository.where(".agents/skills/first/LICENSE"),
                f"differs from upstream's bytes its record lists; {self.FIX}",
            ),
            Problem(
                repository.where(".agents/skills/vendored/SKILL.md"),
                f"differs from upstream's bytes its record lists; {self.FIX}",
            ),
        ]

    @pytest.mark.parametrize(
        "skill", ["principle-naming", "language-python", "nus-mode", "other-mode"]
    )
    def test_reports_a_copy_of_a_skill_named_as_an_authored_one(
        self, repository: ModelRepository, skill: str
    ) -> None:
        repository.rename_copy(skill)
        assert repository.problems() == [
            Problem(
                repository.where(self.RECORD),
                "is invalid: skills: lists a skill whose name starts with principle-"
                " or language- or ends in -mode, which only nustack's authors write;"
                " drop it from skills",
            )
        ]

    def test_reports_a_record_of_an_authored_skill_beside_its_own_problems(
        self, repository: ModelRepository
    ) -> None:
        repository.write_record(
            repository.record().model_copy(
                update={
                    "folder": PurePosixPath("plugin/skills"),
                    "skills": ("principle-naming",),
                    "commit": None,
                    "files": frozendict(),
                }
            ),
            "vendored/authored.json",
        )
        repository.edit(
            self.AUTHORED,
            "Name each part for what it does.",
            "Claude names each part, 2026.",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.AUTHORED),
                "line 11 names an agent host, a model or a host's folder; state the"
                " rule for every host",
            ),
            Problem(
                repository.where(self.AUTHORED),
                "line 11 holds a date or a year; state the rule without it, since skill"
                " text outlives any date",
            ),
            Problem(
                repository.where("vendored/authored.json"),
                "is invalid: skills: lists a skill whose name starts with principle-"
                " or language- or ends in -mode, which only nustack's authors write;"
                " drop it from skills",
            ),
        ]

    def test_reports_only_the_authored_skills_own_problems_without_the_record(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            self.AUTHORED,
            "Name each part for what it does.",
            "Claude names each part, 2026.",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.AUTHORED),
                "line 11 names an agent host, a model or a host's folder; state the"
                " rule for every host",
            ),
            Problem(
                repository.where(self.AUTHORED),
                "line 11 holds a date or a year; state the rule without it, since skill"
                " text outlives any date",
            ),
        ]

    @pytest.mark.parametrize(
        "skill", ["principled", "languages", "moderate", "darkmode", "a-b"]
    )
    def test_accepts_a_copy_of_a_skill_named_unlike_an_authored_one(
        self, repository: ModelRepository, skill: str
    ) -> None:
        repository.rename_copy(skill)
        assert repository.problems() == []

    def test_reports_a_copy_from_the_repository_the_manifests_name(
        self, repository: ModelRepository
    ) -> None:
        repository.name_home("https://github.com/Up/Skills")
        assert repository.problems() == [
            Problem(repository.where(self.RECORD), self.SELF_COPY)
        ]

    def test_reports_only_the_upstream_of_a_copy_from_this_repository(
        self, repository: ModelRepository
    ) -> None:
        repository.name_home("https://github.com/Up/Skills")
        repository.write(f"{self.COPY}/SKILL.md", "edited\n")
        repository.edit(self.HOOKS, self.EXCLUDE, "")
        repository.edit("pyproject.toml", '".agents/skills/vendored"', '"other"')
        assert repository.problems() == [
            Problem(repository.where(self.RECORD), self.SELF_COPY)
        ]

    def test_reports_only_the_upstream_of_a_plugin_copy_from_this_repository(
        self, repository: ModelRepository
    ) -> None:
        repository.vendor_into_plugin()
        repository.name_home("https://github.com/Up/Skills")
        repository.edit(
            "README.md",
            "| [vendored](plugin/skills/vendored/SKILL.md) | Words. |\n",
            "",
        )
        assert repository.problems() == [
            Problem(repository.where(self.RECORD), self.SELF_COPY)
        ]

    def test_reports_a_copy_from_this_repository_beside_a_missing_config(
        self, repository: ModelRepository
    ) -> None:
        repository.name_home("https://github.com/Up/Skills")
        repository.remove(self.HOOKS)
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "is missing; restore it from the repository",
            ),
            Problem(repository.where(self.RECORD), self.SELF_COPY),
        ]

    def test_reports_a_copy_from_this_repository_beside_a_record_it_cannot_read(
        self, repository: ModelRepository
    ) -> None:
        repository.name_home("https://github.com/Up/Skills")
        repository.write("vendored/other.json", "{")
        assert repository.problems() == [
            Problem(
                repository.where("vendored/other.json"),
                "is invalid: the file: fix the JSON (EOF while parsing an object"
                " at line 1 column 1)",
            ),
            Problem(repository.where(self.RECORD), self.SELF_COPY),
        ]

    def test_reports_a_copy_from_this_repository_by_its_www_host(
        self, repository: ModelRepository
    ) -> None:
        vendored = replace(
            Repository(repository.snapshot()).vendored,
            home=RepositoryUrl.parse("https://www.github.com/up/skills"),
        )
        assert vendored.problems(None, None, None) == [
            Problem(repository.where(self.RECORD), self.SELF_COPY)
        ]

    def test_accepts_a_copy_from_another_repository(
        self, repository: ModelRepository
    ) -> None:
        vendored = replace(
            Repository(repository.snapshot()).vendored,
            home=RepositoryUrl.parse("https://github.com/up/other"),
        )
        assert vendored.problems(None, None, None) == []

    def test_reports_a_copy_from_this_repository(
        self, repository: ModelRepository
    ) -> None:
        vendored = replace(
            Repository(repository.snapshot()).vendored,
            home=RepositoryUrl.parse("https://github.com/Up/Skills"),
        )
        assert vendored.problems(None, None, None) == [
            Problem(repository.where(self.RECORD), self.SELF_COPY)
        ]

    def test_reports_a_missing_rewriting_hook(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            self.HOOKS, "      - id: mixed-line-ending\n", "      - id: x\n"
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "has no mixed-line-ending hook; restore it, with an exclude of the"
                " vendored skill folders",
            )
        ]

    @pytest.mark.parametrize(
        "exclude",
        [
            "        exclude: ^(?:\\.agents/skills/other)/\n",
            "        exclude: ^\\.agents/skills/vendored/\n",
            "        exclude: ^(?:.agents/skills/vendored)/\n",
        ],
    )
    def test_reports_a_rewriting_hook_that_skips_another_pattern(
        self, repository: ModelRepository, exclude: str
    ) -> None:
        repository.edit(
            self.HOOKS,
            f"      - id: mixed-line-ending\n{self.EXCLUDE}",
            f"      - id: mixed-line-ending\n{exclude}",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "has the mixed-line-ending hook skip other folders than the vendored"
                " skill folders; set its exclude to ^(?:, then each vendored skill"
                " folder passed through Python's re.escape, sorted and joined by |,"
                " then )/",
            )
        ]

    def test_reports_a_rewriting_hook_that_skips_nothing(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            self.HOOKS,
            f"      - id: mixed-line-ending\n{self.EXCLUDE}",
            "      - id: mixed-line-ending\n",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "has the mixed-line-ending hook skip none of the vendored skill"
                " folders; set its exclude to ^(?:, then each vendored skill folder"
                " passed through Python's re.escape, sorted and joined by |, then )/",
            )
        ]

    def test_reports_a_second_rewriting_hook_that_skips_nothing(
        self, repository: ModelRepository
    ) -> None:
        hook = f"      - id: mixed-line-ending\n{self.EXCLUDE}"
        repository.edit(self.HOOKS, hook, hook + "      - id: mixed-line-ending\n")
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "has the mixed-line-ending hook skip none of the vendored skill"
                " folders; set its exclude to ^(?:, then each vendored skill folder"
                " passed through Python's re.escape, sorted and joined by |, then )/",
            )
        ]

    def test_accepts_hooks_skipping_each_folder_through_re_escape_and_ruff_with_a_slash(
        self, repository: ModelRepository
    ) -> None:
        record = repository.record()
        files = record.files
        repository.write_record(
            record.model_copy(
                update={
                    "skills": ("vendored", "a-b"),
                    "files": files
                    | {
                        "a-b/LICENSE": files["vendored/LICENSE"],
                        "a-b/SKILL.md": files["vendored/SKILL.md"],
                    },
                }
            )
        )
        repository.write(".agents/skills/a-b/LICENSE", "MIT\n")
        repository.write(
            ".agents/skills/a-b/SKILL.md",
            "---\nname: vendored\ndescription: Words.\n---\n",
        )
        repository.skip_in_hooks(
            "^(?:\\.agents/skills/a\\-b|\\.agents/skills/vendored)/",
        )
        repository.edit(
            "pyproject.toml",
            '".agents/skills/vendored"',
            '".agents/skills/vendored", ".agents/skills/a-b/"',
        )
        repository.edit(
            ".gitattributes",
            ".agents/skills/vendored/** -text\n",
            ".agents/skills/a-b/** -text\n.agents/skills/vendored/** -text\n",
        )
        assert repository.problems() == []

    def test_accepts_hooks_that_skip_nothing_when_no_record_names_a_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.remove(self.RECORD)
        repository.remove(f"{self.COPY}/LICENSE")
        repository.remove(f"{self.COPY}/SKILL.md")
        repository.write(
            self.HOOKS,
            "repos:\n  - repo: local\n    hooks:\n"
            "      - id: end-of-file-fixer\n"
            "      - id: fix-byte-order-marker\n"
            "      - id: mixed-line-ending\n"
            "      - id: trailing-whitespace\n"
            "      - id: markdownlint-cli2\n",
        )
        hooks = Repository(repository.snapshot()).hooks
        assert isinstance(hooks, Hooks)
        assert Repository(repository.snapshot()).vendored.hook_problems(hooks) == []

    def test_accepts_a_second_rewriting_hook_that_skips_the_folders(
        self, repository: ModelRepository
    ) -> None:
        hook = f"      - id: mixed-line-ending\n{self.EXCLUDE}"
        repository.edit(self.HOOKS, hook, hook + hook)
        assert repository.problems() == []

    def test_reports_the_excludes_a_removed_record_leaves(
        self, repository: ModelRepository
    ) -> None:
        repository.remove(self.RECORD)
        repository.edit(
            self.HOOKS,
            f"      - id: trailing-whitespace\n{self.EXCLUDE}",
            "      - id: trailing-whitespace\n",
        )
        assert repository.problems() == [
            Problem(repository.where(self.COPY), self.LEFTOVER),
            Problem(
                repository.where(self.HOOKS),
                f"has the end-of-file-fixer hook skip files though"
                f" {self.NO_FOLDER}; remove its exclude",
            ),
            Problem(
                repository.where(self.HOOKS),
                f"has the fix-byte-order-marker hook skip files though"
                f" {self.NO_FOLDER}; remove its exclude",
            ),
            Problem(
                repository.where(self.HOOKS),
                f"has the mixed-line-ending hook skip files though"
                f" {self.NO_FOLDER}; remove its exclude",
            ),
            Problem(
                repository.where(self.HOOKS),
                f"has the markdownlint-cli2 hook skip files though"
                f" {self.NO_FOLDER}; remove its exclude",
            ),
            Problem(
                repository.where("pyproject.toml"),
                f"has a [tool.ruff] extend-exclude though {self.NO_FOLDER};"
                " remove extend-exclude",
            ),
            Problem(
                repository.where(".gitattributes"),
                f"unsets text though {self.NO_FOLDER}; remove each -text",
            ),
        ]

    def test_reports_a_folder_the_hooks_and_ruff_skip_nowhere(
        self, repository: ModelRepository
    ) -> None:
        repository.skip_in_hooks("^(?:other)/")
        repository.edit("pyproject.toml", '".agents/skills/vendored"', '"other"')
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "has the end-of-file-fixer hook skip other folders than the vendored"
                " skill folders; set its exclude to ^(?:, then each vendored skill"
                " folder passed through Python's re.escape, sorted and joined by |,"
                " then )/",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the fix-byte-order-marker hook skip other folders than the"
                " vendored skill folders; set its exclude to ^(?:, then each vendored"
                " skill folder passed through Python's re.escape, sorted and joined by"
                " |, then )/",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the mixed-line-ending hook skip other folders than the vendored"
                " skill folders; set its exclude to ^(?:, then each vendored skill"
                " folder passed through Python's re.escape, sorted and joined by |,"
                " then )/",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the trailing-whitespace hook skip other folders than the"
                " vendored skill folders; set its exclude to ^(?:, then each vendored"
                " skill folder passed through Python's re.escape, sorted and joined by"
                " |, then )/",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the markdownlint-cli2 hook skip other folders than the vendored"
                " skill folders; set its exclude to ^(?:, then each vendored skill"
                " folder passed through Python's re.escape, sorted and joined by |,"
                " then )/",
            ),
            Problem(
                repository.where("pyproject.toml"),
                "has a [tool.ruff] extend-exclude other than the vendored skill"
                " folders; set it to exactly the folders the records name",
            ),
        ]

    def test_reports_a_config_that_does_not_parse(
        self, repository: ModelRepository
    ) -> None:
        repository.write(self.HOOKS, "repos: [\n")
        repository.edit("pyproject.toml", '".agents/skills/vendored"', '"other"')
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "is invalid: it is not valid YAML on line 2; fix it",
            ),
            Problem(
                repository.where("pyproject.toml"),
                "has a [tool.ruff] extend-exclude other than the vendored skill"
                " folders; set it to exactly the folders the records name",
            ),
        ]

    def test_reports_a_ruff_exclude_no_record_names(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            "pyproject.toml",
            '".agents/skills/vendored"',
            '".agents/skills/vendored", "src"',
        )
        assert repository.problems() == [
            Problem(
                repository.where("pyproject.toml"),
                "has a [tool.ruff] extend-exclude other than the vendored skill"
                " folders; set it to exactly the folders the records name",
            )
        ]

    @pytest.mark.parametrize(
        "attributes",
        [
            "plugin/** text eol=lf\n",
            ".agents/skills/vendored/** -text\nplugin/** text eol=lf\n",
            "plugin/** text eol=lf\n.agents/skills/vendored/** text\n",
            "plugin/** -text\n.agents/skills/vendored/** -text\n",
            (
                "plugin/** text eol=lf\n.agents/skills/vendored/** -text\n"
                ".agents/skills/other/** -text\n"
            ),
        ],
    )
    def test_reports_attributes_that_do_not_end_on_unsetting_text_for_the_copies(
        self, repository: ModelRepository, attributes: str
    ) -> None:
        repository.write(".gitattributes", attributes)
        assert repository.problems() == [
            Problem(
                repository.where(".gitattributes"),
                "does not end on a line <folder>/** -text for each vendored skill"
                " folder, sorted, with no other line unsetting text; end it on"
                " exactly those lines, so Git keeps each copy's bytes",
            )
        ]
