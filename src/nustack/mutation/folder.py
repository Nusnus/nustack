"""mutmut's `mutants/` folder: a full run's verdicts, readied for the next run.

The folder keeps, from mutmut's last full run, the commit it ran on and which tests
cover each function, in `mutmut-stats.json`, and each mutant's verdict, in a `.meta`
file beside each mutated source file's copy. A folder whose files are missing or do not
parse holds no verdicts to keep, and a run from it starts empty. Readying the folder
keeps only those files, since mutmut takes a copy newer than its source as unchanged
and keeps a copy whose source is gone, and empties each verdict that must run again.
Each `.meta` file it empties lands whole: it is written to a `.partial` file beside it,
which only a run killed by a signal Python does not handle can leave, and which the
next run removes. A machine crash can still cut one short, which the next read takes
as no verdicts to keep.
"""

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import TypeAdapter
from pydantic import ValidationError

from nustack.sha import Sha
from nustack.sha import ShaError


class Stats(BaseModel):
    """`mutmut-stats.json`, down to the full run's commit and each function's tests."""

    model_config = ConfigDict(frozen=True)

    git_commit: str | None
    tests_by_mangled_function_name: frozendict[str, tuple[str, ...]]


class Verdicts(BaseModel):
    """A `.meta` file, down to each mutant's verdict."""

    model_config = ConfigDict(frozen=True)

    exit_code_by_key: frozendict[str, int | None]


@dataclass(frozen=True)
class Baseline:
    """A full run's commit, each function's tests and each `.meta` file's verdicts."""

    commit: Sha
    tests_by_function: frozendict[str, tuple[str, ...]]
    verdicts: frozendict[Path, Verdicts]


@dataclass(frozen=True)
class MutantsFolder:
    """mutmut's `mutants/` folder, holding the verdicts of its last full run."""

    STATS: ClassVar[str] = "mutmut-stats.json"
    META: ClassVar[str] = ".meta"
    # mutmut's exit code for a mutant its tests let live, which a new test may kill:
    # https://github.com/boxed/mutmut/blob/3.8.1/src/mutmut/stats.py#L15-L36
    SURVIVED: ClassVar[int] = 0
    # mutmut names each mutant <function>__mutmut_<number>:
    # https://github.com/boxed/mutmut/blob/3.8.1/src/mutmut/utils/format_utils.py#L71-L73
    MUTANT: ClassVar[str] = "__mutmut_"
    # Rewriting a .meta file keeps its other fields, whatever mutmut puts there.
    META_FIELDS: ClassVar[TypeAdapter[dict[str, object]]] = TypeAdapter(
        dict[str, object]
    )
    PARTIAL: ClassVar[str] = ".partial"
    path: Path

    def baseline(self) -> Baseline | str:
        stats_path = self.path / self.STATS
        try:
            stats = Stats.model_validate_json(stats_path.read_bytes())
            verdicts = frozendict(
                (meta, Verdicts.model_validate_json(meta.read_bytes()))
                for meta in sorted(self.path.rglob(f"*{self.META}"))
            )
        except FileNotFoundError:
            return f"{stats_path} is missing, so every mutant runs"
        except ValidationError:
            return (
                f"{self.path} holds a file mutmut did not write whole, so every mutant"
                " runs"
            )
        if stats.git_commit is None:
            return f"{stats_path} names no commit, so every mutant runs"
        try:
            commit = Sha.parse(stats.git_commit)
        except ShaError:
            return f"{stats_path} names no commit by its SHA-1, so every mutant runs"
        return Baseline(commit, stats.tests_by_mangled_function_name, verdicts)

    def clear(self) -> None:
        if self.path.exists():
            shutil.rmtree(self.path)

    def keep(self, baseline: Baseline, functions: frozenset[str]) -> None:
        for path in sorted(self.path.rglob("*"), reverse=True):
            if path.is_dir():
                if not any(path.iterdir()):
                    path.rmdir()
            elif path.name != self.STATS and path.suffix != self.META:
                path.unlink()
        for meta, verdicts in baseline.verdicts.items():
            kept = {
                mutant: None
                if code == self.SURVIVED
                or mutant.partition(self.MUTANT)[0] in functions
                else code
                for mutant, code in verdicts.exit_code_by_key.items()
            }
            if kept != verdicts.exit_code_by_key:
                fields = self.META_FIELDS.validate_json(meta.read_bytes())
                self.replace(meta, fields | {"exit_code_by_key": kept})

    # mutmut, the file's only reader, runs as the same user, so mkstemp's owner-only
    # mode serves it.
    def replace(self, meta: Path, fields: dict[str, object]) -> None:
        descriptor, location = tempfile.mkstemp(suffix=self.PARTIAL, dir=meta.parent)
        partial = Path(location)
        try:
            with os.fdopen(descriptor, "w") as file:
                json.dump(fields, file)
            partial.replace(meta)
        finally:
            # Once the move lands the partial name is gone, so this acts only on a
            # failure or an interrupt.
            partial.unlink(missing_ok=True)
