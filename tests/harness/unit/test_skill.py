"""The rules each skill folder follows on its own."""

from collections.abc import Callable
from pathlib import Path

import pytest

from nustack.problem import Problem
from nustack.repository import Repository
from nustack.skill import Frontmatter
from nustack.skill import Skill


def principle_with(plugin_root: Path, frontmatter: str) -> list[Problem]:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(
        f"---\nname: principle-naming\ndescription: Naming.\n{frontmatter}---\n# N\n"
    )
    return skill(plugin_root, "principle-naming").problems()


def skill(plugin_root: Path, name: str) -> Skill:
    return Skill(plugin_root / "skills" / name)


def test_frontmatter_is_frozen() -> None:
    frontmatter = Frontmatter.model_validate(
        {"name": "a", "description": "A.", "triggers": ["user"]}
    )
    field = "triggers"
    with pytest.raises(ValueError, match="Instance is frozen"):
        setattr(frontmatter, field, ("model",))
    assert type(frontmatter.triggers) is tuple


def test_every_shipped_skill_has_no_problems(repository: Repository) -> None:
    assert [
        problem for each in repository.plugin.skills for problem in each.problems()
    ] == []


def test_a_folder_without_skill_md_is_a_problem(plugin_root: Path) -> None:
    (plugin_root / "skills" / "empty").mkdir()
    (problem,) = skill(plugin_root, "empty").problems()
    assert problem.what == "has no SKILL.md; add one or remove the folder"


def test_frontmatter_that_never_closes_is_a_problem(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text("---\nname: principle-naming\n# N\n")
    (what,) = whats(skill(plugin_root, "principle-naming").problems())
    assert what.startswith("frontmatter is invalid")


def test_a_principle_with_dashes_inside_its_description_is_a_problem(
    plugin_root: Path,
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(
        path.read_text().replace("\ndescription: ", "\ndescription: Alpha---", 1)
    )
    (problem,) = skill(plugin_root, "principle-naming").problems()
    assert problem.what == (
        "frontmatter is invalid: line 3 holds ---, which some hosts read as the end"
        " of the frontmatter; reword it"
    )


def test_a_principle_framed_with_a_directive_and_a_marker_is_a_problem(
    plugin_root: Path,
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(
        "---\n%YAML 1.1\n"
        '--- {"name": "principle-naming", "description": "Naming.",'
        ' "disable-model-invocation": true, "triggers": ["user"]}\n'
        "---\n# A skill\n"
    )
    (problem,) = skill(plugin_root, "principle-naming").problems()
    assert problem.what == (
        "frontmatter is invalid: line 3 holds ---, which some hosts read as the end"
        " of the frontmatter; reword it"
    )


@pytest.mark.parametrize("separator", ["\x85", "\u2028", "\u2029"])
def test_a_unicode_line_separator_in_frontmatter_is_a_problem(
    plugin_root: Path, separator: str
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(
        path.read_text().replace("\ndescription: ", f"\ndescription: A{separator}", 1)
    )
    (problem,) = skill(plugin_root, "principle-naming").problems()
    assert problem.what == (
        "frontmatter is invalid: line 3 holds a Unicode line or paragraph"
        " separator, which hosts read differently and most editors hide; delete it"
    )


def test_a_principle_with_a_wrapped_description_is_a_problem(plugin_root: Path) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(
        "---\nname: principle-naming\n"
        'description: "Naming,\na nus-mode principle."\n'
        "disable-model-invocation: true\ntriggers:\n  - user\n---\n# A skill\n"
    )
    (problem,) = skill(plugin_root, "principle-naming").problems()
    assert problem.what == (
        "frontmatter is invalid: line 4 is not a field (a key that starts with a"
        " letter, then a colon, and a space before any value) or a list entry"
        " (spaces, then a dash and a space), the only lines nustack accepts; put"
        " each field on one line, and delete any other line"
    )


def test_a_description_wrapped_onto_a_field_shaped_line_is_a_problem(
    plugin_root: Path,
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(
        "---\nname: principle-naming\n"
        'description: "Naming,\nname: a nus-mode principle."\n'
        "disable-model-invocation: true\ntriggers:\n  - user\n---\n# A skill\n"
    )
    (problem,) = skill(plugin_root, "principle-naming").problems()
    assert problem.what == (
        "frontmatter is invalid: line 3 wraps a value onto the next line; put it on"
        " one line"
    )


def test_a_hash_right_after_a_quoted_description_is_a_problem(
    plugin_root: Path,
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(
        "---\nname: principle-naming\n"
        'description: "Naming, a nus-mode principle."# note\n'
        "disable-model-invocation: true\ntriggers:\n  - user\n---\n# A skill\n"
    )
    (problem,) = skill(plugin_root, "principle-naming").problems()
    assert problem.what == (
        "frontmatter is invalid: line 3 has a # right after a quote or bracket,"
        " which some hosts refuse; put a space before the #"
    )


def test_frontmatter_that_is_not_a_mapping_is_a_problem(plugin_root: Path) -> None:
    path = plugin_root / "skills" / "nus-mode" / "SKILL.md"
    path.write_text("---\n- a list\n---\n# Mode\n")
    (problem,) = skill(plugin_root, "nus-mode").problems()
    assert problem.what == (
        "frontmatter is invalid: it is a list, not key: value fields; write each"
        " field as key: value"
    )


@pytest.mark.parametrize(
    "opening", ["\ufeff---\n", "---\r", "# A skill\n"], ids=["bom", "cr", "none"]
)
def test_a_skill_md_that_opens_no_frontmatter_names_the_fix(
    plugin_root: Path, opening: str
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(opening + "name: principle-naming\ndescription: N.\n---\n")
    (problem,) = skill(plugin_root, "principle-naming").problems()
    assert problem.what == (
        "has no frontmatter; open it with a line that holds only ---,"
        " and save it with no byte order mark and with LF or CRLF line endings"
    )


def test_an_empty_frontmatter_names_the_missing_fields(plugin_root: Path) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text("---\n---\n# A skill\n")
    (problem,) = skill(plugin_root, "principle-naming").problems()
    assert problem.what == (
        "frontmatter is invalid: name: Field required; description: Field required"
    )


@pytest.mark.parametrize(
    "frontmatter",
    [
        "disable_model_invocation: true\ntriggers: [user]\n",
        "colour: red\n",
        "triggers: [\n",
        "description: 2026-02-30\n",
        "disable-model-invocation: 'true'\ntriggers: [user]\n",
        "disable-model-invocation: 1\ntriggers: [user]\n",
        "disable-model-invocation: true\ntriggers: !!set {user: null}\n",
        "disable-model-invocation: yes\ntriggers: [user]\n",
        "disable-model-invocation: false\ndisable-model-invocation: true\n",
        "description: " + "[" * 5000 + "]" * 5000 + "\n",
    ],
)
def test_frontmatter_hosts_cannot_read_is_a_problem(
    plugin_root: Path, frontmatter: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (what,) = whats(principle_with(plugin_root, frontmatter))
    assert what.startswith("frontmatter is invalid")


def test_triggers_that_are_not_a_list_name_the_list_to_write(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(
        path.read_text().replace("triggers:\n  - user", "triggers: user", 1)
    )
    assert any(
        what.endswith("triggers must be a YAML list, such as [user] or [user, model]")
        for what in whats(skill(plugin_root, "principle-naming").problems())
    )


def test_an_unknown_trigger_names_its_place_in_the_list(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(path.read_text().replace("  - user", "  - other", 1))
    assert (
        "frontmatter is invalid: triggers.0: Input should be 'user' or 'model'"
        in whats(skill(plugin_root, "principle-naming").problems())
    )


def test_frontmatter_of_the_wrong_type_names_the_field_and_never_the_value(
    plugin_root: Path, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (what,) = whats(principle_with(plugin_root, "disable-model-invocation: canary\n"))
    assert what.startswith("frontmatter is invalid: disable-model-invocation: ")
    assert "canary" not in what


def test_a_name_at_the_length_limit_is_fine() -> None:
    assert Frontmatter.model_validate({"name": "n" * 64, "description": "N."})


@pytest.mark.parametrize("name", ["Naming", "nam_ing", "na--ming", "naming-", "n" * 65])
def test_a_name_hosts_reject_is_a_problem(
    plugin_root: Path, name: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(f"---\nname: {name}\ndescription: Naming.\n---\n# N\n")
    (what,) = whats(skill(plugin_root, "principle-naming").problems())
    assert what.startswith("frontmatter is invalid")


@pytest.mark.parametrize(
    ("description", "rule"),
    [
        ("''", "fill it in; it is blank"),
        ("' '", "fill it in; it is blank"),
        ('"\\ufeff"', "fill it in; it is blank"),
        ("d" * 1025, "at most 1024 characters"),
    ],
)
def test_a_description_hosts_reject_is_a_problem(
    plugin_root: Path,
    description: str,
    rule: str,
    whats: Callable[[list[Problem]], list[str]],
) -> None:
    path = plugin_root / "skills" / "principle-naming" / "SKILL.md"
    path.write_text(f"---\nname: principle-naming\ndescription: {description}\n---\n")
    (what,) = whats(skill(plugin_root, "principle-naming").problems())
    assert rule in what


def test_a_name_that_differs_from_its_folder_is_a_problem(plugin_root: Path) -> None:
    path = plugin_root / "skills" / "nus-mode" / "SKILL.md"
    path.write_text(path.read_text().replace("name: nus-mode", "name: other"))
    (problem,) = skill(plugin_root, "nus-mode").problems()
    assert "differs from its folder 'nus-mode'" in problem.what
    assert "other" not in problem.what


def test_a_principle_hidden_from_the_model_is_fine(plugin_root: Path) -> None:
    hidden = "disable-model-invocation: true\ntriggers: [user]\n"
    assert principle_with(plugin_root, hidden) == []


@pytest.mark.parametrize(
    "frontmatter",
    [
        "disable-model-invocation: true\ntriggers: [user, model]\n",
        "disable-model-invocation: true\ntriggers: []\n",
        "triggers: [user]\n",
    ],
)
def test_a_principle_the_model_can_invoke_is_a_problem(
    plugin_root: Path, frontmatter: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    (what,) = whats(principle_with(plugin_root, frontmatter))
    assert what == (
        "a principle skill needs disable-model-invocation: true and triggers: [user];"
        " set both in its frontmatter"
    )


@pytest.mark.parametrize(
    "extra",
    [
        "disable-model-invocation: true\n",
        "triggers: [user]\n",
        "triggers: [model]\n",
        "triggers: [user, model, user]\n",
    ],
)
def test_a_mode_without_both_triggers_is_a_problem(
    plugin_root: Path, extra: str, whats: Callable[[list[Problem]], list[str]]
) -> None:
    path = plugin_root / "skills" / "nus-mode" / "SKILL.md"
    path.write_text(path.read_text().replace("description:", f"{extra}description:", 1))
    assert whats(skill(plugin_root, "nus-mode").problems()) == [
        (
            "a mode skill keeps disable-model-invocation and triggers at their"
            " defaults; remove both from its frontmatter"
        )
    ]


def test_a_mode_may_list_its_triggers_in_any_order(plugin_root: Path) -> None:
    path = plugin_root / "skills" / "nus-mode" / "SKILL.md"
    path.write_text(
        path.read_text().replace("---\n", "---\ntriggers: [model, user]\n", 1)
    )
    assert skill(plugin_root, "nus-mode").problems() == []


def test_a_skill_at_the_line_limit_is_a_problem(plugin_root: Path) -> None:
    path = plugin_root / "skills" / "nus-mode" / "SKILL.md"
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines + ["line"] * (500 - len(lines))))
    (problem,) = skill(plugin_root, "nus-mode").problems()
    assert problem.what == "has 500 lines, where it needs under 500; shorten it"


@pytest.mark.parametrize("line", ["line", "a\u2028b\x85c\u2029d"])
def test_a_skill_just_under_the_line_limit_is_fine(
    plugin_root: Path, line: str
) -> None:
    path = plugin_root / "skills" / "nus-mode" / "SKILL.md"
    lines = path.read_text().splitlines()
    path.write_text("\n".join(lines + [line] * (499 - len(lines))))
    assert skill(plugin_root, "nus-mode").problems() == []
