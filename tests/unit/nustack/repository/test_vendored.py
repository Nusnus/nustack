"""Every rewriting tool skips the folder the sync writes the vendored copy to.

A config the check cannot read, or that lacks what it reads, is a Problem.
"""

from pathlib import PurePosixPath

import pytest

from nustack.problem import Problem
from nustack.repository.config import InvalidConfigError
from nustack.repository.vendored import Hooks
from nustack.repository.vendored import SyncWorkflow
from nustack.repository.vendored import VendoredCopy
lazy from tests.fixtures.repository import ModelRepository


class TestHooks:
    """The check sees each hook that could rewrite a file.

    A hook with no id is refused, naming where it sits.
    """

    def test_refuses_a_hook_with_no_id_naming_where_it_sits(self) -> None:
        with pytest.raises(InvalidConfigError) as caught:
            Hooks.parse(
                b"repos:\n  - hooks:\n      - exclude: x\n  - hooks:\n      - id: b\n"
            )
        assert str(caught.value) == "repos.0.hooks.0.id: add it"

    def test_lists_every_hook_of_every_repository(self) -> None:
        hooks = Hooks.parse(
            b"repos:\n  - hooks:\n      - id: a\n        exclude: x\n"
            b"  - hooks:\n      - id: b\n"
        )
        assert [(hook.id, hook.exclude) for hook in hooks.hooks] == [
            ("a", "x"),
            ("b", None),
        ]


class TestSyncWorkflow:
    """The check learns where the sync writes the copy from the workflow itself.

    A null env value stays null and a date reads as text. Jobs, a job, its key or its
    environment of the wrong shape is refused, with a reason that names no key read
    from the file, even a job named as Pydantic marks a key's own error.
    """

    def test_reads_each_jobs_environment(self) -> None:
        workflow = SyncWorkflow.parse(
            b"jobs:\n  a:\n    env:\n      X: y\n      N: 1\n      B: true\n"
            b"      Z: ~\n      D: 2026-01-01\n  b: {}\n"
        )
        assert {name: dict(job.env) for name, job in workflow.jobs.items()} == {
            "a": {"X": "y", "N": 1, "B": True, "Z": None, "D": "2026-01-01"},
            "b": {},
        }

    @pytest.mark.parametrize(
        ("content", "reason"),
        [
            (
                b"jobs:\n  a:\n    env: [x]\n",
                (
                    "jobs.<key>.env: make it an object of names to text, numbers,"
                    " booleans or nulls"
                ),
            ),
            (
                b"jobs:\n  a:\n    env: {X: [1]}\n",
                (
                    "jobs.<key>.env: make it an object of names to text, numbers,"
                    " booleans or nulls"
                ),
            ),
            (
                b"jobs:\n  a:\n    env: {1: x}\n",
                (
                    "jobs.<key>.env: make it an object of names to text, numbers,"
                    " booleans or nulls"
                ),
            ),
            (b"jobs:\n  1: {}\n", "jobs: for each key, make it a string"),
            (b"jobs:\n  a: 1\n", "jobs.<key>: make it an object of keys and values"),
            (
                b'jobs:\n  "[key]": 1\n',
                "jobs.<key>: make it an object of keys and values",
            ),
            (b"jobs: []\n", "jobs: make it an object of keys and values"),
        ],
    )
    def test_refuses_jobs_of_the_wrong_shape_naming_no_key(
        self, content: bytes, reason: str
    ) -> None:
        with pytest.raises(InvalidConfigError) as caught:
            SyncWorkflow.parse(content)
        assert str(caught.value) == reason


class TestVendoredCopy:
    """Every rewriting hook and Ruff skip the folder the sync writes the copy to.

    A missing folder, or one YAML reads as a number or a boolean, is a Problem,
    though a quoted one reads as text. So is a folder outside the repository or
    at its root, or one that is not a plain path. A trailing slash names the same
    folder, and a hook skips the folder passed through Python's re.escape. A
    missing rewriting hook, a folder nothing skips, a hook that skips another
    folder, a second hook that skips nothing, a config that does not parse or a
    missing config is a Problem.
    """

    HOOKS = ".pre-commit-config.yaml"
    WORKFLOW = ".github/workflows/sync-writing-for-agents.yml"

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            ("FOLDER: .agents/skills/vendored", "OTHER: x"),
            ("sync:", "copy:"),
        ],
    )
    def test_reports_a_missing_folder(
        self, repository: ModelRepository, old: str, new: str
    ) -> None:
        repository.edit(self.WORKFLOW, old, new)
        assert repository.problems() == [
            Problem(
                repository.where(self.WORKFLOW),
                "has no FOLDER in its sync job's env; set it to the folder the"
                " sync copies into",
            )
        ]

    @pytest.mark.parametrize("value", ["1", "1.5", "true"])
    def test_reports_a_folder_yaml_reads_as_a_number_or_a_boolean(
        self, repository: ModelRepository, value: str
    ) -> None:
        repository.edit(
            self.WORKFLOW,
            "FOLDER: .agents/skills/vendored",
            f"FOLDER: {value}",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.WORKFLOW),
                "has a FOLDER in its sync job's env that YAML reads as a number"
                " or a boolean; quote it",
            )
        ]

    def test_accepts_a_quoted_folder_yaml_would_read_as_a_number(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.WORKFLOW, "FOLDER: .agents/skills/vendored", 'FOLDER: "1"')
        repository.edit("pyproject.toml", '".agents/skills/vendored"', '"1"')
        for hook in VendoredCopy.REWRITERS:
            repository.edit(
                self.HOOKS,
                f"      - id: {hook}\n        exclude: ^\\.agents/skills/vendored/\n",
                f"      - id: {hook}\n        exclude: ^1/\n",
            )
        assert repository.problems() == []

    @pytest.mark.parametrize(
        "value", ['""', "/", "~", ".", "./", "../out", "/abs", "a/../.."]
    )
    def test_reports_a_folder_outside_the_repository_or_at_its_root(
        self, repository: ModelRepository, value: str
    ) -> None:
        repository.edit(
            self.WORKFLOW,
            "FOLDER: .agents/skills/vendored",
            f"FOLDER: {value}",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.WORKFLOW),
                "has a FOLDER in its sync job's env that names no folder inside"
                " the repository; set it to the folder the sync copies into",
            )
        ]

    @pytest.mark.parametrize(
        "value",
        [
            "./.agents/skills/vendored",
            ".agents/./skills/vendored",
            ".agents//skills/vendored",
            ".agents/skills/vendored//",
            ".agents/skills/vendored/.",
        ],
    )
    def test_reports_a_folder_that_is_not_a_plain_path(
        self, repository: ModelRepository, value: str
    ) -> None:
        repository.edit(
            self.WORKFLOW,
            "FOLDER: .agents/skills/vendored",
            f"FOLDER: {value}",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.WORKFLOW),
                "has a FOLDER in its sync job's env that is not a plain path;"
                " write it with no . part, no //, and no more than one / at its end",
            )
        ]

    def test_reads_a_trailing_slash_on_the_folder_as_the_same_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            self.WORKFLOW,
            "FOLDER: .agents/skills/vendored",
            "FOLDER: .agents/skills/vendored/",
        )
        repository.edit(
            "pyproject.toml", '".agents/skills/vendored"', '".agents/skills/vendored/"'
        )
        assert repository.problems() == []

    @pytest.mark.parametrize(
        ("folder", "exclude"),
        [
            (".agents/skills/vendored.v2", "^\\.agents/skills/vendored\\.v2/"),
            ("a+b", "^a\\+b/"),
            ("a(b", "^a\\(b/"),
            ("a-b", "^a\\-b/"),
            ("a*b", "^a\\*b/"),
            ("a[b", "^a\\[b/"),
        ],
    )
    def test_accepts_hooks_that_skip_a_folder_passed_through_re_escape(
        self, repository: ModelRepository, folder: str, exclude: str
    ) -> None:
        repository.edit(
            self.WORKFLOW,
            "FOLDER: .agents/skills/vendored",
            f"FOLDER: {folder}",
        )
        repository.edit("pyproject.toml", '".agents/skills/vendored"', f'"{folder}"')
        hooks = repository.files[PurePosixPath(self.HOOKS)].decode()
        repository.write(
            self.HOOKS, hooks.replace("^\\.agents/skills/vendored/", exclude)
        )
        assert repository.problems() == []

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
                " folder the sync workflow's FOLDER env var names",
            )
        ]

    def test_reports_a_folder_the_hooks_and_ruff_skip_nowhere(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(self.WORKFLOW, "FOLDER: .agents/skills/vendored", "FOLDER: v2")
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "has the end-of-file-fixer hook skip a folder other than the one"
                " the sync workflow's FOLDER env var names; set its exclude to ^, that"
                " folder passed through Python's re.escape, and /",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the fix-byte-order-marker hook skip a folder other than the one"
                " the sync workflow's FOLDER env var names; set its exclude to ^, that"
                " folder passed through Python's re.escape, and /",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the mixed-line-ending hook skip a folder other than the one"
                " the sync workflow's FOLDER env var names; set its exclude to ^, that"
                " folder passed through Python's re.escape, and /",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the trailing-whitespace hook skip a folder other than the one"
                " the sync workflow's FOLDER env var names; set its exclude to ^, that"
                " folder passed through Python's re.escape, and /",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the markdownlint-cli2 hook skip a folder other than the one"
                " the sync workflow's FOLDER env var names; set its exclude to ^, that"
                " folder passed through Python's re.escape, and /",
            ),
            Problem(
                repository.where("pyproject.toml"),
                "has a [tool.ruff] extend-exclude that leaves out the folder the sync"
                " workflow's FOLDER env var names; add that folder to it",
            ),
        ]

    @pytest.mark.parametrize(
        "exclude",
        [
            "        exclude: ^\\.agents/skills/other/\n",
            "        exclude: ^\\.agents/skills/vendored\n",
            "        exclude: ^.agents/skills/vendored/\n",
            "",
        ],
    )
    def test_reports_a_rewriting_hook_that_skips_another_folder(
        self, repository: ModelRepository, exclude: str
    ) -> None:
        repository.edit(
            self.HOOKS,
            "      - id: mixed-line-ending\n"
            "        exclude: ^\\.agents/skills/vendored/\n",
            f"      - id: mixed-line-ending\n{exclude}",
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "has the mixed-line-ending hook skip a folder other than the one"
                " the sync workflow's FOLDER env var names; set its exclude to ^, that"
                " folder passed through Python's re.escape, and /",
            )
        ]

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            (
                "      - id: mixed-line-ending\n",
                "      - id: mixed-line-ending\n      - id: mixed-line-ending\n",
            ),
            (
                (
                    "      - id: mixed-line-ending\n"
                    "        exclude: ^\\.agents/skills/vendored/\n"
                ),
                (
                    "      - id: mixed-line-ending\n"
                    "        exclude: ^\\.agents/skills/vendored/\n"
                    "      - id: mixed-line-ending\n"
                ),
            ),
        ],
    )
    def test_reports_a_second_rewriting_hook_that_skips_nothing(
        self, repository: ModelRepository, old: str, new: str
    ) -> None:
        repository.edit(self.HOOKS, old, new)
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "has the mixed-line-ending hook skip a folder other than the one"
                " the sync workflow's FOLDER env var names; set its exclude to ^, that"
                " folder passed through Python's re.escape, and /",
            )
        ]

    def test_accepts_a_second_rewriting_hook_that_skips_the_folder(
        self, repository: ModelRepository
    ) -> None:
        hook = (
            "      - id: mixed-line-ending\n"
            "        exclude: ^\\.agents/skills/vendored/\n"
        )
        repository.edit(self.HOOKS, hook, hook + hook)
        assert repository.problems() == []

    def test_accepts_a_folder_of_one_letter(self, repository: ModelRepository) -> None:
        repository.edit(self.WORKFLOW, "FOLDER: .agents/skills/vendored", "FOLDER: X")
        repository.edit("pyproject.toml", '".agents/skills/vendored"', '"X"')
        for hook in VendoredCopy.REWRITERS:
            repository.edit(
                self.HOOKS,
                f"      - id: {hook}\n        exclude: ^\\.agents/skills/vendored/\n",
                f"      - id: {hook}\n        exclude: ^X/\n",
            )
        assert repository.problems() == []

    @pytest.mark.parametrize(
        ("path", "content", "what"),
        [
            (HOOKS, "repos: [\n", "is invalid: it is not valid YAML on line 2; fix it"),
            (
                WORKFLOW,
                "jobs: []\n",
                "is invalid: jobs: make it an object of keys and values",
            ),
        ],
    )
    def test_reports_a_config_that_does_not_parse(
        self, repository: ModelRepository, path: str, content: str, what: str
    ) -> None:
        repository.write(path, content)
        assert repository.problems() == [Problem(repository.where(path), what)]

    @pytest.mark.parametrize("path", [HOOKS, WORKFLOW])
    def test_reports_a_missing_config(
        self, repository: ModelRepository, path: str
    ) -> None:
        repository.remove(path)
        assert repository.problems() == [
            Problem(
                repository.where(path), "is missing; restore it from the repository"
            )
        ]
