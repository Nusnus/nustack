"""A run of mutmut tests again what the changes since its full run can reach."""

from pathlib import PurePosixPath

import pytest

from nustack.mutation.scope import Inputs
from nustack.mutation.scope import Plan
from nustack.mutation.scope import Scope


class TestInputs:
    """A run tests again only what changed files mutmut's tests read can reach.

    A change to no file the tests read runs nothing, nor does an edit to the tests'
    Python that changes only comments or docstring text, and source and test modules
    run only what they reach. Any other file the tests read runs every mutant.
    """

    INPUTS = Inputs(
        (PurePosixPath("src/pkg"),),
        (PurePosixPath("Makefile"), PurePosixPath("tests/fixtures/github")),
    )
    TESTS = frozendict(
        {
            "pkg.a.x_f": (
                "tests/test_a.py::TestA::test_f",
                "tests/test_b.py::TestB::t",
            ),
            "pkg.a.x_g": ("tests/test_b.py::TestB::t",),
            "pkg.b.x_h": ("tests/test_a.pyc::T::t", "tests/unit/test_a.py::T::t"),
        }
    )
    CONFTEST = PurePosixPath("tests/conftest.py")
    SKIP = Plan(
        Scope.SKIP,
        "no file mutmut's tests read changed since mutants/'s full run, so no mutant"
        " runs",
    )

    @staticmethod
    def edited(_path: PurePosixPath) -> tuple[bytes | None, bytes | None]:
        return b"x = 1\n", b"x = 2\n"

    @pytest.mark.parametrize(
        "changed",
        [
            (),
            (
                "README.md",
                "src/other.py",
                "docs/test_a.py",
                "srcpkg/a.py",
                "plugin/skills/nus-mode/SKILL.md",
                ".github/workflows/sync.yml",
                "tests/fixtures/smoke/bun.lock",
                "tests/fixtures/vendored.ts",
                "tests/fixtures/githubx.json",
                "test_root.txt",
                "sub/test_x.py",
            ),
        ],
    )
    def test_runs_nothing_when_no_file_the_tests_read_changed(
        self, changed: tuple[str, ...]
    ) -> None:
        plan = self.INPUTS.plan(
            (PurePosixPath(path) for path in changed), self.TESTS, self.edited
        )
        assert plan == self.SKIP

    def test_leaves_a_changed_source_module_to_mutmut(self) -> None:
        plan = self.INPUTS.plan(
            (PurePosixPath("src/pkg/a.py"),), self.TESTS, self.edited
        )
        assert plan == Plan(
            Scope.CHANGED,
            "the changed functions' mutants run, and those of the 0 functions the"
            " changed test modules cover",
        )

    @pytest.mark.parametrize(
        ("changed", "functions"),
        [
            (("tests/test_a.py",), frozenset({"pkg.a.x_f"})),
            (
                ("tests/test_b.py", "src/pkg/b.py"),
                frozenset({"pkg.a.x_f", "pkg.a.x_g"}),
            ),
            (("tests/unit/a_test.py",), frozenset()),
            (("test/test_c.py",), frozenset()),
            (("test_root.py",), frozenset()),
        ],
    )
    def test_runs_again_each_function_a_changed_test_module_covers(
        self, changed: tuple[str, ...], functions: frozenset[str]
    ) -> None:
        plan = self.INPUTS.plan(
            (PurePosixPath(path) for path in changed), self.TESTS, self.edited
        )
        assert (plan.scope, plan.functions) == (Scope.CHANGED, functions)

    @pytest.mark.parametrize(
        ("path", "reason"),
        [
            (
                "tests/conftest.py",
                (
                    "tests/conftest.py changed, which can reach any verdict, so every"
                    " mutant runs"
                ),
            ),
            (
                "tests/fixtures/github/data.json",
                (
                    "tests/fixtures/github/data.json changed, which can reach any"
                    " verdict, so every mutant runs"
                ),
            ),
            (
                "src/pkg/data.json",
                (
                    "src/pkg/data.json changed, which can reach any verdict, so every"
                    " mutant runs"
                ),
            ),
            (
                "src/pkg",
                "src/pkg changed, which can reach any verdict, so every mutant runs",
            ),
            (
                "Makefile",
                "Makefile changed, which can reach any verdict, so every mutant runs",
            ),
            (
                "pyproject.toml",
                (
                    "pyproject.toml changed, which can reach any"
                    " verdict, so every mutant runs"
                ),
            ),
            (
                "uv.lock",
                "uv.lock changed, which can reach any verdict, so every mutant runs",
            ),
            (
                "test/helper.py",
                (
                    "test/helper.py changed, which can reach any"
                    " verdict, so every mutant runs"
                ),
            ),
            (
                ".python-version",
                (
                    ".python-version changed, which can reach any verdict, so every"
                    " mutant runs"
                ),
            ),
        ],
    )
    def test_runs_every_mutant_when_another_file_the_tests_read_changed(
        self, path: str, reason: str
    ) -> None:
        plan = self.INPUTS.plan(
            (PurePosixPath("src/pkg/a.py"), PurePosixPath(path)),
            self.TESTS,
            self.edited,
        )
        assert plan == Plan(Scope.FULL, reason)

    @pytest.mark.parametrize(
        ("before", "after"),
        [
            (b"x = 1\n", b"# Why x is 1.\nx = 1  # one\n"),
            (b'"""Old."""\nx = 1\n', b'"""New, and\n\nlonger.\n"""\nx = 1\n'),
            (
                (
                    b'class A:\n    """a"""\n\n    def f(self):\n        """b"""\n'
                    b'        return 1\n\n\nasync def g():\n    """c"""\n'
                ),
                (
                    b'class A:\n    """A."""\n\n    def f(self):\n        """B."""\n'
                    b'        return 1\n\n\nasync def g():\n    """C."""\n'
                ),
            ),
            (
                b'#!/usr/bin/env python3\n"""a"""\n',
                b'#!/usr/bin/env python3\n"""b"""\n',
            ),
        ],
    )
    def test_counts_no_edit_that_changes_only_comments_or_docstring_text(
        self, before: bytes, after: bytes
    ) -> None:
        def sources(_path: PurePosixPath) -> tuple[bytes | None, bytes | None]:
            return before, after

        changed = (self.CONFTEST, PurePosixPath("tests/test_a.py"))
        assert self.INPUTS.plan(changed, self.TESTS, sources) == self.SKIP

    @pytest.mark.parametrize(
        ("before", "after"),
        [
            (b"x = 1\n", b'"""a"""\nx = 1\n'),
            (b'def f():\n    """a"""\n    return 1\n', b"def f():\n    return 1\n"),
            (b'"""a"""\n', b"None\n"),
            (b'x = 1\n"a"\n', b'x = 1\n"b"\n'),
            (b'if x:\n    "a"\n', b'if x:\n    "b"\n'),
            (b'b"a"\n', b'b"b"\n'),
            (b"x = 1\n", b"x = 2\n"),
            (b"x = (\n", b"x = (\n"),
            (b"x = 1\n", b"x = (\n"),
            (None, b"x = 1\n"),
            (b"x = 1\n", None),
            (b"#!/usr/bin/python3.14\nx = 1\n", b"#!/usr/bin/python3.15\nx = 1\n"),
            (b"x = 1\n", b"#!/usr/bin/python3\nx = 1\n"),
        ],
    )
    def test_counts_each_other_edit_to_the_tests_python(
        self, before: bytes | None, after: bytes | None
    ) -> None:
        def sources(_path: PurePosixPath) -> tuple[bytes | None, bytes | None]:
            return before, after

        changed = (PurePosixPath("tests/test_a.py"), self.CONFTEST)
        assert self.INPUTS.plan(changed, self.TESTS, sources) == Plan(
            Scope.FULL,
            "tests/conftest.py changed, which can reach any verdict, so every mutant"
            " runs",
        )

    @pytest.mark.parametrize(
        ("path", "scope"),
        [("Makefile", Scope.FULL), ("src/pkg/a.py", Scope.CHANGED)],
    )
    def test_counts_a_comment_only_edit_outside_the_tests_python(
        self, path: str, scope: Scope
    ) -> None:
        changed = PurePosixPath(path)
        sources = {changed: (b"x = 1\n", b"x = 1  # one\n")}
        plan = self.INPUTS.plan((changed,), self.TESTS, sources.__getitem__)
        assert plan.scope == scope
