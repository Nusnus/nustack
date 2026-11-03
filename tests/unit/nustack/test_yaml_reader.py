"""YAML reads into plain data and placed values, and every refusal is the reader's."""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from nustack.yaml_reader import YamlAnchorReusedError
from nustack.yaml_reader import YamlDuplicateKeyError
from nustack.yaml_reader import YamlError
from nustack.yaml_reader import YamlInvalidError
from nustack.yaml_reader import YamlNestingError
from nustack.yaml_reader import YamlUnhashableKeyError
from nustack.yaml_reader import YamlValue
from nustack.yaml_reader import read_yaml
from nustack.yaml_reader import yaml_values


class TestReadYaml:
    """Callers get plain data or one of the reader's errors, never ruamel's types.

    An unknown tag, a value it cannot build, a reused anchor, a repeated key,
    nesting too deep or a key no mapping can hold is refused, naming lines from 0.
    """

    def test_loads_text_as_plain_data(self) -> None:
        assert read_yaml("a: [1, b]\n") == {"a": [1, "b"]}

    def test_loads_bytes_as_plain_data(self) -> None:
        assert read_yaml(b"a: 1\n") == {"a": 1}

    @pytest.mark.parametrize(
        "text", ["a: !!python/object/apply:os.getcwd []\n", "a: !foo bar\n"]
    )
    def test_refuses_a_tag_it_does_not_know(self, text: str) -> None:
        with pytest.raises(YamlInvalidError) as caught:
            read_yaml(text)
        assert caught.value.line == 0

    @pytest.mark.parametrize(
        ("text", "value"),
        [
            ("a: \n", None),
            ('a: "\\x07"\n', "\x07"),
            ("a: 2026-02-28\n", date(2026, 2, 28)),
            (
                "a: 9999-12-31T23:59:59.999999Z\n",
                datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
            ),
        ],
    )
    def test_loads_a_value_it_can_build(self, text: str, value: object) -> None:
        assert read_yaml(text) == {"a": value}

    @pytest.mark.parametrize(
        "text", ["a: \x07\n", "a: 2026-02-30\n", "a: 9999-12-31T23:59:59.9999999Z\n"]
    )
    def test_refuses_a_value_it_cannot_build(self, text: str) -> None:
        with pytest.raises(YamlError) as caught:
            read_yaml(text)
        assert type(caught.value) is YamlError

    def test_refuses_a_reused_anchor_name(self) -> None:
        with pytest.raises(YamlAnchorReusedError):
            read_yaml("a: &x 1\nb: &x 2\n")

    def test_names_the_line_of_a_repeated_key_from_0(self) -> None:
        with pytest.raises(YamlDuplicateKeyError) as caught:
            read_yaml("a: 1\na: 2\n")
        assert caught.value.line == 1

    def test_names_the_line_where_parsing_fails_from_0(self) -> None:
        with pytest.raises(YamlInvalidError) as caught:
            read_yaml("a: {b\n")
        assert caught.value.line == 1

    def test_refuses_nesting_too_deep_to_read(self) -> None:
        with pytest.raises(YamlNestingError):
            read_yaml(f"a: {'[' * 5000}{']' * 5000}\n")

    def test_refuses_a_key_no_mapping_can_hold(self) -> None:
        with pytest.raises(YamlUnhashableKeyError):
            read_yaml("a: {[[b, c], [d, e]]: f}\n")


class TestYamlValues:
    """Each value keeps where it was written, so a refusal can name its line.

    An aliased value is placed once, and empty text holds none. Text that does not
    parse is refused.
    """

    def test_places_each_scalar_and_flow_collection_in_order(self) -> None:
        assert tuple(yaml_values('a: b\nc: |\n  x\nd: [1,\n  2]\ne: "q"#\n')) == (
            YamlValue(start_line=0, end_line=0, end_index=1, block=False),
            YamlValue(start_line=0, end_line=0, end_index=4, block=False),
            YamlValue(start_line=1, end_line=1, end_index=6, block=False),
            YamlValue(start_line=1, end_line=3, end_index=14, block=True),
            YamlValue(start_line=3, end_line=3, end_index=15, block=False),
            YamlValue(start_line=3, end_line=4, end_index=25, block=False),
            YamlValue(start_line=5, end_line=5, end_index=27, block=False),
            YamlValue(start_line=5, end_line=5, end_index=32, block=False),
        )

    @pytest.mark.parametrize("style", ["|", ">"])
    def test_marks_a_block_scalar(self, style: str) -> None:
        assert tuple(yaml_values(f"a: {style}\n  x\n"))[1].block

    def test_walks_into_block_lists_and_their_mappings(self) -> None:
        assert tuple(yaml_values("a:\n  - b\n  - c: d\n")) == (
            YamlValue(start_line=0, end_line=0, end_index=1, block=False),
            YamlValue(start_line=1, end_line=1, end_index=8, block=False),
            YamlValue(start_line=2, end_line=2, end_index=14, block=False),
            YamlValue(start_line=2, end_line=2, end_index=17, block=False),
        )

    def test_places_an_aliased_value_once(self) -> None:
        assert tuple(yaml_values("a: &x [1]\nb: *x\n")) == (
            YamlValue(start_line=0, end_line=0, end_index=1, block=False),
            YamlValue(start_line=0, end_line=0, end_index=9, block=False),
            YamlValue(start_line=1, end_line=1, end_index=11, block=False),
        )

    def test_places_no_value_in_empty_text(self) -> None:
        assert tuple(yaml_values("")) == ()

    def test_refuses_text_that_does_not_parse(self) -> None:
        with pytest.raises(YamlInvalidError) as caught:
            tuple(yaml_values("a: [b\n"))
        assert caught.value.line == 1
