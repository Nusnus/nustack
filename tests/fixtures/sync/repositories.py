"""Real Git repositories shaped like the sync's upstream and nustack's checkout."""

from dataclasses import dataclass
from typing import ClassVar
lazy from collections.abc import Mapping

from nustack.record import CopyRecord
lazy from nustack.sha import Sha
lazy from tests.fixtures.git_repository import GitRepository


@dataclass(frozen=True)
class Sync:
    """An upstream skill that moved on once, and a checkout copying its first state.

    The source folder's name is a glob pattern, so Git reading it as a pattern
    instead of a path shows. The checkout's record names the first state.
    """

    UPSTREAM_URL: ClassVar[str] = "https://github.com/up/skills"
    SOURCE: ClassVar[str] = "skills*"
    SKILL: ClassVar[str] = "s"
    SOURCE_FOLDER: ClassVar[str] = f"{SOURCE}/{SKILL}"
    FOLDER: ClassVar[str] = ".agents/skills"
    COPY: ClassVar[str] = f"{FOLDER}/{SKILL}"
    RECORD: ClassVar[str] = "vendored/w.json"
    BASE: ClassVar[frozendict[str, bytes]] = frozendict(
        {"LICENSE": b"MIT\n", "SKILL.md": b"old\n"}
    )
    upstream: GitRepository
    checkout: GitRepository
    first: Sha
    second: Sha

    @classmethod
    def record_of(
        cls, commit: Sha | None, files: Mapping[str, bytes], **fields: str
    ) -> CopyRecord:
        return CopyRecord.model_validate(
            {
                "upstream": cls.UPSTREAM_URL,
                "source": cls.SOURCE,
                "folder": cls.FOLDER,
                "skills": [cls.SKILL],
                "commit": commit,
                "files": {
                    f"{cls.SKILL}/{path}": CopyRecord.blob(data)
                    for path, data in files.items()
                },
            }
            | fields
        )

    @property
    def record(self) -> CopyRecord:
        return self.record_of(self.first, self.BASE)
