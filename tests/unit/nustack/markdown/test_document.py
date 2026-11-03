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
        assert Section("A", "", 2, 3, 4).holds(line) is held

    @pytest.mark.parametrize(("line", "held"), [(2, False), (3, True), (4, False)])
    def test_holds_in_its_body_the_lines_below_its_heading(
        self, line: int, *, held: bool
    ) -> None:
        assert Section("A", "", 2, 3, 4).holds_in_body(line) is held


class TestDocumentBody:
    """What a reader sees once hosts strip the frontmatter."""

    def test_leaves_out_the_frontmatter(self) -> None:
        assert Document(Path("/a.md"), "---\nname: a\n---\n# A\n").body == "# A\n"


class TestDocumentSections:
    """The parts a reader navigates by, as GitHub renders them, with editor lines.

    A heading in a quote or in indented code splits nothing, nor does a line break hosts
    do not break at. Line breaks in a body are line feeds, whatever the file's line
    endings, and a document without a second-level heading holds no section.
    """

    def test_split_at_second_level_headings_outside_code(self) -> None:
        text = "# T\n\n## 1\n\nOne.\n\n```text\n## no\n```\n\n## 2\n"
        assert Document(Path("/a.md"), text).sections == (
            Section("1", "One.\n\n```text\n## no\n```", 2, 3, 10),
            Section("2", "", 10, 11, 11),
        )

    def test_keep_quoted_headings_and_indented_code(self) -> None:
        text = "## 1\n\n    code\n\n> ## quoted\n\n- last\n"
        assert Document(Path("/a.md"), text).sections == (
            Section("1", "    code\n\n> ## quoted\n\n- last", 0, 1, 7),
        )

    def test_break_lines_only_where_hosts_break_them(self) -> None:
        text = "## 1\n\nOne\u2028## no\x85\u2029\n\n## 2\n"
        assert Document(Path("/a.md"), text).sections == (
            Section("1", "One\u2028## no\x85\u2029", 0, 1, 4),
            Section("2", "", 4, 5, 5),
        )

    def test_leave_a_setext_underline_out_of_the_body(self) -> None:
        text = "1\n---\n\nOne.\n"
        assert Document(Path("/a.md"), text).sections == (
            Section("1", "One.", 0, 2, 4),
        )

    def test_break_body_lines_with_line_feeds(self) -> None:
        text = "## 1\r\n\r\n- A.\r\n- B.\r\n\r\n## 2\r\rC.\rD.\r"
        assert Document(Path("/a.md"), text).sections == (
            Section("1", "- A.\n- B.", 0, 1, 5),
            Section("2", "C.\nD.", 5, 6, 9),
        )

    def test_are_empty_without_a_second_level_heading(self) -> None:
        assert Document(Path("/a.md"), "# T\n\nText.\n").sections == ()

    def test_count_lines_from_the_body_after_frontmatter(self) -> None:
        text = "---\n[x]: https://a\n---\n## A\n\nSee [x].\n\n## B\n\nb\n"
        assert Document(Path("/a.md"), text).sections == (
            Section("A", "See [x].", 0, 1, 4),
            Section("B", "b", 4, 5, 7),
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
    """Every Markdown link and image, resolved to the file and heading it reaches.

    A bare URL or email address stays text, and so does a URL in a link's text. A link
    in a table sits on its row's line, a link with a scheme or a host reaches no file,
    and frontmatter holds no link.
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

    def test_leave_bare_urls_and_email_addresses_as_text(self) -> None:
        text = (
            "See [the docs at www.x.io](https://x.io), www.y.io, https://y.io/a"
            " and a@y.io.\n"
        )
        assert Document(Path("/r/a.md"), text).links == (
            Link("https://x.io", None, "", 0),
        )

    def test_in_a_table_sit_on_their_rows_line(self) -> None:
        text = "| A | B |\n| - | - |\n| [a](a.md) | x |\n| [b](b.md) | y |\n"
        assert Document(Path("/r/s.md"), text).links == (
            Link("a.md", Path("/r/a.md"), "", 2),
            Link("b.md", Path("/r/b.md"), "", 3),
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


class TestDocumentHeaded:
    """The sections at any heading level, each running to the next heading as high.

    A deeper heading stays in the body; a heading as high or higher ends it.
    """

    TEXT = "# T\n\n## A\n\n### 1\n\nOne.\n\n#### d\n\nDeep.\n\n### 2\n\nTwo.\n\n## B\n"

    def test_keep_deeper_headings_in_the_body(self) -> None:
        assert Document(Path("/a.md"), self.TEXT).headed(3) == (
            Section("1", "One.\n\n#### d\n\nDeep.", 4, 5, 12),
            Section("2", "Two.", 12, 13, 16),
        )

    def test_end_at_a_higher_heading(self) -> None:
        assert Document(Path("/a.md"), self.TEXT).headed(4) == (
            Section("d", "Deep.", 8, 9, 12),
        )

    def test_keep_every_character_of_the_body_but_its_blank_lines(self) -> None:
        text = "### X\n\nX\n\nX\n"
        assert Document(Path("/a.md"), text).headed(3) == (
            Section("X", "X\n\nX", 0, 1, 5),
        )

    def test_run_the_top_level_to_the_end(self) -> None:
        assert Document(Path("/a.md"), "# T\n\nText.\n\n# U\n").headed(1) == (
            Section("T", "Text.", 0, 1, 4),
            Section("U", "", 4, 5, 5),
        )


class TestDocumentLineAt:
    """Where a match sits in the text, as the line a Problem names."""

    @pytest.mark.parametrize(("index", "line"), [(0, 1), (2, 1), (3, 2), (6, 3)])
    def test_counts_the_lines_up_to_an_index_from_one(
        self, index: int, line: int
    ) -> None:
        assert Document(Path("/a.md"), "ab\ncd\nef\n").line_at(index) == line


class TestDocumentRelativeHrefs:
    """The relative targets a section's body links to, which break off the page.

    A target with a scheme or a host is no relative one, but a path from the root is,
    and the heading's own link is not the body's.
    """

    def test_name_each_link_and_image_in_the_body(self) -> None:
        text = (
            "## [A](a.md)\n\n[b](b.md) [web](https://x.io) [top](#top) ![i](i.png)"
            " [h](//x.io/h) [r](/r.md)\n\n"
            "## B\n\n[c](c.md)\n"
        )
        document = Document(Path("/r/a.md"), text)
        assert document.relative_hrefs(document.sections[0]) == (
            "b.md",
            "#top",
            "i.png",
            "/r.md",
        )


class TestDocumentShows:
    """A part, such as the changelog entry, shows a reader something on GitHub.

    Text, code, an image or a tag GitHub shows as text is something, and so is a
    details element. A comment, a reference definition, a blank character, a thematic
    break, a task item's checkbox, an empty tag such as `<b></b>`, or an empty list
    item, table, heading or code block is not, though GitHub may draw it. A task marker
    with nothing after it is text, as GitHub prints it, and so are three tildes or more,
    while one or two strike text out. The rows run in the order this docstring names
    each kind, and each row that shows nothing has its shown partner at the same place
    in the shown rows, which then list the rows with no partner.
    """

    @pytest.mark.parametrize(
        "part",
        [
            "Adds.\n",
            "<!-- Draft: write release notes here --> Adds.\n",
            "<!--\nDraft\n-->\nAdds.\n",
            "[kit]: https://example.com\n\n[kit]\n",
            "&copy;\n",
            "\u200bAdds.\n",
            "<p>&copy;</p>\n",
            "<div>&copy;</div>\n",
            "<p>&#8203;Adds.</p>\n",
            "---\n\nAdds.\n",
            "<hr>Adds.\n",
            "- [ ] <!-- x --> Adds.\n",
            "- [x] <!-- x --> Adds.\n",
            "<b>Adds.</b>\n",
            "<br>Adds.\n",
            "- Adds.\n",
            "1. Adds.\n",
            "<table><tr><td>Adds.</td></tr></table>\n",
            "| Adds. |\n|-|\n| |\n",
            "# Adds.\n",
            "```\n<!-- -->\n```\n",
            "~~&copy;~~\n",
            "~<!-- x -->Adds.~\n",
            "- Adds. <!-- Draft -->\n",
            "Adds. <b></b>\n",
            "&lt;!-- --&gt;\n",
            "`<!-- -->`\n",
            "    <!-- -->\n",
            "![](logo.png)\n",
            '<img alt="Launch" src="https://example.com/a.png">\n',
            '<img src="logo.png">\n',
            '<p><img alt="Launch" src="https://example.com/a.png"></p>\n',
            "<script></script>\n",
            "<style>a{}</style>\n",
            "<textarea>a</textarea>\n",
            "<details></details>\n",
            "- [ ]\n",
            "&nbsp;~~~~&nbsp;~~~~\n",
        ],
    )
    def test_finds_text_code_or_a_shown_tag(self, part: str) -> None:
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
            "<p>&nbsp;</p>\n",
            "<div>&nbsp;</div>\n",
            "<p>&#8203;</p>\n",
            "---\n",
            "<hr>\n",
            "- [ ] <!-- x -->\n",
            "- [x] <!-- x -->\n",
            "<b></b>\n",
            "<br>\n",
            "-\n",
            "1.\n",
            "<table><tr><td></td></tr></table>\n",
            "| |\n|-|\n| |\n",
            "#\n",
            "```\n```\n",
            "~~&nbsp;~~\n",
            "~<!-- x -->~\n",
        ],
    )
    def test_finds_that_markup_without_content_shows_nothing(self, part: str) -> None:
        assert Document(Path("/a.md"), part).shows(part) is False


class TestDocumentStandsAlone:
    """A part lifted out, as the changelog entry is, keeps every reference it uses.

    A definition in the frontmatter is no reference of the body.
    """

    @pytest.mark.parametrize(
        ("part", "alone"), [("[x][ref]\n", False), ("[y](y.md)\n", True)]
    )
    def test_tells_whether_a_part_reads_the_same_without_the_rest(
        self, part: str, *, alone: bool
    ) -> None:
        document = Document(Path("/a.md"), f"{part}\n[ref]: r.md\n")
        assert document.stands_alone(part) is alone

    def test_counts_no_reference_in_the_frontmatter_as_one_of_the_body(self) -> None:
        document = Document(Path("/a.md"), "---\n[x]: https://a\n---\nSee [x].\n")
        assert document.stands_alone("[x]\n") is True
