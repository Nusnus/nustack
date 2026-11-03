"""Each skill folder is one every host loads as its kind intends.

Its folder name gives its kind and its frontmatter how hosts load it, and every
break of its name, frontmatter or length is reported, none hiding another.
"""

from pathlib import Path

import pytest

from nustack.plugin.skill import Frontmatter
from nustack.plugin.skill import Kind
from nustack.plugin.skill import Skill
from nustack.problem import Problem
from nustack.tree import File
from nustack.tree import Missing
from nustack.tree import Unreadable


class TestKind:
    """A skill's folder name alone tells nus-mode how to load and index it."""

    @pytest.mark.parametrize(
        ("kind", "prefix", "section"),
        [
            (Kind.MODE, None, "Playbooks"),
            (Kind.PRINCIPLE, "principle-", "Principles"),
            (Kind.LANGUAGE, "language-", "Languages"),
        ],
    )
    def test_names_its_prefix_and_the_mode_heading_that_indexes_it(
        self, kind: Kind, prefix: str | None, section: str
    ) -> None:
        assert (kind.prefix, kind.section) == (prefix, section)

    def test_lists_the_prefixes(self) -> None:
        assert Kind.prefixes() == "'principle-' or 'language-'"

    @pytest.mark.parametrize(
        ("name", "kind"),
        [
            ("nus-mode", Kind.MODE),
            ("principle-naming", Kind.PRINCIPLE),
            ("language-python", Kind.LANGUAGE),
            ("principal-naming", Kind.MODE),
            ("old-principle-naming", Kind.MODE),
        ],
    )
    def test_of_a_folder_name_follows_its_prefix(self, name: str, kind: Kind) -> None:
        assert Kind.of(name) is kind


class TestFrontmatter:
    """The frontmatter decides how hosts load a skill, and never changes once read.

    A name at the length limit is taken, and only both fields hide the skill from
    the model.
    """

    def test_can_key_a_set_since_it_never_changes(self) -> None:
        fields = {"name": "a", "description": "A."}
        frontmatters = {
            Frontmatter.model_validate(fields),
            Frontmatter.model_validate(fields),
        }
        assert len(frontmatters) == 1

    def test_takes_a_name_at_the_length_limit(self) -> None:
        assert Frontmatter.model_validate({"name": "n" * 64, "description": "N."})

    @pytest.mark.parametrize(
        ("fields", "hidden"),
        [
            ({"disable-model-invocation": True, "triggers": ("user",)}, True),
            ({"disable-model-invocation": True, "triggers": ("user", "user")}, False),
            ({"disable-model-invocation": True}, False),
            ({"disable-model-invocation": False, "triggers": ("user",)}, False),
            ({"triggers": ("user",)}, False),
        ],
    )
    def test_hides_from_the_model_only_with_both_fields(
        self, fields: dict[str, object], *, hidden: bool
    ) -> None:
        frontmatter = Frontmatter.model_validate(
            {"name": "a", "description": "A.", **fields}
        )
        assert frontmatter.hidden_from_model is hidden

    @pytest.mark.parametrize(
        ("fields", "sets"),
        [
            ({}, False),
            ({"disable-model-invocation": False}, True),
            ({"triggers": ("user", "model")}, True),
        ],
    )
    def test_knows_whether_it_sets_how_the_skill_is_invoked(
        self, fields: dict[str, object], *, sets: bool
    ) -> None:
        frontmatter = Frontmatter.model_validate(
            {"name": "a", "description": "A.", **fields}
        )
        assert frontmatter.sets_invocation is sets


class TestSkill:
    """A skill is named for its folder, holds valid frontmatter and fits the limit.

    Every Problem it finds is reported, none hiding another.
    """

    HIDDEN = "disable-model-invocation: true\ntriggers:\n  - user\n"
    MODE = Path("/p/skills/nus-mode")
    MODE_FILE = MODE / "SKILL.md"
    KINDS = pytest.mark.parametrize("name", ["principle-naming", "language-python"])
    KIND_FILES = pytest.mark.parametrize(
        ("name", "file"),
        [
            ("principle-naming", Path("/p/skills/principle-naming/SKILL.md")),
            ("language-python", Path("/p/skills/language-python/SKILL.md")),
        ],
    )

    def test_is_named_for_its_folder(self) -> None:
        skill = Skill(Path("/p/skills/principle-naming"), Missing())
        assert (skill.name, skill.kind, skill.path) == (
            "principle-naming",
            Kind.PRINCIPLE,
            Path("/p/skills/principle-naming/SKILL.md"),
        )

    @KINDS
    def test_with_valid_frontmatter_has_no_problems(self, name: str) -> None:
        text = f"---\nname: {name}\ndescription: N.\n{self.HIDDEN}---\n# N\n"
        assert Skill(Path(f"/p/skills/{name}"), File(text.encode())).problems() == []

    @pytest.mark.parametrize(
        ("folder", "problem"),
        [
            (
                "principal-naming",
                Problem(
                    Path("/p/skills/principal-naming"),
                    "starts with a prefix close to 'principle-'; rename the folder to"
                    " start with 'principle-' if it is a principle skill",
                ),
            ),
            (
                "languge-python",
                Problem(
                    Path("/p/skills/languge-python"),
                    "starts with a prefix close to 'language-'; rename the folder to"
                    " start with 'language-' if it is a language skill",
                ),
            ),
        ],
    )
    def test_with_a_misspelled_prefix_is_a_problem(
        self, folder: str, problem: Problem
    ) -> None:
        text = f"---\nname: {folder}\ndescription: N.\n---\n# N\n"
        skill = Skill(Path("/p/skills") / folder, File(text.encode()))
        assert skill.problems() == [problem]

    def test_with_a_misspelled_prefix_and_no_skill_md_has_both_problems(self) -> None:
        assert [
            problem.what
            for problem in Skill(Path("/p/skills/principal-x"), Missing()).problems()
        ] == [
            (
                "starts with a prefix close to 'principle-'; rename the folder to start"
                " with 'principle-' if it is a principle skill"
            ),
            "has no SKILL.md; add one or remove the folder",
        ]

    def test_without_a_skill_md_is_a_problem(self) -> None:
        assert Skill(Path("/p/skills/empty"), Missing()).problems() == [
            Problem(
                Path("/p/skills/empty"),
                "has no SKILL.md; add one or remove the folder",
            )
        ]

    @pytest.mark.parametrize("read", [Unreadable("cannot be read"), File(b"\xff")])
    def test_leaves_a_skill_md_that_does_not_read_to_the_plugin(
        self, read: File | Unreadable
    ) -> None:
        assert Skill(self.MODE, read).problems() == []

    @pytest.mark.parametrize(
        "opening", ["\ufeff---\n", "---\r", "# A skill\n"], ids=["bom", "cr", "none"]
    )
    def test_that_opens_no_frontmatter_is_a_problem(self, opening: str) -> None:
        text = opening + "name: nus-mode\ndescription: N.\n---\n"
        assert Skill(self.MODE, File(text.encode())).problems() == [
            Problem(
                self.MODE_FILE,
                "has no frontmatter; open it with a line that holds only ---, and save"
                " it with no byte order mark and with LF or CRLF line endings",
            )
        ]

    @pytest.mark.parametrize(
        ("name", "what"),
        [
            (
                "Naming",
                "frontmatter is invalid: name: use kebab case, such as nus-mode",
            ),
            (
                "nam_ing",
                "frontmatter is invalid: name: use kebab case, such as nus-mode",
            ),
            (
                "na--ming",
                "frontmatter is invalid: name: use kebab case, such as nus-mode",
            ),
            (
                "naming-",
                "frontmatter is invalid: name: use kebab case, such as nus-mode",
            ),
            (
                "n" * 65,
                "frontmatter is invalid: name: shorten it to at most 64 characters",
            ),
        ],
    )
    def test_with_a_name_hosts_reject_is_a_problem(self, name: str, what: str) -> None:
        text = f"---\nname: {name}\ndescription: N.\n---\n"
        skill = Skill(self.MODE, File(text.encode()))
        assert skill.problems() == [Problem(self.MODE_FILE, what)]

    @KIND_FILES
    @pytest.mark.parametrize(
        ("text", "what"),
        [
            (
                "---\n---\n# N\n",
                ("frontmatter is invalid: name: add it; description: add it"),
            ),
            (
                "---\nname: {name}\ndescription: ''\n---\n",
                "frontmatter is invalid: description: fill it in; it is blank",
            ),
            (
                '---\nname: {name}\ndescription: "\\u200b"\n---\n',
                "frontmatter is invalid: description: fill it in; it is blank",
            ),
            (
                '---\nname: {name}\ndescription: "\\u2060"\n---\n',
                "frontmatter is invalid: description: fill it in; it is blank",
            ),
            (
                '---\nname: {name}\ndescription: "\\x85"\n---\n',
                "frontmatter is invalid: description: fill it in; it is blank",
            ),
            (
                f"---\nname: {{name}}\ndescription: {'d' * 1025}\n---\n",
                (
                    "frontmatter is invalid: description: shorten it to at most 1024"
                    " characters"
                ),
            ),
            (
                (
                    "---\nname: {name}\ndescription: N.\n"
                    "disable-model-invocation: canary\ntriggers:\n  - user\n---\n"
                ),
                (
                    "frontmatter is invalid: disable-model-invocation: make it true"
                    " or false"
                ),
            ),
            (
                (
                    "---\nname: {name}\ndescription: N.\ndisable-model-invocation: true"
                    "\ntriggers: user\n---\n"
                ),
                (
                    "frontmatter is invalid: triggers: make it a YAML list, such as"
                    " [user] or [user, model]"
                ),
            ),
            (
                (
                    "---\nname: {name}\ndescription: N.\ndisable-model-invocation: true"
                    "\ntriggers:\n  - other\n---\n"
                ),
                "frontmatter is invalid: triggers.0: set it to 'user' or 'model'",
            ),
            (
                "---\nname: {name}\ndescription: N.\ncolour: red\n---\n",
                (
                    "frontmatter is invalid: an unknown key: rename it or remove it;"
                    " nustack allows only name, description, disable-model-invocation,"
                    " triggers here"
                ),
            ),
        ],
    )
    def test_with_frontmatter_hosts_cannot_read_is_a_problem(
        self, name: str, file: Path, text: str, what: str
    ) -> None:
        skill = Skill(Path(f"/p/skills/{name}"), File(text.format(name=name).encode()))
        assert skill.problems() == [Problem(file, what)]

    def test_with_a_name_other_than_its_folder_is_a_problem(self) -> None:
        text = "---\nname: other\ndescription: N.\n---\n"
        assert Skill(self.MODE, File(text.encode())).problems() == [
            Problem(
                self.MODE_FILE,
                "name differs from its folder 'nus-mode'; use one name for both",
            )
        ]

    @pytest.mark.parametrize(
        ("name", "file", "what"),
        [
            (
                "principle-naming",
                Path("/p/skills/principle-naming/SKILL.md"),
                (
                    "a principle skill needs disable-model-invocation: true and"
                    " triggers: [user]; set both in its frontmatter"
                ),
            ),
            (
                "language-python",
                Path("/p/skills/language-python/SKILL.md"),
                (
                    "a language skill needs disable-model-invocation: true and"
                    " triggers: [user]; set both in its frontmatter"
                ),
            ),
        ],
    )
    @pytest.mark.parametrize(
        "fields",
        [
            "disable-model-invocation: true\ntriggers: [user, model]\n",
            "disable-model-invocation: true\ntriggers: []\n",
            "triggers: [user]\n",
            "",
        ],
    )
    def test_that_the_model_can_invoke_is_a_problem(
        self, name: str, file: Path, what: str, fields: str
    ) -> None:
        text = f"---\nname: {name}\ndescription: N.\n{fields}---\n"
        assert Skill(Path(f"/p/skills/{name}"), File(text.encode())).problems() == [
            Problem(file, what)
        ]

    @pytest.mark.parametrize(
        "fields",
        [
            "disable-model-invocation: true\n",
            "disable-model-invocation: false\n",
            "triggers: [user]\n",
            "triggers: [model, user]\n",
            "triggers: [user, model]\n",
        ],
    )
    def test_reports_a_mode_that_sets_how_it_is_invoked(self, fields: str) -> None:
        text = f"---\nname: nus-mode\ndescription: N.\n{fields}---\n"
        assert Skill(self.MODE, File(text.encode())).problems() == [
            Problem(
                self.MODE_FILE,
                "a mode skill leaves disable-model-invocation and triggers unset, so"
                " both keep their defaults; remove both from its frontmatter",
            )
        ]

    def test_at_the_line_limit_is_a_problem(self) -> None:
        text = "---\nname: nus-mode\ndescription: N.\n---\n" + "line\n" * 496
        assert Skill(self.MODE, File(text.encode())).problems() == [
            Problem(
                self.MODE_FILE,
                "has 500 lines, where it needs under 500; shorten it",
            )
        ]

    def test_reports_the_line_limit_beside_missing_frontmatter(self) -> None:
        text = "# Nus mode\n" + "line\n" * 499
        assert Skill(self.MODE, File(text.encode())).problems() == [
            Problem(
                self.MODE_FILE,
                "has no frontmatter; open it with a line that holds only ---, and"
                " save it with no byte order mark and with LF or CRLF line endings",
            ),
            Problem(
                self.MODE_FILE,
                "has 500 lines, where it needs under 500; shorten it",
            ),
        ]

    def test_reports_the_line_limit_beside_every_broken_frontmatter_line(
        self,
    ) -> None:
        text = "---\nname: nus-mode---\ndescription: N.---\n---\n" + "line\n" * 496
        assert Skill(self.MODE, File(text.encode())).problems() == [
            Problem(
                self.MODE_FILE,
                "frontmatter is invalid: line 2 holds ---, which some hosts read as"
                " the end of the frontmatter; reword it",
            ),
            Problem(
                self.MODE_FILE,
                "frontmatter is invalid: line 3 holds ---, which some hosts read as"
                " the end of the frontmatter; reword it",
            ),
            Problem(
                self.MODE_FILE,
                "has 500 lines, where it needs under 500; shorten it",
            ),
        ]

    @pytest.mark.parametrize("line", ["line\n", "a\u2028b\x85c\u2029d\n"])
    def test_just_under_the_line_limit_has_no_problems(self, line: str) -> None:
        text = "---\nname: nus-mode\ndescription: N.\n---\n" + line * 495
        assert Skill(self.MODE, File(text.encode())).problems() == []
