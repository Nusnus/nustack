"""YAML reads into plain data and placed values, and every refusal is the reader's."""

import contextlib
import sys
import warnings

import pytest

from nustack import yaml_reader
from nustack.yaml_reader import YamlAnchorReusedError
from nustack.yaml_reader import YamlDuplicateKeyError
from nustack.yaml_reader import YamlError
from nustack.yaml_reader import YamlInvalidError
from nustack.yaml_reader import YamlNestingError
from nustack.yaml_reader import YamlNumberTooLongError
from nustack.yaml_reader import YamlTagError
from nustack.yaml_reader import YamlUnbuildableError
from nustack.yaml_reader import YamlUnhashableKeyError
from nustack.yaml_reader import YamlValue
from nustack.yaml_reader import YamlVersionError
from nustack.yaml_reader import YamlWarning
from nustack.yaml_reader import read_yaml
from nustack.yaml_reader import yaml_values
from tests.fixtures import reader_caller
from tests.fixtures.reader_caller import Caller


class TestReadYaml:
    """Callers get plain data or one of the reader's errors, never ruamel's types.

    Only the core schema's tags and merge keys are built, and an untagged value reads
    by the %YAML version, so a date reads as text. A tag outside the core schema, a
    %YAML version other than 1.1 or 1.2, a key no mapping can hold, a value YAML
    cannot build as its type, an integer too long to convert, a reused anchor, a
    repeated key, text that does not parse, nesting too deep or a character YAML
    cannot read is refused, and a refusal ruamel marks names its line, counted from 0.
    A YAML 1.1 float with no dot in its mantissa reaches the caller as the reader's
    warning, naming its line from 1 and the fix, at the line that called the reader,
    even when the text is then refused; where warnings are errors, a refusal stays the
    refusal and notes each. Any other warning passes on as the same warning, at its own
    line.
    """

    # The files a warning skips to reach the reader's caller.
    READER_FILES = frozenset({yaml_reader.__file__, contextlib.__file__})
    CALLERS = pytest.mark.parametrize(
        "caller", [Caller(read_yaml), Caller.deeper()], ids=["read_yaml", "deeper"]
    )
    MANTISSA = (
        "line 3 holds a YAML 1.1 float with no dot in its mantissa; add one, such as"
        " 1.0e3, or declare %YAML 1.2"
    )

    @pytest.mark.parametrize(
        ("text", "value"),
        [
            ("# a\n%YAML 1.1\n---\na: yes\n", True),
            ("# a\n%YAML 1.2\n---\na: yes\n", "yes"),
        ],
    )
    def test_loads_a_version_it_knows(self, text: str, value: object) -> None:
        assert read_yaml(text) == {"a": value}

    @pytest.mark.parametrize("version", ["1.3", "2.0"])
    def test_refuses_a_version_it_does_not_know(self, version: str) -> None:
        with pytest.raises(YamlVersionError) as caught:
            read_yaml(f"# a\n%YAML {version}\n---\na: yes\n")
        assert caught.value.line == 1

    def test_loads_text_as_plain_data(self) -> None:
        assert read_yaml("a: [1, b]\n") == {"a": [1, "b"]}

    @pytest.mark.parametrize(
        ("text", "value"),
        [
            ("a: !!seq []\n", {"a": []}),
            ("a: !!str bar\n", {"a": "bar"}),
            ("a: !!str aGk=\n", {"a": "aGk="}),
            ("a: !!map {b}\n", {"a": {"b": None}}),
            ("a: !!seq [b: 1, b: 2]\n", {"a": [{"b": 1}, {"b": 2}]}),
            ("a: !!seq [b: 1]\n", {"a": [{"b": 1}]}),
            ("a: !!str 2026-01-01\n", {"a": "2026-01-01"}),
            ("? [!!str aGk=]\n: 1\n", {("aGk=",): 1}),
        ],
    )
    def test_loads_a_tag_it_knows(self, text: str, value: object) -> None:
        assert read_yaml(text) == value

    def test_merges_the_mapping_a_merge_key_names(self) -> None:
        assert read_yaml("a: &x {b: 1}\nc:\n  <<: *x\n  d: 2\n") == {
            "a": {"b": 1},
            "c": {"b": 1, "d": 2},
        }

    @pytest.mark.parametrize(
        "text",
        [
            "a: !!python/object/apply:os.getcwd []\n",
            "a: !foo bar\n",
            "a: !!binary aGk=\n",
            "a: !!set {b}\n",
            "a: !!omap [b: 1, b: 2]\n",
            "a: !!pairs [b: 1]\n",
            "a: !!timestamp 2026-01-01\n",
            "? [!!binary aGk=]\n: 1\n",
        ],
    )
    def test_refuses_a_tag_outside_the_core_schema(self, text: str) -> None:
        with pytest.raises(YamlTagError) as caught:
            read_yaml(text)
        assert caught.value.line == 0

    @pytest.mark.parametrize(
        "text", ["a: {{b: c}: f}\n", "? {b: c}\n: f\n"], ids=["flow", "block"]
    )
    def test_refuses_a_mapping_as_a_key(self, text: str) -> None:
        with pytest.raises(YamlUnhashableKeyError):
            read_yaml(text)

    @pytest.mark.parametrize(
        ("text", "data"),
        [
            ("a: {[b, c]: f}\n", {"a": {("b", "c"): "f"}}),
            ("? [b, c]\n: f\n", {("b", "c"): "f"}),
        ],
        ids=["flow", "block"],
    )
    def test_loads_a_list_key_as_a_tuple(self, text: str, data: object) -> None:
        assert read_yaml(text) == data

    # CPython converts at most 4300 decimal digits of text to an int by default, and
    # any number of digits in a base that is a power of 2:
    # https://docs.python.org/3/library/stdtypes.html#int-max-str-digits
    @pytest.mark.parametrize(
        ("text", "value"),
        [
            (f"a: 1\nb: 1{'0' * 4299}\n", 10**4299),
            (f"a: 1\nb: -1{'0' * 4299}\n", -(10**4299)),
            (f"a: 1\nb: +1{'0' * 4299}\n", 10**4299),
            (f"a: 1\nb: 1{'_0' * 4299}\n", 10**4299),
            (f"%YAML 1.1\n---\na: 1\nb: 01{'0' * 4300}\n", 8**4300),
            (f"a: 1\nb: 0x1{'0' * 4300}\n", 16**4300),
            (f"%YAML 1.1\n---\na: 1\nb: 1{'0' * 4299}:30\n", 10**4299 * 60 + 30),
        ],
        ids=["plain", "negative", "positive", "grouped", "octal", "hex", "sexagesimal"],
    )
    def test_loads_an_integer_python_converts(self, text: str, value: int) -> None:
        assert read_yaml(text) == {"a": 1, "b": value}

    def test_finds_no_integer_too_long_where_python_sets_no_limit(self) -> None:
        limit = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(0)
        try:
            loaded = read_yaml(f"a: 1\nb: 1{'0' * 4300}\n")
        finally:
            sys.set_int_max_str_digits(limit)
        assert loaded == {"a": 1, "b": 10**4300}

    def test_refuses_a_long_unbuildable_integer_as_unbuildable_with_no_limit(
        self,
    ) -> None:
        limit = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(0)
        try:
            with pytest.raises(YamlUnbuildableError):
                read_yaml(f"%YAML 1.1\n---\na: !!int X1{'0' * 4300}\n")
        finally:
            sys.set_int_max_str_digits(limit)

    @pytest.mark.parametrize(
        ("text", "line"),
        [
            (f"a: 1\nb: 1{'0' * 4300}\n", 1),
            (f"a: 1\nb: -1{'0' * 4300}\n", 1),
            (f"a: 1\nb: +1{'0' * 4300}\n", 1),
            (f"a: 1\nb: 1{'_0' * 4300}\n", 1),
            (f"a: 1\nb: !!int _1{'0' * 4300}\n", 1),
            (f"a: 1\nb: !!int {'\u0661' * 5000}\n", 1),
            (f"%YAML 1.1\n---\na: 1\nb: 1{'0' * 4300}:30\n", 3),
            (f"%YAML 1.1\n---\na: 1\nb: !!int 1{'0' * 4300}:60\n", 3),
            (f"%YAML 1.1\n---\na: 1\nb: !!int 1:{'9' * 5000}\n", 3),
        ],
        ids=[
            "plain",
            "negative",
            "positive",
            "grouped",
            "underscore first",
            "Arabic-Indic digits",
            "sexagesimal",
            "sixty past the colon",
            "long past the colon",
        ],
    )
    def test_names_the_line_of_an_integer_too_long_to_convert_from_0(
        self, text: str, line: int
    ) -> None:
        with pytest.raises(YamlNumberTooLongError) as caught:
            read_yaml(text)
        assert caught.value.line == line

    def test_says_to_shorten_an_integer_too_long_to_convert(self) -> None:
        with pytest.raises(YamlNumberTooLongError) as caught:
            read_yaml(f"a: 1\nb: 1{'0' * 4300}\n")
        assert caught.value.reason(1) == (
            "it holds a number too long to read on line 2; shorten it"
        )

    @pytest.mark.parametrize(
        "text",
        [
            f"%YAML 1.1\n---\na: !!int X1{'0' * 4300}\n",
            f"%YAML 1.1\n---\na: !!int 1{'0' * 4300}x\n",
            f"%YAML 1.1\n---\na: !!int 0{'9' * 5000}\n",
            f"a: !!int {'9' * 5000}:30\n",
        ],
        ids=[
            "letter first",
            "letter last",
            "a 9 in YAML 1.1 octal",
            "a colon outside YAML 1.1",
        ],
    )
    def test_refuses_a_long_value_its_version_cannot_read_as_unbuildable(
        self, text: str
    ) -> None:
        with pytest.raises(YamlUnbuildableError):
            read_yaml(text)

    @pytest.mark.parametrize(
        ("value", "built"),
        [
            ("!!str 1", "1"),
            ("!!map {}", {}),
            ("!!seq []", []),
            ("!!int 1", 1),
            ("!!int 0x1", 1),
            ("!!int 0", 0),
            ("!!float 1.5", 1.5),
            ("!!float 0", 0.0),
            ("!!bool true", True),
            ("!!bool false", False),
        ],
    )
    def test_loads_a_value_its_tag_builds(self, value: str, built: object) -> None:
        assert read_yaml(f"a: 1\nb: {value}\n") == {"a": 1, "b": built}

    @pytest.mark.parametrize(
        "value",
        [
            "!!str [1]",
            "!!int [1]",
            "!!int {b: 1}",
            "!!map x",
            "!!seq x",
            "!!int x",
            "!!int 0x",
            "!!int",
            "!!float x",
            "!!float",
            "!!bool x",
            "!!bool",
        ],
    )
    def test_names_the_line_of_a_value_its_tag_cannot_build_from_0(
        self, value: str
    ) -> None:
        with pytest.raises(YamlUnbuildableError) as caught:
            read_yaml(f"a: 1\nb: {value}\n")
        assert caught.value.line == 1

    @pytest.mark.parametrize(
        ("text", "data"),
        [
            ("%YAML 1.1\n---\na: 1\nb: 0x_1\n", {"a": 1, "b": 1}),
            ("%YAML 1.1\n---\nb: 0b_1\n", {"b": 1}),
        ],
        ids=["hex", "binary"],
    )
    def test_loads_an_untagged_integer_with_a_digit_after_its_prefix(
        self, text: str, data: object
    ) -> None:
        assert read_yaml(text) == data

    @pytest.mark.parametrize(
        ("text", "line"),
        [("%YAML 1.1\n---\na: 1\nb: 0x_\n", 3), ("%YAML 1.1\n---\nb: 0b_\n", 2)],
        ids=["hex", "binary"],
    )
    def test_names_the_line_of_an_untagged_value_yaml_cannot_build_from_0(
        self, text: str, line: int
    ) -> None:
        with pytest.raises(YamlUnbuildableError) as caught:
            read_yaml(text)
        assert caught.value.line == line

    def test_loads_anchors_of_distinct_names_and_their_aliases(self) -> None:
        assert read_yaml("a: &x 1\nb: &y 2\nc: *x\n") == {"a": 1, "b": 2, "c": 1}

    def test_refuses_a_reused_anchor_name(self) -> None:
        with pytest.raises(YamlAnchorReusedError):
            read_yaml("a: &x 1\nb: &x 2\n")

    @CALLERS
    def test_warns_the_caller_of_a_float_with_no_dot_as_its_own(
        self, caller: Caller
    ) -> None:
        _, heard = caller.read("%YAML 1.1\n---\nx: 1e3\n")
        assert [
            (str(each.message), each.category, each.filename not in self.READER_FILES)
            for each in heard
        ] == [(self.MANTISSA, YamlWarning, True)]

    # make mutate leaves this test out, as [tool.mutmut] in pyproject.toml says.
    @pytest.mark.caller_line
    @CALLERS
    def test_names_the_line_that_called_the_reader(self, caller: Caller) -> None:
        line, heard = caller.read("%YAML 1.1\n---\nx: 1e3\n")
        assert [(each.category, each.filename, each.lineno) for each in heard] == [
            (YamlWarning, reader_caller.__file__, line)
        ]

    def test_names_in_its_warning_the_source_its_caller_gives(self) -> None:
        with pytest.warns(YamlWarning) as heard:
            read_yaml("%YAML 1.1\n---\nx: 1e3\n", "a.yaml")
        assert [str(each.message) for each in heard] == [
            (
                "line 3 of a.yaml holds a YAML 1.1 float with no dot in its mantissa;"
                " add one, such as 1.0e3, or declare %YAML 1.2"
            )
        ]

    def test_gives_the_caller_a_warning_heard_before_a_refusal(self) -> None:
        with pytest.warns(YamlWarning) as heard, pytest.raises(YamlTagError):
            read_yaml("%YAML 1.1\n---\na: 1e3\nb: !!foo x\n")
        assert [str(each.message) for each in heard] == [self.MANTISSA]

    def test_keeps_a_refusal_with_its_warnings_as_notes_where_warnings_are_errors(
        self,
    ) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with pytest.raises(YamlTagError) as caught:
                read_yaml("%YAML 1.1\n---\na: 1e3\nb: 2e3\nc: !!foo x\n")
        assert caught.value.__notes__ == [
            f"YamlWarning: {self.MANTISSA}",
            (
                "YamlWarning: line 4 holds a YAML 1.1 float with no dot in its"
                " mantissa; add one, such as 1.0e3, or declare %YAML 1.2"
            ),
        ]

    def test_passes_on_a_warning_the_yaml_does_not_earn_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No input makes ruamel warn outside its YAMLWarning, so this stands in for a
        # warning that ruamel, or Python under it, gives while it loads. Its class
        # needs two arguments, so no warning rebuilt from its text can stand in for it,
        # and is no UserWarning, the category warn gives a bare text.
        class PairWarning(RuntimeWarning):
            def __init__(self, first: str, second: str) -> None:
                super().__init__(first, second)

        given = PairWarning("not YAML's", "second")

        def load(_loader: object, _text: str) -> None:
            warnings.warn_explicit(given, PairWarning, "loader.py", 7)

        monkeypatch.setattr("nustack.yaml_reader.YAML.load", load)
        with pytest.warns(PairWarning) as heard:
            _ = read_yaml("a: 1\n")
        assert [
            (each.message is given, each.category, each.filename, each.lineno)
            for each in heard
        ] == [(True, PairWarning, "loader.py", 7)]

    def test_loads_each_distinct_key(self) -> None:
        assert read_yaml("a: 1\nb: 2\n") == {"a": 1, "b": 2}

    def test_names_the_line_of_a_repeated_key_from_0(self) -> None:
        with pytest.raises(YamlDuplicateKeyError) as caught:
            read_yaml("a: 1\na: 2\n")
        assert caught.value.line == 1

    def test_loads_a_flow_mapping_that_closes(self) -> None:
        assert read_yaml("a: {b}\n") == {"a": {"b": None}}

    def test_names_the_line_where_parsing_fails_from_0(self) -> None:
        with pytest.raises(YamlInvalidError) as caught:
            read_yaml("a: {b\n")
        assert caught.value.line == 1

    def test_names_the_line_of_a_failure_that_marks_only_its_context(self) -> None:
        with pytest.raises(YamlInvalidError) as caught:
            read_yaml("a: >\n \n\n  y\n")
        assert (caught.value.line,) == (3,)

    def test_loads_nesting_it_can_read(self) -> None:
        assert read_yaml("a: [[[b]]]\n") == {"a": [[["b"]]]}

    def test_refuses_nesting_too_deep_to_read(self) -> None:
        with pytest.raises(YamlNestingError):
            read_yaml(f"a: {'[' * 5000}{']' * 5000}\n")

    def test_refuses_a_list_of_lists_as_a_key(self) -> None:
        with pytest.raises(YamlUnhashableKeyError):
            read_yaml("a: {[[b, c], [d, e]]: f}\n")

    @pytest.mark.parametrize(
        ("text", "value"),
        [
            ("a: \n", None),
            ('a: "\\x07"\n', "\x07"),
            ("a: 2026-02-30\n", "2026-02-30"),
            ("a: 9999-12-31T23:59:59.9999999Z\n", "9999-12-31T23:59:59.9999999Z"),
            ("a: _1\n", "_1"),
            ("a: =\n", "="),
            ('a: "x\n%YAML 1.3"\n', "x %YAML 1.3"),
            ("%YAML 1.1\n---\na: _10\n", "_10"),
            ("a: >\n  x\n\n  y\n", "x\ny\n"),
            ('a: "\\U0010FFFF"\n', "\U0010ffff"),
        ],
    )
    def test_loads_a_value_it_can_build(self, text: str, value: object) -> None:
        assert read_yaml(text) == {"a": value}

    @pytest.mark.parametrize(
        "text",
        ["a: \x07\n", 'a: "\\UFFFFFFFF"\n'],
        ids=["control character", "escape past the last code point"],
    )
    def test_refuses_a_character_it_cannot_read(self, text: str) -> None:
        with pytest.raises(YamlError) as caught:
            read_yaml(text)
        assert type(caught.value) is YamlError


class TestYamlValues:
    """Each value keeps where it was written, so a refusal can name its line.

    An aliased value is placed once, and empty text holds none. Text that does not
    parse, or names a %YAML version other than 1.1 or 1.2, is refused.
    """

    def test_places_values_under_a_version_it_knows(self) -> None:
        assert tuple(yaml_values("%YAML 1.2\n---\na: 1\n")) == (
            YamlValue(start_line=2, end_line=2, end_index=15, block=False),
            YamlValue(start_line=2, end_line=2, end_index=18, block=False),
        )

    def test_refuses_a_version_it_does_not_know(self) -> None:
        with pytest.raises(YamlVersionError) as caught:
            tuple(yaml_values("%YAML 1.3\n---\na: 1\n"))
        assert caught.value.line == 0

    def test_refuses_text_that_does_not_parse(self) -> None:
        with pytest.raises(YamlInvalidError) as caught:
            tuple(yaml_values("a: [b\n"))
        assert caught.value.line == 1

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
