"""Frontmatter reads only as the lines every host reads alike, and refuses the rest.

Hosts find the same frontmatter and strip it alike, and its fields read as one-line
values and list entries; the sync still compares frontmatter whose close an edit
broke.
"""

import pytest

from nustack.markdown.frontmatter import FrontmatterBlock
from nustack.markdown.frontmatter import InvalidFrontmatterError


class TestFrontmatterBlockFields:
    """Fields read as one-line values and list entries, frozen all the way down.

    An empty block holds no fields. Each line a host might read differently is
    refused by line, a reused anchor with no line, and a repeated key and YAML that
    does not parse by line. A value untagged or with a core tag reads, and a tag
    outside YAML's core schema, such as binary, a set or pairs, is refused by line.
    Nesting too deep, a key that is not text and a control character are
    refused with no line, and a value YAML cannot build as its type by line. Each
    value a host might read differently is refused by line, an alias that contains
    itself is refused, and a shared alias is checked once.
    """

    # An alias walk that revisits what it read slows to a stall; this fails it at once.
    QUICK = pytest.mark.timeout(5)
    LEVELS = 40
    CHAIN = 3000

    def test_reads_each_field(self) -> None:
        assert FrontmatterBlock("name: a\n").fields == frozendict({"name": "a"})

    def test_reads_a_key_that_starts_with_a_capital(self) -> None:
        assert FrontmatterBlock("Description: B.\n").fields == frozendict(
            {"Description": "B."}
        )

    def test_reads_a_key_with_a_space_and_no_value(self) -> None:
        assert FrontmatterBlock("name: \n").fields == frozendict({"name": None})

    def test_reads_no_fields_from_an_empty_block(self) -> None:
        assert FrontmatterBlock("").fields == frozendict()

    def test_refuses_a_list_in_place_of_fields(self) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock("- a\n").fields
        assert str(caught.value) == (
            "it is a list, not key: value fields; write each field as key: value"
        )

    def test_reads_two_dashes_inside_a_value(self) -> None:
        assert FrontmatterBlock("name: a -- b\n").fields == frozendict(
            {"name": "a -- b"}
        )

    @pytest.mark.parametrize("newline", ["\n", "\r\n"])
    def test_reads_fields_and_list_entries(self, newline: str) -> None:
        frontmatter = newline.join(
            ["name: a", "triggers:", "  - user", "tags:", "- b", ""]
        )
        assert FrontmatterBlock(frontmatter).fields == frozendict(
            {"name": "a", "triggers": ("user",), "tags": ("b",)}
        )

    @pytest.mark.parametrize(
        ("frontmatter", "reasons"),
        [
            (
                "name: a---b\n",
                (
                    (
                        "line 2 holds ---, which some hosts read as the end of the"
                        " frontmatter; reword it"
                    ),
                ),
            ),
            (
                "name: a---b\ndescription: c---d\n",
                (
                    (
                        "line 2 holds ---, which some hosts read as the end of the"
                        " frontmatter; reword it"
                    ),
                    (
                        "line 3 holds ---, which some hosts read as the end of the"
                        " frontmatter; reword it"
                    ),
                ),
            ),
            (
                'name: "a\n  --- b"\n',
                (
                    (
                        "line 3 holds ---, which some hosts read as the end of the"
                        " frontmatter; reword it"
                    ),
                    (
                        "line 3 is not a field (a key that starts with a letter, then a"
                        " colon, and a space before any value) or a list entry (spaces,"
                        " then a dash and a space), the only lines nustack accepts; put"
                        " each field on one line, and delete any other line"
                    ),
                ),
            ),
            (
                "---x: b\n",
                (
                    (
                        "line 2 holds ---, which some hosts read as the end of the"
                        " frontmatter; reword it"
                    ),
                    (
                        "line 2 is not a field (a key that starts with a letter, then a"
                        " colon, and a space before any value) or a list entry (spaces,"
                        " then a dash and a space), the only lines nustack accepts; put"
                        " each field on one line, and delete any other line"
                    ),
                ),
            ),
        ],
    )
    def test_refuses_dashes_anywhere(
        self, frontmatter: str, reasons: tuple[str, ...]
    ) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(frontmatter).fields
        assert caught.value.reasons == reasons

    def test_reports_every_line_it_refuses(self) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock("# a\nname: a\ndescription: b\u2028c\n\n").fields
        assert caught.value.reasons == (
            (
                "line 2 is not a field (a key that starts with a letter, then a"
                " colon, and a space before any value) or a list entry (spaces,"
                " then a dash and a space), the only lines nustack accepts; put"
                " each field on one line, and delete any other line"
            ),
            (
                "line 4 holds a Unicode line or paragraph separator, which hosts read"
                " differently and most editors hide; delete it"
            ),
            (
                "line 5 is not a field (a key that starts with a letter, then a"
                " colon, and a space before any value) or a list entry (spaces,"
                " then a dash and a space), the only lines nustack accepts; put"
                " each field on one line, and delete any other line"
            ),
        )

    @pytest.mark.parametrize(
        ("frontmatter", "reason"),
        [
            (
                "%YAML 1.1\nname: a\n",
                (
                    "line 2 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "%TAG !e! tag:example.com,2000:\nname: a\n",
                (
                    "line 2 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "\ufeff%YAML 1.1\nname: a\n",
                (
                    "line 2 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "# a comment\nname: a\n",
                (
                    "line 2 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "name: a\n\ndescription: b\n",
                (
                    "line 3 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                'name: "a\nb"\n',
                (
                    "line 3 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                'name: "a\n  b"\n',
                (
                    "line 3 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                'name: "a\n... b"\n',
                (
                    "line 3 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "name: >\n  a\n",
                (
                    "line 3 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "name: a\n...\n",
                (
                    "line 3 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "name: a\r%YAML 1.1\rdescription: b\n",
                (
                    "line 2 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "name: a\r\r\n",
                (
                    "line 2 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "metadata:\n  a: b\n",
                (
                    "line 3 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "name:\tb\n",
                (
                    "line 2 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "name:b\n",
                (
                    "line 2 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "1a: b\n",
                (
                    "line 2 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "tags:\n\t- b\n",
                (
                    "line 3 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
            (
                "tags:\n- \n",
                (
                    "line 3 is not a field (a key that starts with a letter, then a"
                    " colon, and a space before any value) or a list entry (spaces,"
                    " then a dash and a space), the only lines nustack accepts; put"
                    " each field on one line, and delete any other line"
                ),
            ),
        ],
    )
    def test_refuses_a_line_that_is_not_a_field_or_a_list_entry(
        self, frontmatter: str, reason: str
    ) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(frontmatter).fields
        assert str(caught.value) == reason

    @pytest.mark.parametrize("separator", ["\x85", "\u2028", "\u2029"])
    def test_refuses_a_unicode_line_separator(self, separator: str) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(f"name: a\ndescription: A{separator}b.\n").fields
        assert str(caught.value) == (
            "line 3 holds a Unicode line or paragraph separator, which hosts read"
            " differently and most editors hide; delete it"
        )

    def test_refuses_a_reused_anchor_without_printing_a_warning(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock("a: &x 1\nb: &x 2\n").fields
        assert str(caught.value) == (
            "it reuses an anchor name; give each anchor its own name"
        )
        assert capsys.readouterr().err == ""

    def test_refuses_a_repeated_key(self) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock("name: a\nname: b\n").fields
        assert str(caught.value) == "it repeats a key on line 3; keep one"

    def test_refuses_yaml_that_does_not_parse_naming_only_the_line(self) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock("name: a\ndescription: [canary\n").fields
        assert str(caught.value) == "it is not valid YAML on line 4; fix it"

    @pytest.mark.parametrize(
        "frontmatter", ["name: a\ndescription: a\tb\n", "name: a\ndescription: a\t\n"]
    )
    def test_refuses_a_tab_ruamel_cannot_read_naming_the_fix(
        self, frontmatter: str
    ) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(frontmatter).fields
        assert str(caught.value) == (
            "it is not valid YAML on line 3, which holds a tab outside quotes;"
            " replace the tab with a space, or quote the value"
        )

    def test_reads_a_quoted_tab(self) -> None:
        assert FrontmatterBlock('name: a\ndescription: "a\tb"\n').fields == frozendict(
            {"name": "a", "description": "a\tb"}
        )

    def test_names_the_tag_of_a_tagged_value_holding_a_tab(self) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock('name: a\nt: !!binary "a\tb"\n').fields
        assert str(caught.value) == (
            "it uses a tag on line 3 that nustack does not read; remove the tag"
        )

    @pytest.mark.parametrize(
        ("frontmatter", "value"),
        [
            ("metadata: aGk=\n", "aGk="),
            ("metadata:\n  - aGk=\n", ("aGk=",)),
            ("triggers: {user, model}\n", frozendict({"user": None, "model": None})),
            ("t: [a: [1]]\n", (frozendict({"a": (1,)}),)),
            ("t: 2026-01-01\n", "2026-01-01"),
            ("t: x\n", "x"),
        ],
    )
    def test_reads_an_untagged_value(self, frontmatter: str, value: object) -> None:
        assert tuple(FrontmatterBlock(frontmatter).fields.values()) == (value,)

    @pytest.mark.parametrize(
        ("frontmatter", "error"),
        [
            (
                "metadata: !!binary aGk=\n",
                "it uses a tag on line 2 that nustack does not read; remove the tag",
            ),
            (
                "metadata:\n  - !!binary aGk=\n",
                "it uses a tag on line 3 that nustack does not read; remove the tag",
            ),
            (
                "triggers: !!set {user, model}\n",
                "it uses a tag on line 2 that nustack does not read; remove the tag",
            ),
            (
                "t: !!pairs [a: [1]]\n",
                "it uses a tag on line 2 that nustack does not read; remove the tag",
            ),
            (
                "t: !!omap [a: [1]]\n",
                "it uses a tag on line 2 that nustack does not read; remove the tag",
            ),
            (
                "t: !!timestamp 2026-01-01\n",
                "it uses a tag on line 2 that nustack does not read; remove the tag",
            ),
            (
                "t: !custom x\n",
                "it uses a tag on line 2 that nustack does not read; remove the tag",
            ),
        ],
    )
    def test_refuses_a_tag_outside_the_core_schema(
        self, frontmatter: str, error: str
    ) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(frontmatter).fields
        assert str(caught.value) == error

    def test_refuses_nesting_too_deep_to_read(self) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(f"name: {'[' * 5000}{']' * 5000}\n").fields
        assert str(caught.value) == "it nests too deeply to read; flatten it"

    def test_reads_a_text_key(self) -> None:
        assert FrontmatterBlock("metadata: {canary: x}\n").fields == frozendict(
            {"metadata": frozendict({"canary": "x"})}
        )

    @pytest.mark.parametrize(
        "frontmatter",
        [
            "metadata: {[canary]: x}\n",
            "metadata: {[[canary, b], [c, d]]: x}\n",
            "metadata: {{canary: b}: x}\n",
        ],
    )
    def test_refuses_a_key_that_is_not_text(self, frontmatter: str) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(frontmatter).fields
        assert str(caught.value) == (
            "it holds a key that is not text; write each key as plain text"
        )

    def test_refuses_a_control_character(self) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock("description: a\x07\n").fields
        assert str(caught.value) == (
            "it holds a character YAML cannot read; delete any control character,"
            " or fix the escape that writes one"
        )

    @pytest.mark.parametrize(
        ("value", "built"),
        [("!!str 1", "1"), ("!!bool true", True), ("!!int 1", 1), ("!!float 1.5", 1.5)],
    )
    def test_reads_a_value_its_tag_builds(self, value: str, built: object) -> None:
        assert FrontmatterBlock(f"name: {value}\n").fields == frozendict(
            {"name": built}
        )

    @pytest.mark.parametrize(
        ("value", "message"),
        [
            (
                "!!str [canary]",
                (
                    "it holds a value on line 2 that YAML cannot build as its type;"
                    " fix the value, or remove its tag or merge key"
                ),
            ),
            (
                "!!bool canary",
                (
                    "it holds a value on line 2 that YAML cannot build as its type;"
                    " fix the value, or remove its tag or merge key"
                ),
            ),
            (
                "!!int canary",
                (
                    "it holds a value on line 2 that YAML cannot build as its type;"
                    " fix the value, or remove its tag or merge key"
                ),
            ),
            (
                "!!float canary",
                (
                    "it holds a value on line 2 that YAML cannot build as its type;"
                    " fix the value, or remove its tag or merge key"
                ),
            ),
        ],
    )
    def test_refuses_a_value_its_tag_refuses(self, value: str, message: str) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(f"name: {value}\n").fields
        assert str(caught.value) == message

    @pytest.mark.parametrize(
        "frontmatter", ["name: |\n  - a\n", "description: |\n", "description: >\n"]
    )
    def test_refuses_a_block_value(self, frontmatter: str) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(frontmatter).fields
        assert str(caught.value) == (
            "line 2 opens a | or > block value; write the value on that line, after"
            " its key"
        )

    @pytest.mark.parametrize(
        ("frontmatter", "reason"),
        [
            (
                'description: "Use for\n- naming"\n',
                "line 2 wraps a value onto the next line; put it on one line",
            ),
            (
                'description: "a\nname: b"\n',
                "line 2 wraps a value onto the next line; put it on one line",
            ),
            (
                "description: 'a\nname: b'\n",
                "line 2 wraps a value onto the next line; put it on one line",
            ),
            (
                "metadata: {a: 1,\nb: 2}\n",
                "line 2 wraps a value onto the next line; put it on one line",
            ),
            (
                'triggers:\n  - "a\n  - b"\n',
                "line 3 wraps a value onto the next line; put it on one line",
            ),
            (
                "description: Use for\n  - naming\n",
                "line 2 wraps a value onto the next line; put it on one line",
            ),
        ],
    )
    def test_refuses_a_value_wrapped_onto_the_next_line(
        self, frontmatter: str, reason: str
    ) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(frontmatter).fields
        assert str(caught.value) == reason

    def test_reports_every_value_it_refuses(self) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock('name: "a\n- b"\ndescription: "c\n- d"#e\n').fields
        assert caught.value.reasons == (
            "line 2 wraps a value onto the next line; put it on one line",
            "line 4 wraps a value onto the next line; put it on one line",
            (
                "line 5 has a # right after a quote or bracket, which some hosts"
                " refuse; put a space before the #"
            ),
        )

    def test_reads_a_hash_after_a_space_or_inside_a_plain_value(self) -> None:
        assert FrontmatterBlock('name: "a" # b\ntag: c#d\n').fields == frozendict(
            {"name": "a", "tag": "c#d"}
        )

    @pytest.mark.parametrize(
        ("frontmatter", "reason"),
        [
            (
                'name: "a"# b\n',
                (
                    "line 2 has a # right after a quote or bracket, which some hosts"
                    " refuse; put a space before the #"
                ),
            ),
            (
                "name: 'a'# b\n",
                (
                    "line 2 has a # right after a quote or bracket, which some hosts"
                    " refuse; put a space before the #"
                ),
            ),
            (
                "triggers: [user]# b\n",
                (
                    "line 2 has a # right after a quote or bracket, which some hosts"
                    " refuse; put a space before the #"
                ),
            ),
            (
                "metadata: {a: b}# c\n",
                (
                    "line 2 has a # right after a quote or bracket, which some hosts"
                    " refuse; put a space before the #"
                ),
            ),
            (
                'triggers:\n  - "user"# b\n',
                (
                    "line 3 has a # right after a quote or bracket, which some hosts"
                    " refuse; put a space before the #"
                ),
            ),
        ],
    )
    def test_refuses_a_hash_right_after_a_quote_or_bracket(
        self, frontmatter: str, reason: str
    ) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(frontmatter).fields
        assert str(caught.value) == reason

    @pytest.mark.parametrize(
        "frontmatter", ["metadata: &loop [*loop]\n", "metadata: &loop\n  - *loop\n"]
    )
    @QUICK
    def test_refuses_an_alias_that_contains_itself(self, frontmatter: str) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock(frontmatter).fields
        assert str(caught.value) == (
            "it holds an alias that contains itself; remove the loop"
        )

    def test_refuses_the_first_field_it_cannot_read(self) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            _ = FrontmatterBlock("metadata: &loop [*loop]\nother: {[k]: x}\n").fields
        assert str(caught.value) == (
            "it holds an alias that contains itself; remove the loop"
        )

    @pytest.mark.parametrize(
        ("first", "level"),
        [
            ("a0: &a0 [x]\n", "a{i}: &a{i} [*a{j}, *a{j}]\n"),
            ("a0: &a0\n  - x\n", "a{i}: &a{i}\n  - *a{j}\n  - *a{j}\n"),
        ],
    )
    @QUICK
    def test_checks_each_shared_alias_once(self, first: str, level: str) -> None:
        levels = "".join(level.format(i=i, j=i - 1) for i in range(1, self.LEVELS))
        fields = FrontmatterBlock(first + levels).fields
        assert len(fields) == self.LEVELS

    def test_reads_a_long_alias_chain(self) -> None:
        chain = "".join(f"a{i}: &a{i} [*a{i - 1}]\n" for i in range(1, self.CHAIN))
        assert len(FrontmatterBlock(f"a0: &a0 []\n{chain}").fields) == self.CHAIN

    def test_reads_a_merged_alias_chain(self) -> None:
        links = (f"a{i}: &a{i} [*a{i - 1}]" for i in range(1, self.CHAIN))
        last = f"<<: {{deep: *a{self.CHAIN - 1}}}"
        frontmatter = "metadata: {" + ", ".join(["a0: &a0 []", *links, last]) + "}\n"
        metadata = FrontmatterBlock(frontmatter).fields["metadata"]
        assert isinstance(metadata, frozendict)
        assert (
            len(metadata),
            "a0" in metadata,
            "a2999" in metadata,
            "deep" in metadata,
        ) == (
            3001,
            True,
            True,
            True,
        )

    def test_hands_out_fields_that_never_change(self) -> None:
        fields = FrontmatterBlock("name: a\nmetadata: {kind: c, tags: [[b]]}\n").fields
        metadata = fields["metadata"]
        assert (type(fields), type(metadata), metadata) == (
            frozendict,
            frozendict,
            {"kind": "c", "tags": (("b",),)},
        )

    def test_freezes_a_shared_alias_once(self) -> None:
        fields = FrontmatterBlock("a: &a [b]\nc: [*a, *a]\n").fields
        shared = fields["c"]
        assert isinstance(shared, tuple)
        assert shared[0] is shared[1] is fields["a"]


class TestFrontmatterBlockOf:
    """The frontmatter every host finds, from the same lines, or none at all.

    A frontmatter that never closes is refused.
    """

    @pytest.mark.parametrize(
        ("text", "frontmatter"),
        [
            ("---\nname: a\n---\n# A\n", "name: a\n"),
            ("---\r\nname: a\r\n---\r\n# A\r\n", "name: a\r\n"),
            ("---\nname: a\n---", "name: a\n"),
            ("---\n---\n", ""),
        ],
    )
    def test_takes_the_lines_between_the_dashes(
        self, text: str, frontmatter: str
    ) -> None:
        assert FrontmatterBlock.of(text) == FrontmatterBlock(frontmatter)

    @pytest.mark.parametrize(
        "text",
        ["# A\n", "----\n\ntext\n", "--- \nname: x\n---\n", "A\n---\nname: x\n---\n"],
    )
    def test_finds_none_unless_the_first_line_is_three_dashes(self, text: str) -> None:
        assert FrontmatterBlock.of(text) is None

    @pytest.mark.parametrize(
        "text", ["---\nname: a\n", "---\r\nname: a\r\n", "---\nname: a\n--- \n"]
    )
    def test_refuses_a_block_that_never_closes(self, text: str) -> None:
        with pytest.raises(InvalidFrontmatterError) as caught:
            FrontmatterBlock.of(text)
        assert str(caught.value) == (
            "it opens with --- and never closes; end it with a --- line"
        )


class TestFrontmatterBlockBodyOf:
    """What a host shows once it strips the frontmatter."""

    def test_leaves_the_body(self) -> None:
        assert FrontmatterBlock.body_of("---\nname: a\n---\n# A\n---\n") == "# A\n---\n"


class TestFrontmatterBlockFencedOf:
    """The sync compares a frontmatter even when an edit breaks its close."""

    @pytest.mark.parametrize(
        ("text", "fenced"),
        [
            ("---\nname: a\n---\n# A\n", "---\nname: a\n---\n"),
            ("---\r\nname: a\n", "---\r\nname: a\n"),
            ("# A\n---\n", ""),
        ],
    )
    def test_keeps_the_header_a_closed_or_unclosed_fence_opens(
        self, text: str, fenced: str
    ) -> None:
        assert FrontmatterBlock.fenced_of(text) == fenced
