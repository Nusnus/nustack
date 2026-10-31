"""The rules that span the whole plugin."""

import json
import os
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from nustack.manifest import Manifest
from nustack.plugin import Plugin
from nustack.problem import Problem

DEVIN, CLAUDE, CURSOR = Plugin.MANIFESTS


def test_the_shipped_plugin_has_no_problems(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    assert whats(Plugin(plugin_root).problems()) == []


def test_the_plugin_reads_each_manifest_once(plugin_root: Path) -> None:
    plugin = Plugin(plugin_root)
    devin, *_ = plugin.manifests
    (plugin_root / DEVIN).unlink()
    assert plugin.manifest == devin


def test_a_read_manifest_never_changes(plugin_root: Path) -> None:
    manifest = Plugin(plugin_root).manifest
    field = "version"
    with pytest.raises(ValueError, match="Instance is frozen"):
        setattr(manifest, field, "9.9.9")


def test_a_missing_manifest_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / CLAUDE).unlink()
    assert whats(Plugin(plugin_root).problems()) == [
        "is missing; add it, since its host installs the plugin from it"
    ]


def test_an_invalid_manifest_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / DEVIN).write_text('{"name": "nustack"}')
    (what,) = whats(Plugin(plugin_root).problems())
    assert what.startswith("is invalid")


def test_each_manifest_reports_its_own_problem(plugin_root: Path) -> None:
    (plugin_root / DEVIN).write_text("{}")
    (plugin_root / CLAUDE).unlink()
    problems = Plugin(plugin_root).problems()
    assert [(problem.where, problem.what[:10]) for problem in problems] == [
        (plugin_root / DEVIN, "is invalid"),
        (plugin_root / CLAUDE, "is missing"),
    ]


def test_a_peer_that_differs_is_a_problem_beside_a_broken_manifest(
    plugin_root: Path,
) -> None:
    (plugin_root / CURSOR).write_text("{}")
    manifest = json.loads((plugin_root / CLAUDE).read_text())
    manifest["description"] = "Another description."
    (plugin_root / CLAUDE).write_text(json.dumps(manifest))
    assert [problem.where for problem in Plugin(plugin_root).problems()] == [
        plugin_root / CURSOR,
        plugin_root / CLAUDE,
    ]


def test_peers_are_compared_with_each_other_when_the_devin_manifest_is_broken(
    plugin_root: Path,
) -> None:
    (plugin_root / DEVIN).write_text("{}")
    manifest = json.loads((plugin_root / CURSOR).read_text())
    (plugin_root / CURSOR).write_text(json.dumps(manifest | {"version": "9.9.9"}))
    problems = Plugin(plugin_root).problems()
    assert [problem.where for problem in problems] == [
        plugin_root / DEVIN,
        plugin_root / CURSOR,
    ]
    assert problems[1].what == (
        "differs from the Claude Code manifest in version; "
        "make it identical to the Claude Code manifest"
    )


def test_the_check_reads_each_manifest_once(
    plugin_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[Path] = []
    read = Manifest.read

    def counted(path: Path) -> Manifest:
        reads.append(path)
        return read(path)

    monkeypatch.setattr(Manifest, "read", counted)
    Plugin(plugin_root).problems()
    assert sorted(reads) == sorted(
        plugin_root / relative for relative in Plugin.MANIFESTS
    )


@pytest.mark.parametrize(
    "change",
    [
        {"homepages": "x"},
        {"homepage": "nustack"},
        {"repository": "nustack"},
        {"name": "Nustack"},
        {"version": "1.0"},
        {"version": "01.0.0"},
        {"version": "1\u0660.0.0"},
        {"description": ""},
        {"description": " "},
        {"license": ""},
        {"author": {"name": ""}},
    ],
)
def test_a_manifest_value_hosts_reject_is_a_problem(
    plugin_root: Path,
    change: dict[str, object],
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    manifest = json.loads((plugin_root / DEVIN).read_text())
    (plugin_root / DEVIN).write_text(json.dumps(manifest | change))
    (what,) = whats(Plugin(plugin_root).problems())
    assert what.startswith("is invalid")


def test_an_invalid_manifest_names_the_field_but_never_its_value(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    manifest = json.loads((plugin_root / DEVIN).read_text())
    homepage = {"homepage": "https://user:canary@exa mple.com"}
    (plugin_root / DEVIN).write_text(json.dumps(manifest | homepage))
    (what,) = whats(Plugin(plugin_root).problems())
    assert what.startswith("is invalid: homepage: ")
    assert "canary" not in what


def test_a_manifest_that_is_not_an_object_names_the_file(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / DEVIN).write_text("[]")
    (what,) = whats(Plugin(plugin_root).problems())
    assert what.startswith("is invalid: the file: ")


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"name": "Nustack"}, "name: use kebab case, such as nus-mode"),
        (
            {"version": "01.0.0"},
            "version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1",
        ),
        (
            {"version": "\u0660.\u0660.\u0661"},
            "version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1",
        ),
        ({"description": " "}, "description: fill it in; it is blank"),
    ],
)
def test_an_invalid_name_or_version_names_the_rule_to_follow(
    plugin_root: Path,
    change: dict[str, object],
    reason: str,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    manifest = json.loads((plugin_root / DEVIN).read_text())
    (plugin_root / DEVIN).write_text(json.dumps(manifest | change))
    assert whats(Plugin(plugin_root).problems()) == [f"is invalid: {reason}"]


@pytest.mark.parametrize(
    "version", ["0.0.01", "0.01.0", "0.0.1-rc", "0.0.1\u0663", "0.1\u0663.0"]
)
def test_a_version_beyond_major_minor_patch_is_invalid(
    plugin_root: Path, version: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    manifest = json.loads((plugin_root / DEVIN).read_text())
    (plugin_root / DEVIN).write_text(json.dumps(manifest | {"version": version}))
    assert whats(Plugin(plugin_root).problems()) == [
        (
            "is invalid: version: use MAJOR.MINOR.PATCH without leading zeros, "
            "such as 0.0.1"
        )
    ]


def test_every_invalid_field_is_named_in_one_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    manifest = json.loads((plugin_root / DEVIN).read_text())
    change = {"name": "Not A Name", "version": "x"}
    (plugin_root / DEVIN).write_text(json.dumps(manifest | change))
    [what] = whats(Plugin(plugin_root).problems())
    assert what.startswith("is invalid: name: ")
    assert what.endswith(
        "; version: use MAJOR.MINOR.PATCH without leading zeros, such as 0.0.1"
    )


@pytest.mark.parametrize("relative", [CLAUDE, CURSOR])
def test_a_manifest_that_differs_from_devins_is_a_problem(
    plugin_root: Path, relative: str
) -> None:
    manifest = json.loads((plugin_root / relative).read_text())
    (plugin_root / relative).write_text(json.dumps(manifest | {"version": "9.9.9"}))
    assert [
        (problem.where, problem.what) for problem in Plugin(plugin_root).problems()
    ] == [
        (
            plugin_root / relative,
            (
                "differs from the Devin manifest in version; make it identical to"
                " the Devin manifest"
            ),
        )
    ]


def test_a_missing_skills_folder_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    shutil.rmtree(plugin_root / "skills")
    assert whats(Plugin(plugin_root).problems()) == [
        "is missing; add it with the plugin's skills"
    ]


def test_a_symlinked_manifest_is_a_problem_the_check_never_reads(
    plugin_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text('{"canary": "outside"}')
    (plugin_root / CLAUDE).unlink()
    (plugin_root / CLAUDE).symlink_to(outside)
    assert [
        (problem.where, problem.what) for problem in Plugin(plugin_root).problems()
    ] == [(plugin_root / CLAUDE, Plugin.SYMLINK)]


def test_a_symlinked_skill_folder_is_a_problem_the_check_never_reads(
    plugin_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("canary")
    (outside / "inner").symlink_to(outside / "SKILL.md")
    linked = plugin_root / "skills" / "linked"
    linked.symlink_to(outside)
    assert [
        (problem.where, problem.what) for problem in Plugin(plugin_root).problems()
    ] == [(linked, Plugin.SYMLINK)]


def test_a_symlinked_plugin_is_a_problem_the_check_never_reads(
    plugin_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reads: list[Path] = []
    for read in ("read_bytes", "read_text"):
        monkeypatch.setattr(Path, read, lambda path, *_, **__: reads.append(path))
    linked = tmp_path / "linked"
    linked.symlink_to(plugin_root)
    assert [(problem.where, problem.what) for problem in Plugin(linked).problems()] == [
        (linked, Plugin.SYMLINK)
    ]
    assert reads == []


def test_a_symlinked_loader_is_one_problem(plugin_root: Path, tmp_path: Path) -> None:
    loader = plugin_root / Plugin.LOADER
    loader.rename(tmp_path / Plugin.LOADER)
    loader.symlink_to(tmp_path / Plugin.LOADER)
    assert [
        (problem.where, problem.what) for problem in Plugin(plugin_root).problems()
    ] == [(loader, Plugin.SYMLINK)]


def test_a_symlink_is_a_problem(
    plugin_root: Path,
    tmp_path: Path,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    skills = plugin_root / "skills"
    skills.rename(tmp_path / "skills")
    skills.symlink_to(tmp_path / "skills")
    assert whats(Plugin(plugin_root).problems()) == [
        (
            "is a symlink, which the check never reads through, so it stops here; "
            "put the file itself here, or close the editor whose lock file it is"
        )
    ]


def test_every_symlink_is_a_problem(plugin_root: Path, tmp_path: Path) -> None:
    links = [plugin_root / "a", plugin_root / "b"]
    for link in links:
        link.symlink_to(tmp_path)
    assert sorted(problem.where for problem in Plugin(plugin_root).problems()) == links


def test_a_symlink_stops_the_check_before_it_reads_a_file(
    plugin_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    skills = plugin_root / "skills"
    skills.rename(tmp_path / "skills")
    skills.symlink_to(tmp_path / "skills")
    monkeypatch.setattr(Path, "read_bytes", pytest.fail)
    monkeypatch.setattr(Path, "read_text", pytest.fail)
    assert Plugin(plugin_root).problems()


@pytest.mark.parametrize("mode", [0o111, 0o444])
@pytest.mark.parametrize("folder", ["", ".claude-plugin", "skills/nus-mode/playbooks"])
def test_a_folder_that_cannot_be_opened_stops_the_check(
    plugin_root: Path,
    folder: str,
    mode: int,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    unopened = plugin_root / folder
    unopened.chmod(mode)
    try:
        problems = whats(Plugin(plugin_root).problems())
    finally:
        unopened.chmod(0o755)
    assert problems == [
        (
            "cannot be opened (Permission denied); "
            "give the folder read and execute permission"
        )
    ]


def test_a_file_that_is_not_markdown_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / "skills" / "nus-mode" / "Makefile").write_text("all:\n")
    assert whats(Plugin(plugin_root).problems()) == [
        (
            "is not Markdown; remove it or move it out of the plugin, which holds "
            "only the host manifests, skills, playbooks, the OpenCode loader with "
            "its package.json, and a LICENSE"
        )
    ]


def test_folders_the_check_cannot_list_are_reported_in_path_order(
    plugin_root: Path,
) -> None:
    folders = [plugin_root / "skills" / name for name in "fedcba"]
    for folder in folders:
        folder.mkdir()
        folder.chmod(0)
    try:
        wheres = [problem.where for problem in Plugin(plugin_root).problems()]
    finally:
        for folder in folders:
            folder.chmod(0o755)
    assert wheres == sorted(folders)


def test_a_symlink_stops_the_check_before_it_reads_anything_else(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    mode = plugin_root / "skills" / "nus-mode"
    (mode / "notes.md").symlink_to(mode / "SKILL.md")
    (mode / "Makefile").write_text("all:\n")
    assert whats(Plugin(plugin_root).problems()) == [Plugin.SYMLINK]


def test_a_symlinked_skills_folder_is_never_read(
    plugin_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    (outside / "canary").mkdir(parents=True)
    (outside / "canary" / "SKILL.md").write_text("canary")
    skills = plugin_root / "skills"
    for path in sorted(skills.rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    skills.rmdir()
    skills.symlink_to(outside)
    assert [
        (problem.where, problem.what) for problem in Plugin(plugin_root).problems()
    ] == [(skills, Plugin.SYMLINK)]


def test_markdown_that_is_neither_skill_nor_playbook_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    for relative in (
        "notes.md",
        "skills/notes.md",
        "skills/principle-naming/extra.md",
        "skills/nus-mode/extra.md",
    ):
        (plugin_root / relative).write_text("# Notes\n")
    assert (
        whats(Plugin(plugin_root).problems())
        == [
            (
                "is neither a skill's SKILL.md nor a playbook; move it into the mode's"
                " playbooks folder or out of the plugin"
            )
        ]
        * 4
    )


def test_a_missing_license_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / Plugin.LICENSE).unlink()
    assert whats(Plugin(plugin_root).problems()) == [
        "is missing; copy the repository's LICENSE here"
    ]


def test_a_missing_opencode_loader_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / Plugin.LOADER).unlink()
    assert whats(Plugin(plugin_root).problems()) == [
        "is missing; restore it from the repository, so OpenCode can load the plugin"
    ]


def test_a_missing_license_is_a_problem_beside_a_missing_skills_folder(
    plugin_root: Path,
) -> None:
    (plugin_root / Plugin.LICENSE).unlink()
    shutil.rmtree(plugin_root / "skills")
    assert [problem.where for problem in Plugin(plugin_root).problems()] == [
        plugin_root / Plugin.LICENSE,
        plugin_root / "skills",
    ]


def test_markdown_that_is_not_utf_8_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / "skills" / "nus-mode" / "SKILL.md").write_bytes(b"\xff")
    assert whats(Plugin(plugin_root).problems()) == [
        "is not valid UTF-8; save it as UTF-8"
    ]


def test_an_undecodable_file_leaves_the_other_checks_running(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    playbooks = plugin_root / "skills" / "nus-mode" / "playbooks"
    (playbooks / "investigate.md").write_bytes(b"\xff")
    (playbooks / "new-project.md").write_text("[gone](gone.md)\n")
    problems = whats(Plugin(plugin_root).problems())
    assert "is not valid UTF-8; save it as UTF-8" in problems
    assert any(what.startswith("links to") for what in problems)


def test_a_mode_without_skill_md_is_reported_once(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / "skills" / "nus-mode" / "SKILL.md").unlink()
    assert (
        whats(Plugin(plugin_root).problems()).count(
            "has no SKILL.md; add one or remove the folder"
        )
        == 1
    )


def test_a_second_mode_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / "skills" / "other-mode").mkdir()
    assert (
        "holds 2 modes, where it needs exactly 1; keep one skill folder without the"
        " 'principle-' prefix"
    ) in whats(Plugin(plugin_root).problems())


def test_a_principle_the_mode_does_not_index_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    principle = plugin_root / "skills" / "principle-tests"
    principle.mkdir()
    (principle / "SKILL.md").write_text(
        "---\nname: principle-tests\ndescription: Tests.\n"
        "disable-model-invocation: true\ntriggers: [user]\n---\n# Tests\n"
    )
    (problem,) = whats(Plugin(plugin_root).problems())
    assert problem.startswith("does not index")
    assert "principle-tests" in problem


def test_a_playbook_the_mode_does_not_index_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / "skills" / "nus-mode" / "playbooks" / "extra.md").write_text(
        "# Extra\n"
    )
    (problem,) = whats(Plugin(plugin_root).problems())
    assert "extra.md" in problem


def test_a_folder_named_like_a_playbook_is_not_a_playbook(plugin_root: Path) -> None:
    (plugin_root / "skills" / "nus-mode" / "playbooks" / "extra.md").mkdir()
    assert Plugin(plugin_root).problems() == []


def test_a_broken_link_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / "skills" / "nus-mode" / "playbooks" / "new-project.md").unlink()
    assert any(
        "new-project.md" in what for what in whats(Plugin(plugin_root).problems())
    )


def test_a_manifest_with_a_duplicate_key_names_the_key(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    manifest = plugin_root / DEVIN
    manifest.write_text(manifest.read_text().replace("{", '{"name": "x",', 1))
    (what,) = whats(Plugin(plugin_root).problems())
    assert what == "is invalid: has the key 'name' more than once; keep one"


def test_a_duplicate_key_the_schema_does_not_know_is_not_echoed(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    manifest = plugin_root / DEVIN
    manifest.write_text(
        manifest.read_text().replace("{", '{"token-canary": 1, "token-canary": 2,', 1)
    )
    (what,) = whats(Plugin(plugin_root).problems())
    assert what == "is invalid: has an unknown key more than once; keep one"


def test_an_unknown_key_is_named_without_echoing_it(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    manifest = plugin_root / DEVIN
    manifest.write_text(manifest.read_text().replace("{", '{"token-canary": 1,', 1))
    (what,) = whats(Plugin(plugin_root).problems())
    assert what == (
        "is invalid: an unknown key: rename it or remove it; nustack allows only name, "
        "version, description, author, homepage, repository, license here"
    )


def test_an_unknown_nested_key_names_the_keys_its_place_allows(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    manifest = plugin_root / DEVIN
    content = json.loads(manifest.read_text())
    content["author"]["token-canary"] = 1
    manifest.write_text(json.dumps(content))
    (what,) = whats(Plugin(plugin_root).problems())
    assert what == (
        "is invalid: author.an unknown key: "
        "rename it or remove it; nustack allows only name here"
    )


@pytest.mark.parametrize(
    "content",
    [
        b'{"name": "\xff"}',
        b"[" * 99999 + b"]" * 99999,
        b'{"name": ' + b"1" * 5000 + b"}",
    ],
)
def test_a_manifest_json_cannot_read_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]], content: bytes
) -> None:
    (plugin_root / DEVIN).write_bytes(content)
    (what,) = whats(Plugin(plugin_root).problems())
    assert what.startswith("is invalid: ")


def test_a_manifest_that_cannot_be_read_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / DEVIN).chmod(0)
    (what,) = whats(Plugin(plugin_root).problems())
    assert what == "is invalid: cannot be read (Permission denied); make it readable"


def test_a_skill_whose_alias_contains_itself_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = next((plugin_root / "skills").glob("principle-*/SKILL.md"))
    path.write_text(
        path.read_text().replace("---\n", "---\nmetadata: &loop [*loop]\n", 1)
    )
    assert any(
        what.endswith("it holds an alias that contains itself; remove the loop")
        for what in whats(Plugin(plugin_root).problems())
    )


def test_a_skills_folder_that_cannot_be_read_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    skills = plugin_root / "skills"
    skills.chmod(0)
    try:
        problems = whats(Plugin(plugin_root).problems())
    finally:
        skills.chmod(0o755)
    assert problems[-1] == (
        "cannot be opened (Permission denied); "
        "give the folder read and execute permission"
    )


def test_a_loader_that_cannot_be_read_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (plugin_root / "opencode.ts").chmod(0)
    assert "cannot be read (Permission denied); make it readable" in whats(
        Plugin(plugin_root).problems()
    )


def test_an_entry_that_is_neither_a_file_nor_a_folder_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    os.mkfifo(plugin_root / "skills" / "nus-mode" / "pipe.md")
    assert whats(Plugin(plugin_root).problems()) == [
        "is neither a file nor a folder; remove it"
    ]


def test_a_skill_that_cannot_be_read_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    next((plugin_root / "skills").glob("*/SKILL.md")).chmod(0)
    assert "cannot be read (Permission denied); make it readable" in whats(
        Plugin(plugin_root).problems()
    )
