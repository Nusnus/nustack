"""Git answers from the repository it was given, whatever the caller's Git points at.

It says whether one commit is an ancestor of another, whether the clone holds a
commit, which paths changed since one and which untracked paths it ignores, passes
input and options through, and a failed command, a command that outlasts its time
limit, a missing repository or a head Git names by other than its SHA-1 stops with a
Problem naming the fix.
"""

import os
from pathlib import PurePosixPath
lazy from pathlib import Path

import pytest

from nustack.git import Git
from nustack.git import GitError
from nustack.problem import Problem
from nustack.sha import Sha
from tests.fixtures.git_repository import GitRepository
lazy from tests.fixtures.sync.repositories import Sync


class TestGit:
    """Answers from its own repository, and fails with a Problem naming the fix.

    A listing of the variables Git calls local that outlasts its time limit stops, and
    the caller's other variables reach Git. A head Git names by other than its SHA-1
    fails. Git tells an ancestor from a commit that is not one, and a revision an
    ancestry check cannot read fails. Git tells a commit the clone holds from one it
    lacks, failing outside a repository, reads a file at a commit, or none where the
    commit lacks it, failing outside a repository, and lists each path changed since a
    commit, staged, unstaged, moved or untracked, whatever bytes name it, but those it
    ignores. It lists each untracked path it ignores, by a .gitignore, .git/info/exclude
    or the user's excludes file and whatever bytes name it, a folder it ignores as one
    path, and no tracked path, however it matches. run gives Git no input by default,
    passes input and variables, and fails naming the next step; status returns the exit
    status, also giving no input by default. A missing repository, and a fetch, push,
    remote listing, blob read or commit that outlasts its time limit, fails naming the
    fix.
    """

    @pytest.mark.usefixtures("stalling")
    def test_stops_a_listing_of_local_variables_that_outlasts_its_time_limit(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(GitError) as caught:
            _ = Git(tmp_path, timeout=0.1).environment
        assert caught.value.problem == Problem(
            tmp_path,
            "git rev-parse took over 0.1 seconds; check what Git waits on, such as"
            " its disk or a hook, then rerun",
        )

    def test_keeps_each_variable_git_does_not_list_as_local(
        self, sync: Sync, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GIT_DIR", "elsewhere")
        monkeypatch.setenv("GIT_OBJECT_DIRECTORY", "elsewhere")
        monkeypatch.setenv("NUSTACK_CANARY", "kept")
        environment = Git(sync.upstream.root).environment
        assert (
            {"GIT_DIR", "GIT_OBJECT_DIRECTORY"} & environment.keys(),
            environment["NUSTACK_CANARY"],
        ) == (set(), "kept")

    def test_reads_its_own_repository_when_the_caller_points_git_elsewhere(
        self, sync: Sync, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GIT_DIR", str(sync.checkout.root / ".git"))
        assert Git(sync.upstream.root).head == sync.second

    def test_reads_a_head_git_names_by_its_sha1(self, tmp_path: Path) -> None:
        repository = GitRepository.init(tmp_path / "repository", object_format="sha1")
        repository.write("LICENSE", "MIT\n")
        head = repository.commit("first")
        assert Git(repository.root).head == head

    def test_refuses_a_head_git_names_by_other_than_its_sha1(
        self, tmp_path: Path
    ) -> None:
        repository = GitRepository.init(tmp_path / "repository", object_format="sha256")
        repository.write("LICENSE", "MIT\n")
        repository.record("first")
        with pytest.raises(GitError) as caught:
            _ = Git(repository.root).head
        assert caught.value.problem == Problem(
            repository.root,
            "git rev-parse named a commit by other than its SHA-1; nustack reads only"
            " repositories whose commits Git names by SHA-1, so use one",
        )

    def test_tells_an_ancestor_from_a_commit_that_is_not_one(self, sync: Sync) -> None:
        git = Git(sync.upstream.root)
        assert (
            git.is_ancestor(str(sync.first), str(sync.second)),
            git.is_ancestor(str(sync.second), str(sync.first)),
        ) == (True, False)

    def test_fails_an_ancestry_check_on_a_revision_it_cannot_read(
        self, sync: Sync
    ) -> None:
        with pytest.raises(GitError) as caught:
            _ = Git(sync.upstream.root).is_ancestor("HEAD", "origin/main")
        assert caught.value.problem == Problem(
            sync.upstream.root,
            "git merge-base exited 128; fix the cause Git"
            " printed above, such as a missing clone or revision",
        )

    def test_tells_a_commit_the_clone_holds_from_one_it_lacks(self, sync: Sync) -> None:
        git = Git(sync.checkout.root)
        assert (git.has_commit(git.head), git.has_commit(sync.first)) == (True, False)

    def test_fails_a_commit_check_outside_a_repository(self, tmp_path: Path) -> None:
        with pytest.raises(GitError) as caught:
            _ = Git(tmp_path).has_commit(Sha("0" * 40))
        assert caught.value.problem == Problem(
            tmp_path,
            "git rev-parse exited 128; fix the cause Git"
            " printed above, such as a missing clone or revision",
        )

    def test_names_a_commits_first_parent_or_none_for_a_root(
        self, tmp_path: Path
    ) -> None:
        repository = GitRepository.init(tmp_path / "repository")
        repository.write("a.py", "")
        root = repository.commit("root")
        repository.write("a.py", "x")
        child = repository.commit("child")
        git = Git(repository.root)
        assert (git.first_parent(child), git.first_parent(root)) == (root, None)

    def test_fails_a_first_parent_lookup_outside_a_repository(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(GitError) as caught:
            _ = Git(tmp_path).first_parent(Sha("0" * 40))
        assert caught.value.problem == Problem(
            tmp_path,
            "git rev-parse exited 128; fix the cause Git"
            " printed above, such as a missing clone or revision",
        )

    def test_lists_the_first_parent_commits_that_change_a_path_named_like_a_branch(
        self, tmp_path: Path
    ) -> None:
        repository = GitRepository.init(tmp_path / "repository")
        repository.write("side", "1")
        first = repository.commit("first")
        repository.git("checkout", "-q", "-b", "side")
        repository.write("side", "side")
        repository.commit("side")
        repository.git("checkout", "-q", "main")
        repository.write("b.py", "")
        repository.commit("other path")
        repository.git("merge", "-q", "--no-ff", "-m", "merge", "side")
        merge = Sha(repository.git("rev-parse", "HEAD").strip())
        repository.git("checkout", "-q", "-b", "elsewhere", str(first))
        assert Git(repository.root).first_parent_commits(
            "main", PurePosixPath("side")
        ) == (merge, first)

    def test_refuses_a_first_parent_line_git_names_by_other_than_its_sha1(
        self, tmp_path: Path
    ) -> None:
        repository = GitRepository.init(tmp_path / "repository", object_format="sha256")
        repository.write("a.py", "")
        repository.record("root")
        with pytest.raises(GitError) as caught:
            _ = Git(repository.root).first_parent_commits("main", PurePosixPath("a.py"))
        assert caught.value.problem == Problem(
            repository.root,
            "git log named a commit by other than its SHA-1; nustack reads only"
            " repositories whose commits Git names by SHA-1, so use one",
        )

    def test_reads_a_file_at_a_commit_or_none_where_the_commit_lacks_it(
        self, tmp_path: Path
    ) -> None:
        repository = GitRepository.init(tmp_path / "repository")
        repository.write("a b/c.py", "old\n")
        base = repository.commit("base")
        repository.write("a b/c.py", "new\n")
        git = Git(repository.root)
        assert (
            git.file_at(base, PurePosixPath("a b/c.py")),
            git.file_at(base, PurePosixPath("d.py")),
        ) == (b"old\n", None)

    def test_fails_a_file_read_outside_a_repository(self, tmp_path: Path) -> None:
        with pytest.raises(GitError) as caught:
            _ = Git(tmp_path).file_at(Sha("0" * 40), PurePosixPath("a.py"))
        assert caught.value.problem == Problem(
            tmp_path,
            "git rev-parse exited 128; fix the cause Git"
            " printed above, such as a missing clone or revision",
        )

    def test_lists_each_path_changed_since_a_commit_but_those_git_ignores(
        self, tmp_path: Path
    ) -> None:
        repository = GitRepository.init(tmp_path / "repository")
        repository.write(".gitignore", "ignored\n")
        repository.write("a", "")
        repository.write("b", "")
        repository.write("c d/e", "")
        repository.write("moved", "the same bytes on either side of the move\n")
        base = repository.commit("base")
        repository.write("a", "staged\n")
        repository.git("add", "a")
        repository.write("c d/e", "unstaged\n")
        repository.write("ignored", "")
        repository.write(str(base), "")
        (repository.root / os.fsdecode(b"\xff")).write_text("")
        repository.git("rm", "-q", "b")
        repository.git("mv", "moved", "renamed")
        assert Git(repository.root).changed_since(base) == (
            PurePosixPath("a"),
            PurePosixPath("b"),
            PurePosixPath("c d/e"),
            PurePosixPath(str(base)),
            PurePosixPath("moved"),
            PurePosixPath("renamed"),
            PurePosixPath("\udcff"),
        )

    def test_lists_each_untracked_path_it_ignores_and_a_whole_folder_as_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = GitRepository.init(tmp_path / "repository")
        repository.write(".gitignore", "*.tmp\ncache/\nforced\n")
        repository.write("forced", "")
        repository.git("add", "-f", "forced")
        repository.commit("base")
        repository.write(".git/info/exclude", ".DS_Store\n")
        (tmp_path / "config/git").mkdir(parents=True)
        (tmp_path / "config/git/ignore").write_text("*.swp\n")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        repository.write("a/.DS_Store", "")
        repository.write("a/b.swp", "")
        repository.write("cache/b", "")
        repository.write("cache/c/d", "")
        repository.write("a/kept", "")
        (repository.root / os.fsdecode(b"\xff.tmp")).write_text("")
        assert Git(repository.root).ignored() == {
            PurePosixPath("a/.DS_Store"),
            PurePosixPath("a/b.swp"),
            PurePosixPath("cache"),
            PurePosixPath("\udcff.tmp"),
        }

    def test_gives_run_no_input_by_default(self, sync: Sync) -> None:
        output = Git(sync.upstream.root).run("hash-object", "--stdin")
        assert output == b"e69de29bb2d1d6434b8b29ae775ad8c2e48c5391\n"

    def test_passes_input_and_variables_to_git(self, sync: Sync) -> None:
        git = Git(sync.upstream.root)
        assert (
            git.run("hash-object", "--stdin", stdin=b"old\n"),
            git.run(
                "var",
                "GIT_AUTHOR_IDENT",
                environment=frozendict(
                    {"GIT_AUTHOR_NAME": "Ada", "GIT_AUTHOR_EMAIL": "ada@example.com"}
                ),
            ).split(b" <")[0],
        ) == (b"3367afdbbf91e638efe983616377c60477cc6612\n", b"Ada")

    def test_names_the_repository_and_the_next_step_of_a_failed_command(
        self, tmp_path: Path
    ) -> None:
        with pytest.raises(GitError) as caught:
            _ = Git(tmp_path).run("rev-parse", "HEAD")
        assert caught.value.problem == Problem(
            tmp_path,
            "git rev-parse exited 128; fix the cause Git printed above, "
            "such as a missing clone or revision",
        )

    def test_reports_the_exit_status_of_a_command(self, sync: Sync) -> None:
        git = Git(sync.upstream.root)
        assert (git.status("rev-parse", "HEAD"), git.status("rev-parse", "x")) == (
            0,
            128,
        )

    def test_gives_status_no_input_by_default(self, sync: Sync) -> None:
        assert Git(sync.upstream.root).status("check-ignore", "--stdin") == 1

    def test_names_a_missing_repository_and_the_fix(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing"
        with pytest.raises(GitError) as caught:
            _ = Git(missing).run("rev-parse", "HEAD")
        assert caught.value.problem == Problem(
            missing,
            "cannot run Git (No such file or directory); check the clone path and Git",
        )

    def test_stops_a_fetch_that_outlasts_its_time_limit(
        self, sync: Sync, monkeypatch: pytest.MonkeyPatch, stall: str
    ) -> None:
        monkeypatch.setenv("GIT_SSH_COMMAND", f"{stall}; :")
        with pytest.raises(GitError) as caught:
            _ = Git(sync.upstream.root, timeout=0.1).run("fetch", "ssh://remote/r")
        assert caught.value.problem == Problem(
            sync.upstream.root,
            "git fetch took over 0.1 seconds; check that the"
            " remote answers, then rerun",
        )

    def test_stops_a_push_that_outlasts_its_time_limit(
        self, sync: Sync, monkeypatch: pytest.MonkeyPatch, stall: str
    ) -> None:
        monkeypatch.setenv("GIT_SSH_COMMAND", f"{stall}; :")
        with pytest.raises(GitError) as caught:
            _ = Git(sync.upstream.root, timeout=0.1).run(
                "push", "ssh://remote/r", "HEAD:refs/heads/b"
            )
        assert caught.value.problem == Problem(
            sync.upstream.root,
            "git push took over 0.1 seconds; check that the remote answers, then rerun",
        )

    def test_stops_a_remote_listing_that_outlasts_its_time_limit(
        self, sync: Sync, monkeypatch: pytest.MonkeyPatch, stall: str
    ) -> None:
        monkeypatch.setenv("GIT_SSH_COMMAND", f"{stall}; :")
        with pytest.raises(GitError) as caught:
            _ = Git(sync.upstream.root, timeout=0.1).run("ls-remote", "ssh://remote/r")
        assert caught.value.problem == Problem(
            sync.upstream.root,
            "git ls-remote took over 0.1 seconds; check that"
            " the remote answers, then rerun",
        )

    def test_stops_a_blob_read_a_partial_clone_fetches_that_outlasts_its_time_limit(
        self, sync: Sync, monkeypatch: pytest.MonkeyPatch, stall: str
    ) -> None:
        monkeypatch.setenv("GIT_SSH_COMMAND", f"{stall}; :")
        setup = Git(sync.upstream.root)
        _ = setup.run("remote", "add", "promisor", "ssh://remote/r")
        _ = setup.run("config", "remote.promisor.promisor", "true")
        _ = setup.run("config", "extensions.partialClone", "promisor")
        with pytest.raises(GitError) as caught:
            _ = Git(sync.upstream.root, timeout=0.1).run("cat-file", "blob", "1" * 40)
        assert caught.value.problem == Problem(
            sync.upstream.root,
            "git cat-file took over 0.1 seconds; check what Git waits on, such as"
            " its disk or, in a partial clone, the remote it fetches from, then rerun",
        )

    def test_stops_a_commit_a_hook_holds_past_its_time_limit(
        self, sync: Sync, stall: str
    ) -> None:
        hook = sync.upstream.root / ".git" / "hooks" / "pre-commit"
        hook.write_text(f"#!/bin/sh\nexec {stall}\n")
        hook.chmod(0o755)
        setup = Git(sync.upstream.root)
        # A global core.hooksPath would skip the repository's own hooks.
        _ = setup.run("config", "core.hooksPath", str(hook.parent))
        _ = setup.run("config", "user.name", "Ada")
        _ = setup.run("config", "user.email", "ada@example.com")
        with pytest.raises(GitError) as caught:
            _ = Git(sync.upstream.root, timeout=0.1).run(
                "commit", "--allow-empty", "-m", "x"
            )
        assert caught.value.problem == Problem(
            sync.upstream.root,
            "git commit took over 0.1 seconds; check what Git waits on, such as its"
            " disk or a hook, then rerun",
        )
