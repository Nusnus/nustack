"""What a vendored copy records: where it comes from and the bytes it holds.

A record, `vendored/<copy>.json`, is the one home of a copy's upstream repository,
the upstream folder that holds the skills it copies, the folder in this repository
that holds the copies, the skills it copies, the upstream commit it copied and the
Git blob of each file the copy holds. The sync writes it with the copy, and the
check holds each file to its blob, so the copy needs no network to check. The
check reads only whether the commit is null, never comparing it with upstream,
and holds no file's mode, which the sync copies from upstream, so a record
written by hand, with blobs hashed from the files here and a made-up commit,
passes until the sync runs. A record whose commit is null names skills the sync
has not copied yet.
"""

import hashlib
import json
import re
from pathlib import Path
from pathlib import PurePosixPath
from typing import Annotated
from typing import ClassVar
from typing import Self
from typing import assert_never

from pydantic import AfterValidator
from pydantic import BaseModel
from pydantic import BeforeValidator
from pydantic import ConfigDict
from pydantic import Field
from pydantic import PlainSerializer
from pydantic import ValidationError
from pydantic import model_validator

from nustack.github.name import RepositoryUrl
from nustack.plugin.plugin import Plugin
from nustack.plugin.skill import HostFrontmatter
from nustack.plugin.skill import Kind
from nustack.plugin.skill import Skill
from nustack.problem import Problem
from nustack.sha import NotSha1Error
from nustack.sha import Sha
from nustack.tree import Absent
from nustack.tree import File
from nustack.tree import Read
from nustack.tree import Unreadable
from nustack.validation import Pattern
from nustack.validation import Schema


class InvalidRecordError(ValueError):
    """A record that is not valid JSON, or breaks its schema."""


def plain_path(value: str) -> str:
    path = PurePosixPath(value)
    # Git names paths as plain text, with no . part, no // and no / at either end.
    if not path.parts or path.is_absolute() or ".." in path.parts or str(path) != value:
        msg = (
            "write a relative path with no . or .. part, no //, and no / at either end"
        )
        raise ValueError(msg)
    return value


# A Problem repeats a record's file path, so each part holds only characters that
# print as themselves, as every upstream file copied so far does.
def file_path(value: str) -> str:
    part = r"[A-Za-z0-9._-]+"
    if not re.fullmatch(f"{part}(/{part})*", plain_path(value)):
        msg = "write each part of the path in letters, digits, ., _ and - alone"
        raise ValueError(msg)
    return value


# A value of another type is left for pydantic, which names the type it wants.
def plain_folder(value: object) -> object:
    return plain_path(value) if isinstance(value, str) else value


# RepositoryUrl and Sha are no types pydantic reads, so a value of another type is
# refused here with the fix pydantic would give. The sync clones the URL with .git
# added.
def repository_url(value: object) -> RepositoryUrl:
    if not isinstance(value, str):
        raise ValueError(Schema.FIXES["string_type"])  # noqa: TRY004 -- pydantic reads only a ValueError as a refusal
    url = RepositoryUrl.parse(value)
    if url.name_with_owner.name.endswith(".git"):
        msg = "write the URL with no .git suffix"
        raise ValueError(msg)
    return url


# NotSha1Error speaks of what Git names, so the record's own fix is the pattern's.
def commit_sha(value: object) -> object:
    if isinstance(value, Sha):
        return value
    if not isinstance(value, str):
        raise ValueError(Schema.FIXES["string_type"])  # noqa: TRY004 -- pydantic reads only a ValueError as a refusal
    try:
        return Sha(value)
    except NotSha1Error:
        raise ValueError(Pattern.SHA.fix) from None


type PlainPath = Annotated[str, AfterValidator(plain_path)]
type PlainFolder = Annotated[PurePosixPath, BeforeValidator(plain_folder)]
type FilePath = Annotated[str, AfterValidator(file_path)]
# A blob's ID stays text, held to the SHA-1 pattern: the check only compares it
# with CopyRecord.blob's digest of a file's bytes and the sync only hands it to Git,
# while Sha names a commit, which a blob never is.
type ObjectId = Annotated[str, Field(pattern=Pattern.SHA.value)]
type CommitSha = Annotated[Sha, BeforeValidator(commit_sha), PlainSerializer(str)]
type Upstream = Annotated[
    RepositoryUrl, BeforeValidator(repository_url), PlainSerializer(str)
]


class CopyRecord(BaseModel):
    """A vendored copy's upstream and source, its skills, commit and file blobs.

    Each file sits under one of its skills, by its path from the copy's folder; a
    copied skill holds a `SKILL.md` and the license it was copied under. The skills
    are a fixed list: the sync never copies a skill upstream adds, and stops on a
    listed skill upstream no longer holds. The source is a folder below upstream's
    root, so an upstream that keeps its skills at its root cannot be copied.
    """

    FOLDER: ClassVar[PurePosixPath] = PurePosixPath("vendored")
    SUFFIX: ClassVar[str] = ".json"
    LICENSE: ClassVar[str] = Skill.LICENSE
    MISSING: ClassVar[str] = (
        f"is missing; pass a record in {FOLDER}/ by its path from the repository's"
        " folder"
    )
    SYMLINK_FIX: ClassVar[str] = (
        "is a symlink, which the check never reads through; replace it with the {}"
        " itself"
    )
    SYMLINK: ClassVar[str] = SYMLINK_FIX.format("record")
    FOLDER_SYMLINK: ClassVar[str] = SYMLINK_FIX.format("folder")
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    upstream: Upstream
    source: PlainFolder
    folder: PlainFolder
    skills: tuple[
        Annotated[
            str,
            Field(pattern=Pattern.NAME.value, max_length=HostFrontmatter.NAME_LENGTH),
        ],
        ...,
    ]
    commit: CommitSha | None
    files: frozendict[FilePath, ObjectId]

    @property
    def upstream_folders(self) -> tuple[str, ...]:
        return tuple(f"{self.source}/{skill}" for skill in self.skills)

    @property
    def skill_folders(self) -> tuple[PurePosixPath, ...]:
        return tuple(self.skill_folder(skill) for skill in self.skills)

    @property
    def in_plugin(self) -> bool:
        return self.folder.is_relative_to(Plugin.FOLDER)

    @property
    def text(self) -> str:
        fields = self.model_dump(mode="json")
        fields["files"] = dict(sorted(fields["files"].items()))
        return json.dumps(fields, indent=2) + "\n"

    @model_validator(mode="after")
    def skills_listed_once(self) -> Self:
        if not self.skills or len(set(self.skills)) != len(self.skills):
            msg = "skills: list each skill the copy holds, once"
            raise ValueError(msg)
        return self

    # A skill named as the mode, a principle or a language skill is one nustack's
    # authors write; this check comes before the files', so the record's first
    # problem names the skill rather than the files it lacks.
    @model_validator(mode="after")
    def skills_copied_not_authored(self) -> Self:
        if any(Plugin.is_authored_name(skill) for skill in self.skills):
            prefixes = " or ".join(
                kind.prefix for kind in Kind if kind.prefix is not None
            )
            msg = (
                f"skills: lists a skill whose name starts with {prefixes} or ends in"
                " -mode, which only nustack's authors write; drop it from skills"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def commit_and_files_from_one_sync(self) -> Self:
        if (self.commit is None) != (not self.files):
            msg = (
                "commit and files: set both from one sync, or set commit to null and"
                " files to {} until the first sync"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def files_under_their_skills(self) -> Self:
        if any(
            path.partition("/")[0] not in self.skills or not path.partition("/")[2]
            for path in self.files
        ):
            msg = "files: put each file under a skill the record lists"
            raise ValueError(msg)
        if self.files and any(
            f"{skill}/{name}" not in self.files
            for skill in self.skills
            for name in (Skill.FILE, self.LICENSE)
        ):
            msg = f"files: give each skill its {Skill.FILE} and {self.LICENSE}"
            raise ValueError(msg)
        return self

    # The sync pushes each record's copy to the branch sync/<copy>, so a record whose
    # name Git refuses in a branch is one it never syncs.
    @staticmethod
    def branch(path: PurePosixPath) -> str:
        return f"sync/{path.stem}"

    @classmethod
    def reading(
        cls, root: Path, path: PurePosixPath, read: Read, missing: str
    ) -> CopyRecord | Problem:
        if not cls.read_by_sync(path):
            move = (
                f", or move it out of {cls.FOLDER}/"
                if path.is_relative_to(cls.FOLDER)
                else ""
            )
            return Problem(
                root / path,
                f"is no record the sync reads; name it {cls.FOLDER}/<copy>{cls.SUFFIX},"
                f" with <copy> in kebab case such as obsidian-skills{move}",
            )
        return cls.read(root / path, read, missing)

    @classmethod
    def read_by_sync(cls, path: PurePosixPath) -> bool:
        return (
            path.parent == cls.FOLDER
            and path.suffix == cls.SUFFIX
            and re.fullmatch(Pattern.NAME.unanchored, path.stem) is not None
        )

    @classmethod
    def read(cls, path: Path, read: Read, missing: str) -> CopyRecord | Problem:
        match read:
            case File(content=content):
                try:
                    _ = content.decode()
                except UnicodeDecodeError:
                    return Problem(path, Problem.NOT_UTF8)
                try:
                    record = cls.parse(content)
                except InvalidRecordError as error:
                    return Problem(path, f"is invalid: {error}")
                if content != record.text.encode():
                    return Problem(path, cls.layout())
                return record
            case Absent() as absent:
                return Problem(path, absent.absence(missing))
            case Unreadable(reason=reason):
                return Problem(path, reason)
            case unexpected:
                assert_never(unexpected)

    @classmethod
    def parse(cls, content: bytes) -> Self:
        schema = Schema(cls)
        try:
            record = cls.model_validate_json(content)
        except ValidationError as error:
            raise InvalidRecordError(schema.refusal(content, error)) from error
        if refusal := schema.refusal(content):
            raise InvalidRecordError(refusal)
        return record

    # The sync writes a record as text does, so one laid out otherwise would make
    # the next sync propose a change to the record alone.
    @classmethod
    def layout(cls) -> str:
        return (
            "is laid out other than the sync writes it; write it as JSON indented by"
            f" 2 spaces, with its keys in the order {', '.join(cls.model_fields)}, its"
            " files sorted, every non-ASCII character escaped as \\uXXXX and one"
            " newline at the end"
        )

    @staticmethod
    def blob(data: bytes) -> str:
        # Git names a blob by the SHA-1 of its header and bytes:
        # https://git-scm.com/book/en/v2/Git-Internals-Git-Objects#_object_storage
        header = f"blob {len(data)}\0".encode()
        # The flag only matters where FIPS mode refuses SHA-1, which no test runs.
        return hashlib.sha1(
            header + data,
            usedforsecurity=False,  # pragma: no mutate
        ).hexdigest()

    def skill_folder(self, skill: str) -> PurePosixPath:
        return self.folder / skill

    def files_of(self, skill: str) -> frozendict[str, str]:
        prefix = f"{skill}/"
        return frozendict(
            (path.removeprefix(prefix), oid)
            for path, oid in self.files.items()
            if path.startswith(prefix)
        )

    def copied(self, commit: Sha, files: frozendict[str, str]) -> Self:
        return self.model_validate(
            self.model_dump() | {"commit": commit, "files": files}
        )
