"""The sync's description stays factual and inert, whatever upstream's text holds.

A body that differs from the posted one only in its run link counts as unchanged,
and a template that lost or repeats an anchor, or a body too long to post, stops
the sync. A change to frontmatter alone rates as medium risk.
"""

from pathlib import Path

import pytest

from nustack.problem import Problem
from nustack.record import CopyRecord
from nustack.sha import Sha
from nustack.sync.change import Blob
from nustack.sync.change import FileChange
from nustack.sync.description import Badge
from nustack.sync.description import Colour
from nustack.sync.description import SyncDescription
from nustack.sync.description import SyncLinks
from nustack.sync.description import SyncTemplate
from nustack.sync.description import code
from nustack.sync.description import listing
from nustack.sync.history import Commit
from nustack.sync.history import History
from nustack.sync.tree import Mode
from tests.fixtures.sync.description import Passage


class TestSyncDescription:
    """A reviewer gets each fact approval needs, and nothing upstream can inject.

    A base whose record names no commit upstream's head holds states no range, one
    whose record names the copied commit says the copy drifted, and a change to
    frontmatter alone rates as medium risk. A body that differs
    only in its run link is not posted again.
    """

    LINKS = SyncLinks("https://run", "https://checks")
    RECORD = CopyRecord(
        upstream="https://github.com/mattpocock/skills",
        source="src",
        folder="dst",
        skills=("s",),
        commit=None,
        files=frozendict(),
    )
    TIP = Sha("4ae2317ddb22b046e26455e4f9c9b3aaaf62212d")
    COMPARE = (
        "[Compare upstream from aaaaaaa, the commit the base's record names, to"
        " 4ae2317](https://github.com/mattpocock/skills/compare/"
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa...4ae2317ddb22b046e26455e4f9c9b3aaaf62212d)"
    )
    LOADING = (
        "A field that decides when a skill loads changed or was not compared; the"
        " files list names each file"
    )
    TERMS = "A license, frontmatter or policy file changed; the files list names each"

    @pytest.mark.parametrize(
        ("folder", "purpose", "scope"),
        [
            (
                "plugin/skills",
                "ships in nustack's plugin to every user",
                "instructions beyond what each skill's description says it covers",
            ),
            (
                ".agents/skills",
                "steers how agents work on nustack",
                "instructions beyond wording",
            ),
            (
                "plugins",
                "steers how agents work on nustack",
                "instructions beyond wording",
            ),
        ],
    )
    def test_says_what_the_copy_does_and_what_review_reads_for_by_where_it_lives(
        self, folder: str, purpose: str, scope: str
    ) -> None:
        record = CopyRecord(**(self.RECORD.model_dump() | {"folder": folder}))
        description = SyncDescription(
            self.LINKS, record, History(self.TIP, None, ()), (), ()
        )
        assert (description.purpose, description.scope) == (purpose, scope)

    def test_states_no_range_for_an_unknown_commit_and_reports_license_and_frontmatter(
        self,
    ) -> None:
        changes = (
            FileChange("s/LICENSE", None, Blob(b"MIT\n", Mode.REGULAR)),
            FileChange(
                "s/SKILL.md", Blob(b"x", Mode.REGULAR), Blob(b"\xff", Mode.REGULAR)
            ),
            FileChange("s/old.md", Blob(b"[x](https://x)", Mode.REGULAR), None),
        )
        description = SyncDescription(
            self.LINKS, self.RECORD, History(self.TIP, None, ()), changes, ()
        )
        assert description.checks == (
            "- [Copy](https://run): passed, 1 added, 1 changed and 1 removed against"
            " upstream's head, modes and LICENSE included" + Passage.CI
        )
        assert description.terms == (
            "Terms and loading:\n\n- LICENSE: ` s/LICENSE ` added\n- SKILL.md"
            " frontmatter: ` s/SKILL.md ` not compared (a side contains NUL or is not"
            " UTF-8)\n- agents/ policy files: unchanged"
        )
        assert description.changed == (
            "- 1 added, 1 changed and 1 removed against upstream's head\n"
            f"- {self.LOADING}\n- " + Passage.UNKNOWN_COMMIT
        )
        assert description.evidence.split("\n\n", 2)[2] == (
            Passage.NO_COMMITS + "Changed files under the copy (3):\n\n"
            "- ` s/LICENSE `: added, +1/-0 lines\n"
            "- ` s/SKILL.md `: changed, a side contains NUL or is not UTF-8; inspect"
            " the file itself\n"
            "- ` s/old.md `: removed, +0/-1 lines" + Passage.EMPTY_SCANS + Passage.NOTES
        )

    def test_rates_a_frontmatter_change_alone_as_medium_risk(self) -> None:
        change = FileChange(
            "s/SKILL.md",
            Blob(b"---\nname: x\n---\n", Mode.REGULAR),
            Blob(b"---\nname: y\n---\n", Mode.REGULAR),
        )
        description = SyncDescription(
            self.LINKS, self.RECORD, History(self.TIP, None, ()), (change,), ()
        )
        assert description.terms.splitlines()[3] == (
            "- SKILL.md frontmatter: ` s/SKILL.md ` changed"
        )
        assert description.changed.splitlines()[1] == f"- {self.TERMS}"
        assert description.badges == (
            "![Risk: medium](https://img.shields.io/badge/risk-medium-9a6700"
            "?style=flat-square) ![Checks: 1 passed, CI pending]"
            "(https://img.shields.io/badge/checks-1%20passed%2C%20CI%20pending-9a6700"
            "?style=flat-square) ![Size: 1 file](https://img.shields.io/badge/size-1"
            "%20file-6e7781?style=flat-square)"
        )

    def test_rates_a_changed_description_as_high_risk(self) -> None:
        change = FileChange(
            "s/SKILL.md",
            Blob(b"---\nname: x\ndescription: Old.\n---\n", Mode.REGULAR),
            Blob(b"---\nname: x\ndescription: New.\n---\n", Mode.REGULAR),
        )
        description = SyncDescription(
            self.LINKS, self.RECORD, History(self.TIP, None, ()), (change,), ()
        )
        assert description.changed.splitlines()[1] == f"- {self.LOADING}"
        assert description.badges.startswith(
            "![Risk: high](https://img.shields.io/badge/risk-high-cf222e"
            "?style=flat-square) "
        )

    def test_flags_a_loading_change_in_a_policy_file(self) -> None:
        changes = (
            FileChange(
                "s/agents/openai.yaml",
                Blob(b"policy:\n  allow_implicit_invocation: false\n", Mode.REGULAR),
                None,
            ),
            FileChange("s/agents/x.yaml", None, Blob(b"name: x\n", Mode.REGULAR)),
            FileChange("s/agents/y.yaml", None, Blob(b"\xff", Mode.REGULAR)),
        )
        description = SyncDescription(
            self.LINKS, self.RECORD, History(self.TIP, None, ()), changes, ()
        )
        assert description.terms.splitlines()[4] == (
            "- agents/ policy files: ` s/agents/openai.yaml ` removed, and a loading"
            " field changed; ` s/agents/x.yaml ` added; ` s/agents/y.yaml ` added,"
            " not compared (a side contains NUL or is not UTF-8)"
        )
        assert description.changed.splitlines()[1] == f"- {self.LOADING}"
        assert description.badges.startswith("![Risk: high]")

    def test_flags_an_uncompared_policy_file_alone(self) -> None:
        changes = (FileChange("s/agents/y.yaml", None, Blob(b"\0", Mode.REGULAR)),)
        description = SyncDescription(
            self.LINKS, self.RECORD, History(self.TIP, None, ()), changes, ()
        )
        assert description.changed.splitlines()[1] == f"- {self.LOADING}"

    def test_flags_nothing_for_a_license_or_a_file_outside_policy_and_the_skill(
        self,
    ) -> None:
        changes = (
            FileChange("s/tool.bin", None, Blob(b"\0", Mode.REGULAR)),
            FileChange("s/a/SKILL.md", None, Blob(b"x", Mode.REGULAR)),
        )
        description = SyncDescription(
            self.LINKS, self.RECORD, History(self.TIP, None, ()), changes, ()
        )
        assert description.changed.splitlines()[1] == (
            "- License, frontmatter and policy files are unchanged"
        )
        assert description.badges.startswith("![Risk: medium]")
        licensed = SyncDescription(
            self.LINKS,
            self.RECORD,
            History(self.TIP, None, ()),
            (FileChange("s/LICENSE", Blob(b"MIT\n", Mode.REGULAR), None),),
            (),
        )
        assert licensed.changed.splitlines()[1] == f"- {self.TERMS}"
        assert licensed.badges.startswith("![Risk: medium]")

    @pytest.mark.parametrize(
        ("commits", "summary"),
        [
            ((), Passage.NO_COMMITS.rstrip("\n")),
            (
                (Commit(Sha("b" * 40), "one"), Commit(Sha("c" * 40), "two")),
                (
                    "Upstream commits touching the skills or repository LICENSE"
                    " (2):\n\n- [`bbbbbbb`]"
                    "(https://github.com/mattpocock/skills/commit/"
                    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb)"
                    " ` one `\n- [`ccccccc`]"
                    "(https://github.com/mattpocock/skills/commit/"
                    "cccccccccccccccccccccccccccccccccccccccc)"
                    " ` two `"
                ),
            ),
        ],
    )
    def test_counts_the_upstream_commits_since_the_base(
        self, commits: tuple[Commit, ...], summary: str
    ) -> None:
        description = SyncDescription(
            self.LINKS, self.RECORD, History(self.TIP, Sha("a" * 40), commits), (), ()
        )
        assert description.provenance == self.COMPARE
        assert description.evidence.split("\n\nChanged files")[0] == (
            Passage.TERMS + summary
        )

    def test_says_a_copy_drifted_when_upstream_changed_nothing_since_the_base(
        self,
    ) -> None:
        description = SyncDescription(
            self.LINKS,
            self.RECORD,
            History(self.TIP, self.TIP, ()),
            (
                FileChange(
                    "s/tool", Blob(b"", Mode.REGULAR), Blob(b"", Mode.EXECUTABLE)
                ),
            ),
            (),
        )
        assert description.provenance == (
            "Upstream changed nothing the copy holds since 4ae2317, the commit the"
            " base's record names, so this restores each file to the blob the record"
            " names and its mode to upstream's"
        )

    @pytest.mark.parametrize(
        ("before", "after", "files"),
        [
            (
                Blob(b"", Mode.REGULAR),
                Blob(b"", Mode.EXECUTABLE),
                "- ` s/tool `: changed, +0/-0 lines, mode 100644 to 100755",
            ),
            (
                None,
                Blob(b"", Mode.EXECUTABLE),
                "- ` s/tool `: added, +0/-0 lines, mode 100755",
            ),
            (None, Blob(b"", Mode.REGULAR), "- ` s/tool `: added, +0/-0 lines"),
            (
                Blob(b"a\n", Mode.EXECUTABLE),
                Blob(b"b\n", Mode.EXECUTABLE),
                "- ` s/tool `: changed, +1/-1 lines",
            ),
            (Blob(b"", Mode.EXECUTABLE), None, "- ` s/tool `: removed, +0/-0 lines"),
            (
                Blob(b"", Mode.EXECUTABLE),
                Blob(b"", Mode.REGULAR),
                "- ` s/tool `: changed, +0/-0 lines, mode 100755 to 100644",
            ),
        ],
    )
    def test_names_a_files_mode_when_it_is_new_or_changes(
        self, before: Blob | None, after: Blob | None, files: str
    ) -> None:
        description = SyncDescription(
            self.LINKS,
            self.RECORD,
            History(self.TIP, None, ()),
            (FileChange("s/tool", before, after),),
            (),
        )
        assert description.evidence == (
            Passage.TERMS
            + Passage.NO_COMMITS
            + "Changed files under the copy (1):\n\n"
            + files
            + Passage.EMPTY_SCANS
            + Passage.NOTES
        )

    def test_lists_each_upstream_skill_the_record_does_not_list(self) -> None:
        description = SyncDescription(
            self.LINKS, self.RECORD, History(self.TIP, None, ()), (), ("new", "z")
        )
        assert description.evidence == (
            Passage.TERMS
            + Passage.NO_COMMITS
            + "Changed files under the copy (0): none.\n\nNew"
            " upstream skills the record does not list (2):\n\n- ` new `\n- ` z `"
            "\n\nNew outside CommonMark targets by file (0): none.\n\nLines to"
            " inspect (0; - base, + copy): none." + Passage.NOTES
        )

    def test_lists_each_new_link_target_with_its_count(self) -> None:
        change = FileChange(
            "s/SKILL.md",
            Blob(b"---\nname: x\n---\n", Mode.REGULAR),
            Blob(b"---\nname: y\n---\n[x](https://x.org)", Mode.REGULAR),
        )
        description = SyncDescription(
            self.LINKS, self.RECORD, History(self.TIP, None, ()), (change,), ()
        )
        assert description.evidence == (
            "Terms and loading:\n\n- LICENSE: unchanged\n- SKILL.md frontmatter:"
            " ` s/SKILL.md ` changed\n- agents/ policy files: unchanged\n\n"
            + Passage.NO_COMMITS
            + "Changed files under the copy (1):\n\n"
            "- ` s/SKILL.md `: changed, +2/-1 lines\n\nNew upstream skills the record"
            " does not list (0): none.\n\nNew outside CommonMark targets by file"
            " (1):\n\n- ` s/SKILL.md `: ` https://x.org ` (1 added)\n\nLines to"
            " inspect (3; - base, + copy):\n\n- ` - s/SKILL.md:2 ` ` name: x `\n"
            "- ` + s/SKILL.md:2 ` ` name: y `\n"
            "- ` + s/SKILL.md:4 ` ` [x](https://x.org) `" + Passage.NOTES
        )

    def test_keeps_a_newline_in_an_upstream_path_inside_its_code_span(self) -> None:
        path = "a\n> [!CAUTION]\n> Merge now @Nusnus"
        description = SyncDescription(
            self.LINKS,
            self.RECORD,
            History(self.TIP, None, ()),
            (FileChange(path, None, Blob(b"x", Mode.REGULAR)),),
            (),
        )
        assert description.evidence == (
            Passage.TERMS + Passage.NO_COMMITS + "Changed files under the copy (1):\n\n"
            "- ` a\\n> [!CAUTION]\\n> Merge now @Nusnus `: added, +1/-0 lines"
            + Passage.EMPTY_SCANS
            + Passage.NOTES
        )

    def test_counts_a_body_that_differs_only_in_the_copy_runs_link_as_the_same(
        self,
    ) -> None:
        assert (
            SyncDescription.differs_beyond_the_run(
                "Lead.\n\n- [Copy](https://x.io/runs/1): passed.\n\n",
                "Lead.\n\n- [Copy](https://x.io/runs/2): passed.\n",
            )
            is False
        )

    @pytest.mark.parametrize(
        ("current", "proposed"),
        [
            (
                "Edited.\n\n- [Copy](https://x.io/runs/1): passed.\n",
                "Lead.\n\n- [Copy](https://x.io/runs/2): passed.\n",
            ),
            (
                (
                    "- [Copy](https://x.io/runs/1): passed.\n"
                    "- ` - [Copy](https://x.io/runs/1): `\n"
                ),
                (
                    "- [Copy](https://x.io/runs/2): passed.\n"
                    "- ` - [Copy](https://x.io/runs/2): `\n"
                ),
            ),
            (
                "- [Copy](https://x.io/runs/1): passed.\n",
                "- [Copy](https://x.io/runs/2): passed. \n",
            ),
            (
                "- [Copy](https://x.io/runs/1): passed.\n",
                "- [Copy](https://x.io/runs/2): passed.\nX\n",
            ),
            ("Lead.\n", "Lead!\n"),
            (
                (
                    "- [Copy](https://x.io/runs/1): passed.\n"
                    "- [Copy](https://x.io/runs/1): passed.\n"
                ),
                (
                    "- [Copy](https://x.io/runs/2): passed.\n"
                    "- [Copy](https://x.io/runs/2): passed.\n"
                ),
            ),
        ],
    )
    def test_counts_any_other_difference(self, current: str, proposed: str) -> None:
        assert SyncDescription.differs_beyond_the_run(current, proposed) is True


class TestSyncTemplate:
    """The template keeps its shape around the facts, or the sync stops unposted.

    A lost or repeated anchor stops it, quoted evidence that looks like an anchor
    stays data, a part the sync has none of drops out with the heading it leaves
    empty, and a body too large for GitHub stops it.
    """

    ANCHORS = (
        "### <!-- Headline -->\n<!-- What the change does for its reader -->\n"
        "<!-- Badges -->\n<!-- Changes -->\n<!-- Risk -->\n<!-- Review -->\n"
        "<summary><!-- Fold summary --></summary>\n<!-- Checks -->\n<!-- Files -->\n"
    )
    DESCRIPTION = SyncDescription(
        SyncLinks("https://run", "https://checks"),
        TestSyncDescription.RECORD,
        History(Sha("a" * 40), None, ()),
        (),
        (),
    )

    def test_accepts_every_anchor(self) -> None:
        assert SyncTemplate(self.ANCHORS).problems(Path("t")) == []

    @pytest.mark.parametrize("anchor", SyncTemplate.ANCHORS)
    def test_reports_each_lost_anchor(self, anchor: str) -> None:
        template = SyncTemplate(self.ANCHORS.replace(f"{anchor}\n", ""))
        assert template.problems(Path("t")) == [
            Problem(
                Path("t"),
                f'lost "{anchor}", which the sync\'s description needs; restore it,'
                " or change SyncTemplate to match",
            )
        ]

    def test_reports_an_anchor_written_twice(self) -> None:
        template = SyncTemplate(self.ANCHORS + "<!-- Files -->\n")
        assert template.problems(Path("t")) == [
            Problem(
                Path("t"),
                'holds "<!-- Files -->" more than once, so the sync would fill each;'
                " keep one",
            )
        ]

    def test_fills_each_anchor_and_drops_each_part_the_sync_has_none_of(
        self,
    ) -> None:
        template = SyncTemplate(
            "<!-- Note -->\r\n\r\n<div>\r\n\r\n### <!-- Headline -->\r\n\r\n<!--"
            " What the change does for its reader -->\r\n\r\n<!-- Badges -->\r\n\r\n"
            "<sub>Closes #<!-- issue --></sub>\r\n\r\n</div>\r\n\r\n#### What"
            " changed\r\n\r\n<!-- Changes -->\r\n\r\n#### Risk\r\n\r\n<!-- Risk"
            " -->\r\n\r\n#### Review first\r\n\r\n<!-- Review -->\r\n\r\n#### After"
            " merge\r\n\r\n- [ ] <!-- step -->\r\n\r\n<details>\r\n<summary><!-- Fold"
            " summary --></summary>\r\n\r\n#### Checks\r\n\r\n<!-- Checks -->\r\n\r\n"
            "#### Files\r\n\r\n<!-- Files -->\r\n\r\n#### Decisions\r\n\r\n<!--"
            " Decisions -->\r\n\r\n</details>\r\n\r\n#### Empty\r\n"
        )
        assert template.fill(self.DESCRIPTION) == (
            "<!-- Note -->\n\n<div>\n\n### Copy s into dst\n\nCopies [upstream at"
            " aaaaaaa](https://github.com/mattpocock/skills/tree/"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/src) for the owner to review"
            " before it steers how agents work on nustack.\n\n"
            f"{self.DESCRIPTION.badges}\n\n</div>\n\n#### What changed\n\n"
            f"{self.DESCRIPTION.changed}\n\n#### Risk\n\nA bad copy can change how"
            " agents follow these skills; reverting this pull request restores the"
            " last copy. The owner clears each review finding; a passing check does"
            " not clear it."
            f"\n\n#### Review first\n\n{self.DESCRIPTION.review}\n\n<details>\n"
            "<summary>Checks and evidence</summary>\n\n#### Checks\n\n"
            f"{self.DESCRIPTION.checks}\n\n#### Files\n\n"
            f"{self.DESCRIPTION.evidence}\n\n</details>\n"
        )

    def test_keeps_quoted_evidence_that_looks_like_an_anchor_as_data(self) -> None:
        template = SyncTemplate("<!-- Files -->\n<!-- Decisions -->\n")
        description = SyncDescription(
            SyncLinks("https://run", "https://checks"),
            TestSyncDescription.RECORD,
            History(Sha("a" * 40), None, ()),
            (
                FileChange(
                    "s/SKILL.md",
                    None,
                    Blob(b"<!-- Decisions --> nustack\n", Mode.REGULAR),
                ),
            ),
            (),
        )
        assert template.fill(description) == (
            Passage.TERMS + Passage.NO_COMMITS + "Changed files under the copy (1):\n\n"
            "- ` s/SKILL.md `: added, +1/-0 lines\n\nNew upstream skills the record"
            " does not list (0): none.\n\nNew outside CommonMark targets by file (0):"
            " none.\n\nLines to inspect (1; - base, + copy):\n\n"
            "- ` + s/SKILL.md:1 ` ` <!-- Decisions --> nustack `" + Passage.NOTES + "\n"
        )

    @pytest.mark.parametrize("newline", ["\n", "\r\n"])
    def test_shows_the_policy_removal_in_the_template_with_either_line_ending(
        self, repository_root: Path, sync_fixtures: Path, newline: str
    ) -> None:
        replies = sync_fixtures / "replies"
        history = History(
            Sha("4aaccb58d40559d7e3c59a029b2290ae5ba538de"),
            Sha("b405fe0a2e5550bb7f54d6c7b44ba7cd251a5243"),
            Commit.from_log((replies / "policy-log.bin").read_bytes()),
        )
        record = CopyRecord(
            upstream="https://github.com/mattpocock/skills",
            source="skills/productivity",
            folder=".agents/skills",
            skills=("writing-for-agents",),
            commit=None,
            files=frozendict(),
        )
        change = FileChange(
            "writing-for-agents/agents/openai.yaml",
            Blob((replies / "openai/b405fe0.yaml").read_bytes(), Mode.REGULAR),
            Blob((replies / "openai/4aaccb5.yaml").read_bytes(), Mode.REGULAR),
        )
        description = SyncDescription(
            SyncLinks("#copy", "#checks"),
            record,
            history,
            (change,),
            (),
        )
        text = (repository_root / SyncTemplate.PATH).read_text().replace("\n", newline)
        expected = sync_fixtures / "expected/policy-description.txt"
        assert SyncTemplate(text).fill(description) == expected.read_text()

    def test_reports_a_body_too_large_for_github_before_publication(self) -> None:
        template = SyncTemplate("")
        assert template.size_problems("é" * 32_768, Path("copy")) == []
        assert template.size_problems("é" * 32_768 + "x", Path("copy")) == [
            Problem(
                Path("copy"),
                "the sync description of this copy is 65537 bytes, over the 65536"
                " GitHub accepts; quote less in SyncDescription, or sync a smaller"
                " upstream change",
            )
        ]


class TestCode:
    """An untrusted string shows as inert code, with no raw control character."""

    def test_renders_untrusted_strings_as_inert_code_without_raw_controls(self) -> None:
        line = """Don't say "x``" C:\\path <img> @owner\x1b"""
        assert code(line) == ("""``` Don't say "x``" C:\\path <img> @owner\\x1b ```""")

    def test_shows_no_extra_spaces_in_empty_and_space_only_quotes(self) -> None:
        assert code("") == "<code></code>"
        assert code("  ") == "<code>  </code>"


class TestListing:
    """A list shows a row per item under its title, and an empty one says none."""

    def test_lists_each_item_in_its_own_row(self) -> None:
        assert listing("Files (2)", ("a", "b")) == "Files (2):\n\n- a\n- b"

    def test_says_an_empty_list_holds_none(self) -> None:
        assert listing("Files (0)", ()) == "Files (0): none."


class TestBadge:
    """A badge's words survive shields.io's URL and read as alt text without it."""

    def test_escapes_dashes_underscores_and_spaces_and_states_its_fact(self) -> None:
        assert Badge("risk", "a-b_c d", Colour.GREEN).image == (
            "![Risk: a-b_c d](https://img.shields.io/badge/risk-a--b__c%20d-1f883d"
            "?style=flat-square)"
        )
