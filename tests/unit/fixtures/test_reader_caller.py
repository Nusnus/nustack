"""A caller reads from one line of its own, and deeper reads from the reader's file."""

import inspect
import warnings

from nustack import yaml_reader
from tests.fixtures import reader_caller
from tests.fixtures.reader_caller import Caller


class TestCaller:
    """A read keeps each warning its call raised and the line that made the call.

    deeper's reader reads YAML as the reader does, from a function in its file.
    """

    def test_keeps_each_warning_and_the_line_that_called_the_reader(self) -> None:
        def reader(text: str) -> None:
            warnings.warn(text, stacklevel=2)

        line, heard = Caller(reader).read("heard")
        assert [(str(each.message), each.filename, each.lineno) for each in heard] == [
            ("heard", reader_caller.__file__, line)
        ]

    def test_reads_yaml_from_a_function_in_the_readers_file(self) -> None:
        reader = Caller.deeper().reader
        assert (reader("a: 1\n"), inspect.getfile(reader)) == (
            {"a": 1},
            yaml_reader.__file__,
        )
