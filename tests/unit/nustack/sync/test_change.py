"""Comparing two copies of a file yields a reviewer's evidence, and no verdict.

That is its edits, its loading effect, its new outside links and the added lines a
reviewer should read; text it cannot compare is left for review.
"""

import pytest

from nustack.sync.change import Blob
from nustack.sync.change import Comparison
from nustack.sync.change import Edit
from nustack.sync.change import FileChange
from nustack.sync.tree import Mode


class TestFileChange:
    """A file's change shows its edits, loading effect, outside links and cue lines.

    A mode-only change is a change, and text it cannot compare is left for review,
    never counted as unchanged. A body edit leaves the frontmatter unchanged, while
    a lost closing fence changes it. Only new outside uses count; an edit's CRLF
    drops while a bare CR stays, and a repeated line stays out of the diff. A file
    under agents/ is a policy file, a nested SKILL.md has no frontmatter lines, and
    a removal is numbered on the base side. Only added cue lines are quoted, and a
    link through the parent or from the root leaves, while one that only starts with
    dots stays.
    """

    def test_counts_a_mode_only_change_as_a_change_with_no_line_edits(self) -> None:
        change = FileChange(
            "s/tool", Blob(b"", Mode.REGULAR), Blob(b"", Mode.EXECUTABLE)
        )
        assert change.status == "changed"
        assert change.edits == ()

    @pytest.mark.parametrize("data", [b"x\0y", b"\xff"])
    def test_leaves_non_text_for_review_rather_than_treating_it_as_clean(
        self, data: bytes
    ) -> None:
        change = FileChange("s/SKILL.md", None, Blob(data, Mode.REGULAR))
        assert change.texts is None
        assert change.frontmatter_comparison is Comparison.BINARY
        assert change.outside_links == ()
        assert change.edits == ()
        assert change.marked_lines == ()

    def test_reads_nul_on_the_base_side_alone_as_non_text(self) -> None:
        change = FileChange(
            "s/SKILL.md", Blob(b"x\0y", Mode.REGULAR), Blob(b"y", Mode.REGULAR)
        )
        assert change.texts is None

    def test_reads_a_base_that_is_not_utf8_as_non_text(self) -> None:
        change = FileChange(
            "s/SKILL.md", Blob(b"\xff", Mode.REGULAR), Blob(b"y", Mode.REGULAR)
        )
        assert change.texts is None

    def test_leaves_frontmatter_unchanged_by_a_body_edit_even_with_a_later_fence(
        self,
    ) -> None:
        change = FileChange(
            "s/SKILL.md",
            Blob(b"---\r\nname: old\r\n---\r\nold", Mode.REGULAR),
            Blob(b"---\r\nname: old\r\n---\r\nnew\n---\n", Mode.REGULAR),
        )
        assert change.frontmatter_comparison is Comparison.UNCHANGED
        assert change.marked_lines == ()

    def test_reads_a_lost_closing_fence_as_a_changed_frontmatter(self) -> None:
        change = FileChange(
            "s/SKILL.md",
            Blob(b"---\nname: x\n---\n", Mode.REGULAR),
            Blob(b"---\nname: x\nword the text", Mode.REGULAR),
        )
        assert change.frontmatter_comparison is Comparison.CHANGED
        assert change.marked_lines == (
            Edit("-", 3, "---"),
            Edit("+", 3, "word the text"),
        )

    def test_counts_only_new_outside_uses_of_references_images_and_paths(
        self,
    ) -> None:
        change = FileChange(
            "s/guide/read.md",
            Blob(b"[keep](https://same.org)\n", Mode.REGULAR),
            Blob(
                b"[keep](https://same.org) [repeat](https://same.org) [ref][] [ref][] "
                b"![img](//cdn.org/i) [root](/p) [up](%2E%2E/%2E%2E/a) "
                b"[edge](../..#here) [inside](../SKILL.md) [self](#here) "
                b"[colon](notes%3Awording.md) [query](?path=../../outside)\n\n"
                b"[ref]: mailto:a@example.org\n",
                Mode.REGULAR,
            ),
        )
        assert change.outside_links == (
            ("%2E%2E/%2E%2E/a", 1),
            ("../..#here", 1),
            ("//cdn.org/i", 1),
            ("/p", 1),
            ("https://same.org", 1),
            ("mailto:a@example.org", 2),
        )

    def test_drops_an_edits_crlf_and_keeps_a_bare_cr_and_spaces_in_the_line(
        self,
    ) -> None:
        change = FileChange(
            "s/notes.md",
            Blob(b"a\r\nb  \r\n", Mode.REGULAR),
            Blob(b"a\r\nc\rd\r\n", Mode.REGULAR),
        )
        assert change.edits == (Edit("-", 2, "b  "), Edit("+", 2, "c\rd"))

    def test_keeps_repeated_lines_out_of_the_diff_when_one_line_is_added(self) -> None:
        repeated = b"same line\n" * 200
        change = FileChange(
            "s/notes.md",
            Blob(repeated, Mode.REGULAR),
            Blob(b"new line\n" + repeated, Mode.REGULAR),
        )
        assert change.edits == (Edit("+", 1, "new line"),)

    def test_counts_a_file_under_agents_as_a_policy_file(self) -> None:
        assert FileChange("s/agents/openai.yaml", None, None).policy is True
        assert FileChange("s/SKILL.md", None, None).policy is False
        assert FileChange("s/agents.md", None, None).policy is False

    def test_reads_a_removed_line_of_a_longer_old_frontmatter_as_a_loading_line(
        self,
    ) -> None:
        change = FileChange(
            "s/SKILL.md",
            Blob(
                b"---\nname: x\ndescription: X.\ndisable-model-invocation: true\n"
                b"triggers: [user]\n---\nbody\n",
                Mode.REGULAR,
            ),
            Blob(b"---\nname: x\n---\nbody\n", Mode.REGULAR),
        )
        assert change.loading_lines == (
            Edit("-", 3, "description: X."),
            Edit("-", 4, "disable-model-invocation: true"),
            Edit("-", 5, "triggers: [user]"),
        )

    def test_finds_no_frontmatter_lines_in_a_nested_skill_file(self) -> None:
        change = FileChange(
            "s/refs/SKILL.md",
            Blob(b"---\nname: x\n---\n", Mode.REGULAR),
            Blob(b"---\nname: y\n---\n", Mode.REGULAR),
        )
        assert change.loading_lines == ()

    def test_leaves_loading_uncompared_in_a_policy_file_with_nul(self) -> None:
        change = FileChange(
            "s/agents/openai.yaml",
            Blob(b"policy:\n", Mode.REGULAR),
            Blob(b"\0allow_implicit_invocation: true\n", Mode.REGULAR),
        )
        assert change.loading is Comparison.BINARY

    def test_reads_a_removed_loading_field_in_a_policy_file_as_a_loading_change(
        self,
    ) -> None:
        change = FileChange(
            "s/agents/openai.yaml",
            Blob(b"policy:\n  allow_implicit_invocation: false\n", Mode.REGULAR),
            Blob(b"", Mode.REGULAR),
        )
        assert change.loading is Comparison.CHANGED

    def test_reads_a_loading_field_edit_in_the_skill_frontmatter_as_a_loading_change(
        self,
    ) -> None:
        change = FileChange(
            "s/SKILL.md",
            Blob(b"---\nname: x\n---\n", Mode.REGULAR),
            Blob(b"---\nname: x\ndisable-model-invocation: true\n---\n", Mode.REGULAR),
        )
        assert change.loading is Comparison.CHANGED

    def test_reads_a_description_edit_in_the_skill_frontmatter_as_a_loading_change(
        self,
    ) -> None:
        change = FileChange(
            "s/SKILL.md",
            Blob(b"---\nname: x\ndescription: Old.\n---\n", Mode.REGULAR),
            Blob(b"---\nname: x\ndescription: New.\n---\n", Mode.REGULAR),
        )
        assert change.loading is Comparison.CHANGED

    @pytest.mark.parametrize(
        ("path", "old", "new"),
        [
            ("s/agents/openai.yaml", b"name: a\n", b"name: b\n"),
            (
                "s/agents/openai.yaml",
                b"description: a\n",
                b"description: b\n",
            ),
            (
                "s/SKILL.md",
                b"---\nname: x\n---\n",
                b"---\nname: x\n---\ndescription: b\n",
            ),
            (
                "s/SKILL.md",
                b"---\nname: x\nmetadata: a\n---\n",
                b"---\nname: x\nmetadata: a description: b\n---\n",
            ),
            ("s/SKILL.md", b"---\nname: x\n---\n", b"---\nname: x\n---\ntriggers\n"),
            (
                "s/SKILL.md",
                b"---\nname: x\ndescriptions: a\n---\n",
                b"---\nname: x\ndescriptions: b\n---\n",
            ),
            ("s/notes.md", b"", b"triggers: [model]\n"),
        ],
    )
    def test_reads_other_edits_as_leaving_loading_unchanged(
        self, path: str, old: bytes, new: bytes
    ) -> None:
        change = FileChange(path, Blob(old, Mode.REGULAR), Blob(new, Mode.REGULAR))
        assert change.loading is Comparison.UNCHANGED

    def test_reads_a_configuration_only_on_the_base_side_as_removed_lines(self) -> None:
        change = FileChange(
            "s/agents/host.yml",
            Blob(b"policy:\n  allow_implicit_invocation: false\n", Mode.REGULAR),
            None,
        )
        assert change.status == "removed"
        assert change.marked_lines == (
            Edit("-", 1, "policy:"),
            Edit("-", 2, "  allow_implicit_invocation: false"),
        )

    def test_quotes_only_added_cues_outside_frontmatter_and_host_settings(self) -> None:
        change = FileChange(
            "s/notes.md",
            Blob(b"Read REVIEW.md\nRead AGENTS.md\n", Mode.REGULAR),
            Blob(
                b"Read REVIEW.md\nRun git push\nsee https://example.org\n"
                b"Use short words\n",
                Mode.REGULAR,
            ),
        )
        assert change.marked_lines == (
            Edit("+", 2, "Run git push"),
            Edit("+", 3, "see https://example.org"),
        )

    @pytest.mark.parametrize(
        "line",
        [
            "Read AGENTS.md",
            "Read CLAUDE.md",
            "Read REVIEW.md",
            "Turn on nus-mode",
            "Run nustack",
            "disable-model-invocation: false",
            "allow_implicit_invocation: true",
            "triggers: [model]",
            "Then git push",
            "Then git commit",
            "Run curl",
            "Run sudo",
            "Run SUDO",
            "See http://example.com",
            "See https://example.com",
            "See HTTPS://example.com",
        ],
    )
    def test_quotes_each_added_line_that_names_a_marker(self, line: str) -> None:
        change = FileChange(
            "s/notes.md",
            Blob(b"", Mode.REGULAR),
            Blob(f"{line}\n".encode(), Mode.REGULAR),
        )
        assert change.marked_lines == (Edit("+", 1, line),)

    @pytest.mark.parametrize(
        "line", ["Plain words", "git pushes", "curls", "httpx://example.com"]
    )
    def test_quotes_no_added_line_that_only_resembles_one(self, line: str) -> None:
        change = FileChange(
            "s/notes.md",
            Blob(b"", Mode.REGULAR),
            Blob(f"{line}\n".encode(), Mode.REGULAR),
        )
        assert change.marked_lines == ()

    @pytest.mark.parametrize("href", ["../x.md", "..", "/x.md", "../t/SKILL.md"])
    def test_counts_a_link_through_the_parent_or_from_the_root_as_leaving(
        self, href: str
    ) -> None:
        assert FileChange("s/SKILL.md", None, None).leaves(href) is True

    @pytest.mark.parametrize("href", ["..notes.md", "a/../b.md", "../s/x.md"])
    def test_counts_a_link_that_only_starts_with_dots_as_staying(
        self, href: str
    ) -> None:
        assert FileChange("s/SKILL.md", None, None).leaves(href) is False
