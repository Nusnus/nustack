"""mutants/ yields its full run's verdicts, or why it holds none, and keeps them."""

import json
import re
import signal
lazy from pathlib import Path

import pytest

from nustack.mutation.folder import Baseline
from nustack.mutation.folder import MutantsFolder
from nustack.mutation.folder import Verdicts
from nustack.sha import Sha


class TestMutantsFolder:
    """A full run's commit, tests and verdicts come back, or the reason none do.

    clear removes the folder, whether or not it exists. keep leaves only the stats
    and the verdicts, and empties each survivor's verdict and each verdict of a
    function to run again, reading a mutant's function up to its first `__mutmut_`
    as mutmut does, and rewriting no other file. A rewrite lands whole through a
    `.partial` file beside it, which an interrupt removes.
    """

    COMMIT = "0123456789abcdef0123456789abcdef01234567"
    STATS = frozendict(
        {
            "git_commit": COMMIT,
            "tests_by_mangled_function_name": {"pkg.a.x_f": ["tests/test_a.py::T::t"]},
            "stats_time": 1.5,
        }
    )
    VERDICTS = frozendict(
        {
            "exit_code_by_key": {
                "pkg.a.x_f__mutmut_1": 1,
                "pkg.a.x_f__mutmut_2": 36,
                "pkg.a.x_g__mutmut_1": 0,
                "pkg.a.x_g__mutmut_2": 1,
                "pkg.a.x_g__mutmut_3": None,
                "pkg.a.x_f__mutmut_x__mutmut_1": 1,
            },
            "hash_by_function_name": {"x_f": "1a"},
        }
    )
    KEPT = frozendict({"exit_code_by_key": {"pkg.b.x_h__mutmut_1": 1}})

    @pytest.fixture
    def folder(self, tmp_path: Path) -> MutantsFolder:
        folder = tmp_path / "mutants"
        (folder / "src/pkg/empty").mkdir(parents=True)
        (folder / "tests").mkdir()
        (folder / MutantsFolder.STATS).write_text(json.dumps(dict(self.STATS)))
        (folder / "src/pkg/a.py.meta").write_text(json.dumps(dict(self.VERDICTS)))
        (folder / "src/pkg/b.py.meta").write_text(json.dumps(dict(self.KEPT)))
        (folder / "src/pkg/a.py").write_text("")
        (folder / "src/pkg/a.py.spans").write_text("{}")
        (folder / "tests/test_a.py").write_text("")
        return MutantsFolder(folder)

    def test_reads_the_full_runs_commit_tests_and_verdicts(
        self, folder: MutantsFolder
    ) -> None:
        assert folder.baseline() == Baseline(
            Sha(self.COMMIT),
            frozendict({"pkg.a.x_f": ("tests/test_a.py::T::t",)}),
            frozendict(
                {
                    folder.path / "src/pkg/a.py.meta": Verdicts(
                        exit_code_by_key=self.VERDICTS["exit_code_by_key"]
                    ),
                    folder.path / "src/pkg/b.py.meta": Verdicts(
                        exit_code_by_key=self.KEPT["exit_code_by_key"]
                    ),
                }
            ),
        )

    def test_names_missing_stats(self, tmp_path: Path) -> None:
        assert MutantsFolder(tmp_path / "mutants").baseline() == (
            f"{tmp_path}/mutants/mutmut-stats.json is missing, so every mutant runs"
        )

    @pytest.mark.parametrize(
        "path", [MutantsFolder.STATS, "src/pkg/a.py.meta", "src/pkg/b.py.meta"]
    )
    def test_names_a_file_cut_short(self, folder: MutantsFolder, path: str) -> None:
        file = folder.path / path
        file.write_bytes(file.read_bytes()[:-1])
        assert folder.baseline() == (
            f"{folder.path} holds a file mutmut did not write whole, so every mutant"
            " runs"
        )

    @pytest.mark.parametrize(
        ("commit", "reason"),
        [
            (None, "names no commit, so every mutant runs"),
            ("main", "names no commit by its SHA-1, so every mutant runs"),
        ],
    )
    def test_names_stats_without_a_commit_sha(
        self, folder: MutantsFolder, commit: str | None, reason: str
    ) -> None:
        stats = folder.path / MutantsFolder.STATS
        stats.write_text(json.dumps(dict(self.STATS) | {"git_commit": commit}))
        assert folder.baseline() == f"{stats} {reason}"

    def test_clears_the_folder(self, folder: MutantsFolder) -> None:
        folder.clear()
        folder.clear()
        assert not folder.path.exists()

    def test_keeps_only_the_stats_and_verdicts_emptying_each_to_run_again(
        self, folder: MutantsFolder
    ) -> None:
        baseline = folder.baseline()
        assert isinstance(baseline, Baseline)
        kept = folder.path / "src/pkg/b.py.meta"
        kept.write_text(json.dumps(dict(self.KEPT), indent=1))
        folder.keep(baseline, frozenset({"pkg.a.x_f", "pkg.c.x_i"}))
        files = sorted(
            str(path.relative_to(folder.path)) for path in folder.path.rglob("*")
        )
        verdicts = json.loads((folder.path / "src/pkg/a.py.meta").read_text())
        assert (files, verdicts, kept.read_text()) == (
            [
                "mutmut-stats.json",
                "src",
                "src/pkg",
                "src/pkg/a.py.meta",
                "src/pkg/b.py.meta",
            ],
            {
                "exit_code_by_key": {
                    "pkg.a.x_f__mutmut_1": None,
                    "pkg.a.x_f__mutmut_2": None,
                    "pkg.a.x_g__mutmut_1": None,
                    "pkg.a.x_g__mutmut_2": 1,
                    "pkg.a.x_g__mutmut_3": None,
                    "pkg.a.x_f__mutmut_x__mutmut_1": None,
                },
                "hash_by_function_name": {"x_f": "1a"},
            },
            json.dumps(dict(self.KEPT), indent=1),
        )

    @pytest.mark.usefixtures("interruptible")
    def test_leaves_the_verdicts_whole_and_no_partial_file_when_interrupted(
        self, folder: MutantsFolder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        baseline = folder.baseline()
        assert isinstance(baseline, Baseline)
        meta = folder.path / "src/pkg/a.py.meta"
        before = meta.read_bytes()
        partials: list[str] = []

        def interrupted(*_args: object) -> None:
            partials.extend(
                entry.name
                for entry in meta.parent.iterdir()
                if entry.name not in {"a.py.meta", "b.py.meta"}
            )
            signal.raise_signal(signal.SIGINT)

        monkeypatch.setattr(json, "dump", interrupted)
        with pytest.raises(KeyboardInterrupt):
            folder.keep(baseline, frozenset())
        assert (
            [re.fullmatch(r"tmp\w+\.partial", name) is not None for name in partials],
            sorted(entry.name for entry in meta.parent.iterdir()),
            meta.read_bytes(),
        ) == ([True], ["a.py.meta", "b.py.meta"], before)
