"""The manifests parse into what hosts accept, and agree on what they share.

A broken field or entry is named, and OpenCode installs the package by its name and
loads only the loader.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath
from typing import ClassVar
lazy from collections.abc import Iterator

import pytest

from nustack.plugin.manifest import ClaudeMarketplace
from nustack.plugin.manifest import CursorMarketplace
from nustack.plugin.manifest import Exports
from nustack.plugin.manifest import InvalidMetadataError
from nustack.plugin.manifest import Manifest
from nustack.plugin.manifest import Package
from nustack.plugin.manifest import Person
from tests.fixtures.repository import ModelRepository


class TestManifest:
    """Each manifest holds only what hosts accept; a disagreement names its field.

    A manifest nested too deep for the stack is refused, each field parses, and a
    manifest can key a set, since it never changes. A value hosts reject and a file
    JSON cannot read are refused. Two manifests that agree name no field, and a
    disagreement names each field.
    """

    SMALL_STACK: ClassVar[int] = 1 << 20

    @pytest.fixture
    def small_stack(self) -> Iterator[None]:
        previous = threading.stack_size(self.SMALL_STACK)
        yield
        threading.stack_size(previous)

    @pytest.mark.usefixtures("small_stack")
    def test_refuses_nesting_too_deep_for_the_stack(self) -> None:
        with (
            ThreadPoolExecutor(max_workers=1) as thread,
            pytest.raises(InvalidMetadataError) as caught,
        ):
            thread.submit(Manifest.parse, b"[" * 99999 + b"]" * 99999).result()
        assert str(caught.value) == (
            "the file: fix the JSON (recursion limit exceeded at line 1 column 202)"
        )

    def test_parses_each_field(self) -> None:
        manifest = Manifest.parse(ModelRepository.MANIFEST.encode())
        assert (manifest.name, manifest.version, manifest.author) == (
            "kit",
            "1.2.3",
            Person(name="Ada"),
        )

    def test_can_key_a_set_since_it_never_changes(self) -> None:
        content = ModelRepository.MANIFEST.encode()
        assert len({Manifest.parse(content), Manifest.parse(content)}) == 1

    @pytest.mark.parametrize(
        ("change", "reason"),
        [
            ({"name": "Kit"}, "name: use kebab case, such as nus-mode"),
            ({"name": "a--b"}, "name: use kebab case, such as nus-mode"),
            (
                {"version": "01.0.0"},
                ("version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"),
            ),
            (
                {"version": "0.0.01"},
                ("version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"),
            ),
            (
                {"version": "0.01.0"},
                ("version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"),
            ),
            (
                {"version": "0.0.1-rc"},
                ("version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"),
            ),
            (
                {"version": "1\u0660.0.0"},
                ("version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"),
            ),
            (
                {"version": "0.0.1\u0663"},
                ("version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"),
            ),
            (
                {"version": "\u0660.\u0660.\u0661"},
                ("version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"),
            ),
            ({"description": " "}, "description: fill it in; it is blank"),
            ({"description": "\ufeff"}, "description: fill it in; it is blank"),
            ({"license": ""}, "license: fill it in; it is blank"),
            ({"author": {"name": ""}}, "author.name: fill it in; it is blank"),
            (
                {"homepage": "https://user:canary@exa mple.com"},
                "homepage: use a full http or https URL, such as https://example.com",
            ),
            (
                {"repository": "https://example.com/kit"},
                (
                    "repository: give the repository's URL as"
                    " https://<host>/<owner>/<name>, with no user, password, port,"
                    " query or fragment"
                ),
            ),
            (
                {"repository": 5},
                (
                    "repository: give the repository's URL as"
                    " https://<host>/<owner>/<name>, with no user, password, port,"
                    " query or fragment"
                ),
            ),
            (
                {"name": "Not A Name", "version": "x"},
                (
                    "name: use kebab case, such as nus-mode; version: use"
                    " MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"
                ),
            ),
            (
                {"token-canary": 1},
                (
                    "an unknown key: rename it or remove it; nustack allows only name,"
                    " version, description, author, homepage, repository, license here"
                ),
            ),
            (
                {"author": {"name": "Ada", "token-canary": 1}},
                (
                    "author.an unknown key: rename it or remove it; nustack allows only"
                    " name here"
                ),
            ),
        ],
    )
    def test_refuses_a_value_hosts_reject(
        self, change: dict[str, object], reason: str
    ) -> None:
        with pytest.raises(InvalidMetadataError) as caught:
            Manifest.parse(
                json.dumps(ModelRepository.MANIFEST_FIELDS | change).encode()
            )
        assert str(caught.value) == reason

    @pytest.mark.parametrize(
        ("content", "reason"),
        [
            (b"[]", "the file: make it an object of keys and values"),
            (
                b'{"name": "\xff"}',
                (
                    "the file: fix the JSON (invalid unicode code point at line 1"
                    " column 11)"
                ),
            ),
            (
                b'{"name": ' + b"1" * 5000 + b"}",
                "the file: fix the JSON (number out of range at line 1 column 4311)",
            ),
            (
                b'{"name": "a", ' + ModelRepository.MANIFEST.encode()[1:],
                "has the key 'name' more than once in the file; keep one",
            ),
            (
                b'{"name": "a", "version": "1.2.3", '
                + ModelRepository.MANIFEST.encode()[1:],
                (
                    "has the key 'name' more than once in the file; keep one; has the"
                    " key 'version' more than once in the file; keep one"
                ),
            ),
            (
                b'{"token-canary": 1, "token-canary": 2, '
                + ModelRepository.MANIFEST.encode()[1:],
                (
                    "has an unknown key more than once in the file; keep one; an"
                    " unknown key: rename it or remove it; nustack allows only name,"
                    " version, description, author, homepage, repository, license"
                    " here"
                ),
            ),
            (
                b'{"name": "a", '
                + json.dumps(
                    ModelRepository.MANIFEST_FIELDS | {"version": "x", "license": " "}
                ).encode()[1:],
                (
                    "has the key 'name' more than once in the file; keep one; version:"
                    " use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1;"
                    " license: fill it in; it is blank"
                ),
            ),
        ],
    )
    def test_refuses_a_file_json_cannot_read(self, content: bytes, reason: str) -> None:
        with pytest.raises(InvalidMetadataError) as caught:
            Manifest.parse(content)
        assert str(caught.value) == reason

    def test_names_no_field_when_two_manifests_agree(self) -> None:
        manifest = Manifest.parse(ModelRepository.MANIFEST.encode())
        assert manifest.differing(manifest) == ()

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("name", "other"),
            ("version", "9.9.9"),
            ("description", "Other."),
            ("author", {"name": "Bo"}),
            ("homepage", "https://example.com/other"),
            ("repository", "https://example.com/nus/other"),
            ("license", "Apache-2.0"),
        ],
    )
    def test_names_each_field_two_manifests_disagree_on(
        self, field: str, value: object
    ) -> None:
        left = Manifest.parse(ModelRepository.MANIFEST.encode())
        right = Manifest.parse(
            json.dumps(ModelRepository.MANIFEST_FIELDS | {field: value}).encode()
        )
        assert left.differing(right) == (field,)


class TestMarketplace:
    """Each host finds the marketplace's description, and a broken entry is named.

    Claude's description under another field name is refused, and a key repeated in
    a nested entry is named.
    """

    def test_reads_claudes_description_at_its_top_level(self) -> None:
        marketplace = ClaudeMarketplace.parse(
            b'{"name": "kit", "description": "Kit.", "owner": {"name": "Ada"},'
            b' "plugins": []}'
        )
        assert marketplace.description == "Kit."

    def test_reads_cursors_description_under_its_metadata(self) -> None:
        marketplace = CursorMarketplace.parse(
            b'{"name": "kit", "metadata": {"description": "Kit."},'
            b' "owner": {"name": "Ada"}, "plugins": []}'
        )
        assert marketplace.description == "Kit."

    def test_refuses_another_name_for_claudes_description_field(self) -> None:
        with pytest.raises(InvalidMetadataError) as caught:
            ClaudeMarketplace.parse(
                b'{"name": "kit", "summary": "Kit.", "owner": {"name": "Ada"},'
                b' "plugins": []}'
            )
        assert str(caught.value) == (
            "description: add it; an unknown key: rename it or remove it;"
            " nustack allows only name, owner, plugins, description here"
        )

    def test_names_the_entry_that_breaks_a_rule(self) -> None:
        with pytest.raises(InvalidMetadataError) as caught:
            ClaudeMarketplace.parse(
                b'{"name": "kit", "description": "A kit.", "owner": {"name": "Ada"},'
                b' "plugins": [{"name": "kit", "source": "a", "description": "A."},'
                b' {"name": "kit", "description": "A."}]}'
            )
        assert str(caught.value) == "plugins.1.source: add it"

    def test_names_where_a_nested_key_repeats(self) -> None:
        with pytest.raises(InvalidMetadataError) as caught:
            ClaudeMarketplace.parse(
                b'{"name": "kit", "description": "A kit.", "owner": {"name": "Ada"},'
                b' "plugins": [{"name": "kit", "source": "a", "source": "b",'
                b' "description": "A kit."}]}'
            )
        assert str(caught.value) == (
            "has the key 'source' more than once in plugins.0; keep one"
        )


class TestExports:
    """OpenCode loads the file the package points it to."""

    def test_name_the_loader_file(self) -> None:
        assert PurePosixPath("opencode.ts") == Exports.LOADER


class TestPackage:
    """OpenCode installs the package by its name and loads nothing but the loader.

    A blank name is refused.
    """

    def test_refuses_a_blank_name(self) -> None:
        with pytest.raises(InvalidMetadataError) as caught:
            Package.parse(
                b'{"name": " ", "version": "1.2.3", "type": "module",'
                b' "exports": {".": "./opencode.ts"}}'
            )
        assert str(caught.value) == "name: fill it in; it is blank"

    def test_names_the_loader_as_its_one_export(self) -> None:
        with pytest.raises(InvalidMetadataError) as caught:
            Package.parse(
                b'{"name": "kit", "version": "1.2.3", "type": "module",'
                b' "exports": {".": "./other.ts"}}'
            )
        assert str(caught.value) == "exports.\".\": set it to './opencode.ts'"
