"""The test suite's layout: tier folders of tests that mirror what they test.

A test module outside the tier folders or mirroring no source, or a shared helper
inside a tier, is a Problem naming where it belongs. A test of a shared helper
mirrors the helper inside its tier's fixtures folder, and a TypeScript test may
mirror a shell script, which it runs as a process. A tier may hold `conftest.py`,
and the smoke tests and the settings tests mirror no source.
"""

from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar

from nustack.problem import Problem


@dataclass(frozen=True)
class Suite:
    """Every file under the tests folder, each test module held to what it tests."""

    TESTS: ClassVar[PurePosixPath] = PurePosixPath("tests")
    TIERS: ClassVar[tuple[str, ...]] = ("unit", "integration", "smoke")
    SMOKE: ClassVar[PurePosixPath] = TESTS / "smoke"
    FIXTURES: ClassVar[PurePosixPath] = TESTS / "fixtures"
    CONFTEST: ClassVar[str] = "conftest.py"
    PYTHON_SOURCES: ClassVar[PurePosixPath] = PurePosixPath("src")
    # Each tests the tools' settings, so mirrors no source file.
    SETTINGS: ClassVar[frozenset[PurePosixPath]] = frozenset(
        {
            TESTS / "unit/test_settings.py",
            TESTS / "integration/test_settings.py",
            TESTS / "unit/settings.test.ts",
        }
    )
    root: Path
    sources: frozenset[PurePosixPath]
    tests: tuple[PurePosixPath, ...]

    def problems(self) -> list[Problem]:
        problems = []
        for path in self.tests:
            if not self.is_test_module(path):
                problems.extend(self.helper_problems(path))
            elif not path.is_relative_to(self.SMOKE) and path not in self.SETTINGS:
                problems.extend(self.module_problems(path))
        return problems

    def helper_problems(self, path: PurePosixPath) -> list[Problem]:
        parts = path.relative_to(self.TESTS).parts
        if parts[0] not in self.TIERS or path.name == self.CONFTEST:
            return []
        return [
            Problem(
                self.root / path,
                "is no test, yet sits in a tier folder; move it into "
                f"{self.FIXTURES}, beside the tiers, which holds what tests share",
            )
        ]

    def module_problems(self, path: PurePosixPath) -> list[Problem]:
        parts = path.relative_to(self.TESTS).parts
        if parts[0] not in self.TIERS:
            return [
                Problem(
                    self.root / path,
                    f"sits outside the tier folders {', '.join(self.TIERS)} under "
                    f"{self.TESTS}; move it into the tier of the test it holds",
                )
            ]
        sources = self.sources_of(path)
        if {*sources} & {*self.sources, *self.tests}:
            return []
        return [
            Problem(
                self.root / path,
                f"mirrors {' or '.join(map(str, sources))}, which does not exist; "
                "move it to mirror the source it tests, or remove it",
            )
        ]

    def sources_of(self, path: PurePosixPath) -> tuple[PurePosixPath, ...]:
        folders = PurePosixPath(*path.relative_to(self.TESTS).parts[1:-1])
        if folders.is_relative_to(self.FIXTURES.name):
            folders = self.TESTS / folders
        elif path.suffix == ".py":
            folders = self.PYTHON_SOURCES / folders
        if path.name.endswith(".test.ts"):
            stem = path.name.removesuffix(".test.ts")
            return (folders / f"{stem}.ts", folders / f"{stem}.sh")
        return (folders / path.name.removeprefix("test_"),)

    @staticmethod
    def is_test_module(path: PurePosixPath) -> bool:
        return (path.name.startswith("test_") and path.suffix == ".py") or (
            path.name.endswith(".test.ts")
        )
