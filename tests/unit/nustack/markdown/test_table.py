"""Tables read as GitHub renders them, each cell as its text and first link."""

from pathlib import Path

from nustack.markdown.document import Document
from nustack.markdown.table import Cell
from nustack.markdown.table import Row
from nustack.markdown.table import Table
from nustack.markdown.table import Tables


class TestTables:
    """Each rendered table reads as its header and body rows, in order.

    A table in a fenced block or an HTML comment, which never renders, holds no rows.
    A row holds the line it starts on. A cell reads as the text it renders, an escaped
    pipe stays in it, and a cell holds its first link's target and text, past any link
    inside that text.
    """

    def test_reads_no_table_that_never_renders(self) -> None:
        table = "| a | b |\n| - | - |\n| c | d |\n"
        assert (
            Tables(
                Document(Path("/a.md"), f"```\n{table}```\n\n<!--\n{table}-->\n")
            ).tables
            == ()
        )

    def test_reads_each_table_as_its_header_and_rows(self) -> None:
        text = "| a | b |\n| - | - |\n| c | d |\n\ntext\n\n| e |\n| - |\n"
        assert Tables(Document(Path("/a.md"), text)).tables == (
            Table(
                (Cell("a", None, None), Cell("b", None, None)),
                (Row(2, (Cell("c", None, None), Cell("d", None, None))),),
            ),
            Table((Cell("e", None, None),), ()),
        )

    def test_reads_a_cells_text_as_it_renders(self) -> None:
        text = "| a |\n| - |\n| \\*b\\* &amp;amp; *c* `d` ![e](f) <i>g</i> |\n"
        assert Tables(Document(Path("/a.md"), text)).tables[0].body == (
            Row(2, (Cell("*b* &amp; c d e g", None, None),)),
        )

    def test_reads_a_cells_first_link_and_its_escaped_pipe(self) -> None:
        text = "| a | b |\n| - | - |\n| [x](y) [z](w) | p \\| q |\n|  | e |\n"
        assert Tables(Document(Path("/a.md"), text)).tables[0].body == (
            Row(2, (Cell("x z", "y", "x"), Cell("p | q", None, None))),
            Row(3, (Cell("", None, None), Cell("e", None, None))),
        )

    def test_reads_a_links_text_across_its_formatting(self) -> None:
        text = "| a |\n| - |\n| [*x* `y`](z) |\n"
        assert Tables(Document(Path("/a.md"), text)).tables[0].body == (
            Row(2, (Cell("x y", "z", "x y"),)),
        )

    def test_ends_a_link_at_its_own_close_past_an_autolink_in_its_text(self) -> None:
        text = "| a |\n| - |\n| [<http://x> y](z) |\n"
        assert Tables(Document(Path("/a.md"), text)).tables[0].body == (
            Row(2, (Cell("http://x y", "z", "http://x y"),)),
        )
