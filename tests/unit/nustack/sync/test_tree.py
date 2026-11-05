"""A copy's tree listing finds which upstream revision the checkout's copy came from.

A mode change alone changes a path, and a license alone matches no copy. A copy
that lacks its SKILL.md or LICENSE, or holds a symlink or submodule, is a Problem.
"""

from pathlib import Path

from nustack.problem import Problem
from nustack.sha import Sha
from nustack.sync.tree import CopyTree
from nustack.sync.tree import GitEntry
from nustack.sync.tree import Mode


class TestCopyTree:
    """The description compares against the upstream revision the checkout holds.

    A filename keeps its tabs, edge spaces and non-UTF-8 bytes; a mode change alone
    changes a path, a license alone matches no copy, and the newest match wins even
    after a revert. A missing SKILL.md or LICENSE, a symlink or a submodule is named
    with its fix.
    """

    def test_keeps_the_copy_and_the_root_license_from_a_listing(
        self, sync_fixtures: Path
    ) -> None:
        # git ls-tree -r -z HEAD, in a repository holding a non-UTF-8 path, a
        # symlink and a submodule
        listing = sync_fixtures / "replies/mixed-listing.bin"
        assert CopyTree.from_listing(listing.read_bytes(), "skill") == CopyTree(
            frozendict(
                {
                    "a\t\udcff.md": GitEntry(
                        Mode.EXECUTABLE, "78981922613b2afb6025042ff6bd878ac1994e85"
                    ),
                    "link": GitEntry(
                        Mode.SYMLINK, "2e65efe2a145dda7ee51d1741299f848e5bf752e"
                    ),
                    "sub": GitEntry(
                        Mode.SUBMODULE, "4c73ab3f7c46887314adc8151e71326d6f87eb10"
                    ),
                    "LICENSE": GitEntry(
                        Mode.REGULAR, "a22a2da24d1ceeef3d0c2f1f4f68923f55b8d4cc"
                    ),
                }
            )
        )

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

    def test_takes_no_license_alone_as_a_matching_copy_of_the_skill(self) -> None:
        tree = CopyTree(frozendict({"LICENSE": GitEntry(Mode.REGULAR, "same")}))
        assert tree.newest_match(((Sha("a" * 40), tree),)) is None

    def test_takes_the_newest_exact_match_even_after_an_upstream_revert(self) -> None:
        base = CopyTree(frozendict({"SKILL.md": GitEntry(Mode.REGULAR, "same")}))
        executable = CopyTree(
            frozendict({"SKILL.md": GitEntry(Mode.EXECUTABLE, "same")})
        )
        assert base.newest_match(
            (
                (Sha("a" * 40), executable),
                (Sha("b" * 40), base),
                (Sha("c" * 40), base),
            )
        ) == Sha("b" * 40)
        assert base.newest_match(((Sha("a" * 40), executable),)) is None

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
                "has no upstream source; pass --source-folder the skill's folder"
                " upstream",
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
