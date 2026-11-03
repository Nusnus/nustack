"""Git, as the sync reads upstream's history and both copies, and lands the new copy.

It stages the copy from upstream's objects, byte for byte with each file's mode,
says whether the staged copy differs from the checkout's or from the one already
proposed on a branch, commits and pushes it, and deletes the branch of a proposal
it withdraws.
"""

from dataclasses import dataclass
from typing import ClassVar

from nustack.git import Git
from nustack.git import GitError
from nustack.sync.change import Blob
from nustack.sync.change import FileChange
from nustack.sync.history import Commit
from nustack.sync.history import History
from nustack.sync.tree import CopyTree
from nustack.sync.tree import GitEntry


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

    def history(self, tip: str, source_folder: str, base: CopyTree) -> History:
        paths = ("--", f"{source_folder}/", CopyTree.LICENSE)
        log = self.run("log", "--first-parent", "--format=%H", tip, *paths)
        revisions = log.decode().splitlines()
        copied = revisions[0] if revisions else tip
        baseline = base.newest_match(
            (sha, self.tree(sha, source_folder, CopyTree.LICENSE)) for sha in revisions
        )
        commits = ()
        if baseline is not None:
            log = self.run("log", "-z", "--format=%H %s", f"{baseline}..{tip}", *paths)
            commits = Commit.from_log(log)
        return History(copied, baseline, commits)

    def tree(self, revision: str, folder: str, *paths: str) -> CopyTree:
        listing = self.run("ls-tree", "-r", "-z", revision, "--", f"{folder}/", *paths)
        return CopyTree.from_listing(listing, folder)

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
    def stage(self, folder: str, upstream_git: CopyGit, copy_tree: CopyTree) -> None:
        self.run("rm", "-r", "--cached", "--ignore-unmatch", "--", f"{folder}/")
        for path, entry in copy_tree.files.items():
            blob = upstream_git.run("cat-file", "blob", entry.oid)
            stored = self.run("hash-object", "-w", "--stdin", stdin=blob)
            oid = stored.decode().strip()
            self.run(
                "update-index",
                "--add",
                "--cacheinfo",
                f"{entry.mode},{oid},{folder}/{path}",
            )

    def proposes(self, remote_url: str, branch: str) -> bool:
        self.run("fetch", remote_url, branch)
        parents = self.run("log", "-1", "--format=%P", "FETCH_HEAD").decode().split()
        return parents == [self.head] and not self.staged("FETCH_HEAD")

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
