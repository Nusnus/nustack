"""The suite's settings enforce how Python's tests run, measure coverage and lint.

No test relies on order, an ignored warning or a stale xfail, no pragma hides
code from coverage, data of unknown type is narrowed, and pure modules import no I/O.
"""

import json
import subprocess
import sys
import tomllib
lazy from pathlib import Path

import pytest


class TestPytest:
    """A passing suite relies on no test order, ignored warning or stale xfail."""

    @pytest.fixture
    def suite(self, pytester: pytest.Pytester, pyproject: Path) -> pytest.Pytester:
        settings = tomllib.loads(pyproject.read_text())["tool"]["pytest"]
        options = {key: value for key, value in settings.items() if key != "testpaths"}
        lines = "\n".join(
            f"{key} = {json.dumps(value)}" for key, value in options.items()
        )
        pytester.makefile(".toml", pyproject=f"[tool.pytest]\n{lines}\n")
        return pytester

    def test_runs_in_random_order_under_a_printed_seed(
        self, suite: pytest.Pytester
    ) -> None:
        suite.makepyfile(test_a="def test_a():\n    pass\n")
        result = suite.runpytest_subprocess()
        result.stdout.fnmatch_lines(["Using --randomly-seed=*"])

    def test_fails_a_test_that_warns(self, suite: pytest.Pytester) -> None:
        suite.makepyfile(
            test_a="import warnings\n\n\ndef test_a():\n    warnings.warn('canary')\n"
        )
        result = suite.runpytest_subprocess()
        assert result.parseoutcomes() == {"failed": 1}

    def test_fails_an_expected_failure_that_passes(
        self, suite: pytest.Pytester
    ) -> None:
        suite.makepyfile(
            test_a="import pytest\n\n\n@pytest.mark.xfail\ndef test_a():\n    pass\n"
        )
        result = suite.runpytest_subprocess()
        assert result.parseoutcomes() == {"failed": 1}


class TestCoverage:
    """No pragma can hide code from coverage."""

    MODULE = (
        "import typing\n"
        "from textwrap import dedent\n"
        "from typing import TYPE_CHECKING, Annotated, Literal, assert_never, overload\n"
        "if TYPE_CHECKING:\n"
        "    import os\n"
        "if typing.TYPE_CHECKING:\n"
        "    import sys\n"
        "def stub() -> None: ...\n"
        "class Sender:\n"
        "    def send(self) -> None: ...  # comment\n"
        "@overload\n"
        "def one(x: int) -> int: ...\n"
        "@overload\n"
        "def one(x: str) -> str: ...\n"
        "def one(x: int | str) -> int | str:\n"
        "    return x\n"
        "def many(\n"
        "    x: int,\n"
        ") -> int: ...\n"
        "class Sink(typing.Protocol):\n"
        "    def send(self) -> None:\n"
        '        """Send."""\n'
        "        ...\n"
        "@overload\n"
        'def split(text: str, sep: str = "#") -> list[str]: ...\n'
        "@overload\n"
        'def split(text: bytes, sep: bytes = b"#") -> list[bytes]: ...\n'
        'def split(text, sep="#"):\n'
        "    return text.split(sep)\n"
        "class Marker(typing.Protocol):\n"
        "    def size(self) -> int: ...\n"
        '    def send(self, mark: str = "#") -> None: ...\n'
        "def tag(\n"
        "    x: int,\n"
        ") -> \"Literal['#']\": ...\n"
        "class Matcher(typing.Protocol):\n"
        "    def match(self) -> None:\n"
        '        r"""Match \\d."""\n'
        "        ...\n"
        "class Reader(typing.Protocol):\n"
        "    def read(self) -> None:\n"
        '        """Read.\n'
        "\n"
        "        More.\n"
        '        """\n'
        "        ...\n"
        "    def peek(self) -> None:\n"
        '        """Peek.\n'
        "\n"
        "        More.\n"
        '        """\n'
        "def source() -> str:\n"
        '    return dedent("""\n'
        "        def f() -> None: ...\n"
        '    """)\n'
        'def a(x="a", y="b"):  # Note: "c f(z): ...\n'
        "    return x\n"
        'def q1(x="\'\\""):  # see "a: ...\n'
        "    return 1\n"
        'def q2(x="""a"b"""):  # see "a: ...\n'
        "    return 1\n"
        "def q3(\n"
        "    x: int,\n"
        ') -> """a"b""":  # see a"b: ...\n'
        "    return 1\n"
        'def q4(x: str = "\'\\"#") -> None: ...\n'
        "class Mark(typing.Protocol):\n"
        '    def send(self, mark: str = "\'\\"#") -> None: ...\n'
        "    def wait(self) -> None:\n"
        '        R"""Doc."""\n'
        "        ...\n"
        'def q5(sep: str = "\\n") -> None: ...\n'
        'def q7(x="""#""") -> None: ...\n'
        "def r1(x='''it's \"q\"'''):  # see 'c: ...\n"
        "    return 1\n"
        "def r2(x=f\"{'\"'}\"):  # see 'c: ...\n"
        "    return 1\n"
        "def r3(\n"
        "    x: int,\n"
        ") -> '''it's \"q\"''':  # see 'c: ...\n"
        "    return 1\n"
        'def r4(t: str = "{}") -> None: ...\n'
        "R4 = 1\n"
        "def g(flag):\n"
        "    if flag:\n"
        '        return "\\\n'
        'def "  # "c: ...\n'
        "    return 2\n"
        "X = g(False)\n"
        "QUOTES = {'\"': '\"'}\n"
        "def s1(x=rf\"\\{QUOTES['\"']}\"):  # Don't trim: ...\n"
        "    return 1\n"
        "def s2(x=rt\"\\{QUOTES['\"']}\"):  # Don't trim: ...\n"
        "    return 1\n"
        "def s3(\n"
        "    x: int,\n"
        ") -> Annotated[str, rf\"\\{QUOTES['\"']}\"]:  # Don't trim: ...\n"
        "    return 1\n"
        "class Docs(typing.Protocol):\n"
        "    def d1(self) -> None:\n"
        "        '''Doc.'''\n"
        "        ...\n"
        "    def d2(self) -> None:\n"
        "        r'''Doc.'''\n"
        "        ...\n"
        "    def d3(self) -> None:\n"
        "        R'''Doc.'''\n"
        "        ...\n"
        "def table() -> dict[int, object]:\n"
        "    return {\n"
        "        len(\n"
        "            'a'\n"
        "        ): ...\n"
        "    }\n"
        "def lookup() -> dict[str, object]:\n"
        "    return {\n"
        "        'ab'[\n"
        "            0\n"
        "        ]: ...\n"
        "    }\n"
        "class Noqa(typing.Protocol):\n"
        "    def n(self) -> None:\n"
        '        """Doc."""  # noqa: D401\n'
        "        ...\n"
        "def body() -> None:\n"
        "    ...\n"
        "def usage() -> str:\n"
        '    return """Usage:\n'
        "    ...\n"
        '    """\n'
        "def note() -> int:  # Note: ...\n"
        "    return 1\n"
        "async def ex() -> None:  # Example: ...\n"
        "    return None\n"
        "def todo():  # TODO(me): ...\n"
        "    return None\n"
        "def work() -> int:\n"
        "    ...\n"
        "    return 1\n"
        "def pick(kind: Literal['a']) -> int:\n"
        "    match kind:\n"
        "        case 'a':\n"
        "            return 1\n"
        "        case unexpected:\n"
        "            assert_never(unexpected)\n"
        "def skipped() -> int:  # pragma: no cover\n"
        "    return 2\n"
        "def branch(flag: bool) -> int:\n"
        "    if flag:  # pragma: no branch\n"
        "        return 3\n"
        "    return 4\n"
        "one(1)\n"
        "split('a#b')\n"
        "pick('a')\n"
        "branch(True)\n"
    )

    @pytest.fixture
    def report(self, tmp_path: Path, pyproject: Path) -> str:
        (tmp_path / "mod.py").write_text(self.MODULE)
        for command in (
            ["run", f"--rcfile={pyproject}", "--source=.", "mod.py"],
            ["report", f"--rcfile={pyproject}", "--fail-under=0"],
        ):
            run = subprocess.run(  # noqa: S603 -- the test's own interpreter, with fixed arguments
                [sys.executable, "-m", "coverage", *command],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                check=True,
            )
        return run.stdout

    def test_excludes_only_stubs_type_checking_and_assert_never_arms_without_pragmas(
        self, report: str
    ) -> None:
        line = report.splitlines()[2]
        assert line.split() == [
            "mod.py",
            "85",
            "22",
            "6",
            "5",
            "70%",
            "46,",
            "57,",
            "59,",
            "61,",
            "65,",
            "73->74,",
            "73->exit,",
            "75,",
            "77,",
            "81,",
            "82->83,",
            "82->exit,",
            "92,",
            "94,",
            "98,",
            "110,",
            "116,",
            "126,",
            "128,",
            "132,",
            "134,",
            "136,",
            "138-139,",
            "147,",
            "151",
        ]


class TestRuff:
    """Data of unknown type is narrowed, and pure modules import no I/O subpackage."""

    @pytest.mark.parametrize(
        ("source", "line"),
        [
            (
                "from typing import cast\n",
                (
                    "src/nustack/a.py:1:20: TID251 `typing.cast` is banned: Narrow the"
                    " value with isinstance, match or a TypeIs function instead."
                ),
            ),
            (
                "from typing_extensions import cast\n",
                (
                    "src/nustack/a.py:1:31: TID251 `typing_extensions.cast` is banned:"
                    " Narrow the value with isinstance, match or a TypeIs function"
                    " instead."
                ),
            ),
            (
                "import urllib.request\n",
                (
                    "src/nustack/a.py:1:8: TID251 `urllib.request` is banned: Do I/O in"
                    " the modules import-linter allows it in."
                ),
            ),
            ("import urllib.parse\n", "All checks passed!"),
            (
                "from http import client\n",
                (
                    "src/nustack/a.py:1:18: TID251 `http.client` is banned: Do I/O in"
                    " the modules import-linter allows it in."
                ),
            ),
        ],
    )
    def test_bans_cast_and_each_io_subpackage_alone(
        self, pyproject: Path, source: str, line: str
    ) -> None:
        run = subprocess.run(  # noqa: S603 -- the test's own interpreter, with fixed arguments
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                f"--config={pyproject}",
                "--select=TID251",
                "--output-format=concise",
                "--stdin-filename=src/nustack/a.py",
                "-",
            ],
            input=source,
            capture_output=True,
            text=True,
            # Ruff asks for check; the test reads the exit status itself:
            # https://docs.astral.sh/ruff/rules/subprocess-run-without-check/
            check=False,
        )
        assert run.stdout.splitlines()[0] == line
