"""The rules that tie the plugin to the files released beside it."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from nustack.manifest import Manifest
from nustack.manifest import Package
from nustack.plugin import Plugin
from nustack.problem import Problem
from nustack.repository import Repository


def reads_differently(version: str) -> str:
    return (
        f"has an entry for {version} that reads differently on its own: "
        "a reference it uses is defined elsewhere in the changelog; "
        "define it inside the entry"
    )


def test_the_shipped_repository_has_no_problems(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    assert whats(repository.problems()) == []


def test_without_valid_manifests_no_version_is_compared(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (repository.plugin.root / ".claude-plugin" / "plugin.json").unlink()
    repository.changelog_path.write_text("# Changelog\n")
    assert whats(repository.problems()) == [
        "is missing; add it, since its host installs the plugin from it"
    ]


def test_the_check_reads_each_manifest_once(
    repository: Repository, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[Path] = []
    read = Manifest.read

    def counted(path: Path) -> Manifest:
        reads.append(path)
        return read(path)

    monkeypatch.setattr(Manifest, "read", counted)
    repository.problems()
    assert sorted(reads) == sorted(
        repository.plugin.root / relative for relative in Plugin.MANIFESTS
    )


def test_a_symlinked_plugin_stops_the_release_checks(
    repository: Repository, tmp_path: Path
) -> None:
    plugin = repository.plugin.root
    elsewhere = tmp_path / "elsewhere"
    plugin.rename(elsewhere)
    (elsewhere / "package.json").write_text("{}")
    plugin.symlink_to(elsewhere)
    problems = Repository(repository.root).problems()
    assert [(problem.where, problem.what) for problem in problems] == [
        (plugin, Plugin.SYMLINK)
    ]


def test_a_folder_the_check_cannot_list_stops_the_release_checks(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    plugin = repository.plugin.root
    (plugin / "package.json").write_text("{}")
    playbooks = plugin / "skills" / "nus-mode" / "playbooks"
    playbooks.chmod(0o111)
    try:
        problems = whats(Repository(repository.root).problems())
    finally:
        playbooks.chmod(0o755)
    assert problems == [
        (
            "cannot be opened (Permission denied); "
            "give the folder read and execute permission"
        )
    ]


def test_a_symlink_in_the_plugin_stops_the_release_checks(
    repository: Repository,
) -> None:
    package = repository.plugin.root / "package.json"
    outside = repository.root / "outside.json"
    package.rename(outside)
    package.symlink_to(outside)
    repository.changelog_path.write_text("# Changelog\n")
    assert [(p.where, p.what) for p in repository.problems()] == [
        (package, Plugin.SYMLINK)
    ]


def test_plugin_and_release_problems_are_reported_together(
    repository: Repository, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (repository.plugin.root / "skills" / "nus-mode" / "playbooks" / "x.md").write_text(
        "[gone](gone.md)\n"
    )
    repository.changelog_path.write_text("# Changelog\n")
    problems = whats(repository.problems())
    assert any(what.startswith("links to") for what in problems)
    assert (
        f"does not open with the entry for {version}; "
        f"add a '## [{version}] - <release date>' section above the other releases"
    ) in problems


@pytest.mark.parametrize(
    ("relative", "text"),
    [
        (".claude-plugin/marketplace.json", "{}"),
        (".cursor-plugin/marketplace.json", "{}"),
        ("pyproject.toml", "[project\n"),
        (
            "CHANGELOG.md",
            (
                "# Changelog\n\n## [0.0.0] - 2026-01-01\n\n- A.\n\n"
                "## [0.0.0] - 2026-01-01\n\n- B.\n"
            ),
        ),
        ("LICENSE", None),
    ],
)
def test_a_release_file_problem_is_reported_beside_broken_manifests(
    repository: Repository, relative: str, text: str | None
) -> None:
    for manifest in Plugin.MANIFESTS:
        (repository.plugin.root / manifest).write_text("{}")
    path = repository.root / relative
    if text is None:
        path.unlink()
    else:
        path.write_text(text)
    assert [problem.where for problem in repository.problems()] == [
        *(repository.plugin.root / manifest for manifest in Plugin.MANIFESTS),
        path,
    ]


@pytest.mark.parametrize(
    "relative",
    [
        ".claude-plugin/marketplace.json",
        ".cursor-plugin/marketplace.json",
        "CHANGELOG.md",
        "pyproject.toml",
        "LICENSE",
    ],
)
def test_a_missing_release_file_is_a_problem(
    repository: Repository, relative: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (repository.root / relative).unlink()
    (what,) = whats(repository.problems())
    assert what.startswith("is missing; add ")


@pytest.mark.parametrize(
    ("relative", "text"),
    [
        (".claude-plugin/marketplace.json", "{}"),
        (".cursor-plugin/marketplace.json", "{}"),
        ("pyproject.toml", "[project\n"),
        ("pyproject.toml", "[project]\nversion = " + "1" * 5000 + "\n"),
    ],
)
def test_an_invalid_release_file_is_a_problem(
    repository: Repository,
    relative: str,
    text: str,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    (repository.root / relative).write_text(text)
    (what,) = whats(repository.problems())
    assert what.startswith("is invalid")


@pytest.mark.parametrize(
    ("relative", "start"),
    [
        ("CHANGELOG.md", "is not valid UTF-8; save it as UTF-8"),
        ("pyproject.toml", "is invalid: it is not valid UTF-8; save it as UTF-8"),
    ],
)
def test_a_release_file_that_is_not_utf_8_is_a_problem(
    repository: Repository,
    relative: str,
    start: str,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    (repository.root / relative).write_bytes(b"\xff")
    (what,) = whats(repository.problems())
    assert what.startswith(start)


@pytest.mark.parametrize(
    "relative", ["CHANGELOG.md", "pyproject.toml", "LICENSE", "plugin/LICENSE"]
)
def test_a_release_file_that_cannot_be_read_is_a_problem(
    repository: Repository,
    relative: str,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    (repository.root / relative).chmod(0)
    (what,) = whats(repository.problems())
    assert what.endswith("cannot be read (Permission denied); make it readable")


@pytest.mark.parametrize(
    "change",
    [
        {"name": ""},
        {"description": ""},
        {"owner": {"name": ""}},
        {"plugins": [{"name": "", "source": "./plugin", "description": "D."}]},
        {"plugins": [{"name": "nustack", "source": "", "description": "D."}]},
        {"plugins": [{"name": "nustack", "source": "./plugin", "description": ""}]},
        {"name": "Not kebab case"},
        {"plugins": [{"name": "Nu Stack", "source": "./plugin", "description": "D."}]},
    ],
)
def test_a_marketplace_value_hosts_reject_is_a_problem(
    repository: Repository,
    change: dict[str, object],
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    path = repository.root / ".claude-plugin" / "marketplace.json"
    path.write_text(json.dumps(json.loads(path.read_text()) | change))
    (what,) = whats(repository.problems())
    assert what.startswith("is invalid")


def test_an_unknown_key_in_a_marketplace_entry_names_the_keys_an_entry_allows(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = repository.root / ".claude-plugin" / "marketplace.json"
    content = json.loads(path.read_text())
    content["plugins"][0]["token-canary"] = 1
    path.write_text(json.dumps(content))
    assert whats(repository.problems()) == [
        (
            "is invalid: plugins.0.an unknown key: "
            "rename it or remove it; nustack allows only name, source, description here"
        )
    ]


def test_an_unknown_key_in_cursor_metadata_names_the_keys_metadata_allows(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = repository.root / ".cursor-plugin" / "marketplace.json"
    content = json.loads(path.read_text())
    content["metadata"]["token-canary"] = 1
    path.write_text(json.dumps(content))
    assert whats(repository.problems()) == [
        (
            "is invalid: metadata.an unknown key: "
            "rename it or remove it; nustack allows only description here"
        )
    ]


def test_a_bad_field_inside_a_nested_object_is_named(
    repository: Repository,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    path = repository.root / ".cursor-plugin" / "marketplace.json"
    marketplace = json.loads(path.read_text())
    path.write_text(json.dumps(marketplace | {"metadata": {"description": ""}}))
    assert whats(repository.problems()) == [
        "is invalid: metadata.description: fill it in; it is blank"
    ]


@pytest.mark.parametrize(
    ("relative", "source"),
    [
        (".claude-plugin/marketplace.json", "./plugin"),
        (".cursor-plugin/marketplace.json", "plugin"),
    ],
)
def test_a_marketplace_that_lists_another_source_is_a_problem(
    repository: Repository, relative: str, source: str
) -> None:
    path = repository.root / relative
    path.write_text(path.read_text().replace(f'"source": "{source}"', '"source": "x"'))
    (problem,) = repository.problems()
    assert problem.where == path
    assert problem.what.startswith("lists")


@pytest.mark.parametrize("field", ["name", "description"])
def test_a_marketplace_entry_that_differs_names_fields_and_never_values(
    repository: Repository, field: str
) -> None:
    path = repository.root / ".claude-plugin" / "marketplace.json"
    marketplace = json.loads(path.read_text())
    marketplace["plugins"][0][field] = "canary-value"
    path.write_text(json.dumps(marketplace))
    (problem,) = repository.problems()
    assert problem.what == (
        f"lists the plugin with a different {field}; use the plugin "
        "manifest's name and description, and the source './plugin'"
    )


def test_a_marketplace_with_no_entries_is_a_problem(repository: Repository) -> None:
    path = repository.root / ".claude-plugin" / "marketplace.json"
    marketplace = json.loads(path.read_text())
    marketplace["plugins"] = []
    path.write_text(json.dumps(marketplace))
    (problem,) = repository.problems()
    assert problem.where == path


def test_a_marketplace_with_two_entries_is_a_problem(repository: Repository) -> None:
    path = repository.root / ".claude-plugin" / "marketplace.json"
    marketplace = json.loads(path.read_text())
    marketplace["plugins"] *= 2
    path.write_text(json.dumps(marketplace))
    assert [problem.what for problem in repository.problems()] == [
        "lists 2 plugins, where it needs exactly 1; list only this plugin"
    ]


def test_a_marketplace_source_is_checked_beside_broken_manifests(
    repository: Repository,
) -> None:
    (repository.plugin.root / ".claude-plugin" / "plugin.json").unlink()
    path = repository.root / ".claude-plugin" / "marketplace.json"
    path.write_text(path.read_text().replace('"./plugin"', '"x"'))
    assert [problem.where for problem in repository.problems()] == [
        repository.plugin.root / ".claude-plugin" / "plugin.json",
        path,
    ]


def test_a_cursor_marketplace_without_its_metadata_is_a_problem(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = repository.root / ".cursor-plugin" / "marketplace.json"
    marketplace = json.loads(path.read_text())
    del marketplace["metadata"]
    path.write_text(json.dumps(marketplace))
    (what,) = whats(repository.problems())
    assert what.startswith("is invalid")


@pytest.mark.parametrize("metadata", [{}, {"description": ""}, {"description": " "}])
def test_a_cursor_marketplace_without_a_description_is_a_problem(
    repository: Repository,
    metadata: dict[str, str],
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    path = repository.root / ".cursor-plugin" / "marketplace.json"
    path.write_text(json.dumps(json.loads(path.read_text()) | {"metadata": metadata}))
    (what,) = whats(repository.problems())
    assert what.startswith("is invalid")


@pytest.mark.parametrize(
    "text", ["# Changelog\n\n## [0.0.0] - 2026-01-01\n", "# Changelog\n"]
)
def test_a_changelog_that_does_not_open_with_the_version_is_a_problem(
    repository: Repository,
    version: str,
    text: str,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    repository.changelog_path.write_text(text)
    assert whats(repository.problems()) == [
        (
            f"does not open with the entry for {version}; "
            f"add a '## [{version}] - <release date>' section above the other releases"
        )
    ]


def test_an_unreleased_section_may_open_the_changelog(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    notes = repository.release_notes()
    text = repository.changelog_path.read_text()
    repository.changelog_path.write_text(
        text.replace("## [", "## [Unreleased]\n\n- Next.\n\n## [", 1)
    )
    fresh = Repository(repository.root)
    assert whats(fresh.problems()) == []
    assert fresh.release_notes() == notes


def test_an_unreleased_section_is_titled_exactly(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    text = repository.changelog_path.read_text()
    repository.changelog_path.write_text(
        text.replace("## [", "## [unreleased]\n\n- Next.\n\n## [", 1)
    )
    assert (
        "has an entry titled '[unreleased]'; title it '[<version>] - <YYYY-MM-DD>' "
        "with the release's version"
    ) in whats(Repository(repository.root).problems())


def test_an_unreleased_section_below_a_release_is_a_problem(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    with repository.changelog_path.open("a") as changelog:
        _ = changelog.write("\n## [Unreleased]\n\n- Next.\n")
    assert any(
        what.startswith("has an entry titled '[Unreleased]'")
        for what in whats(Repository(repository.root).problems())
    )


def test_an_older_entry_without_a_version_is_a_problem(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    text = repository.changelog_path.read_text()
    repository.changelog_path.write_text(
        text + "\n## [not-a-version] - 2026-01-01\n\n- Old.\n"
    )
    assert whats(Repository(repository.root).problems()) == [
        (
            "has an entry titled '[not-a-version] - 2026-01-01'; "
            "title it '[<version>] - <YYYY-MM-DD>' with the release's version"
        )
    ]


def test_an_older_entry_with_a_newer_version_is_a_problem(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    version = repository.plugin.manifest.version
    newer = f"{int(version.split('.')[0]) + 1}.0.0"
    repository.changelog_path.write_text(
        f"# Changelog\n\n## [{version}] - 2026-10-31\n\n- New.\n\n"
        f"## [{newer}] - 2026-01-01\n\n- Old.\n"
    )
    assert whats(Repository(repository.root).problems()) == [
        (
            f"has the entry for {version} above the one for {newer}; "
            "list releases newest first, by version"
        )
    ]


def test_an_older_entry_with_a_newer_date_is_a_problem(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    version = repository.plugin.manifest.version
    repository.changelog_path.write_text(
        f"# Changelog\n\n## [{version}] - 2026-10-31\n\n- New.\n\n"
        "## [0.0.0] - 2999-01-01\n\n- Old.\n"
    )
    assert whats(Repository(repository.root).problems()) == [
        (
            "has the entry dated 2026-10-31 above the one dated 2999-01-01; "
            "list releases newest first, by date"
        )
    ]


def test_entries_are_ordered_by_version_as_numbers(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (repository.plugin.root / ".claude-plugin" / "plugin.json").unlink()
    repository.changelog_path.write_text(
        "# Changelog\n\n## [0.0.10] - 2026-02-01\n\n- Ten.\n\n"
        "## [0.0.9] - 2026-01-01\n\n- Nine.\n"
    )
    assert whats(repository.problems()) == [
        "is missing; add it, since its host installs the plugin from it"
    ]


def test_a_huge_version_number_is_ordered_without_converting_it(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    huge = "0.0." + "9" * 5000
    text = repository.changelog_path.read_text()
    repository.changelog_path.write_text(
        text + f"\n## [{huge}] - 2026-01-01\n\n- Old.\n"
    )
    (what,) = whats(Repository(repository.root).problems())
    assert what.endswith("; list releases newest first, by version")


@pytest.mark.parametrize(
    "title",
    [
        "{version}",
        "[{version}]",
        "[{version}] - 26-01-01",
        "[{version}] - \u0662\u0660\u0662\u0666-\u0660\u0661-\u0660\u0661",
    ],
)
def test_a_changelog_entry_without_a_dated_keep_a_changelog_title_is_a_problem(
    repository: Repository,
    version: str,
    title: str,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    heading = title.format(version=version)
    repository.changelog_path.write_text(f"# Changelog\n\n## {heading}\n\n- New.\n")
    assert whats(repository.problems()) == [
        (
            f"has an entry titled {heading!r}; "
            "title it '[<version>] - <YYYY-MM-DD>' with the release's version"
        )
    ]


def test_a_changelog_entry_dated_on_no_real_day_is_a_problem(
    repository: Repository, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    heading = f"[{version}] - 2026-02-30"
    repository.changelog_path.write_text(f"# Changelog\n\n## {heading}\n\n- New.\n")
    assert whats(repository.problems()) == [
        (
            "has an entry dated 2026-02-30, which is no real day; "
            "date it with the release day"
        )
    ]


def test_a_changelog_title_with_trailing_text_is_a_problem(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    text = repository.changelog_path.read_text()
    title = next(line for line in text.splitlines() if line.startswith("## ["))
    repository.changelog_path.write_text(text.replace(title, f"{title} and more", 1))
    assert any(
        what.startswith(f"has an entry titled '{title[3:]} and more'")
        for what in whats(Repository(repository.root).problems())
    )


def test_a_version_with_two_changelog_entries_is_a_problem(
    repository: Repository, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    repository.changelog_path.write_text(
        f"# Changelog\n\n## [{version}] - 2026-01-02\n\n- New.\n\n"
        f"## [{version}] - 2026-01-01\n\n- Again.\n"
    )
    assert whats(repository.problems()) == [
        f"has more than one entry for {version}; merge them into one"
    ]


def test_an_empty_changelog_entry_is_a_problem(
    repository: Repository, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    repository.changelog_path.write_text(
        f"# Changelog\n\n## [{version}] - 2026-01-01\n\n"
        "## [0.0.0] - 2026-01-01\n\n- Old.\n"
    )
    assert whats(repository.problems()) == [
        f"has an empty entry for {version}; list what the release changes under it"
    ]


def test_an_empty_entry_is_a_problem_beside_older_references(
    repository: Repository, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    repository.changelog_path.write_text(
        f"# Changelog\n\n## [{version}] - 2026-01-01\n\n"
        "## [0.0.0] - 2026-01-01\n\n- See [o].\n\n[o]: https://x.io/o\n"
    )
    assert whats(repository.problems()) == [
        f"has an empty entry for {version}; list what the release changes under it"
    ]


def test_an_entry_that_uses_a_reference_defined_outside_it_is_a_problem(
    repository: Repository, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    repository.changelog_path.write_text(
        f"# Changelog\n\n## [{version}] - 2026-01-01\n\n- See [o].\n\n"
        "## [0.0.0] - 2026-01-01\n\n- Old.\n\n[o]: https://x.io/o\n"
    )
    assert whats(repository.problems()) == [reads_differently(version)]


def test_an_entry_whose_image_uses_an_outside_reference_is_a_problem(
    repository: Repository, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    repository.changelog_path.write_text(
        f"# Changelog\n\n## [{version}] - 2026-01-01\n\n"
        "- ![See [g](https://x.io/g)][i]\n\n"
        "## [0.0.0] - 2026-01-01\n\n- Old.\n\n[i]: https://x.io/i.png\n"
    )
    assert whats(repository.problems()) == [reads_differently(version)]


def test_an_entry_whose_own_reference_an_earlier_one_shadows_is_a_problem(
    repository: Repository, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    repository.changelog_path.write_text(
        f"# Changelog\n\n[g]: https://x.io/old\n\n## [{version}] - 2026-01-01\n\n"
        "- See [g].\n\n"
        "[g]: https://x.io/new\n"
    )
    assert whats(repository.problems()) == [reads_differently(version)]


def test_an_entry_with_its_own_titled_reference_is_fine(
    repository: Repository, version: str
) -> None:
    repository.changelog_path.write_text(
        f"# Changelog\n\n## [{version}] - 2026-01-01\n\n- See [guide][g].\n\n"
        '[g]: <https://x.io/a(b> "Guide"\n'
    )
    assert repository.problems() == []


@pytest.mark.parametrize(
    ("text", "remedy"),
    [
        ("[project\n", "; fix it"),
        (
            "[project]\nversion = " + "1" * 5000 + "\n",
            "it holds a number too long to read; shorten it",
        ),
        (
            "[project]\na = " + "[" * 5000 + "]" * 5000 + "\n",
            "it nests too deeply to read; flatten it",
        ),
    ],
)
def test_an_invalid_pyproject_names_its_remedy(
    repository: Repository,
    text: str,
    remedy: str,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    repository.pyproject_path.write_text(text)
    (what,) = whats(repository.problems())
    assert what.endswith(remedy)


def test_a_package_version_beyond_major_minor_patch_is_invalid(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = repository.plugin.root / "package.json"
    path.write_text(json.dumps(json.loads(path.read_text()) | {"version": "0.0.01"}))
    assert any(
        what.endswith(
            "version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"
        )
        for what in whats(Repository(repository.root).problems())
    )


def test_a_harness_version_that_differs_from_the_plugin_is_a_problem(
    repository: Repository, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = repository.pyproject_path
    path.write_text(
        path.read_text().replace(f'version = "{version}"', 'version = "9.9.9"')
    )
    assert whats(repository.problems()) == [
        (
            "has a version that differs from the plugin manifests; "
            "use the manifests' version"
        )
    ]


def test_a_harness_without_a_version_is_a_problem(
    repository: Repository, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = repository.pyproject_path
    path.write_text(path.read_text().replace(f'version = "{version}"\n', ""))
    assert whats(repository.problems()) == [
        "is invalid: needs a version string in its [project] table"
    ]


def test_a_missing_opencode_package_is_a_problem(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (repository.plugin.root / "package.json").unlink()
    assert whats(repository.problems()) == [
        (
            "is missing; add it with the plugin's name and version, "
            "so OpenCode can load the plugin"
        )
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"type": "commonjs"},
        {"exports": {".": "./other.ts"}},
        {"exports": {}},
        {"version": ""},
        {"extra": 1},
    ],
)
def test_an_invalid_opencode_package_is_a_problem(
    repository: Repository,
    change: dict[str, object],
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    path = repository.plugin.root / "package.json"
    path.write_text(json.dumps(json.loads(path.read_text()) | change))
    (what,) = whats(repository.problems())
    assert what.startswith("is invalid")


@pytest.mark.parametrize(
    ("exports", "reason"),
    [
        ({".": "./x.ts"}, "exports.\".\": Input should be './opencode.ts'"),
        (
            {"./token-canary": "./opencode.ts"},
            (
                'exports.".": Field required; '
                "exports.an unknown key: "
                'rename it or remove it; nustack allows only "." here'
            ),
        ),
    ],
)
def test_an_invalid_export_names_only_the_keys_the_schema_fixes(
    repository: Repository,
    exports: dict[str, str],
    reason: str,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    path = repository.plugin.root / "package.json"
    path.write_text(json.dumps(json.loads(path.read_text()) | {"exports": exports}))
    (what,) = whats(repository.problems())
    assert what == f"is invalid: {reason}"


@pytest.mark.parametrize(
    "change",
    [{"version": "9.9.9"}, {"name": "other"}, {"name": "other", "version": "9.9.9"}],
)
def test_an_opencode_package_that_differs_from_the_plugin_is_a_problem(
    repository: Repository,
    change: dict[str, str],
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    path = repository.plugin.root / "package.json"
    path.write_text(json.dumps(json.loads(path.read_text()) | change))
    fields = " and ".join(change)
    verb = "differ" if len(change) > 1 else "differs"
    assert whats(repository.problems()) == [
        (
            f"has a {fields} that {verb} from the plugin manifests; "
            f"use the manifests' {fields}"
        )
    ]


def test_the_opencode_package_cannot_be_changed_once_read(
    repository: Repository,
) -> None:
    package = Package.read(repository.plugin.root / "package.json")
    with pytest.raises(ValidationError):
        package.exports.loader = "./opencode.ts"  # ty: ignore[invalid-assignment]


def test_an_unreadable_license_names_the_file_it_cannot_read(
    repository: Repository,
) -> None:
    repository.license_path.chmod(0)
    try:
        wheres = [problem.where for problem in repository.license_problems()]
    finally:
        repository.license_path.chmod(0o644)
    assert wheres == [repository.license_path]


def test_an_unreadable_plugin_license_names_the_plugin_copy(
    repository: Repository,
) -> None:
    copy = repository.plugin.root / "LICENSE"
    copy.chmod(0)
    try:
        wheres = [problem.where for problem in repository.license_problems()]
    finally:
        copy.chmod(0o644)
    assert wheres == [copy]


def test_a_plugin_license_that_differs_is_a_problem(
    repository: Repository, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (repository.plugin.root / Plugin.LICENSE).write_text("Another license\n")
    assert whats(repository.problems()) == [
        "differs from the repository's LICENSE; copy the repository's LICENSE over it"
    ]
