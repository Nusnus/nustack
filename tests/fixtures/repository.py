"""A small repository that passes every check, held in memory for tests to break."""

import json
import re
from pathlib import Path
from pathlib import PurePosixPath
from typing import ClassVar

from nustack.plugin.plugin import Plugin
from nustack.record import CopyRecord
from nustack.repository.disk import Disk
from nustack.repository.repository import Repository
from nustack.tree import Blocked
from nustack.tree import Entry
from nustack.tree import File
from nustack.tree import Folder
from nustack.tree import Missing
from nustack.tree import NotAFolder
from nustack.tree import Read
from nustack.tree import Snapshot
from nustack.tree import Symlink
from nustack.tree import Tree
from nustack.tree import Unopened
lazy from nustack.problem import Problem


class MissingTextError(LookupError):
    """Text a test edits in a model file that the file does not hold."""

    def __init__(self, path: str, text: str) -> None:
        super().__init__(f"{path} does not hold {text!r}; edit text the file holds")


class ModelRepository:
    """A small repository that passes every check, written out by hand.

    Tests break one file of it and read what the check says; `save` writes it to
    disk for the tests of the commands and of the reads.
    """

    MANIFEST_FIELDS: ClassVar[frozendict[str, object]] = frozendict(
        {
            "name": "kit",
            "version": "1.2.3",
            "description": "A kit.",
            "author": frozendict({"name": "Ada"}),
            "homepage": "https://example.com/nus/kit",
            "repository": "https://example.com/nus/kit",
            "license": "MIT",
        }
    )
    MANIFEST: ClassVar[str] = json.dumps(MANIFEST_FIELDS)
    CLAUDE_MARKETPLACE_FIELDS: ClassVar[frozendict[str, object]] = frozendict(
        {
            "name": "kit",
            "description": "Ada's kit.",
            "owner": frozendict({"name": "Ada"}),
            "plugins": (
                frozendict(
                    {"name": "kit", "source": "./plugin", "description": "A kit."}
                ),
            ),
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
            "README.md": (
                "# kit\n\n### 1️⃣ Install\n\nRun `kit add`.\n\n"
                "### 2️⃣ Use\n\nRun `kit`.\n\n"
                "### 3️⃣ Turn it on\n\n```markdown\nWork in nus-mode.\n```\n\n"
                "| Skill | What it holds |\n"
                "| --- | --- |\n"
                "| [principle-naming](plugin/skills/principle-naming/SKILL.md) |"
                " Naming. |\n"
                "| [language-python](plugin/skills/language-python/SKILL.md) |"
                " Python. |\n"
            ),
            "CHANGELOG.md": (
                "# Changelog\n\n"
                "[Unreleased]: https://example.com/nus/kit/compare/v1.2.3...HEAD\n"
                "[1.2.3]: https://example.com/nus/kit/releases/tag/v1.2.3\n"
                "[1.2.2]: https://example.com/nus/kit/releases/tag/v1.2.2\n\n"
                "## [Unreleased]\n\n## [1.2.3] - 2026-01-02\n\n"
                "### Added\n\n- Adds the kit.\n\n"
                "## [1.2.2] - 2026-01-01\n\n- Starts.\n"
            ),
            ".claude-plugin/marketplace.json": json.dumps(CLAUDE_MARKETPLACE_FIELDS),
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
                '[tool.commitizen]\ntag_format = "v$version"\nversion_files = [\n'
                '  "plugin/.claude-plugin/plugin.json:version",\n'
                '  "plugin/.cursor-plugin/plugin.json:version",\n'
                '  "plugin/.devin-plugin/plugin.json:version",\n'
                '  "plugin/package.json:version",\n]\n\n'
                '[tool.ruff]\nextend-exclude = [".agents/skills/vendored"]\n'
            ),
            ".gitattributes": (
                "plugin/** text eol=lf\n.agents/skills/vendored/** -text\n"
            ),
            ".pre-commit-config.yaml": "repos:\n  - repo: local\n    hooks:\n"
            + "".join(
                f"      - id: {hook}\n"
                "        exclude: ^(?:\\.agents/skills/vendored)/\n"
                for hook in HOOK_IDS
            ),
            "vendored/copy.json": json.dumps(
                {
                    "upstream": "https://github.com/up/skills",
                    "source": "skills",
                    "folder": ".agents/skills",
                    "skills": ["vendored"],
                    "commit": "c" * 40,
                    "files": {
                        "vendored/LICENSE": "a22a2da24d1ceeef3d0c2f1f4f68923f55b8d4cc",
                        "vendored/SKILL.md": "ddf5f443afc72521c9dd8ca283a8bac781fb8237",
                    },
                },
                indent=2,
            )
            + "\n",
            ".agents/skills/vendored/LICENSE": "MIT\n",
            ".agents/skills/vendored/SKILL.md": (
                "---\nname: vendored\ndescription: Words.\n---\n"
            ),
            ".github/workflows/release.yml": 'on:\n  push:\n    tags: ["v*"]\n',
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
        self.copy_entries: dict[PurePosixPath, Entry] = {}

    def vendor_into_plugin(self) -> None:
        old, new = ".agents/skills/vendored", "plugin/skills/vendored"
        for name in ("LICENSE", "SKILL.md"):
            self.files[PurePosixPath(new, name)] = self.files.pop(
                PurePosixPath(old, name)
            )
        for path in (
            "vendored/copy.json",
            "pyproject.toml",
            ".pre-commit-config.yaml",
            ".gitattributes",
        ):
            text = self.files[PurePosixPath(path)].decode()
            self.write(
                path,
                text.replace(old.replace(".", "\\.", 1), new)
                .replace(old, new)
                .replace('"folder": ".agents/skills"', '"folder": "plugin/skills"'),
            )
        self.list_skill("vendored", "Words.")

    def copy_file(self, path: str, content: str) -> None:
        record = self.record()
        files = record.files | {f"vendored/{path}": CopyRecord.blob(content.encode())}
        self.write_record(record.model_copy(update={"files": files}))
        self.write(f"{record.folder}/vendored/{path}", content)

    def record(self) -> CopyRecord:
        return CopyRecord.parse(self.files[PurePosixPath("vendored/copy.json")])

    def write_record(
        self, record: CopyRecord, path: str = "vendored/copy.json"
    ) -> None:
        self.write(path, record.text)

    def record_before_first_sync(self) -> None:
        self.write_record(
            self.record().model_copy(update={"commit": None, "files": frozendict()})
        )

    def skip_in_hooks(self, exclude: str) -> None:
        for hook in self.HOOK_IDS:
            self.edit(
                ".pre-commit-config.yaml",
                f"      - id: {hook}\n"
                "        exclude: ^(?:\\.agents/skills/vendored)/\n",
                f"      - id: {hook}\n        exclude: {exclude}\n",
            )

    def rename_copy(self, skill: str) -> None:
        record = self.record()
        files = record.files
        self.write_record(
            record.model_copy(
                update={
                    "skills": (skill,),
                    "files": frozendict(
                        {
                            f"{skill}/LICENSE": files["vendored/LICENSE"],
                            f"{skill}/SKILL.md": files["vendored/SKILL.md"],
                        }
                    ),
                }
            )
        )
        for name in ("LICENSE", "SKILL.md"):
            self.write(
                f".agents/skills/{skill}/{name}",
                self.files.pop(PurePosixPath(".agents/skills/vendored", name)),
            )
        self.skip_in_hooks(f"^(?:\\.agents/skills/{re.escape(skill)})/")
        self.edit(
            "pyproject.toml", '".agents/skills/vendored"', f'".agents/skills/{skill}"'
        )
        self.edit(
            ".gitattributes", ".agents/skills/vendored/", f".agents/skills/{skill}/"
        )

    def record_a_first_skill(self) -> CopyRecord:
        record = self.record()
        files = record.files
        first = record.model_copy(
            update={
                "skills": ("first", "vendored"),
                "files": frozendict(
                    {
                        "first/LICENSE": files["vendored/LICENSE"],
                        "first/SKILL.md": files["vendored/SKILL.md"],
                    }
                )
                | files,
            }
        )
        self.write_record(first)
        self.skip_in_hooks("^(?:\\.agents/skills/first|\\.agents/skills/vendored)/")
        self.edit(
            "pyproject.toml",
            '[".agents/skills/vendored"]',
            '[".agents/skills/first", ".agents/skills/vendored"]',
        )
        self.edit(
            ".gitattributes",
            ".agents/skills/vendored/** -text\n",
            ".agents/skills/first/** -text\n.agents/skills/vendored/** -text\n",
        )
        return first

    def name_home(self, url: str) -> None:
        for manifest in Plugin.MANIFESTS:
            self.edit(
                str(Plugin.FOLDER / manifest),
                '"repository": "https://example.com/nus/kit"',
                f'"repository": "{url}"',
            )
        changelog = self.files[PurePosixPath("CHANGELOG.md")].decode()
        self.write(
            "CHANGELOG.md", changelog.replace("https://example.com/nus/kit", url)
        )

    def list_skill(self, name: str, description: str) -> None:
        self.edit(
            "README.md",
            "| --- | --- |\n",
            f"| --- | --- |\n| [{name}](plugin/skills/{name}/SKILL.md) |"
            f" {description} |\n",
        )

    def edit(self, path: str, old: str, new: str) -> None:
        before, found, after = self.files[PurePosixPath(path)].decode().partition(old)
        if not found:
            raise MissingTextError(path, old)
        self.write(path, before + new + after)

    def write(self, path: str, content: str | bytes) -> None:
        self.files[PurePosixPath(path)] = (
            content.encode() if isinstance(content, str) else content
        )

    def remove(self, path: str) -> None:
        del self.files[PurePosixPath(path)]

    def put(self, path: str, entry: Entry) -> None:
        self.entries[PurePosixPath(path).relative_to("plugin")] = entry

    def put_in_copy(self, path: str, entry: Entry) -> None:
        self.copy_entries[PurePosixPath(path)] = entry

    def fail_read(self, path: str, read: Read) -> None:
        self.reads[PurePosixPath(path)] = read

    def fail_listing(self, path: str, unopened: Unopened) -> None:
        self.unlisted[PurePosixPath(path)] = unopened

    def where(self, path: str) -> Path:
        return self.root / path

    def problems(self) -> list[Problem]:
        return Repository(self.snapshot()).problems()

    def snapshot(self) -> Snapshot:
        plugin_folder = PurePosixPath("plugin")
        entries: dict[PurePosixPath, Entry] = {}
        for path, content in self.files.items():
            if path.is_relative_to(plugin_folder):
                inside = path.relative_to(plugin_folder)
                entries |= {parent: Folder() for parent in inside.parents[:-1]}
                entries[inside] = File(content)
        entries |= self.entries
        # As Disk does, nothing is read below an entry that is not a folder, and a
        # symlink or a folder that will not open leaves only those entries.
        entries = {
            path: entry
            for path, entry in entries.items()
            if all(
                isinstance(entries.get(parent, Folder()), Folder)
                for parent in path.parents[:-1]
            )
        }
        unsafe = {
            path: entry
            for path, entry in entries.items()
            if isinstance(entry, Symlink | Unopened)
        }
        # A plugin path that is no folder it can read leaves only that entry.
        top = entries.get(PurePosixPath("."))
        if isinstance(top, NotAFolder | Missing | Symlink | Unopened):
            unsafe = {PurePosixPath("."): top}
        records = frozendict(
            (path, self.reads.get(path, self.read(path)))
            for path in sorted(
                {
                    *self.listing(str(CopyRecord.FOLDER)),
                    *(
                        path
                        for path in self.reads
                        if path.parent == CopyRecord.FOLDER
                        and path.suffix == CopyRecord.SUFFIX
                    ),
                }
            )
        )
        return Snapshot(
            self.root,
            Tree(
                self.root / plugin_folder,
                frozendict(sorted((unsafe or entries).items())),
            ),
            frozendict(
                (file, self.reads.get(file, self.read(file)))
                for file in Repository.FILES
            ),
            self.listing("src"),
            self.listing("tests"),
            frozendict(self.unlisted),
            records,
            frozendict(
                (folder, self.tree(folder))
                for folder in sorted(Disk.skill_folders(records))
            ),
            self.listing(".agents/skills"),
        )

    def tree(self, folder: PurePosixPath) -> Tree:
        entries: dict[PurePosixPath, Entry] = {}
        for path, content in self.files.items():
            if path.is_relative_to(folder):
                inside = path.relative_to(folder)
                entries |= {parent: Folder() for parent in inside.parents[:-1]}
                entries[inside] = File(content)
        entries |= {
            path.relative_to(folder): entry
            for path, entry in self.copy_entries.items()
            if path.is_relative_to(folder)
        }
        if not entries:
            return Tree(self.root / folder, frozendict({PurePosixPath("."): Missing()}))
        unsafe = {
            path: entry
            for path, entry in entries.items()
            if isinstance(entry, Symlink | Unopened)
        }
        # Only a copy folder's own place can hold a file where a folder belongs.
        if isinstance(top := entries.get(PurePosixPath(".")), NotAFolder):
            unsafe = {PurePosixPath("."): top}
        return Tree(self.root / folder, frozendict(sorted((unsafe or entries).items())))

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
