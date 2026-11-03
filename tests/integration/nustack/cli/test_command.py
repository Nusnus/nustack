"""The release and sync workflows' commands, on real Git repositories and a fake gh.

The sync's description command prints a body or a Problem, the sync command opens,
updates or closes its pull request, and the release commands hold a tag to main and
the plugin version and publish its release.
"""

lazy from pathlib import Path

import pytest

from nustack.cli.command import app
from nustack.cli.command import publish
from nustack.cli.command import release_tag
from nustack.cli.command import sync as sync_command
from nustack.cli.command import sync_description
from nustack.sync.description import SyncCopy
from nustack.sync.description import SyncLinks
from nustack.sync.proposal import Proposal
from tests.fixtures.repository import ModelRepository
from tests.fixtures.sync.git_repository import GitRepository
from tests.fixtures.sync.git_repository import Sync
lazy from tests.fixtures.gh import FakeGh


@pytest.mark.usefixtures("template")
class TestSyncDescriptionCommand:
    """The workflow gets a body to publish, or a Problem and no body.

    A clone that is no Git repository, or a body too large for GitHub, stops it.
    """

    LINKS = SyncLinks("https://x.io/up", "https://x.io/run", "https://x.io/checks")

    def test_prints_the_description_of_the_upstream_change(
        self, sync: Sync, capsys: pytest.CaptureFixture[str], repository_root: Path
    ) -> None:
        sync_description(
            upstream=self.LINKS.upstream,
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=sync.upstream.root,
            source=sync.SOURCE,
            folder=sync.FOLDER,
            root=sync.checkout.root,
        )
        expected = repository_root / "tests/fixtures/sync/expected/description.txt"
        output = capsys.readouterr()
        assert (output.out, output.err) == (expected.read_text(), "")

    def test_takes_the_workflows_flags(
        self,
        sync: Sync,
        repository_root: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(sync.checkout.root.parent)
        with pytest.raises(SystemExit) as stopped:
            app(
                [
                    "sync-description",
                    "--upstream",
                    "https://x.io/up",
                    "--run",
                    "https://x.io/run",
                    "--checks",
                    "https://x.io/checks",
                    "--clone",
                    "upstream",
                    "--source",
                    sync.SOURCE,
                    "--folder",
                    sync.FOLDER,
                    "--root",
                    "checkout",
                ]
            )
        expected = repository_root / "tests/fixtures/sync/expected/description.txt"
        output = capsys.readouterr()
        assert (stopped.value.code, output.out, output.err) == (
            0,
            expected.read_text(),
            "",
        )

    def test_stops_at_a_clone_that_is_no_git_repository_naming_its_full_path(
        self,
        sync: Sync,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        missing = sync.upstream.root.parent / "missing"
        missing.mkdir()
        monkeypatch.chdir(missing.parent)
        with pytest.raises(SystemExit) as stopped:
            sync_description(
                upstream=self.LINKS.upstream,
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=Path("missing"),
                source=sync.SOURCE,
                folder=sync.FOLDER,
                root=sync.checkout.root,
            )
        output = capsys.readouterr()
        assert (stopped.value.code, output.out, output.err) == (
            1,
            "",
            (
                f"{missing}: git rev-parse exited 128; fix the cause Git printed"
                " above, such as a missing clone or revision\n"
            ),
        )

    def test_stops_at_a_description_too_large_for_github(
        self, sync: Sync, capsys: pytest.CaptureFixture[str]
    ) -> None:
        sync.upstream.write(f"{sync.SOURCE}/SKILL.md", "nustack\n" * 9000)
        sync.upstream.commit("third")
        with pytest.raises(SystemExit) as stopped:
            sync_description(
                upstream=self.LINKS.upstream,
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                source=sync.SOURCE,
                folder=sync.FOLDER,
                root=sync.checkout.root,
            )
        output = capsys.readouterr()
        assert (stopped.value.code, output.out, output.err) == (
            1,
            "",
            (
                f"{sync.checkout.root}/copy: the sync description of this copy is"
                " 307184 bytes, over the 65536 GitHub accepts; quote less in"
                " SyncDescription, or sync a smaller upstream change\n"
            ),
        )


@pytest.mark.usefixtures("template")
class TestSyncCommand:
    """The workflow stages upstream's copy and leaves one pull request proposing it.

    A failed gh command, a second pull request on the branch, a copy it cannot make,
    a repository without a default branch or a clone Git cannot read stops it. A
    reply no recording holds, such as an empty default branch, is written in the
    form of gh's recorded replies.
    """

    LINKS = SyncLinks("https://github.com/up/skills", "https://x.io/run", "#checks")

    PULLS = (
        "api",
        "--method",
        "GET",
        "--paginate",
        "repos/o/r/pulls",
        "-f",
        "state=open",
        "-f",
        "base=main",
        "-f",
        "head=o:sync/w",
        "--jq",
        ".[] | select(.head.repo.id == .base.repo.id) | .number",
    )

    DEFAULT = ("api", "repos/o/r", "--jq", ".default_branch")

    @pytest.fixture
    def default_branch(self, gh: FakeGh, github_fixtures: Path) -> None:
        gh.replay(
            *self.DEFAULT, recording=github_fixtures / "default-branch/found.json"
        )

    @pytest.mark.usefixtures("default_branch")
    def test_opens_a_pull_request_for_upstreams_new_copy(
        self,
        sync: Sync,
        remote: str,
        gh: FakeGh,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        copy = SyncCopy(sync.upstream.root, sync.SOURCE, sync.FOLDER)
        proposal = Proposal("main", "sync/w", remote)
        sync_command(
            upstream=self.LINKS.upstream,
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=copy.clone,
            source=copy.source,
            folder=copy.folder,
            branch=proposal.branch,
            remote=proposal.remote,
            repository="o/r",
            root=sync.checkout.root,
        )
        (argv, body) = gh.calls[-1]
        assert (
            capsys.readouterr().out,
            argv[:2],
            "| ✅ **[Copy](https://x.io/run)** |" in body,
        ) == (
            "Opened a pull request proposing sync/w for main.\n",
            ("pr", "create"),
            True,
        )

    @pytest.mark.usefixtures("default_branch")
    def test_closes_the_pull_request_once_the_copy_matches_upstream(
        self,
        sync: Sync,
        remote: str,
        gh: FakeGh,
        github_fixtures: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        copy = SyncCopy(sync.upstream.root, sync.SOURCE, sync.FOLDER)
        sync_command(
            upstream=self.LINKS.upstream,
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=copy.clone,
            source=copy.source,
            folder=copy.folder,
            branch="sync/w",
            remote=remote,
            repository="o/r",
            root=sync.checkout.root,
        )
        gh.replay(*self.PULLS, recording=github_fixtures / "open-pulls/one.json")
        sync_command(
            upstream=self.LINKS.upstream,
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=copy.clone,
            source=copy.source,
            folder=copy.folder,
            branch="sync/w",
            remote=remote,
            repository="o/r",
            root=sync.checkout.root,
        )
        assert capsys.readouterr().out.splitlines()[-1] == (
            "Closed pull request #267: the copy matches upstream again."
        )

    @pytest.mark.usefixtures("default_branch")
    def test_stops_on_a_gh_command_that_failed(
        self,
        sync: Sync,
        gh: FakeGh,
        github_fixtures: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gh.replay(*self.PULLS, recording=github_fixtures / "open-pulls/missing.json")
        with pytest.raises(SystemExit) as stopped:
            sync_command(
                upstream=self.LINKS.upstream,
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                source=sync.SOURCE,
                folder=sync.FOLDER,
                branch="sync/w",
                remote="remote",
                repository="o/r",
                root=sync.checkout.root,
            )
        assert (stopped.value.code, capsys.readouterr().err) == (
            1,
            "o/r: gh api exited 1; fix the cause gh printed above, then rerun\n",
        )

    @pytest.mark.usefixtures("default_branch")
    def test_stops_when_more_than_one_pull_request_proposes_the_branch(
        self,
        sync: Sync,
        gh: FakeGh,
        github_fixtures: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gh.replay(*self.PULLS, recording=github_fixtures / "open-pulls/several.json")
        with pytest.raises(SystemExit) as stopped:
            sync_command(
                upstream=self.LINKS.upstream,
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                source=sync.SOURCE,
                folder=sync.FOLDER,
                branch="sync/w",
                remote="remote",
                repository="o/r",
                root=sync.checkout.root,
            )
        assert (stopped.value.code, capsys.readouterr().err) == (
            1,
            (
                "o/r: has pull requests #267, #265, #264, #259, #258 that all propose"
                " sync/w for main; close all but one, then rerun\n"
            ),
        )

    def test_stops_on_a_copy_it_cannot_make_naming_its_full_path(
        self,
        sync: Sync,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(sync.checkout.root.parent)
        with pytest.raises(SystemExit) as stopped:
            sync_command(
                upstream=self.LINKS.upstream,
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                source="missing",
                folder=sync.FOLDER,
                branch="sync/w",
                remote="remote",
                repository="o/r",
                root=Path(sync.checkout.root.name),
            )
        assert (stopped.value.code, capsys.readouterr().err) == (
            1,
            (
                f"{sync.checkout.root}/copy/SKILL.md: has no upstream source; pass"
                " --source the skill's folder upstream\n"
            ),
        )

    def test_stops_on_a_repository_that_names_no_default_branch(
        self, sync: Sync, gh: FakeGh, capsys: pytest.CaptureFixture[str]
    ) -> None:
        gh.reply(*self.DEFAULT, stdout="\n")
        with pytest.raises(SystemExit) as stopped:
            sync_command(
                upstream=self.LINKS.upstream,
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                source=sync.SOURCE,
                folder=sync.FOLDER,
                branch="sync/w",
                remote="remote",
                repository="o/r",
                root=sync.checkout.root,
            )
        assert (stopped.value.code, capsys.readouterr().err, gh.calls[-1][0]) == (
            1,
            (
                "o/r: gh names no default branch for o/r; check that the token can"
                " read the repository\n"
            ),
            self.DEFAULT,
        )

    def test_stops_on_a_clone_git_cannot_read_naming_its_full_path(
        self,
        sync: Sync,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        missing = sync.upstream.root.parent / "missing"
        monkeypatch.chdir(missing.parent)
        with pytest.raises(SystemExit) as stopped:
            sync_command(
                upstream=self.LINKS.upstream,
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=Path("missing"),
                source=sync.SOURCE,
                folder=sync.FOLDER,
                branch="sync/w",
                remote="remote",
                repository="o/r",
                root=sync.checkout.root,
            )
        assert (stopped.value.code, capsys.readouterr().err) == (
            1,
            (
                f"{missing}: cannot run Git (No such file or directory); check the"
                " clone path and Git\n"
            ),
        )


class TestReleaseTagCommand:
    """The release workflow publishes only a tag on main that names the version.

    A tag off main or naming another version is named, and a repository where Git
    finds no main stops it.
    """

    @pytest.fixture
    def checkout(self, tmp_path: Path) -> GitRepository:
        root = ModelRepository(tmp_path / "repository").save()
        checkout = GitRepository(root)
        checkout.git("init", "-q", "-b", "main")
        checkout.git("update-ref", "refs/remotes/origin/main", checkout.commit("base"))
        return checkout

    def test_passes_a_tag_on_main_that_names_the_version(
        self, checkout: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        release_tag("v1.2.3", root=checkout.root)
        assert capsys.readouterr() == (
            "v1.2.3 is on main and names the plugin version\n",
            "",
        )

    def test_names_a_tag_off_main_that_names_another_version(
        self, checkout: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        checkout.write("notes.txt", "x")
        checkout.commit("off main")
        with pytest.raises(SystemExit) as stopped:
            release_tag("v9.9.9", root=checkout.root)
        assert (stopped.value.code, capsys.readouterr().err) == (
            1,
            (
                "v9.9.9: is not on main; delete it and tag the commit the squash merge"
                " made on main\n"
                "v9.9.9: does not match plugin version 1.2.3; delete it and tag v1.2.3,"
                " or set the version as AGENTS.md's Releases section says\n"
            ),
        )

    def test_stops_where_git_cannot_find_main_naming_the_full_path(
        self,
        checkout: GitRepository,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        checkout.git("update-ref", "-d", "refs/remotes/origin/main")
        monkeypatch.chdir(checkout.root.parent)
        with pytest.raises(SystemExit) as stopped:
            release_tag("v1.2.3", root=Path(checkout.root.name))
        assert (stopped.value.code, capsys.readouterr().err) == (
            1,
            (
                f"{checkout.root}: git merge-base exited 128; fix the cause Git printed"
                " above, such as a missing clone or revision\n"
            ),
        )


class TestPublishCommand:
    """The release workflow publishes the tag's release, or stops naming why."""

    TAG = ("api", "repos/o/r/commits/tags/v1.2.3", "--jq", ".sha")

    @pytest.fixture(autouse=True)
    def tagged(self, gh: FakeGh, github_fixtures: Path) -> None:
        gh.replay(*self.TAG, recording=github_fixtures / "tag-commit/found.json")

    def test_prints_the_published_release(
        self,
        gh: FakeGh,
        github_fixtures: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gh.replay(
            *("release", "view", "v1.2.3", "-R", "o/r", "--json", "isDraft"),
            *("--jq", ".isDraft"),
            recording=github_fixtures / "release-draft/missing.json",
        )
        publish(
            "v1.2.3",
            commit="81c986c0e0a7c511f2941ed3cec09f7975687f80",
            repository="o/r",
            folder=tmp_path,
        )
        assert capsys.readouterr() == ("Published release v1.2.3\n", "")

    def test_stops_naming_why_it_cannot_publish(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as stopped:
            publish("v1.2.3", commit="another", repository="o/r", folder=tmp_path)
        assert (stopped.value.code, capsys.readouterr().err) == (
            1,
            (
                "v1.2.3: has moved off the commit CI passed on; the run the move"
                " started publishes it\n"
            ),
        )
