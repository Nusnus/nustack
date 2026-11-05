"""What a run of mutmut must test again, from the files changed since its full run.

mutmut keeps each mutant's verdict in its `mutants/` folder and tests again only the
mutants of a function whose source changed. A file its tests never read reaches no
verdict, so a change to it runs nothing, and neither does an edit to the tests' Python
that changes only its comments or the text of its docstrings, which no test reads. A
changed test module can let a mutant its tests killed live, which mutmut misses, so the
mutants of each function its tests cover run again. Any other change to what the tests
read, such as a test helper, a fixture, the settings or the lockfile, can reach any
verdict, so every mutant runs from an empty folder. A change to a function's callers or
callees, or to a source file outside its functions, reaches verdicts mutmut keeps, so
only a full run catches what it does to them.
"""

import ast
from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import ClassVar
lazy from collections.abc import Callable
lazy from collections.abc import Iterable
lazy from collections.abc import Mapping


class Scope(StrEnum):
    """Which mutants a run of mutmut tests."""

    SKIP = "skip"
    CHANGED = "changed"
    FULL = "full"


@dataclass(frozen=True)
class Plan:
    """A scope, the functions whose mutants run again beyond mutmut's own, and why."""

    scope: Scope
    reason: str
    functions: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Inputs:
    """What mutmut's tests read: the sources, the tests' Python and the settings.

    `reads` lists each other file or folder they read, such as a fixture.
    """

    # mutmut copies these folders whole beside the sources, and runs its tests there:
    # https://github.com/boxed/mutmut/blob/3.8.1/src/mutmut/configuration.py#L184-L195
    TEST_FOLDERS: ClassVar[tuple[PurePosixPath, ...]] = (
        PurePosixPath("tests"),
        PurePosixPath("test"),
    )
    ROOT_TESTS: ClassVar[str] = "test*.py"
    # The settings and lockfiles mutmut copies, and the Python version uv runs it on.
    SETTINGS: ClassVar[tuple[PurePosixPath, ...]] = tuple(
        PurePosixPath(path)
        for path in (
            "setup.cfg",
            "pyproject.toml",
            "uv.lock",
            "poetry.lock",
            "Pipfile.lock",
            "pdm.lock",
            ".python-version",
        )
    )
    # pytest's default python_files, which pyproject.toml keeps:
    # https://docs.pytest.org/en/stable/reference/reference.html#confval-python_files
    TEST_MODULES: ClassVar[tuple[str, ...]] = ("test_*.py", "*_test.py")
    sources: tuple[PurePosixPath, ...]
    reads: tuple[PurePosixPath, ...]

    def plan(
        self,
        changed: Iterable[PurePosixPath],
        tests_by_function: Mapping[str, Iterable[str]],
        sources: Callable[[PurePosixPath], tuple[bytes | None, bytes | None]],
    ) -> Plan:
        read = [
            path
            for path in changed
            if self.read(path)
            and not (self.test_code(path) and self.same(*sources(path)))
        ]
        if not read:
            return Plan(
                Scope.SKIP,
                "no file mutmut's tests read changed since mutants/'s full run, so no"
                " mutant runs",
            )
        modules: set[PurePosixPath] = set()
        for path in read:
            if self.inside(path, self.sources) and path.suffix == ".py":
                continue
            if self.test_code(path) and any(
                fnmatch(path.name, module) for module in self.TEST_MODULES
            ):
                modules.add(path)
            else:
                return Plan(
                    Scope.FULL,
                    f"{path} changed, which can reach any verdict, so every mutant"
                    " runs",
                )
        prefixes = tuple(f"{module}::" for module in modules)
        functions = frozenset(
            function
            for function, tests in tests_by_function.items()
            if any(test.startswith(prefixes) for test in tests)
        )
        return Plan(
            Scope.CHANGED,
            f"the changed functions' mutants run, and those of the {len(functions)}"
            " functions the changed test modules cover",
            functions,
        )

    def read(self, path: PurePosixPath) -> bool:
        return self.test_code(path) or self.inside(
            path, (*self.sources, *self.SETTINGS, *self.reads)
        )

    def test_code(self, path: PurePosixPath) -> bool:
        return path.suffix == ".py" and (
            self.inside(path, self.TEST_FOLDERS)
            or (len(path.parts) == 1 and fnmatch(path.name, self.ROOT_TESTS))
        )

    # Each source is a file's bytes, or None where it is missing or unreadable.
    @classmethod
    def same(cls, before: bytes | None, after: bytes | None) -> bool:
        code = cls.code(before)
        return code is not None and code == cls.code(after)

    # ast.parse drops comments, and ast.dump the place of each node, so a test that
    # needs a node's line, such as tests/fixtures/reader_caller.py's, finds it in the
    # code Python compiled. A docstring's text goes too, but not whether there is one,
    # which a test can check. A #! line is a comment that runs the file.
    @classmethod
    def code(cls, source: bytes | None) -> str | None:
        if source is None:
            return None
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        # The nodes whose first statement, a string, is their docstring:
        # https://docs.python.org/3/library/ast.html#ast.get_docstring
        documented = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        for node in ast.walk(tree):
            if isinstance(node, documented):
                match node.body:
                    case [
                        ast.Expr(value=ast.Constant(value=str(text)) as docstring),
                        *_,
                    ]:
                        docstring.value = text[:0]
        start = source.startswith(b"#!") and source.partition(b"\n")[0]
        return f"{start!r} {ast.dump(tree)}"

    @staticmethod
    def inside(path: PurePosixPath, places: tuple[PurePosixPath, ...]) -> bool:
        return any(path == place or place in path.parents for place in places)
