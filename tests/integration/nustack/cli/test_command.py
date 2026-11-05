"""nustack's sync, mutants and release commands, on real Git repositories and a fake gh.

sync-description, a command a person runs by hand, prints the body the sync command
would publish, or a Problem. The sync command opens, updates or closes its pull request,
the mutants command readies mutmut's folder from what changed since its full run, and
the release commands bump the version and title the changelog's unreleased changes with
it, hold a tag to main and the plugin version, push it from main's latest commit, and
publish its release.
"""

import json
import shutil
import tempfile
from datetime import UTC
from datetime import datetime
from datetime import tzinfo
from pathlib import Path

import pytest

from nustack.cli import command
from nustack.cli.command import app
from nustack.cli.command import bump
from nustack.cli.command import mutants
from nustack.cli.command import publish
from nustack.cli.command import push_tag
from nustack.cli.command import release_tag
from nustack.cli.command import sync as sync_command
from nustack.cli.command import sync_description
from nustack.commitizen import Commitizen
from nustack.release.tag import Tag
from nustack.sha import Sha
from nustack.sync.description import SyncLinks
from nustack.sync.proposal import Proposal
from tests.fixtures.gh import GhArgv
from tests.fixtures.git_repository import GitRepository
from tests.fixtures.permissions import SKIP_AS_ROOT
from tests.fixtures.repository import ModelRepository
lazy from tests.fixtures.gh import FakeGh
lazy from tests.fixtures.sync.repositories import Sync


@pytest.mark.usefixtures("template")
class TestSyncDescriptionCommand:
    """A person gets the body sync would publish, or a Problem and no body.

    A clone or checkout that is no Git repository, a record the check refuses, a
    skill upstream no longer holds, or a body too large for GitHub, stops it.
    """

    LINKS = SyncLinks("https://x.io/run", "https://x.io/checks")

    def test_prints_the_description_of_the_upstream_change(
        self, sync: Sync, capsys: pytest.CaptureFixture[str], repository_root: Path
    ) -> None:
        sync_description(
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=sync.upstream.root,
            record=sync.RECORD,
            root=sync.checkout.root,
        )
        expected = repository_root / "tests/fixtures/sync/expected/description.txt"
        output = capsys.readouterr()
        assert (output.out, output.err) == (expected.read_text(), "")

    def test_lists_a_skill_upstream_added_after_the_last_copied_change(
        self, sync: Sync, capsys: pytest.CaptureFixture[str], repository_root: Path
    ) -> None:
        sync.upstream.write(f"{sync.SOURCE}/new/SKILL.md", "new\n")
        sync.upstream.commit("add a skill")
        sync_description(
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=sync.upstream.root,
            record=sync.RECORD,
            root=sync.checkout.root,
        )
        expected = (
            repository_root / "tests/fixtures/sync/expected/description-new-skill.txt"
        )
        output = capsys.readouterr()
        assert (output.out, output.err) == (expected.read_text(), "")

    def test_says_nothing_is_proposed_when_the_copy_matches_upstream(
        self, sync: Sync, capsys: pytest.CaptureFixture[str]
    ) -> None:
        files = {"LICENSE": b"MIT\n", "SKILL.md": b"new\n", "tool": b""}
        for path, data in files.items():
            sync.checkout.write(f"{Sync.COPY}/{path}", data.decode())
        (sync.checkout.root / Sync.COPY / "tool").chmod(0o755)
        sync.checkout.write(sync.RECORD, Sync.record_of(sync.second, files).text)
        sync.checkout.commit("synced")
        sync_description(
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=sync.upstream.root,
            record=sync.RECORD,
            root=sync.checkout.root,
        )
        assert capsys.readouterr() == (
            "The copy matches upstream; the sync proposes nothing.\n",
            "",
        )

    def test_takes_each_option_by_its_flag(
        self,
        sync: Sync,
        repository_root: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(sync.checkout.root.parent)
        with pytest.raises(SystemExit) as caught:
            app(
                [
                    "sync-description",
                    "--run",
                    "https://x.io/run",
                    "--checks",
                    "https://x.io/checks",
                    "--clone",
                    "upstream",
                    "--record",
                    sync.RECORD,
                    "--root",
                    "checkout",
                ]
            )
        expected = repository_root / "tests/fixtures/sync/expected/description.txt"
        output = capsys.readouterr()
        assert (caught.value.code, output.out, output.err) == (
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
        with pytest.raises(SystemExit) as caught:
            sync_description(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=Path("missing"),
                record=sync.RECORD,
                root=sync.checkout.root,
            )
        output = capsys.readouterr()
        assert (caught.value.code, output.out, output.err) == (
            1,
            "",
            (
                f"{missing}: git rev-parse exited 128; fix the cause Git printed"
                " above, such as a missing clone or revision\n"
            ),
        )

    def test_stops_at_a_checkout_that_is_no_git_repository_naming_its_full_path(
        self, sync: Sync, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        checkout = tmp_path / "plain"
        for path in (sync.RECORD, ".github/pull_request_template.md"):
            (checkout / path).parent.mkdir(parents=True, exist_ok=True)
            (checkout / path).write_bytes((sync.checkout.root / path).read_bytes())
        with pytest.raises(SystemExit) as caught:
            sync_description(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                record=sync.RECORD,
                root=checkout,
            )
        output = capsys.readouterr()
        assert (caught.value.code, output.out, output.err) == (
            1,
            "",
            (
                f"{checkout}: git ls-tree exited 128; fix the cause Git printed above,"
                " such as a missing clone or revision\n"
            ),
        )

    def test_stops_on_a_skill_upstream_no_longer_holds_naming_its_full_path(
        self, sync: Sync, capsys: pytest.CaptureFixture[str]
    ) -> None:
        sync.checkout.write(
            sync.RECORD, Sync.record_of(sync.first, Sync.BASE, source="missing").text
        )
        with pytest.raises(SystemExit) as caught:
            sync_description(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                record=sync.RECORD,
                root=sync.checkout.root,
            )
        output = capsys.readouterr()
        assert (caught.value.code, output.out, output.err) == (
            1,
            "",
            (
                f"{sync.checkout.root}/{Sync.COPY}/SKILL.md: has no upstream"
                " source; set the record's source to the upstream folder that holds"
                " the skill's folder, rename the skill in the record's skills to"
                " upstream's new name as AGENTS.md says, or drop the skill from the"
                " record's skills\n"
            ),
        )

    def test_stops_on_a_record_the_check_refuses_naming_its_full_path(
        self, sync: Sync, capsys: pytest.CaptureFixture[str]
    ) -> None:
        sync.checkout.write(
            sync.RECORD, Sync.record_of(sync.first, Sync.BASE, folder="copy").text
        )
        with pytest.raises(SystemExit) as caught:
            sync_description(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                record=sync.RECORD,
                root=sync.checkout.root,
            )
        output = capsys.readouterr()
        assert (caught.value.code, output.out, output.err) == (
            1,
            "",
            (
                f"{sync.checkout.root}/{Sync.RECORD}: folder: names no skills folder"
                " a host reads; set it to .agents/skills or plugin/skills\n"
            ),
        )

    def test_stops_at_a_description_too_large_for_github(
        self, sync: Sync, capsys: pytest.CaptureFixture[str]
    ) -> None:
        sync.upstream.write(f"{sync.SOURCE_FOLDER}/SKILL.md", "nustack\n" * 9000)
        sync.upstream.commit("third")
        with pytest.raises(SystemExit) as caught:
            sync_description(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                record=sync.RECORD,
                root=sync.checkout.root,
            )
        output = capsys.readouterr()
        assert (caught.value.code, output.out, output.err) == (
            1,
            "",
            (
                f"{sync.checkout.root}/.agents/skills: the sync description of this"
                " copy is 325403 bytes, over the 65536 GitHub accepts; quote less in"
                " SyncDescription, or sync a smaller upstream change\n"
            ),
        )


@pytest.mark.usefixtures("template")
class TestSyncCommand:
    """The workflow stages upstream's copy and leaves one pull request proposing it.

    A failed gh command, a second pull request on the branch, a copy it cannot make,
    a repository without a default branch or a clone Git cannot read stops it. A
    reply no recording holds, such as an empty default branch, is the test's own.
    """

    LINKS = SyncLinks("https://x.io/run", "#checks")

    @pytest.fixture
    def default_branch(self, gh: FakeGh, github_fixtures: Path) -> None:
        gh.replay(
            *GhArgv.DEFAULT_BRANCH,
            recording=github_fixtures / "default-branch/found.json",
        )

    @pytest.mark.usefixtures("default_branch")
    def test_opens_a_pull_request_for_upstreams_new_copy(
        self,
        sync: Sync,
        remote_url: str,
        gh: FakeGh,
        github_fixtures: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gh.replay(
            *GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/none.json"
        )
        proposal = Proposal("main", "sync/w", remote_url)
        sync_command(
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=sync.upstream.root,
            record=sync.RECORD,
            remote_url=proposal.remote_url,
            name_with_owner=GhArgv.REPOSITORY,
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
        remote_url: str,
        gh: FakeGh,
        github_fixtures: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gh.replay(
            *GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/none.json"
        )
        gh.replay(*GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/one.json")
        sync_command(
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=sync.upstream.root,
            record=sync.RECORD,
            remote_url=remote_url,
            name_with_owner=GhArgv.REPOSITORY,
            root=sync.checkout.root,
        )
        sync_command(
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=sync.upstream.root,
            record=sync.RECORD,
            remote_url=remote_url,
            name_with_owner=GhArgv.REPOSITORY,
            root=sync.checkout.root,
        )
        assert capsys.readouterr().out.splitlines()[-1] == (
            "Closed pull request #267: the copy matches upstream again."
        )

    @pytest.mark.usefixtures("default_branch")
    def test_proposes_restoring_a_copy_that_drifted_from_a_record_of_upstreams_head(
        self,
        sync: Sync,
        remote_url: str,
        gh: FakeGh,
        github_fixtures: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sync.checkout.write(
            Sync.RECORD,
            Sync.record_of(
                sync.second,
                {"LICENSE": b"MIT\n", "SKILL.md": b"new\n", "tool": b""},
            ).text,
        )
        sync.checkout.commit("drift")
        gh.replay(
            *GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/none.json"
        )
        sync_command(
            run=self.LINKS.run,
            checks=self.LINKS.checks,
            clone=sync.upstream.root,
            record=sync.RECORD,
            remote_url=remote_url,
            name_with_owner=GhArgv.REPOSITORY,
            root=sync.checkout.root,
        )
        assert (
            capsys.readouterr().out,
            sync.checkout.git("show", f"HEAD:{Sync.COPY}/SKILL.md"),
        ) == ("Opened a pull request proposing sync/w for main.\n", "new\n")

    @pytest.mark.usefixtures("default_branch")
    def test_names_the_new_upstream_skills_when_it_proposes_nothing(
        self,
        sync: Sync,
        remote_url: str,
        gh: FakeGh,
        github_fixtures: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sync.upstream.write(f"{sync.SOURCE}/new/SKILL.md", "new\n")
        sync.upstream.commit("add a skill")
        gh.replay(
            *GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/none.json"
        )
        gh.replay(*GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/one.json")
        for _ in range(2):
            sync_command(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                record=sync.RECORD,
                remote_url=remote_url,
                name_with_owner=GhArgv.REPOSITORY,
                root=sync.checkout.root,
            )
        assert capsys.readouterr().out.splitlines()[-3:] == [
            "Opened a pull request proposing sync/w for main.",
            "Closed pull request #267: the copy matches upstream again.",
            (
                "Upstream holds skills the record does not list: new; add each one the"
                " copy should hold to the skills of vendored/w.json. Each run names"
                " them again until a sync records a commit that holds them."
            ),
        ]

    @pytest.mark.usefixtures("default_branch")
    def test_stops_on_a_gh_command_that_failed(
        self,
        sync: Sync,
        gh: FakeGh,
        github_fixtures: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gh.replay(
            *GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/missing.json"
        )
        with pytest.raises(SystemExit) as caught:
            sync_command(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                record=sync.RECORD,
                remote_url="remote",
                name_with_owner=GhArgv.REPOSITORY,
                root=sync.checkout.root,
            )
        assert (caught.value.code, capsys.readouterr().err) == (
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
        gh.replay(
            *GhArgv.OPEN_PULLS, recording=github_fixtures / "open-pulls/several.json"
        )
        with pytest.raises(SystemExit) as caught:
            sync_command(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                record=sync.RECORD,
                remote_url="remote",
                name_with_owner=GhArgv.REPOSITORY,
                root=sync.checkout.root,
            )
        assert (caught.value.code, capsys.readouterr().err) == (
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
        sync.checkout.write(
            sync.RECORD, Sync.record_of(sync.first, Sync.BASE, source="missing").text
        )
        monkeypatch.chdir(sync.checkout.root.parent)
        with pytest.raises(SystemExit) as caught:
            sync_command(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                record=sync.RECORD,
                remote_url="remote",
                name_with_owner=GhArgv.REPOSITORY,
                root=Path(sync.checkout.root.name),
            )
        assert (caught.value.code, capsys.readouterr().err) == (
            1,
            (
                f"{sync.checkout.root}/{Sync.COPY}/SKILL.md: has no upstream"
                " source; set the record's source to the upstream folder that holds"
                " the skill's folder, rename the skill in the record's skills to"
                " upstream's new name as AGENTS.md says, or drop the skill from the"
                " record's skills\n"
            ),
        )

    def test_stops_on_a_repository_that_names_no_default_branch(
        self, sync: Sync, gh: FakeGh, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # GitHub gives every repository a default branch, so no recording holds this.
        gh.reply(*GhArgv.DEFAULT_BRANCH, stdout="\n")
        with pytest.raises(SystemExit) as caught:
            sync_command(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=sync.upstream.root,
                record=sync.RECORD,
                remote_url="remote",
                name_with_owner=GhArgv.REPOSITORY,
                root=sync.checkout.root,
            )
        assert (caught.value.code, capsys.readouterr().err, gh.calls[-1][0]) == (
            1,
            (
                "o/r: gh names no default branch for o/r; check that the token can"
                " read the repository\n"
            ),
            GhArgv.DEFAULT_BRANCH,
        )

    def test_stops_on_a_clone_git_cannot_read_naming_its_full_path(
        self,
        sync: Sync,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        missing = sync.upstream.root.parent / "missing"
        monkeypatch.chdir(missing.parent)
        with pytest.raises(SystemExit) as caught:
            sync_command(
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=Path("missing"),
                record=sync.RECORD,
                remote_url="remote",
                name_with_owner=GhArgv.REPOSITORY,
                root=sync.checkout.root,
            )
        assert (caught.value.code, capsys.readouterr().err) == (
            1,
            (
                f"{missing}: cannot run Git (No such file or directory); check the"
                " clone path and Git\n"
            ),
        )


class TestMutantsCommand:
    """make mutate-changed keeps each verdict the changes since its full run miss.

    A change to no file the tests read, or only to the comments and docstring text of
    the tests' Python, skips the run; a changed or deleted test module empties the
    verdicts of each function its tests cover; any other change they read, a
    folder with no full run, or a full run on a commit the clone lacks clears the
    folder. A root Git cannot read, or a folder it cannot change, stops it with the
    fix.
    """

    PYPROJECT = (
        '[project]\nversion = "1.2.3"\n\n[tool.mutmut]\nsource_paths = ["src/pkg"]\n'
        '\n[tool.nustack.mutation]\nreads = ["Makefile"]\n'
    )
    VERDICTS = frozendict(
        {"exit_code_by_key": {"pkg.a.x_f__mutmut_1": 1, "pkg.a.x_g__mutmut_1": 1}}
    )

    @pytest.fixture
    def project(self, tmp_path: Path) -> GitRepository:
        project = GitRepository.init(tmp_path / "project")
        project.write(".gitignore", "mutants/\n")
        project.write("pyproject.toml", self.PYPROJECT)
        project.write("src/pkg/a.py", "")
        project.write("tests/test_a.py", "")
        project.write("tests/conftest.py", '"""Shares fixtures."""\n')
        project.write("README.md", "")
        commit = project.commit("base")
        project.write("mutants/src/pkg/a.py", "")
        project.write("mutants/src/pkg/a.py.meta", json.dumps(dict(self.VERDICTS)))
        project.write(
            "mutants/mutmut-stats.json",
            json.dumps(
                {
                    "git_commit": str(commit),
                    "tests_by_mangled_function_name": {
                        "pkg.a.x_f": ["tests/test_a.py::T::t"],
                        "pkg.a.x_g": ["tests/test_b.py::T::t"],
                    },
                }
            ),
        )
        return project

    def test_skips_the_run_when_no_file_the_tests_read_changed(
        self, project: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project.write("README.md", "changed\n")
        mutants(root=project.root)
        assert (
            capsys.readouterr(),
            (project.root / "mutants/src/pkg/a.py").exists(),
        ) == (
            (
                "skip\n",
                (
                    "no file mutmut's tests read changed since mutants/'s full run, so"
                    " no mutant runs\n"
                ),
            ),
            True,
        )

    def test_skips_the_run_when_the_tests_changed_only_comments_and_docstrings(
        self, project: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project.write("tests/conftest.py", '"""Shares the fixtures."""\n# Why.\n')
        project.write("tests/test_a.py", "# Nothing yet.\n")
        mutants(root=project.root)
        meta = json.loads((project.root / "mutants/src/pkg/a.py.meta").read_text())
        assert (capsys.readouterr().out, meta) == ("skip\n", dict(self.VERDICTS))

    def test_counts_a_deleted_test_module_as_changed(
        self, project: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (project.root / "tests/test_a.py").unlink()
        mutants(root=project.root)
        assert capsys.readouterr().out == "changed\n"

    def test_empties_each_verdict_a_changed_test_module_reaches(
        self,
        project: GitRepository,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        project.write("tests/test_a.py", "changed\n")
        monkeypatch.chdir(project.root.parent)
        with pytest.raises(SystemExit) as caught:
            app(["mutants", "--root", project.root.name])
        meta = json.loads((project.root / "mutants/src/pkg/a.py.meta").read_text())
        assert (
            caught.value.code,
            capsys.readouterr(),
            meta,
            (project.root / "mutants/src/pkg/a.py").exists(),
        ) == (
            0,
            (
                "changed\n",
                (
                    "the changed functions' mutants run, and those of the 1 functions"
                    " the changed test modules cover\n"
                ),
            ),
            {
                "exit_code_by_key": {
                    "pkg.a.x_f__mutmut_1": None,
                    "pkg.a.x_g__mutmut_1": 1,
                }
            },
            False,
        )

    @pytest.mark.parametrize(
        ("path", "reason"),
        [
            (
                "tests/conftest.py",
                (
                    "tests/conftest.py changed, which can reach any verdict, so every"
                    " mutant runs\n"
                ),
            ),
            (
                "Makefile",
                "Makefile changed, which can reach any verdict, so every mutant runs\n",
            ),
        ],
    )
    def test_clears_the_folder_when_another_copied_file_changed(
        self,
        project: GitRepository,
        path: str,
        reason: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        project.write(path, "")
        mutants(root=project.root)
        assert (capsys.readouterr(), (project.root / "mutants").exists()) == (
            ("full\n", reason),
            False,
        )

    def test_clears_a_folder_whose_full_run_the_clone_lacks(
        self, project: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        stats = project.root / "mutants/mutmut-stats.json"
        stats.write_text(
            json.dumps({"git_commit": "0" * 40, "tests_by_mangled_function_name": {}})
        )
        mutants(root=project.root)
        assert (capsys.readouterr(), (project.root / "mutants").exists()) == (
            (
                "full\n",
                (
                    f"{project.root}/mutants comes from a commit this clone lacks, so"
                    " every mutant runs; fetch it to keep its verdicts\n"
                ),
            ),
            False,
        )

    def test_runs_every_mutant_without_a_full_run(
        self, project: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (project.root / "mutants/mutmut-stats.json").unlink()
        mutants(root=project.root)
        assert (capsys.readouterr(), (project.root / "mutants").exists()) == (
            (
                "full\n",
                (
                    f"{project.root}/mutants/mutmut-stats.json is missing, so every"
                    " mutant runs\n"
                ),
            ),
            False,
        )

    def test_stops_on_a_root_git_cannot_read(
        self, project: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        shutil.rmtree(project.root / ".git")
        with pytest.raises(SystemExit) as caught:
            mutants(root=project.root)
        assert (caught.value.code, capsys.readouterr()) == (
            1,
            (
                "",
                (
                    f"{project.root}: git rev-parse exited 128; fix the cause Git"
                    " printed above, such as a missing clone or revision\n"
                ),
            ),
        )

    @SKIP_AS_ROOT
    def test_stops_on_a_folder_it_cannot_change(
        self, project: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        project.write("tests/test_a.py", "changed\n")
        shut = project.root / "mutants/src/pkg"
        shut.chmod(0o500)
        try:
            with pytest.raises(SystemExit) as caught:
                mutants(root=project.root)
        finally:
            shut.chmod(0o700)
        assert (caught.value.code, capsys.readouterr()) == (
            1,
            (
                "",
                (
                    f"{project.root}/mutants: cannot be changed (Permission denied);"
                    " let your user write to it, or remove it and run make mutate\n"
                ),
            ),
        )


class TestBumpCommand:
    """A release sets its version and titles the unreleased changes with it and today.

    It takes the next patch or the version given. A working tree with changes, which
    would ride into the release's commit, and a changelog that lists no unreleased
    change stop it before any file changes, and so does a bump commitizen refuses;
    manifests the bump leaves disagreeing, or a changelog it cannot write, stop it
    after.
    """

    LOCK = 'version = 1\n\n[[package]]\nname = "kit"\nversion = "1.2.3"\n'
    VERSIONED = (
        "pyproject.toml",
        "uv.lock",
        "plugin/.claude-plugin/plugin.json",
        "plugin/.cursor-plugin/plugin.json",
        "plugin/.devin-plugin/plugin.json",
        "plugin/package.json",
    )

    @pytest.fixture
    def model(self, tmp_path: Path) -> ModelRepository:
        model = ModelRepository(tmp_path / "repository")
        model.edit(
            "pyproject.toml",
            "[tool.commitizen]\n",
            '[tool.commitizen]\nversion_provider = "uv"\n',
        )
        model.write("uv.lock", self.LOCK)
        return model

    @pytest.fixture
    def checkout(self, model: ModelRepository) -> GitRepository:
        model.edit(
            "CHANGELOG.md",
            "## [Unreleased]\n\n",
            "## [Unreleased]\n\n### Fixed\n\n- Fixes the kit.\n\n",
        )
        checkout = GitRepository(model.save())
        checkout.git("init", "-q", "-b", "main")
        checkout.commit("base")
        checkout.git("tag", "v1.2.3")
        return checkout

    # The changelog lands from a file beside it, never from the temporary folder.
    @pytest.fixture(autouse=True)
    def no_temporary_folder(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "missing"))

    # Late on 4 March in UTC is already 5 March east of it, so a run that reads the
    # local day dates the release otherwise.
    @pytest.fixture(autouse=True)
    def clock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class Clock(datetime):
            @classmethod
            def now(cls, tz: tzinfo | None = None) -> Clock:
                moment = cls(2026, 3, 4, 23, 30, tzinfo=UTC)
                return moment if tz is UTC else cls(2026, 3, 5, 9, 30)

        monkeypatch.setattr(command, "datetime", Clock)

    def versions(self, checkout: GitRepository) -> list[bool]:
        return [
            '"1.2.3"' in (checkout.root / path).read_text() for path in self.VERSIONED
        ]

    @pytest.mark.parametrize(
        ("version", "bumped"), [(None, "1.2.4"), ("2.0.0", "2.0.0")]
    )
    def test_sets_the_version_and_titles_the_changes_with_it_and_the_day_in_utc(
        self,
        checkout: GitRepository,
        version: str | None,
        bumped: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        bump(version, root=checkout.root)
        assert (
            capsys.readouterr(),
            (checkout.root / "CHANGELOG.md").read_text(),
            [
                f'"{bumped}"' in (checkout.root / path).read_text()
                for path in self.VERSIONED
            ],
        ) == (
            (f"Released [Unreleased] as [{bumped}] - 2026-03-04\n", ""),
            (
                "# Changelog\n\n"
                f"[Unreleased]: https://example.com/nus/kit/compare/v{bumped}...HEAD\n"
                f"[{bumped}]: https://example.com/nus/kit/releases/tag/v{bumped}\n"
                "[1.2.3]: https://example.com/nus/kit/releases/tag/v1.2.3\n"
                "[1.2.2]: https://example.com/nus/kit/releases/tag/v1.2.2\n\n"
                f"## [Unreleased]\n\n## [{bumped}] - 2026-03-04\n\n"
                "### Fixed\n\n- Fixes the kit.\n\n"
                "## [1.2.3] - 2026-01-02\n\n### Added\n\n- Adds the kit.\n\n"
                "## [1.2.2] - 2026-01-01\n\n- Starts.\n"
            ),
            [True] * len(self.VERSIONED),
        )

    # A tracked file's edit, and an untracked file in a clone set to hide untracked
    # files from git status, both count.
    @pytest.mark.parametrize("changed", ["CHANGELOG.md", "notes.md"])
    def test_stops_before_any_change_from_a_working_tree_with_changes(
        self, checkout: GitRepository, capsys: pytest.CaptureFixture[str], changed: str
    ) -> None:
        checkout.git("config", "status.showUntrackedFiles", "no")
        checkout.write(changed, "An unrelated edit.\n")
        with pytest.raises(SystemExit) as caught:
            bump(None, root=checkout.root)
        assert (
            caught.value.code,
            capsys.readouterr().err,
            self.versions(checkout),
            (checkout.root / changed).read_text(),
        ) == (
            1,
            (
                f"{checkout.root}: holds changes git status lists, which would ride"
                " into the release's commit; commit or stash them, then rerun\n"
            ),
            [True] * len(self.VERSIONED),
            "An unrelated edit.\n",
        )

    def test_stops_where_git_cannot_read_the_working_tree(
        self, model: ModelRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = model.save()
        with pytest.raises(SystemExit) as caught:
            bump(None, root=root)
        assert (caught.value.code, capsys.readouterr().err) == (
            1,
            (
                f"{root}: git status exited 128; fix the cause Git printed above,"
                " such as a missing clone or revision\n"
            ),
        )

    def test_stops_before_any_change_without_unreleased_changes(
        self, model: ModelRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        checkout = GitRepository(model.save())
        checkout.git("init", "-q", "-b", "main")
        checkout.commit("base")
        with pytest.raises(SystemExit) as caught:
            bump(None, root=checkout.root)
        assert (
            caught.value.code,
            capsys.readouterr().err,
            self.versions(checkout),
        ) == (
            1,
            (
                f"{checkout.root}/CHANGELOG.md: lists no change under [Unreleased];"
                " list each change since the last release there, as AGENTS.md's Pull"
                " requests says\n"
            ),
            [True] * len(self.VERSIONED),
        )

    def test_stops_on_a_bump_commitizen_refuses(
        self, checkout: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        checkout.git("tag", "--delete", "v1.2.3")
        with pytest.raises(SystemExit) as caught:
            bump(None, root=checkout.root)
        assert (
            caught.value.code,
            capsys.readouterr().err.endswith(
                f"{checkout.root}: cz bump exited 1; fix the cause it printed above,"
                " such as a release tag this clone lacks, which git fetch --tags"
                " origin brings\n"
            ),
            self.versions(checkout),
        ) == (1, True, [True] * len(self.VERSIONED))

    def test_stops_on_manifests_the_bump_leaves_disagreeing(
        self,
        checkout: GitRepository,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def disagreeing(bumper: Commitizen, _version: str | None) -> None:
            manifest = bumper.root / "plugin/.claude-plugin/plugin.json"
            manifest.write_text(manifest.read_text().replace("1.2.3", "1.2.4"))

        monkeypatch.setattr(Commitizen, "bump", disagreeing)
        with pytest.raises(SystemExit) as caught:
            bump(None, root=checkout.root)
        assert (caught.value.code, capsys.readouterr().err) == (
            1,
            (
                f"{checkout.root}/plugin: holds no manifest nustack can read after cz"
                " bump; run nustack check for the cause\n"
            ),
        )

    @SKIP_AS_ROOT
    def test_stops_on_a_changelog_it_cannot_write(
        self, checkout: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        checkout.root.chmod(0o555)
        try:
            with pytest.raises(SystemExit) as caught:
                bump(None, root=checkout.root)
        finally:
            checkout.root.chmod(0o755)
        assert (caught.value.code, capsys.readouterr().err) == (
            1,
            (
                f"{checkout.root}/CHANGELOG.md: cannot be written (Permission"
                " denied); let your user write to it and its folder, then restore the"
                " files nustack bump changed with git restore and rerun it\n"
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
        checkout.git(
            "update-ref", "refs/remotes/origin/main", str(checkout.commit("base"))
        )
        return checkout

    def test_passes_a_tag_on_main_that_names_the_version(
        self, checkout: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        release_tag(Tag("1.2.3"), root=checkout.root)
        assert capsys.readouterr() == (
            "v1.2.3 is on main and names the plugin version\n",
            "",
        )

    def test_names_a_tag_off_main_that_names_another_version(
        self, checkout: GitRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        checkout.write("notes.txt", "x")
        checkout.commit("off main")
        with pytest.raises(SystemExit) as caught:
            release_tag(Tag("9.9.9"), root=checkout.root)
        assert (caught.value.code, capsys.readouterr().err) == (
            1,
            (
                "v9.9.9: is not on main; delete it and tag the commit the squash merge"
                " made on main\n"
                "v9.9.9: does not match plugin version 1.2.3; delete it and tag v1.2.3,"
                " or set the version as .agents/skills/release/SKILL.md says\n"
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
        with pytest.raises(SystemExit) as caught:
            release_tag(Tag("1.2.3"), root=Path(checkout.root.name))
        assert (caught.value.code, capsys.readouterr().err) == (
            1,
            (
                f"{checkout.root}: git merge-base exited 128; fix the cause Git printed"
                " above, such as a missing clone or revision\n"
            ),
        )


class TestPushTagCommand:
    """A release tag lands on origin, on the commit of main that set its version.

    A later commit on main is left untagged, whether or not its pyproject.toml reads,
    and a root commit that set the version gets the tag. A version main never set, a
    working tree with changes, which the checkout would carry, and a shallow clone,
    whose history may stop above the release, are pushed nowhere, a
    fetch Git refuses stops it with the fix, and a failed push names the tag and
    leaves nothing a rerun trips on.
    """

    @pytest.fixture
    def work(self, tmp_path: Path) -> GitRepository:
        work = GitRepository(ModelRepository(tmp_path / "work").save())
        pyproject = (work.root / "pyproject.toml").read_text()
        (work.root / "pyproject.toml").unlink()
        work.git("init", "-q", "-b", "main")
        work.commit("base")
        work.write("pyproject.toml", pyproject)
        work.commit("release")
        return work

    @pytest.fixture
    def remote(self, work: GitRepository, tmp_path: Path) -> GitRepository:
        work.git("clone", "-q", "--bare", str(work.root), str(tmp_path / "remote.git"))
        return GitRepository(tmp_path / "remote.git")

    @pytest.fixture
    def clone(self, remote: GitRepository, tmp_path: Path) -> GitRepository:
        remote.git("clone", "-q", str(remote.root), str(tmp_path / "clone"))
        return GitRepository(tmp_path / "clone")

    @pytest.mark.parametrize("later", ["# A later change.\n{}", "[project"])
    def test_tags_the_commit_on_main_that_set_the_version(
        self,
        work: GitRepository,
        tmp_path: Path,
        later: str,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        release = work.git("rev-parse", "HEAD").strip()
        pyproject = (work.root / "pyproject.toml").read_text()
        work.write("pyproject.toml", later.format(pyproject))
        work.commit("later")
        work.git("clone", "-q", "--bare", str(work.root), str(tmp_path / "remote.git"))
        remote = GitRepository(tmp_path / "remote.git")
        remote.git("clone", "-q", str(remote.root), str(tmp_path / "clone"))
        clone = GitRepository(tmp_path / "clone")
        push_tag(Tag("1.2.3"), root=clone.root)
        assert (
            capsys.readouterr(),
            clone.git("rev-parse", "HEAD").strip(),
            remote.git("rev-parse", "v1.2.3").strip(),
            clone.git("tag", "--list"),
        ) == ((f"Pushed v1.2.3, on {release}\n", ""), release, release, "")

    def test_tags_a_root_commit_that_set_the_version(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        work = GitRepository(ModelRepository(tmp_path / "work").save())
        work.git("init", "-q", "-b", "main")
        release = str(work.commit("release"))
        work.git("clone", "-q", "--bare", str(work.root), str(tmp_path / "remote.git"))
        remote = GitRepository(tmp_path / "remote.git")
        remote.git("clone", "-q", str(remote.root), str(tmp_path / "clone"))
        push_tag(Tag("1.2.3"), root=tmp_path / "clone")
        assert (capsys.readouterr(), remote.git("rev-parse", "v1.2.3").strip()) == (
            (f"Pushed v1.2.3, on {release}\n", ""),
            release,
        )

    def test_pushes_nowhere_a_version_main_never_set(
        self,
        clone: GitRepository,
        remote: GitRepository,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        head = clone.git("rev-parse", "HEAD")
        with pytest.raises(SystemExit) as caught:
            push_tag(Tag("9.9.9"), root=clone.root)
        assert (
            caught.value.code,
            capsys.readouterr().err,
            clone.git("rev-parse", "HEAD"),
            remote.git("tag", "--list"),
        ) == (
            1,
            (
                "v9.9.9: names no commit on origin's main: none of its first-parent"
                " commits sets version 9.9.9; merge the release pull request, then"
                " rerun\n"
            ),
            head,
            "",
        )

    def test_pushes_nowhere_from_a_working_tree_with_changes(
        self,
        clone: GitRepository,
        remote: GitRepository,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        clone.write("notes.txt", "uncommitted")
        head = clone.git("rev-parse", "HEAD")
        with pytest.raises(SystemExit) as caught:
            push_tag(Tag("1.2.3"), root=clone.root)
        assert (
            caught.value.code,
            capsys.readouterr().err,
            clone.git("rev-parse", "HEAD"),
            remote.git("tag", "--list"),
        ) == (
            1,
            (
                f"{clone.root}: holds changes git status lists, which the check would"
                " read in place of main's commit; commit or stash them, then rerun\n"
            ),
            head,
            "",
        )

    def test_pushes_nowhere_from_a_shallow_clone(
        self,
        work: GitRepository,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        pyproject = (work.root / "pyproject.toml").read_text()
        work.write("pyproject.toml", f"# A later change.\n{pyproject}")
        work.commit("later")
        work.git("clone", "-q", "--bare", str(work.root), str(tmp_path / "remote.git"))
        remote = GitRepository(tmp_path / "remote.git")
        url = (tmp_path / "remote.git").as_uri()
        remote.git("clone", "-q", "--depth", "1", url, str(tmp_path / "clone"))
        with pytest.raises(SystemExit) as caught:
            push_tag(Tag("1.2.3"), root=tmp_path / "clone")
        assert (
            caught.value.code,
            capsys.readouterr().err,
            remote.git("tag", "--list"),
        ) == (
            1,
            (
                f"{tmp_path / 'clone'}: is a shallow clone, whose history may stop"
                " above the commit that set the version; run git fetch --unshallow"
                " origin, then rerun\n"
            ),
            "",
        )

    def test_stops_where_git_cannot_fetch(
        self,
        clone: GitRepository,
        remote: GitRepository,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        shutil.rmtree(remote.root)
        with pytest.raises(SystemExit) as caught:
            push_tag(Tag("1.2.3"), root=clone.root)
        assert (caught.value.code, capsys.readouterr().err) == (
            1,
            (
                f"{clone.root}: git fetch exited 128; fix the cause Git printed above,"
                " such as a missing clone or revision\n"
            ),
        )

    def test_names_the_tag_of_a_failed_push_and_pushes_it_on_a_rerun(
        self,
        work: GitRepository,
        clone: GitRepository,
        remote: GitRepository,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        hook = remote.root / "hooks/pre-receive"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        with pytest.raises(SystemExit) as caught:
            push_tag(Tag("1.2.3"), root=clone.root)
        failed = (
            caught.value.code,
            capsys.readouterr().err,
            clone.git("tag", "--list"),
        )
        hook.unlink()
        push_tag(Tag("1.2.3"), root=clone.root)
        release = work.git("rev-parse", "HEAD").strip()
        assert (failed, capsys.readouterr().out, remote.git("rev-parse", "v1.2.3")) == (
            (
                1,
                (
                    "v1.2.3: was not pushed to origin; fix the cause Git printed"
                    " above, such as a tag origin already holds, then rerun\n"
                ),
                "",
            ),
            f"Pushed v1.2.3, on {release}\n",
            f"{release}\n",
        )


class TestPublishCommand:
    """The release workflow publishes the tag's release, or stops naming why."""

    @pytest.fixture(autouse=True)
    def tagged(self, gh: FakeGh, github_fixtures: Path) -> None:
        gh.replay(
            *GhArgv.TAG_COMMIT_V1_2_3,
            recording=github_fixtures / "tag-commit/found.json",
        )

    def test_prints_the_published_release(
        self,
        gh: FakeGh,
        github_fixtures: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gh.replay(
            *GhArgv.RELEASE_STATE_V1_2_3,
            recording=github_fixtures / "release-state/missing.json",
        )
        publish(
            Tag("1.2.3"),
            commit=Sha("81c986c0e0a7c511f2941ed3cec09f7975687f80"),
            name_with_owner=GhArgv.REPOSITORY,
            zip_folder=tmp_path,
        )
        assert capsys.readouterr() == ("Published release v1.2.3\n", "")

    def test_stops_naming_why_it_cannot_publish(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as caught:
            publish(
                Tag("1.2.3"),
                commit=Sha("b" * 40),
                name_with_owner=GhArgv.REPOSITORY,
                zip_folder=tmp_path,
            )
        assert (caught.value.code, capsys.readouterr().err) == (
            1,
            (
                "v1.2.3: has moved off the commit CI passed on; the run the move"
                " started publishes it\n"
            ),
        )
