"""Every rewriting tool skips the folder the sync writes the vendored copy to.

A config the check cannot read, or that lacks what it reads, is a Problem.
"""

import pytest

from nustack.problem import Problem
from nustack.repository.vendored import Hooks
from nustack.repository.vendored import InvalidConfigError
from nustack.repository.vendored import Workflow
lazy from tests.fixtures.repository import ModelRepository


class TestHooks:
    """The check sees each hook that could rewrite a file.

    A config it cannot read is refused naming why.
    """

    def test_lists_every_hook_of_every_repository(self) -> None:
        hooks = Hooks.parse(
            b"repos:\n  - hooks:\n      - id: a\n        exclude: x\n"
            b"  - hooks:\n      - id: b\n"
        )
        assert [(hook.id, hook.exclude) for hook in hooks.hooks] == [
            ("a", "x"),
            ("b", None),
        ]

    @pytest.mark.parametrize(
        ("content", "reason"),
        [
            (b"repos: [\n", "it is not valid YAML; fix it"),
            (
                b"repos:\n  - hooks:\n      - exclude: x\n",
                (
                    "needs a repos list, each with a hooks list of entries that each"
                    " hold an id; fix its shape"
                ),
            ),
        ],
    )
    def test_refuses_a_file_it_cannot_read(self, content: bytes, reason: str) -> None:
        with pytest.raises(InvalidConfigError) as caught:
            Hooks.parse(content)
        assert str(caught.value) == reason


class TestWorkflow:
    """The check learns where the sync writes the copy from the workflow itself.

    A job environment of the wrong shape is refused.
    """

    def test_reads_each_jobs_environment(self) -> None:
        workflow = Workflow.parse(b"jobs:\n  a:\n    env:\n      X: y\n  b: {}\n")
        assert {name: dict(job.env) for name, job in workflow.jobs.items()} == {
            "a": {"X": "y"},
            "b": {},
        }

    def test_refuses_a_job_environment_of_the_wrong_shape(self) -> None:
        with pytest.raises(InvalidConfigError) as caught:
            Workflow.parse(b"jobs:\n  a:\n    env: [x]\n")
        assert str(caught.value) == (
            "needs a jobs mapping, each job with any env a mapping of strings;"
            " fix its shape"
        )


class TestVendoredCopy:
    """Every rewriting hook and Ruff skip the folder the sync writes the copy to.

    A trailing slash names the same folder, and a missing destination, hook or
    config, or a config that does not parse, is a Problem.
    """

    HOOKS = ".pre-commit-config.yaml"
    WORKFLOW = ".github/workflows/sync-writing-for-agents.yml"

    def test_agrees_in_the_model_repository(self, repository: ModelRepository) -> None:
        assert repository.problems() == []

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            ("DESTINATION: .agents/skills/vendored", "OTHER: x"),
            ("sync:", "copy:"),
        ],
    )
    def test_without_a_destination_is_a_problem(
        self, repository: ModelRepository, old: str, new: str
    ) -> None:
        repository.edit(self.WORKFLOW, old, new)
        assert repository.problems() == [
            Problem(
                repository.where(self.WORKFLOW),
                "has no DESTINATION in its sync job's env; set it to the folder the"
                " sync copies into",
            )
        ]

    def test_reports_a_destination_the_hooks_and_ruff_skip_nowhere(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            self.WORKFLOW, "DESTINATION: .agents/skills/vendored", "DESTINATION: v2"
        )
        assert repository.problems() == [
            Problem(
                repository.where(self.HOOKS),
                "has the end-of-file-fixer hook skip a folder other than the sync"
                " workflow's DESTINATION; set its exclude to ^, that folder with"
                " each . escaped, and /",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the fix-byte-order-marker hook skip a folder other than the sync"
                " workflow's DESTINATION; set its exclude to ^, that folder with"
                " each . escaped, and /",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the mixed-line-ending hook skip a folder other than the sync"
                " workflow's DESTINATION; set its exclude to ^, that folder with"
                " each . escaped, and /",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the trailing-whitespace hook skip a folder other than the sync"
                " workflow's DESTINATION; set its exclude to ^, that folder with"
                " each . escaped, and /",
            ),
            Problem(
                repository.where(self.HOOKS),
                "has the markdownlint-cli2 hook skip a folder other than the sync"
                " workflow's DESTINATION; set its exclude to ^, that folder with"
                " each . escaped, and /",
            ),
            Problem(
                repository.where("pyproject.toml"),
                "has a [tool.ruff] extend-exclude that leaves out the sync workflow's"
                " DESTINATION; add that folder to it",
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
                "has the mixed-line-ending hook skip a folder other than the sync"
                " workflow's DESTINATION; set its exclude to ^, that folder with"
                " each . escaped, and /",
            )
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
                " sync workflow's DESTINATION folder",
            )
        ]

    def test_reads_a_trailing_slash_on_the_destination_as_the_same_folder(
        self, repository: ModelRepository
    ) -> None:
        repository.edit(
            self.WORKFLOW,
            "DESTINATION: .agents/skills/vendored",
            "DESTINATION: .agents/skills/vendored/",
        )
        repository.edit(
            "pyproject.toml", '".agents/skills/vendored"', '".agents/skills/vendored/"'
        )
        assert repository.problems() == []

    @pytest.mark.parametrize(
        ("path", "content", "what"),
        [
            (HOOKS, "repos: [\n", "is invalid: it is not valid YAML; fix it"),
            (
                WORKFLOW,
                "jobs: []\n",
                (
                    "is invalid: needs a jobs mapping, each job with any env a mapping"
                    " of strings; fix its shape"
                ),
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
