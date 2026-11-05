"""The project's settings yield what other files must agree with, or a Problem."""

import pytest

from nustack.repository.pyproject import InvalidPyprojectError
from nustack.repository.pyproject import Pyproject


class TestPyproject:
    """The settings other checks compare with come from pyproject.toml, or a Problem.

    Without commitizen's table, no tag format is named and `cz bump` versions no file;
    without mutmut's or nustack's, mutmut mutates nothing named and its tests read
    nothing listed; without Ruff's, no
    folder is excluded.
    """

    def test_reads_the_version_and_each_tools_settings(
        self,
    ) -> None:
        pyproject = Pyproject.parse(
            b'[project]\nversion = "1.2.3"\n\n'
            b'[tool.commitizen]\ntag_format = "v$version"\n'
            b'version_files = ["f:version"]\n\n'
            b'[tool.mutmut]\nsource_paths = ["src/p"]\n\n'
            b'[tool.nustack.mutation]\nreads = ["Makefile"]\n\n'
            b'[tool.ruff]\nextend-exclude = ["v"]\n'
        )
        assert (
            pyproject.project.version,
            pyproject.tool.commitizen.tag_format,
            pyproject.tool.commitizen.version_files,
            pyproject.tool.mutmut.source_paths,
            pyproject.tool.nustack.mutation.reads,
            pyproject.tool.ruff.extend_exclude,
        ) == ("1.2.3", "v$version", ("f:version",), ("src/p",), ("Makefile",), ("v",))

    def test_names_no_tool_setting_without_its_table(
        self,
    ) -> None:
        pyproject = Pyproject.parse(b'[project]\nversion = "1.2.3"\n')
        assert (
            pyproject.tool.commitizen.tag_format,
            pyproject.tool.commitizen.version_files,
            pyproject.tool.mutmut.source_paths,
            pyproject.tool.nustack.mutation.reads,
            pyproject.tool.ruff.extend_exclude,
        ) == (None, (), (), (), ())

    @pytest.mark.parametrize(
        ("content", "reason"),
        [
            (
                b"[project]\nname = 'x'\n",
                "project.version: add it",
            ),
            (
                b'[project]\nversion = "999"\n',
                (
                    "project.version: use MAJOR.MINOR.PATCH without leading zeros,"
                    " such as 0.0.1"
                ),
            ),
            (
                b"[project]\nversion = 1\n",
                "project.version: make it a string",
            ),
            (
                b'[project]\nversion = "1.2.3"\n[tool.ruff]\nextend-exclude = 1\n',
                "tool.ruff.extend-exclude: make it a list",
            ),
            (
                b'[project]\nversion = "1.2.3"\n[tool.commitizen]\ntag_format = 1\n',
                "tool.commitizen.tag_format: make it a string",
            ),
            (
                b'[project]\nversion = "1.2.3"\n[tool.commitizen]\nversion_files = 1\n',
                "tool.commitizen.version_files: make it a list",
            ),
            (
                b"[project]\nsecret = canary\n",
                "it is not valid TOML on line 2; fix it",
            ),
            (b"\xff", "it is not valid UTF-8; save it as UTF-8"),
            (
                b"[project]\nversion = " + b"1" * 5000 + b"\n",
                "it holds a number too long to read; shorten it",
            ),
            (
                b"x = " + b"[" * 5000 + b"]" * 5000 + b"\n",
                "it nests too deeply to read; flatten it",
            ),
        ],
    )
    def test_refuses_a_file_it_cannot_read(self, content: bytes, reason: str) -> None:
        with pytest.raises(InvalidPyprojectError) as caught:
            Pyproject.parse(content)
        assert str(caught.value) == reason
