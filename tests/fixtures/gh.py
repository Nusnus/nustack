"""A gh executable that replays the replies a test gives it and logs every call.

Put first on PATH, it stands in for gh, so the harness runs its real subprocess
calls. Beside it are the repository tests run GitHub on and the argv of each read of
it they replay.
"""

import json
import stat
import sys
from dataclasses import dataclass
from typing import ClassVar
lazy from pathlib import Path

from nustack.github.name import NameWithOwner


class GhArgv:
    """The repository tests run GitHub on, and the argv of each read of it they replay.

    Each argv is named for the GitHub method that runs it, and for the pull request
    or tag it reads. The open pull requests are those from branch sync/w into main.
    """

    REPOSITORY: ClassVar[NameWithOwner] = NameWithOwner("o", "r")
    DEFAULT_BRANCH: ClassVar[tuple[str, ...]] = (
        "api",
        "repos/o/r",
        "--jq",
        ".default_branch",
    )
    OPEN_PULLS: ClassVar[tuple[str, ...]] = (
        "api",
        "--method",
        "GET",
        "--paginate",
        "repos/o/r/pulls",
        "-f",
        "state=open",
        "-f",
        "base=main",
        "-f",
        "head=o:sync/w",
        "--jq",
        ".[] | select(.head.repo.id == .base.repo.id) | .number",
    )
    PULL_BODY_5: ClassVar[tuple[str, ...]] = (
        "api",
        "repos/o/r/pulls/5",
        "--jq",
        ".body",
    )
    PULL_BODY_267: ClassVar[tuple[str, ...]] = (
        "api",
        "repos/o/r/pulls/267",
        "--jq",
        ".body",
    )
    TAG_COMMIT_V1_2_3: ClassVar[tuple[str, ...]] = (
        "api",
        "repos/o/r/commits/tags/v1.2.3",
        "--jq",
        ".sha",
    )
    TAG_COMMIT_V0_0_1: ClassVar[tuple[str, ...]] = (
        "api",
        "repos/o/r/commits/tags/v0.0.1",
        "--jq",
        ".sha",
    )
    TAG_COMMIT_V0_1_0: ClassVar[tuple[str, ...]] = (
        "api",
        "repos/o/r/commits/tags/v0.1.0",
        "--jq",
        ".sha",
    )
    RELEASE_STATE_V1_2_3: ClassVar[tuple[str, ...]] = (
        *("release", "view", "v1.2.3", "-R", "o/r"),
        *("--json", "isDraft", "--jq", ".isDraft"),
    )
    RELEASE_STATE_V0_0_1: ClassVar[tuple[str, ...]] = (
        *("release", "view", "v0.0.1", "-R", "o/r"),
        *("--json", "isDraft", "--jq", ".isDraft"),
    )
    RELEASE_STATE_V0_1_0: ClassVar[tuple[str, ...]] = (
        *("release", "view", "v0.1.0", "-R", "o/r"),
        *("--json", "isDraft", "--jq", ".isDraft"),
    )


@dataclass(frozen=True)
class FakeGh:
    """A folder holding the gh executable, its replies and its log of calls.

    Replies to one call come back in the order given, the last one from then on.
    A call no reply matches prints nothing and succeeds. That departs from gh,
    which prints a link for some changes, since the harness reads no output of a
    command that changes GitHub; a test of a read replays a recorded reply.
    """

    SCRIPT: ClassVar[str] = """\
import json, pathlib, sys
here = pathlib.Path(sys.argv[0]).parent
argv = sys.argv[1:]
with (here / "calls.jsonl").open("a") as log:
    log.write(json.dumps({"argv": argv, "stdin": sys.stdin.read()}) + "\\n")
replies = json.loads((here / "replies.json").read_text())
queue = replies.get(json.dumps(argv), [{"stdout": "", "stderr": "", "code": 0}])
reply = queue.pop(0) if len(queue) > 1 else queue[0]
(here / "replies.json").write_text(json.dumps(replies))
sys.stdout.write(reply["stdout"])
sys.stderr.write(reply["stderr"])
sys.exit(reply["code"])
"""
    folder: Path

    @property
    def calls(self) -> list[tuple[tuple[str, ...], str]]:
        log = self.folder / "calls.jsonl"
        if not log.exists():
            return []
        return [
            (tuple(call["argv"]), call["stdin"])
            for call in map(json.loads, log.read_text().splitlines())
        ]

    @classmethod
    def install(cls, folder: Path) -> FakeGh:
        fake = cls(folder)
        folder.mkdir()
        script = folder / "gh"
        script.write_text(f"#!{sys.executable}\n{cls.SCRIPT}")
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        (folder / "replies.json").write_text("{}")
        return fake

    def replay(self, *argv: str, recording: Path) -> str:
        reply = json.loads(recording.read_text())
        self.reply(
            *argv, stdout=reply["stdout"], stderr=reply["stderr"], code=reply["code"]
        )
        return reply["stdout"]

    def reply(
        self, *argv: str, stdout: str = "", stderr: str = "", code: int = 0
    ) -> None:
        path = self.folder / "replies.json"
        replies = json.loads(path.read_text())
        replies.setdefault(json.dumps(list(argv)), []).append(
            {"stdout": stdout, "stderr": stderr, "code": code}
        )
        path.write_text(json.dumps(replies))
