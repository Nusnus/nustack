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
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import ClassVar
from typing import assert_never
from urllib.parse import quote
lazy from collections.abc import Iterable

from nustack.plugin.skill import Skill
from nustack.problem import Problem
from nustack.sync.change import Comparison
from nustack.sync.change import FileChange
from nustack.sync.tree import CopyTree
lazy from nustack.record import CopyRecord
lazy from nustack.sync.history import History


@dataclass(frozen=True)
class SyncLinks:
    """Trusted workflow links; copied text never supplies a Markdown destination."""

    run: str
    checks: str


class Colour(StrEnum):
    """A badge's colour, each with white text above WCAG's 4.5:1 contrast."""

    GREEN = "1f883d"
    AMBER = "9a6700"
    RED = "cf222e"
    GREY = "6e7781"


@dataclass(frozen=True)
class Badge:
    """A shields.io static badge whose alt text states its fact without the image."""

    label: str
    message: str
    colour: Colour

    @property
    def image(self) -> str:
        url = "https://img.shields.io/badge/{}-{}-{}?style=flat-square".format(
            *(
                quote(part.replace("-", "--").replace("_", "__"), safe="")
                for part in (self.label, self.message, self.colour)
            )
        )
        return f"![{self.label.capitalize()}: {self.message}]({url})"


@dataclass(frozen=True)
class SyncDescription:
    """Review facts about the two snapshots, never a verdict on the copied text."""

    NON_TEXT: ClassVar[str] = "a side contains NUL or is not UTF-8"
    NOT_COMPARED: ClassVar[str] = f"not compared ({NON_TEXT})"
    COPY_CHECK: ClassVar[str] = "- [Copy]({run}):"
    record_path: str
    links: SyncLinks
    record: CopyRecord
    history: History
    changes: tuple[FileChange, ...]
    new_skills: tuple[str, ...]

    @property
    def purpose(self) -> str:
        if self.record.in_plugin:
            return "ships in nustack's plugin to every user"
        return "steers how agents work on nustack"

    # writing-for-agents governs only wording; a plugin skill directs whatever its
    # description says it covers.
    @property
    def scope(self) -> str:
        if self.record.in_plugin:
            return "instructions beyond what each skill's description says it covers"
        return "instructions beyond wording"

    @property
    def headline(self) -> str:
        home = (
            "nustack's plugin"
            if self.record.in_plugin
            else "the skills for working on nustack"
        )
        skills = self.record.skills
        copied = skills[0] if len(skills) == 1 else f"{len(skills)} skills"
        return f"### Copy {copied} into {home}"

    @property
    def summary(self) -> str:
        copied = self.history.copied
        source_url = f"{self.record.upstream}/tree/{copied}/{self.record.source}"
        return (
            f"Copies [upstream at {copied.short}]({source_url}) for the owner to"
            f" review before it {self.purpose}."
        )

    @cached_property
    def watched(self) -> tuple[FileChange, ...]:
        return tuple(
            change
            for change in self.changes
            if change.policy or change.in_skill in (Skill.FILE, CopyTree.LICENSE)
        )

    @cached_property
    def loading(self) -> bool:
        return any(
            change.loading is not Comparison.UNCHANGED
            for change in self.watched
            if change.in_skill != CopyTree.LICENSE
        )

    @property
    def record_changes(self) -> bool:
        return self.history.baseline != self.history.copied or any(
            self.record.files.get(change.path)
            != (None if change.after is None else CopyRecord.blob(change.after.data))
            for change in self.changes
        )

    @property
    def rewritten_record(self) -> tuple[str, ...]:
        return (
            (
                (
                    f"{code(self.record_path)}: its commit and blobs, rewritten to"
                    " upstream's"
                ),
            )
            if self.record_changes
            else ()
        )

    @property
    def badges(self) -> str:
        files = len(self.changes) + len(self.rewritten_record)
        risk = ("high", Colour.RED) if self.loading else ("medium", Colour.AMBER)
        badges = (
            Badge("risk", *risk),
            Badge("checks", "1 passed, CI pending", Colour.AMBER),
            Badge("size", f"{files} file{'' if files == 1 else 's'}", Colour.GREY),
        )
        return " ".join(badge.image for badge in badges)

    @property
    def changed(self) -> str:
        counts = Counter(change.status for change in self.changes)
        if self.loading:
            terms = (
                "A field that decides when a skill loads changed or was not"
                " compared; the files list names each file"
            )
        elif any(self.terms_status(change) != "unchanged" for change in self.watched):
            terms = (
                "A license, frontmatter or policy file changed; the files list"
                " names each"
            )
        else:
            terms = None
        bullets = (
            (
                f"{counts['added']} added, {counts['changed']} changed and"
                f" {counts['removed']} removed against upstream's head"
            ),
            terms,
            self.provenance,
        )
        return "\n".join(f"- {bullet}" for bullet in bullets if bullet)

    def terms_status(self, change: FileChange) -> str:
        if change.in_skill == Skill.FILE:
            if change.frontmatter_comparison is Comparison.UNCHANGED:
                return "unchanged"
            return self.frontmatter_status(change)
        return change.status

    @property
    def review(self) -> str:
        return (
            f"- Whether to accept this copy, which {self.purpose}\n"
            f"- The whole diff, for {self.scope}, claims of authority or wider"
            " loading, which no check can decide\n"
            # Departs from the part on what to read first in
            # ../../../plugin/skills/principle-pr-descriptions/SKILL.md: AGENTS.md
            # has whoever accepts a sync add its changelog entry before the merge.
            "- Before the merge, whoever accepts the copy adds its changelog entry"
            " under Unreleased"
        )

    @cached_property
    def checks(self) -> str:
        counts = Counter(change.status for change in self.changes)
        return (
            f"{self.COPY_CHECK.format(run=self.links.run)} passed, {counts['added']}"
            f" added, {counts['changed']} changed and {counts['removed']} removed"
            f" against upstream's head, modes and {CopyTree.LICENSE} included\n"
            f"- [CI]({self.links.checks}): pending. Approve this pull request's"
            " workflows if prompted; the linked runs hold the results."
        )

    @cached_property
    def terms(self) -> str:
        licenses = "; ".join(
            f"{code(change.path)} {change.status}"
            for change in self.changes
            if change.in_skill == CopyTree.LICENSE
        )
        frontmatter = "; ".join(
            f"{code(change.path)} {self.frontmatter_status(change)}"
            for change in self.changes
            if change.in_skill == Skill.FILE
            and change.frontmatter_comparison is not Comparison.UNCHANGED
        )
        policy = "; ".join(
            f"{code(change.path)} {change.status}{self.loading_note(change.loading)}"
            for change in self.changes
            if change.policy
        )
        return listing(
            "Terms and loading",
            (
                f"{CopyTree.LICENSE}: {licenses or 'unchanged'}",
                f"{Skill.FILE} frontmatter: {frontmatter or 'unchanged'}",
                f"{FileChange.POLICIES} policy files: {policy or 'unchanged'}",
            ),
        )

    def frontmatter_status(self, change: FileChange) -> str:
        match change.frontmatter_comparison:
            case Comparison.CHANGED | Comparison.UNCHANGED as comparison:
                return comparison.value
            case Comparison.BINARY:
                return self.NOT_COMPARED
            case unexpected:
                assert_never(unexpected)

    @cached_property
    def provenance(self) -> str | None:
        baseline, copied = self.history.baseline, self.history.copied
        if baseline is None:
            return None
        if baseline == copied:
            return f"Restores each file and mode to upstream's {baseline.short}"
        compare = f"{self.record.upstream}/compare/{baseline}...{copied}"
        return (
            f"[Compare upstream from {baseline.short}, the commit the base's record"
            f" names, to {copied.short}]({compare})"
        )

    @cached_property
    def commits(self) -> str:
        title = f"Upstream commits touching the skills or repository {CopyTree.LICENSE}"
        if self.history.baseline is None:
            return listing(
                title,
                ("Unknown: the base's record names no commit upstream's head holds",),
            )
        upstream_url = self.record.upstream
        return listing(
            f"{title} ({len(self.history.commits)})",
            (
                f"[`{commit.sha.short}`]({upstream_url}/commit/{commit.sha}) "
                f"{code(commit.subject)}"
                for commit in self.history.commits
            ),
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
        # Departs from the fold's files in reading order in
        # ../../../plugin/skills/principle-pr-descriptions/SKILL.md and the fold look in
        # ../../../.github/pull_request_template.md. The template's Files part is headed
        # Evidence, as the fold's summary names it, since it holds more than files. It
        # lists every file the size badge counts, the copy's in path order and then the
        # record when the sync rewrites it, each path in a code span. Beside them it
        # holds the terms, upstream commits, new upstream skills, links and lines the
        # scans found, and what those scans miss, quoting each commit subject and line
        # whole however long. REVIEW.md has a sync's review start from its files, links
        # and quoted lines, and none of the copy is nustack's to read first; the terms,
        # commits and new skills say what changed in kind and why, and the scan notes
        # what those lists miss, so each sits beside the lists; and a cut path, subject
        # or line could hide what an untrusted text directs.
        return "\n\n".join(
            (
                self.terms,
                self.commits,
                listing(f"Changed files under the copy ({len(files)})", files),
                *(
                    (
                        listing(
                            f"The copy's record ({len(self.rewritten_record)})",
                            self.rewritten_record,
                        ),
                    )
                    if self.rewritten_record
                    else ()
                ),
                listing(
                    f"New upstream skills the record does not list"
                    f" ({len(self.new_skills)})",
                    map(code, self.new_skills),
                ),
                listing(
                    f"New outside CommonMark targets by file ({len(links)})", links
                ),
                listing(f"Lines to inspect ({len(lines)}; - base, + copy)", lines),
                listing(
                    "How the scans read",
                    (
                        (
                            "Links: net new link and image targets per file, as"
                            " CommonMark parses them"
                        ),
                        (
                            "Links miss raw HTML, bare URLs, email addresses and"
                            " rejected URI schemes, which only the diff shows"
                        ),
                        (
                            f"Lines: every edit in {Skill.FILE} frontmatter and"
                            f" {FileChange.POLICIES}"
                        ),
                        (
                            "Lines: added lines naming rules, invocation fields,"
                            " selected commands or HTTP(S) URLs"
                        ),
                        "Both scans skip binary comparisons",
                    ),
                ),
            )
        )

    @classmethod
    def differs_beyond_the_run(cls, current: str, proposed: str) -> bool:
        return cls.beyond_the_run(current) != cls.beyond_the_run(proposed)

    @classmethod
    def beyond_the_run(cls, body: str) -> str:
        before, after = (re.escape(part) for part in cls.COPY_CHECK.split("{run}"))
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
                return ", and a loading field changed"
            case Comparison.BINARY:
                return f", {cls.NOT_COMPARED}"
            case unexpected:
                assert_never(unexpected)


@dataclass(frozen=True)
class SyncTemplate:
    """Fills the PR template's exact line anchors with a sync description's parts.

    Each anchor is replaced once, so quoted evidence stays data, and a lost or
    repeated anchor, or a body too large for GitHub, is a Problem. The parts a
    sync has none of, with any heading they leave empty, drop out.
    """

    PATH: ClassVar[Path] = Path(".github/pull_request_template.md")
    HEADLINE: ClassVar[str] = "### <!-- Headline -->"
    SUMMARY: ClassVar[str] = "<!-- What the change does for its reader -->"
    BADGES: ClassVar[str] = "<!-- Badges -->"
    CHANGES: ClassVar[str] = "<!-- Changes -->"
    RISK: ClassVar[str] = "<!-- Risk -->"
    REVIEW: ClassVar[str] = "<!-- Review -->"
    FOLD: ClassVar[str] = "<summary><!-- Fold summary --></summary>"
    CHECKS: ClassVar[str] = "<!-- Checks -->"
    FILES_HEADING: ClassVar[str] = "#### Files"
    FILES: ClassVar[str] = "<!-- Files -->"
    ANCHORS: ClassVar[tuple[str, ...]] = (
        HEADLINE,
        SUMMARY,
        BADGES,
        CHANGES,
        RISK,
        REVIEW,
        FOLD,
        CHECKS,
        FILES_HEADING,
        FILES,
    )
    UNUSED: ClassVar[tuple[str, ...]] = (
        "<sub>Closes #<!-- issue --></sub>",
        "- [ ] <!-- step -->",
        "<!-- Decisions -->",
    )
    HEADING: ClassVar[str] = "#### "
    # The template opens on a comment that guides whoever writes a description;
    # the sync's description drops it.
    GUIDE: ClassVar[str] = "<!--\n"
    GUIDE_END: ClassVar[str] = "-->\n"
    # GitHub's docs name no limit, yet creating a pull request with a body over
    # 65,536 characters fails with "Body is too long (maximum is 65536
    # characters)", as https://github.com/gerchowl/flock/issues/2810 records.
    # Counting bytes stays under it, since no character is under one byte.
    MAX_BODY_BYTES: ClassVar[int] = 65_536
    text: str

    @cached_property
    def lines(self) -> tuple[str, ...]:
        text = self.text.replace("\r\n", "\n")
        if text.startswith(self.GUIDE):
            text = text.partition(self.GUIDE_END)[2]
        return tuple(text.split("\n"))

    @cached_property
    def shape(self) -> tuple[str, ...]:
        kept = [line for line in self.lines if line not in self.UNUSED]
        shaped = [
            line
            for index, line in enumerate(kept)
            if not (
                line.startswith(self.HEADING) and self.ends_empty(kept[index + 1 :])
            )
        ]
        return tuple(
            line
            for index, line in enumerate(shaped)
            if line or index == 0 or shaped[index - 1]
        )

    def ends_empty(self, rest: list[str]) -> bool:
        following = next((line for line in rest if line), "")
        return following in ("", "<details>", "</details>") or following.startswith(
            self.HEADING
        )

    def problems(self, path: Path) -> list[Problem]:
        missing = [line for line in self.ANCHORS if line not in self.lines]
        repeated = [line for line in self.ANCHORS if self.lines.count(line) > 1]
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
            self.HEADLINE: description.headline,
            self.SUMMARY: description.summary,
            self.BADGES: description.badges,
            self.CHANGES: description.changed,
            self.RISK: "A bad copy can change how agents follow these skills; reverting"
            " this pull request restores the last copy.",
            self.REVIEW: description.review,
            self.FOLD: "<summary>Checks and evidence</summary>",
            self.CHECKS: description.checks,
            self.FILES_HEADING: "#### Evidence",
            self.FILES: description.evidence,
        }
        return "\n".join(fills.get(line, line) for line in self.shape).strip() + "\n"

    def size_problems(self, body: str, copy_folder: Path) -> list[Problem]:
        size = len(body.encode())
        if size <= self.MAX_BODY_BYTES:
            return []
        return [
            Problem(
                copy_folder,
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


def listing(title: str, items: Iterable[str]) -> str:
    rows = "\n".join(f"- {item}" for item in items)
    return f"##### {title}\n\n{rows or 'None.'}"
