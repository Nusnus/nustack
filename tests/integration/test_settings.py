"""The suite's settings set how Python's code lints, its tests run and coverage counts.

Data of unknown type is narrowed, imports are absolute and the standard library's HTTP
clients are banned, since nustack reaches the network only by running Git or gh. No
test relies on order, an ignored warning, a stale xfail, an unknown setting, marker or
repeated parametrization id; a test or fixture that hangs fails at its time limit, and
no pragma or unimported module hides code from coverage.
"""

import json
import tomllib
lazy from pathlib import Path

import pytest

from tests.fixtures.processes import run_module


class TestRuff:
    """Unknown data is narrowed, imports are absolute, and HTTP clients are banned."""

    @pytest.mark.parametrize(
        ("rule", "source", "line"),
        [
            (
                "TID252",
                "from . import b\n",
                (
                    "src/nustack/a.py:1:1: TID252 Prefer absolute imports over"
                    " relative imports"
                ),
            ),
            ("TID252", "from nustack import b\n", "All checks passed!"),
            (
                "TID251",
                "from http import client\n",
                (
                    "src/nustack/a.py:1:18: TID251 `http.client` is banned: nustack"
                    " reaches the network only by running Git or gh, through"
                    " nustack.git or nustack.github."
                ),
            ),
            ("TID251", "from http import HTTPStatus\n", "All checks passed!"),
            (
                "TID251",
                "from typing import cast\n",
                (
                    "src/nustack/a.py:1:20: TID251 `typing.cast` is banned: Narrow the"
                    " value with isinstance, match or a TypeIs function instead."
                ),
            ),
            ("TID251", "from typing import TypeIs\n", "All checks passed!"),
            (
                "TID251",
                "from typing_extensions import cast\n",
                (
                    "src/nustack/a.py:1:31: TID251 `typing_extensions.cast` is banned:"
                    " Narrow the value with isinstance, match or a TypeIs function"
                    " instead."
                ),
            ),
            ("TID251", "from typing_extensions import TypeIs\n", "All checks passed!"),
            (
                "TID251",
                "import urllib.request\n",
                (
                    "src/nustack/a.py:1:8: TID251 `urllib.request` is banned: nustack"
                    " reaches the network only by running Git or gh, through"
                    " nustack.git or nustack.github."
                ),
            ),
            ("TID251", "import urllib.parse\n", "All checks passed!"),
        ],
    )
    def test_bans_relative_imports_cast_and_each_io_subpackage_alone(
        self, pyproject: Path, rule: str, source: str, line: str
    ) -> None:
        output = run_module(
            "ruff",
            "check",
            f"--config={pyproject}",
            f"--select={rule}",
            "--output-format=concise",
            "--stdin-filename=src/nustack/a.py",
            "-",
            source=source,
        )
        assert output.splitlines()[0] == line


class TestPytest:
    """A passing suite relies on no test order, ignored warning or stale xfail.

    An unknown setting, marker or repeated parametrization id stops the suite, and a
    hung test or fixture fails under a time limit instead of stalling the suite.
    """

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

    def test_passes_a_test_that_warns_nothing(self, suite: pytest.Pytester) -> None:
        suite.makepyfile(test_a="def test_a():\n    assert True\n")
        result = suite.runpytest_subprocess()
        assert result.parseoutcomes() == {"passed": 1}

    def test_refuses_an_unknown_setting(self, suite: pytest.Pytester) -> None:
        suite.makepyfile(test_a="def test_a():\n    pass\n")
        result = suite.runpytest_subprocess("-o", "no_such_setting=1")
        result.stderr.fnmatch_lines(["*Unknown config option: no_such_setting*"])
        assert result.ret == pytest.ExitCode.USAGE_ERROR

    def test_refuses_an_unregistered_marker(self, suite: pytest.Pytester) -> None:
        suite.makepyfile(
            test_a=(
                "import pytest\n\n\n@pytest.mark.no_such_mark\n"
                "def test_a():\n    pass\n"
            )
        )
        result = suite.runpytest_subprocess()
        result.stdout.fnmatch_lines(["*'no_such_mark' not found in `markers`*"])
        assert result.parseoutcomes() == {"errors": 1}

    def test_accepts_a_registered_marker(self, suite: pytest.Pytester) -> None:
        suite.makepyfile(
            test_a=(
                "import pytest\n\n\n@pytest.mark.timeout(5)\ndef test_a():\n    pass\n"
            )
        )
        result = suite.runpytest_subprocess()
        assert result.parseoutcomes() == {"passed": 1}

    def test_refuses_parametrization_ids_that_repeat(
        self, suite: pytest.Pytester
    ) -> None:
        suite.makepyfile(
            test_a=(
                "import pytest\n\n\n"
                "@pytest.mark.parametrize('x', [1, 2], ids=['a', 'a'])\n"
                "def test_a(x):\n    pass\n"
            )
        )
        result = suite.runpytest_subprocess()
        assert result.parseoutcomes() == {"errors": 1}

    def test_accepts_parametrization_ids_that_differ(
        self, suite: pytest.Pytester
    ) -> None:
        suite.makepyfile(
            test_a=(
                "import pytest\n\n\n"
                "@pytest.mark.parametrize('x', [1, 2], ids=['a', 'b'])\n"
                "def test_a(x):\n    pass\n"
            )
        )
        result = suite.runpytest_subprocess()
        assert result.parseoutcomes() == {"passed": 2}

    def test_fails_an_expected_failure_that_passes(
        self, suite: pytest.Pytester
    ) -> None:
        suite.makepyfile(
            test_a="import pytest\n\n\n@pytest.mark.xfail\ndef test_a():\n    pass\n"
        )
        result = suite.runpytest_subprocess()
        assert result.parseoutcomes() == {"failed": 1}

    def test_counts_an_expected_failure_that_fails(
        self, suite: pytest.Pytester
    ) -> None:
        suite.makepyfile(
            test_a=(
                "import pytest\n\n\n@pytest.mark.xfail\n"
                "def test_a():\n    assert False\n"
            )
        )
        result = suite.runpytest_subprocess()
        assert result.parseoutcomes() == {"xfailed": 1}

    def test_bounds_each_test_with_a_time_limit(self, suite: pytest.Pytester) -> None:
        suite.makepyfile(test_a="def test_a():\n    pass\n")
        result = suite.runpytest_subprocess()
        result.stdout.fnmatch_lines(["timeout: 60.0s"])

    def test_fails_a_test_or_fixture_that_outlasts_the_time_limit(
        self, suite: pytest.Pytester
    ) -> None:
        suite.makepyfile(
            test_a="import time\n\nimport pytest\n\n\n@pytest.fixture\n"
            "def hung():\n    time.sleep(30)\n\n\n"
            "def test_a():\n    time.sleep(30)\n\n\n"
            "def test_b(hung):\n    pass\n\n\n"
            "def test_c():\n    pass\n"
        )
        result = suite.runpytest_subprocess("-o", "timeout=0.5")
        assert result.parseoutcomes() == {"failed": 1, "errors": 1, "passed": 1}
        result.stdout.fnmatch_lines(["*Timeout (>0.5s) from pytest-timeout*"])


class TestCoverage:
    """No pragma can hide code from coverage, and no module can go unmeasured.

    Coverage reads every module in the package and the tests, namespace packages
    included, run or not.
    """

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
        _ = run_module(
            "coverage",
            "run",
            f"--rcfile={pyproject}",
            "--source=.",
            "mod.py",
            cwd=tmp_path,
            check=True,
        )
        return run_module(
            "coverage",
            "report",
            f"--rcfile={pyproject}",
            "--fail-under=0",
            cwd=tmp_path,
            check=True,
        )

    def test_counts_every_unrun_module_in_the_package_and_tests(
        self, tmp_path: Path, pyproject: Path
    ) -> None:
        for name, text in {
            "nustack/__init__.py": "",
            "nustack/unrun.py": "x = 1\n",
            "tests/unit/unrun.py": "x = 1\n",
            "main.py": "import nustack\n",
        }.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / name).write_text(text)
        _ = run_module(
            "coverage",
            "run",
            f"--rcfile={pyproject}",
            "main.py",
            cwd=tmp_path,
            check=True,
        )
        output = run_module(
            "coverage",
            "json",
            f"--rcfile={pyproject}",
            "--fail-under=0",
            "-o",
            "-",
            cwd=tmp_path,
            check=True,
        )
        assert sorted(json.loads(output)["files"]) == [
            "nustack/__init__.py",
            "nustack/unrun.py",
            "tests/unit/unrun.py",
        ]

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
