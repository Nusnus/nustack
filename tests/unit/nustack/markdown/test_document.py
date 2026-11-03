"""Markdown reads into the parts the checks inspect, as GitHub and hosts render it."""

from pathlib import Path

import pytest
from markdown_it.token import Token

from nustack.markdown.document import Document
from nustack.markdown.document import Fence
from nustack.markdown.document import Lines
from nustack.markdown.document import Link
from nustack.markdown.document import Section
from nustack.markdown.document import UnmappedTokenError
from nustack.problem import Problem
from nustack.tree import File
from nustack.tree import Missing
from nustack.tree import Unreadable


class TestLines:
    """Each line a Problem names is the line an editor shows, for text and tokens.

    A token markdown-it maps to no lines is refused.
    """

    def test_break_only_where_hosts_break_them(self) -> None:
        assert Lines("a\u2028## b\x85\u2029c\r\nd\re\nf").lines == (
            "a\u2028## b\x85\u2029c\r\n",
            "d\r",
            "e\n",
            "f",
        )

    def test_span_a_token_with_a_line_range(self) -> None:
        assert Lines.span(Token("heading_open", "h2", 1, map=[3, 4])) == (3, 4)

    def test_refuse_a_token_without_a_line_range(self) -> None:
        with pytest.raises(UnmappedTokenError) as caught:
            Lines.span(Token("heading_open", "h2", 1))
        assert str(caught.value) == (
            "markdown-it gave the heading_open token no line range; pass"
            " Lines.span only block tokens, which markdown-it maps to lines"
        )


class TestSection:
    """What one heading governs, so a check can measure or quote that part alone."""

    @pytest.mark.parametrize(("line", "held"), [(1, False), (2, True), (4, False)])
    def test_holds_the_lines_from_its_heading_to_the_next(
        self, line: int, *, held: bool
    ) -> None:
        assert Section("A", "", 2, 4).holds(line) is held


class TestDocumentBody:
    """What a reader sees once hosts strip the header."""

    def test_leaves_out_the_frontmatter(self) -> None:
        assert Document(Path("/a.md"), "---\nname: a\n---\n# A\n").body == "# A\n"


class TestDocumentSections:
    """The parts a reader navigates by, as GitHub renders them, with editor lines.

    A document without a second-level heading holds none; a heading in a quote or in
    indented code splits nothing, nor does a line break hosts do not break at.
    """

    def test_split_at_second_level_headings_outside_code(self) -> None:
        text = "# T\n\n## 1\n\nOne.\n\n```text\n## no\n```\n\n## 2\n"
        assert Document(Path("/a.md"), text).sections == (
            Section("1", "One.\n\n```text\n## no\n```", 2, 10),
            Section("2", "", 10, 11),
        )

    def test_keep_quoted_headings_and_indented_code(self) -> None:
        text = "## 1\n\n    code\n\n> ## quoted\n\n- last\n"
        assert Document(Path("/a.md"), text).sections == (
            Section("1", "    code\n\n> ## quoted\n\n- last", 0, 7),
        )

    def test_break_lines_only_where_hosts_break_them(self) -> None:
        text = "## 1\n\nOne\u2028## no\x85\u2029\n\n## 2\n"
        assert Document(Path("/a.md"), text).sections == (
            Section("1", "One\u2028## no\x85\u2029", 0, 4),
            Section("2", "", 4, 5),
        )

    def test_leave_a_setext_underline_out_of_the_body(self) -> None:
        text = "1\n---\n\nOne.\n"
        assert Document(Path("/a.md"), text).sections == (Section("1", "One.", 0, 4),)

    def test_end_each_body_line_with_a_line_feed(self) -> None:
        text = "## 1\r\n\r\n- A.\r\n- B.\r\n\r\n## 2\r\rC.\r"
        assert Document(Path("/a.md"), text).sections == (
            Section("1", "- A.\n- B.", 0, 5),
            Section("2", "C.", 5, 8),
        )

    def test_without_a_second_level_heading_hold_no_section(self) -> None:
        assert Document(Path("/a.md"), "# T\n\nText.\n").sections == ()

    def test_counts_lines_from_the_body_after_front_matter(self) -> None:
        text = "---\n[x]: https://a\n---\n## A\n\nSee [x].\n\n## B\n\nb\n"
        assert Document(Path("/a.md"), text).sections == (
            Section("A", "See [x].", 0, 4),
            Section("B", "b", 4, 7),
        )


class TestDocumentAnchors:
    """Every anchor a link may name, so a broken one is caught before it ships."""

    def test_name_each_heading_as_github_does(self) -> None:
        text = (
            "# Top\n\n## 🔀 How it works\n\n### `make check` runs\n\n"
            "## Top\n\n## Top\n\n## A, b & c!\n"
        )
        assert Document(Path("/a.md"), text).anchors == {
            "top",
            "-how-it-works",
            "make-check-runs",
            "top-1",
            "top-2",
            "a-b--c",
        }


class TestDocumentAbsolute:
    """Paths that break once the plugin moves, told apart from links that leave it."""

    def test_holds_a_local_path_from_the_root_apart_from_urls(self) -> None:
        document = Document(
            Path("/r/a.md"), "[a](/r/b.md) [n](/r/a%00.md) [u](https://x.io/b.md)\n"
        )
        assert (document.absolute, document.malformed, document.links) == (
            ("/r/b.md", "/r/a%00.md"),
            (),
            (Link("https://x.io/b.md", None, "", 0),),
        )


class TestDocumentMalformed:
    """Hrefs no file could ever be, kept apart so their Problem asks for a rewrite."""

    def test_holds_a_link_no_file_can_be(self) -> None:
        document = Document(Path("/r/a.md"), "[n](a%00.md)\n")
        assert (document.malformed, document.links) == (("a%00.md",), ())


class TestDocumentLinks:
    """Every target a reader can follow, resolved to the file and heading it reaches.

    A link with a scheme or a host reaches no file, and frontmatter holds no link.
    """

    def test_hold_each_link_and_image_outside_code(self) -> None:
        text = (
            "[b](b.md#part) [web](https://x.io) [top](#top)\n"
            "`[inline](inline.md)`\n\n"
            "```\n[c](c.md)\n```\n\n"
            "![i](i.png) [empty]()\n"
        )
        assert Document(Path("/r/a.md"), text).links == (
            Link("b.md#part", Path("/r/b.md"), "part", 0),
            Link("https://x.io", None, "", 0),
            Link("#top", Path("/r/a.md"), "top", 0),
            Link("i.png", Path("/r/i.png"), "", 7),
            Link("", Path("/r/a.md"), "", 7),
        )

    def test_resolve_titles_references_encodings_and_parents(self) -> None:
        text = (
            '[t](t.md "Title") [r][ref] [s](my%20file.md) [u](../u.md)\n\n[ref]: r.md\n'
        )
        assert [link.target for link in Document(Path("/r/s/a.md"), text).links] == [
            Path("/r/s/t.md"),
            Path("/r/s/r.md"),
            Path("/r/s/my file.md"),
            Path("/r/u.md"),
        ]

    def test_take_no_target_from_a_scheme_or_a_host(self) -> None:
        text = "[p](//x.io/a) [t](tel:+15551234) [q](q.md?plain=1)\n"
        assert [link.target for link in Document(Path("/r/a.md"), text).links] == [
            None,
            None,
            Path("/r/q.md"),
        ]

    def test_skip_the_frontmatter(self) -> None:
        text = "---\ndescription: '[b](b.md)'\n---\n# A\n"
        assert Document(Path("/r/a.md"), text).links == ()


class TestDocumentFences:
    """The code examples a check reads by their language, apart from the prose."""

    def test_hold_each_fenced_block_with_its_info(self) -> None:
        text = "```markdown\nA line.\n```\n\n    indented\n\n~~~ text \nB\n~~~\n"
        assert Document(Path("/a.md"), text).fences == (
            Fence("markdown", "A line.\n"),
            Fence("text", "B\n"),
        )


class TestDocumentSteps:
    """The steps a playbook's done-condition check walks; their sublists stay inside."""

    def test_hold_each_top_level_numbered_item_with_its_lines(self) -> None:
        text = (
            "# P\n\n1. One.\n   1. Inner.\n\n   More.\n2. Two.\n\n"
            "- loose\n\n> 1. quoted\n"
        )
        assert Document(Path("/a.md"), text).steps == (
            "1. One.\n   1. Inner.\n\n   More.\n",
            "2. Two.\n\n",
        )


class TestDocumentDefinitions:
    """Each link definition's target and title, keyed as markdown-it keys its label.

    A definition with no title holds an empty one, and nothing else markdown-it
    records is kept, so no caller can change a definition.
    """

    def test_keeps_each_target_and_title_in_mappings_no_caller_can_change(
        self,
    ) -> None:
        text = '[Kit]: https://a "T"\n[b]: /b\n'
        definitions = Document(Path("/a.md"), text).definitions
        assert (type(definitions), type(definitions["KIT"]), definitions) == (
            frozendict,
            frozendict,
            {
                "KIT": {"href": "https://a", "title": "T"},
                "B": {"href": "/b", "title": ""},
            },
        )


class TestDocumentReferences:
    """Each link definition's target, keyed as markdown-it keys its label."""

    def test_gives_each_target_in_a_mapping_no_caller_can_change(self) -> None:
        references = Document(Path("/a.md"), "[Kit]: https://a\n").references
        assert (type(references), references) == (frozendict, {"KIT": "https://a"})


class TestDocumentOf:
    """Only text every host decodes becomes a document; any other file, the reason."""

    def test_reads_a_utf8_file(self) -> None:
        assert Document.of(Path("/a.md"), File(b"# A\n"), "is missing") == Document(
            Path("/a.md"), "# A\n"
        )

    @pytest.mark.parametrize(
        ("read", "what"),
        [
            (File(b"\xff"), "is not valid UTF-8; save it as UTF-8"),
            (Missing(), "is missing; add it"),
            (Unreadable("cannot be read"), "cannot be read"),
        ],
    )
    def test_says_why_a_file_gives_no_document(
        self, read: File | Missing | Unreadable, what: str
    ) -> None:
        assert Document.of(Path("/a.md"), read, "is missing; add it") == Problem(
            Path("/a.md"), what
        )


class TestDocumentLineAt:
    """Where a match sits in the text, as the line a Problem names."""

    @pytest.mark.parametrize(("index", "line"), [(0, 1), (2, 1), (3, 2), (6, 3)])
    def test_counts_the_lines_up_to_an_index_from_one(
        self, index: int, line: int
    ) -> None:
        assert Document(Path("/a.md"), "ab\ncd\nef\n").line_at(index) == line


class TestDocumentShows:
    """A part, such as a release's notes, shows a reader something on GitHub.

    A part may show a reader nothing at all.
    """

    @pytest.mark.parametrize(
        "part",
        [
            "- Adds.\n",
            "- Adds. <!-- Draft -->\n",
            "`<!-- -->`\n",
            "```\n<!-- -->\n```\n",
            "    <!-- -->\n",
            "![](logo.png)\n",
            "<p>Adds.</p>\n",
            "<!-- Draft --> Adds.\n",
            '<img alt="Launch" src="https://example.com/a.png">\n',
            '<img src="logo.png">\n',
            "<p>&copy;</p>\n",
            "<script></script>\n",
            "<style>a{}</style>\n",
            "<textarea>a</textarea>\n",
            '<p><img alt="Launch" src="https://example.com/a.png"></p>\n',
            "Adds. <b></b>\n",
            "&lt;!-- --&gt;\n",
        ],
    )
    def test_shows_text_code_or_an_image(self, part: str) -> None:
        assert Document(Path("/a.md"), part).shows(part) is True

    @pytest.mark.parametrize(
        "part",
        [
            "",
            "<!-- Draft: write release notes here -->\n",
            "<!--\nDraft\n-->\n",
            "[kit]: https://example.com\n",
            "&nbsp;\n",
            "\u200b\n",
            "-\n",
            "---\n",
            "#\n",
            "<details></details>\n",
            "```\n```\n",
            "<b></b>\n",
            "<p>&nbsp;</p>\n",
            "<div>&nbsp;</div>\n",
            "<p>&#8203;</p>\n",
            "<br>\n",
        ],
    )
    def test_shows_nothing_a_reader_sees(self, part: str) -> None:
        assert Document(Path("/a.md"), part).shows(part) is False


class TestDocumentStandsAlone:
    """A part lifted out, as a release's notes are, keeps every reference it uses.

    A definition in the front matter is no reference of the body.
    """

    @pytest.mark.parametrize(
        ("part", "alone"), [("[x][ref]\n", False), ("[y](y.md)\n", True)]
    )
    def test_tells_whether_a_part_reads_the_same_without_the_rest(
        self, part: str, *, alone: bool
    ) -> None:
        document = Document(Path("/a.md"), f"{part}\n[ref]: r.md\n")
        assert document.stands_alone(part) is alone

    def test_counts_no_reference_in_the_front_matter_as_one_of_the_body(self) -> None:
        document = Document(Path("/a.md"), "---\n[x]: https://a\n---\nSee [x].\n")
        assert document.stands_alone("[x]\n") is True
