"""A sync-description run that a test expects to stop."""

from dataclasses import dataclass
lazy from pathlib import Path

import pytest

from nustack.cli.command import sync_description
lazy from nustack.sync.description import SyncLinks


@dataclass(frozen=True)
class StoppedSync:
    """Runs sync-description on a repository's record, keeping its exit and output."""

    links: SyncLinks
    capsys: pytest.CaptureFixture[str]

    def report(
        self, root: Path, record: str = "vendored/copy.json"
    ) -> tuple[int | str | None, str, str]:
        with pytest.raises(SystemExit) as caught:
            sync_description(
                run=self.links.run,
                checks=self.links.checks,
                clone=root,
                record=record,
                root=root,
            )
        output = self.capsys.readouterr()
        return caught.value.code, output.out, output.err
