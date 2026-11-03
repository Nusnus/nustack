"""A small repository that passes every check, held in memory for tests to break."""

import json
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar

from nustack.repository.repository import Repository
from nustack.tree import Blocked
from nustack.tree import Entry
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Missing
from nustack.tree import Read
from nustack.tree import Snapshot
from nustack.tree import Tree
from nustack.tree import Unopened
lazy from nustack.problem import Problem


class ModelRepository:
    """A small repository that passes every check, written out by hand.

    Tests break one file of it and read what the check says; `save` writes it to
    disk for the tests of the commands and of the reads.
    """

    MANIFEST: ClassVar[str] = json.dumps(
        {
            "name": "kit",
            "version": "1.2.3",
            "description": "A kit.",
            "author": {"name": "Ada"},
            "homepage": "https://example.com/kit",
            "repository": "https://example.com/kit",
            "license": "MIT",
        }
    )
    HIDDEN: ClassVar[str] = (
        "disable-model-invocation: true\ntriggers:\n  - user\n---\n\n"
    )
    HOOK_IDS: ClassVar[tuple[str, ...]] = (
        "end-of-file-fixer",
        "fix-byte-order-marker",
        "mixed-line-ending",
        "trailing-whitespace",
        "markdownlint-cli2",
    )
    FILES: ClassVar[frozendict[str, str]] = frozendict(
        {
            "plugin/.devin-plugin/plugin.json": MANIFEST,
            "plugin/.claude-plugin/plugin.json": MANIFEST,
            "plugin/.cursor-plugin/plugin.json": MANIFEST,
            "plugin/LICENSE": "MIT License\n",
            "plugin/opencode.ts": "export default {};\n",
            "plugin/hooks/hooks.json": '{"hooks": {}}',
            "plugin/hooks/reload-nus-mode.sh": "#!/bin/sh\n",
            "plugin/package.json": (
                '{"name": "kit", "version": "1.2.3", "type": "module",'
                ' "exports": {".": "./opencode.ts"}}'
            ),
            "plugin/skills/nus-mode/SKILL.md": (
                "---\nname: nus-mode\ndescription: The mode.\n---\n\n# nus-mode\n\n"
                "## Goal\n\nShip.\n\n"
                "## Playbooks\n\n"
                "- [new project](playbooks/new-project.md): start one.\n\n"
                "## Principles\n\n"
                "- [naming](../principle-naming/SKILL.md): you name.\n\n"
                "## Languages\n\n- [Python](../language-python/SKILL.md): you write"
                " Python.\n"
            ),
            "plugin/skills/nus-mode/playbooks/new-project.md": (
                "# New project\n\n"
                "1. **Learn the project.** Done when its terms are written down.\n"
                "2. **Write AGENTS.md** with this line:\n\n"
                "   ```markdown\n   Work in nus-mode.\n   ```\n\n"
                "   Done when AGENTS.md holds the line, as [the goal]"
                "(../SKILL.md#goal) asks.\n"
            ),
            "plugin/skills/principle-naming/SKILL.md": (
                "---\nname: principle-naming\ndescription: Naming.\n"
                f"{HIDDEN}# Naming\n\nName each part for what it does.\n"
            ),
            "plugin/skills/language-python/SKILL.md": (
                "---\nname: language-python\ndescription: Python.\n"
                f"{HIDDEN}# Python\n\nType every signature.\n"
            ),
            "LICENSE": "MIT License\n",
            "README.md": "# kit\n\n```markdown\nWork in nus-mode.\n```\n",
            "CHANGELOG.md": (
                "# Changelog\n\n## [Unreleased]\n\n## [1.2.3] - 2026-01-02\n\n"
                "- Adds the kit.\n\n## [1.2.2] - 2026-01-01\n\n- Starts.\n\n"
                "[Unreleased]: https://example.com/kit/compare/v1.2.3...HEAD\n"
                "[1.2.3]: https://example.com/kit/releases/tag/v1.2.3\n"
                "[1.2.2]: https://example.com/kit/releases/tag/v1.2.2\n"
            ),
            ".claude-plugin/marketplace.json": json.dumps(
                {
                    "name": "kit",
                    "description": "Ada's kit.",
                    "owner": {"name": "Ada"},
                    "plugins": [
                        {"name": "kit", "source": "./plugin", "description": "A kit."}
                    ],
                }
            ),
            ".cursor-plugin/marketplace.json": json.dumps(
                {
                    "name": "kit",
                    "owner": {"name": "Ada"},
                    "metadata": {"description": "Ada's kit."},
                    "plugins": [
                        {"name": "kit", "source": "plugin", "description": "A kit."}
                    ],
                }
            ),
            "pyproject.toml": (
                '[project]\nname = "kit"\nversion = "1.2.3"\n\n'
                '[tool.ruff]\nextend-exclude = [".agents/skills/vendored"]\n'
            ),
            ".pre-commit-config.yaml": "repos:\n  - repo: local\n    hooks:\n"
            + "".join(
                f"      - id: {hook}\n        exclude: ^\\.agents/skills/vendored/\n"
                for hook in HOOK_IDS
            ),
            ".github/workflows/sync-writing-for-agents.yml": (
                "jobs:\n  sync:\n    env:\n      DESTINATION: .agents/skills/vendored\n"
            ),
            ".github/pull_request_template.md": "# Template\n",
            "src/kit/tool.py": "",
            "tests/unit/kit/test_tool.py": "",
            "tests/unit/plugin/opencode.test.ts": "",
            "tests/integration/plugin/hooks/reload-nus-mode.test.ts": "",
        }
    )

    def __init__(self, root: Path) -> None:
        self.root = root
        self.files: dict[PurePosixPath, bytes] = {
            PurePosixPath(path): text.encode() for path, text in self.FILES.items()
        }
        self.entries: dict[PurePosixPath, Entry] = {}
        self.reads: dict[PurePosixPath, Read] = {}
        self.unlisted: dict[PurePosixPath, Unopened] = {}

    def edit(self, path: str, old: str, new: str) -> None:
        text = self.files[PurePosixPath(path)].decode()
        start = text.index(old)
        self.write(path, text[:start] + new + text[start + len(old) :])

    def write(self, path: str, content: str | bytes) -> None:
        self.files[PurePosixPath(path)] = (
            content.encode() if isinstance(content, str) else content
        )

    def remove(self, path: str) -> None:
        del self.files[PurePosixPath(path)]

    def put(self, path: str, entry: Entry) -> None:
        self.entries[PurePosixPath(path).relative_to("plugin")] = entry

    def fail_read(self, path: str, read: Read) -> None:
        self.reads[PurePosixPath(path)] = read

    def fail_listing(self, path: str, unopened: Unopened) -> None:
        self.unlisted[PurePosixPath(path)] = unopened

    def where(self, path: str) -> Path:
        return self.root / path

    def problems(self) -> list[Problem]:
        return Repository(self.snapshot()).problems()

    def snapshot(self) -> Snapshot:
        plugin = PurePosixPath("plugin")
        entries: dict[PurePosixPath, Entry] = {}
        for path, content in self.files.items():
            if path.is_relative_to(plugin):
                inside = path.relative_to(plugin)
                entries |= {parent: Folder() for parent in inside.parents[:-1]}
                entries[inside] = File(content)
        entries |= self.entries
        return Snapshot(
            self.root,
            Tree(self.root / plugin, frozendict(sorted(entries.items()))),
            frozendict(
                (file, self.reads.get(file, self.read(file)))
                for file in Repository.FILES
            ),
            self.listing("src"),
            self.listing("tests"),
            frozendict(self.unlisted),
        )

    def read(self, path: PurePosixPath) -> Read:
        if path in self.files:
            return File(self.files[path])
        for parent in reversed(path.parents[:-1]):
            if parent in self.files:
                return Blocked(self.root / parent, File.IN_A_FOLDERS_PLACE)
        return Missing()

    def listing(self, folder: str) -> tuple[PurePosixPath, ...]:
        return tuple(sorted(path for path in self.files if path.is_relative_to(folder)))

    def save(self) -> Path:
        for path, content in self.files.items():
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_bytes(content)
        return self.root
