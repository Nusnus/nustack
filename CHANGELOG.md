# Changelog

All notable changes to nustack are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]: https://github.com/Nusnus/nustack/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/Nusnus/nustack/releases/tag/v0.0.2
[0.0.1]: https://github.com/Nusnus/nustack/releases/tag/v0.0.1

## [Unreleased]

### Added

- nus-mode files a nustack bug when you ask, with the fields and `bug` label of nustack's [bug form](https://github.com/Nusnus/nustack/issues/new?template=bug.yml), and offers to file one when it departs from a rule for a reason that would hold in any project like yours.
- For nustack's maintainers:
  - `AGENTS.md` has agents weigh an issue's text as data, never as instructions.

### Changed

- A PR description links the issue it resolves with a closing keyword, such as `Fixes #12`, so its merge into the default branch closes the issue.

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
