"""The zip hosts install from holds the plugin exactly, the same bytes every time.

The zip lands whole or not at all for every reader, and a failed or interrupted run
leaves no partial file behind. A zip folder or zip path it cannot write to is a
Problem naming the next step.
"""

import re
import resource
import signal
import stat
import sys
from pathlib import Path
from pathlib import PurePosixPath
from zipfile import ZIP_STORED
from zipfile import ZipFile
from zipfile import ZipInfo

import pytest

from nustack.plugin.bundle import Bundle
from nustack.plugin.manifest import Manifest
from nustack.problem import Problem
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Tree
from tests.fixtures.permissions import SKIP_AS_ROOT
from tests.fixtures.repository import ModelRepository


class TestBundle:
    """Every host installs the same plugin from the zip; a rebuild changes no byte.

    The zip is named for the plugin and its version, each missing folder on its path is
    made, and a zip folder it cannot write to names its cause and fix. It holds each
    file in path order, regular, uncompressed, dated 1980 and made on Unix wherever it
    is written, and is readable by anyone. An earlier zip there is replaced only by a
    whole one: a zip it cannot finish keeps the earlier one, and a folder in its place
    is named.

    Each partial file is hidden beside the zip and carries its name. A run leaves only
    the zip in its folder, leaves another run's partial file alone, even one written at
    the same time, and leaves no partial file when interrupted, which only a killed run
    can leave.
    """

    MANIFEST = Manifest.parse(ModelRepository.MANIFEST.encode())
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
            "is a file, not a folder; pass --zip-folder a folder, or remove the file",
        )

    @SKIP_AS_ROOT
    def test_reports_a_folder_it_cannot_write_in(self, tmp_path: Path) -> None:
        (tmp_path / "locked").mkdir(mode=0o555)
        zip_folder = tmp_path / "locked" / "dist"
        assert Bundle(self.TREE, self.MANIFEST).write(zip_folder) == Problem(
            zip_folder,
            "cannot be written (Permission denied); pass --zip-folder a folder you can"
            " write to",
        )

    @SKIP_AS_ROOT
    def test_reports_a_read_only_folder_as_the_folders_problem(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "dist").mkdir(mode=0o555)
        assert Bundle(self.TREE, self.MANIFEST).write(tmp_path / "dist") == Problem(
            tmp_path / "dist",
            "cannot be written (Permission denied); pass --zip-folder a folder you can"
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

    @pytest.mark.parametrize("platform", ["linux", "win32"])
    def test_holds_regular_uncompressed_files_from_1980(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str
    ) -> None:
        monkeypatch.setattr(sys, "platform", platform)
        path = Bundle(self.TREE, self.MANIFEST).write(tmp_path)
        assert isinstance(path, Path)
        with ZipFile(path) as archive:
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

    def test_is_readable_by_anyone(self, written: Path) -> None:
        assert oct(stat.S_IMODE(written.stat().st_mode)) == "0o644"

    def test_reports_a_zip_it_cannot_finish_and_keeps_the_earlier_one(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "kit-1.2.3.zip").write_bytes(b"earlier")
        limit = resource.getrlimit(resource.RLIMIT_FSIZE)
        handler = signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        resource.setrlimit(resource.RLIMIT_FSIZE, (16, limit[1]))
        try:
            written = Bundle(self.TREE, self.MANIFEST).write(tmp_path)
        finally:
            resource.setrlimit(resource.RLIMIT_FSIZE, limit)
            _ = signal.signal(signal.SIGXFSZ, handler)
        assert (
            written,
            [path.name for path in tmp_path.iterdir()],
            (tmp_path / "kit-1.2.3.zip").read_bytes(),
        ) == (
            Problem(
                tmp_path,
                "cannot be written (File too large); pass --zip-folder a folder you can"
                " write to",
            ),
            ["kit-1.2.3.zip"],
            b"earlier",
        )

    def test_replaces_an_earlier_zip_in_the_same_folder(
        self, written: Path, tmp_path: Path
    ) -> None:
        earlier = tmp_path / "a" / written.name
        earlier.parent.mkdir()
        earlier.write_bytes(b"earlier")
        assert (
            Bundle(self.TREE, self.MANIFEST).write(earlier.parent),
            earlier.read_bytes(),
        ) == (earlier, written.read_bytes())

    def test_reports_a_folder_in_the_zips_place(self, tmp_path: Path) -> None:
        (tmp_path / "kit-1.2.3.zip").mkdir()
        assert (
            Bundle(self.TREE, self.MANIFEST).write(tmp_path),
            [path.name for path in tmp_path.iterdir()],
        ) == (
            Problem(
                tmp_path / "kit-1.2.3.zip",
                "cannot be written (Is a directory); remove what is in its place,"
                " or pass --zip-folder a folder you can write to",
            ),
            ["kit-1.2.3.zip"],
        )

    def test_leaves_only_the_zip_in_its_folder(self, written: Path) -> None:
        assert list(written.parent.iterdir()) == [written]

    def test_leaves_alone_the_partial_zip_of_a_run_still_writing(
        self, tmp_path: Path
    ) -> None:
        other = tmp_path / ".kit-1.2.3.zip.other.partial"
        other.write_bytes(b"PK")
        _ = Bundle(self.TREE, self.MANIFEST).write(tmp_path)
        assert ({path.name for path in tmp_path.iterdir()}, other.read_bytes()) == (
            {".kit-1.2.3.zip.other.partial", "kit-1.2.3.zip"},
            b"PK",
        )

    def test_lands_whole_beside_another_run_writing_at_the_same_time(
        self, written: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        zip_folder = tmp_path / "a"
        writestr = ZipFile.writestr
        inner: list[Path | Problem] = []
        with monkeypatch.context() as patched:

            def interleaved(archive: ZipFile, entry: ZipInfo, content: bytes) -> None:
                patched.undo()
                inner.append(Bundle(self.TREE, self.MANIFEST).write(zip_folder))
                writestr(archive, entry, content)

            patched.setattr(ZipFile, "writestr", interleaved)
            path = Bundle(self.TREE, self.MANIFEST).write(zip_folder)
        assert (
            inner,
            path,
            [entry.name for entry in zip_folder.iterdir()],
            (zip_folder / written.name).read_bytes(),
        ) == (
            [zip_folder / written.name],
            zip_folder / written.name,
            [written.name],
            written.read_bytes(),
        )

    def test_leaves_no_partial_zip_when_interrupted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        partials: list[str] = []

        def interrupted(_archive: ZipFile, *_args: object) -> None:
            partials.extend(entry.name for entry in tmp_path.iterdir())
            raise KeyboardInterrupt

        monkeypatch.setattr(ZipFile, "writestr", interrupted)
        with pytest.raises(KeyboardInterrupt):
            _ = Bundle(self.TREE, self.MANIFEST).write(tmp_path)
        assert (
            [
                re.fullmatch(r"\.kit-1\.2\.3\.zip\.\w+\.partial", name) is not None
                for name in partials
            ],
            list(tmp_path.iterdir()),
        ) == ([True], [])

    def test_is_identical_whenever_its_files_are(
        self, written: Path, tmp_path: Path
    ) -> None:
        other = tmp_path / "b" / written.name
        assert (
            Bundle(self.TREE, self.MANIFEST).write(other.parent),
            other.read_bytes(),
        ) == (other, written.read_bytes())
