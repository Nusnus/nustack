"""Git, as the sync reads upstream's history and both copies, and lands the new copy.

It stages the copy from upstream's objects, byte for byte with each file's mode,
beside the record of the commit and blobs it copied, says whether the staged copy
differs from the checkout's or from the one already proposed on a branch, commits
and pushes it, and deletes the branch of a proposal it withdraws.
"""

import re
from dataclasses import dataclass
from typing import ClassVar
lazy from collections.abc import Callable
lazy from collections.abc import Iterable

from nustack.git import Git
from nustack.git import GitError
from nustack.plugin.skill import Skill
from nustack.sha import Sha
from nustack.sync.change import Blob
from nustack.sync.change import FileChange
from nustack.sync.history import Commit
from nustack.sync.history import History
from nustack.sync.tree import CopyTree
from nustack.sync.tree import GitEntry
from nustack.sync.tree import Mode
from nustack.validation import Pattern
lazy from nustack.record import CopyRecord


@dataclass(frozen=True)
class CopyGit(Git):
    """Reads both copies' Git objects; stages, commits, pushes and withdraws a copy."""

    # These variables set the commit's author and committer over any the caller
    # exports or configures:
    # https://git-scm.com/docs/git-commit-tree#_commit_information
    BOT: ClassVar[frozendict[str, str]] = frozendict(
        {
            f"GIT_{role}_{field}": value
            for role in ("AUTHOR", "COMMITTER")
            for field, value in {
                "NAME": "github-actions[bot]",
                "EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
            }.items()
        }
    )

    # The root LICENSE counts only while a skill copies it, lacking its own.
    def history(self, tip: Sha, record: CopyRecord) -> History:
        own = self.tree(str(tip), record.upstream_folders).files
        borrowed = any(
            f"{skill}/{CopyTree.LICENSE}" not in own for skill in record.skills
        )
        paths = (
            "--",
            *(f"{folder}/" for folder in record.upstream_folders),
            *((CopyTree.LICENSE,) if borrowed else ()),
        )
        revisions = self.read_log(
            lambda log: [Sha(name) for name in log.decode().splitlines()],
            "--first-parent",
            "-1",
            "--format=%H",
            str(tip),
            *paths,
        )
        match revisions:
            case [newest]:
                copied = newest
            case _:
                copied = tip
        baseline = record.commit
        if baseline is None or not self.holds(str(baseline), str(tip)):
            return History(copied, None, ())
        commits = self.read_log(
            Commit.from_log, "-z", "--format=%H %s", f"{baseline}..{tip}", *paths
        )
        return History(copied, baseline, commits)

    def read_log[T](self, parse: Callable[[bytes], T], *args: str) -> T:
        log = self.run("log", *args)
        with self.naming_by_sha("git log"):
            return parse(log)

    def head_tree(self, record: CopyRecord) -> CopyTree:
        return self.tree("HEAD", record.upstream_folders, CopyTree.LICENSE)

    def tree(self, revision: str, folders: Iterable[str], *paths: str) -> CopyTree:
        folders = tuple(folders)
        listing = self.run(
            "ls-tree", "-r", "-z", revision, "--", *(f"{f}/" for f in folders), *paths
        )
        return CopyTree.from_listing(listing, folders)

    # A skill upstream held at the recorded commit is one the record leaves out
    # on purpose, so only one added since is new. That commit is the newest that
    # changed the copy, so a skill added after it stays new on every run until a
    # sync records a later one. A record before its first sync, or whose commit
    # upstream no longer holds, has no such commit, so every skill it does not list
    # is new.
    def new_skills(self, revision: Sha, record: CopyRecord) -> tuple[str, ...]:
        known = (
            self.skills(str(record.commit), record)
            if record.commit is not None
            and self.holds(str(record.commit), str(revision))
            else ()
        )
        return tuple(
            name
            for name in self.skills(str(revision), record)
            if name not in record.skills and name not in known
        )

    # rev-parse --verify --quiet exits 1, printing nothing, when the commit is
    # absent: https://git-scm.com/docs/git-rev-parse#Documentation/git-rev-parse.txt---verify
    def holds(self, commit: str, tip: str) -> bool:
        match self.status(
            "rev-parse",
            "--verify",
            "--quiet",
            f"{commit}^{{commit}}",
        ):
            case 0:
                return self.is_ancestor(commit, tip)
            case 1:
                return False
            case status:
                raise GitError(self.failure("rev-parse", status))

    # Only a folder holding a SKILL.md, under a name a record may list, is a skill
    # the record could copy.
    def skills(self, revision: str, record: CopyRecord) -> tuple[str, ...]:
        listing = self.run(
            "ls-tree", "-r", "-z", "--name-only", revision, "--", f"{record.source}/"
        )
        return tuple(
            name
            for path in listing.decode(errors="surrogateescape").split("\0")
            for name, *rest in [path.removeprefix(f"{record.source}/").split("/")]
            if rest == [Skill.FILE] and re.fullmatch(Pattern.NAME.unanchored, name)
        )

    def changes(
        self, base: CopyTree, upstream_git: CopyGit, proposed: CopyTree
    ) -> tuple[FileChange, ...]:
        return tuple(
            FileChange(
                path,
                self.blob(base.files.get(path)),
                upstream_git.blob(proposed.files.get(path)),
            )
            for path in base.changed_paths(proposed)
        )

    def blob(self, entry: GitEntry | None) -> Blob | None:
        return (
            None
            if entry is None
            else Blob(self.run("cat-file", "blob", entry.oid), entry.mode)
        )

    # hash-object stores standard input as given, with no attribute or filter, and
    # update-index stages the object without a checkout, so no byte changes:
    # https://git-scm.com/docs/git-hash-object#Documentation/git-hash-object.txt---no-filters
    def stage(
        self,
        record_path: str,
        record: CopyRecord,
        commit: Sha,
        upstream_git: CopyGit,
        copy_tree: CopyTree,
    ) -> None:
        for folder in record.skill_folders:
            self.run("rm", "-r", "--cached", "--ignore-unmatch", "--", f"{folder}/")
        blobs: dict[str, str] = {}
        for path, entry in copy_tree.files.items():
            blobs[path] = entry.oid
            self.add(
                f"{record.folder}/{path}",
                entry.mode,
                upstream_git.run("cat-file", "blob", entry.oid),
            )
        copied = record.copied(commit, frozendict(blobs))
        self.add(record_path, Mode.REGULAR, copied.text.encode())

    def add(self, path: str, mode: Mode, blob: bytes) -> None:
        stored = self.run("hash-object", "-w", "--stdin", stdin=blob)
        oid = stored.decode().strip()
        self.run("update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}")

    def proposes(self, remote_url: str, branch: str) -> bool:
        self.run("fetch", remote_url, branch)
        parents = self.run("log", "-1", "--format=%P", "FETCH_HEAD").decode().split()
        return parents == [str(self.head)] and not self.staged("FETCH_HEAD")

    def push(self, remote_url: str, branch: str, title: str, body: str) -> None:
        self.run("commit", "-m", title, "-m", body, environment=self.BOT)
        self.run("push", "--force", remote_url, f"HEAD:refs/heads/{branch}")

    # ls-remote --exit-code exits 2 when no ref matches:
    # https://git-scm.com/docs/git-ls-remote
    def withdraw(self, remote_url: str, branch: str) -> None:
        ref = f"refs/heads/{branch}"
        match self.status("ls-remote", "--exit-code", remote_url, ref):
            case 0:
                self.run("push", remote_url, "--delete", ref)
            case 2:
                pass
            case status:
                raise GitError(self.failure("ls-remote", status))

    # diff --quiet exits 1 when the trees differ: https://git-scm.com/docs/git-diff
    def staged(self, against: str = "HEAD") -> bool:
        match self.status("diff", "--cached", "--quiet", against):
            case 0:
                return False
            case 1:
                return True
            case status:
                raise GitError(self.failure("diff", status))
