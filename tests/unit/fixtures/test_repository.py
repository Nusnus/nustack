"""The model repository edits its files, and reads as Disk reads it saved to disk."""

import os
import shutil
from pathlib import PurePosixPath
lazy from pathlib import Path

import pytest

from nustack.record import CopyRecord
from nustack.repository.disk import Disk
from nustack.tree import Folder
from nustack.tree import Missing
from nustack.tree import NotAFolder
from nustack.tree import Special
from nustack.tree import Symlink
from nustack.tree import Unopened
from nustack.tree import Unreadable
from tests.fixtures.permissions import SKIP_AS_ROOT
from tests.fixtures.repository import MissingTextError
from tests.fixtures.repository import ModelRepository


class TestModelRepository:
    """Each entry a test puts in the plugin or a copy reads as Disk reads it.

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

    def test_reads_only_the_symlink_in_a_copy_once_one_is_put(
        self, tmp_path: Path
    ) -> None:
        repository = ModelRepository(tmp_path)
        repository.put_in_copy(".agents/skills/vendored/link", Symlink())
        root = repository.save()
        (root / ".agents/skills/vendored/link").symlink_to(root / "LICENSE")
        assert repository.snapshot() == Disk(root).snapshot()

    def test_reads_a_special_file_in_a_copy_beside_its_files(
        self, tmp_path: Path
    ) -> None:
        repository = ModelRepository(tmp_path)
        repository.put_in_copy(".agents/skills/vendored/pipe", Special())
        root = repository.save()
        os.mkfifo(root / ".agents/skills/vendored/pipe")
        assert repository.snapshot() == Disk(root).snapshot()

    @pytest.mark.skipif(os.geteuid() == 0, reason="root reads every file")
    def test_reads_a_file_in_a_copy_that_cannot_be_read(self, tmp_path: Path) -> None:
        repository = ModelRepository(tmp_path)
        repository.put_in_copy(
            ".agents/skills/vendored/LICENSE",
            Unreadable("cannot be read (Permission denied); make it readable"),
        )
        root = repository.save()
        (root / ".agents/skills/vendored/LICENSE").chmod(0)
        try:
            assert repository.snapshot() == Disk(root).snapshot()
        finally:
            (root / ".agents/skills/vendored/LICENSE").chmod(0o644)

    @pytest.mark.skipif(os.geteuid() == 0, reason="root opens every folder")
    def test_reads_only_a_folder_in_a_copy_that_will_not_open(
        self, tmp_path: Path
    ) -> None:
        repository = ModelRepository(tmp_path)
        repository.put_in_copy(
            ".agents/skills/vendored/notes",
            Unopened(
                "cannot be opened (Permission denied); give the folder read and"
                " execute permission"
            ),
        )
        root = repository.save()
        (root / ".agents/skills/vendored/notes").mkdir()
        (root / ".agents/skills/vendored/notes").chmod(0)
        try:
            assert repository.snapshot() == Disk(root).snapshot()
        finally:
            (root / ".agents/skills/vendored/notes").chmod(0o755)

    def test_reads_a_folder_named_as_a_record(self, tmp_path: Path) -> None:
        repository = ModelRepository(tmp_path)
        repository.fail_read("vendored/folder.json", Folder())
        root = repository.save()
        (root / "vendored/folder.json").mkdir()
        assert repository.snapshot() == Disk(root).snapshot()

    def test_reads_a_broken_symlink_named_as_a_record(self, tmp_path: Path) -> None:
        repository = ModelRepository(tmp_path)
        repository.fail_read("vendored/gone.json", Unreadable(CopyRecord.SYMLINK))
        root = repository.save()
        (root / "vendored/gone.json").symlink_to(root / "gone")
        assert repository.snapshot() == Disk(root).snapshot()

    def test_reads_a_symlink_to_a_record_as_one_it_cannot_read(
        self, tmp_path: Path
    ) -> None:
        repository = ModelRepository(tmp_path)
        repository.fail_read("vendored/link.json", Unreadable(CopyRecord.SYMLINK))
        root = repository.save()
        (root / "vendored/link.json").symlink_to(root / "vendored/copy.json")
        assert repository.snapshot() == Disk(root).snapshot()

    def test_reads_only_a_file_in_a_copy_folders_place(self, tmp_path: Path) -> None:
        repository = ModelRepository(tmp_path)
        repository.remove(".agents/skills/vendored/LICENSE")
        repository.remove(".agents/skills/vendored/SKILL.md")
        repository.write(".agents/skills/vendored", "x")
        repository.put_in_copy(".agents/skills/vendored/.", NotAFolder())
        assert repository.snapshot() == Disk(repository.save()).snapshot()

    def test_reads_a_missing_copy_folder_as_one_missing_entry(
        self, tmp_path: Path
    ) -> None:
        repository = ModelRepository(tmp_path)
        repository.remove(".agents/skills/vendored/LICENSE")
        repository.remove(".agents/skills/vendored/SKILL.md")
        assert repository.snapshot() == Disk(repository.save()).snapshot()
