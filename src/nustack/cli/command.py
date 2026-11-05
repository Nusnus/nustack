"""The `nustack` command that the make targets, the workflows and a person run.

Its commands check the repository, bundle the plugin, print the plugin version's release
page, print for a person the description of a vendored copy's sync pull request, stage
the sync's copy and propose it in that pull request, check a release tag, and publish
its release. Each path is an option, no command takes an empty value, `nustack`
alone prints the help, and `nustack --version` prints the installed version. A command
that fails prints its Problems and exits with a failing status, never a traceback.
"""

import json
import sys
from importlib.metadata import version
from pathlib import Path
from pathlib import PurePosixPath
from typing import Annotated
from typing import NoReturn
from typing import assert_never

import typer

from nustack.cli import parameter
from nustack.git import Git
from nustack.git import GitError
from nustack.github.gh import GitHub
from nustack.github.gh import GitHubError
from nustack.github.name import NameWithOwner
from nustack.markdown.document import Document
from nustack.plugin.bundle import Bundle
from nustack.problem import Problem
from nustack.record import CopyRecord
from nustack.release.publication import Publication
from nustack.release.tag import Tag
from nustack.repository.disk import Disk
from nustack.repository.repository import Release
from nustack.repository.repository import Repository
from nustack.rule import Rule
from nustack.sync.description import SyncDescription
from nustack.sync.description import SyncLinks
from nustack.sync.description import SyncTemplate
from nustack.sync.git import CopyGit
from nustack.sync.proposal import Proposal
from nustack.sync.tree import CopyTree
from nustack.tree import Missing
from nustack.tree import NotAFolder
from nustack.tree import Symlink
from nustack.tree import Unopened
lazy from nustack.sha import Sha
lazy from nustack.sync.change import FileChange
lazy from nustack.sync.history import History

# Module constants, since the module holds commands and no type: the commands and
# their options share them.
# Package metadata matches a distribution's name in any case, so no test tells
# "nustack" from another casing, and mutmut leaves module-level values alone:
# https://peps.python.org/pep-0503/#normalized-names
DISTRIBUTION = "nustack"

ZIP_FOLDER = Path("dist")

app = typer.Typer(
    help="Check, bundle and release the nustack plugin, and sync its vendored copies.",
    context_settings={"help_option_names": ["-h", "--help"]},
)


# Git names the paths in a tree as text, so a record's path stays str.
# Inside Annotated, Typer reads an Option's default as its name, and a
# default_factory there shows the class, not `.`, in help, so each command writes
# its own `Path()` default.
# https://github.com/fastapi/typer/blob/0.27.3/typer/utils.py#L140-L149
RootOption = Annotated[
    Path, typer.Option(parser=parameter.path, help="The nustack repository's folder.")
]
NameWithOwnerOption = Annotated[
    NameWithOwner,
    typer.Option(
        parser=parameter.name_with_owner,
        metavar="<owner>/<name>",
        help="The GitHub repository.",
    ),
]
TagArgument = Annotated[
    Tag, typer.Argument(parser=parameter.tag, help="The release's tag.")
]
RunOption = Annotated[
    str,
    typer.Option(parser=parameter.text, help="The URL of the workflow run that syncs."),
]
ChecksOption = Annotated[
    str,
    typer.Option(parser=parameter.text, help="The URL of the sync branch's checks."),
]
CloneOption = Annotated[
    Path, typer.Option(parser=parameter.path, help="Upstream's clone.")
]
RecordOption = Annotated[
    str,
    typer.Option(
        parser=parameter.path_text,
        metavar="<path>",
        help="The copy's record, by its path from the repository's folder.",
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
    zip_folder: Annotated[
        Path,
        typer.Option(parser=parameter.path, help="The folder to write the zip into."),
    ] = ZIP_FOLDER,
) -> None:
    release = checked_release(root)
    match Bundle(release.tree, release.manifest).write(zip_folder):
        case Problem() as problem:
            fail([problem])
        case zip_path:
            print(zip_path)


@app.command(help="Print the plugin version's release page, after a clean check.")
def notes(root: RootOption = Path()) -> None:
    print(checked_release(root).notes)


@app.command(
    help="Print each record the sync reads, with its copy's branch, as a JSON list."
)
def records(root: RootOption = Path()) -> None:
    root = root.resolve()
    paths = sorted(
        relative
        for path in (root / CopyRecord.FOLDER).glob(f"*{CopyRecord.SUFFIX}")
        if CopyRecord.read_by_sync(relative := PurePosixPath(path.relative_to(root)))
    )
    if not paths:
        fail(
            [
                Problem(
                    root / CopyRecord.FOLDER,
                    "holds no record the sync reads; add one as AGENTS.md says",
                )
            ]
        )
    print(
        json.dumps(
            [{"record": str(path), "branch": CopyRecord.branch(path)} for path in paths]
        )
    )


@app.command(
    help="Print a vendored copy's upstream, once its record passes the check's rules"
    " for records."
)
def upstream(*, record: RecordOption, root: RootOption = Path()) -> None:
    print(read_record(root.resolve(), record).upstream)


@app.command(help="Print the description of a vendored copy's sync pull request.")
def sync_description(
    *,
    run: RunOption,
    checks: ChecksOption,
    clone: CloneOption,
    record: RecordOption,
    root: RootOption = Path(),
) -> None:
    checkout_git, upstream_git = CopyGit(root.resolve()), CopyGit(clone.resolve())
    copy_record = read_record(checkout_git.root, record)
    template = sync_template(checkout_git.root)
    try:
        new_skills = upstream_git.new_skills(upstream_git.head, copy_record)
        if problems := upstream_git.head_tree(copy_record).problems(
            checkout_git.root, copy_record, new_skills
        ):
            fail(problems)
        history = upstream_git.history(upstream_git.head, copy_record)
    except GitError as error:
        fail([error.problem])
    if not copy_changes(checkout_git, upstream_git, copy_record, history):
        print("The copy matches upstream; the sync proposes nothing.")
        return
    links = SyncLinks(run, checks)
    print(
        described(
            links,
            template,
            checkout_git=checkout_git,
            upstream_git=upstream_git,
            record=copy_record,
            history=history,
            new_skills=new_skills,
        ),
        end="",
    )


@app.command(
    help="Stage upstream's newest version of a vendored copy, and open, update or"
    " close the pull request that proposes it."
)
# https://github.com/fastapi/typer/blob/0.27.3/typer/main.py#L1373-L1389
def sync(  # noqa: PLR0913 -- Typer reads each option from a parameter of its own
    *,
    run: RunOption,
    checks: ChecksOption,
    clone: CloneOption,
    record: RecordOption,
    remote_url: Annotated[
        str, typer.Option(parser=parameter.text, help="The URL to push the branch to.")
    ],
    name_with_owner: NameWithOwnerOption,
    root: RootOption = Path(),
) -> None:
    links = SyncLinks(run, checks)
    checkout_git, upstream_git = CopyGit(root.resolve()), CopyGit(clone.resolve())
    copy_record = read_record(checkout_git.root, record)
    template = sync_template(checkout_git.root)
    try:
        new_skills = upstream_git.new_skills(upstream_git.head, copy_record)
        tree = upstream_git.head_tree(copy_record)
        if problems := tree.problems(checkout_git.root, copy_record, new_skills):
            fail(problems)
        history = upstream_git.history(upstream_git.head, copy_record)
        checkout_git.stage(record, copy_record, history.copied, upstream_git, tree)
        staged = checkout_git.staged()
        body = (
            described(
                links,
                template,
                checkout_git=checkout_git,
                upstream_git=upstream_git,
                record=copy_record,
                history=history,
                new_skills=new_skills,
            )
            if staged
            else ""
        )
        github = GitHub(name_with_owner)
        branch = CopyRecord.branch(PurePosixPath(record))
        outcome = Proposal(github.default_branch(), branch, remote_url).propose(
            PurePosixPath(record).stem, copy_record, checkout_git, github, body
        )
    except GitError as error:
        fail([error.problem])
    except GitHubError as error:
        fail([Problem(str(name_with_owner), error.what)])
    match outcome:
        case Problem() as problem:
            fail([problem])
        case message:
            print(message)
    # A staged copy's description lists the new skills itself.
    if new_skills and not staged:
        print(
            "Upstream holds skills the record does not list:"
            f" {', '.join(new_skills)}; add each one the copy should hold to the"
            f" skills of {record}. Each run names them again until a sync records a"
            " commit that holds them."
        )


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
    if problems := tag.problems(release.manifest.version, on_main=on_main):
        fail(problems)
    print(f"{tag} is on main and names the plugin version")


@app.command(
    help="Publish the GitHub release for a tag from the zip and notes CI built."
)
def publish(
    tag: TagArgument,
    *,
    commit: Annotated[
        Sha,
        typer.Option(
            parser=parameter.commit, help="The commit CI built the release from."
        ),
    ],
    name_with_owner: NameWithOwnerOption,
    zip_folder: Annotated[
        Path,
        typer.Option(
            parser=parameter.path,
            help="The folder that holds the zip and notes.md CI built.",
        ),
    ] = ZIP_FOLDER,
) -> None:
    match Publication(tag, commit, zip_folder).publish(GitHub(name_with_owner)):
        case Problem() as problem:
            fail([problem])
        case message:
            print(message)


# Git stages a path only as it names it, so a record's path is passed plain.
def read_record(root: Path, path: str) -> CopyRecord:
    if PurePosixPath(path).as_posix() != path:
        fail(
            [
                Problem(
                    root / path,
                    "is no plain path; pass it as vendored/<copy>.json, with no ."
                    " part, no // and no / at either end",
                )
            ]
        )
    record = CopyRecord.reading(
        root,
        PurePosixPath(path),
        Disk.read_record(root / path),
        CopyRecord.MISSING,
    )
    if isinstance(record, Problem):
        fail([record])
    vendored = Repository(Disk(root).snapshot()).vendored
    if problems := vendored.record_problems(PurePosixPath(path)):
        fail(problems)
    return record


def sync_template(root: Path) -> SyncTemplate:
    template_path = root / SyncTemplate.PATH
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
    return template


def described(  # noqa: PLR0913 -- the sync's links, template, clones, copy, skills
    links: SyncLinks,
    template: SyncTemplate,
    *,
    checkout_git: CopyGit,
    upstream_git: CopyGit,
    record: CopyRecord,
    history: History,
    new_skills: tuple[str, ...],
) -> str:
    changes = copy_changes(checkout_git, upstream_git, record, history)
    description = SyncDescription(links, record, history, changes, new_skills)
    body = template.fill(description)
    if problems := template.size_problems(body, checkout_git.root / record.folder):
        fail(problems)
    return body


def copy_changes(
    checkout_git: CopyGit, upstream_git: CopyGit, record: CopyRecord, history: History
) -> tuple[FileChange, ...]:
    try:
        base = checkout_git.tree("HEAD", map(str, record.skill_folders))
        proposed = upstream_git.tree(
            str(history.copied), record.upstream_folders, CopyTree.LICENSE
        )
        return checkout_git.changes(base, upstream_git, proposed)
    except GitError as error:
        fail([error.problem])


def checked_release(root: Path) -> Release:
    root = root.resolve()
    match Disk.unusable_root(root):
        case None:
            pass
        case Unopened(reason=reason):
            fail([Problem(root, reason)])
        case Symlink() | NotAFolder() | Missing():
            fail(
                [
                    Problem(
                        root,
                        f"{Problem.NOT_A_FOLDER}; pass the repository's folder as"
                        " --root",
                    )
                ]
            )
        case unexpected:
            assert_never(unexpected)
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
        print(version(DISTRIBUTION))
        raise typer.Exit
