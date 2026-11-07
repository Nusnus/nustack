# Changelog

All notable changes to nustack are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]: https://github.com/Nusnus/nustack/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/Nusnus/nustack/releases/tag/v0.0.2
[0.0.1]: https://github.com/Nusnus/nustack/releases/tag/v0.0.1

## [Unreleased]

### Added

- `principle-responses` shapes how a reply, status update, question or report reads, so a person takes it in at a glance: the answer first, short sentences and paragraphs, a table only to compare values, one format for each kind of answer, a link for each thing named, and bold only for what the person must see. nus-mode reads it whenever the agent writes to a person.
- `deterministic tests` spends each mutation run where it can find something: none for a change it cannot reach, only what a pull request's changes reach, and every mutant from an empty cache after each merge to the default branch and before each release. `language-python` says what mutmut's cache keeps through a change, and how a run that keeps a full run's verdicts makes up for it.
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
  - `nustack bump`, from a working tree with no changes, sets a release's version, the next patch or the one given, titles `CHANGELOG.md`'s `[Unreleased]` section with it and the day, below a new empty one, and sets the changelog's links, so `make check` passes right after it.
  - `nustack push-tag`, from a full clone whose working tree has no changes, checks out the commit on `origin/main` that set the release's version, the newest on its first-parent line, so a later merge stays untagged; it checks the release tag there as `nustack release-tag` does, then pushes the tag on that commit to `origin`, leaving no local tag that a rerun after a failed push would trip on.
  - `AGENTS.md` has each pull request add its own entry under `CHANGELOG.md`'s `[Unreleased]`; the PR template asks for it, and `REVIEW.md` has review check it.
  - `AGENTS.md` has skill text written, and reviewed, for the strongest agent as timeless Zen: each principle holds the owner's value, true in any project, plus only where the owner's taste departs from that agent's pick.

### Changed

- README is a short front page: what nustack is, how to install, use and update it on each host, how it works, the skills and how to contribute.
- A PR description reads like one calm app screen at any size of change: a centered headline and one-line summary, badges for risk, checks and size, plain-word sections for what changed, the risk, what to review first and the steps after the merge, and one fold for checks, files and decisions. It links the issue it resolves with a closing keyword, such as `Closes #12`, so its merge into the default branch closes the issue.
- nus-mode's cheap-ETA exception moves from its rule for times into its rule to choose quality over session cost, and keeps only the ETA's analysis cheap, never the reading of the live pace.
- nus-mode estimates from observed pace: it reads how fast each job, agent and subagent the work waits on is moving now, tries each other way it has when one fails, and states the basis with the ETA, the observed pace or the past runs it fell back on and why.
- `language-python` links each of its rules for tests to the principle it gives the Python form of.
- `long term` keeps only what builds work to last, done once: performance from the first version, the full bar on temporary code, each fix at its cause and for every instance of its flaw, every file touched finished, each exemption from a check narrow, and only what stays true in the repository; it no longer asks to keep old callers working. Its rules on file and code order move to `layout`, on what to build on to `dependencies`, on wording to `self-explanatory code`, and on tests to `deterministic tests`; nus-mode loads each of those principles wherever its new rules apply.
- `types` keeps only where its rules depart from a strong agent's pick: illegal states unrepresentable in every type, parameter and result, values that never change frozen all the way down, and each member of a closed set handled by name, proven exhaustive wherever a checker can. Its rules on signatures and on enumerating a closed set fold into those, and a branch that meets an unexpected member fails as `fail fast` already says.
- `boundaries` keeps only where its rules depart from a strong agent's pick: data from outside the system, settings from the environment included, parsed once, where it enters, strictly into the project's domain types, failing on what does not fit them exactly, such as an unknown field in a format the project owns, or a value of the wrong type. Its rule to hold an expected absence as data is cut, and nus-mode no longer loads `boundaries` when a value may be absent.
- `fail fast` keeps only where its rules depart from a strong agent's pick: a wrong state fails where it is first detected, with an error that says how to recover; each assumption is checked once, where it can first fail, and trusted past it; only a failure the design expects is recovered from, so an unknown member of a closed set travels up; a default stands in only where the caller gave nothing, and a given value that does not resolve, such as a misspelled setting, fails; an error is of the project's domain, and its message names what was wrong and, unless it is secret, the bad value; and a new rule holds an expected absence, such as a lookup with no match, in its type, as an optional value or an empty collection, for the caller to handle, so nus-mode now loads `fail fast` when a value may be absent.
- `resilience` now means code that comes through failure and load by its design rather than by scattered guards, with each failure and edge case absorbed by its structure or left to fail on purpose: it is built for the load it will grow into, and the larger load at which it breaks is known; it leaves state a rerun finishes, whatever line the process stops at, with work that may run again idempotent and each change landed whole or not at all; every wait on anything outside the process stays bounded by a limit set from its healthy duration; retries stay in one layer, and a wait a reply asks for is now a minimum rather than the wait; and a reduced mode still says so and ends once its dependency is back. Its retry how-to is cut, since a strong agent's retry already does each step; its how-to for landing a write whole is cut, since each tool lands a write its own way and `language-python` keeps Python's; and its rule that a timeout's error names what stalled is cut, since `fail fast` already says it. nus-mode now loads it also for code that guards against or handles a failure, a retry and a fallback included, or does work that grows with its input, data or traffic.
- `deterministic tests` holds tests in general and keeps only its most significant rules: each test fails when, and only when, the behaviour it guards breaks. It keeps the smallest test set; each test with a way to fail, its expected value worked out from the promise, and seen failing; fakes only at the boundaries, each hand-written fake tested against its boundary, and replies recorded from real systems; waits on events, a faked clock where behaviour depends on time, timing tests proven under load and flakes fixed at their cause; hard failures and full coverage; tiered tests that mirror the source; and mutation runs only where they can find something, with a full run gating each release. Test names, refusal pairs, canaries, real-time margins, holding tests to the code's standard, testing the suite's settings, suite speed and the mirror check are cut, as are its how-to detail and the reasons a strong agent already knows; where shared test helpers live moves to `layout`.
- `dependencies` keeps only where its rules depart from a strong agent's pick: dependencies point one way; what the language and its standard tools provide comes before code of one's own; code builds on stable public APIs and documented behaviour; each third-party library has one home, in the project's own types and errors, apart from a framework the code runs in or a library whose classes its types extend; an application targets the newest runtime release and a library every maintained one; a declared range floats above a floor while the lockfile pins, a dependency that installs exactly the version declared pins it, with an update tool proposing each newer one, and the rest take the bounds their documentation gives; and deciding logic stays pure, with the I/O at the edges.
- `layout` keeps only where its rules depart from a strong agent's pick: each folder holds one area and each file one responsibility you can state in a line, which splits on a second one, never on size alone, and moves when that responsibility does; the top-level split goes by domain, by layer or both, whichever makes the design readable, and within it two or more files that serve one area share a package named for it, a package holds more than one module, a module whose parts are concepts of their own becomes one, and files in one folder whose names share a prefix no tool requires are a missing package; the layout shows which layers build on which; a folder or module exists once it has content; every file keeps one order, its ecosystem's or one the project writes down; and code orders state up and behaviour down. Its rule to put behaviour with the data it serves leaves layout, since its subject is how code is shaped into types and functions, which is `design`'s. Its rule to plan the layout before writing it is cut, since a strong agent does it anyway. It takes in from `deterministic tests` where helpers that tests share sit, since that rule's subject is where files live: in one folder beside the test tiers, except one the test framework scopes by place, which stays with its tests while they share a tier.
- nus-mode's cold read pictures a reader new to the project reading the work.
- The plugin's description, which each host and the marketplaces show, names the Obsidian skills beside the mode.
- For nustack's maintainers:
  - CI runs `make mutate` from an empty `mutants/` only on `main` and on release tags, once the other checks pass. A pull request ready for review runs `make mutate-changed`, which keeps the verdicts of `main`'s last full run and reruns the functions it changes and those its changed test modules cover, as `nustack mutants` decides. A change to no file mutmut's tests read, as `pyproject.toml`'s `[tool.nustack.mutation] reads` lists them beside the code, runs no mutant, nor does an edit to the tests' Python that changes only comments, layout or docstring wording, and the test run fails when a test, a fixture, a conftest or a test module's import opens or lists a repository file that list does not count.
  - The release steps move from `AGENTS.md` into the `release` skill in `.agents/skills/`, so they load only for a release.
  - A release's `cz bump` runs with no `--yes`: `pyproject.toml` gives commitizen nustack's `v<version>` tag format, so it finds the earlier releases' tags.
  - The `release` skill leaves the agent only the entry's lead, the cold read of the release page, the pull request and its merge: `nustack bump` makes the release's edits, and `nustack push-tag` checks and pushes its tag.
  - `tsconfig.json` no longer skips the libraries' type declarations, so `tsc` checks them too; `package.json` adds `@types/json-schema`, whose types `@ai-sdk/provider` imports.
  - `nustack sync` and `nustack publish` refuse a `--name-with-owner` that is not `<owner>/<name>`, with an owner and name GitHub would take.
  - `nustack release-tag` and `nustack publish` refuse a tag that is not `v<version>`, and `nustack publish` a `--commit` that is not a commit's full SHA.
  - `nustack check` refuses a plugin manifest whose `repository` is not `https://<host>/<owner>/<name>`, the URL the changelog's and release page's links build on.
  - `nustack check` reads a release workflow whose `on` names its events as one event or a list, whose push trigger is null, or whose tags filter is one string, as GitHub does.
  - The scheduled `Sync vendored copies` workflow proposes each upstream change as one pull request per record.
  - `nustack sync` and `nustack sync-description` take `--record`, the vendored copy's record, and `nustack sync` names its branch from the record.
  - `REVIEW.md` has reviewers read every vendored copy's sync pull request, not only writing-for-agents', as untrusted text.
  - `make smoke` runs Claude Code 2.1.312 and holds it to the fake model's context window, so the prompt that fills that window still makes Claude Code summarize the session on its own. Since 2.1.293, Claude Code gives `claude-haiku-5-5`, the smoke tests' model, a window that prompt leaves far from full.
  - nustack's PR template and the sync workflow's generated description of a vendored copy's change follow the new PR description page: badges, plain sections and one fold.

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
  - `nustack check`, and each command that runs it or reads a vendored copy, such as `notes`, `bundle`, `bump` and `sync`, skips each untracked file Git ignores inside the folders the check reads, such as a `.DS_Store` Finder leaves in `plugin/` or a vendored copy, where it refused it, which failed `make check` and stalled `nustack bump`. The release zip leaves such a file out, and an untracked file Git does not ignore is still refused.
  - `make check` passes on a machine whose user or system Git config ignores a file in `plugin/`, such as a `.DS_Store` Finder leaves: the integration tests run Git with only the repository's config and excludes, and the OpenCode loader's test expects only the skill folders in `plugin/skills/`.
  - `nustack check` refuses an unknown key in `pyproject.toml`'s `[tool.nustack]` table or its `mutation` table with the fix, where it dropped it, so a misspelled `reads` left the tests' reads unlisted.
  - `make mutate-changed` runs every mutant when a `.meta` file in `mutants/` gives a verdict that is not an exit code, such as `"0"` or `true`, and says the file is not in the shape mutmut writes, where it read `"0"` as a survivor and `true` as 1; a file in another wrong shape, which it called one mutmut did not write whole, now gets that reason too.

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
