"""The sync reads, stages, commits, pushes and withdraws in real repositories.

The caller's Git settings sway none of it, and a failed command stops with a Problem
naming the fix.
"""

from pathlib import Path
lazy from collections.abc import Mapping

import pytest

from nustack.git import GitError
from nustack.problem import Problem
from nustack.sha import Sha
from nustack.sync.change import Blob
from nustack.sync.git import CopyGit
from nustack.sync.history import Commit
from nustack.sync.history import History
from nustack.sync.tree import Mode
from tests.fixtures.git_repository import GitRepository
lazy from tests.fixtures.sync.repositories import Sync


class TestCopyGit:
    """Answers from its own repository; the base is the commit the record names.

    The copied commit is the newest first-parent commit that changes a copied file,
    counting the root LICENSE only while a skill copies it. A record naming no commit,
    or one the tip does not hold, gives no commit range, a
    locally edited base reads from the checkout, and option-like or magic paths stay
    literal. Staging writes the record of the commit and blobs it copied.
    Withdrawing deletes the branch once, and nothing where it is absent. A failed
    command, or a remote or revision it cannot read, stops with a Problem naming the
    fix.
    """

    def test_finds_the_base_revision_and_reads_both_object_stores(
        self, sync: Sync
    ) -> None:
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        history = upstream_git.history(upstream_git.head, sync.record)
        assert (history.copied, history.baseline, history.commits) == (
            sync.second,
            sync.first,
            (Commit(sync.second, "second"),),
        )
        changes = checkout_git.changes(
            checkout_git.tree("HEAD", [sync.COPY]),
            upstream_git,
            upstream_git.tree(str(sync.second), [sync.SOURCE_FOLDER], "LICENSE"),
        )
        assert [(change.path, change.before, change.after) for change in changes] == [
            ("s/SKILL.md", Blob(b"old\n", Mode.REGULAR), Blob(b"new\n", Mode.REGULAR)),
            ("s/tool", None, Blob(b"", Mode.EXECUTABLE)),
        ]

    def test_names_each_skill_under_the_source_the_record_does_not_list(
        self, sync: Sync
    ) -> None:
        sync.upstream.write(f"{sync.SOURCE}/new/SKILL.md", "new\n")
        sync.upstream.write(f"{sync.SOURCE}/README.md", "not a skill\n")
        sync.upstream.write(f"{sync.SOURCE}/notes/README.md", "no SKILL.md\n")
        sync.upstream.write(f"{sync.SOURCE}/Bad Name/SKILL.md", "no valid name\n")
        sync.upstream.write(f"{sync.SOURCE}/new/nested/SKILL.md", "nested\n")
        sync.upstream.write("elsewhere/SKILL.md", "outside the source\n")
        revision = sync.upstream.commit("add a skill")
        assert CopyGit(sync.upstream.root).new_skills(revision, sync.record) == ("new",)

    def test_names_no_skill_upstream_held_at_the_recorded_commit(
        self, sync: Sync
    ) -> None:
        sync.upstream.write(f"{sync.SOURCE}/kept/SKILL.md", "kept\n")
        recorded = sync.upstream.commit("add a skill the record leaves out")
        sync.upstream.write(f"{sync.SOURCE}/new/SKILL.md", "new\n")
        revision = sync.upstream.commit("add a skill")
        record = sync.record_of(recorded, sync.BASE)
        assert CopyGit(sync.upstream.root).new_skills(revision, record) == ("new",)

    @pytest.mark.parametrize(
        ("commit", "files"),
        [(None, {}), (Sha("d" * 40), {"LICENSE": b"MIT\n", "SKILL.md": b"old\n"})],
    )
    def test_names_every_unlisted_skill_without_a_commit_upstream_holds(
        self, sync: Sync, commit: Sha | None, files: Mapping[str, bytes]
    ) -> None:
        sync.upstream.write(f"{sync.SOURCE}/kept/SKILL.md", "kept\n")
        revision = sync.upstream.commit("add a skill")
        record = sync.record_of(commit, files)
        assert CopyGit(sync.upstream.root).new_skills(revision, record) == ("kept",)

    def test_skips_a_folder_whose_name_is_not_utf_8(self, sync: Sync) -> None:
        name = b"\xff".decode(errors="surrogateescape")
        sync.upstream.write(f"{sync.SOURCE}/{name}/SKILL.md", "new\n")
        revision = sync.upstream.commit("add a skill named in another encoding")
        assert CopyGit(sync.upstream.root).new_skills(revision, sync.record) == ()

    def test_names_each_new_skill_under_an_option_like_source(self, sync: Sync) -> None:
        sync.upstream.write("-up/new/SKILL.md", "new\n")
        revision = sync.upstream.commit("add an option-like source")
        record = sync.record_of(sync.first, sync.BASE, source="-up")
        assert CopyGit(sync.upstream.root).new_skills(revision, record) == ("new",)

    def test_names_the_newest_revision_that_changed_the_copy(self, sync: Sync) -> None:
        sync.upstream.write("elsewhere", "not copied")
        sync.upstream.commit("unrelated")
        upstream_git = CopyGit(sync.upstream.root)
        history = upstream_git.history(upstream_git.head, sync.record)
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
        history = upstream_git.history(head, Sync.record_of(None, {}))
        assert (history.copied, history.baseline, history.commits) == (head, None, ())

    def test_reads_a_history_git_names_by_sha1(self, tmp_path: Path) -> None:
        repository = GitRepository.init(tmp_path / "repository", object_format="sha1")
        repository.write("LICENSE", "MIT\n")
        tip = repository.commit("license")
        git = CopyGit(repository.root)
        assert git.history(tip, Sync.record_of(None, {})) == History(tip, None, ())

    def test_refuses_a_history_git_names_by_other_than_sha1(
        self, tmp_path: Path
    ) -> None:
        repository = GitRepository.init(tmp_path / "repository", object_format="sha256")
        repository.write("LICENSE", "MIT\n")
        # Git takes a SHA-256 name's first 40 digits as an abbreviation of it.
        tip = Sha(repository.record("license")[:40])
        git = CopyGit(repository.root)
        with pytest.raises(GitError) as caught:
            git.history(tip, Sync.record_of(None, {}))
        assert caught.value.problem == Problem(
            repository.root,
            "git log named a commit by other than its SHA-1; nustack reads only"
            " repositories whose commits Git names by SHA-1, so use one",
        )

    @pytest.mark.parametrize(
        ("commit", "files"),
        [(None, {}), (Sha("d" * 40), {"LICENSE": b"MIT\n", "SKILL.md": b"old\n"})],
    )
    def test_gives_no_range_for_a_record_naming_no_commit_upstream_holds(
        self, sync: Sync, commit: Sha | None, files: Mapping[str, bytes]
    ) -> None:
        upstream_git = CopyGit(sync.upstream.root)
        history = upstream_git.history(upstream_git.head, Sync.record_of(commit, files))
        assert (history.copied, history.baseline, history.commits) == (
            sync.second,
            None,
            (),
        )

    def test_gives_no_range_for_a_recorded_commit_the_tip_does_not_hold(
        self, sync: Sync
    ) -> None:
        repo = sync.upstream
        repo.git("switch", "-qc", "side", str(sync.first))
        repo.write(f"{sync.SOURCE_FOLDER}/SKILL.md", "only on side\n")
        side = repo.commit("side")
        repo.git("switch", "-q", "main")
        upstream_git = CopyGit(repo.root)
        history = upstream_git.history(
            upstream_git.head, Sync.record_of(side, Sync.BASE)
        )
        assert (history.copied, history.baseline, history.commits) == (
            sync.second,
            None,
            (),
        )

    def test_skips_a_root_license_change_once_each_skill_has_its_own(
        self, sync: Sync
    ) -> None:
        repo = sync.upstream
        repo.write(f"{sync.SOURCE_FOLDER}/LICENSE", "own\n")
        own = repo.commit("own license")
        repo.write("LICENSE", "root only\n")
        repo.commit("root license")
        upstream_git = CopyGit(repo.root)
        history = upstream_git.history(upstream_git.head, Sync.record_of(None, {}))
        assert history.copied == own

    def test_names_the_merge_that_brought_a_change_as_the_copied_commit(
        self, sync: Sync
    ) -> None:
        repo = sync.upstream
        repo.git("checkout", "-q", "-b", "side")
        repo.write(f"{sync.SOURCE_FOLDER}/SKILL.md", "side\n")
        repo.commit("side change")
        repo.git("checkout", "-q", "main")
        repo.write("other", "main\n")
        repo.commit("main change")
        repo.git("merge", "-q", "--no-ff", "-m", "merge side", "side")
        upstream_git = CopyGit(repo.root)
        history = upstream_git.history(upstream_git.head, Sync.record_of(None, {}))
        assert str(history.copied) == repo.git("rev-parse", "HEAD").strip()

    def test_starts_the_history_at_the_recorded_commit_and_stops_at_the_tip(
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
        history = upstream_git.history(tip, Sync.record_of(baseline, Sync.BASE))
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
        tree = upstream_git.tree(str(revision), [":(exclude)skill"], "LICENSE")
        assert upstream_git.blob(tree.files[":(exclude)skill/LICENSE"]) == Blob(
            b"only for the skill\n", Mode.REGULAR
        )

    def test_keeps_nested_blobs_under_an_option_like_folder_in_the_tree(
        self, sync: Sync
    ) -> None:
        sync.upstream.write("-skill/agents/settings", "policy\n")
        revision = sync.upstream.commit("nested settings")
        upstream_git = CopyGit(sync.upstream.root)
        tree = upstream_git.tree(str(revision), ["-skill"])
        assert upstream_git.blob(tree.files["-skill/agents/settings"]) == Blob(
            b"policy\n", Mode.REGULAR
        )

    def test_reads_a_locally_edited_base_from_the_checkout(self, sync: Sync) -> None:
        sync.checkout.write(f"{sync.COPY}/SKILL.md", "local\n")
        sync.checkout.commit("edit")
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        changes = checkout_git.changes(
            checkout_git.tree("HEAD", [sync.COPY]),
            upstream_git,
            upstream_git.tree(str(sync.second), [sync.SOURCE_FOLDER], "LICENSE"),
        )
        assert [(change.path, change.before) for change in changes] == [
            ("s/SKILL.md", Blob(b"local\n", Mode.REGULAR)),
            ("s/tool", None),
        ]

    def test_stages_upstreams_copy_byte_for_byte_beside_its_record(
        self, sync: Sync
    ) -> None:
        sync.checkout.write(f"{sync.COPY}/stale", "gone\n")
        sync.checkout.commit("stale")
        checkout_git, upstream_git = (
            CopyGit(sync.checkout.root),
            CopyGit(sync.upstream.root),
        )
        tree = upstream_git.tree("HEAD", [sync.SOURCE_FOLDER], "LICENSE")
        checkout_git.stage(sync.RECORD, sync.record, sync.second, upstream_git, tree)
        fresh = Sync.record_of(None, {}, folder="-fresh")
        checkout_git.stage(
            "vendored/-fresh.json", fresh, sync.second, upstream_git, tree
        )
        assert (
            checkout_git.run(
                "ls-files", "-s", "--", "-fresh", ".agents/skills"
            ).decode(),
            checkout_git.run("cat-file", "blob", f":{sync.RECORD}").decode(),
            checkout_git.run("cat-file", "blob", ":vendored/-fresh.json").decode(),
            (sync.checkout.root / sync.COPY / "SKILL.md").read_text(),
        ) == (
            (
                "100644 a22a2da24d1ceeef3d0c2f1f4f68923f55b8d4cc 0\t-fresh/s/LICENSE\n"
                "100644 3e757656cf36eca53338e520d134963a44f793f8 0\t-fresh/s/SKILL.md\n"
                "100755 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 0\t-fresh/s/tool\n"
                f"100644 a22a2da24d1ceeef3d0c2f1f4f68923f55b8d4cc 0"
                f"\t{Sync.COPY}/LICENSE\n"
                f"100644 3e757656cf36eca53338e520d134963a44f793f8 0"
                f"\t{Sync.COPY}/SKILL.md\n"
                f"100755 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 0"
                f"\t{Sync.COPY}/tool\n"
            ),
            (
                "{\n"
                '  "upstream": "https://github.com/up/skills",\n'
                '  "source": "skills*",\n'
                '  "folder": ".agents/skills",\n'
                '  "skills": [\n'
                '    "s"\n'
                "  ],\n"
                f'  "commit": "{sync.second}",\n'
                '  "files": {\n'
                '    "s/LICENSE": "a22a2da24d1ceeef3d0c2f1f4f68923f55b8d4cc",\n'
                '    "s/SKILL.md": "3e757656cf36eca53338e520d134963a44f793f8",\n'
                '    "s/tool": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"\n'
                "  }\n"
                "}\n"
            ),
            (
                "{\n"
                '  "upstream": "https://github.com/up/skills",\n'
                '  "source": "skills*",\n'
                '  "folder": "-fresh",\n'
                '  "skills": [\n'
                '    "s"\n'
                "  ],\n"
                f'  "commit": "{sync.second}",\n'
                '  "files": {\n'
                '    "s/LICENSE": "a22a2da24d1ceeef3d0c2f1f4f68923f55b8d4cc",\n'
                '    "s/SKILL.md": "3e757656cf36eca53338e520d134963a44f793f8",\n'
                '    "s/tool": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"\n'
                "  }\n"
                "}\n"
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
        copy_tree = upstream_git.tree("HEAD", [sync.SOURCE_FOLDER], "LICENSE")
        checkout_git.stage(
            sync.RECORD, sync.record, sync.second, upstream_git, copy_tree
        )
        checkout_git.push(remote_url, "sync/w", "docs: sync", "Copies it.")
        sync.checkout.git("reset", "-q", "--soft", "HEAD~1")
        proposed = checkout_git.proposes(remote_url, "sync/w")
        sync.checkout.write(f"{sync.COPY}/SKILL.md", "newer\n")
        sync.checkout.git("add", f"{sync.COPY}/SKILL.md")
        restaged = checkout_git.proposes(remote_url, "sync/w")
        sync.checkout.git("commit", "-qm", "moved on")
        checkout_git.stage(
            sync.RECORD, sync.record, sync.second, upstream_git, copy_tree
        )
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
            sync.RECORD,
            sync.record,
            sync.second,
            upstream_git,
            upstream_git.tree("HEAD", [sync.SOURCE_FOLDER], "LICENSE"),
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

    def test_fails_to_check_a_commit_in_a_folder_git_cannot_read(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(GitError) as caught:
            CopyGit(tmp_path).holds("d" * 40, "HEAD")
        assert caught.value.problem == Problem(
            tmp_path,
            "git rev-parse exited 128; fix the cause Git"
            " printed above, such as a missing clone or revision",
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
            sync.RECORD,
            sync.record,
            sync.second,
            upstream_git,
            upstream_git.tree("HEAD", [sync.SOURCE_FOLDER], "LICENSE"),
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
