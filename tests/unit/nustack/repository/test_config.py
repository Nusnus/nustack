"""A YAML config file reads down to what the check reads, or is refused naming why."""

import warnings
from pathlib import PurePosixPath
from typing import ClassVar

import pytest

from nustack.repository.config import InvalidConfigError
from nustack.repository.config import YamlConfig
from nustack.yaml_reader import YamlWarning


class TestYamlConfig:
    """A config reads as its model, down to the keys the model names.

    A file that is not UTF-8, YAML that does not parse or that the reader refuses,
    and a file that lacks what the model reads are each refused, with the line where
    one applies, counted from 1. A warning of the reader's names the file.
    """

    class Named(YamlConfig):
        """A config that reads one key."""

        PATH: ClassVar[PurePosixPath] = PurePosixPath("named.yaml")
        name: str

    @pytest.mark.parametrize(
        ("content", "reason"),
        [
            (b"name: x\n# caf\xe9\n", "it is not valid UTF-8; save it as UTF-8"),
            (
                "name: x\n".encode("utf-16"),
                "it is not valid UTF-8; save it as UTF-8",
            ),
            (b"name: [\n", "it is not valid YAML on line 2; fix it"),
            (
                b"name: x\ny: !!set {}\n",
                "it uses a tag on line 2 that nustack does not read; remove the tag",
            ),
            (
                b"name: x\ny: !!str [1]\n",
                (
                    "it holds a value on line 2 that YAML cannot build as its type;"
                    " fix the value, or remove its tag or merge key"
                ),
            ),
            (b"name: x\nname: x\n", "it repeats a key on line 2; keep one"),
            (
                b"%YAML 1.3\n---\nname: x\n",
                (
                    "it names a YAML version other than 1.1 or 1.2 on line 1; set it"
                    " to 1.2"
                ),
            ),
            (
                b"name: x\na: &y 1\nb: &y 2\n",
                "it reuses an anchor name; give each anchor its own name",
            ),
            (b"other: x\n", "name: add it"),
        ],
    )
    def test_refuses_a_file_it_cannot_read(self, content: bytes, reason: str) -> None:
        with pytest.raises(InvalidConfigError) as caught:
            self.Named.parse(content)
        assert str(caught.value) == reason

    @pytest.mark.parametrize(
        "content",
        [
            b"name: x\n# cafe\n",
            b"name: x\n",
            b"name: x\ny: !!map {}\n",
            b"name: x\ny: !!str 1\n",
            b"name: x\ny: []\n",
            b"%YAML 1.2\n---\nname: x\n",
            b"name: x\na: &y 1\nb: &z 2\n",
            b"other: y\nname: x\n",
        ],
    )
    def test_reads_a_file_each_refused_one_differs_from_only_where_it_breaks(
        self, content: bytes
    ) -> None:
        assert self.Named.parse(content).name == "x"

    def test_names_itself_in_a_warning_of_the_reader(self) -> None:
        with warnings.catch_warnings(record=True) as heard:
            warnings.simplefilter("always")
            self.Named.parse(b"%YAML 1.1\n---\nname: x\nn: 1e3\n")
        assert [(each.category, str(each.message)) for each in heard] == [
            (
                YamlWarning,
                (
                    "line 4 of named.yaml holds a YAML 1.1 float with no dot in its"
                    " mantissa; add one, such as 1.0e3, or declare %YAML 1.2"
                ),
            )
        ]
