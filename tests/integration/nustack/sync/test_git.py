"""The sync reads its evidence from real repositories, unswayed by the caller's Git.

A failed command or a missing clone stops with a Problem naming the fix.
"""

lazy from pathlib import Path

import pytest

from nustack.git import GitError
from nustack.sync.change import Blob
from nustack.sync.git import CopyGit
from nustack.sync.history import Commit
from nustack.sync.tree import Mode
lazy from tests.fixtures.sync.git_repository import GitRepository
lazy from tests.fixtures.sync.git_repository import Sync


class TestGit:
    """Answers from its own repository; the base is the newest first-parent copy.

    Without a match there is no commit range, a match only on a side branch is no
    base, a locally edited base reads from the checkout, and option-like or magic
    paths stay literal. A failed command, a missing clone or a revision it cannot
    read stops with a Problem naming the fix.
    """

    @pytest.mark.usefixtures("template")
    def test_finds_the_staged_copy_proposed_on_a_branch_from_the_base_alone(
        self, sync: Sync, remote: str
    ) -> None:
        checkout, upstream = CopyGit(sync.checkout.root), CopyGit(sync.upstream.root)
        copy = upstream.tree("HEAD", sync.SOURCE, "LICENSE")
        checkout.stage(sync.FOLDER, upstream, copy)
        checkout.push(remote, "sync/w", "docs: sync", "Copies it.")
        sync.checkout.git("reset", "-q", "--soft", "HEAD~1")
        proposed = checkout.proposes(remote, "sync/w")
        sync.checkout.write(f"{sync.FOLDER}/SKILL.md", "newer\n")
        sync.checkout.git("add", f"{sync.FOLDER}/SKILL.md")
        restaged = checkout.proposes(remote, "sync/w")
        sync.checkout.git("commit", "-qm", "moved on")
        checkout.stage(sync.FOLDER, upstream, copy)
        rebased = checkout.proposes(remote, "sync/w")
        assert (proposed, restaged, rebased) == (True, False, False)

    def test_finds_the_base_revision_and_reads_both_object_stores(
        self, sync: Sync
    ) -> None:
        checkout, upstream = CopyGit(sync.checkout.root), CopyGit(sync.upstream.root)
        base = checkout.tree("HEAD", sync.FOLDER)
        history = upstream.history(upstream.head, sync.SOURCE, base)
        assert (history.copied, history.baseline, history.commits) == (
            sync.second,
            sync.first,
            (Commit(sync.second, "second"),),
        )
        changes = checkout.changes(
            base, upstream, upstream.tree(sync.second, sync.SOURCE, "LICENSE")
        )
        assert [(change.path, change.before, change.after) for change in changes] == [
            ("SKILL.md", Blob(b"old\n", Mode.REGULAR), Blob(b"new\n", Mode.REGULAR)),
            ("tool", None, Blob(b"", Mode.EXECUTABLE)),
        ]

    def test_reads_a_locally_edited_base_from_the_checkout(self, sync: Sync) -> None:
        sync.checkout.write(f"{sync.FOLDER}/SKILL.md", "local\n")
        sync.checkout.commit("edit")
        checkout, upstream = CopyGit(sync.checkout.root), CopyGit(sync.upstream.root)
        changes = checkout.changes(
            checkout.tree("HEAD", sync.FOLDER),
            upstream,
            upstream.tree(sync.second, sync.SOURCE, "LICENSE"),
        )
        assert [(change.path, change.before) for change in changes] == [
            ("SKILL.md", Blob(b"local\n", Mode.REGULAR)),
            ("tool", None),
        ]

    def test_names_the_newest_revision_that_changed_the_copy(self, sync: Sync) -> None:
        sync.upstream.write("elsewhere", "not copied")
        sync.upstream.commit("unrelated")
        checkout, upstream = CopyGit(sync.checkout.root), CopyGit(sync.upstream.root)
        history = upstream.history(
            upstream.head, sync.SOURCE, checkout.tree("HEAD", sync.FOLDER)
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
        upstream = CopyGit(repo.root)
        history = upstream.history(head, "missing", upstream.tree(head, "missing"))
        assert (history.copied, history.baseline, history.commits) == (head, None, ())

    def test_without_a_match_it_does_not_invent_a_commit_range(
        self, sync: Sync
    ) -> None:
        checkout, upstream = CopyGit(sync.checkout.root), CopyGit(sync.upstream.root)
        history = upstream.history(
            upstream.head, sync.SOURCE, checkout.tree("HEAD", "missing")
        )
        assert (history.copied, history.baseline, history.commits) == (
            sync.second,
            None,
            (),
        )

    def test_takes_a_match_on_main_before_a_merge_as_the_base(self, sync: Sync) -> None:
        repo = sync.upstream
        repo.git("switch", "-qc", "side", sync.first)
        repo.write(f"{sync.SOURCE}/SKILL.md", "only on side\n")
        side = repo.commit("side")
        repo.git("switch", "-q", "main")
        repo.git("merge", "--no-commit", "-s", "ours", "side")
        repo.write(f"{sync.SOURCE}/SKILL.md", "different from both parents\n")
        merge = repo.commit("merge")
        upstream = CopyGit(repo.root)
        history = upstream.history(
            upstream.head,
            sync.SOURCE,
            upstream.tree(sync.second, sync.SOURCE, "LICENSE"),
        )
        assert (history.copied, history.baseline, history.commits) == (
            merge,
            sync.second,
            (Commit(merge, "merge"), Commit(side, "side")),
        )

    def test_takes_no_match_on_a_side_branch_as_a_copy_from_main(
        self, sync: Sync
    ) -> None:
        repo = sync.upstream
        repo.git("switch", "-qc", "side", sync.first)
        repo.write(f"{sync.SOURCE}/SKILL.md", "only on side\n")
        side = repo.commit("side")
        repo.git("switch", "-q", "main")
        repo.git("merge", "--no-commit", "-s", "ours", "side")
        repo.write(f"{sync.SOURCE}/SKILL.md", "different from both parents\n")
        merge = repo.commit("merge")
        upstream = CopyGit(repo.root)
        history = upstream.history(
            upstream.head, sync.SOURCE, upstream.tree(side, sync.SOURCE, "LICENSE")
        )
        assert (history.copied, history.baseline, history.commits) == (merge, None, ())

    def test_takes_the_newest_revision_matching_the_copy_as_the_base(
        self, sync: Sync
    ) -> None:
        repo = sync.upstream
        repo.write(f"{sync.SOURCE}/SKILL.md", "old\n")
        repo.git("rm", "-q", f"{sync.SOURCE}/tool")
        reverted = repo.commit("revert")
        repo.write(f"{sync.SOURCE}/SKILL.md", "newer\n")
        tip = repo.commit("newer")
        upstream = CopyGit(repo.root)
        history = upstream.history(
            tip, sync.SOURCE, upstream.tree(sync.first, sync.SOURCE, "LICENSE")
        )
        assert (history.baseline, history.commits) == (
            reverted,
            (Commit(tip, "newer"),),
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
        upstream = CopyGit(repo.root)
        history = upstream.history(
            tip, sync.SOURCE, upstream.tree(baseline, sync.SOURCE, "LICENSE")
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
        upstream = CopyGit(repo.root)
        tree = upstream.tree(revision, ":(exclude)skill", "LICENSE")
        assert upstream.blob(tree.files["LICENSE"]) == Blob(
            b"only for the skill\n", Mode.REGULAR
        )

    def test_keeps_nested_blobs_under_an_option_like_folder_in_the_tree(
        self, sync: Sync
    ) -> None:
        sync.upstream.write("-skill/agents/settings", "policy\n")
        revision = sync.upstream.commit("nested settings")
        upstream = CopyGit(sync.upstream.root)
        tree = upstream.tree(revision, "-skill")
        assert upstream.blob(tree.files["agents/settings"]) == Blob(
            b"policy\n", Mode.REGULAR
        )

    def test_stages_upstreams_copy_byte_for_byte_in_place_of_the_old_one(
        self, sync: Sync
    ) -> None:
        sync.checkout.write(f"{sync.FOLDER}/stale", "gone\n")
        sync.checkout.commit("stale")
        checkout, upstream = CopyGit(sync.checkout.root), CopyGit(sync.upstream.root)
        checkout.stage(
            sync.FOLDER, upstream, upstream.tree("HEAD", sync.SOURCE, "LICENSE")
        )
        checkout.stage(
            "-fresh", upstream, upstream.tree("HEAD", sync.SOURCE, "LICENSE")
        )
        assert (
            checkout.run("ls-files", "-s").decode(),
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

    def test_says_whether_the_staged_copy_differs_from_a_revision(
        self, sync: Sync
    ) -> None:
        checkout, upstream = CopyGit(sync.checkout.root), CopyGit(sync.upstream.root)
        unchanged = checkout.staged()
        checkout.stage(
            sync.FOLDER, upstream, upstream.tree("HEAD", sync.SOURCE, "LICENSE")
        )
        assert (unchanged, checkout.staged()) == (False, True)

    def test_fails_to_compare_with_a_revision_it_cannot_read(self, sync: Sync) -> None:
        with pytest.raises(GitError) as failed:
            CopyGit(sync.checkout.root).staged("missing")
        assert str(failed.value) == (
            f"{sync.checkout.root}: git diff exited 128; fix the cause Git printed"
            " above, such as a missing clone or revision"
        )

    def test_pushes_the_staged_copy_as_the_bots_commit_on_the_base(
        self, sync: Sync, remote: str
    ) -> None:
        checkout, upstream = CopyGit(sync.checkout.root), CopyGit(sync.upstream.root)
        base = checkout.head
        checkout.stage(
            sync.FOLDER, upstream, upstream.tree("HEAD", sync.SOURCE, "LICENSE")
        )
        checkout.push(remote, "sync/w", "docs: sync", "Copies it.")
        pushed = CopyGit(sync.checkout.root).run(
            "log", "-1", "--format=%P%n%an <%ae>%n%B", "HEAD"
        )
        remote_head = sync.checkout.git(
            "--git-dir", remote, "rev-parse", "refs/heads/sync/w"
        )
        assert (pushed.decode(), remote_head) == (
            (
                f"{base}\ngithub-actions[bot]"
                " <41898282+github-actions[bot]@users.noreply.github.com>\n"
                "docs: sync\n\nCopies it.\n\n"
            ),
            f"{checkout.head}\n",
        )
