"""The zip hosts install from holds the plugin exactly, the same bytes every time.

An output folder or zip path it cannot write to is a Problem naming the next step.
"""

import stat
from pathlib import Path
from pathlib import PurePosixPath
from zipfile import ZIP_STORED
from zipfile import ZipFile

import pytest

from nustack.plugin.bundle import Bundle
from nustack.plugin.manifest import Manifest
from nustack.problem import Problem
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Tree


class TestBundle:
    """Every host installs the same plugin from the zip; a rebuild changes no byte.

    Each missing folder on its path is made, and an earlier zip there replaced. An
    output path it cannot write to names its cause and fix.
    """

    MANIFEST = Manifest.parse(
        b'{"name": "kit", "version": "1.2.3", "description": "A kit.",'
        b' "author": {"name": "Ada"}, "homepage": "https://example.com/kit",'
        b' "repository": "https://example.com/kit", "license": "MIT"}'
    )
    TREE = Tree(
        Path("/r/plugin"),
        frozendict(
            {
                PurePosixPath("skills"): Folder(),
                PurePosixPath("skills/a/SKILL.md"): File(b"# A\n"),
                PurePosixPath("skills/a-b.md"): File(b"# AB\n"),
                PurePosixPath("LICENSE"): File(b"MIT License\n"),
            }
        ),
    )

    @pytest.fixture
    def written(self, tmp_path: Path) -> Path:
        path = Bundle(self.TREE, self.MANIFEST).write(tmp_path)
        assert isinstance(path, Path)
        return path

    def test_is_named_for_the_plugin_and_its_version(self, tmp_path: Path) -> None:
        assert Bundle(self.TREE, self.MANIFEST).write(tmp_path / "dist") == (
            tmp_path / "dist" / "kit-1.2.3.zip"
        )

    def test_makes_each_missing_folder_on_its_path(self, tmp_path: Path) -> None:
        assert Bundle(self.TREE, self.MANIFEST).write(tmp_path / "a" / "dist") == (
            tmp_path / "a" / "dist" / "kit-1.2.3.zip"
        )

    def test_reports_a_file_in_the_folders_place(self, tmp_path: Path) -> None:
        (tmp_path / "dist").write_text("x")
        assert Bundle(self.TREE, self.MANIFEST).write(tmp_path / "dist") == Problem(
            tmp_path / "dist",
            "is a file, not a folder; pass --out a folder, or remove the file",
        )

    def test_reports_a_folder_it_cannot_write_in(self, tmp_path: Path) -> None:
        (tmp_path / "locked").mkdir(mode=0o555)
        folder = tmp_path / "locked" / "dist"
        assert Bundle(self.TREE, self.MANIFEST).write(folder) == Problem(
            folder,
            "cannot be written (Permission denied); pass --out a folder you can"
            " write to",
        )

    def test_reports_a_folder_in_the_zips_place(self, tmp_path: Path) -> None:
        (tmp_path / "kit-1.2.3.zip").mkdir()
        assert Bundle(self.TREE, self.MANIFEST).write(tmp_path) == Problem(
            tmp_path / "kit-1.2.3.zip",
            "cannot be written (Is a directory); remove what is in its place, or"
            " pass --out a folder you can write to",
        )

    def test_reports_a_read_only_folder_as_the_folders_problem(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "dist").mkdir(mode=0o555)
        assert Bundle(self.TREE, self.MANIFEST).write(tmp_path / "dist") == Problem(
            tmp_path / "dist",
            "cannot be written (Permission denied); pass --out a folder you can"
            " write to",
        )

    def test_holds_each_file_in_path_order(self, written: Path) -> None:
        with ZipFile(written) as archive:
            contents = [(name, archive.read(name)) for name in archive.namelist()]
        assert contents == [
            ("LICENSE", b"MIT License\n"),
            ("skills/a/SKILL.md", b"# A\n"),
            ("skills/a-b.md", b"# AB\n"),
        ]

    def test_holds_regular_uncompressed_files_from_1980(self, written: Path) -> None:
        with ZipFile(written) as archive:
            entries = archive.infolist()
        assert {
            (
                entry.create_system,
                entry.external_attr >> 16,
                entry.compress_type,
                entry.date_time,
            )
            for entry in entries
        } == {(3, stat.S_IFREG | 0o644, ZIP_STORED, (1980, 1, 1, 0, 0, 0))}

    def test_replaces_an_earlier_bundle_in_the_same_folder(self, written: Path) -> None:
        first = written.read_bytes()
        assert (
            Bundle(self.TREE, self.MANIFEST).write(written.parent),
            written.read_bytes(),
        ) == (written, first)

    def test_is_identical_whenever_its_files_are(
        self, written: Path, tmp_path: Path
    ) -> None:
        other = tmp_path / "b" / written.name
        assert (
            Bundle(self.TREE, self.MANIFEST).write(other.parent),
            other.read_bytes(),
        ) == (other, written.read_bytes())
