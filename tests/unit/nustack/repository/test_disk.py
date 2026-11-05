"""The disk reads into the values every check decides on, never past a symlink.

A path it cannot read, stat or list keeps the disk's reason, and one that an entry
above it blocks names that entry, as the model repository does.
"""

import json
import os
import socket
from pathlib import Path
from pathlib import PurePosixPath
from unittest import mock

from nustack.problem import Problem
from nustack.repository.disk import Disk
from nustack.repository.repository import Repository
from nustack.tree import Blocked
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Missing
from nustack.tree import NotAFolder
from nustack.tree import Read
from nustack.tree import Special
from nustack.tree import Symlink
from nustack.tree import Tree
from nustack.tree import Unopened
from nustack.tree import Unreadable
from tests.fixtures.permissions import SKIP_AS_ROOT
lazy from tests.fixtures.repository import ModelRepository


class TestDisk:
    """Checks get the repository as it is on disk, read without following a link out.

    Disk reads what the model repository holds, a path under a file as blocked, and
    the folders it cannot list in path order. A missing plugin, one under a file or
    one it cannot stat, a symlinked root or a file in the plugin's place reads as
    one entry; a folder it cannot open or a symlink stops all reading, and entries
    list in path order. A path reads by what it holds, and one it cannot read keeps
    the disk's reason.

    A listing of a missing folder, or of a file in a folder's place, holds nothing,
    a folder it cannot open is listed as such, and a listing holds each path that is
    a regular file or links to one, leaving out caches.

    Every scan and listing leaves out each path Git ignores, and nothing under a
    folder it ignores; outside a Git repository, Git ignores nothing.
    """

    def test_reads_what_the_model_repository_holds(
        self, repository: ModelRepository
    ) -> None:
        assert Disk(repository.save()).snapshot() == repository.snapshot()

    def test_reads_nothing_git_ignores(self, repository: ModelRepository) -> None:
        root = repository.save()
        for path in (
            "plugin/.DS_Store",
            ".agents/skills/vendored/.DS_Store",
            "src/.DS_Store",
            "tests/cache/a.py",
            "vendored/old.json/a.json",
        ):
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_bytes(b"\0")
        (root / "plugin/skills/cache").mkdir()
        (root / "plugin/skills/cache/a").symlink_to(root / "README.md")
        ignored = frozenset(
            {
                PurePosixPath("plugin/.DS_Store"),
                PurePosixPath("plugin/skills/cache"),
                PurePosixPath(".agents/skills/vendored/.DS_Store"),
                PurePosixPath("src/.DS_Store"),
                PurePosixPath("tests/cache"),
                PurePosixPath("vendored/old.json"),
            }
        )
        assert Disk(root, ignored).snapshot() == repository.snapshot()

    def test_ignores_nothing_outside_a_git_repository(self, tmp_path: Path) -> None:
        assert Disk.of(tmp_path) == Disk(tmp_path)

    def test_reads_no_record_through_a_symlinked_records_folder(
        self, repository: ModelRepository
    ) -> None:
        root = repository.save()
        records = root.with_name("records")
        (root / "vendored").rename(records)
        (root / "vendored").symlink_to(records)
        assert Repository(Disk(root).snapshot()).problems() == [
            Problem(
                root / "vendored/copy.json",
                f"cannot be read, since {root}/vendored is a symlink, which the check"
                " never reads through; replace it with the folder itself",
            )
        ]

    def test_reads_the_skill_folders_of_every_record_in_a_destination(self) -> None:
        records: frozendict[PurePosixPath, Read] = frozendict(
            {
                PurePosixPath("vendored/a.json"): File(
                    json.dumps(
                        {
                            "upstream": "https://github.com/up/skills",
                            "source": "skills",
                            "folder": ".agents/skills",
                            "skills": ["a"],
                            "commit": None,
                            "files": {},
                        },
                        indent=2,
                    ).encode()
                    + b"\n"
                ),
                PurePosixPath("vendored/b.json"): File(
                    json.dumps(
                        {
                            "upstream": "https://github.com/up/skills",
                            "source": "skills",
                            "folder": "plugin/skills",
                            "skills": ["b"],
                            "commit": None,
                            "files": {},
                        },
                        indent=2,
                    ).encode()
                    + b"\n"
                ),
                PurePosixPath("vendored/c.json"): File(
                    json.dumps(
                        {
                            "upstream": "https://github.com/up/skills",
                            "source": "skills",
                            "folder": "src",
                            "skills": ["c"],
                            "commit": None,
                            "files": {},
                        },
                        indent=2,
                    ).encode()
                    + b"\n"
                ),
            }
        )
        assert Disk.skill_folders(records) == {
            PurePosixPath(".agents/skills/a"),
            PurePosixPath("plugin/skills/b"),
        }

    def test_reads_a_path_under_a_file_as_blocked_where_the_model_repository_does(
        self, repository: ModelRepository
    ) -> None:
        repository.remove(".claude-plugin/marketplace.json")
        repository.write(".claude-plugin", "x")
        assert Disk(repository.save()).snapshot() == repository.snapshot()

    @SKIP_AS_ROOT
    def test_orders_the_folders_it_cannot_list_by_path(self, tmp_path: Path) -> None:
        for folder in ("tests/b", "tests/a", "src/shut"):
            (tmp_path / folder).mkdir(parents=True)
            (tmp_path / folder).chmod(0)
        try:
            unlisted = Disk(tmp_path).snapshot().unlisted
        finally:
            for folder in ("tests/b", "tests/a", "src/shut"):
                (tmp_path / folder).chmod(0o755)
        assert list(unlisted) == [
            PurePosixPath("src/shut"),
            PurePosixPath("tests/a"),
            PurePosixPath("tests/b"),
        ]

    def test_reads_a_missing_plugin_as_one_missing_entry(self, tmp_path: Path) -> None:
        assert Disk(tmp_path).tree(tmp_path / "plugin") == Tree(
            tmp_path / "plugin", frozendict({PurePosixPath("."): Missing()})
        )

    def test_reads_a_plugin_under_a_file_as_one_missing_entry(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "file").write_text("")
        assert Disk(tmp_path).tree(tmp_path / "file" / "plugin") == Tree(
            tmp_path / "file" / "plugin", frozendict({PurePosixPath("."): Missing()})
        )

    @SKIP_AS_ROOT
    def test_reads_a_plugin_it_cannot_stat_as_one_unopened_entry(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "shut").mkdir()
        (tmp_path / "shut").chmod(0)
        try:
            tree = Disk(tmp_path).tree(tmp_path / "shut" / "plugin")
        finally:
            (tmp_path / "shut").chmod(0o755)
        assert tree == Tree(
            tmp_path / "shut" / "plugin",
            frozendict(
                {
                    PurePosixPath("."): Unopened(
                        "cannot be opened (Permission denied); give the folder read"
                        " and execute permission"
                    )
                }
            ),
        )

    def test_reads_a_symlinked_root_as_one_symlink(self, tmp_path: Path) -> None:
        (tmp_path / "outside").mkdir()
        (tmp_path / "outside" / "a.md").write_text("x")
        (tmp_path / "plugin").symlink_to(tmp_path / "outside")
        with mock.patch.object(Path, "read_bytes", autospec=True) as read:
            tree = Disk(tmp_path).tree(tmp_path / "plugin")
        read.assert_not_called()
        assert tree == Tree(
            tmp_path / "plugin", frozendict({PurePosixPath("."): Symlink()})
        )

    def test_reads_a_file_in_the_plugins_place_as_no_folder(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "plugin").write_text("x")
        with mock.patch.object(Path, "read_bytes", autospec=True) as read:
            tree = Disk(tmp_path).tree(tmp_path / "plugin")
        read.assert_not_called()
        assert tree == Tree(
            tmp_path / "plugin", frozendict({PurePosixPath("."): NotAFolder()})
        )

    @SKIP_AS_ROOT
    def test_reads_no_file_once_it_finds_a_folder_it_cannot_open(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "a.md").write_text("x")
        (tmp_path / "shut").mkdir()
        (tmp_path / "shut").chmod(0)
        try:
            entries = dict(Disk(tmp_path).tree(tmp_path).entries)
        finally:
            (tmp_path / "shut").chmod(0o755)
        assert entries == {
            PurePosixPath("shut"): Unopened(
                "cannot be opened (Permission denied); give the folder read and"
                " execute permission"
            )
        }

    def test_reads_each_entry_by_its_kind(self, tmp_path: Path) -> None:
        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "SKILL.md").write_bytes(b"# A\n")
        os.mkfifo(tmp_path / "fifo")
        assert dict(Disk(tmp_path).tree(tmp_path).entries) == {
            PurePosixPath("fifo"): Special(),
            PurePosixPath("skills"): Folder(),
            PurePosixPath("skills/SKILL.md"): File(b"# A\n"),
        }

    def test_reads_no_file_once_it_finds_a_symlink(self, tmp_path: Path) -> None:
        (tmp_path / "outside.md").write_text("x")
        (tmp_path / "plugin").mkdir()
        (tmp_path / "plugin" / "a.md").write_text("x")
        (tmp_path / "plugin" / "link").symlink_to(tmp_path / "outside.md")
        with mock.patch.object(Path, "read_bytes", autospec=True) as read:
            tree = Disk(tmp_path).tree(tmp_path / "plugin")
        read.assert_not_called()
        assert tree == Tree(
            tmp_path / "plugin", frozendict({PurePosixPath("link"): Symlink()})
        )

    def test_lists_each_symlink_in_path_order(self, tmp_path: Path) -> None:
        for name in ("b", "a", "c"):
            (tmp_path / name).symlink_to(tmp_path)
        assert list(Disk(tmp_path).tree(tmp_path).entries) == [
            PurePosixPath("a"),
            PurePosixPath("b"),
            PurePosixPath("c"),
        ]

    def test_lists_each_entry_in_path_order(self, tmp_path: Path) -> None:
        for name in ("b", "a", "c"):
            (tmp_path / name).write_text("x")
        assert list(Disk(tmp_path).tree(tmp_path).entries) == [
            PurePosixPath("a"),
            PurePosixPath("b"),
            PurePosixPath("c"),
        ]

    def test_reads_a_path_that_holds_no_file_by_what_it_holds(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "folder").mkdir()
        (tmp_path / "file").write_text("x")
        with socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(tmp_path / "socket"))
            assert (
                Disk.read(tmp_path / "gone"),
                Disk.read(tmp_path / "file" / "inside"),
                Disk.read(tmp_path / "socket"),
                Disk.read(tmp_path / "folder"),
            ) == (
                Missing(),
                Blocked(
                    tmp_path / "file",
                    "is a file where a folder belongs; move the file, then add the"
                    " folder",
                ),
                Special(),
                Folder(),
            )

    @SKIP_AS_ROOT
    def test_reads_a_path_in_a_folder_it_cannot_open_as_unreadable_naming_the_folder(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "shut").mkdir()
        (tmp_path / "shut").chmod(0)
        try:
            read = Disk.read(tmp_path / "shut" / "a")
        finally:
            (tmp_path / "shut").chmod(0o755)
        assert read == Unreadable(
            f"cannot be read, since {tmp_path / 'shut'} cannot be opened (Permission"
            " denied); give the folder read and execute permission"
        )

    def test_reads_a_path_it_cannot_stat_for_another_reason_with_that_reason(
        self, tmp_path: Path
    ) -> None:
        assert Disk.read(tmp_path / ("a" * 300)) == Unreadable(
            "cannot be read (File name too long); make it readable"
        )

    def test_reads_a_path_through_a_symlink_loop_as_unreadable_naming_the_symlink(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "loop").symlink_to(tmp_path / "loop")
        assert (Disk.read(tmp_path / "loop"), Disk.read(tmp_path / "loop" / "a")) == (
            Unreadable(
                f"cannot be read, since {tmp_path / 'loop'} is a symlink that leads"
                " back to itself; point it at the file or folder it stands for"
            ),
        ) * 2

    def test_reads_a_path_under_an_entry_that_is_no_file_or_folder_as_blocked(
        self, tmp_path: Path
    ) -> None:
        os.mkfifo(tmp_path / "fifo")
        assert Disk.read(tmp_path / "fifo" / "a") == Blocked(
            tmp_path / "fifo",
            "is neither a file nor a folder; remove it, then add the folder",
        )

    @SKIP_AS_ROOT
    def test_reads_a_file_it_cannot_open_as_unreadable(self, tmp_path: Path) -> None:
        (tmp_path / "a").write_text("x")
        (tmp_path / "a").chmod(0)
        assert Disk.read(tmp_path / "a") == Unreadable(
            "cannot be read (Permission denied); make it readable"
        )

    def test_lists_nothing_under_a_missing_folder(self, tmp_path: Path) -> None:
        assert Disk(tmp_path).listing(PurePosixPath("src")) == ((), {})

    def test_lists_nothing_under_a_file_in_a_folders_place(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "src").write_text("")
        assert Disk(tmp_path).listing(PurePosixPath("src")) == ((), {})

    @SKIP_AS_ROOT
    def test_lists_each_folder_it_cannot_open(self, tmp_path: Path) -> None:
        (tmp_path / "tests" / "shut").mkdir(parents=True)
        (tmp_path / "tests" / "a.py").write_text("")
        (tmp_path / "tests" / "shut").chmod(0)
        try:
            listing = Disk(tmp_path).listing(PurePosixPath("tests"))
        finally:
            (tmp_path / "tests" / "shut").chmod(0o755)
        assert listing == (
            (PurePosixPath("tests/a.py"),),
            {
                PurePosixPath("tests/shut"): Unopened(
                    "cannot be opened (Permission denied); give the folder read and"
                    " execute permission"
                )
            },
        )

    def test_lists_files_under_a_folder_without_caches(self, tmp_path: Path) -> None:
        (tmp_path / "src" / "kit" / "__pycache__").mkdir(parents=True)
        (tmp_path / "src" / "kit" / "a.py").write_text("")
        (tmp_path / "src" / "kit" / "__pycache__" / "a.pyc").write_text("")
        (tmp_path / "src" / "kit" / "gone").symlink_to(tmp_path / "missing")
        (tmp_path / "src" / "kit" / "link").symlink_to(
            tmp_path / "src" / "kit" / "a.py"
        )
        os.mkfifo(tmp_path / "src" / "kit" / "pipe")
        assert Disk(tmp_path).listing(PurePosixPath("src")) == (
            (PurePosixPath("src/kit/a.py"), PurePosixPath("src/kit/link")),
            {},
        )
