"""The `nustack` command's output and exit status."""

from pathlib import Path
from zipfile import ZipFile

import pytest

from nustack.cli import app
from nustack.cli import bundle
from nustack.cli import check
from nustack.cli import notes
from nustack.repository import Repository


def test_version_prints_the_plugin_version(
    version: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        app(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"{version}\n"


def test_check_passes_on_a_clean_repository(
    repository: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    check(repository.root)
    assert capsys.readouterr().out == "nustack check: no problems\n"


def test_check_exits_1_and_reports_each_problem_on_stderr(
    repository: Repository, capsys: pytest.CaptureFixture[str]
) -> None:
    repository.changelog_path.write_text("# Changelog\n")
    (repository.plugin.root / "notes.txt").write_text("notes\n")
    with pytest.raises(SystemExit) as exit_info:
        check(repository.root)
    assert exit_info.value.code == 1
    output = capsys.readouterr()
    assert output.out == ""
    lines = output.err.splitlines()
    assert any("CHANGELOG.md" in line for line in lines)
    assert any("notes.txt" in line for line in lines)


def test_check_reports_a_folder_that_is_not_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        check(tmp_path)
    assert "is missing" in capsys.readouterr().err


def test_bundle_prints_only_the_zip_path(
    repository: Repository,
    tmp_path: Path,
    version: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle(repository.root, tmp_path / "dist")
    path = tmp_path / "dist" / f"nustack-{version}.zip"
    assert capsys.readouterr().out == f"{path}\n"
    with ZipFile(path) as archive:
        assert ".devin-plugin/plugin.json" in archive.namelist()


def test_bundle_refuses_a_repository_with_problems(
    repository: Repository, tmp_path: Path
) -> None:
    repository.changelog_path.write_text("# Changelog\n")
    with pytest.raises(SystemExit):
        bundle(repository.root, tmp_path / "dist")
    assert not (tmp_path / "dist").exists()


def test_notes_prints_the_entry_for_the_plugin_version(
    repository: Repository, version: str, capsys: pytest.CaptureFixture[str]
) -> None:
    repository.changelog_path.write_text(
        f"# Changelog\n\n## [{version}] - 2026-01-01\n\n"
        "- New.\n\n```text\n## kept\n```\n\n"
        "## [0.0.0] - 2026-01-01\n\n- Old.\n"
    )
    notes(repository.root)
    assert capsys.readouterr().out == "- New.\n\n```text\n## kept\n```\n"


def test_notes_print_the_entry_as_written(
    repository: Repository, version: str, capsys: pytest.CaptureFixture[str]
) -> None:
    repository.changelog_path.write_text(
        f"# Changelog\n\n## [{version}] - 2026-01-01\n\n"
        "- See [d].\n\n[d]: https://x.io/d\n\n"
        "## [0.0.0] - 2026-01-01\n\n- Old.\n"
    )
    notes(repository.root)
    assert capsys.readouterr().out == "- See [d].\n\n[d]: https://x.io/d\n"


def test_notes_refuse_a_repository_with_problems(repository: Repository) -> None:
    repository.changelog_path.write_text("# Changelog\n")
    with pytest.raises(SystemExit) as exit_info:
        notes(repository.root)
    assert exit_info.value.code == 1
