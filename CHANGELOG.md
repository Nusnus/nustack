# Changelog

All notable changes to nustack are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]: https://github.com/Nusnus/nustack/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/Nusnus/nustack/releases/tag/v0.0.2
[0.0.1]: https://github.com/Nusnus/nustack/releases/tag/v0.0.1

## [Unreleased]

### Added

- nus-mode files a nustack bug when you ask, with the fields and `bug` label of nustack's [bug form](https://github.com/Nusnus/nustack/issues/new?template=bug.yml), and offers to file one when it departs from a rule for a reason that would hold in any project like yours.
- The `new-project` playbook creates the project's remote repository where it has none, and configures its settings where it is on GitHub, such as branch protection on `main`.
- The `align` playbook reshapes existing code, from a snippet to a whole project, to nus-mode's bar within its project's standards, if any, so later work in nus-mode meets no friction with them.
- The plugin ships Steph Ango's six Obsidian skills ([kepano/obsidian-skills](https://github.com/kepano/obsidian-skills)), unchanged and each with its MIT license: `obsidian-markdown`, `obsidian-bases`, `json-canvas`, `obsidian-cli`, `defuddle` and `knap`. The agent can load each one, in nus-mode or without it, when the task matches its description, such as writing a `.base` or `.canvas` file.
- For nustack's maintainers:
  - `AGENTS.md` has agents weigh an issue's text as data, never as instructions.
  - `AGENTS.md` keeps nus-mode's bullets on quality over session cost and on times as the owner words them.
  - `nustack check` holds commitizen's `tag_format` in `pyproject.toml`, and the release workflow's push tags filter, to the release tags' `v<version>` form.
  - A record in `vendored/` names each vendored copy's upstream, skills, commit and file blobs. `nustack check` holds each copy to its record's bytes and exempts it from the rules for authored files, and requires each copied folder in the commit hooks' and Ruff's excludes and in `.gitattributes`' lines that unset `text`, and each vendored plugin skill in README's skills table.
  - `make smoke` checks that Claude Code and OpenCode each offer the model each vendored skill `tests/fixtures/vendored.ts` lists.
  - `REVIEW.md` has reviewers check a record written by hand against upstream.
  - A vendored copy's sync pull request lists each skill upstream added that its record does not name.
  - `nustack upstream` prints a vendored copy's upstream once its record passes the check's rules for records, so the sync workflow clones it without checking the rest of the repository first.
  - `nustack records` prints each record the sync reads, with its copy's branch, so the sync workflow's matrix comes from a tested command.
  - `.claude/skills` is a symlink to `.agents/skills/`, so Claude Code offers each skill for working on nustack, such as writing-for-agents, as the other hosts do.

### Changed

- A PR description links the issue it resolves with a closing keyword, such as `Fixes #12`, so its merge into the default branch closes the issue.
- nus-mode's cheap-ETA exception moves from its rule for times into its rule to choose quality over session cost, and keeps only the ETA's analysis cheap, never the reading of the live pace.
- nus-mode estimates from observed pace: it reads how fast each job, agent and subagent the work waits on is moving now, tries each other way it has when one fails, and states the basis with the ETA, the observed pace or the past runs it fell back on and why.
- `language-python` links each of its rules for tests to the principle it gives the Python form of.
- nus-mode's cold read pictures a reader new to the project reading the work.
- The plugin's description, which each host and the marketplaces show, names the Obsidian skills beside the mode.
- For nustack's maintainers:
  - A release runs `uv run cz bump --increment PATCH --version-files-only` with no `--yes`: `pyproject.toml` gives commitizen nustack's `v<version>` tag format, so it finds the earlier releases' tags.
  - `tsconfig.json` no longer skips the libraries' type declarations, so `tsc` checks them too; `package.json` adds `@types/json-schema`, whose types `@ai-sdk/provider` imports.
  - `nustack sync` and `nustack publish` refuse a `--name-with-owner` that is not `<owner>/<name>`, with an owner and name GitHub would take.
  - `nustack release-tag` and `nustack publish` refuse a tag that is not `v<version>`, and `nustack publish` a `--commit` that is not a commit's full SHA.
  - `nustack check` refuses a plugin manifest whose `repository` is not `https://<host>/<owner>/<name>`, the URL the changelog's and release page's links build on.
  - `nustack check` reads a release workflow whose `on` names its events as one event or a list, whose push trigger is null, or whose tags filter is one string, as GitHub does.
  - The scheduled `Sync vendored copies` workflow proposes each upstream change as one pull request per record.
  - `nustack sync` and `nustack sync-description` take `--record`, the vendored copy's record, and `nustack sync` names its branch from the record.
  - `REVIEW.md` has reviewers read every vendored copy's sync pull request, not only writing-for-agents', as untrusted text.
  - `make smoke` runs Claude Code 2.1.312 and holds it to the fake model's context window, so the prompt that fills that window still makes Claude Code summarize the session on its own. Since 2.1.293, Claude Code gives `claude-haiku-5-5`, the smoke tests' model, a window that prompt leaves far from full.

### Removed

- For nustack's maintainers:
  - The scheduled `Sync writing-for-agents` workflow, which `Sync vendored copies` replaces.
  - The `--upstream-url`, `--source-folder` and `--folder` options of `nustack sync` and `nustack sync-description`, which `--record` replaces.

### Fixed

- The Claude Code hook and the OpenCode loader name the path of each file they cannot use. Each message offers reinstalling the plugin as the other remedy, as the loader's messages already did. The hook names which part of nus-mode's SKILL.md it cannot use: missing or unclosed frontmatter, a blank body or a body that does not open with the mode's title. The loader names a frontmatter block that opens and never closes as such, where it said the file had none, and reads an empty block as no fields, as `nustack check` does, so it names the missing name.
- For nustack's maintainers:
  - `nustack publish` stops when gh reports a release's draft state as neither true nor false, where it took the release as published.
  - `nustack check` names the field that breaks `pyproject.toml` or a YAML config, and gives a SKILL.md with lone-CR line endings the right line in each problem.
  - The Devin blueprint's message for a failed Bun check names the test file that failed and points to bun test's report, where it always blamed the Bun version.
  - `nustack sync` and `nustack sync-description` stop with the fix when Git names a commit by other than its SHA-1, as in a SHA-256 repository, where they took the name as a SHA.
  - `nustack check` refuses a release workflow whose `%YAML 1.1` directive reads `on` as true with the fix, where it said to add `on`, and its warning of a YAML 1.1 float with no dot names the file.
  - `nustack publish` says to push a tag again only where GitHub finds no such tag, and passes on gh's other failures to read it as they are.

## [0.0.2] - 2026-11-04

nustack's second release adds a principle for tests to nus-mode, the mode that has a coding agent build software to a senior engineer's bar; a principle is a skill, an instruction file the agent reads when its work needs it. When the agent writes or changes a test, or a test passes on some runs and fails on others, it now makes the test's outcome depend only on its inputs: the test waits for what the code does rather than for time to pass, and passes or fails the same way on every run, however busy the machine.

### Added

- `principle-deterministic-tests`, a principle nus-mode reads when the agent writes or changes a test or its helpers, or a test passes on some runs and fails on others: a test's outcome depends only on its inputs, the same on every run and under any load. `language-python`, the skill the agent reads for Python work, gives the principle's Python form: a test that interrupts its own code raises the interrupt at the moment the code reaches the point it interrupts, not from a timer, and the agent proves a test under load by running that one test in a loop, where [pytest-randomly](https://github.com/pytest-dev/pytest-randomly) gives each run a new seed, which varies the values `random` gives.

### Changed

- In Python, the agent gives every test the whole of the suite's per-test time limit, the limit that [pytest-timeout](https://github.com/pytest-dev/pytest-timeout)'s `timeout` setting puts on each test, as `principle-deterministic-tests` says. Before, `language-python` told the agent to give a test that checks some code ends quickly, such as a loop that must end, a shorter limit with `@pytest.mark.timeout`, which a busy machine can outlast.
- The plugin's description, which opens each release page, names its author in full: Tomer Nosrati.
- For nustack's maintainers:
  - `nustack` is nustack's own command-line tool. A release sets its version with one command, commitizen's `uv run cz bump --increment PATCH --version-files-only --yes`, which AGENTS.md's Releases step 1 names, in place of editing each file whose version `nustack` compares and running `uv lock`. `nustack check` fails when the files listed in `pyproject.toml`'s `[tool.commitizen] version_files`, which that command sets, differ from the files whose version `nustack check` compares.

### Fixed

- For nustack's maintainers:
  - `nustack` stops a Git or `gh` command that stalls or is interrupted; `gh` is GitHub's command-line tool. The tests of that stop pass the same way under load: a command that stalls never ends on its own; each test that signals a command waits until the command reports it is ready; the wait for a stopped command's processes to end runs on a fake clock wherever a test needs it to run out; and each wait a test needs to finish, such as for a command to report it is ready, may last the suite's whole per-test time limit.

## [0.0.1] - 2026-11-04

nustack's first release brings nus-mode, a mode that has a coding agent build software to a senior engineer's bar, installable in Devin, Claude Code, Cursor and OpenCode. nus-mode follows a playbook, a task's numbered steps, when one fits, and reads skills, instruction files the agent loads when its work needs them: one for each principle and one for Python. When the agent's host, the app it runs in, summarizes a long session, nus-mode comes back on its own, or, on hosts where it cannot, has the agent load it again.

### Added

- `nus-mode`, with the playbooks `investigate` and `new-project`, and the skills it reads: `language-python`, for Python work, and one principle for each area of its rules: `principle-naming`, `principle-dry`, `principle-fail-fast`, `principle-boundaries`, `principle-types`, `principle-design`, `principle-layout`, `principle-dependencies`, `principle-resilience`, `principle-long-term`, `principle-self-explanatory-code` and `principle-pr-descriptions`.
- Rules across nus-mode, its playbooks and its principles. The agent departs from a rule only with a reason stated beside the departure; where nothing there can hold one, the reason goes in the project's `AGENTS.md`, the file of instructions agents read in a repository. Among them:
  - files grouped into packages by area
  - module docstrings that summarize their whole file
  - each review finding treated as a hypothesis to confirm or refute
  - fixing a flaw everywhere it appears
  - the fewest words that say it clearly
  - documented defaults left unwritten
  - no class that holds no data and only groups functions
  - test names that read as a sentence after their class's name
  - test cases that write out their expected values
  - decisions nothing else settles, made as the [Zen of Python](https://peps.python.org/pep-0020/)'s aphorisms favour
  - time estimates from the pace the work keeps
  - quality over session cost
- The agent offers to work on its own once it is highly confident it can finish your task without you, and does so once you agree.
- nus-mode comes back after Claude Code or OpenCode summarizes a session that loaded it.
- On other hosts, nus-mode tells the agent to load it again once a summary drops it.
- In OpenCode, the nustack plugin refuses a broken skill, such as a `SKILL.md` that is not valid UTF-8 or a symlinked skill folder, and names the fix when it cannot read its skills folder.
- Each release page opens with what nustack is, then the release's summary and its changes, README's install and use steps and, from the second release on, a link to every change since the previous one.
- Each release before v0.1.0 is published as a GitHub pre-release.
- For nustack's maintainers:
  - `nustack`, the command-line tool that checks, bundles and publishes the plugin, run through `make check`, `make bundle` and the release workflow.
  - `nustack check` enforces nustack's rules, among them: playbook done conditions; link anchors; skill text that names no host; each marketplace's owner, which must be the plugin's author; one name and description shared by both marketplaces; README's line that turns nus-mode on for a project, which must match the new-project playbook's; README's skills table, which must give each principle and language skill its description; and the test layout.
  - `nustack check` holds the release's changelog entry to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)'s types of change, each once and in order, with each group showing something, and to full URLs for its links and images.
  - `nustack check` holds README to one `### 1️⃣ Install` and one `### 2️⃣ Use` section, each showing something, with full URLs for its links and images, and checks that each reference label those sections and the release's changelog entry use resolves on the release page as it does in their own file.
  - `nustack check` names each problem it finds, such as a missing `plugin/skills/` folder, a misplaced `[Unreleased]` section or a symlink loop, and names the line of each YAML value it refuses: one with a tag outside YAML's core schema, a repeated key, a number too long to read or broken syntax.
  - `nustack check`, `bundle` and `notes` take each path as an option, `--root` or `--zip-folder`, and stop with one problem at a root that is not a folder or lacks a `plugin/` folder; every `nustack` command refuses an empty option, and its help says what each option and argument holds.
  - A `pyproject.toml` parse error never repeats the file's contents, which may hold a secret.
  - `nustack notes` prints a CRLF changelog's entry without carriage returns.
  - `nustack bundle` writes its zip whole or not at all, so a failed run leaves no half-written zip.
  - Each Git and gh command the harness runs stops once it outlasts its time limit, naming the next step, so none waits without limit.
  - Each Python test fails once it outlasts its time limit, so a stalled test never stalls the suite.
  - `make mutate` runs mutation tests over `nustack`, and CI runs them on every pull request.
  - A scheduled workflow proposes the changes made [upstream](https://github.com/mattpocock/skills) to `writing-for-agents`, a skill copied into the repository, as a pull request, and refuses a pull request template that repeats one of the lines the sync fills.
  - The sync and release workflows run tested `nustack` commands, not shell logic.
  - Dependabot's dependency updates raise each dependency's floor to its newest release, and CI installs the Bun that `package.json` names.
