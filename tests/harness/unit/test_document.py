"""Reading the Markdown that skills, playbooks and the changelog are written in."""

import signal
from collections.abc import Callable
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError

from nustack.document import Document
from nustack.document import InvalidFrontmatterError
from nustack.document import Section
from nustack.document import lines_of
from nustack.problem import Problem


def write(path: Path, text: str) -> Document:
    path.write_text(text)
    return Document(path)


@contextmanager
def within(seconds: int) -> Generator[None]:
    previous = signal.signal(
        signal.SIGALRM, lambda *_: pytest.fail(f"took over {seconds} seconds")
    )
    _ = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        _ = signal.setitimer(signal.ITIMER_REAL, 0)
        _ = signal.signal(signal.SIGALRM, previous)


def test_a_document_says_why_it_cannot_be_read(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_bytes(b"\xff")
    locked = write(tmp_path / "locked.md", "# A\n")
    locked.path.chmod(0)
    assert write(tmp_path / "good.md", "# A\n").unreadable is None
    assert Document(tmp_path / "bad.md").unreadable == (
        "is not valid UTF-8; save it as UTF-8"
    )
    assert locked.unreadable == "cannot be read (Permission denied); make it readable"


def test_frontmatter_that_never_closes_is_invalid(tmp_path: Path) -> None:
    document = write(tmp_path / "a.md", "---\nname: a\n")
    with pytest.raises(InvalidFrontmatterError, match="never closes; end it with"):
        _ = document.frontmatter


def test_crlf_frontmatter_that_never_closes_is_invalid(tmp_path: Path) -> None:
    document = write(tmp_path / "a.md", "---\r\nname: a\r\n")
    with pytest.raises(InvalidFrontmatterError, match="never closes; end it with"):
        _ = document.frontmatter


def test_frontmatter_is_parsed(tmp_path: Path) -> None:
    document = write(tmp_path / "a.md", "---\nname: a\n---\n# A\n")
    assert document.frontmatter == {"name": "a"}


def test_a_document_without_frontmatter_has_none(tmp_path: Path) -> None:
    assert write(tmp_path / "a.md", "# A\n").frontmatter is None


@pytest.mark.parametrize("text", ["----\n\ntext\n", "--- \nname: x\n---\n"])
def test_a_first_line_other_than_three_dashes_opens_no_frontmatter(
    tmp_path: Path, text: str
) -> None:
    assert write(tmp_path / "a.md", text).frontmatter is None


def test_empty_frontmatter_is_an_empty_mapping(tmp_path: Path) -> None:
    assert write(tmp_path / "a.md", "---\n---\n").frontmatter == {}


def test_frontmatter_with_windows_line_endings_is_parsed(tmp_path: Path) -> None:
    document = write(tmp_path / "a.md", "---\r\nname: a\r\n---\r\n# A\r\n")
    assert document.frontmatter == {"name": "a"}


def test_frontmatter_closed_at_the_end_of_the_file_is_parsed(tmp_path: Path) -> None:
    assert write(tmp_path / "a.md", "---\nname: a\n---").frontmatter == {"name": "a"}


@pytest.mark.parametrize(
    ("header", "number"),
    [
        ("name: a---b", 2),
        ("name: a---b\ndescription: c---d", 2),
        ('name: "a\n  --- b"', 3),
        ("---x: b", 2),
        ("--- {name: a}", 2),
    ],
)
def test_dashes_anywhere_in_frontmatter_are_invalid(
    tmp_path: Path, header: str, number: int
) -> None:
    document = write(tmp_path / "a.md", f"---\n{header}\n---\n# A\n")
    with pytest.raises(
        InvalidFrontmatterError,
        match=(
            f"line {number} holds ---, which some hosts read as the end of the"
            " frontmatter; reword it"
        ),
    ):
        _ = document.frontmatter


def test_two_dashes_inside_a_value_are_parsed(tmp_path: Path) -> None:
    document = write(tmp_path / "a.md", "---\nname: a -- b\n---\n# A\n")
    assert document.frontmatter == {"name": "a -- b"}


@pytest.mark.parametrize(
    ("header", "number"),
    [
        ("%YAML 1.1\nname: a", 2),
        ("%TAG !e! tag:example.com,2000:\nname: a", 2),
        ("\ufeff%YAML 1.1\nname: a", 2),
        ("# a comment\nname: a", 2),
        ("name: a\n\ndescription: b", 3),
        ('name: "a\nb"', 3),
        ('name: "a\n  b"', 3),
        ('name: "a\n... b"', 3),
        ("name: >\n  a", 3),
        ("name: a\n...", 3),
        ("name: a\r%YAML 1.1\rdescription: b", 2),
        ("metadata:\n  a: b", 3),
        ("name:\tb", 2),
        ("name:b", 2),
        ("1a: b", 2),
        ("tags:\n\t- b", 3),
        ("tags:\n- ", 3),
    ],
)
def test_a_line_that_is_not_a_field_or_a_list_entry_is_invalid(
    tmp_path: Path, header: str, number: int
) -> None:
    document = write(tmp_path / "a.md", f"---\n{header}\n---\n# A\n")
    with pytest.raises(
        InvalidFrontmatterError,
        match=(
            f"line {number} is not a field \\(a key that starts with a letter, then"
            " a colon, and a space before any value\\) or a list entry"
        ),
    ):
        _ = document.frontmatter


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_fields_and_list_entries_are_valid(tmp_path: Path, newline: str) -> None:
    lines = ["---", "name: a", "triggers:", "  - user", "tags:", "- b", "---", ""]
    document = write(tmp_path / "a.md", newline.join(lines))
    assert document.frontmatter == {"name": "a", "triggers": ["user"], "tags": ["b"]}


@pytest.mark.parametrize("separator", ["\x85", "\u2028", "\u2029"])
def test_a_unicode_line_separator_is_invalid(tmp_path: Path, separator: str) -> None:
    text = f"---\nname: a\ndescription: A{separator}b.\n---\n"
    with pytest.raises(
        InvalidFrontmatterError,
        match="line 3 holds a Unicode line or paragraph separator, which hosts read",
    ):
        _ = write(tmp_path / "a.md", text).frontmatter


def test_a_reused_anchor_names_its_remedy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    document = write(tmp_path / "a.md", "---\na: &x 1\nb: &x 2\n---\n")
    with pytest.raises(InvalidFrontmatterError, match="reuses an anchor name; give"):
        _ = document.frontmatter
    assert capsys.readouterr().err == ""


def test_a_duplicate_frontmatter_key_names_its_remedy(tmp_path: Path) -> None:
    document = write(tmp_path / "a.md", "---\nname: a\nname: b\n---\n# A\n")
    with pytest.raises(
        InvalidFrontmatterError, match="repeats a key on line 3; keep one"
    ):
        _ = document.frontmatter


def test_frontmatter_that_is_not_yaml_names_the_line_and_never_the_value(
    tmp_path: Path,
) -> None:
    document = write(tmp_path / "a.md", "---\nname: a\ndescription: [canary\n---\n")
    with pytest.raises(InvalidFrontmatterError) as caught:
        _ = document.frontmatter
    assert str(caught.value) == "it is not valid YAML on line 4; fix it"


def test_a_yaml_error_without_a_position_names_no_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: object) -> object:
        raise MarkedYAMLError(problem="canary")

    monkeypatch.setattr(YAML, "load", refuse)
    document = write(tmp_path / "a.md", "---\nname: a\n---\n")
    with pytest.raises(InvalidFrontmatterError) as caught:
        _ = document.frontmatter
    assert str(caught.value) == "it is not valid YAML; fix it"


def test_frontmatter_nested_too_deeply_is_invalid(tmp_path: Path) -> None:
    document = write(tmp_path / "a.md", f"---\nname: {'[' * 5000}{']' * 5000}\n---\n")
    with pytest.raises(InvalidFrontmatterError) as caught:
        _ = document.frontmatter
    assert str(caught.value) == "it nests too deeply to read; flatten it"


@pytest.mark.parametrize(
    "header",
    [
        "metadata: {[canary]: x}\n",
        "metadata: {[[canary, b], [c, d]]: x}\n",
    ],
)
def test_a_key_that_is_not_text_is_invalid_without_echoing_it(
    tmp_path: Path, header: str
) -> None:
    document = write(tmp_path / "a.md", f"---\n{header}---\n")
    with pytest.raises(InvalidFrontmatterError, match="key that is not text") as caught:
        _ = document.frontmatter
    assert "canary" not in str(caught.value)


@pytest.mark.parametrize("value", ["a\x07", "2026-02-30"])
def test_a_value_yaml_cannot_read_names_its_remedy(tmp_path: Path, value: str) -> None:
    document = write(tmp_path / "a.md", f"---\ndescription: {value}\n---\n")
    with pytest.raises(
        InvalidFrontmatterError, match="a value YAML cannot read; quote"
    ):
        _ = document.frontmatter


@pytest.mark.parametrize(
    "value",
    ["!!bool canary", "!!int canary", "!!float canary", "!!int", "!!int _", "!!float"],
)
def test_a_value_its_tag_refuses_is_invalid_without_echoing_it(
    tmp_path: Path, value: str
) -> None:
    document = write(tmp_path / "a.md", f"---\nname: {value}\n---\n")
    with pytest.raises(InvalidFrontmatterError) as caught:
        _ = document.frontmatter
    assert "canary" not in str(caught.value)


def test_frontmatter_after_a_malformed_document_is_parsed(tmp_path: Path) -> None:
    with pytest.raises(InvalidFrontmatterError):
        _ = write(
            tmp_path / "bad.md", "---\nextra: [2026-02-30]\nname: a\nname: b\n---\n"
        ).frontmatter
    assert write(tmp_path / "a.md", "---\nname: a\n---\n# A\n").frontmatter == {
        "name": "a"
    }


@pytest.mark.parametrize("header", ["name: |\n  - a", "description: |", "name: >-"])
def test_a_block_value_is_invalid(tmp_path: Path, header: str) -> None:
    document = write(tmp_path / "a.md", f"---\n{header}\n---\n# A\n")
    with pytest.raises(
        InvalidFrontmatterError,
        match=(
            r"line 2 opens a \| or > block value; write the value on that line,"
            " after its key"
        ),
    ):
        _ = document.frontmatter


@pytest.mark.parametrize(
    ("header", "number"),
    [
        ('description: "Use for\n- naming"', 2),
        ('description: "a\nname: b"', 2),
        ("description: 'a\nname: b'", 2),
        ("metadata: {a: 1,\nb: 2}", 2),
        ('triggers:\n  - "a\n  - b"', 3),
        ("description: Use for\n  - naming", 2),
        ('name: "a\n- b"\ndescription: "c\n- d"', 2),
        ('triggers:\n  - "a\n  - b"\n  - "c\n  - d"', 3),
    ],
)
def test_a_value_wrapped_onto_a_line_shaped_like_a_field_is_invalid(
    tmp_path: Path, header: str, number: int
) -> None:
    document = write(tmp_path / "a.md", f"---\n{header}\n---\n# A\n")
    with pytest.raises(
        InvalidFrontmatterError,
        match=f"line {number} wraps a value onto the next line; put it on one line",
    ):
        _ = document.frontmatter


@pytest.mark.parametrize(
    ("header", "number"),
    [
        ('name: "a"# b', 2),
        ("name: 'a'# b", 2),
        ("triggers: [user]# b", 2),
        ("metadata: {a: b}# c", 2),
        ('triggers:\n  - "user"# b', 3),
    ],
)
def test_a_hash_right_after_a_quote_or_bracket_is_invalid(
    tmp_path: Path, header: str, number: int
) -> None:
    document = write(tmp_path / "a.md", f"---\n{header}\n---\n# A\n")
    with pytest.raises(
        InvalidFrontmatterError,
        match=(
            f"line {number} has a # right after a quote or bracket, which some hosts"
            " refuse; put a space before the #"
        ),
    ):
        _ = document.frontmatter


def test_a_hash_after_a_space_or_inside_a_plain_value_is_parsed(
    tmp_path: Path,
) -> None:
    document = write(tmp_path / "a.md", '---\nname: "a" # b\ntag: c#d\n---\n# A\n')
    assert document.frontmatter == {"name": "a", "tag": "c#d"}


@pytest.mark.parametrize(
    "header", ["metadata: !!binary aGk=\n", "metadata:\n  - !!binary aGk=\n"]
)
def test_binary_data_is_invalid(tmp_path: Path, header: str) -> None:
    document = write(tmp_path / "a.md", f"---\n{header}---\n")
    with pytest.raises(InvalidFrontmatterError, match="binary data; write it as text"):
        _ = document.frontmatter


@pytest.mark.parametrize(
    "header", ["metadata: &loop [*loop]\n", "metadata: &loop\n  - *loop\n"]
)
def test_an_alias_that_contains_itself_is_invalid(tmp_path: Path, header: str) -> None:
    document = write(tmp_path / "a.md", f"---\n{header}---\n")
    with (
        within(5),
        pytest.raises(InvalidFrontmatterError, match="contains itself; remove the"),
    ):
        _ = document.frontmatter


def test_shared_aliases_are_checked_once(tmp_path: Path) -> None:
    count = 40
    levels = "".join(f"a{i}: &a{i} [*a{i - 1}, *a{i - 1}]\n" for i in range(1, count))
    document = write(tmp_path / "a.md", f"---\na0: &a0 [x]\n{levels}---\n")
    with within(5):
        frontmatter = document.frontmatter
    assert isinstance(frontmatter, dict)
    assert len(frontmatter) == count


def test_shared_block_aliases_are_checked_once(tmp_path: Path) -> None:
    count = 40
    levels = "".join(
        f"a{i}: &a{i}\n  - *a{i - 1}\n  - *a{i - 1}\n" for i in range(1, count)
    )
    document = write(tmp_path / "a.md", f"---\na0: &a0\n  - x\n{levels}---\n")
    with within(5):
        frontmatter = document.frontmatter
    assert isinstance(frontmatter, dict)
    assert len(frontmatter) == count


def test_a_merged_alias_chain_is_read(tmp_path: Path) -> None:
    count = 3000
    parts = ["a0: &a0 []", *(f"a{i}: &a{i} [*a{i - 1}]" for i in range(1, count))]
    header = "metadata: {" + ", ".join([*parts, f"<<: {{deep: *a{count - 1}}}"]) + "}"
    frontmatter = write(tmp_path / "a.md", f"---\n{header}\n---\n").frontmatter
    assert frontmatter is not None
    metadata = frontmatter["metadata"]
    assert isinstance(metadata, dict)
    assert "deep" in metadata


def test_a_long_alias_chain_is_read(tmp_path: Path) -> None:
    count = 3000
    chain = "".join(f"a{i}: &a{i} [*a{i - 1}]\n" for i in range(1, count))
    frontmatter = write(tmp_path / "a.md", f"---\na0: &a0 []\n{chain}---\n").frontmatter
    assert isinstance(frontmatter, dict)
    assert len(frontmatter) == count


def test_a_list_in_place_of_fields_is_invalid(tmp_path: Path) -> None:
    document = write(tmp_path / "a.md", "---\n- a\n---\n# A\n")
    with pytest.raises(
        InvalidFrontmatterError,
        match="it is a list, not key: value fields; write each field as key: value",
    ):
        _ = document.frontmatter


def test_sections_split_at_second_level_headings_outside_code(tmp_path: Path) -> None:
    text = "# T\n\n## 1\n\nOne.\n\n```text\n## no\n```\n\n## 2\n"
    assert write(tmp_path / "a.md", text).sections == [
        Section("1", "One.\n\n```text\n## no\n```"),
        Section("2", ""),
    ]


def test_sections_keep_quoted_headings_and_indented_code(tmp_path: Path) -> None:
    text = "## 1\n\n    code\n\n> ## quoted\n\n- last\n"
    assert write(tmp_path / "a.md", text).sections == [
        Section("1", "    code\n\n> ## quoted\n\n- last")
    ]


def test_sections_break_lines_only_where_hosts_break_them(tmp_path: Path) -> None:
    text = "## 1\n\nOne\u2028## no\x85\u2029\n\n## 2\n"
    assert write(tmp_path / "a.md", text).sections == [
        Section("1", "One\u2028## no\x85\u2029"),
        Section("2", ""),
    ]


def test_targets_hold_only_relative_links_outside_code(tmp_path: Path) -> None:
    text = (
        "[b](b.md#part) [web](https://x.io) [top](#top) [mail](mailto:a@b.c)\n"
        "`[inline](inline.md)`\n\n"
        "```\n[c](c.md)\n```\n\n"
        "~~~\n[d](d.md)\n~~~\n\n"
        "1. Step\n\n   ```markdown\n   [e](e.md)\n   ```\n"
    )
    assert write(tmp_path / "a.md", text).targets == {(tmp_path / "b.md").resolve()}


def test_titled_reference_and_encoded_links_are_targets(tmp_path: Path) -> None:
    text = '[t](t.md "Title") [r][ref] [s](my%20file.md)\n\n[ref]: r.md\n'
    assert write(tmp_path / "a.md", text).targets == {
        (tmp_path / name).resolve() for name in ("t.md", "r.md", "my file.md")
    }


def test_links_with_a_scheme_or_host_are_not_targets(tmp_path: Path) -> None:
    text = "[p](//x.io/a) [t](tel:+15551234) [q](q.md?plain=1)\n"
    assert write(tmp_path / "a.md", text).targets == {(tmp_path / "q.md").resolve()}


def test_links_in_frontmatter_are_not_targets(tmp_path: Path) -> None:
    document = write(tmp_path / "a.md", "---\ndescription: '[b](b.md)'\n---\n# A\n")
    assert document.targets == frozenset()


def test_images_are_targets_and_empty_links_are_not(tmp_path: Path) -> None:
    document = write(tmp_path / "a.md", "![i](i.png) [empty]()\n")
    assert document.targets == {(tmp_path / "i.png").resolve()}


def test_a_link_to_a_missing_file_is_a_problem(tmp_path: Path) -> None:
    (problem,) = write(tmp_path / "a.md", "[b](b.md)\n").link_problems(tmp_path)
    assert "b.md" in problem.what


def test_a_link_out_of_the_root_is_a_problem(tmp_path: Path) -> None:
    (tmp_path / "outside.md").write_text("")
    (tmp_path / "root").mkdir()
    document = write(tmp_path / "root" / "a.md", "[o](../outside.md)\n")
    assert len(document.link_problems(tmp_path / "root")) == 1


def test_a_link_to_a_file_inside_the_root_is_fine(tmp_path: Path) -> None:
    (tmp_path / "b.md").write_text("")
    assert write(tmp_path / "a.md", "[b](b.md)\n").link_problems(tmp_path) == []


def test_a_malformed_link_is_a_problem(
    tmp_path: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    document = write(tmp_path / "a.md", "[n](a%00.md)\n")
    assert whats(document.link_problems(tmp_path)) == [
        "has a malformed link 'a%00.md'; write it as a full URL or a path to a file"
    ]


def test_lines_break_only_where_hosts_break_them() -> None:
    text = "a\u2028## b\x85\u2029c\r\nd\re\nf"
    assert lines_of(text) == ["a\u2028## b\x85\u2029c\r\n", "d\r", "e\n", "f"]
