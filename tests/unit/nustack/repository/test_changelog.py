"""The changelog holds each release once, newest first, as the release reads it.

Only a top `[Unreleased]` section may sit above the releases. The top entry opens on
an optional lead, groups its changes by Keep a Changelog's types and gives each link
and image a full URL. The release below it is the previous one, and a CRLF entry
reads with line feeds. Each release and the plugin version link to their tag's page,
and `[Unreleased]`, while that section exists, to the changes since the plugin
version.
"""

lazy from pathlib import Path

import pytest

from nustack.github.name import NameWithOwner
from nustack.github.name import RepositoryUrl
from nustack.markdown.document import Document
from nustack.problem import Problem
from nustack.repository.changelog import Changelog


class TestEntry:
    """The top entry opens on an optional lead, then its changes.

    An entry with no groups is all lead. The lead may sit between thematic breaks, only
    blank lines are trimmed around it and the changes, a CRLF entry reads with line
    feeds, and the lead may sit under a setext title.
    """

    TOP = "# Changelog\n\n## [1.2.3] - 2026-01-02\n\n"
    BOTTOM = "\n## [1.2.2] - 2026-01-01\n"

    def test_splits_the_lead_from_the_changes(self, changelog_path: Path) -> None:
        entry = Changelog(
            Document(
                changelog_path,
                self.TOP
                + "Lead.\n\n### Added\n\n- A.\n\n### Fixed\n\n- F.\n"
                + self.BOTTOM,
            )
        ).entry
        assert (entry.lead, entry.changes) == (
            "Lead.",
            "### Added\n\n- A.\n\n### Fixed\n\n- F.",
        )

    def test_is_all_lead_without_groups(self, changelog_path: Path) -> None:
        entry = Changelog(
            Document(changelog_path, self.TOP + "Lead only.\n" + self.BOTTOM)
        ).entry
        assert (entry.lead, entry.changes) == ("Lead only.", "")

    def test_keeps_a_lead_between_thematic_breaks(self, changelog_path: Path) -> None:
        entry = Changelog(
            Document(
                changelog_path,
                self.TOP + "---\n\nLead.\n\n---\n\n### Added\n\n- A.\n" + self.BOTTOM,
            )
        ).entry
        assert (entry.lead, entry.changes) == (
            "---\n\nLead.\n\n---",
            "### Added\n\n- A.",
        )

    def test_trims_only_the_blank_lines_around_its_lead_and_changes(
        self, changelog_path: Path
    ) -> None:
        entry = Changelog(
            Document(
                changelog_path,
                self.TOP + "    code\n\nX\n\n### Added\n\n- X\n" + self.BOTTOM,
            )
        ).entry
        assert (entry.lead, entry.changes) == ("    code\n\nX", "### Added\n\n- X")

    def test_reads_a_crlf_lead_and_changes_with_line_feeds(
        self, changelog_path: Path
    ) -> None:
        entry = Changelog(
            Document(
                changelog_path,
                self.TOP + "A.\r\nB.\r\n\r\n### Added\r\n\r\n- C.\r\n" + self.BOTTOM,
            )
        ).entry
        assert (entry.lead, entry.changes) == ("A.\nB.", "### Added\n\n- C.")

    def test_leaves_a_setext_title_underline_out_of_its_lead(
        self, changelog_path: Path
    ) -> None:
        entry = Changelog(
            Document(
                changelog_path,
                "# Changelog\n\n[1.2.3] - 2026-01-02\n---\n\nLead.\n\n"
                "### Added\n\n- A.\n" + self.BOTTOM,
            )
        ).entry
        assert (entry.lead, entry.changes) == ("Lead.", "### Added\n\n- A.")

    def test_may_open_on_its_first_group(self, changelog_path: Path) -> None:
        changelog = Changelog(
            Document(changelog_path, self.TOP + "### Added\n\n- A.\n" + self.BOTTOM)
        )
        assert (changelog.entry.lead, changelog.problems("1.2.3")) == ("", [])


class TestChangelog:
    """The top entry is the release page's body, titled with its version and a real day.

    Entries run newest first by version and date, and the top one stands alone. The
    changelog may open without an `[Unreleased]` section, and the release below the top
    one, skipping a misnamed one, is the previous release. The changelog may not open
    with an `[Unreleased]` section spelled in another case, nor hold more than one, nor
    one, in any case, below a release. A changelog that opens with neither the plugin
    version's entry nor an `[Unreleased]` section asks for that entry to be added. A bad
    top title is offered the `[Unreleased]` spelling, unless a release or an
    `[Unreleased]` section sits above it. A version too long for int, or an entry dated
    on no real day, still orders by its version. Without the manifests, the top entry is
    compared with no plugin version. A bad top title is all it reports, unless an entry
    is newer than the plugin version, while an older entry's bad title leaves the top
    entry's checks running. An entry newer than the plugin version asks for the version
    to be set, wherever it sits, and a top entry for a longer version, such as 1.2.30,
    is such an entry. The plugin version's entry below another asks to be moved up, and
    a top entry for another version asks for the `[Unreleased]` section to be retitled.
    The top entry gives each link and image a full URL, while an older entry, and the
    top entry's own title, may link relatively.
    """

    TOP = "# Changelog\n\n## [Unreleased]\n\n"

    def test_may_open_without_an_unreleased_section(self, changelog_path: Path) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                "# Changelog\n\n## [1.2.3] - 2026-01-02\n\n### Added\n\n- Adds.\n",
            )
        )
        assert changelog.problems("1.2.3") == []

    def test_skips_only_a_top_section_titled_exactly_unreleased(
        self, changelog_path: Path
    ) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                "# Changelog\n\n## [Unreleased] draft\n\n- A.\n\n"
                "## [1.2.3] - 2026-01-02\n\n### Added\n\n- B.\n",
            )
        )
        assert changelog.entry.body == "- A."

    def test_names_the_second_of_three_releases_as_previous(
        self, changelog_path: Path
    ) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-03\n\n## [1.2.2] - 2026-01-02\n\n"
                "## [1.2.1] - 2026-01-01\n",
            )
        )
        assert changelog.previous == "1.2.2"

    def test_names_no_previous_release_for_the_first(
        self, changelog_path: Path
    ) -> None:
        changelog = Changelog(
            Document(changelog_path, self.TOP + "## [1.2.3] - 2026-01-02\n")
        )
        assert changelog.previous is None

    def test_skips_a_misnamed_release_for_the_previous(
        self, changelog_path: Path
    ) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-02\n\n## 1.2.2\n\n"
                "## [1.2.1] - 2026-01-01\n",
            )
        )
        assert changelog.previous == "1.2.1"

    def test_takes_the_top_release_as_its_entry(self, changelog_path: Path) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-02\n\n### Added\n\n- Adds.\n",
            )
        )
        assert changelog.entry.changes == "### Added\n\n- Adds."

    def test_reports_an_unreleased_section_spelled_in_another_case(
        self, changelog_path: Path
    ) -> None:
        text = (
            "# Changelog\n\n## [unreleased]\n\n- C.\n\n"
            "## [1.2.3] - 2026-01-02\n\n### Added\n\n- A.\n\n"
            "## [1.2.2] - 2026-01-01\n\n### Added\n\n- B.\n"
        )
        assert Changelog(Document(changelog_path, text)).problems("1.2.3") == [
            Problem(
                changelog_path,
                "titles its [Unreleased] section '[unreleased]'; spell it [Unreleased]",
            )
        ]

    @pytest.mark.parametrize(
        "releases",
        ["## [1.2.3] - 2026-01-02\n\n### Added\n\n- C.\n", ""],
        ids=["a release", "no release"],
    )
    def test_reads_one_unreleased_section_above_the_releases(
        self, changelog_path: Path, releases: str
    ) -> None:
        assert (
            Changelog(
                Document(
                    changelog_path,
                    "# Changelog\n\n## [Unreleased]\n\n- A.\n\n" + releases,
                )
            ).problems(None)
            == []
        )

    @pytest.mark.parametrize(
        ("extra", "releases"),
        [
            (
                "## [Unreleased]\n\n- B.\n\n",
                "## [1.2.3] - 2026-01-02\n\n### Added\n\n- C.\n",
            ),
            (
                "## [Unreleased]\n\n- B.\n\n" * 2,
                "## [1.2.3] - 2026-01-02\n\n### Added\n\n- C.\n",
            ),
            ("## [Unreleased]\n\n- B.\n", ""),
        ],
        ids=["two", "three", "two and no release"],
    )
    def test_reports_a_second_unreleased_section_above_any_release(
        self, changelog_path: Path, extra: str, releases: str
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                "# Changelog\n\n## [Unreleased]\n\n- A.\n\n" + extra + releases,
            )
        ).problems(None) == [
            Problem(
                changelog_path,
                "has more than one [Unreleased] section; merge them into one",
            )
        ]

    @pytest.mark.parametrize("title", ["[Unreleased]", "[unreleased]"])
    def test_reports_an_unreleased_section_below_a_release(
        self, changelog_path: Path, title: str
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                "# Changelog\n\n## [1.2.3] - 2026-01-02\n\n### Added\n\n- C.\n\n"
                f"## {title}\n\n- A.\n",
            )
        ).problems(None) == [
            Problem(
                changelog_path,
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
    def test_reports_an_entry_titled_another_way(
        self, changelog_path: Path, title: str, what: str
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                self.TOP
                + "## [1.2.3] - 2026-01-02\n\n### Added\n\n- A.\n\n"
                + f"## {title}\n\n- B.\n",
            )
        ).problems("1.2.3") == [Problem(changelog_path, what)]

    def test_offers_the_unreleased_spelling_for_a_bad_top_title(
        self, changelog_path: Path
    ) -> None:
        text = "# Changelog\n\n## [Unreleasd]\n\n## [1.2.3] - 2026-01-02\n\n- A.\n"
        assert Changelog(Document(changelog_path, text)).problems(None) == [
            Problem(
                changelog_path,
                "has an entry titled '[Unreleasd]'; title it '[<version>] -"
                " <YYYY-MM-DD>' with the release's version, or spell it [Unreleased]"
                " if no release is due",
            )
        ]

    def test_offers_no_unreleased_spelling_for_a_bad_title_below_a_release(
        self, changelog_path: Path
    ) -> None:
        text = (
            "# Changelog\n\n## [1.2.3] - 2026-01-02\n\n- A.\n\n## [Unreleasd]\n\n- B.\n"
        )
        assert Changelog(Document(changelog_path, text)).problems(None) == [
            Problem(
                changelog_path,
                "has an entry titled '[Unreleasd]'; title it '[<version>] -"
                " <YYYY-MM-DD>' with the release's version",
            )
        ]

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
    def test_reports_an_entry_dated_on_no_real_day(
        self, changelog_path: Path, day: str, what: str
    ) -> None:
        assert Changelog(
            Document(
                changelog_path, self.TOP + f"## [1.2.3] - {day}\n\n### Added\n\n- A.\n"
            )
        ).problems("1.2.3") == [Problem(changelog_path, what)]

    def test_reports_two_entries_for_one_version(self, changelog_path: Path) -> None:
        assert Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-02\n\n### Added\n\n- A.\n\n"
                "## [1.2.3] - 2026-01-02\n\n### Added\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                changelog_path, "has more than one entry for 1.2.3; merge them into one"
            )
        ]

    def test_lists_each_version_with_two_entries_once_in_sorted_order(
        self, changelog_path: Path
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-03\n\n### Added\n\n- A.\n\n"
                "## [1.2.3] - 2026-01-03\n\n### Added\n\n- B.\n\n"
                "## [1.2.2] - 2026-01-02\n\n### Added\n\n- C.\n\n"
                "## [1.2.2] - 2026-01-02\n\n### Added\n\n- D.\n\n"
                "## [1.2.10] - 2026-01-01\n\n### Added\n\n- E.\n\n"
                "## [1.2.10] - 2026-01-01\n\n### Added\n\n- F.\n",
            )
        ).problems(None)[:3] == [
            Problem(
                changelog_path,
                "has more than one entry for 1.2.10; merge them into one",
            ),
            Problem(
                changelog_path, "has more than one entry for 1.2.2; merge them into one"
            ),
            Problem(
                changelog_path, "has more than one entry for 1.2.3; merge them into one"
            ),
        ]

    def test_reports_an_older_entry_with_a_newer_version(
        self, changelog_path: Path
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.3.0] - 2026-01-03\n\n### Added\n\n- A.\n\n"
                "## [1.2.3] - 2026-01-02\n\n### Added\n\n- B.\n\n"
                "## [1.10.0] - 2026-01-01\n\n### Added\n\n- C.\n",
            )
        ).problems("1.3.0") == [
            Problem(
                changelog_path,
                "has the entry for 1.2.3 above the one for 1.10.0; list releases"
                " newest first, by version",
            )
        ]

    def test_orders_versions_by_each_part_rather_than_the_whole(
        self, changelog_path: Path
    ) -> None:
        assert (
            Changelog(
                Document(
                    changelog_path,
                    self.TOP + "## [1.2.3] - 2026-01-02\n\n### Added\n\n- A.\n\n"
                    "## [0.10.0] - 2026-01-01\n\n### Added\n\n- B.\n",
                )
            ).problems("1.2.3")
            == []
        )

    def test_orders_a_version_too_long_for_int(self, changelog_path: Path) -> None:
        huge = "9" * 5000
        assert Changelog(
            Document(
                changelog_path,
                self.TOP + f"## [1.2.3] - 2026-01-02\n\n### Added\n\n- A.\n\n"
                f"## [{huge}.0.0] - 2026-01-01\n\n### Added\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                f"has the entry for 1.2.3 above the one for {huge}.0.0; list releases"
                " newest first, by version",
            )
        ]

    def test_orders_an_entry_dated_on_no_real_day_by_its_version(
        self, changelog_path: Path
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-02-30\n\n### Added\n\n- A.\n\n"
                "## [1.2.4] - 2026-01-01\n\n### Added\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has an entry dated 2026-02-30, which is no real day; date it with"
                " the release day",
            ),
            Problem(
                changelog_path,
                "has the entry for 1.2.3 above the one for 1.2.4; list releases"
                " newest first, by version",
            ),
        ]

    def test_reports_an_older_entry_with_a_newer_date(
        self, changelog_path: Path
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-03\n\n### Added\n\n- A.\n\n"
                "## [1.2.2] - 2026-01-01\n\n### Added\n\n- B.\n\n"
                "## [1.2.1] - 2026-01-02\n\n### Added\n\n- C.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has the entry dated 2026-01-01 above the one dated 2026-01-02; list"
                " releases newest first, by date",
            )
        ]

    def test_compares_no_plugin_version_without_the_manifests(
        self, changelog_path: Path
    ) -> None:
        assert (
            Changelog(
                Document(
                    changelog_path,
                    self.TOP + "## [1.2.2] - 2026-01-02\n\n### Added\n\n- A.\n",
                )
            ).problems(None)
            == []
        )

    def test_says_no_more_than_a_bad_title(self, changelog_path: Path) -> None:
        assert Changelog(
            Document(changelog_path, self.TOP + "## Release\n\n- A.\n")
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has an entry titled 'Release'; title it '[<version>] - <YYYY-MM-DD>'"
                " with the release's version",
            )
        ]

    def test_says_no_more_than_a_bad_top_title_beside_a_valid_entry(
        self, changelog_path: Path
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                self.TOP
                + "## [1.2.3]\n\n- A.\n\n"
                + "## [1.2.2] - 2026-01-01\n\n### Added\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has an entry titled '[1.2.3]'; title it '[<version>] - <YYYY-MM-DD>'"
                " with the release's version",
            )
        ]

    def test_checks_the_top_entry_beside_a_bad_older_title(
        self, changelog_path: Path
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                self.TOP
                + "## [1.2.3] - 2026-01-02\n\n### Added\n\n- See [a](a.md).\n\n"
                + "## [1.2.2]\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has an entry titled '[1.2.2]'; title it '[<version>] - <YYYY-MM-DD>'"
                " with the release's version",
            ),
            Problem(
                changelog_path,
                "links a.md from the entry for 1.2.3, which the release page copies,"
                " where a relative link breaks; link it by its full URL",
            ),
        ]

    def test_asks_to_set_the_version_of_a_newer_entry_below_a_bad_top_title(
        self, changelog_path: Path
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                "# Changelog\n\n## Release\n\n- A.\n\n"
                "## [1.2.4] - 2026-01-02\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has an entry titled 'Release'; title it '[<version>] - <YYYY-MM-DD>'"
                " with the release's version, or spell it [Unreleased] if no release"
                " is due",
            ),
            Problem(
                changelog_path,
                "does not open with the entry for 1.2.3; set the newest entry's"
                " version in every file whose version nustack check compares, or"
                " remove the entries newer than 1.2.3",
            ),
        ]

    def test_says_no_more_than_a_bad_top_title_above_an_older_entry(
        self, changelog_path: Path
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                "# Changelog\n\n## Release\n\n- A.\n\n"
                "## [1.2.2] - 2026-01-02\n\n- B.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has an entry titled 'Release'; title it '[<version>] - <YYYY-MM-DD>'"
                " with the release's version, or spell it [Unreleased] if no release"
                " is due",
            )
        ]

    @pytest.mark.parametrize(
        ("newer", "version", "what"),
        [
            (
                "1.2.4",
                "1.2.3",
                (
                    "does not open with the entry for 1.2.3; set the newest entry's"
                    " version in every file whose version nustack check compares,"
                    " or remove the entries newer than 1.2.3"
                ),
            ),
            (
                "1.2.10",
                "1.2.9",
                (
                    "does not open with the entry for 1.2.9; set the newest entry's"
                    " version in every file whose version nustack check compares,"
                    " or remove the entries newer than 1.2.9"
                ),
            ),
        ],
    )
    def test_asks_to_set_the_version_of_a_newer_entry_above_the_version(
        self, changelog_path: Path, newer: str, version: str, what: str
    ) -> None:
        text = (
            f"## [{newer}] - 2026-01-03\n\n- B.\n\n"
            f"## [{version}] - 2026-01-02\n\n- A.\n"
        )
        assert Changelog(Document(changelog_path, self.TOP + text)).problems(
            version
        ) == [Problem(changelog_path, what)]

    def test_asks_to_set_the_version_of_a_newer_entry_below_the_version(
        self, changelog_path: Path
    ) -> None:
        text = (
            "## [1.2.2] - 2026-01-02\n\n- A.\n\n## [1.2.3] - 2026-01-03\n\n- B.\n\n"
            "## [1.2.4] - 2026-01-04\n\n- C.\n"
        )
        assert Changelog(Document(changelog_path, self.TOP + text)).problems(
            "1.2.3"
        ) == [
            Problem(
                changelog_path,
                "has the entry for 1.2.2 above the one for 1.2.3; list releases"
                " newest first, by version",
            ),
            Problem(
                changelog_path,
                "has the entry for 1.2.3 above the one for 1.2.4; list releases"
                " newest first, by version",
            ),
            Problem(
                changelog_path,
                "has the entry dated 2026-01-02 above the one dated 2026-01-03; list"
                " releases newest first, by date",
            ),
            Problem(
                changelog_path,
                "has the entry dated 2026-01-03 above the one dated 2026-01-04; list"
                " releases newest first, by date",
            ),
            Problem(
                changelog_path,
                "does not open with the entry for 1.2.3; set the newest entry's"
                " version in every file whose version nustack check compares, or"
                " remove the entries newer than 1.2.3",
            ),
        ]

    @pytest.mark.parametrize(
        "top", ["# Changelog\n\n", "# Changelog\n\n## [Unreleased]\n\n"]
    )
    def test_asks_to_set_the_version_of_a_newer_entry_where_the_version_has_none(
        self, changelog_path: Path, top: str
    ) -> None:
        text = top + (
            "## [1.2.4] - 2026-01-03\n\n- B.\n\n## [1.2.2] - 2026-01-02\n\n- A.\n"
        )
        assert Changelog(Document(changelog_path, text)).problems("1.2.3") == [
            Problem(
                changelog_path,
                "does not open with the entry for 1.2.3; set the newest entry's"
                " version in every file whose version nustack check compares, or"
                " remove the entries newer than 1.2.3",
            )
        ]

    def test_takes_a_top_entry_for_a_longer_version_as_another_version(
        self, changelog_path: Path
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.30] - 2026-01-02\n\n### Added\n\n- A.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "does not open with the entry for 1.2.3; set the newest entry's"
                " version in every file whose version nustack check compares, or"
                " remove the entries newer than 1.2.3",
            )
        ]

    def test_asks_to_move_an_entry_for_the_version_below_another(
        self, changelog_path: Path
    ) -> None:
        text = "## [1.2.2] - 2026-01-02\n\n- A.\n\n## [1.2.3] - 2026-01-03\n\n- B.\n"
        assert Changelog(Document(changelog_path, self.TOP + text)).problems(
            "1.2.3"
        ) == [
            Problem(
                changelog_path,
                "has the entry for 1.2.2 above the one for 1.2.3; list releases"
                " newest first, by version",
            ),
            Problem(
                changelog_path,
                "has the entry dated 2026-01-02 above the one dated 2026-01-03; list"
                " releases newest first, by date",
            ),
            Problem(
                changelog_path,
                "does not open with the entry for 1.2.3; move the entry for 1.2.3"
                " above the other releases",
            ),
        ]

    @pytest.mark.parametrize(
        "text", ["## [1.2.2] - 2026-01-02\n\n### Added\n\n- A.\n", ""]
    )
    def test_reports_an_opening_entry_for_another_version(
        self, changelog_path: Path, text: str
    ) -> None:
        assert Changelog(Document(changelog_path, self.TOP + text)).problems(
            "1.2.3"
        ) == [
            Problem(
                changelog_path,
                "does not open with the entry for 1.2.3; retitle its [Unreleased]"
                " section '[1.2.3] - <release date>'",
            )
        ]

    @pytest.mark.parametrize(
        "text",
        [
            "# Changelog\n\n## [1.2.2] - 2026-01-02\n\n### Added\n\n- A.\n",
            "# Changelog\n",
        ],
    )
    def test_asks_for_a_new_entry_where_no_unreleased_section_opens(
        self, changelog_path: Path, text: str
    ) -> None:
        assert Changelog(Document(changelog_path, text)).problems("1.2.3") == [
            Problem(
                changelog_path,
                "does not open with the entry for 1.2.3; add a '## [1.2.3] - <release"
                " date>' section above the releases",
            )
        ]

    @pytest.mark.parametrize(
        "entry",
        [
            "",
            "   \n",
            "[kit]: https://example.com\n\n",
            "<!-- Draft: write release notes here -->\n\n",
        ],
    )
    def test_reports_an_entry_that_shows_nothing(
        self, changelog_path: Path, entry: str
    ) -> None:
        assert Changelog(
            Document(
                changelog_path,
                self.TOP
                + f"## [1.2.3] - 2026-01-02\n\n{entry}"
                + "## [1.2.2] - 2026-01-01\n\n### Added\n\n- A.\n",
            )
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "shows nothing in the entry for 1.2.3; list what the release changes"
                " under it, which the release page copies",
            )
        ]

    @pytest.mark.parametrize(
        "text",
        [
            (
                "## [1.2.3] - 2026-01-02\n\n### Added\n\n- Adds [the kit][kit].\n\n"
                "## [1.2.2] - 2026-01-01\n\n### Added\n\n- A.\n\n[kit]: https://example.com\n"
            ),
            (
                "## [1.2.3] - 2026-01-02\n\n### Added\n\n- Adds ![a logo][logo].\n\n"
                "## [1.2.2] - 2026-01-01\n\n### Added\n\n- A.\n\n[logo]: https://example.com/a.png\n"
            ),
        ],
    )
    def test_reports_an_entry_that_uses_a_reference_defined_outside_it(
        self, changelog_path: Path, text: str
    ) -> None:
        assert Changelog(Document(changelog_path, self.TOP + text)).problems(
            "1.2.3"
        ) == [
            Problem(
                changelog_path,
                "uses a reference in the entry for 1.2.3 that is defined elsewhere in"
                " the file, so it reads differently on the release page; define it"
                " inside the entry for 1.2.3, under a label no other definition in the"
                " file uses",
            )
        ]

    def test_accepts_an_entry_with_its_own_reference(
        self, changelog_path: Path
    ) -> None:
        assert (
            Changelog(
                Document(
                    changelog_path,
                    self.TOP
                    + "## [1.2.3] - 2026-01-02\n\n### Added\n\n"
                    + "- Adds [the kit][kit].\n\n"
                    '[kit]: https://example.com "The kit"\n',
                )
            ).problems("1.2.3")
            == []
        )

    def test_reports_a_relative_link_in_the_top_entry(
        self, changelog_path: Path
    ) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-02\n\n### Added\n\n"
                "- See [a](a.md) and [b](#b).\n",
            )
        )
        assert changelog.problems("1.2.3") == [
            Problem(
                changelog_path,
                "links a.md from the entry for 1.2.3, which the release page copies,"
                " where a relative link breaks; link it by its full URL",
            ),
            Problem(
                changelog_path,
                "links #b from the entry for 1.2.3, which the release page copies,"
                " where a relative link breaks; link it by its full URL",
            ),
        ]

    def test_reports_a_relative_image_in_the_top_entry(
        self, changelog_path: Path
    ) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-02\n\n### Added\n\n"
                "- Shows ![a logo](logo.png).\n",
            )
        )
        assert changelog.problems("1.2.3") == [
            Problem(
                changelog_path,
                "links logo.png from the entry for 1.2.3, which the release page"
                " copies, where a relative link breaks; link it by its full URL",
            )
        ]

    def test_accepts_a_full_url_image_in_the_top_entry(
        self, changelog_path: Path
    ) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-02\n\n### Added\n\n"
                "- Shows ![a logo](https://x.io/logo.png).\n",
            )
        )
        assert changelog.problems("1.2.3") == []

    def test_accepts_a_full_url_in_the_top_entry(self, changelog_path: Path) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-02\n\n### Added\n\n"
                "- See [a](https://x.io/a.md).\n",
            )
        )
        assert changelog.problems("1.2.3") == []

    def test_accepts_a_relative_link_in_an_older_entry(
        self, changelog_path: Path
    ) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                self.TOP + "## [1.2.3] - 2026-01-02\n\n### Added\n\n- A.\n\n"
                "## [1.2.2] - 2026-01-01\n\n### Added\n\n- See [a](a.md).\n",
            )
        )
        assert changelog.problems("1.2.3") == []

    def test_accepts_a_relative_link_in_the_top_entrys_title(
        self, changelog_path: Path
    ) -> None:
        changelog = Changelog(
            Document(
                changelog_path,
                "# Changelog\n\n[1.2.3]: releases/tag/v1.2.3\n\n"
                "## [Unreleased]\n\n## [1.2.3] - 2026-01-02\n\n### Added\n\n- A.\n",
            )
        )
        assert changelog.problems("1.2.3") == []


class TestChangelogGroups:
    """The top entry groups its changes by Keep a Changelog's types of change.

    Each type is a group once, each group shows something, and the groups run in the
    order Keep a Changelog lists them. Interleaved groups are reported once per type and
    once per pair out of order, the same type twice in a row is in order, a group of no
    type is left out of the order check, and a group holding only a comment shows
    nothing.
    """

    TOP = "# Changelog\n\n## [1.2.3] - 2026-01-02\n\n"
    BOTTOM = "\n## [1.2.2] - 2026-01-01\n"

    def test_reports_changes_under_no_group(self, changelog_path: Path) -> None:
        assert Changelog(
            Document(changelog_path, self.TOP + "Lead.\n\n- A.\n" + self.BOTTOM)
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "lists the changes in the entry for 1.2.3 under no group; group them"
                " under '### <type>' headings, each one of Added, Changed, Deprecated,"
                " Removed, Fixed or Security, as Keep a Changelog does",
            )
        ]

    def test_reports_a_group_of_no_type(self, changelog_path: Path) -> None:
        assert Changelog(
            Document(changelog_path, self.TOP + "### Misc\n\n- A.\n" + self.BOTTOM)
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has a group titled 'Misc' in the entry for 1.2.3; title it Added,"
                " Changed, Deprecated, Removed, Fixed or Security, as Keep a"
                " Changelog does",
            )
        ]

    def test_reports_interleaved_groups_once_each(self, changelog_path: Path) -> None:
        entry = (
            "### Fixed\n\n- A.\n\n### Removed\n\n- B.\n\n"
            "### Fixed\n\n- C.\n\n### Removed\n\n- D.\n"
        )
        assert Changelog(
            Document(changelog_path, self.TOP + entry + self.BOTTOM)
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has more than one Removed group in the entry for 1.2.3;"
                " merge them into one",
            ),
            Problem(
                changelog_path,
                "has more than one Fixed group in the entry for 1.2.3;"
                " merge them into one",
            ),
            Problem(
                changelog_path,
                "has the Fixed group above the Removed group in the entry for 1.2.3;"
                " order the groups Added, Changed, Deprecated, Removed, Fixed and"
                " Security, as Keep a Changelog lists them",
            ),
        ]

    def test_reports_a_type_grouped_twice_in_a_row_as_in_order(
        self, changelog_path: Path
    ) -> None:
        entry = "### Added\n\n- A.\n\n### Added\n\n- B.\n"
        assert Changelog(
            Document(changelog_path, self.TOP + entry + self.BOTTOM)
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has more than one Added group in the entry for 1.2.3;"
                " merge them into one",
            )
        ]

    def test_reports_groups_out_of_order(self, changelog_path: Path) -> None:
        entry = "### Fixed\n\n- A.\n\n### Misc\n\n- M.\n\n### Added\n\n- B.\n"
        assert Changelog(
            Document(changelog_path, self.TOP + entry + self.BOTTOM)
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "has a group titled 'Misc' in the entry for 1.2.3; title it Added,"
                " Changed, Deprecated, Removed, Fixed or Security, as Keep a"
                " Changelog does",
            ),
            Problem(
                changelog_path,
                "has the Fixed group above the Added group in the entry for 1.2.3;"
                " order the groups Added, Changed, Deprecated, Removed, Fixed and"
                " Security, as Keep a Changelog lists them",
            ),
        ]

    @pytest.mark.parametrize(
        "entry",
        [
            "Lead.\n\n### Added\n\n- A.\n",
            "### Added\n\n- A.\n\n### Fixed\n\n- F.\n",
            "### Removed\n\n- B.\n\n### Fixed\n\n- A.\n",
            "### Added\n\n- A.\n\n### Changed\n\n- C.\n\n### Security\n\n- S.\n",
        ],
    )
    def test_accepts_each_type_once_in_order_with_its_changes(
        self, changelog_path: Path, entry: str
    ) -> None:
        assert (
            Changelog(
                Document(changelog_path, self.TOP + entry + self.BOTTOM)
            ).problems("1.2.3")
            == []
        )

    def test_reports_a_group_that_shows_nothing(self, changelog_path: Path) -> None:
        entry = "### Added\n\n- A.\n\n### Fixed\n\n<!-- none -->\n"
        assert Changelog(
            Document(changelog_path, self.TOP + entry + self.BOTTOM)
        ).problems("1.2.3") == [
            Problem(
                changelog_path,
                "shows nothing in the Fixed group of the entry for 1.2.3; list its"
                " changes under it, or remove it",
            )
        ]


class TestChangelogLinks:
    """Each release and the plugin version link to their tag's page.

    A changelog without releases holds no link, and the plugin version is linked even
    beside an entry whose title does not parse. `[Unreleased]` links to the changes
    since the plugin version, and missing links are reported for the titled releases,
    then the plugin version, then `[Unreleased]`. An `[Unreleased]` link is refused
    where no `[Unreleased]` section exists in any case, and accepted beside one spelled
    in another case, while the link of an `[Unreleased]` section below a release is
    left alone.
    """

    REPOSITORY_URL = RepositoryUrl("github.com", NameWithOwner("o", "r"))
    HEAD = (
        "# Changelog\n\n## [Unreleased]\n\n"
        "## [1.2.3] - 2026-01-02\n\n### Added\n\n- A.\n\n"
    )

    def test_finds_no_link_in_a_changelog_without_releases(
        self, changelog_path: Path
    ) -> None:
        text = "# Changelog\n\n## [Unreleased]\n\n[Unreleased]: https://x\n"
        assert (
            Changelog(Document(changelog_path, text)).link_problems(
                self.REPOSITORY_URL, "1.2.3"
            )
            == []
        )

    def test_links_the_plugin_version_beside_an_entry_with_a_bad_title(
        self, changelog_path: Path
    ) -> None:
        text = (
            "# Changelog\n\n## [Unreleased]\n\n## [1.2.3]\n\n- A.\n\n"
            "[Unreleased]: https://github.com/o/r/compare/v1.2.3...HEAD\n"
            "[1.2.3]: https://github.com/o/r/releases/tag/v1.2.3\n"
        )
        assert (
            Changelog(Document(changelog_path, text)).link_problems(
                self.REPOSITORY_URL, "1.2.3"
            )
            == []
        )

    def test_reports_the_plugin_versions_missing_link_beside_an_entry_with_a_bad_title(
        self, changelog_path: Path
    ) -> None:
        text = (
            "# Changelog\n\n## [Unreleased]\n\n## [1.2.3]\n\n- A.\n\n"
            "[Unreleased]: https://github.com/o/r/compare/v1.2.3...HEAD\n"
        )
        assert Changelog(Document(changelog_path, text)).link_problems(
            self.REPOSITORY_URL, "1.2.3"
        ) == [
            Problem(
                changelog_path,
                "has no link for [1.2.3]; add '[1.2.3]:"
                " https://github.com/o/r/releases/tag/v1.2.3' above the first ##"
                " heading",
            )
        ]

    def test_accepts_the_targets_each_link_names(self, changelog_path: Path) -> None:
        text = (
            self.HEAD + "[Unreleased]: https://github.com/o/r/compare/v1.2.3...HEAD\n"
            "[1.2.3]: https://github.com/o/r/releases/tag/v1.2.3\n"
        )
        assert (
            Changelog(Document(changelog_path, text)).link_problems(
                self.REPOSITORY_URL, "1.2.3"
            )
            == []
        )

    def test_reports_each_link_the_changelog_leaves_out(
        self, changelog_path: Path
    ) -> None:
        assert Changelog(Document(changelog_path, self.HEAD)).link_problems(
            self.REPOSITORY_URL, "1.2.3"
        ) == [
            Problem(
                changelog_path,
                "has no link for [1.2.3]; add '[1.2.3]:"
                " https://github.com/o/r/releases/tag/v1.2.3' above the first ##"
                " heading",
            ),
            Problem(
                changelog_path,
                "has no link for [Unreleased]; add '[Unreleased]:"
                " https://github.com/o/r/compare/v1.2.3...HEAD' above the first ##"
                " heading",
            ),
        ]

    def test_reports_the_titled_releases_links_before_the_plugin_versions(
        self, changelog_path: Path
    ) -> None:
        text = "# Changelog\n\n## [Unreleased]\n\n## [1.2.2] - 2026-01-01\n\n- A.\n"
        assert Changelog(Document(changelog_path, text)).link_problems(
            self.REPOSITORY_URL, "1.2.3"
        ) == [
            Problem(
                changelog_path,
                "has no link for [1.2.2]; add '[1.2.2]:"
                " https://github.com/o/r/releases/tag/v1.2.2' above the first ##"
                " heading",
            ),
            Problem(
                changelog_path,
                "has no link for [1.2.3]; add '[1.2.3]:"
                " https://github.com/o/r/releases/tag/v1.2.3' above the first ##"
                " heading",
            ),
            Problem(
                changelog_path,
                "has no link for [Unreleased]; add '[Unreleased]:"
                " https://github.com/o/r/compare/v1.2.3...HEAD' above the first ##"
                " heading",
            ),
        ]

    def test_reports_each_link_to_another_target(self, changelog_path: Path) -> None:
        text = (
            self.HEAD + "[Unreleased]: https://github.com/o/r/releases/tag/v1.2.3\n"
            "[1.2.3]: https://github.com/o/r/compare/v1.2.3...HEAD\n"
        )
        assert Changelog(Document(changelog_path, text)).link_problems(
            self.REPOSITORY_URL, "1.2.3"
        ) == [
            Problem(
                changelog_path,
                "links [1.2.3] to https://github.com/o/r/compare/v1.2.3...HEAD;"
                " link it to https://github.com/o/r/releases/tag/v1.2.3",
            ),
            Problem(
                changelog_path,
                "links [Unreleased] to https://github.com/o/r/releases/tag/v1.2.3;"
                " link it to https://github.com/o/r/compare/v1.2.3...HEAD",
            ),
        ]

    def test_reports_an_unreleased_link_without_its_section(
        self, changelog_path: Path
    ) -> None:
        text = (
            "# Changelog\n\n[Unreleased]: https://x\n\n## [1.2.3] - 2026-01-02\n\n"
            f"- A.\n\n[1.2.3]: {self.REPOSITORY_URL}/releases/tag/v1.2.3\n"
        )
        assert Changelog(Document(changelog_path, text)).link_problems(
            self.REPOSITORY_URL, "1.2.3"
        ) == [
            Problem(
                changelog_path,
                "links [Unreleased] but has no [Unreleased] section; add the section"
                " above the releases if changes await a release, or remove the link",
            )
        ]

    def test_leaves_the_link_of_an_unreleased_section_below_a_release(
        self, changelog_path: Path
    ) -> None:
        text = (
            "# Changelog\n\n[Unreleased]: https://x\n\n## [1.2.3] - 2026-01-02\n\n"
            "- A.\n\n## [Unreleased]\n\n"
            f"[1.2.3]: {self.REPOSITORY_URL}/releases/tag/v1.2.3\n"
        )
        assert (
            Changelog(Document(changelog_path, text)).link_problems(
                self.REPOSITORY_URL, "1.2.3"
            )
            == []
        )

    def test_accepts_an_unreleased_link_beside_its_section_in_another_case(
        self, changelog_path: Path
    ) -> None:
        text = (
            "# Changelog\n\n## [unreleased]\n\n## [1.2.3] - 2026-01-02\n\n- A.\n\n"
            "[Unreleased]: https://github.com/o/r/compare/v1.2.3...HEAD\n"
            "[1.2.3]: https://github.com/o/r/releases/tag/v1.2.3\n"
        )
        assert (
            Changelog(Document(changelog_path, text)).link_problems(
                self.REPOSITORY_URL, "1.2.3"
            )
            == []
        )
