"""Fails the run when the tests read a repository file nustack mutants does not count.

nustack mutants skips a change to a file mutmut's tests never read, as `Inputs.read`
judges it, so a test that reads another repository file would let a pull request keep
a verdict that file's change flips. Python's audit hooks report each file this process
opens to read and each folder it lists. tests/conftest.py loads this plugin ahead of
every other, and it collects the reads from then until the session ends, apart from
pytest's and coverage's own reads and the import system's listings, then holds them to
`Inputs.read`. It misses four kinds of read: one through another process, such as the
fake gh's or `git rev-parse --local-env-vars`; one before tests/conftest.py loads it,
which is pytest's of its settings, an installed plugin's, or the conftest's own module
body, which a test holds to its docstring and plugin list; an `os.open` of a path
relative to a folder's descriptor; and a check of a path's existence or metadata, such
as `Path.exists()`, `is_file()` or `stat()`, which raises no audit event, so a `skipif`
on a file's existence goes unseen.
"""

import os
import sys
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar
lazy from collections.abc import Generator
lazy from collections.abc import Iterator

import pytest

from nustack.cli.command import mutation_inputs


@dataclass
class Reads:
    """The repository paths one session read, each by the first place to read it.

    A place is the test running, else the collector collecting, such as the module
    whose import reads a file, else pytest's startup until the session starts, else the
    session.
    """

    ROOT: ClassVar[Path] = Path(__file__).resolve().parents[2]
    SKIPPED: ClassVar[tuple[Path, ...]] = (Path(sys.prefix).resolve(),)
    SESSION: ClassVar[str] = "the session"
    STARTUP: ClassVar[str] = "startup, which imports the conftests and their plugins,"
    PASSTHROUGH: ClassVar[frozenset[str]] = frozenset(
        {
            "configparser",
            "fnmatch",
            "genericpath",
            "glob",
            "os",
            "pathlib",
            "posixpath",
            "shutil",
        }
    )
    TOOLS: ClassVar[frozenset[str]] = frozenset({"_pytest", "coverage", "pytest_cov"})
    IMPORTERS: ClassVar[frozenset[str]] = frozenset(
        {"_frozen_importlib", "_frozen_importlib_external", "importlib"}
    )
    sessions: ClassVar[list[Reads]] = []
    first: dict[PurePosixPath, str] = field(default_factory=dict)
    listed: dict[PurePosixPath, str] = field(default_factory=dict)
    places: list[str] = field(default_factory=list)

    @classmethod
    def audit(cls, event: str, args: tuple[object, ...]) -> None:
        if not cls.sessions:
            return
        reads = cls.sessions[-1]
        path = cls.read_path(event, args)
        listing = event != "open"
        if (
            path is None
            or not path.is_relative_to(cls.ROOT)
            or any(path.is_relative_to(skipped) for skipped in cls.SKIPPED)
            or "__pycache__" in path.parts
            or cls.caller() in (cls.TOOLS | cls.IMPORTERS if listing else cls.TOOLS)
        ):
            return
        seen = reads.listed if listing else reads.first
        place = reads.places[-1] if reads.places else cls.SESSION
        seen.setdefault(PurePosixPath(path.relative_to(cls.ROOT)), place)

    # pytest reads its cache and lists each folder it collects, coverage probes for its
    # settings and lists each folder it reports on, and the import system lists each
    # folder it searches; none of it is a test reading the repository. The import
    # system's reads stay kept, since what a test imports is what it reads.
    @classmethod
    def caller(cls) -> str:
        names = (
            frame.f_globals.get("__name__", "")
            for frame, _ in traceback.walk_stack(None)
        )
        caller = next(
            name
            for name in names
            if name != __name__ and name.partition(".")[0] not in cls.PASSTHROUGH
        )
        return caller.partition(".")[0]

    @classmethod
    @contextmanager
    def at(cls, place: str) -> Generator[None]:
        places = cls.sessions[-1].places
        places.append(place or cls.SESSION)
        try:
            yield
        finally:
            _ = places.pop()

    # An os.open with a relative path may resolve against a folder's descriptor, as
    # shutil.rmtree's do, so only an absolute one names its file. A name in angle
    # brackets is Python's for code from no file, such as the <unknown> that a
    # SyntaxError from ast.parse tries to open for its line.
    @staticmethod
    def read_path(event: str, args: tuple[object, ...]) -> Path | None:
        match event, args:
            case "open", (str(name), *_) if name.startswith("<") and name.endswith(">"):
                return None
            case "open", (str() | bytes() | os.PathLike() as path, None, int(flags)):
                relative = not Path(os.fsdecode(path)).is_absolute()
                if (flags & os.O_ACCMODE) != os.O_RDONLY or relative:
                    return None
            case "open", (str() | bytes() | os.PathLike() as path, str(mode), _):
                if any(letter in mode for letter in "wax+"):
                    return None
            case "os.scandir" | "os.listdir", (
                str() | bytes() | os.PathLike() as path,
            ):
                pass
            case _:
                return None
        return Path(os.path.realpath(os.fsdecode(path)))


sys.addaudithook(Reads.audit)


# pytest registers this module before it imports the next plugin or conftest, so each
# run, pytester's in-process ones included, starts its own record here.
def pytest_plugin_registered(plugin: object) -> None:
    if plugin is sys.modules[__name__]:
        Reads.sessions.append(Reads(places=[Reads.STARTUP]))


def pytest_sessionstart() -> None:
    Reads.sessions[-1].places.clear()


@pytest.hookimpl(wrapper=True)
def pytest_make_collect_report(collector: pytest.Collector) -> Iterator[None]:
    with Reads.at(collector.nodeid):
        return (yield)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item) -> Iterator[None]:
    with Reads.at(item.nodeid):
        return (yield)


@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session: pytest.Session) -> None:
    reads = Reads.sessions.pop()
    inputs = mutation_inputs(Reads.ROOT)
    uncounted = sorted(
        [(where, path) for path, where in reads.first.items() if not inputs.read(path)]
        + [
            (where, path)
            for path, where in reads.listed.items()
            if not inputs.read(path)
        ]
    )
    if not uncounted:
        return
    writer = session.config.get_terminal_writer()
    writer.line()
    for where, path in uncounted:
        writer.line(
            f"{where} reads {path}, which nustack mutants does not count; add it to"
            " [tool.nustack] mutation.reads in pyproject.toml"
        )
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
