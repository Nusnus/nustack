"""The changelog holds each release once, newest first, as the release reads it.

Only a top `[Unreleased]` section may sit above the releases, and the notes keep
line feeds whatever the file's line endings.
"""

from pathlib import Path

import pytest

from nustack.markdown.document import Document
from nustack.problem import Problem
from nustack.repository.changelog import Changelog


class TestChangelog:
    """The top entry is the release's notes, titled with its version and a real day.

    Entries run newest first by version and date, each standing alone. It may open
    without an [Unreleased] section, and a version too long for int, or an entry
    dated on no real day, still orders by its version.
    """

    PATH = Path("/r/CHANGELOG.md")
    TOP = "# Changelog\n\n## [Unreleased]\n\n"

    def test_publishes_the_top_release_as_its_notes(self) -> None:
        changelog = Changelog(
            Document(self.PATH, self.TOP + "## [1.2.3] - 2026-01-02\n\n- Adds.\n")
        )
        assert changelog.release_notes == "- Adds."

    def test_publishes_crlf_notes_with_line_feeds(self) -> None:
        changelog = Changelog(
            Document(
                self.PATH,
                "# Changelog\r\n\r\n## [1.2.3] - 2026-01-02\r\n\r\n- A.\r\n- B.\r\n",
            )
        )
        assert changelog.release_notes == "- A.\n- B."

    def test_may_open_without_an_unreleased_section(self) -> None:
        changelog = Changelog(
            Document(self.PATH, "# Changelog\n\n## [1.2.3] - 2026-01-02\n\n- Adds.\n")
        )
        assert changelog.problems("1.2.3") == []

    def test_skips_only_a_top_section_titled_exactly_unreleased(self) -> None:
        changelog = Changelog(
            Document(
                self.PATH,
                "# Changelog\n\n## [Unreleased] draft\n\n- A.\n\n"
                "## [1.2.3] - 2026-01-02\n\n- B.\n",
            )
        )
        assert changelog.release_notes == "- A."

    def test_reports_an_unreleased_section_below_a_release(self) -> None:
        assert Changelog(
            Document(
                self.PATH,
                "# Changelog\n\n## [1.2.3] - 2026-01-02\n\n- A.\n\n"
                "## [1.2.2] - 2026-01-01\n\n- B.\n\n"
                "## [Unreleased]\n\n- C.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                self.PATH,
                "has an [Unreleased] section below a release; move it above the"
                " releases",
            )
        ]

    @pytest.mark.parametrize(
        ("title", "what"),
        [
            (
                "Unreleased",
                (
                    "has an entry titled 'Unreleased'; title it"
                    " '[<version>] - <YYYY-MM-DD>' with the release's version"
                ),
            ),
            (
                "[1.2.3]",
                (
                    "has an entry titled '[1.2.3]'; title it"
                    " '[<version>] - <YYYY-MM-DD>' with the release's version"
                ),
            ),
            (
                "[1.2.3] - 2026-01-02 (yanked)",
                (
                    "has an entry titled '[1.2.3] - 2026-01-02 (yanked)'; title it"
                    " '[<version>] - <YYYY-MM-DD>' with the release's version"
                ),
            ),
            (
                "[v1.2.3] - 2026-01-02",
                (
                    "has an entry titled '[v1.2.3] - 2026-01-02'; title it"
                    " '[<version>] - <YYYY-MM-DD>' with the release's version"
                ),
            ),
            (
                "1.2.3 - 2026-01-02",
                (
                    "has an entry titled '1.2.3 - 2026-01-02'; title it"
                    " '[<version>] - <YYYY-MM-DD>' with the release's version"
                ),
            ),
            (
                "[1.2.3]  -  2026-01-02",
                (
                    "has an entry titled '[1.2.3]  -  2026-01-02'; title it"
                    " '[<version>] - <YYYY-MM-DD>' with the release's version"
                ),
            ),
        ],
    )
    def test_reports_an_entry_titled_another_way(self, title: str, what: str) -> None:
        assert Changelog(
            Document(
                self.PATH,
                self.TOP + f"## [1.2.3] - 2026-01-02\n\n- A.\n\n## {title}\n\n- B.\n",
            )
        ).problems("1.2.3") == [Problem(self.PATH, what)]

    @pytest.mark.parametrize(
        ("day", "what"),
        [
            (
                "2026-02-30",
                (
                    "has an entry dated 2026-02-30, which is no real day; date it with"
                    " the release day"
                ),
            ),
            (
                "2026-13-01",
                (
                    "has an entry dated 2026-13-01, which is no real day; date it with"
                    " the release day"
                ),
            ),
        ],
    )
    def test_reports_an_entry_dated_on_no_real_day(self, day: str, what: str) -> None:
        assert Changelog(
            Document(self.PATH, self.TOP + f"## [1.2.3] - {day}\n\n- A.\n")
        ).problems("1.2.3") == [Problem(self.PATH, what)]

    def test_reports_two_entries_for_one_version(self) -> None:
        assert Changelog(
            Document(
                self.PATH,
                self.TOP + "## [1.2.3] - 2026-01-02\n\n- A.\n\n"
                "## [1.2.3] - 2026-01-02\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(self.PATH, "has more than one entry for 1.2.3; merge them into one")
        ]

    def test_lists_each_version_with_two_entries_once_in_sorted_order(self) -> None:
        assert Changelog(
            Document(
                self.PATH,
                self.TOP + "## [1.2.3] - 2026-01-03\n\n- A.\n\n"
                "## [1.2.3] - 2026-01-03\n\n- B.\n\n"
                "## [1.2.2] - 2026-01-02\n\n- C.\n\n"
                "## [1.2.2] - 2026-01-02\n\n- D.\n\n"
                "## [1.2.10] - 2026-01-01\n\n- E.\n\n"
                "## [1.2.10] - 2026-01-01\n\n- F.\n",
            )
        ).problems(None)[:3] == [
            Problem(
                self.PATH, "has more than one entry for 1.2.10; merge them into one"
            ),
            Problem(
                self.PATH, "has more than one entry for 1.2.2; merge them into one"
            ),
            Problem(
                self.PATH, "has more than one entry for 1.2.3; merge them into one"
            ),
        ]

    def test_reports_an_older_entry_with_a_newer_version(self) -> None:
        assert Changelog(
            Document(
                self.PATH,
                self.TOP + "## [1.3.0] - 2026-01-03\n\n- A.\n\n"
                "## [1.2.3] - 2026-01-02\n\n- B.\n\n"
                "## [1.10.0] - 2026-01-01\n\n- C.\n",
            )
        ).problems("1.3.0") == [
            Problem(
                self.PATH,
                "has the entry for 1.2.3 above the one for 1.10.0; list releases"
                " newest first, by version",
            )
        ]

    def test_orders_versions_by_each_part_rather_than_the_whole(self) -> None:
        assert (
            Changelog(
                Document(
                    self.PATH,
                    self.TOP + "## [1.2.3] - 2026-01-02\n\n- A.\n\n"
                    "## [0.10.0] - 2026-01-01\n\n- B.\n",
                )
            ).problems("1.2.3")
            == []
        )

    def test_orders_a_version_too_long_for_int(self) -> None:
        huge = "9" * 5000
        assert Changelog(
            Document(
                self.PATH,
                self.TOP + f"## [1.2.3] - 2026-01-02\n\n- A.\n\n"
                f"## [{huge}.0.0] - 2026-01-01\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                self.PATH,
                f"has the entry for 1.2.3 above the one for {huge}.0.0; list releases"
                " newest first, by version",
            )
        ]

    def test_reports_an_older_entry_with_a_newer_date(self) -> None:
        assert Changelog(
            Document(
                self.PATH,
                self.TOP + "## [1.2.3] - 2026-01-03\n\n- A.\n\n"
                "## [1.2.2] - 2026-01-01\n\n- B.\n\n"
                "## [1.2.1] - 2026-01-02\n\n- C.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                self.PATH,
                "has the entry dated 2026-01-01 above the one dated 2026-01-02; list"
                " releases newest first, by date",
            )
        ]

    def test_orders_an_entry_dated_on_no_real_day_by_its_version(self) -> None:
        assert Changelog(
            Document(
                self.PATH,
                self.TOP + "## [1.2.3] - 2026-02-30\n\n- A.\n\n"
                "## [1.2.4] - 2026-01-01\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                self.PATH,
                "has an entry dated 2026-02-30, which is no real day; date it with"
                " the release day",
            ),
            Problem(
                self.PATH,
                "has the entry for 1.2.3 above the one for 1.2.4; list releases"
                " newest first, by version",
            ),
        ]

    @pytest.mark.parametrize("text", ["## [1.2.2] - 2026-01-02\n\n- A.\n", ""])
    def test_reports_an_opening_entry_for_another_version(self, text: str) -> None:
        assert Changelog(Document(self.PATH, self.TOP + text)).problems("1.2.3") == [
            Problem(
                self.PATH,
                "does not open with the entry for 1.2.3; retitle its [Unreleased]"
                " section '[1.2.3] - <release date>'",
            )
        ]

    @pytest.mark.parametrize(
        "text", ["# Changelog\n\n## [1.2.2] - 2026-01-02\n\n- A.\n", "# Changelog\n"]
    )
    def test_asks_for_a_new_entry_where_no_unreleased_section_opens(
        self, text: str
    ) -> None:
        assert Changelog(Document(self.PATH, text)).problems("1.2.3") == [
            Problem(
                self.PATH,
                "does not open with the entry for 1.2.3; add a '## [1.2.3] - <release"
                " date>' section above the releases",
            )
        ]

    def test_reports_an_unreleased_section_spelled_in_another_case(self) -> None:
        text = "# Changelog\n\n## [unreleased]\n\n## [1.2.3] - 2026-01-02\n\n- A.\n"
        assert Changelog(Document(self.PATH, text)).problems("1.2.3") == [
            Problem(
                self.PATH,
                "titles its [Unreleased] section '[unreleased]'; spell it [Unreleased]",
            )
        ]

    def test_takes_a_top_entry_for_a_longer_version_as_another_version(self) -> None:
        assert Changelog(
            Document(self.PATH, self.TOP + "## [1.2.30] - 2026-01-02\n\n- A.\n")
        ).problems("1.2.3") == [
            Problem(
                self.PATH,
                "does not open with the entry for 1.2.3; retitle its [Unreleased]"
                " section '[1.2.3] - <release date>'",
            )
        ]

    def test_says_no_more_than_a_bad_title(self) -> None:
        assert Changelog(
            Document(self.PATH, self.TOP + "## Release\n\n- A.\n")
        ).problems("1.2.3") == [
            Problem(
                self.PATH,
                "has an entry titled 'Release'; title it '[<version>] - <YYYY-MM-DD>'"
                " with the release's version",
            )
        ]

    def test_says_no_more_than_a_bad_top_title_beside_a_valid_entry(self) -> None:
        assert Changelog(
            Document(
                self.PATH,
                self.TOP + "## [1.2.3]\n\n- A.\n\n## [1.2.2] - 2026-01-01\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                self.PATH,
                "has an entry titled '[1.2.3]'; title it '[<version>] - <YYYY-MM-DD>'"
                " with the release's version",
            )
        ]

    def test_compares_no_version_without_the_manifests(self) -> None:
        assert (
            Changelog(
                Document(self.PATH, self.TOP + "## [1.2.2] - 2026-01-02\n\n- A.\n")
            ).problems(None)
            == []
        )

    @pytest.mark.parametrize(
        "entry",
        [
            "",
            "   \n",
            "[kit]: https://example.com\n\n",
            "<!-- Draft: write release notes here -->\n\n",
        ],
    )
    def test_reports_an_entry_that_shows_nothing(self, entry: str) -> None:
        assert Changelog(
            Document(
                self.PATH,
                self.TOP
                + f"## [1.2.3] - 2026-01-02\n\n{entry}"
                + "## [1.2.2] - 2026-01-01\n\n- A.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                self.PATH,
                "has an empty entry for 1.2.3; list what the release changes under it",
            )
        ]

    @pytest.mark.parametrize(
        "text",
        [
            (
                "## [1.2.3] - 2026-01-02\n\n- Adds [the kit][kit].\n\n"
                "## [1.2.2] - 2026-01-01\n\n- A.\n\n[kit]: https://example.com\n"
            ),
            (
                "## [1.2.3] - 2026-01-02\n\n- Adds ![a logo][logo].\n\n"
                "## [1.2.2] - 2026-01-01\n\n- A.\n\n[logo]: https://example.com/a.png\n"
            ),
        ],
    )
    def test_reports_an_entry_that_uses_a_reference_defined_outside_it(
        self, text: str
    ) -> None:
        assert Changelog(Document(self.PATH, self.TOP + text)).problems("1.2.3") == [
            Problem(
                self.PATH,
                "has an entry for 1.2.3 that reads differently on its own: a reference"
                " it uses is defined elsewhere in the changelog; define it inside the"
                " entry",
            )
        ]

    def test_accepts_an_entry_with_its_own_reference(self) -> None:
        assert (
            Changelog(
                Document(
                    self.PATH,
                    self.TOP + "## [1.2.3] - 2026-01-02\n\n- Adds [the kit][kit].\n\n"
                    '[kit]: https://example.com "The kit"\n',
                )
            ).problems("1.2.3")
            == []
        )


class TestChangelogLinks:
    """Each release links to its tag, and [Unreleased] to what changed since.

    A changelog without releases holds no link.
    """

    PATH = Path("/r/CHANGELOG.md")
    REPO = "https://github.com/o/r"
    HEAD = "# Changelog\n\n## [Unreleased]\n\n## [1.2.3] - 2026-01-02\n\n- A.\n\n"

    def test_accepts_the_targets_each_link_names(self) -> None:
        text = (
            self.HEAD + "[Unreleased]: https://github.com/o/r/compare/v1.2.3...HEAD\n"
            "[1.2.3]: https://github.com/o/r/releases/tag/v1.2.3\n"
        )
        assert Changelog(Document(self.PATH, text)).link_problems(self.REPO) == []

    def test_reports_each_link_the_changelog_leaves_out(self) -> None:
        assert Changelog(Document(self.PATH, self.HEAD)).link_problems(self.REPO) == [
            Problem(
                self.PATH,
                "has no link for [1.2.3]; add '[1.2.3]:"
                " https://github.com/o/r/releases/tag/v1.2.3' above the first ##"
                " heading",
            ),
            Problem(
                self.PATH,
                "has no link for [Unreleased]; add '[Unreleased]:"
                " https://github.com/o/r/compare/v1.2.3...HEAD' above the first ##"
                " heading",
            ),
        ]

    def test_holds_no_link_in_a_changelog_without_releases(self) -> None:
        text = "# Changelog\n\n## [Unreleased]\n\n[Unreleased]: https://x\n"
        assert Changelog(Document(self.PATH, text)).link_problems(self.REPO) == []

    def test_reports_each_link_to_another_target(self) -> None:
        text = (
            self.HEAD + "[Unreleased]: https://github.com/o/r/releases/tag/v1.2.3\n"
            "[1.2.3]: https://github.com/o/r/compare/v1.2.3...HEAD\n"
        )
        assert Changelog(Document(self.PATH, text)).link_problems(self.REPO) == [
            Problem(
                self.PATH,
                "links [1.2.3] to https://github.com/o/r/compare/v1.2.3...HEAD;"
                " link it to https://github.com/o/r/releases/tag/v1.2.3",
            ),
            Problem(
                self.PATH,
                "links [Unreleased] to https://github.com/o/r/releases/tag/v1.2.3;"
                " link it to https://github.com/o/r/compare/v1.2.3...HEAD",
            ),
        ]
