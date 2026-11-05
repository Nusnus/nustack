"""`.gitattributes` yields only the lines that set attributes, each with single spaces.

Blank lines and comments yield nothing, and a file that is not UTF-8 is refused.
"""

import pytest

from nustack.repository.gitattributes import GitAttributes


class TestGitAttributes:
    """The check compares each line that sets attributes as Git splits it."""

    @pytest.mark.parametrize(
        ("content", "lines"),
        [
            (b"# the copies\nplugin/** text eol=lf\n", ("plugin/** text eol=lf",)),
            (b"  # indented\n", ()),
            (b"\n   \nplugin/** -text\n\n", ("plugin/** -text",)),
            (b"  plugin/**\t  text   eol=lf  \n", ("plugin/** text eol=lf",)),
            (b"a -text\r\nb -text", ("a -text", "b -text")),
        ],
    )
    def test_reads_each_line_that_sets_attributes(
        self, content: bytes, lines: tuple[str, ...]
    ) -> None:
        assert GitAttributes.parse(content).lines == lines

    def test_refuses_a_file_that_is_not_utf_8(self) -> None:
        with pytest.raises(UnicodeDecodeError):
            GitAttributes.parse(b"plugin/** -text\n\xff\n")
