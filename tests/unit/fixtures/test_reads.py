"""A run fails when a test reads a repository file nustack mutants does not count."""

import ast
import os
import sys
import types
from pathlib import PurePosixPath
from typing import ClassVar
lazy from pathlib import Path

import pytest

from tests.fixtures import reads
from tests.fixtures.reads import Reads


class TestReads:
    """A run naming where each uncounted read happened fails.

    The place is the test that read the file, the module whose import did, or pytest's
    startup for a conftest's or its plugin's import. A run reading only counted files
    passes, and tests/conftest.py loads this plugin before any code of its own runs.
    """

    UNCOUNTED: ClassVar[str] = (
        " reads plugin/skills/nus-mode/SKILL.md, which nustack mutants does not"
        " count; add it to [tool.nustack] mutation.reads in pyproject.toml"
    )

    READ: ClassVar[str] = (
        "from pathlib import Path\n\n"
        "DATA = Path({root!r}, 'plugin/skills/nus-mode/SKILL.md').read_bytes()\n"
    )

    @pytest.mark.parametrize(
        ("files", "line"),
        [
            (
                {
                    "test_x.py": (
                        "from pathlib import Path\n\n\ndef test_reads():\n"
                        "    Path({root!r}, 'plugin/skills/nus-mode/SKILL.md')"
                        ".read_bytes()\n"
                    )
                },
                "test_x.py::test_reads" + UNCOUNTED,
            ),
            ({"test_x.py": READ}, "test_x.py" + UNCOUNTED),
            ({"helper.py": READ}, Reads.STARTUP + UNCOUNTED),
            ({"tests/conftest.py": READ}, Reads.STARTUP + UNCOUNTED),
            (
                {
                    "test_x.py": (
                        "from pathlib import Path\n\n\ndef test_reads():\n"
                        "    Path({root!r}, 'Makefile').read_bytes()\n"
                    )
                },
                None,
            ),
        ],
    )
    def test_fails_a_run_that_reads_an_uncounted_file(
        self,
        pytester: pytest.Pytester,
        repository_root: Path,
        files: dict[str, str],
        line: str | None,
    ) -> None:
        pytester.makeconftest('pytest_plugins = ("tests.fixtures.reads", "helper")\n')
        _ = pytester.makepyfile(helper="", test_y="def test_passes():\n    pass\n")
        for name, source in files.items():
            path = pytester.path / name
            path.parent.mkdir(exist_ok=True)
            _ = path.write_text(source.format(root=str(repository_root)))
        pytester.syspathinsert()
        result = pytester.runpytest_inprocess("-p", "no:randomly", "-p", "no:cov")
        expected = pytest.ExitCode.TESTS_FAILED if line else pytest.ExitCode.OK
        assert (result.ret, line in result.outlines if line else True) == (
            expected,
            True,
        )

    def test_root_conftest_loads_this_plugin_first_and_reads_nothing_before(
        self, repository_root: Path
    ) -> None:
        module = ast.parse((repository_root / "tests" / "conftest.py").read_text())
        statements = [ast.unparse(node).partition(" = ") for node in module.body[1:]]
        assert (
            ast.get_docstring(module) is not None,
            [name for name, _, _ in statements],
            ast.literal_eval(statements[0][2])[0],
        ) == (True, ["pytest_plugins"], "tests.fixtures.reads")


class TestReadPath:
    """Each audit event that reads a file or lists a folder names it; others none."""

    @pytest.mark.parametrize(
        ("event", "args", "read"),
        [
            ("open", ("/a/b", "r", 0), "/a/b"),
            ("open", (b"/a/b", "rb", 0), "/a/b"),
            ("open", ("/a/b", "w", 0), None),
            ("open", ("/a/b", "a", 0), None),
            ("open", ("/a/b", "x", 0), None),
            ("open", ("/a/b", "r+", 0), None),
            ("open", ("/a/b", None, os.O_RDONLY), "/a/b"),
            ("open", ("b", None, os.O_RDONLY), None),
            ("open", ("/a/b", None, os.O_WRONLY), None),
            ("open", ("/a/b", None, os.O_RDWR), None),
            ("open", (3, "r", 0), None),
            ("open", ("<unknown>", "rb", 0), None),
            ("open", ("/a/<b>", "rb", 0), "/a/<b>"),
            ("os.scandir", ("/a",), "/a"),
            ("os.listdir", ("/a",), "/a"),
            ("os.scandir", (3,), None),
            ("os.remove", ("/a/b", -1), None),
        ],
    )
    def test_names_the_path_each_read_takes(
        self, event: str, args: tuple[object, ...], read: str | None
    ) -> None:
        assert Reads.read_path(event, args) == (read and Path(os.path.realpath(read)))


class TestAudit:
    """A repository read during a test is kept under the first test to make it.

    A read of Python's own files or of bytecode is not, and a read outside a
    session goes unkept.
    """

    def test_keeps_each_repository_read_under_its_first_place(
        self, monkeypatch: pytest.MonkeyPatch, repository_root: Path
    ) -> None:
        reads = Reads()
        monkeypatch.setattr(Reads, "sessions", [reads])
        Reads.audit("open", (str(repository_root / "Makefile"), "r", 0))
        with Reads.at("first"):
            Reads.audit("open", (str(repository_root / "Makefile"), "r", 0))
            Reads.audit("open", (str(repository_root / "uv.lock"), "r", 0))
            with Reads.at(""):
                Reads.audit("os.listdir", (str(repository_root / "src"),))
            Reads.audit("os.listdir", (str(repository_root / "plugin"),))
            bytecode = repository_root / "src" / "__pycache__" / "x"
            Reads.audit("open", (str(bytecode), "r", 0))
            Reads.audit("open", (str(Path(sys.prefix) / "x"), "r", 0))
            Reads.audit("open", ("/", "r", 0))
            Reads.audit("os.remove", ("/", -1))
        assert (reads.first, reads.listed, reads.places) == (
            {
                PurePosixPath("Makefile"): "the session",
                PurePosixPath("uv.lock"): "first",
            },
            {PurePosixPath("src"): "the session", PurePosixPath("plugin"): "first"},
            [],
        )

    @pytest.mark.parametrize(
        ("module", "kept"),
        [
            ("_pytest.main", ()),
            ("coverage.config", ()),
            ("pytest_cov.plugin", ()),
            ("importlib._bootstrap_external", ("open",)),
            ("_frozen_importlib_external", ("open",)),
            ("tests.unit.lister", ("open", "os.listdir")),
            ("os", ("open", "os.listdir")),
        ],
    )
    def test_keeps_no_read_by_pytest_or_coverage_nor_import_system_listing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        repository_root: Path,
        module: str,
        kept: tuple[str, ...],
    ) -> None:
        reads = Reads()
        monkeypatch.setattr(Reads, "sessions", [reads])

        def reader(path: str) -> None:
            Reads.audit("open", (path, "r", 0))
            Reads.audit("os.listdir", (path,))

        types.FunctionType(reader.__code__, {"__name__": module, "Reads": Reads})(
            str(repository_root / "plugin")
        )
        plugin = {PurePosixPath("plugin"): "the session"}
        assert (reads.first, reads.listed) == (
            plugin if "open" in kept else {},
            plugin if "os.listdir" in kept else {},
        )

    def test_keeps_nothing_outside_a_session(
        self, monkeypatch: pytest.MonkeyPatch, repository_root: Path
    ) -> None:
        sessions: list[Reads] = []
        monkeypatch.setattr(Reads, "sessions", sessions)
        Reads.audit("open", (str(repository_root / "Makefile"), "r", 0))
        assert sessions == []


class TestPluginRegistered:
    """Registering this plugin starts a run's record; registering another, none."""

    def test_starts_a_record_for_this_plugin_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sessions: list[Reads] = []
        monkeypatch.setattr(Reads, "sessions", sessions)
        reads.pytest_plugin_registered(types.ModuleType("other"))
        reads.pytest_plugin_registered(reads)
        assert sessions == [Reads(places=[Reads.STARTUP])]
