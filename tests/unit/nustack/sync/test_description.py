"""The sync's description stays factual and inert, whatever upstream's text holds.

A body that differs from the posted one only in its run link counts as unchanged,
and a template that lost or repeats an anchor, or a body too long to post, stops
the sync.
"""

from pathlib import Path

import pytest

from nustack.problem import Problem
from nustack.sync.change import Blob
from nustack.sync.change import FileChange
from nustack.sync.description import SyncDescription
from nustack.sync.description import SyncLinks
from nustack.sync.description import SyncTemplate
from nustack.sync.description import code
from nustack.sync.description import fold
from nustack.sync.history import Commit
from nustack.sync.history import History
from nustack.sync.tree import Mode


class TestSyncDescription:
    """A reviewer gets each fact approval needs, and nothing upstream can inject.

    A body that differs only in its run link is not posted again. An unmatched base
    states no range, and an empty list or quote shows as empty.
    """

    LINKS = SyncLinks(
        "https://github.com/mattpocock/skills", "https://run", "https://checks"
    )
    TIP = "4ae2317ddb22b046e26455e4f9c9b3aaaf62212d"

    def test_states_no_range_for_an_unmatched_base_and_reports_license_and_header(
        self,
    ) -> None:
        changes = (
            FileChange("LICENSE", None, Blob(b"MIT\n", Mode.REGULAR)),
            FileChange(
                "SKILL.md", Blob(b"x", Mode.REGULAR), Blob(b"\xff", Mode.REGULAR)
            ),
            FileChange("old.md", Blob(b"[x](https://x)", Mode.REGULAR), None),
        )
        description = SyncDescription(
            self.LINKS, "src", "dst", History(self.TIP, None, ()), changes
        )
        assert description.facts.splitlines()[:2] == [
            (
                "| ✅ **[Copy](https://run)** | Compared the base copy"
                " with upstream's at its head, including modes and LICENSE:"
                " 1 added, 1 changed, 1 removed. |"
            ),
            (
                "| ⚠️ **Terms and loading** | LICENSE: added. SKILL.md frontmatter:"
                " not compared (a side contains NUL or is not UTF-8). agents/ policy"
                " files: unchanged. |"
            ),
        ]
        assert description.provenance == (
            "No first-parent change to the upstream paths matched the base copy,"
            " including its license and modes. The commit range is unknown."
        )
        assert (
            "- ` SKILL.md `: changed, a side contains NUL or is not UTF-8; "
            "inspect the file itself" in description.evidence
        )
        assert "- ` old.md `: removed, +0/-1 lines" in description.evidence

    @pytest.mark.parametrize(
        ("commits", "summary"),
        [
            ((), "**Upstream commits touching the skill or repository LICENSE (0).**"),
            (
                (Commit("b" * 40, "one"), Commit("c" * 40, "two")),
                (
                    "<summary>Upstream commits touching the skill or repository LICENSE"
                    " (2)</summary>"
                ),
            ),
        ],
    )
    def test_counts_the_upstream_commits_since_the_base(
        self, commits: tuple[Commit, ...], summary: str
    ) -> None:
        description = SyncDescription(
            self.LINKS, "src", "dst", History(self.TIP, "a" * 40, commits), ()
        )
        assert summary in description.provenance

    @pytest.mark.parametrize(
        ("before", "after", "files"),
        [
            (
                Blob(b"", Mode.REGULAR),
                Blob(b"", Mode.EXECUTABLE),
                (
                    "<details>\n<summary>Changed files under the copy"
                    " (1)</summary>\n\n- ` tool `: changed, +0/-0 lines, mode 100644"
                    " to 100755\n\n</details>"
                ),
            ),
            (
                None,
                Blob(b"", Mode.EXECUTABLE),
                (
                    "<details>\n<summary>Changed files under the copy (1)</summary>\n\n"
                    "- ` tool `: added, +0/-0 lines, mode 100755\n\n</details>"
                ),
            ),
            (None, Blob(b"", Mode.REGULAR), "- ` tool `: added, +0/-0 lines"),
            (
                Blob(b"a\n", Mode.EXECUTABLE),
                Blob(b"b\n", Mode.EXECUTABLE),
                (
                    "<details>\n<summary>Changed files under the copy (1)</summary>\n\n"
                    "- ` tool `: changed, +1/-1 lines\n\n</details>"
                ),
            ),
            (Blob(b"", Mode.EXECUTABLE), None, "- ` tool `: removed, +0/-0 lines"),
            (
                Blob(b"", Mode.EXECUTABLE),
                Blob(b"", Mode.REGULAR),
                (
                    "<details>\n<summary>Changed files under the copy"
                    " (1)</summary>\n\n- ` tool `: changed, +0/-0 lines, mode 100755"
                    " to 100644\n\n</details>"
                ),
            ),
        ],
    )
    def test_names_a_files_mode_when_it_is_new_or_changes(
        self, before: Blob | None, after: Blob | None, files: str
    ) -> None:
        description = SyncDescription(
            self.LINKS,
            "src",
            "dst",
            History(self.TIP, None, ()),
            (FileChange("tool", before, after),),
        )
        assert files in description.evidence

    def test_lists_each_new_link_target_with_its_count(self) -> None:
        change = FileChange(
            "SKILL.md",
            Blob(b"---\nname: x\n---\n", Mode.REGULAR),
            Blob(b"---\nname: y\n---\n[x](https://x.org)", Mode.REGULAR),
        )
        description = SyncDescription(
            self.LINKS, "src", "dst", History(self.TIP, None, ()), (change,)
        )
        assert (
            "<details>\n<summary>New outside CommonMark targets by file"
            " (1)</summary>\n\n- ` SKILL.md `: ` https://x.org ` (1"
            " added)\n\n</details>"
        ) in description.evidence
        assert "LICENSE: unchanged. SKILL.md frontmatter: changed." in description.facts
        assert "| **Terms and loading** |" in description.facts

    def test_flags_a_loading_change_in_a_policy_file(self) -> None:
        changes = (
            FileChange(
                "agents/openai.yaml",
                Blob(b"policy:\n  allow_implicit_invocation: false\n", Mode.REGULAR),
                None,
            ),
            FileChange("agents/x.yaml", None, Blob(b"name: x\n", Mode.REGULAR)),
            FileChange("agents/y.yaml", None, Blob(b"\xff", Mode.REGULAR)),
        )
        description = SyncDescription(
            self.LINKS, "src", "dst", History(self.TIP, None, ()), changes
        )
        assert description.facts.splitlines()[1] == (
            "| ⚠️ **Terms and loading** | LICENSE: unchanged. SKILL.md frontmatter:"
            " unchanged. agents/ policy files: ` agents/openai.yaml ` removed ⚠️ a"
            " loading field changed; ` agents/x.yaml ` added; ` agents/y.yaml ` added"
            " ⚠️ not compared (a side contains NUL or is not UTF-8). |"
        )

    def test_flags_the_row_for_an_uncompared_policy_file_alone(self) -> None:
        changes = (FileChange("agents/y.yaml", None, Blob(b"\0", Mode.REGULAR)),)
        description = SyncDescription(
            self.LINKS, "src", "dst", History(self.TIP, None, ()), changes
        )
        assert description.facts.splitlines()[1] == (
            "| ⚠️ **Terms and loading** | LICENSE: unchanged. SKILL.md frontmatter:"
            " unchanged. agents/ policy files: ` agents/y.yaml ` added ⚠️ not compared"
            " (a side contains NUL or is not UTF-8). |"
        )

    def test_flags_nothing_for_an_uncompared_file_outside_policy_and_the_skill(
        self,
    ) -> None:
        changes = (FileChange("tool.bin", None, Blob(b"\0", Mode.REGULAR)),)
        description = SyncDescription(
            self.LINKS, "src", "dst", History(self.TIP, None, ()), changes
        )
        assert description.facts.splitlines()[1] == (
            "| **Terms and loading** | LICENSE: unchanged. SKILL.md frontmatter:"
            " unchanged. agents/ policy files: unchanged. |"
        )

    def test_renders_untrusted_strings_as_inert_code_without_raw_controls(self) -> None:
        line = """Don't say "x``" C:\\path <img> @owner\x1b"""
        assert code(line) == ("""``` Don't say "x``" C:\\path <img> @owner\\x1b ```""")

    def test_keeps_a_newline_in_an_upstream_path_inside_its_code_span(self) -> None:
        path = "a\n> [!CAUTION]\n> Merge now @Nusnus"
        description = SyncDescription(
            self.LINKS,
            "skills/s",
            "copy",
            History(self.TIP, None, ()),
            (FileChange(path, None, Blob(b"x", Mode.REGULAR)),),
        )
        assert code(path) == ("` a\\n> [!CAUTION]\\n> Merge now @Nusnus `")
        assert "\n> [!CAUTION]" not in description.evidence

    def test_counts_a_body_that_differs_only_in_the_copy_runs_link_as_the_same(
        self,
    ) -> None:
        assert (
            SyncDescription.differs_beyond_the_run(
                "Lead.\n\n| ✅ **[Copy](https://x.io/runs/1)** | Compared. |\n\n",
                "Lead.\n\n| ✅ **[Copy](https://x.io/runs/2)** | Compared. |\n",
            )
            is False
        )

    @pytest.mark.parametrize(
        ("current", "proposed"),
        [
            (
                "Edited.\n\n| ✅ **[Copy](https://x.io/runs/1)** | Compared. |\n",
                "Lead.\n\n| ✅ **[Copy](https://x.io/runs/2)** | Compared. |\n",
            ),
            (
                (
                    "| ✅ **[Copy](https://x.io/runs/1)** | Compared. |\n"
                    "- ` | ✅ **[Copy](https://x.io/runs/1)** | `\n"
                ),
                (
                    "| ✅ **[Copy](https://x.io/runs/2)** | Compared. |\n"
                    "- ` | ✅ **[Copy](https://x.io/runs/2)** | `\n"
                ),
            ),
            (
                "| ✅ **[Copy](https://x.io/runs/1)** | Compared. |\n",
                "| ✅ **[Copy](https://x.io/runs/2)** | Compared. | \n",
            ),
            (
                "| ✅ **[Copy](https://x.io/runs/1)** | Compared. |\n",
                "| ✅ **[Copy](https://x.io/runs/2)** | Compared. |\nX\n",
            ),
            ("Lead.\n", "Lead!\n"),
            (
                (
                    "| ✅ **[Copy](https://x.io/runs/1)** | Compared. |\n"
                    "| ✅ **[Copy](https://x.io/runs/1)** | Compared. |\n"
                ),
                (
                    "| ✅ **[Copy](https://x.io/runs/2)** | Compared. |\n"
                    "| ✅ **[Copy](https://x.io/runs/2)** | Compared. |\n"
                ),
            ),
        ],
    )
    def test_counts_any_other_difference(self, current: str, proposed: str) -> None:
        assert SyncDescription.differs_beyond_the_run(current, proposed) is True

    def test_folds_each_item_into_its_own_row(self) -> None:
        assert fold("Files (2)", ("a", "b")) == (
            "<details>\n<summary>Files (2)</summary>\n\n- a\n- b\n\n</details>"
        )

    def test_names_an_empty_list_without_folding_it(self) -> None:
        assert fold("Files (0)", ()) == "**Files (0).**"

    def test_shows_no_extra_spaces_in_empty_and_space_only_quotes(self) -> None:
        assert code("") == "<code></code>"
        assert code("  ") == "<code>  </code>"


class TestSyncTemplate:
    """The template keeps its shape around the facts, or the sync stops unposted.

    A lost, repeated or late anchor, or a body too large for GitHub, stops it;
    quoted evidence that looks like an anchor stays data.
    """

    def test_fills_each_anchor_and_drops_what_follows_decisions(self) -> None:
        template = SyncTemplate(
            "# Title\r\n<!-- Lead -->\r\n| **Feedback wanted** | |\r\n| <!-- mark -->"
            " **[<!-- check"
            " -->](<!-- run link -->)** | <!-- result --> |\r\n| **Risk** | |\r\n<!--"
            " Files -->\r\n<!-- One heading per idea -->\r\n\r\n## ⚖️"
            " Decisions\r\nkept out\r\n"
        )
        description = SyncDescription(
            SyncLinks("https://up", "https://run", "https://checks"),
            "skills/s",
            "copy",
            History("a" * 40, None, ()),
            (),
        )
        assert template.fill(description) == (
            "# Title\n"
            "**Copies [writing-for-agents at aaaaaaa](https://up/tree/"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/skills/s) into `copy/`** for the"
            " owner to review before it steers how agents word nustack's docs.\n"
            "| **Feedback wanted** | Whether to accept this copy as wording guidance"
            " for nustack |\n"
            "| ✅ **[Copy](https://run)** | Compared the base copy"
            " with upstream's at its head, including modes and LICENSE:"
            " 0 added, 0 changed, 0 removed. |\n"
            "| **Terms and loading** | LICENSE: unchanged. SKILL.md frontmatter:"
            " unchanged. agents/ policy files: unchanged. |\n"
            "| ⚠️ **[CI](https://checks)** | Approve this pull request's workflows if"
            " prompted; see the linked runs for results. |\n"
            "| **Risk** | The copy is untrusted. The owner clears each review"
            " finding; a passing check does not clear it. |\n"
            "No first-parent change to the upstream paths matched the base copy,"
            " including its license and modes. The commit range is unknown.\n\n"
            "**Changed files under the copy (0).**\n\n"
            "**New outside CommonMark targets by file (0).**\n\n"
            "**Lines to inspect (0; - base, + copy).**\n\n"
            "**Links:** net new destinations per file that the CommonMark parser"
            " recognizes as links or images. Check raw HTML, bare URLs and rejected"
            " URI schemes in the diff.\n\n"
            "**Lines:** edits in `SKILL.md` frontmatter and `agents/`, plus added"
            " lines naming rules, invocation fields, selected commands or HTTP(S)"
            " URLs. Both scans skip binary comparisons.\n\n"
            "**Owner review:** read the whole diff for instructions beyond wording,"
            " claims of authority or wider loading. These cues cannot decide any of"
            " them.\n"
        )

    def test_keeps_quoted_evidence_that_looks_like_an_anchor_as_data(self) -> None:
        template = SyncTemplate("<!-- Files -->\n<!-- One heading per idea -->\n")
        description = SyncDescription(
            SyncLinks("https://up", "https://run", "https://checks"),
            "skills/s",
            "copy",
            History("a" * 40, None, ()),
            (
                FileChange(
                    "SKILL.md",
                    None,
                    Blob(b"<!-- One heading per idea --> nustack\n", Mode.REGULAR),
                ),
            ),
        )
        assert "` <!-- One heading per idea --> nustack `" in template.fill(description)

    def test_accepts_every_anchor_before_decisions(self) -> None:
        template = SyncTemplate(
            "<!-- Lead -->\n|"
            " **Feedback wanted** | |\n| <!-- mark --> **[<!-- check -->](<!-- run"
            " link -->)** | <!-- result --> |\n| **Risk** | |\n<!-- Files -->\n<!--"
            " One heading per idea -->\n## ⚖️ Decisions\n"
        )
        assert template.problems(Path("t")) == []

    @pytest.mark.parametrize(
        ("anchor", "what"),
        [
            (
                "<!-- Lead -->",
                (
                    'lost "<!-- Lead -->", which the sync\'s description needs;'
                    " restore it, or change SyncTemplate to match"
                ),
            ),
            (
                "| **Feedback wanted** | |",
                (
                    'lost "| **Feedback wanted** | |", which the sync\'s description'
                    " needs; restore it, or change SyncTemplate to match"
                ),
            ),
            (
                (
                    "| <!-- mark --> **[<!-- check -->](<!-- run link -->)** | <!--"
                    " result --> |"
                ),
                (
                    'lost "| <!-- mark --> **[<!-- check -->](<!-- run link -->)** |'
                    " <!-- result --> |\", which the sync's description needs; restore"
                    " it, or change SyncTemplate to match"
                ),
            ),
            (
                "<!-- One heading per idea -->",
                (
                    'lost "<!-- One heading per idea -->", which the sync\'s'
                    " description needs; restore it, or change SyncTemplate to match"
                ),
            ),
        ],
    )
    def test_reports_each_lost_anchor(self, anchor: str, what: str) -> None:
        template = SyncTemplate(
            "<!-- Lead -->\n|"
            " **Feedback wanted** | |\n| <!-- mark --> **[<!-- check -->](<!-- run"
            " link -->)** | <!-- result --> |\n| **Risk** | |\n<!-- Files -->\n<!--"
            " One heading per idea -->\n## ⚖️ Decisions\n".replace(anchor, "")
        )
        assert template.problems(Path("t")) == [Problem(Path("t"), what)]

    def test_reports_an_anchor_written_twice(self) -> None:
        template = SyncTemplate(
            "<!-- Lead -->\n|"
            " **Feedback wanted** | |\n| <!-- mark --> **[<!-- check -->](<!-- run"
            " link -->)** | <!-- result --> |\n| **Risk** | |\n<!-- Files -->\n<!--"
            " Files -->\n<!-- One heading per idea -->\n## ⚖️ Decisions\n"
        )
        assert template.problems(Path("t")) == [
            Problem(
                Path("t"),
                'holds "<!-- Files -->" more than once, so the sync would fill each;'
                " keep one",
            )
        ]

    def test_reports_an_anchor_after_decisions_as_missing(self) -> None:
        template = SyncTemplate(
            "<!-- Lead -->\n|"
            " **Feedback wanted** | |\n| <!-- mark --> **[<!-- check -->](<!-- run"
            " link -->)** | <!-- result --> |\n| **Risk** | |\n<!-- One heading per"
            " idea -->\n## ⚖️ Decisions\n<!-- Files -->"
        )
        assert template.problems(Path("t")) == [
            Problem(
                Path("t"),
                'lost "<!-- Files -->", which the sync\'s description needs; '
                "restore it, or change SyncTemplate to match",
            )
        ]

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

    @pytest.mark.parametrize("newline", ["\n", "\r\n"])
    def test_shows_the_policy_removal_in_the_template_with_either_line_ending(
        self, repository_root: Path, sync_fixtures: Path, newline: str
    ) -> None:
        replies = sync_fixtures / "replies"
        history = History(
            "4aaccb58d40559d7e3c59a029b2290ae5ba538de",
            "b405fe0a2e5550bb7f54d6c7b44ba7cd251a5243",
            Commit.from_log((replies / "policy-log.bin").read_bytes()),
        )
        change = FileChange(
            "agents/openai.yaml",
            Blob((replies / "openai/b405fe0.yaml").read_bytes(), Mode.REGULAR),
            Blob((replies / "openai/4aaccb5.yaml").read_bytes(), Mode.REGULAR),
        )
        description = SyncDescription(
            SyncLinks("https://github.com/mattpocock/skills", "#copy", "#checks"),
            "skills/productivity/writing-for-agents",
            ".agents/skills/writing-for-agents",
            history,
            (change,),
        )
        text = (repository_root / SyncTemplate.PATH).read_text().replace("\n", newline)
        expected = sync_fixtures / "expected/policy-description.txt"
        assert SyncTemplate(text).fill(description) == expected.read_text()
