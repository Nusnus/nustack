"""The `nustack` command, the harness's entry point."""

import sys
from pathlib import Path

from cyclopts import App

from nustack.bundle import Bundle
from nustack.repository import Repository

app = App(help="Check and bundle the nustack plugin.")


@app.command(help="Hold the plugin to the rules in AGENTS.md.")
def check(root: Path = Path()) -> None:
    exit_on_problems(Repository(root.resolve()))
    print("nustack check: no problems")


@app.command(help="Build the zip that hosts install from a file, after a clean check.")
def bundle(root: Path = Path(), out: Path = Path("dist")) -> None:
    repository = Repository(root.resolve())
    exit_on_problems(repository)
    print(Bundle(repository.plugin).write(out))


@app.command(help="Print the plugin version's changelog entry, after a clean check.")
def notes(root: Path = Path()) -> None:
    repository = Repository(root.resolve())
    exit_on_problems(repository)
    print(repository.release_notes())


def exit_on_problems(repository: Repository) -> None:
    problems = repository.problems()
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        sys.exit(1)
