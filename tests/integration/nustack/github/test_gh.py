"""GitHub, read and changed through gh, as the release and sync workflows need.

Each read parses gh's real reply, each change sends gh the arguments and input it
takes, and a failed or missing gh, or one that outlasts its time limit or prints
output the harness cannot read, stops with an error naming the fix.
"""

lazy from pathlib import Path

import pytest

from nustack.github.gh import GitHub
from nustack.github.gh import GitHubError
from nustack.github.gh import ReleaseState
from nustack.release.tag import Tag
from nustack.sha import Sha
from tests.fixtures.gh import GhArgv
lazy from tests.fixtures.gh import FakeGh


class TestGitHub:
    """The workflows get GitHub's answers, or an error naming what to do next.

    A repository gh cannot read or an empty default branch raises that error, as does a
    pull request number that is not decimal or a tag commit that is not a SHA. A tag
    GitHub cannot find raises it with the fix to push the tag again, and gh's other
    failures to read a tag raise the failed command's. A missing release reads as
    missing, and a release gh cannot read, or reads as neither a draft nor published,
    raises the error. A command gets no input by default, and a failed command, a
    missing gh or a command that outlasts its time limit raises the error. The replies
    no recording holds, an empty default branch, a pull request number or tag commit
    GitHub never prints and a draft flag other than true or false, are written beside
    their tests with the reason.
    """

    def test_reads_the_default_branch(self, gh: FakeGh, github_fixtures: Path) -> None:
        gh.replay(
            *GhArgv.DEFAULT_BRANCH,
            recording=github_fixtures / "default-branch/found.json",
        )
        assert GitHub(GhArgv.REPOSITORY).default_branch() == "main"

    def test_stops_on_a_repository_gh_cannot_read(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *GhArgv.DEFAULT_BRANCH,
            recording=github_fixtures / "default-branch/missing.json",
        )
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY).default_branch()
        assert caught.value.what == (
            "gh api exited 1; fix the cause gh printed above, then rerun"
        )

    def test_stops_on_an_empty_default_branch(self, gh: FakeGh) -> None:
        # GitHub gives every repository a default branch, so no recording holds this.
        gh.reply(*GhArgv.DEFAULT_BRANCH, stdout="\n")
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY).default_branch()
        assert caught.value.what == (
            "gh names no default branch for o/r; check that the token can read the"
            " repository"
        )

    @pytest.mark.parametrize(
        ("reply", "pulls"),
        [("open-pulls/one.json", (267,)), ("open-pulls/none.json", ())],
    )
    def test_lists_the_open_pull_requests_from_this_repositorys_branch(
        self, gh: FakeGh, github_fixtures: Path, reply: str, pulls: tuple[int, ...]
    ) -> None:
        gh.replay(*GhArgv.OPEN_PULLS, recording=github_fixtures / reply)
        assert GitHub(GhArgv.REPOSITORY).open_pulls("main", "sync/w") == pulls

    def test_refuses_a_pull_request_number_that_is_not_decimal(
        self, gh: FakeGh
    ) -> None:
        # GitHub numbers every pull request, so no recording holds another value.
        gh.reply(*GhArgv.OPEN_PULLS, stdout="267\nnull\n")
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY).open_pulls("main", "sync/w")
        assert caught.value.what == (
            "an open pull request from sync/w into main has no number (gh printed"
            " other than digits for it); rerun once GitHub answers"
        )

    def test_reads_a_pull_requests_description(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *GhArgv.PULL_BODY_5, recording=github_fixtures / "pull-body/found.json"
        )
        # The harness reads gh's output as text, which turns the body's CRLF line ends
        # into LF.
        assert GitHub(GhArgv.REPOSITORY).pull_body(5) == (
            "## Summary\n"
            "\n"
            "Speeds up the integration tests that dominated CI wall time. The "
            "dominant costs were: real-model calls repeatedly fetching MSA + "
            "running AF2 embeddings, oversized diffusion loops in tests that are "
            "effectively smoke tests, and full-fidelity `DiGSO3SDE` lookup-table "
            "builds (~200s on CPU) triggered by tests that use mocked score models."
            "\n"
            "\n"
            "## CI wall-clock\n"
            "\n"
            "Baseline is the last successful CI run on `main` (PR #237 head, "
            "`b5b3619`). This PR head is `90724c9` (numbers for commit `067224d` "
            "are the local CPU cold-cache estimate — CI still in progress).\n"
            "\n"
            "| Job | Baseline | This PR | Δ |\n"
            "|---|---|---|---|\n"
            "| Linux py 3.11 | 1327s (22:07) | 761s (12:41) | \u221243% |\n"
            "| Linux py 3.12 | 2090s (34:50) | 704s (11:44) | \u221266% |\n"
            "| Linux py 3.13 | 1323s (22:03) | 651s (10:51) | \u221251% |\n"
            "\n"
            "## Per-test durations (Linux py 3.13, CI numbers)\n"
            "\n"
            "| Test | Baseline | This PR | Change that drove it |\n"
            "|---|---|---|---|\n"
            "| `test_steering_with_config_path` | 272s | ~150s (est.)¹ | (5) "
            "test-scaled yaml override |\n"
            "| "
            "`TestGenerateBatchWithSteering::test_generate_batch_with_fkc_denoiser`"
            " | 197s | 0.22s | (2) tiny `DiGSO3SDE` (mock score) |\n"
            "| "
            "`TestGenerateBatchWithSteering::test_generate_batch_with_smc_denoiser`"
            " | 196s | ~0.5s | (2) |\n"
            "| `TestGenerateBatchWithSteering::test_generate_batch_unsteered_dpm` |"
            " 195s | ~0.5s | (2) |\n"
            "| `test_sample.py::test_generate_batch` | 187s | 0.15s | (3) tiny "
            "`DiGSO3SDE` (mock score) |\n"
            "| `test_steering_with_config_dict[*]` | 3\u00d7 16s | 3\u00d7 3.3s "
            "| (1) + (4) "
            "embeds cache + trims |\n"
            "\n"
            "¹ Local CPU cold-cache measurement (`147.81s`); CI run on `067224d` "
            "still in progress.\n"
            "\n"
            "## Changes\n"
            "\n"
            "1. **Session-scoped embeddings cache** — new `cached_embeds_dir` "
            "fixture in `tests/conftest.py`, backed by "
            "`.pytest_cache/d/bioemu_embeds/` (gitignored). The ColabFold MSA fetch"
            " + AF2 forward pass runs at most once per checkout; all chignolin "
            "`sample()` tests pass `cache_embeds_dir` (or `--cache_embeds_dir` for "
            "CLI subprocesses).\n"
            "2. **Shrink `DiGSO3SDE` in mock-score tests** — "
            "`TestGenerateBatchWithSteering` and `test_generate_batch` were "
            "rebuilding the full `num_sigma=1000, l_max=2000, num_omega=2000` "
            "lookup tables despite using mocked score models. Replaced with "
            "`num_sigma=10, l_max=10, num_omega=10` (via a class-scoped `sdes` "
            "fixture for the former).\n"
            "3. **Trim `num_samples` and disable `filter_samples`** — `num_samples`"
            " reduced (10→4 in chignolin, 5→2 in CLI); `filter_samples=False` skips"
            " the mdtraj-based physical filter which was buying nothing in "
            "existence-only assertions.\n"
            "4. **Shrink diffusion `N`** — dict-based steering tests use `N=25` "
            "instead of the yaml's production `N=100`. `N<25` caused occasional PDB"
            " writer failures (coords overflowed the 8-column PDB field when "
            "samples didn't denoise enough).\n"
            "5. **Test-scaled yaml for `test_steering_with_config_path`** (commit "
            "`067224d`) — writes a tmp yaml with `N=25` and `num_particles=2` "
            "instead of loading `src/bioemu/config/steering/physical_steering.yaml`"
            " verbatim (`N=100`, `num_particles=5`).\n"
            "6. **Session-scoped SO(3) cache dir** — new `cached_so3_dir` fixture "
            "(also `.pytest_cache/`-backed) threaded via `cache_so3_dir` / "
            "`--cache_so3_dir`.\n"
            "\n"
            "## Not addressed here\n"
            "\n"
            "- `test_dpm_solver_has_gradients` (196s setup) — the shared `sdes` "
            "conftest fixture still builds full-fidelity SO(3) tables at "
            "`~/sampling_so3_cache`. Fixing this requires either persisting the "
            "cache across CI runs via `actions/cache` or splitting the fixture "
            "(since `test_ppft_loss` asserts an exact expected value that depends "
            "on the full-fidelity marginals).\n"
            "- `test_so3_score` (132s) — numerical correctness test doing a "
            "200-step forward + reverse geodesic random walk over 1000 SO(3) "
            "samples; reducing would loosen the test's Wasserstein-distance "
            "tolerance.\n"
            "\n"
            "Copilot-Session: 2a2bf724-e182-456d-a0a7-5a9bfadbd725\n"
            "\n"
        )

    def test_opens_edits_and_closes_a_pull_request(self, gh: FakeGh) -> None:
        github = GitHub(GhArgv.REPOSITORY)
        github.create_pull("main", "sync/w", "docs: sync", "Body.\n")
        github.edit_pull(12, "New.\n")
        github.close_pull(12, "Nothing to propose.")
        assert gh.calls == [
            (
                (
                    "pr",
                    "create",
                    "-R",
                    "o/r",
                    "--base",
                    "main",
                    "--head",
                    "sync/w",
                    "--title",
                    "docs: sync",
                    "--body-file",
                    "-",
                ),
                "Body.\n",
            ),
            (("pr", "edit", "12", "-R", "o/r", "--body-file", "-"), "New.\n"),
            (
                (
                    "pr",
                    "close",
                    "12",
                    "-R",
                    "o/r",
                    "--comment",
                    "Nothing to propose.",
                ),
                "",
            ),
        ]

    def test_reads_the_commit_a_tag_names(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *GhArgv.TAG_COMMIT_V1_2_3,
            recording=github_fixtures / "tag-commit/found.json",
        )
        assert GitHub(GhArgv.REPOSITORY).tag_commit(Tag("1.2.3")) == Sha(
            "81c986c0e0a7c511f2941ed3cec09f7975687f80"
        )

    def test_says_to_push_again_a_tag_github_cannot_find(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *GhArgv.TAG_COMMIT_V1_2_3,
            recording=github_fixtures / "tag-commit/missing.json",
        )
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY).tag_commit(Tag("1.2.3"))
        assert caught.value.what == (
            "names no commit GitHub can find; push it again if it was deleted, then"
            " rerun"
        )

    def test_passes_on_a_failed_tag_read_as_its_exit(
        self, gh: FakeGh, capfd: pytest.CaptureFixture[str]
    ) -> None:
        # gh's other failures, such as a lost connection, print no answer from GitHub.
        gh.reply(*GhArgv.TAG_COMMIT_V1_2_3, stderr="error connecting\n", code=1)
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY).tag_commit(Tag("1.2.3"))
        assert (caught.value.what, capfd.readouterr().err) == (
            "gh api exited 1; fix the cause gh printed above, then rerun",
            "error connecting\n",
        )

    def test_refuses_a_tag_commit_that_is_not_a_sha(self, gh: FakeGh) -> None:
        # GitHub names every tag's commit by its SHA, so no recording holds another
        # value.
        gh.reply(*GhArgv.TAG_COMMIT_V1_2_3, stdout="null\n")
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY).tag_commit(Tag("1.2.3"))
        assert caught.value.what == (
            "names no commit (gh printed other than a SHA for it); rerun once GitHub"
            " answers"
        )

    def test_reads_a_draft_release_as_a_draft(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *GhArgv.RELEASE_STATE_V1_2_3,
            recording=github_fixtures / "release-state/draft.json",
        )
        assert (
            GitHub(GhArgv.REPOSITORY).release_state(Tag("1.2.3")) is ReleaseState.DRAFT
        )

    def test_reads_a_published_release_giving_gh_no_input(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *GhArgv.RELEASE_STATE_V1_2_3,
            recording=github_fixtures / "release-state/published.json",
        )
        assert (GitHub(GhArgv.REPOSITORY).release_state(Tag("1.2.3")), gh.calls) == (
            ReleaseState.PUBLISHED,
            [(GhArgv.RELEASE_STATE_V1_2_3, "")],
        )

    def test_reads_a_missing_release_as_missing(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *GhArgv.RELEASE_STATE_V1_2_3,
            recording=github_fixtures / "release-state/missing.json",
        )
        assert (
            GitHub(GhArgv.REPOSITORY).release_state(Tag("1.2.3"))
            is ReleaseState.MISSING
        )

    @pytest.mark.parametrize(
        ("stdout", "what"),
        [
            (
                "null\n",
                (
                    "its release reads as neither a draft nor published (gh printed"
                    " other than true or false for isDraft); rerun once GitHub answers"
                ),
            ),
            (
                "1\n",
                (
                    "its release reads as neither a draft nor published (gh printed"
                    " other than true or false for isDraft); rerun once GitHub answers"
                ),
            ),
            (
                "{\n",
                (
                    "its release reads as neither a draft nor published (gh printed"
                    " other than true or false for isDraft); rerun once GitHub answers"
                ),
            ),
        ],
    )
    def test_refuses_a_draft_flag_other_than_true_or_false(
        self, gh: FakeGh, stdout: str, what: str
    ) -> None:
        # GitHub types isDraft as a boolean, so no recording holds another value.
        gh.reply(*GhArgv.RELEASE_STATE_V1_2_3, stdout=stdout)
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY).release_state(Tag("1.2.3"))
        assert caught.value.what == what

    def test_names_why_a_release_cannot_be_read(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *GhArgv.RELEASE_STATE_V1_2_3,
            recording=github_fixtures / "release-state/unauthorized.json",
        )
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY).release_state(Tag("1.2.3"))
        assert caught.value.what == (
            "its release cannot be read (HTTP 401: Bad credentials"
            " (https://api.github.com/repos/microsoft/bioemu/releases/tags/v1.4.0)\n"
            "Try authenticating with:  gh auth login); fix the cause gh names, or"
            " rerun once GitHub answers"
        )

    @pytest.mark.parametrize(
        ("prerelease", "flag"), [(True, "--prerelease"), (False, "--prerelease=false")]
    )
    def test_drafts_uploads_to_and_publishes_a_release(
        self, gh: FakeGh, tmp_path: Path, flag: str, *, prerelease: bool
    ) -> None:
        github = GitHub(GhArgv.REPOSITORY)
        github.create_draft(Tag("1.2.3"))
        github.upload(Tag("1.2.3"), (tmp_path / "a.zip", tmp_path / "b.zip"))
        github.publish(
            Tag("1.2.3"), "nustack 1.2.3", tmp_path / "notes.md", prerelease=prerelease
        )
        assert [argv for argv, _ in gh.calls] == [
            (
                "release",
                "create",
                "v1.2.3",
                "-R",
                "o/r",
                "--draft",
                "--verify-tag",
                "--notes",
                "",
            ),
            (
                "release",
                "upload",
                "v1.2.3",
                "-R",
                "o/r",
                str(tmp_path / "a.zip"),
                str(tmp_path / "b.zip"),
                "--clobber",
            ),
            (
                "release",
                "edit",
                "v1.2.3",
                "-R",
                "o/r",
                "--draft=false",
                flag,
                "--title",
                "nustack 1.2.3",
                "--notes-file",
                str(tmp_path / "notes.md"),
            ),
        ]

    def test_names_the_command_that_failed_and_the_next_step(
        self, gh: FakeGh, github_fixtures: Path
    ) -> None:
        gh.replay(
            *GhArgv.PULL_BODY_5, recording=github_fixtures / "pull-body/missing.json"
        )
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY).pull_body(5)
        assert caught.value.what == (
            "gh api exited 1; fix the cause gh printed above, then rerun"
        )

    def test_names_a_missing_gh_and_where_to_get_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PATH", str(tmp_path))
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY).pull_body(5)
        assert caught.value.what == (
            "cannot run gh (No such file or directory); install it from"
            " https://cli.github.com"
        )

    @pytest.mark.usefixtures("stalling")
    def test_stops_a_command_that_outlasts_its_time_limit(self) -> None:
        with pytest.raises(GitHubError) as caught:
            _ = GitHub(GhArgv.REPOSITORY, timeout=0.1).pull_body(5)
        assert caught.value.what == (
            "gh api took over 0.1 seconds; rerun once GitHub answers"
        )
