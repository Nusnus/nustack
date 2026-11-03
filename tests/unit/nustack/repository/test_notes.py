"""The release page reads on its own: the plugin, its changes, how to start."""

from nustack.repository.repository import Release
from nustack.repository.repository import Repository
lazy from tests.fixtures.repository import ModelRepository


class TestReleaseNotes:
    """The page opens on the plugin, and links its full changelog from a release.

    The first release has no release before it, so no comparison either.
    """

    def test_links_no_comparison_for_the_first_release(
        self, repository: ModelRepository
    ) -> None:
        repository.edit("CHANGELOG.md", "\n\n## [1.2.2] - 2026-01-01\n\n- Starts.", "")
        repository.edit(
            "CHANGELOG.md", "[1.2.2]: https://example.com/kit/releases/tag/v1.2.2\n", ""
        )
        repository.edit("CHANGELOG.md", "### Added", "Lead.\n\n### Added")
        release = Repository(repository.snapshot()).release()
        assert isinstance(release, Release)
        assert release.notes == (
            "> **[kit](https://example.com/kit)** · A kit.\n\nLead.\n\n"
            "## 🆕 What changed\n\n### Added\n\n- Adds the kit.\n\n"
            "## 🚀 Quick start\n\n### 1️⃣ Install\n\nRun `kit add`.\n\n"
            "### 2️⃣ Use\n\nRun `kit`."
        )
