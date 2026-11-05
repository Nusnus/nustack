"""The sync reads, stages, commits, pushes and withdraws in real repositories.

The caller's Git settings sway none of it, and a failed command stops with a Problem
naming the fix.
"""

from pathlib import Path

import pytest

from nustack.git import GitError
from nustack.problem import Problem
from nustack.sync.change import Blob
from nustack.sync.git import CopyGit
from nustack.sync.history import Commit
from nustack.sync.history import History
from nustack.sync.tree import Mode
from tests.fixtures.git_repository import GitRepository
lazy from nustack.sha import Sha
lazy from tests.fixtures.sync.repositories import Sync


class TestCopyGit:
    """Answers from its own repository; the base is the newest first-parent copy.

    Without a match there is no commit range, a match only on a side branch is no
    base, a locally edited base reads from the checkout, and option-like or magic
    paths stay literal. Withdrawing deletes the branch once, and nothing where it is
    absent. A failed command, a remote or revision it cannot read, or a history Git
    names by other than SHA-1, stops with a Problem naming the fix.
    """

    @pytest.fixture
    def merged(self, sync: Sync) -> tuple[Sha, Sha]:
        repo = sync.upstream
        repo.git("switch", "-qc", "side", str(sync.first))
        repo.write(f"{sync.SOURCE_FOLDER}/SKILL.md", "only on side\n")
        side = repo.commit("side")
        repo.git("switch", "-q", "main")
        repo.git("merge", "--no-commit", "-s", "ours", "side")
        repo.write(f"{sync.SOURCE_FOLDER}/SKILL.md", "different from both parents\n")
        return side, repo.commit("merge")

    def test_finds_the_base_revision_and_reads_both_object_stores(
        self, sync: Sync
    ) -> None:
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        base = checkout_git.tree("HEAD", sync.FOLDER)
        history = upstream_git.history(upstream_git.head, sync.SOURCE_FOLDER, base)
        assert (history.copied, history.baseline, history.commits) == (
            sync.second,
            sync.first,
            (Commit(sync.second, "second"),),
        )
        changes = checkout_git.changes(
            base,
            upstream_git,
            upstream_git.tree(str(sync.second), sync.SOURCE_FOLDER, "LICENSE"),
        )
        assert [(change.path, change.before, change.after) for change in changes] == [
            ("SKILL.md", Blob(b"old\n", Mode.REGULAR), Blob(b"new\n", Mode.REGULAR)),
            ("tool", None, Blob(b"", Mode.EXECUTABLE)),
        ]

    def test_names_the_newest_revision_that_changed_the_copy(self, sync: Sync) -> None:
        sync.upstream.write("elsewhere", "not copied")
        sync.upstream.commit("unrelated")
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        history = upstream_git.history(
            upstream_git.head,
            sync.SOURCE_FOLDER,
            checkout_git.tree("HEAD", sync.FOLDER),
        )
        assert (history.copied, history.baseline, history.commits) == (
            sync.second,
            sync.first,
            (Commit(sync.second, "second"),),
        )

    def test_names_the_head_when_no_revision_changed_the_copy(
        self, tmp_path: Path
    ) -> None:
        repo = GitRepository.init(tmp_path / "upstream")
        repo.write("elsewhere", "not copied")
        head = repo.commit("unrelated")
        upstream_git = CopyGit(repo.root)
        history = upstream_git.history(
            head, "missing", upstream_git.tree(str(head), "missing")
        )
        assert (history.copied, history.baseline, history.commits) == (head, None, ())

    def test_gives_no_range_when_no_upstream_tree_matches(self, sync: Sync) -> None:
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        history = upstream_git.history(
            upstream_git.head, sync.SOURCE_FOLDER, checkout_git.tree("HEAD", "missing")
        )
        assert (history.copied, history.baseline, history.commits) == (
            sync.second,
            None,
            (),
        )

    def test_takes_a_match_on_main_before_a_merge_as_the_base(
        self, sync: Sync, merged: tuple[Sha, Sha]
    ) -> None:
        side, merge = merged
        upstream_git = CopyGit(sync.upstream.root)
        history = upstream_git.history(
            upstream_git.head,
            sync.SOURCE_FOLDER,
            upstream_git.tree(str(sync.second), sync.SOURCE_FOLDER, "LICENSE"),
        )
        assert (history.copied, history.baseline, history.commits) == (
            merge,
            sync.second,
            (Commit(merge, "merge"), Commit(side, "side")),
        )

    def test_takes_no_match_on_a_side_branch_as_a_copy_from_main(
        self, sync: Sync, merged: tuple[Sha, Sha]
    ) -> None:
        side, merge = merged
        upstream_git = CopyGit(sync.upstream.root)
        history = upstream_git.history(
            upstream_git.head,
            sync.SOURCE_FOLDER,
            upstream_git.tree(str(side), sync.SOURCE_FOLDER, "LICENSE"),
        )
        assert (history.copied, history.baseline, history.commits) == (merge, None, ())

    def test_takes_the_newest_revision_matching_the_copy_as_the_base(
        self, sync: Sync
    ) -> None:
        repo = sync.upstream
        repo.write(f"{sync.SOURCE_FOLDER}/SKILL.md", "old\n")
        repo.git("rm", "-q", f"{sync.SOURCE_FOLDER}/tool")
        reverted = repo.commit("revert")
        repo.write(f"{sync.SOURCE_FOLDER}/SKILL.md", "newer\n")
        tip = repo.commit("newer")
        upstream_git = CopyGit(repo.root)
        history = upstream_git.history(
            tip,
            sync.SOURCE_FOLDER,
            upstream_git.tree(str(sync.first), sync.SOURCE_FOLDER, "LICENSE"),
        )
        assert (history.baseline, history.commits) == (
            reverted,
            (Commit(tip, "newer"),),
        )

    def test_reads_a_history_git_names_by_sha1(self, tmp_path: Path) -> None:
        repository = GitRepository.init(tmp_path / "repository", object_format="sha1")
        repository.write("LICENSE", "MIT\n")
        tip = repository.commit("license")
        git = CopyGit(repository.root)
        assert git.history(
            tip, "skill", git.tree(str(tip), "skill", "LICENSE")
        ) == History(tip, None, ())

    def test_refuses_a_history_git_names_by_other_than_sha1(
        self, tmp_path: Path
    ) -> None:
        repository = GitRepository.init(tmp_path / "repository", object_format="sha256")
        repository.write("LICENSE", "MIT\n")
        # Git takes a SHA-256 name's first 40 digits as an abbreviation of it.
        tip = Sha(repository.record("license")[:40])
        git = CopyGit(repository.root)
        with pytest.raises(GitError) as caught:
            git.history(tip, "skill", git.tree(str(tip), "skill", "LICENSE"))
        assert caught.value.problem == Problem(
            repository.root,
            "git log named a commit by other than its SHA-1; nustack reads only"
            " repositories whose commits Git names by SHA-1, so use one",
        )

    def test_starts_the_history_at_the_matching_license_and_stops_at_the_pin(
        self, sync: Sync
    ) -> None:
        repo = sync.upstream
        repo.write("LICENSE", "first license change\n")
        baseline = repo.commit("license only")
        repo.write("elsewhere", "not copied")
        repo.commit("unrelated")
        repo.write("LICENSE", "proposed license\n")
        tip = repo.commit("proposed license")
        repo.write("LICENSE", "first license change\n")
        repo.commit("future revert")
        upstream_git = CopyGit(repo.root)
        history = upstream_git.history(
            tip,
            sync.SOURCE_FOLDER,
            upstream_git.tree(str(baseline), sync.SOURCE_FOLDER, "LICENSE"),
        )
        assert (history.copied, history.baseline, history.commits) == (
            tip,
            baseline,
            (Commit(tip, "proposed license"),),
        )

    def test_prefers_a_skill_license_to_the_root_license_even_in_a_magic_path(
        self, sync: Sync
    ) -> None:
        repo = sync.upstream
        repo.write(":(exclude)skill/LICENSE", "only for the skill\n")
        revision = repo.commit("skill license")
        upstream_git = CopyGit(repo.root)
        tree = upstream_git.tree(str(revision), ":(exclude)skill", "LICENSE")
        assert upstream_git.blob(tree.files["LICENSE"]) == Blob(
            b"only for the skill\n", Mode.REGULAR
        )

    def test_keeps_nested_blobs_under_an_option_like_folder_in_the_tree(
        self, sync: Sync
    ) -> None:
        sync.upstream.write("-skill/agents/settings", "policy\n")
        revision = sync.upstream.commit("nested settings")
        upstream_git = CopyGit(sync.upstream.root)
        tree = upstream_git.tree(str(revision), "-skill")
        assert upstream_git.blob(tree.files["agents/settings"]) == Blob(
            b"policy\n", Mode.REGULAR
        )

    def test_reads_a_locally_edited_base_from_the_checkout(self, sync: Sync) -> None:
        sync.checkout.write(f"{sync.FOLDER}/SKILL.md", "local\n")
        sync.checkout.commit("edit")
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        changes = checkout_git.changes(
            checkout_git.tree("HEAD", sync.FOLDER),
            upstream_git,
            upstream_git.tree(str(sync.second), sync.SOURCE_FOLDER, "LICENSE"),
        )
        assert [(change.path, change.before) for change in changes] == [
            ("SKILL.md", Blob(b"local\n", Mode.REGULAR)),
            ("tool", None),
        ]

    def test_stages_upstreams_copy_byte_for_byte_in_place_of_the_old_one(
        self, sync: Sync
    ) -> None:
        sync.checkout.write(f"{sync.FOLDER}/stale", "gone\n")
        sync.checkout.commit("stale")
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        checkout_git.stage(
            sync.FOLDER,
            upstream_git,
            upstream_git.tree("HEAD", sync.SOURCE_FOLDER, "LICENSE"),
        )
        checkout_git.stage(
            "-fresh",
            upstream_git,
            upstream_git.tree("HEAD", sync.SOURCE_FOLDER, "LICENSE"),
        )
        assert (
            checkout_git.run("ls-files", "-s").decode(),
            (sync.checkout.root / sync.FOLDER / "SKILL.md").read_text(),
        ) == (
            (
                "100644 a22a2da24d1ceeef3d0c2f1f4f68923f55b8d4cc 0\t-fresh/LICENSE\n"
                "100644 3e757656cf36eca53338e520d134963a44f793f8 0\t-fresh/SKILL.md\n"
                "100755 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 0\t-fresh/tool\n"
                "100644 a22a2da24d1ceeef3d0c2f1f4f68923f55b8d4cc 0\tcopy/LICENSE\n"
                "100644 3e757656cf36eca53338e520d134963a44f793f8 0\tcopy/SKILL.md\n"
                "100755 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 0\tcopy/tool\n"
            ),
            "old\n",
        )

    @pytest.mark.usefixtures("template")
    def test_finds_the_staged_copy_proposed_on_a_branch_from_the_base_alone(
        self, sync: Sync, remote_url: str
    ) -> None:
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        copy_tree = upstream_git.tree("HEAD", sync.SOURCE_FOLDER, "LICENSE")
        checkout_git.stage(sync.FOLDER, upstream_git, copy_tree)
        checkout_git.push(remote_url, "sync/w", "docs: sync", "Copies it.")
        sync.checkout.git("reset", "-q", "--soft", "HEAD~1")
        proposed = checkout_git.proposes(remote_url, "sync/w")
        sync.checkout.write(f"{sync.FOLDER}/SKILL.md", "newer\n")
        sync.checkout.git("add", f"{sync.FOLDER}/SKILL.md")
        restaged = checkout_git.proposes(remote_url, "sync/w")
        sync.checkout.git("commit", "-qm", "moved on")
        checkout_git.stage(sync.FOLDER, upstream_git, copy_tree)
        rebased = checkout_git.proposes(remote_url, "sync/w")
        assert (proposed, restaged, rebased) == (True, False, False)

    def test_pushes_the_staged_copy_as_the_bots_commit_on_the_base(
        self, sync: Sync, remote_url: str
    ) -> None:
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        base = checkout_git.head
        checkout_git.stage(
            sync.FOLDER,
            upstream_git,
            upstream_git.tree("HEAD", sync.SOURCE_FOLDER, "LICENSE"),
        )
        checkout_git.push(remote_url, "sync/w", "docs: sync", "Copies it.")
        pushed = checkout_git.run("log", "-1", "--format=%P%n%an <%ae>%n%B", "HEAD")
        remote_head = sync.checkout.git(
            "--git-dir", remote_url, "rev-parse", "refs/heads/sync/w"
        )
        assert (pushed.decode(), remote_head) == (
            (
                f"{base}\ngithub-actions[bot]"
                " <41898282+github-actions[bot]@users.noreply.github.com>\n"
                "docs: sync\n\nCopies it.\n\n"
            ),
            f"{checkout_git.head}\n",
        )

    def test_deletes_the_branch_from_the_remote_once(
        self, sync: Sync, remote_url: str
    ) -> None:
        checkout_git = CopyGit(sync.checkout.root)
        _ = checkout_git.run("push", remote_url, "HEAD:refs/heads/sync/w")
        checkout_git.withdraw(remote_url, "sync/w")
        checkout_git.withdraw(remote_url, "sync/w")
        assert checkout_git.run("ls-remote", remote_url) == b""

    def test_pushes_nothing_to_a_remote_without_the_branch(
        self, sync: Sync, remote_url: str
    ) -> None:
        checkout_git = CopyGit(sync.checkout.root)
        _ = checkout_git.run("push", remote_url, "HEAD:refs/heads/main")
        refusal = Path(remote_url) / "hooks" / "pre-receive"
        refusal.write_text("#!/bin/sh\nexit 1\n")
        refusal.chmod(0o755)
        checkout_git.withdraw(remote_url, "sync/w")
        assert checkout_git.run("ls-remote", remote_url) == (
            f"{checkout_git.head}\trefs/heads/main\n".encode()
        )

    def test_fails_to_delete_a_branch_from_a_remote_it_cannot_read(
        self, sync: Sync, tmp_path: Path
    ) -> None:
        with pytest.raises(GitError) as caught:
            CopyGit(sync.checkout.root).withdraw(str(tmp_path / "none"), "sync/w")
        assert caught.value.problem == Problem(
            sync.checkout.root,
            "git ls-remote exited 128; fix the cause Git"
            " printed above, such as a missing clone or revision",
        )

    def test_says_whether_the_staged_copy_differs_from_a_revision(
        self, sync: Sync
    ) -> None:
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        unchanged = checkout_git.staged()
        checkout_git.stage(
            sync.FOLDER,
            upstream_git,
            upstream_git.tree("HEAD", sync.SOURCE_FOLDER, "LICENSE"),
        )
        assert (unchanged, checkout_git.staged()) == (False, True)

    def test_fails_to_compare_with_a_revision_it_cannot_read(self, sync: Sync) -> None:
        with pytest.raises(GitError) as caught:
            CopyGit(sync.checkout.root).staged("missing")
        assert caught.value.problem == Problem(
            sync.checkout.root,
            "git diff exited 128; fix the cause Git printed"
            " above, such as a missing clone or revision",
        )
