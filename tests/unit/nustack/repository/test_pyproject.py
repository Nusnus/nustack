"""The project's settings yield what other files must agree with, or a Problem."""

import pytest

from nustack.repository.pyproject import InvalidPyprojectError
from nustack.repository.pyproject import Pyproject


class TestPyproject:
    """The settings other checks compare with come from pyproject.toml, or a Problem.

    Without Ruff's table, no folder is excluded.
    """

    def test_reads_the_version_and_ruffs_excluded_folders(self) -> None:
        pyproject = Pyproject.parse(
            b'[project]\nversion = "1.2.3"\n\n[tool.ruff]\nextend-exclude = ["v"]\n'
        )
        assert (pyproject.project.version, pyproject.tool.ruff.extend_exclude) == (
            "1.2.3",
            ("v",),
        )

    def test_excludes_no_folder_without_ruffs_table(self) -> None:
        pyproject = Pyproject.parse(b'[project]\nversion = "1.2.3"\n')
        assert pyproject.tool.ruff.extend_exclude == ()

    @pytest.mark.parametrize(
        ("content", "reason"),
        [
            (
                b"[project]\nname = 'x'\n",
                (
                    "needs a MAJOR.MINOR.PATCH version, such as 0.0.1, in its [project]"
                    " table, and a list of strings as any [tool.ruff] extend-exclude"
                ),
            ),
            (
                b'[project]\nversion = "999"\n',
                (
                    "needs a MAJOR.MINOR.PATCH version, such as 0.0.1, in its [project]"
                    " table, and a list of strings as any [tool.ruff] extend-exclude"
                ),
            ),
            (
                b"[project]\nversion = 1\n",
                (
                    "needs a MAJOR.MINOR.PATCH version, such as 0.0.1, in its [project]"
                    " table, and a list of strings as any [tool.ruff] extend-exclude"
                ),
            ),
            (
                b'[project]\nversion = "1"\n[tool.ruff]\nextend-exclude = 1\n',
                (
                    "needs a MAJOR.MINOR.PATCH version, such as 0.0.1, in its [project]"
                    " table, and a list of strings as any [tool.ruff] extend-exclude"
                ),
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
