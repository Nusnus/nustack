"""A gh executable that replays the replies a test gives it and logs every call.

Put first on PATH, it stands in for gh, so the harness runs its real subprocess
calls.
"""

import json
import stat
import sys
from dataclasses import dataclass
from typing import ClassVar
lazy from pathlib import Path


@dataclass(frozen=True)
class FakeGh:
    """A folder holding the gh executable, its replies and its log of calls.

    Replies to one call come back in the order given, the last one from then on.
    A call no reply matches prints nothing and succeeds, as gh's commands that
    change GitHub do once GitHub accepts them.
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
