"""The test suite mirrors what it tests, tier by tier.

Smoke tests, the settings tests, `conftest.py` and fixtures need no source, a test
of a shared helper mirrors the helper, and a TypeScript test may mirror a shell
script; a module outside the tiers or mirroring nothing, or a helper inside a tier,
is a Problem.
"""

from pathlib import Path
from pathlib import PurePosixPath

import pytest

from nustack.problem import Problem
from nustack.repository.suite import Suite


class TestSuite:
    """A reader finds a module's tests at the same path under a tier folder.

    Only the exempt files mirror no source, and only tests sit in a tier.
    """

    ROOT = Path("/r")

    SOURCES = frozenset(
        {
            PurePosixPath("src/kit/tool.py"),
            PurePosixPath("plugin/opencode.ts"),
            PurePosixPath("plugin/hooks/reload.sh"),
        }
    )

    @pytest.mark.parametrize(
        "test",
        [
            "tests/unit/kit/test_tool.py",
            "tests/integration/kit/test_tool.py",
            "tests/unit/plugin/opencode.test.ts",
            "tests/integration/plugin/hooks/reload.test.ts",
            "tests/smoke/test_anything.py",
            "tests/unit/test_settings.py",
            "tests/integration/test_settings.py",
            "tests/unit/settings.test.ts",
            "tests/conftest.py",
            "tests/unit/conftest.py",
            "tests/integration/kit/conftest.py",
            "tests/fixtures/repository.py",
            "tests/fixtures/registry.ts",
        ],
    )
    def test_accepts_a_module_that_mirrors_its_source_or_is_exempt(
        self, test: str
    ) -> None:
        assert Suite(self.ROOT, self.SOURCES, (PurePosixPath(test),)).problems() == []

    @pytest.mark.parametrize(
        "helper",
        [
            ("tests/fixtures/deadline.py", "tests/unit/fixtures/test_deadline.py"),
            (
                "tests/fixtures/sync/git.py",
                "tests/integration/fixtures/sync/test_git.py",
            ),
            ("tests/fixtures/registry.ts", "tests/unit/fixtures/registry.test.ts"),
        ],
    )
    def test_accepts_a_test_of_a_shared_helper_that_mirrors_it(
        self, helper: tuple[str, str]
    ) -> None:
        tests = tuple(PurePosixPath(path) for path in helper)
        assert Suite(self.ROOT, self.SOURCES, tests).problems() == []

    @pytest.mark.parametrize(
        ("test", "what"),
        [
            (
                "tests/unit/kit/test_gone.py",
                (
                    "mirrors src/kit/gone.py, which does not exist; move it to mirror"
                    " the source it tests, or remove it"
                ),
            ),
            (
                "tests/unit/test_tool.py",
                (
                    "mirrors src/tool.py, which does not exist; move it to mirror the"
                    " source it tests, or remove it"
                ),
            ),
            (
                "tests/integration/plugin/gone.test.ts",
                (
                    "mirrors plugin/gone.ts or plugin/gone.sh, which does not exist;"
                    " move it to mirror the source it tests, or remove it"
                ),
            ),
            (
                "tests/unit/kit/test_reload.py",
                (
                    "mirrors src/kit/reload.py, which does not exist; move it to"
                    " mirror the source it tests, or remove it"
                ),
            ),
            (
                "tests/unit/fixtures/test_gone.py",
                (
                    "mirrors tests/fixtures/gone.py, which does not exist; move it to"
                    " mirror the source it tests, or remove it"
                ),
            ),
            (
                "tests/unit/fixtures/gone.test.ts",
                (
                    "mirrors tests/fixtures/gone.ts or tests/fixtures/gone.sh, which"
                    " does not exist; move it to mirror the source it tests, or remove"
                    " it"
                ),
            ),
        ],
    )
    def test_reports_a_module_that_mirrors_nothing(self, test: str, what: str) -> None:
        assert Suite(self.ROOT, self.SOURCES, (PurePosixPath(test),)).problems() == [
            Problem(self.ROOT / test, what)
        ]

    @pytest.mark.parametrize(
        "test",
        ["tests/harness/test_tool.py", "tests/test_tool.py", "tests/loader/a.test.ts"],
    )
    def test_reports_a_module_outside_the_tier_folders(self, test: str) -> None:
        assert Suite(self.ROOT, self.SOURCES, (PurePosixPath(test),)).problems() == [
            Problem(
                self.ROOT / test,
                "sits outside the tier folders unit, integration, smoke under tests;"
                " move it into the tier of the test it holds",
            )
        ]

    @pytest.mark.parametrize(
        "helper",
        [
            "tests/unit/kit/helpers.ts",
            "tests/integration/fakes.py",
            "tests/smoke/data.json",
        ],
    )
    def test_reports_a_file_in_a_tier_folder_that_is_no_test(self, helper: str) -> None:
        assert Suite(self.ROOT, self.SOURCES, (PurePosixPath(helper),)).problems() == [
            Problem(
                self.ROOT / helper,
                "is no test, yet sits in a tier folder; move it into tests/fixtures,"
                " beside the tiers, which holds what tests share",
            )
        ]
