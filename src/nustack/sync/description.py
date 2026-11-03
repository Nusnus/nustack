"""The description of the sync's pull request, filled into the PR template.

It states the facts a reviewer needs about the two copies, where they came from and
what changed in each file, under the workflow's own links. It fills only the
template's anchored part, so copied text stays data that never supplies a link or a
verdict; a template that lost an anchor, or a body too long to post, stops the
sync. A body that differs from the posted one only in its run link is unchanged.
"""

import re
from collections import Counter
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import ClassVar
from typing import assert_never
lazy from collections.abc import Iterable

from nustack.plugin.skill import Skill
from nustack.problem import Problem
from nustack.sync.change import Comparison
from nustack.sync.change import FileChange
from nustack.sync.tree import CopyTree
lazy from nustack.sync.history import History


@dataclass(frozen=True)
class SyncLinks:
    """Trusted workflow links; copied text never supplies a Markdown destination."""

    upstream: str
    run: str
    checks: str


@dataclass(frozen=True)
class SyncCopy:
    """Where the sync copies from and to: upstream's clone, its skill, and the copy."""

    clone: Path
    source: str
    folder: str


@dataclass(frozen=True)
class SyncDescription:
    """Review facts about the two snapshots, never a verdict on the copied text."""

    NON_TEXT: ClassVar[str] = "a side contains NUL or is not UTF-8"
    NOT_COMPARED: ClassVar[str] = f"not compared ({NON_TEXT})"
    COPY_ROW: ClassVar[str] = "| ✅ **[Copy]({run})** |"
    links: SyncLinks
    source: str
    folder: str
    history: History
    changes: tuple[FileChange, ...]

    @property
    def lead(self) -> str:
        source = f"{self.links.upstream}/tree/{self.history.copied}/{self.source}"
        return (
            f"**Copies [writing-for-agents at {self.history.copied[:7]}]({source}) "
            f"into `{self.folder}/`** for the owner to review before it steers "
            "how agents word nustack's docs."
        )

    @cached_property
    def facts(self) -> str:
        counts = Counter(change.status for change in self.changes)
        files = {change.path: change for change in self.changes}
        license_change = files.get(CopyTree.LICENSE)
        license_status = license_change.status if license_change else "unchanged"
        skill_change = files.get(Skill.FILE)
        comparison = (
            skill_change.frontmatter_comparison
            if skill_change
            else Comparison.UNCHANGED
        )
        match comparison:
            case Comparison.CHANGED | Comparison.UNCHANGED:
                frontmatter_status = comparison.value
            case Comparison.BINARY:
                frontmatter_status = self.NOT_COMPARED
            case unexpected:
                assert_never(unexpected)
        policies = [change for change in self.changes if change.policy]
        policy = "; ".join(
            f"{code(change.path)} {change.status}{self.loading_note(change.loading)}"
            for change in policies
        )
        watched = [*policies, *([skill_change] if skill_change else [])]
        loading = any(change.loading is not Comparison.UNCHANGED for change in watched)
        return (
            f"{self.COPY_ROW.format(run=self.links.run)} Compared the base copy with "
            f"upstream's at its head, including modes and {CopyTree.LICENSE}: "
            f"{counts['added']} added, "
            f"{counts['changed']} changed, {counts['removed']} removed. |\n"
            f"| {'⚠️ ' if loading else ''}**Terms and loading** | {CopyTree.LICENSE}: "
            f"{license_status}. {Skill.FILE} frontmatter: "
            f"{frontmatter_status}. "
            f"{FileChange.POLICIES} policy files: {policy or 'unchanged'}. |\n"
            f"| ⚠️ **[CI]({self.links.checks})** | Approve this pull request's "
            "workflows if prompted; see the linked runs for results. |"
        )

    @cached_property
    def provenance(self) -> str:
        if self.history.baseline is None:
            return (
                "No first-parent change to the upstream paths matched the base "
                "copy, including its license and modes. The commit range is unknown."
            )
        baseline = self.history.baseline
        upstream = self.links.upstream
        compare = f"{upstream}/compare/{baseline}...{self.history.copied}"
        return (
            f"[Compare upstream from `{baseline[:7]}` to `{self.history.copied[:7]}`]"
            f"({compare}). The start is the newest first-parent path revision "
            "matching the base copy, not a recorded sync SHA.\n\n"
            + fold(
                f"Upstream commits touching the skill or repository {CopyTree.LICENSE} "
                f"({len(self.history.commits)})",
                (
                    f"[`{commit.sha[:7]}`]({upstream}/commit/{commit.sha}) "
                    f"{code(commit.subject)}"
                    for commit in self.history.commits
                ),
            )
        )

    @cached_property
    def evidence(self) -> str:
        files: list[str] = []
        links: list[str] = []
        lines: list[str] = []
        for change in self.changes:
            if change.texts is None:
                detail = f"{self.NON_TEXT}; inspect the file itself"
            else:
                counts = Counter(edit.side for edit in change.edits)
                detail = f"+{counts['+']}/-{counts['-']} lines"
            files.append(
                f"{code(change.path)}: {change.status}, {detail}{change.modes}"
            )
            links.extend(
                f"{code(change.path)}: {code(href)} ({count} added)"
                for href, count in change.outside_links
            )
            lines.extend(
                f"{code(f'{edit.side} {change.path}:{edit.number}')} {code(edit.text)}"
                for edit in change.marked_lines
            )
        return "\n\n".join(
            (
                self.provenance,
                fold(f"Changed files under the copy ({len(files)})", files),
                fold(f"New outside CommonMark targets by file ({len(links)})", links),
                fold(f"Lines to inspect ({len(lines)}; - base, + copy)", lines),
                (
                    "**Links:** net new destinations per file that the CommonMark "
                    "parser recognizes as links or images. Check raw HTML, bare URLs "
                    "and rejected URI schemes in the diff.\n\n"
                    f"**Lines:** edits in `{Skill.FILE}` frontmatter and "
                    f"`{FileChange.POLICIES}`, plus "
                    "added lines naming rules, invocation fields, selected commands "
                    "or HTTP(S) URLs. Both scans skip binary comparisons.\n\n"
                    "**Owner review:** read the whole diff for instructions beyond "
                    "wording, claims of authority or wider loading. These cues "
                    "cannot decide any of them."
                ),
            )
        )

    @classmethod
    def differs_beyond_the_run(cls, current: str, proposed: str) -> bool:
        return cls.beyond_the_run(current) != cls.beyond_the_run(proposed)

    @classmethod
    def beyond_the_run(cls, body: str) -> str:
        before, after = (re.escape(part) for part in cls.COPY_ROW.split("{run}"))
        row = re.search(rf"^{before}(?P<run>[^\s)]*){after}", body, re.MULTILINE)
        if row is not None:
            body = body[: row.start("run")] + body[row.end("run") :]
        # gh ends each string its --jq prints with a newline:
        # https://github.com/cli/go-gh/blob/v2.9.0/pkg/jq/jq.go#L85
        return body.rstrip("\n")

    @classmethod
    def loading_note(cls, loading: Comparison) -> str:
        match loading:
            case Comparison.UNCHANGED:
                return ""
            case Comparison.CHANGED:
                return " ⚠️ a loading field changed"
            case Comparison.BINARY:
                return f" ⚠️ {cls.NOT_COMPARED}"
            case unexpected:
                assert_never(unexpected)


@dataclass(frozen=True)
class SyncTemplate:
    """Fills the PR template's exact line anchors with a sync description's parts.

    Each anchor is replaced once, so quoted evidence stays data, and a lost or
    repeated anchor, or a body too large for GitHub, is a Problem.
    """

    PATH: ClassVar[Path] = Path(".github/pull_request_template.md")
    LEAD: ClassVar[str] = "<!-- Lead -->"
    FEEDBACK: ClassVar[str] = "| **Feedback wanted** | |"
    CHECK: ClassVar[str] = (
        "| <!-- mark --> **[<!-- check -->](<!-- run link -->)** | <!-- result --> |"
    )
    RISK: ClassVar[str] = "| **Risk** | |"
    FILES: ClassVar[str] = "<!-- Files -->"
    IDEA: ClassVar[str] = "<!-- One heading per idea -->"
    DECISIONS: ClassVar[str] = "## ⚖️ Decisions"
    # GitHub's docs name no limit, yet creating a pull request with a body over
    # 65,536 characters fails with "Body is too long (maximum is 65536
    # characters)", as https://github.com/gerchowl/flock/issues/2810 records.
    # Counting bytes stays under it, since no character is under one byte.
    MAX_BODY_BYTES: ClassVar[int] = 65_536
    text: str

    @cached_property
    def lines(self) -> tuple[str, ...]:
        return tuple(self.text.replace("\r\n", "\n").split("\n"))

    @cached_property
    def head(self) -> tuple[str, ...]:
        if self.DECISIONS not in self.lines:
            return self.lines
        return self.lines[: self.lines.index(self.DECISIONS)]

    def problems(self, path: Path) -> list[Problem]:
        anchors = (
            self.LEAD,
            self.FEEDBACK,
            self.CHECK,
            self.RISK,
            self.FILES,
            self.IDEA,
        )
        missing = [line for line in anchors if line not in self.head]
        if self.DECISIONS not in self.lines:
            missing.append(self.DECISIONS)
        repeated = [line for line in anchors if self.head.count(line) > 1]
        return [
            *(
                Problem(
                    path,
                    f'lost "{line}", which the sync\'s description needs; '
                    "restore it, or change SyncTemplate to match",
                )
                for line in missing
            ),
            *(
                Problem(
                    path,
                    f'holds "{line}" more than once, so the sync would fill each; '
                    "keep one",
                )
                for line in repeated
            ),
        ]

    def fill(self, description: SyncDescription) -> str:
        fills = {
            self.LEAD: description.lead,
            self.FEEDBACK: "| **Feedback wanted** | Whether to accept this copy as "
            "wording guidance for nustack |",
            self.CHECK: description.facts,
            self.RISK: "| **Risk** | The copy is untrusted. The owner clears each "
            "review finding; a passing check does not clear it. |",
            self.FILES: description.evidence,
            self.IDEA: "",
        }
        return "\n".join(fills.get(line, line) for line in self.head).rstrip() + "\n"

    def size_problems(self, body: str, copy: Path) -> list[Problem]:
        size = len(body.encode())
        if size <= self.MAX_BODY_BYTES:
            return []
        return [
            Problem(
                copy,
                f"the sync description of this copy is {size} bytes, over the"
                f" {self.MAX_BODY_BYTES} GitHub accepts; quote less in"
                " SyncDescription, or sync a smaller upstream change",
            )
        ]


def code(value: str) -> str:
    visible = "".join(
        char if char.isprintable() else repr(char)[1:-1] for char in value
    )
    # A code span cannot be empty and keeps its padding if it holds only
    # spaces: https://spec.commonmark.org/0.31.2/#code-spans
    if not visible.strip():
        return f"<code>{visible}</code>"
    longest = max((len(run) for run in re.findall(r"`+", visible)), default=0)
    fence = "`" * (longest + 1)
    return f"{fence} {visible} {fence}"


def fold(summary: str, items: Iterable[str]) -> str:
    rows = "\n".join(f"- {item}" for item in items)
    if not rows:
        return f"**{summary}.**"
    return f"<details>\n<summary>{summary}</summary>\n\n{rows}\n\n</details>"
