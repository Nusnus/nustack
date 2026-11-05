"""A copy's tree listing holds each skill's files under the skill's name.

Each skill takes upstream's root license where its own folder holds none, and a mode
change alone changes a path. A skill that lacks its SKILL.md or LICENSE, or a copy
that holds a symlink, a submodule or a file named with a character other than a
letter, digit, ., _ or -, is a Problem.
"""

from pathlib import Path

import pytest

from nustack.problem import Problem
from nustack.record import CopyRecord
from nustack.sync.tree import CopyTree
from nustack.sync.tree import GitEntry
from nustack.sync.tree import Mode


class TestCopyTree:
    """The sync compares, records and stages a copy by these entries.

    A filename keeps its tabs, edge spaces and non-UTF-8 bytes; each skill keeps its
    own license over the root's, and a mode change alone changes a path. A missing
    SKILL.md or LICENSE, a symlink, a submodule or a name that is not UTF-8 is named
    with its fix.
    """

    RECORD = CopyRecord.model_validate(
        {
            "upstream": "https://github.com/up/skills",
            "source": "skills",
            "folder": "c",
            "skills": ["s"],
            "commit": None,
            "files": {},
        }
    )

    def test_keeps_the_copy_and_the_root_license_from_a_listing(
        self, sync_fixtures: Path
    ) -> None:
        # git ls-tree -r -z HEAD, in a repository holding a non-UTF-8 path, a
        # symlink and a submodule
        listing = sync_fixtures / "replies/mixed-listing.bin"
        assert CopyTree.from_listing(listing.read_bytes(), ["skill"]) == CopyTree(
            frozendict(
                {
                    "skill/LICENSE": GitEntry(
                        Mode.REGULAR, "a22a2da24d1ceeef3d0c2f1f4f68923f55b8d4cc"
                    ),
                    "skill/a\t\udcff.md": GitEntry(
                        Mode.EXECUTABLE, "78981922613b2afb6025042ff6bd878ac1994e85"
                    ),
                    "skill/link": GitEntry(
                        Mode.SYMLINK, "2e65efe2a145dda7ee51d1741299f848e5bf752e"
                    ),
                    "skill/sub": GitEntry(
                        Mode.SUBMODULE, "4c73ab3f7c46887314adc8151e71326d6f87eb10"
                    ),
                }
            )
        )

    def test_keeps_a_filenames_tab_edge_spaces_and_non_utf8_byte(
        self, sync_fixtures: Path
    ) -> None:
        # git --literal-pathspecs ls-tree -r -z HEAD -- -src/
        listing = sync_fixtures / "replies/non-utf8/path.bin"
        tree = CopyTree.from_listing(listing.read_bytes(), ["-src"])
        assert tree.files == {
            "-src/ edge .md ": GitEntry(
                Mode.REGULAR, "54aeb5dc2537483ba853f1b52ed0bdc20e0193c8"
            ),
            "-src/nested/\udcff\t.md": GitEntry(
                Mode.REGULAR, "994e126d270f6ab080f20051254741652e2bc726"
            ),
        }

    def test_joins_the_upstream_root_license_to_the_relative_file_list(
        self, sync_fixtures: Path
    ) -> None:
        # git ls-tree -r -z b405fe0 -- skills/productivity/writing-for-agents/ LICENSE
        listing = sync_fixtures / "replies/ls-tree.bin"
        tree = CopyTree.from_listing(
            listing.read_bytes(), ["skills/productivity/writing-for-agents"]
        )
        assert tree.files == {
            "writing-for-agents/LICENSE": GitEntry(
                Mode.REGULAR, "f1dd2c09108dde1a5f56097cee8461b3ea834499"
            ),
            "writing-for-agents/SKILL-MECHANICS.md": GitEntry(
                Mode.REGULAR, "c28e3bf035403080a849ac4b7816d3af93d145ff"
            ),
            "writing-for-agents/SKILL.md": GitEntry(
                Mode.REGULAR, "c059d48cd70cfd1494bde74afcc426010b1c10e3"
            ),
            "writing-for-agents/agents/openai.yaml": GitEntry(
                Mode.REGULAR, "d677a13f4b6bd80091ceff2e3ebfa3f173e723b7"
            ),
        }

    def test_gives_each_skill_its_own_license_before_the_root_one(
        self, sync_fixtures: Path
    ) -> None:
        # git ls-tree -r -z 7b46075 -- skills/a/ skills/b/ LICENSE
        listing = sync_fixtures / "replies/own-license.bin"
        tree = CopyTree.from_listing(listing.read_bytes(), ["skills/a", "skills/b"])
        assert tree.blobs == {
            "a/LICENSE": "d8649da39ddf7910d29982e2f19cd9c0ff5ffe96",
            "a/SKILL.md": "78981922613b2afb6025042ff6bd878ac1994e85",
            "b/LICENSE": "4414025192f28e1f710bf02cf3c55a0cf05b3f2a",
            "b/SKILL.md": "61780798228d17af2d34fce4cfbdf35556832472",
        }

    def test_counts_a_mode_change_alone_as_a_changed_path(self) -> None:
        regular = CopyTree(
            frozendict(
                {
                    "SKILL.md": GitEntry(Mode.REGULAR, "same"),
                    "a.md": GitEntry(Mode.REGULAR, "kept"),
                }
            )
        )
        executable = CopyTree(
            frozendict(
                {
                    "SKILL.md": GitEntry(Mode.EXECUTABLE, "same"),
                    "a.md": GitEntry(Mode.REGULAR, "kept"),
                }
            )
        )
        assert regular.changed_paths(executable) == ("SKILL.md",)

    def test_accepts_a_copy_with_its_skill_file_and_license(self) -> None:
        tree = CopyTree(
            frozendict(
                {
                    "s/SKILL.md": GitEntry(Mode.REGULAR, "a"),
                    "s/LICENSE": GitEntry(Mode.REGULAR, "b"),
                    "s/tool": GitEntry(Mode.EXECUTABLE, "c"),
                }
            )
        )
        assert tree.problems(Path("/"), self.RECORD, ()) == []

    def test_names_only_the_skill_md_of_a_skill_gone_upstream(self) -> None:
        assert CopyTree(frozendict()).problems(Path("/"), self.RECORD, ()) == [
            Problem(
                Path("/c/s/SKILL.md"),
                "has no upstream source; set the record's source to the upstream"
                " folder that holds the skill's folder, rename the skill in the"
                " record's skills to upstream's new name as AGENTS.md says, or drop"
                " the skill from the record's skills",
            )
        ]

    def test_names_the_license_of_a_skill_upstream_holds_without_one(self) -> None:
        tree = CopyTree(frozendict({"s/SKILL.md": GitEntry(Mode.REGULAR, "b")}))
        assert tree.problems(Path("/"), self.RECORD, ()) == [
            Problem(
                Path("/c/s/LICENSE"),
                "has no upstream source; upstream holds no LICENSE in the skill's"
                " folder or at its root; ask the owner to raise it upstream",
            )
        ]

    def test_names_the_new_upstream_skills_a_missing_skill_may_be_renamed_to(
        self,
    ) -> None:
        tree = CopyTree(frozendict({"s/LICENSE": GitEntry(Mode.REGULAR, "b")}))
        assert tree.problems(Path("/"), self.RECORD, ("t", "u")) == [
            Problem(
                Path("/c/s/SKILL.md"),
                "has no upstream source; set the record's source to the upstream"
                " folder that holds the skill's folder, rename the skill in the"
                " record's skills to upstream's new name as AGENTS.md says (upstream"
                " holds t, u, which the record does not list), or drop the skill from"
                " the record's skills",
            )
        ]

    def test_names_each_file_a_copy_cannot_hold_and_each_one_it_lacks(self) -> None:
        tree = CopyTree(
            frozendict(
                {
                    "s/link": GitEntry(Mode.SYMLINK, "a"),
                    "s/module": GitEntry(Mode.SUBMODULE, "b"),
                    "s/nested/link": GitEntry(Mode.SYMLINK, "c"),
                }
            )
        )
        assert tree.problems(Path("/"), self.RECORD, ()) == [
            Problem(
                Path("/c/s/SKILL.md"),
                "has no upstream source; set the record's source to the upstream"
                " folder that holds the skill's folder, rename the skill in the"
                " record's skills to upstream's new name as AGENTS.md says, or drop"
                " the skill from the record's skills",
            ),
            Problem(
                Path("/c/s"),
                "holds, upstream, a symlink, which no copy can hold; ask the owner to"
                " raise it upstream",
            ),
            Problem(
                Path("/c/s"),
                "holds, upstream, a submodule, which no copy can hold; ask the owner"
                " to raise it upstream",
            ),
        ]

    def test_names_a_skill_holding_a_file_whose_name_is_not_utf_8_upstream(
        self, sync_fixtures: Path
    ) -> None:
        # git --literal-pathspecs ls-tree -r -z HEAD -- -src/
        listing = (sync_fixtures / "replies/non-utf8/path.bin").read_bytes() + (
            b"100644 blob 54aeb5dc2537483ba853f1b52ed0bdc20e0193c8"
            b"\t-src/nested/SKILL.md\0"
            b"100644 blob 994e126d270f6ab080f20051254741652e2bc726\tLICENSE\0"
        )
        tree = CopyTree.from_listing(listing, ["-src/nested"])
        record = self.RECORD.model_copy(update={"skills": ("nested",)})
        assert tree.problems(Path("/"), record, ()) == [
            Problem(
                Path("/c/nested"),
                "holds, upstream, a file named with a character other than a letter,"
                " digit, ., _ or -, which no copy can hold; ask the owner to raise it"
                " upstream",
            )
        ]

    @pytest.mark.parametrize(
        "name", ["s/\x1b[31m.md", "s/a b.md", "s/x\n fake: line", "s/é.md"]
    )
    def test_names_a_skill_holding_a_file_whose_name_a_record_cannot_hold(
        self, name: str
    ) -> None:
        tree = CopyTree(
            frozendict(
                {
                    "s/LICENSE": GitEntry(Mode.REGULAR, "1" * 40),
                    "s/SKILL.md": GitEntry(Mode.REGULAR, "2" * 40),
                    name: GitEntry(Mode.REGULAR, "3" * 40),
                }
            )
        )
        assert tree.problems(Path("/"), self.RECORD, ()) == [
            Problem(
                Path("/c/s"),
                "holds, upstream, a file named with a character other than a letter,"
                " digit, ., _ or -, which no copy can hold; ask the owner to raise it"
                " upstream",
            )
        ]

    def test_takes_files_named_with_letters_digits_dots_underscores_and_dashes(
        self,
    ) -> None:
        tree = CopyTree(
            frozendict(
                {
                    "s/LICENSE": GitEntry(Mode.REGULAR, "1" * 40),
                    "s/SKILL.md": GitEntry(Mode.REGULAR, "2" * 40),
                    "s/.ref/A_b-1.2.md": GitEntry(Mode.REGULAR, "3" * 40),
                }
            )
        )
        assert tree.problems(Path("/"), self.RECORD, ()) == []
