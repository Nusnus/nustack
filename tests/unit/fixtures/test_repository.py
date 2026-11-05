"""The model repository edits its files, and reads as Disk reads it saved to disk."""

import os
import shutil
from pathlib import PurePosixPath
lazy from pathlib import Path

import pytest

from nustack.repository.disk import Disk
from nustack.tree import Missing
from nustack.tree import NotAFolder
from nustack.tree import Special
from nustack.tree import Symlink
from nustack.tree import Unopened
from tests.fixtures.permissions import SKIP_AS_ROOT
from tests.fixtures.repository import MissingTextError
from tests.fixtures.repository import ModelRepository


class TestModelRepository:
    """Each entry a test puts in the plugin leaves the snapshot Disk would read.

    An edit replaces the first copy of its text, and an edit of text the file does not
    hold names the file and the text.
    """

    def test_replaces_the_first_copy_of_the_text_an_edit_names(
        self, tmp_path: Path
    ) -> None:
        repository = ModelRepository(tmp_path)
        repository.write("a.md", "one two one\n")
        repository.edit("a.md", "one", "three")
        assert repository.files[PurePosixPath("a.md")] == b"three two one\n"

    def test_refuses_an_edit_of_text_the_file_does_not_hold(
        self, tmp_path: Path
    ) -> None:
        repository = ModelRepository(tmp_path)
        repository.write("a.md", "one\n")
        with pytest.raises(MissingTextError) as caught:
            repository.edit("a.md", "two", "three")
        assert str(caught.value) == "a.md does not hold 'two'; edit text the file holds"

    def test_reads_nothing_below_a_special_file_in_a_folders_place(
        self, tmp_path: Path
    ) -> None:
        repository = ModelRepository(tmp_path)
        repository.put("plugin/skills/nus-mode", Special())
        root = repository.save()
        shutil.rmtree(root / "plugin/skills/nus-mode")
        os.mkfifo(root / "plugin/skills/nus-mode")
        assert repository.snapshot() == Disk(root).snapshot()

    @SKIP_AS_ROOT
    def test_reads_only_a_folder_that_will_not_open_once_one_is_put(
        self, tmp_path: Path
    ) -> None:
        repository = ModelRepository(tmp_path)
        repository.put(
            "plugin/skills",
            Unopened(
                "cannot be opened (Permission denied); give the folder read and"
                " execute permission"
            ),
        )
        root = repository.save()
        (root / "plugin/skills").chmod(0)
        try:
            assert repository.snapshot() == Disk(root).snapshot()
        finally:
            (root / "plugin/skills").chmod(0o755)

    def test_reads_only_the_symlink_once_one_is_put(self, tmp_path: Path) -> None:
        repository = ModelRepository(tmp_path)
        repository.put("plugin/a", Symlink())
        root = repository.save()
        (root / "plugin" / "a").symlink_to(root / "LICENSE")
        assert repository.snapshot() == Disk(root).snapshot()

    def test_reads_only_a_symlink_in_the_plugins_place(self, tmp_path: Path) -> None:
        repository = ModelRepository(tmp_path)
        repository.put("plugin", Symlink())
        repository.put("plugin/a", Symlink())
        root = repository.save()
        shutil.rmtree(root / "plugin")
        (root / "plugin").symlink_to(root / "LICENSE")
        assert repository.snapshot() == Disk(root).snapshot()

    @SKIP_AS_ROOT
    def test_reads_only_a_plugin_that_will_not_open(self, tmp_path: Path) -> None:
        repository = ModelRepository(tmp_path)
        repository.put(
            "plugin",
            Unopened(
                "cannot be opened (Permission denied); give the folder read and"
                " execute permission"
            ),
        )
        repository.put("plugin/a", Symlink())
        root = repository.save()
        (root / "plugin").chmod(0)
        try:
            assert repository.snapshot() == Disk(root).snapshot()
        finally:
            (root / "plugin").chmod(0o755)

    def test_reads_only_a_missing_plugin(self, tmp_path: Path) -> None:
        repository = ModelRepository(tmp_path)
        repository.put("plugin", Missing())
        root = repository.save()
        shutil.rmtree(root / "plugin")
        assert repository.snapshot() == Disk(root).snapshot()

    def test_reads_only_a_file_in_the_plugins_place(self, tmp_path: Path) -> None:
        repository = ModelRepository(tmp_path)
        repository.put("plugin", NotAFolder())
        root = repository.save()
        shutil.rmtree(root / "plugin")
        (root / "plugin").write_text("x")
        assert repository.snapshot() == Disk(root).snapshot()
