"""Git's NUL-framed path log reads into commits, whatever their subjects hold."""

lazy from pathlib import Path

from nustack.sync.history import Commit


class TestCommit:
    """A subject reaches the description exactly as upstream wrote it.

    A subject may be empty or hold bytes that are not UTF-8.
    """

    def test_keeps_each_subject_whole_with_its_spaces_and_odd_bytes(self) -> None:
        assert Commit.from_log(b"a1 first\0b2  two  spaces \xff\0") == (
            Commit("a1", "first"),
            Commit("b2", " two  spaces \udcff"),
        )

    def test_keeps_the_hash_and_subject_of_each_commit_in_the_path_log(
        self, sync_fixtures: Path
    ) -> None:
        # git log -z '--format=%H %s' b405fe0..4ae2317 --
        # skills/productivity/writing-for-agents/ LICENSE
        log = sync_fixtures / "replies/log.bin"
        assert Commit.from_log(log.read_bytes()) == (
            Commit(
                "321658273cb1d20b76026717d027d505790106d4",
                "Remove all em-dashes from the repo",
            ),
            Commit(
                "4aaccb58d40559d7e3c59a029b2290ae5ba538de",
                "fix: make writing-for-agents model-invokable in Codex",
            ),
        )

    def test_reads_subjects_that_are_empty_or_hold_non_utf8_bytes(
        self, sync_fixtures: Path
    ) -> None:
        # git log -z '--format=%H %s' in a repository of two commits, one with
        # an empty subject and one with the subject b"keep \xff\x1b"
        log = sync_fixtures / "replies/non-utf8/subject.bin"
        assert Commit.from_log(log.read_bytes()) == (
            Commit("b72fbcaf814b1dcc422919af153198ebb690afd8", ""),
            Commit("6ee06899e5eb52a22d0876fd9a0c53e0d7933a7c", "keep \udcff\x1b"),
        )
