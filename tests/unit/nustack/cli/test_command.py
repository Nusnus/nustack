"""Each command's arguments, help, output and exit status."""

import re
import tomllib
from pathlib import Path
from zipfile import ZipFile
lazy from collections.abc import Callable

import pytest

from nustack.cli.command import app
from nustack.cli.command import sync_description
from nustack.github.name import NameWithOwner
from nustack.github.name import RepositoryUrl
from nustack.rule import Rule
from nustack.sync.description import SyncLinks
from tests.fixtures.permissions import SKIP_AS_ROOT
from tests.fixtures.terminal import plain
lazy from tests.fixtures.repository import ModelRepository


class TestEmptyValues:
    """No command reads an empty value as a default or the folder it runs in."""

    @pytest.mark.parametrize(
        ("arguments", "usage", "error"),
        [
            (
                ["check", "--root", ""],
                "Usage: nustack check [OPTIONS]",
                "Invalid value for '--root': give a path, not an empty string",
            ),
            (
                ["bundle", "--root", ""],
                "Usage: nustack bundle [OPTIONS]",
                "Invalid value for '--root': give a path, not an empty string",
            ),
            (
                ["bundle", "--zip-folder", ""],
                "Usage: nustack bundle [OPTIONS]",
                "Invalid value for '--zip-folder': give a path, not an empty string",
            ),
            (
                ["notes", "--root", ""],
                "Usage: nustack notes [OPTIONS]",
                "Invalid value for '--root': give a path, not an empty string",
            ),
            (
                ["sync-description", "--upstream-url", ""],
                "Usage: nustack sync-description [OPTIONS]",
                "Invalid value for '--upstream-url': give a value, not an empty string",
            ),
            (
                ["sync-description", "--run", ""],
                "Usage: nustack sync-description [OPTIONS]",
                "Invalid value for '--run': give a value, not an empty string",
            ),
            (
                ["sync-description", "--checks", ""],
                "Usage: nustack sync-description [OPTIONS]",
                "Invalid value for '--checks': give a value, not an empty string",
            ),
            (
                ["sync-description", "--clone", ""],
                "Usage: nustack sync-description [OPTIONS]",
                "Invalid value for '--clone': give a path, not an empty string",
            ),
            (
                ["sync-description", "--source-folder", ""],
                "Usage: nustack sync-description [OPTIONS]",
                "Invalid value for '--source-folder': give a path, not an empty string",
            ),
            (
                ["sync-description", "--folder", ""],
                "Usage: nustack sync-description [OPTIONS]",
                "Invalid value for '--folder': give a path, not an empty string",
            ),
            (
                ["sync-description", "--root", ""],
                "Usage: nustack sync-description [OPTIONS]",
                "Invalid value for '--root': give a path, not an empty string",
            ),
            (
                ["sync", "--upstream-url", ""],
                "Usage: nustack sync [OPTIONS]",
                "Invalid value for '--upstream-url': give a value, not an empty string",
            ),
            (
                ["sync", "--run", ""],
                "Usage: nustack sync [OPTIONS]",
                "Invalid value for '--run': give a value, not an empty string",
            ),
            (
                ["sync", "--checks", ""],
                "Usage: nustack sync [OPTIONS]",
                "Invalid value for '--checks': give a value, not an empty string",
            ),
            (
                ["sync", "--clone", ""],
                "Usage: nustack sync [OPTIONS]",
                "Invalid value for '--clone': give a path, not an empty string",
            ),
            (
                ["sync", "--source-folder", ""],
                "Usage: nustack sync [OPTIONS]",
                "Invalid value for '--source-folder': give a path, not an empty string",
            ),
            (
                ["sync", "--folder", ""],
                "Usage: nustack sync [OPTIONS]",
                "Invalid value for '--folder': give a path, not an empty string",
            ),
            (
                ["sync", "--branch", ""],
                "Usage: nustack sync [OPTIONS]",
                "Invalid value for '--branch': give a value, not an empty string",
            ),
            (
                ["sync", "--remote-url", ""],
                "Usage: nustack sync [OPTIONS]",
                "Invalid value for '--remote-url': give a value, not an empty string",
            ),
            (
                ["sync", "--name-with-owner", ""],
                "Usage: nustack sync [OPTIONS]",
                (
                    "Invalid value for '--name-with-owner': give a value, not an empty"
                    " string"
                ),
            ),
            (
                ["sync", "--root", ""],
                "Usage: nustack sync [OPTIONS]",
                "Invalid value for '--root': give a path, not an empty string",
            ),
            (
                ["release-tag", ""],
                "Usage: nustack release-tag [OPTIONS] {tag}",
                "Invalid value for 'tag': give a value, not an empty string",
            ),
            (
                ["release-tag", "v1.2.3", "--root", ""],
                "Usage: nustack release-tag [OPTIONS] {tag}",
                "Invalid value for '--root': give a path, not an empty string",
            ),
            (
                ["publish", ""],
                "Usage: nustack publish [OPTIONS] {tag}",
                "Invalid value for 'tag': give a value, not an empty string",
            ),
            (
                ["publish", "v1.2.3", "--commit", ""],
                "Usage: nustack publish [OPTIONS] {tag}",
                "Invalid value for '--commit': give a value, not an empty string",
            ),
            (
                ["publish", "v1.2.3", "--name-with-owner", ""],
                "Usage: nustack publish [OPTIONS] {tag}",
                (
                    "Invalid value for '--name-with-owner': give a value, not an empty"
                    " string"
                ),
            ),
            (
                ["publish", "v1.2.3", "--zip-folder", ""],
                "Usage: nustack publish [OPTIONS] {tag}",
                "Invalid value for '--zip-folder': give a path, not an empty string",
            ),
        ],
    )
    @pytest.mark.usefixtures("elsewhere")
    def test_are_refused_by_every_command(
        self,
        arguments: list[str],
        usage: str,
        error: str,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("COLUMNS", "80")
        with pytest.raises(SystemExit) as caught:
            _ = app(arguments, prog_name="nustack")
        lines = plain(capsys.readouterr().err).splitlines()
        assert (caught.value.code, lines[0], lines[3].strip("│ ")) == (2, usage, error)


class TestHelp:
    """-h, and nustack alone, show how to call nustack and each command."""

    @pytest.mark.parametrize(
        ("arguments", "usage"),
        [
            (["-h"], "Usage: nustack [OPTIONS] COMMAND [ARGS]..."),
            (["--help"], "Usage: nustack [OPTIONS] COMMAND [ARGS]..."),
            ([], "Usage: nustack [OPTIONS] COMMAND [ARGS]..."),
            (["check", "-h"], "Usage: nustack check [OPTIONS]"),
            (["bundle", "-h"], "Usage: nustack bundle [OPTIONS]"),
            (["notes", "-h"], "Usage: nustack notes [OPTIONS]"),
            (["sync-description", "-h"], "Usage: nustack sync-description [OPTIONS]"),
            (["sync", "-h"], "Usage: nustack sync [OPTIONS]"),
            (["release-tag", "-h"], "Usage: nustack release-tag [OPTIONS] {tag}"),
            (["publish", "-h"], "Usage: nustack publish [OPTIONS] {tag}"),
        ],
    )
    def test_prints_the_usage_and_exits_0(
        self,
        arguments: list[str],
        usage: str,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("COLUMNS", "80")
        with pytest.raises(SystemExit) as caught:
            _ = app(arguments, prog_name="nustack")
        output = capsys.readouterr()
        lines = plain(output.out).splitlines()
        assert (caught.value.code, lines[1].strip(), output.err) == (0, usage, "")

    @pytest.mark.parametrize(
        ("arguments", "line"),
        [
            (
                ["check", "-h"],
                "--root          <path>  The nustack repository's folder. [default: .]",
            ),
            (
                ["bundle", "-h"],
                (
                    "--zip-folder          <path>  The folder to write the zip into."
                    " [default: dist]"
                ),
            ),
            (
                ["notes", "-h"],
                "--root          <path>  The nustack repository's folder. [default: .]",
            ),
            (
                ["sync-description", "-h"],
                (
                    "*  --upstream-url           <url>   The upstream repository's URL."
                    " [required]"
                ),
            ),
            (
                ["sync-description", "-h"],
                (
                    "*  --source-folder          <path>  The skill's folder in"
                    " upstream. [required]"
                ),
            ),
            (
                ["sync-description", "-h"],
                (
                    "--root                   <path>  The nustack repository's folder."
                    " [default: .]"
                ),
            ),
            (
                ["release-tag", "-h"],
                "*    tag      <tag>  The release's tag. [required]",
            ),
            (
                ["publish", "-h"],
                (
                    "--zip-folder               <path>          The folder that holds"
                    " the zip and notes.md CI built. [default: dist]"
                ),
            ),
        ],
    )
    def test_describes_each_option_and_its_default(
        self,
        arguments: list[str],
        line: str,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("COLUMNS", "120")
        with pytest.raises(SystemExit):
            _ = app(arguments, prog_name="nustack")
        output = plain(capsys.readouterr().out)
        rows = [row.strip("│ ") for row in output.splitlines()]
        assert line in rows


class TestCheck:
    """make check and CI fail exactly when a rule breaks, naming each place to fix.

    A relative root's problems name full paths, and a root the check cannot stat, or
    that is a symlink loop, a file or gone, stops the check with the reason.
    """

    def test_lists_each_rule_in_its_help(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("COLUMNS", "1000")
        with pytest.raises(SystemExit):
            _ = app(["check", "--help"], prog_name="nustack")
        unpadded = re.sub(r"(?m)^ | +$", "", plain(capsys.readouterr().out))
        # TestRule pins Rule.help() word for word, so this test takes its text
        # from Rule.help() and guards how check passes it to Typer and how the
        # help renders it.
        assert unpadded.partition("╭─ Options")[0] == (
            f"\nUsage: nustack check [OPTIONS]\n\n{Rule.help()}\n\n"
        )

    @pytest.mark.usefixtures("elsewhere")
    def test_takes_its_root_as_an_option(
        self, repository: ModelRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as caught:
            _ = app(["check", "--root", str(repository.save())])
        assert (caught.value.code, capsys.readouterr()) == (
            0,
            ("nustack check: no problems\n", ""),
        )

    def test_defaults_its_root_to_the_folder_it_runs_in(
        self,
        repository: ModelRepository,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(repository.save())
        with pytest.raises(SystemExit) as caught:
            _ = app(["check"])
        assert (caught.value.code, capsys.readouterr()) == (
            0,
            ("nustack check: no problems\n", ""),
        )

    def test_names_each_problem_by_its_full_path_from_a_relative_root(
        self,
        repository: ModelRepository,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repository.remove("README.md")
        root = repository.save()
        monkeypatch.chdir(root.parent)
        with pytest.raises(SystemExit):
            _ = app(["check", "--root", root.name])
        assert capsys.readouterr().err == (
            f"{root}/README.md: is missing; add it with the plugin's guide\n"
        )

    @SKIP_AS_ROOT
    def test_stops_at_a_root_it_cannot_stat_with_the_reason(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        (tmp_path / "shut").mkdir()
        (tmp_path / "shut").chmod(0)
        try:
            with pytest.raises(SystemExit) as caught:
                _ = app(["check", "--root", str(tmp_path / "shut" / "root")])
        finally:
            (tmp_path / "shut").chmod(0o755)
        assert (caught.value.code, capsys.readouterr()) == (
            1,
            (
                "",
                (
                    f"{tmp_path / 'shut' / 'root'}: cannot be opened (Permission"
                    " denied); give the folder read and execute permission\n"
                ),
            ),
        )

    @pytest.mark.parametrize(
        "build",
        [
            pytest.param(lambda root: root.symlink_to(root), id="symlink-loop"),
            pytest.param(lambda root: root.write_text("x"), id="file"),
            pytest.param(lambda _: None, id="gone"),
        ],
    )
    def test_stops_at_a_root_that_is_not_a_folder(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        build: Callable[[Path], object],
    ) -> None:
        root = tmp_path / "root"
        build(root)
        with pytest.raises(SystemExit) as caught:
            _ = app(["check", "--root", str(root)])
        assert (caught.value.code, capsys.readouterr()) == (
            1,
            (
                "",
                (
                    f"{root}: is not a folder, so the check stops here; pass the"
                    " repository's folder as --root\n"
                ),
            ),
        )

    def test_exits_1_with_each_problem_on_stderr(
        self, repository: ModelRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repository.remove("README.md")
        repository.write("plugin/notes.txt", "x")
        root = repository.save()
        with pytest.raises(SystemExit) as caught:
            _ = app(["check", "--root", str(root)])
        assert (caught.value.code, capsys.readouterr()) == (
            1,
            (
                "",
                (
                    f"{root}/plugin/notes.txt: is not Markdown; remove it or move it"
                    " out of the plugin\n"
                    f"{root}/README.md: is missing; add it with the plugin's guide\n"
                ),
            ),
        )


class TestBundle:
    """make bundle gets one path to upload, and no zip of a broken plugin.

    It takes its root and zip folder as options, the folder it runs in and dist by
    default. A broken plugin gets no zip; otherwise the zip holds the plugin's files
    and only its path prints. A zip folder it cannot write to exits 1 naming it.
    """

    @pytest.mark.usefixtures("elsewhere")
    def test_takes_its_root_and_zip_folder_as_options(
        self, repository: ModelRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = repository.save()
        with pytest.raises(SystemExit) as caught:
            _ = app(["bundle", "--root", str(root), "--zip-folder", "out"])
        assert (caught.value.code, capsys.readouterr()) == (
            0,
            ("out/kit-1.2.3.zip\n", ""),
        )

    def test_defaults_to_the_folder_it_runs_in_and_dist(
        self,
        repository: ModelRepository,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(repository.save())
        with pytest.raises(SystemExit) as caught:
            _ = app(["bundle"])
        assert (caught.value.code, capsys.readouterr()) == (
            0,
            ("dist/kit-1.2.3.zip\n", ""),
        )

    def test_writes_nothing_for_a_repository_with_problems(
        self, repository: ModelRepository, tmp_path: Path
    ) -> None:
        repository.remove("README.md")
        with pytest.raises(SystemExit):
            _ = app(
                [
                    "bundle",
                    "--root",
                    str(repository.save()),
                    "--zip-folder",
                    str(tmp_path / "dist"),
                ]
            )
        assert not (tmp_path / "dist").exists()

    def test_writes_the_plugins_files_and_prints_only_the_zip_path(
        self,
        repository: ModelRepository,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        root = repository.save()
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            _ = app(["bundle", "--root", str(root)])
        path = Path("dist/kit-1.2.3.zip")
        with ZipFile(path) as archive:
            names = archive.namelist()
        assert (capsys.readouterr().out, names[0]) == (
            f"{path}\n",
            ".claude-plugin/plugin.json",
        )

    def test_exits_1_naming_a_zip_folder_it_cannot_write_to(
        self,
        repository: ModelRepository,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        zip_folder = tmp_path / "out"
        zip_folder.write_text("x")
        with pytest.raises(SystemExit) as caught:
            _ = app(
                [
                    "bundle",
                    "--root",
                    str(repository.save()),
                    "--zip-folder",
                    str(zip_folder),
                ]
            )
        assert (caught.value.code, capsys.readouterr()) == (
            1,
            (
                "",
                (
                    f"{zip_folder}: is a file, not a folder; pass --zip-folder a"
                    " folder, or remove the file\n"
                ),
            ),
        )


class TestNotes:
    """The release publishes the page built around the changelog entry.

    While a check fails, it publishes nothing.
    """

    PAGE_END = (
        "## 🚀 Quick start\n\n### 1️⃣ Install\n\nRun `kit add`.\n\n"
        "### 2️⃣ Use\n\nRun `kit`.\n\n"
        "**Full changelog:** [`v1.2.2...v1.2.3`]"
        "(https://example.com/nus/kit/compare/v1.2.2...v1.2.3)\n"
    )
    NOTES = (
        "> **[kit](https://example.com/nus/kit)** · A kit.\n\n"
        "## 🆕 What's new\n\n### Added\n\n- Adds the kit.\n\n" + PAGE_END
    )

    @pytest.mark.usefixtures("elsewhere")
    def test_takes_its_root_as_an_option(
        self, repository: ModelRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as caught:
            _ = app(["notes", "--root", str(repository.save())])
        assert (caught.value.code, capsys.readouterr()) == (
            0,
            (self.NOTES, ""),
        )

    def test_defaults_its_root_to_the_folder_it_runs_in(
        self,
        repository: ModelRepository,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(repository.save())
        with pytest.raises(SystemExit) as caught:
            _ = app(["notes"])
        assert (caught.value.code, capsys.readouterr()) == (
            0,
            (self.NOTES, ""),
        )

    def test_exits_1_for_a_repository_with_problems(
        self, repository: ModelRepository
    ) -> None:
        repository.remove("README.md")
        with pytest.raises(SystemExit) as caught:
            _ = app(["notes", "--root", str(repository.save())])
        assert caught.value.code == 1

    def test_prints_the_entry_for_the_plugin_version_as_written(
        self, repository: ModelRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repository.edit(
            "CHANGELOG.md",
            "- Adds the kit.\n",
            "- See [d].\n\n```text\n## kept\n```\n\n[d]: https://x.io/d\n",
        )
        with pytest.raises(SystemExit):
            _ = app(["notes", "--root", str(repository.save())])
        assert capsys.readouterr().out == (
            "> **[kit](https://example.com/nus/kit)** · A kit.\n\n"
            "## 🆕 What's new\n\n### Added\n\n"
            "- See [d].\n\n```text\n## kept\n```\n\n[d]: https://x.io/d\n\n"
            + self.PAGE_END
        )


class TestSyncDescription:
    """No sync PR opens from a template that lost what the sync fills.

    A missing template stops the command too, named by its full path.
    """

    LINKS = SyncLinks(
        RepositoryUrl("x.io", NameWithOwner("up", "skills")),
        "https://x.io/run",
        "https://x.io/checks",
    )

    def test_exits_1_naming_the_missing_template_by_its_full_path(
        self,
        repository: ModelRepository,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repository.remove(".github/pull_request_template.md")
        root = repository.save()
        monkeypatch.chdir(root.parent)
        with pytest.raises(SystemExit) as caught:
            sync_description(
                upstream_url=self.LINKS.upstream_url,
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=root,
                source_folder="skills/s",
                folder="copy",
                root=Path(root.name),
            )
        output = capsys.readouterr()
        assert (caught.value.code, output.out, output.err) == (
            1,
            "",
            (
                f"{root}/.github/pull_request_template.md: is missing; restore it,"
                " since the sync fills it\n"
            ),
        )

    def test_exits_1_naming_each_line_the_template_lost(
        self, repository: ModelRepository, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repository.write(
            ".github/pull_request_template.md",
            "<!-- Lead -->\n\n"
            "| **Feedback wanted** | |\n"
            "| <!-- mark --> **[<!-- check -->](<!-- run link -->)** |"
            " <!-- result --> |\n\n<!-- Files -->\n\n<!-- One heading per idea -->\n",
        )
        root = repository.save()
        with pytest.raises(SystemExit) as caught:
            sync_description(
                upstream_url=self.LINKS.upstream_url,
                run=self.LINKS.run,
                checks=self.LINKS.checks,
                clone=root,
                source_folder="skills/s",
                folder="copy",
                root=root,
            )
        output = capsys.readouterr()
        assert (caught.value.code, output.out, output.err) == (
            1,
            "",
            (
                f'{root}/.github/pull_request_template.md: lost "| **Risk** | |", which'
                " the sync's description needs; restore it, or change SyncTemplate to"
                " match\n"
                f'{root}/.github/pull_request_template.md: lost "## ⚖️ Decisions", which'
                " the sync's description needs; restore it, or change SyncTemplate to"
                " match\n"
            ),
        )


class TestVersion:
    """`nustack --version` prints pyproject.toml's version, even beside --help."""

    @pytest.mark.parametrize("arguments", [["--version"], ["--version", "--help"]])
    def test_prints_the_one_pyproject_declares(
        self,
        arguments: list[str],
        pyproject: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        version = tomllib.loads(pyproject.read_text())["project"]["version"]
        with pytest.raises(SystemExit) as caught:
            _ = app(arguments)
        assert (caught.value.code, capsys.readouterr()) == (0, (f"{version}\n", ""))
