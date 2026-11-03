"""A copy's tree listing finds which upstream revision the checkout's copy came from.

A mode change alone changes a path, and a license alone matches no copy.
"""

lazy from pathlib import Path

from nustack.problem import Problem
from nustack.sync.tree import CopyTree
from nustack.sync.tree import GitEntry
from nustack.sync.tree import Mode


class TestCopyTree:
    """The description compares against the upstream revision the checkout holds.

    A mode change alone changes a path, a license alone matches no copy, the newest
    match wins even after a revert, and a filename keeps its tabs, edge spaces and
    non-UTF-8 bytes.
    """

    def test_keeps_the_copy_and_the_root_license_from_a_listing(self) -> None:
        listing = (
            b"100644 blob o1\tLICENSE\0"
            b"100755 blob o2\tskill/a\t\xff.md\0"
            b"100644 blob o3\tother/x\0"
            b"120000 blob o4\tskill/link\0"
            b"160000 commit o5\tskill/sub\0"
        )
        assert CopyTree.from_listing(listing, "skill") == CopyTree(
            frozendict(
                {
                    "a\t\udcff.md": GitEntry(Mode.EXECUTABLE, "o2"),
                    "link": GitEntry(Mode.SYMLINK, "o4"),
                    "sub": GitEntry(Mode.SUBMODULE, "o5"),
                    "LICENSE": GitEntry(Mode.REGULAR, "o1"),
                }
            )
        )

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

    def test_takes_the_newest_exact_match_even_after_an_upstream_revert(self) -> None:
        base = CopyTree(frozendict({"SKILL.md": GitEntry(Mode.REGULAR, "same")}))
        executable = CopyTree(
            frozendict({"SKILL.md": GitEntry(Mode.EXECUTABLE, "same")})
        )
        assert (
            base.newest_match((("tip", executable), ("revert", base), ("old", base)))
            == "revert"
        )
        assert base.newest_match((("tip", executable),)) is None

    def test_takes_no_license_alone_as_a_matching_copy_of_the_skill(self) -> None:
        tree = CopyTree(frozendict({"LICENSE": GitEntry(Mode.REGULAR, "same")}))
        assert tree.newest_match((("tip", tree),)) is None

    def test_joins_the_upstream_root_license_to_the_relative_file_list(
        self, sync_fixtures: Path
    ) -> None:
        # git ls-tree -r -z b405fe0 -- skills/productivity/writing-for-agents/ LICENSE
        listing = sync_fixtures / "replies/ls-tree.bin"
        tree = CopyTree.from_listing(
            listing.read_bytes(), "skills/productivity/writing-for-agents"
        )
        assert tree.files == {
            "LICENSE": GitEntry(
                Mode.REGULAR, "f1dd2c09108dde1a5f56097cee8461b3ea834499"
            ),
            "SKILL-MECHANICS.md": GitEntry(
                Mode.REGULAR, "c28e3bf035403080a849ac4b7816d3af93d145ff"
            ),
            "SKILL.md": GitEntry(
                Mode.REGULAR, "c059d48cd70cfd1494bde74afcc426010b1c10e3"
            ),
            "agents/openai.yaml": GitEntry(
                Mode.REGULAR, "d677a13f4b6bd80091ceff2e3ebfa3f173e723b7"
            ),
        }

    def test_keeps_a_filenames_tab_edge_spaces_and_non_utf8_byte(
        self, sync_fixtures: Path
    ) -> None:
        # git --literal-pathspecs ls-tree -r -z HEAD -- -src/
        listing = sync_fixtures / "replies/non-utf8/path.bin"
        tree = CopyTree.from_listing(listing.read_bytes(), "-src")
        assert tree.files == {
            " edge .md ": GitEntry(
                Mode.REGULAR, "54aeb5dc2537483ba853f1b52ed0bdc20e0193c8"
            ),
            "nested/\udcff\t.md": GitEntry(
                Mode.REGULAR, "994e126d270f6ab080f20051254741652e2bc726"
            ),
        }

    def test_accepts_a_copy_with_its_skill_file_and_license(self) -> None:
        tree = CopyTree(
            frozendict(
                {
                    "SKILL.md": GitEntry(Mode.REGULAR, "a"),
                    "LICENSE": GitEntry(Mode.REGULAR, "b"),
                    "tool": GitEntry(Mode.EXECUTABLE, "c"),
                }
            )
        )
        assert tree.problems(Path("/c")) == []

    def test_names_each_file_a_copy_cannot_hold_and_each_one_it_lacks(self) -> None:
        tree = CopyTree(
            frozendict(
                {
                    "link": GitEntry(Mode.SYMLINK, "a"),
                    "module": GitEntry(Mode.SUBMODULE, "b"),
                }
            )
        )
        assert tree.problems(Path("/c")) == [
            Problem(
                Path("/c/SKILL.md"),
                "has no upstream source; pass --source the skill's folder upstream",
            ),
            Problem(
                Path("/c/LICENSE"),
                "has no upstream source; upstream holds no LICENSE in the skill's"
                " folder or at its root; ask the owner to raise it upstream",
            ),
            Problem(
                Path("/c/link"),
                "is a symlink upstream, which no copy can hold; ask the owner to raise"
                " it upstream",
            ),
            Problem(
                Path("/c/module"),
                "is a submodule upstream, which no copy can hold; ask the owner to"
                " raise it upstream",
            ),
        ]
