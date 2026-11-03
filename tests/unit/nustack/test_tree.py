"""The files held in memory answer every read the checks make, as the disk would.

Only bytes every host decodes count as text, a file or folder the disk refused says
what to change before checking again, and a path under an entry where a folder
belongs names that entry.
"""

import errno
from pathlib import Path
from pathlib import PurePosixPath

import pytest

from nustack.tree import Blocked
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Missing
from nustack.tree import Read
from nustack.tree import Snapshot
from nustack.tree import Special
from nustack.tree import Symlink
from nustack.tree import Tree
from nustack.tree import Unopened
from nustack.tree import Unreadable


class TestFile:
    """Only bytes every host decodes count as text to a check."""

    @pytest.mark.parametrize(("content", "text"), [(b"a\n", "a\n"), (b"\xff", None)])
    def test_reads_text_only_from_utf8(self, content: bytes, text: str | None) -> None:
        assert File(content).text == text


class TestBlocked:
    """A path under an entry where a folder belongs names that entry and its fix."""

    def test_names_the_blocking_entry_and_its_fix(self) -> None:
        assert Blocked(Path("/p/a"), "is a pipe; remove it").absence("is missing") == (
            "cannot be read, since /p/a is a pipe; remove it"
        )


class TestUnreadable:
    """A file the disk refused tells the user what to change before checking again."""

    def test_says_why_and_how_to_fix_it(self) -> None:
        error = OSError(errno.EACCES, "Permission denied")
        assert Unreadable.of(error) == Unreadable(
            "cannot be read (Permission denied); make it readable"
        )


class TestUnopened:
    """A folder the disk refused tells the user what to change before checking again."""

    def test_says_why_and_how_to_fix_it(self) -> None:
        error = OSError(errno.EACCES, "Permission denied")
        assert Unopened.of(error) == Unopened(
            "cannot be opened (Permission denied); "
            "give the folder read and execute permission"
        )


class TestTree:
    """Checks see the files the disk held, in one order, each read as its kind.

    A symlink reads as missing, and a path below a file, an unreadable file or a
    special entry reads as blocked, naming the topmost such entry.
    """

    TREE = Tree(
        Path("/p"),
        frozendict(
            {
                PurePosixPath("b.md"): File(b"b"),
                PurePosixPath("a.md"): File(b"a"),
                PurePosixPath("s"): Folder(),
                PurePosixPath("s/l"): Symlink(),
                PurePosixPath("p"): Special(),
                PurePosixPath("u.md"): Unreadable("cannot be read"),
            }
        ),
    )

    def test_lists_its_files_in_path_order(self) -> None:
        assert list(self.TREE.files.items()) == [
            (PurePosixPath("a.md"), File(b"a")),
            (PurePosixPath("b.md"), File(b"b")),
        ]

    @pytest.mark.parametrize(
        ("path", "read"),
        [
            ("a.md", File(b"a")),
            ("u.md", Unreadable("cannot be read")),
            ("s", Folder()),
            ("s/l", Missing()),
            ("p", Special()),
            ("nothing", Missing()),
        ],
    )
    def test_reads_a_file_or_a_folder(self, path: str, read: Read) -> None:
        assert self.TREE.read(PurePosixPath(path)) == read

    @pytest.mark.parametrize(
        ("entry", "blocked"),
        [
            (
                File(b"x"),
                Blocked(
                    Path("/p/a/b"),
                    "is a file where a folder belongs; move the file, then add the"
                    " folder",
                ),
            ),
            (
                Unreadable("cannot be read (Permission denied); make it readable"),
                Blocked(
                    Path("/p/a/b"),
                    "is a file where a folder belongs; move the file, then add the"
                    " folder",
                ),
            ),
            (
                Special(),
                Blocked(
                    Path("/p/a/b"),
                    "is neither a file nor a folder; remove it, then add the folder",
                ),
            ),
        ],
    )
    def test_reads_a_path_under_an_entry_where_a_folder_belongs_as_blocked(
        self, entry: File | Unreadable | Special, blocked: Blocked
    ) -> None:
        tree = Tree(
            Path("/p"),
            frozendict({PurePosixPath("a"): Folder(), PurePosixPath("a/b"): entry}),
        )
        assert tree.read(PurePosixPath("a/b/c")) == blocked

    def test_reads_a_path_two_folders_below_a_file_as_blocked(self) -> None:
        tree = Tree(Path("/p"), frozendict({PurePosixPath("a"): File(b"x")}))
        assert tree.read(PurePosixPath("a/b/c")) == Blocked(
            Path("/p/a"),
            "is a file where a folder belongs; move the file, then add the folder",
        )


class TestSnapshot:
    """The checks read only what the disk handed over, never the disk itself.

    A file the disk was never asked for is a bug in the caller, so reading it fails.
    """

    SNAPSHOT = Snapshot(
        Path("/r"),
        Tree(Path("/r/plugin"), frozendict()),
        frozendict(
            {
                PurePosixPath("LICENSE"): File(b"MIT"),
                PurePosixPath("README.md"): Missing(),
            }
        ),
        (),
        (),
        frozendict(),
    )

    def test_reads_each_file_the_disk_handed_over(self) -> None:
        assert (
            self.SNAPSHOT.read(PurePosixPath("LICENSE")),
            self.SNAPSHOT.read(PurePosixPath("README.md")),
        ) == (File(b"MIT"), Missing())

    def test_fails_on_a_file_the_disk_was_never_asked_for(self) -> None:
        with pytest.raises(KeyError):
            self.SNAPSHOT.read(PurePosixPath("NOTICE"))
