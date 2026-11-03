"""The `nustack` command that the make targets and the workflows run.

Its commands check the repository, bundle the plugin, print the release notes,
check a release tag and publish its release, and stage the writing-for-agents sync's
copy and propose it in a pull request. Each path is an option, no command takes an
empty value, and `nustack` alone prints the help. A command that fails prints its
Problems and exits with a failing status, never a traceback.
"""

import sys
from importlib.metadata import version
from pathlib import Path
from typing import Annotated
from typing import NoReturn

import typer

from nustack.cli.parameter import path
from nustack.cli.parameter import path_text
from nustack.cli.parameter import text
from nustack.git import Git
from nustack.git import GitError
from nustack.github import GitHub
from nustack.github import GitHubError
from nustack.markdown.document import Document
from nustack.plugin.bundle import Bundle
from nustack.release import Publication
from nustack.release import Tag
from nustack.repository.disk import Disk
from nustack.repository.repository import Release
from nustack.repository.repository import Repository
from nustack.rule import Rule
from nustack.sync.description import SyncCopy
from nustack.sync.description import SyncDescription
from nustack.sync.description import SyncLinks
from nustack.sync.description import SyncTemplate
from nustack.sync.git import CopyGit
from nustack.sync.proposal import Proposal
from nustack.sync.tree import CopyTree
from nustack.tree import Unopened
lazy from nustack.problem import Problem

app = typer.Typer(
    help="Check, bundle and release the nustack plugin, and sync its vendored"
    " writing-for-agents copy.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


# Git names the paths in a tree as text, so source and folder stay str.
# Inside Annotated, Typer reads an Option's default as its name, and a
# default_factory there shows the class, not `.`, in help, so each command writes
# its own `Path()` default.
# https://github.com/fastapi/typer/blob/0.27.3/typer/utils.py#L140-L149
RootOption = Annotated[
    Path, typer.Option(parser=path, help="The nustack repository's folder.")
]
RepositoryOption = Annotated[
    str, typer.Option(parser=text, help="The GitHub repository, as <owner>/<name>.")
]
TagArgument = Annotated[str, typer.Argument(parser=text, help="The release's tag.")]
UpstreamOption = Annotated[
    str, typer.Option(parser=text, help="The upstream repository's URL.")
]
RunOption = Annotated[
    str, typer.Option(parser=text, help="The URL of the workflow run that syncs.")
]
ChecksOption = Annotated[
    str, typer.Option(parser=text, help="The URL of the sync branch's checks.")
]
CloneOption = Annotated[Path, typer.Option(parser=path, help="Upstream's clone.")]
SourceOption = Annotated[
    str,
    typer.Option(
        parser=path_text, metavar="<path>", help="The skill's folder in upstream."
    ),
]
FolderOption = Annotated[
    str,
    typer.Option(
        parser=path_text, metavar="<path>", help="The copy's folder in the repository."
    ),
]


@app.callback(invoke_without_command=True)
def nustack(
    context: typer.Context,
    *,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=print_version,
            is_eager=True,
            help="Print the installed nustack version.",
        ),
    ] = False,
) -> None:
    if context.invoked_subcommand is None:
        print(context.get_help())


@app.command(help=Rule.help())
def check(root: RootOption = Path()) -> None:
    checked_release(root)
    print("nustack check: no problems")


@app.command(help="Build the zip that hosts install from a file, after a clean check.")
def bundle(
    root: RootOption = Path(),
    out: Annotated[
        Path, typer.Option(parser=path, help="The folder to write the zip into.")
    ] = Path("dist"),
) -> None:
    release = checked_release(root)
    match Bundle(release.tree, release.manifest).write(out):
        case Problem() as problem:
            fail([problem])
        case zip_path:
            print(zip_path)


@app.command(help="Print the plugin version's changelog entry, after a clean check.")
def notes(root: RootOption = Path()) -> None:
    print(checked_release(root).notes)


@app.command(
    help="Print the description of the writing-for-agents sync's pull request."
)
def sync_description(  # noqa: PLR0913 -- one argument per option the sync workflow passes
    *,
    upstream: UpstreamOption,
    run: RunOption,
    checks: ChecksOption,
    clone: CloneOption,
    source: SourceOption,
    folder: FolderOption,
    root: RootOption = Path(),
) -> None:
    copy = SyncCopy(clone, source, folder)
    checkout, upstream_git = CopyGit(root.resolve()), CopyGit(clone.resolve())
    links = SyncLinks(upstream, run, checks)
    print(described(links, checkout, upstream_git, copy), end="")


@app.command(
    help="Stage upstream's writing-for-agents as the copy, and open, update or close"
    " the pull request that proposes it."
)
def sync(  # noqa: PLR0913 -- one argument per option the sync workflow passes
    *,
    upstream: UpstreamOption,
    run: RunOption,
    checks: ChecksOption,
    clone: CloneOption,
    source: SourceOption,
    folder: FolderOption,
    branch: Annotated[
        str, typer.Option(parser=text, help="The branch that proposes the copy.")
    ],
    remote: Annotated[
        str, typer.Option(parser=text, help="The URL to push the branch to.")
    ],
    repository: RepositoryOption,
    root: RootOption = Path(),
) -> None:
    links, copy = SyncLinks(upstream, run, checks), SyncCopy(clone, source, folder)
    checkout, upstream_git = CopyGit(root.resolve()), CopyGit(clone.resolve())
    try:
        tree = upstream_git.tree("HEAD", source, CopyTree.LICENSE)
        if problems := tree.problems(checkout.root / folder):
            fail(problems)
        checkout.stage(folder, upstream_git, tree)
        staged = checkout.staged()
        body = described(links, checkout, upstream_git, copy) if staged else ""
        github = GitHub(repository)
        outcome = Proposal(github.default_branch(), branch, remote).propose(
            upstream, checkout, github, body
        )
    except GitError as error:
        fail([error.problem])
    except GitHubError as error:
        fail([Problem(Path(repository), error.what)])
    match outcome:
        case Problem() as problem:
            fail([problem])
        case message:
            print(message)


@app.command(help="Check that a release tag is on main and names the plugin version.")
def release_tag(
    tag: TagArgument,
    root: RootOption = Path(),
) -> None:
    release = checked_release(root)
    try:
        on_main = Git(root.resolve()).is_ancestor("HEAD", "origin/main")
    except GitError as error:
        fail([error.problem])
    if problems := Tag(tag).problems(release.manifest.version, on_main=on_main):
        fail(problems)
    print(f"{tag} is on main and names the plugin version")


@app.command(
    help="Publish the GitHub release for a tag from the zip and notes CI built."
)
def publish(
    tag: TagArgument,
    *,
    commit: Annotated[
        str, typer.Option(parser=text, help="The commit CI built the release from.")
    ],
    repository: RepositoryOption,
    folder: Annotated[
        Path, typer.Option(parser=path, help="The folder that holds the zip CI built.")
    ] = Path("dist"),
) -> None:
    match Publication(tag, commit, folder).publish(GitHub(repository)):
        case Problem() as problem:
            fail([problem])
        case message:
            print(message)


def described(
    links: SyncLinks, checkout: CopyGit, upstream: CopyGit, copy: SyncCopy
) -> str:
    template_path = checkout.root / SyncTemplate.PATH
    match Document.of(
        template_path,
        Disk.read(template_path),
        "is missing; restore it, since the sync fills it",
    ):
        case Document(text=template_text):
            template = SyncTemplate(template_text)
        case problem:
            fail([problem])
    if problems := template.problems(template_path):
        fail(problems)
    try:
        base = checkout.tree("HEAD", copy.folder)
        history = upstream.history(upstream.head, copy.source, base)
        proposed = upstream.tree(history.copied, copy.source, CopyTree.LICENSE)
        changes = checkout.changes(base, upstream, proposed)
    except GitError as error:
        fail([error.problem])
    description = SyncDescription(links, copy.source, copy.folder, history, changes)
    body = template.fill(description)
    if problems := template.size_problems(body, checkout.root / copy.folder):
        fail(problems)
    return body


def checked_release(root: Path) -> Release:
    root = root.resolve()
    unusable = Disk.unusable_root(root)
    if isinstance(unusable, Unopened):
        fail([Problem(root, unusable.reason)])
    if unusable is not None:
        fail(
            [
                Problem(
                    root,
                    "is not a folder, so the check stops here; pass the"
                    " repository's folder as --root",
                )
            ]
        )
    release = Repository(Disk(root).snapshot()).release()
    if not isinstance(release, Release):
        fail(release)
    return release


def fail(problems: list[Problem]) -> NoReturn:
    for problem in problems:
        print(problem, file=sys.stderr)
    sys.exit(1)


def print_version(*, value: bool) -> None:
    if value:
        # Package metadata matches a distribution's name in any case, so no test
        # tells "nustack" from another casing:
        # https://peps.python.org/pep-0503/#normalized-names
        print(version("nustack"))  # pragma: no mutate
        raise typer.Exit
