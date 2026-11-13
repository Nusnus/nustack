# Changelog

All notable changes to nustack are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]: https://github.com/Nusnus/nustack/compare/v0.0.5...HEAD
[0.0.5]: https://github.com/Nusnus/nustack/releases/tag/v0.0.5
[0.0.4]: https://github.com/Nusnus/nustack/releases/tag/v0.0.4
[0.0.3]: https://github.com/Nusnus/nustack/releases/tag/v0.0.3
[0.0.2]: https://github.com/Nusnus/nustack/releases/tag/v0.0.2
[0.0.1]: https://github.com/Nusnus/nustack/releases/tag/v0.0.1

## [Unreleased]

### Changed

- Each skill vendored from obsidian-skills moves to a newer upstream commit.
- The [`new-project`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/new-project.md) playbook makes each instruction file a host reads instead of `AGENTS.md`, such as `CLAUDE.md`, a symlink to `AGENTS.md`; keeps the project's own skills in `.agents/skills/`; and makes each skills folder a host reads instead, such as `.claude/skills`, a symlink to it.
- Eleven principle skills are reworded to read more easily, with no change to what they ask: [`design`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-design/SKILL.md), [`dependencies`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-dependencies/SKILL.md) and [`PR descriptions`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-pr-descriptions/SKILL.md) list their cases and parts as sub-bullets, and `PR descriptions` moves its headings bullet below the two bullets it refers to; [`layout`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-layout/SKILL.md) links the test tiers it names; [`DRY`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-dry/SKILL.md) and [`responses`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-responses/SKILL.md) lose two clauses that added no rule; `PR descriptions` joins two clauses of its lead with a semicolon; [`self-explanatory code`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-self-explanatory-code/SKILL.md) sets a condition off between commas; and [`boundaries`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-boundaries/SKILL.md), [`deterministic tests`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-deterministic-tests/SKILL.md), [`long term`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-long-term/SKILL.md) and [`resilience`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-resilience/SKILL.md) split three sentences, reorder two and move one colon, with a comma in its old place.
- [`nus-mode`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/SKILL.md), its six playbooks and [`language-python`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/language-python/SKILL.md) are reworded to read more easily, with no change to what they ask: [`align`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/align.md), [`audit`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/audit.md), [`investigate`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/investigate.md), `new-project` and [`polish`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/polish.md) separate the parts of fifteen lists with semicolons or as sub-bullets; `new-project` reorders two sentences and `align` splits one; `align` and `new-project` set three conditions off between commas; `new-project` says "config" for "configuration" and "agreed" for "accepted"; `align` says "hand break" for "planted break", and `new-project` and [`small-project`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/small-project.md) say "broken by hand" for "broken on purpose"; `small-project` refers to `new-project`'s done conditions where it repeated two, and loses two reasons its opening gives; `nus-mode` and `align` move a comma and a colon inside their bold leads; and `language-python` ends three folder paths in a slash and says "CLIs" for "command-line interfaces".
- `README.md` links the friction point it names to nus-mode's goal, ends two folder paths in a slash and says "documentation" for "docs".
- For nustack's maintainers:
  - `CLAUDE.md` is a symlink to `AGENTS.md`.
  - The release script exits 2 on a command line it does not take, as the other scripts do.
  - `AGENTS.md`, `REVIEW.md`, the release skill and the PR template are reworded to read more easily, with no change to what they ask: five names gain links; `AGENTS.md` gives its note on Bun's version beside the blueprint the note names, and its note on `@types/json-schema` after the sentence on CI; `AGENTS.md` says "bug form" for "issue form", "approval" for "OK" and "so the entry" for "so that entry", and `REVIEW.md` says "flaw" for "defect"; the release skill ends each step on "Done when", separates one done condition's parts with a semicolon and reorders a sentence; and the template's comment puts a semicolon before the fold's table and a full stop before its Files rule.
  - The vendor, hosts and check scripts and the blueprint give one home each to two messages, a time limit and curl's options; the vendor script moves its `license` function into the loop whose variable it reads; two workflows and the Markdown linter's config put their keys in their documentation's order; none of them changes what it does.
  - The Markdown linter's config links the section of GitHub's documentation about an image that follows the reader's theme, and four comments in the scripts and configs end a folder path in a slash.

### Fixed

- For nustack's maintainers:
  - The vendor script stops, naming `vendor.json`, when the file is not an object of records, or a record's field is missing or of the wrong type; the vendor workflow's step that lists the copies fails when the file is not an object.
  - `bun run check` reports alone, as it reports a file it cannot read, each `vendor.json` record it cannot use and each manifest, marketplace or `package.json` string it cannot read, so no comparison that reads one adds a problem with wrong advice. It names a `vendor.json` that is not an object of records, a skill with no name, a README with no nus-mode block and a blueprint that names no Bun version.
  - `bun run check` sorts the files it lists under `plugin/` and the lines for what it cannot read, whose order changed between runs.
  - The vendor script leaves the caller's `HEAD` and index as they were when Git runs it, as a commit hook or `git rebase --exec` does.
  - The vendor script stops before it copies into `plugin/skills/` an upstream skill whose `SKILL.md` is missing, is not UTF-8, or holds no YAML frontmatter with a name and a one-line description.
  - Where upstream moved a skill's folder, the vendor script's advice names the record's `source` to change, where it said upstream dropped the skill.
  - The vendor script's fetches start none of Git's maintenance, which failed some runs of `--update`.
  - `bun run hosts` starts Bun and both hosts with `PATH` alone of the variables set outside, so no other variable moves a file of theirs out of its temporary folder, and a proxy the environment names reaches none of them.
  - `bun run hosts` waits for OpenCode's server to stop before it removes its temporary folder, and prints the server's log when the server logs no address or no password, or lists none of the plugin's skills in time.
  - The vendor script and `bun run hosts` stop where a tool whose answer they act on, such as jq or diff, cannot run or fails with a status that is none of its answers, so neither takes such a failure for another, such as a copy that differs.
  - `bun scripts/release.ts publish` stops before it tags when the clone is shallow, or when the bump is uncommitted, merged in part or not on `origin/main`.
  - The tests of the OpenCode plugin fail where they passed on a broken plugin, such as one that puts nus-mode back in a session whose prompts invoked no skill, or forgets, once it starts again, which sessions loaded nus-mode.
  - The Devin blueprint's step fails where `apt-get update` fails, where it passed and left the machine without jq.

## [0.0.5] - 2026-11-09

nustack's fifth release adds three playbooks to nus-mode, the mode that has a coding agent build software to a senior engineer's bar. A playbook holds one task as numbered steps: small project starts a project only you use, polish cuts a project's lines, and audit reports what align and polish would change without changing anything. New project keeps the projects others will use or that outlive the task, and align offers a project what new project would build that it lacks. The agent also names the check behind each claim it makes, replaces an old form outright instead of keeping both, explains a benchmark result before acting on it, and fixes the cause of a problem, not its symptom.

### Added

- The [`small-project`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/small-project.md) playbook starts a project only you use, within the task, such as an experiment. It holds the code to the full bar and skips agreed standards, commit hooks, CI, a remote repository and docs beyond those its tools create.
- The [`polish`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/polish.md) playbook cuts as many lines from a project's code, tests, docs and config as nus-mode's principles justify, keeping what the project does, and splits each line too dense to read.
- The [`audit`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/audit.md) playbook reports what align and polish would change in a project, each finding confirmed and routed to one of them, and leaves the project unchanged.
- nus-mode names the check behind each claim that work is done or works and how far it reached, and with it each thing left unchecked or unknown, and labels each claim it did not observe as inferred from evidence it names, or else as guessed, as [`principle-responses`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-responses/SKILL.md) says.
- nus-mode replaces an old form outright, keeping it deprecated only for an outside consumer promised a stable interface, data an earlier version stored beyond the change's reach, or an older version running mid-deploy, and naming beside it when it can go, as [`principle-long-term`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-long-term/SKILL.md) says.
- nus-mode explains each benchmark or eval result before acting on it or reporting it, writing the result that would change its decision before the runs, as `principle-long-term` says.

### Changed

- The [`new-project`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/new-project.md) playbook starts a project others will use or that outlives the task. It writes a README, and the license and changelog you agree to, and it creates the remote repository in the step that configures it, after the docs.
- The [`align`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/align.md) playbook offers a project each part of what new project builds that it lacks: a remote repository with CI, each doc, and each part an existing doc lacks.
- nus-mode follows `principle-responses` on claims when it reports to another agent.
- nus-mode fixes the cause of each problem, not its symptom: before it fixes a problem, it traces it to the flaw that produces it and fixes that, as `principle-long-term` says.
- For nustack's maintainers:
  - AGENTS.md, and the release script's comment on pre-releases, state that nustack promises its users no stable interface before v0.1.0, and leave how an old form is replaced to `principle-long-term`.

### Fixed

- For nustack's maintainers:
  - The Devin blueprint downloads Bun from npm's registry when Bun's GitHub release fails to download, which GitHub can refuse with a 504 for longer than the download's retries last.

## [0.0.4] - 2026-11-08

nustack's fourth release adds one rule to nus-mode, the mode that has a coding agent build software to a senior engineer's bar. When fixing one failure turns up another of the same kind, the agent stops patching them one at a time: it names why its approach keeps producing them, and replaces the approach.

### Added

- nus-mode changes an approach that keeps failing: when fixing one failure turns up another of the same kind, it names why the approach keeps producing them, and replaces it.

## [0.0.3] - 2026-11-08

nustack's third release trims nus-mode, the mode that has a coding agent build software to a senior engineer's bar. Most principles, the skills the agent reads for one kind of decision each, keep only where Tomer Nosrati's taste departs from a strong agent's pick, the choice a strong coding agent makes with no instruction, so each rule the agent reads changes what it does. The release adds a principle for how the agent writes to you, a playbook that brings existing code up to nus-mode's bar, and Steph Ango's six Obsidian skills. On Claude Code, Claude Code itself puts nus-mode back after a summary, in place of nustack's hook, except in the two cases the Removed section names.

### Added

- [`principle-responses`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-responses/SKILL.md) shapes how a reply, status update, question or report reads.
- nus-mode files a nustack bug when you ask, with the fields and `bug` label of nustack's [bug form](https://github.com/Nusnus/nustack/issues/new?template=bug.yml), and offers to file one when it departs from a rule for a reason that would hold in any project like yours.
- The [`new-project`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/new-project.md) playbook creates the project's remote repository where it has none, and configures its settings where it is on GitHub, such as branch protection on `main`.
- The [`align`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/align.md) playbook reshapes existing code, from a snippet to a whole project, to nus-mode's bar within its project's standards, if any, so later work in nus-mode meets no friction with them.
- The plugin ships Steph Ango's six Obsidian skills ([kepano/obsidian-skills](https://github.com/kepano/obsidian-skills)), unchanged and each with its MIT license: `obsidian-markdown`, `obsidian-bases`, `json-canvas`, `obsidian-cli`, `defuddle` and `knap`. The agent can load each one, in nus-mode or without it, when the task matches its description, such as writing a `.base` or `.canvas` file.

### Changed

- nus-mode calls its principles the Zen of Nusnus and keeps only the goal, the index of its skills, how they combine with the project and each other, and Tomer Nosrati's lines on how an agent works. It drops the rule that the request sets the scope, since [`long term`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-long-term/SKILL.md) says how far its fixes reach; working on your own covers the decisions within the request, until the task is done. It drops settling open decisions by the Zen of Python, in every language, with its aphorisms in ties and design decisions, since the Zen of Python is Python's own creed and a strong agent follows it in Python unprompted. It cuts the steps, cross-references and reasons a strong agent follows without them: listing friction points before fixing them, reasoning through doubt before an experiment, and refusing a reviewer's say-so.
- [`types`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-types/SKILL.md), [`boundaries`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-boundaries/SKILL.md), [`fail fast`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-fail-fast/SKILL.md), [`dependencies`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-dependencies/SKILL.md), [`layout`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-layout/SKILL.md), [`design`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-design/SKILL.md), [`DRY`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-dry/SKILL.md), [`naming`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-naming/SKILL.md), [`self-explanatory code`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-self-explanatory-code/SKILL.md) and [`language-python`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/language-python/SKILL.md) keep only where their rules depart from a strong agent's pick, `language-python` for what Python changes. The [`investigate`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/investigate.md) and `new-project` playbooks keep their steps and only those departures.
- `naming`'s rename drops "everywhere the name appears" and "in the same commit".
- `self-explanatory code` drops its call to rename, extract or restructure until each part reads plainly, its list of what a project's docs state and its call to state a rule in your own words.
- `long term` keeps only what builds work to last, done once, and drops its rules to keep old callers working and to cover every line and branch.
- [`resilience`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-resilience/SKILL.md) is redefined as code that comes through failure and load by its design rather than by scattered guards.
- [`deterministic tests`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-deterministic-tests/SKILL.md) holds tests in general and keeps only its most significant rules; where shared test helpers live moves to `layout`.
- `deterministic tests` has each new test fail against code broken by hand, where `long term` accepted a hand break or a mutation run. `language-python` drops pytest-cov, coverage with its exclusions, mutmut, and the hand breaks of the code mutmut leaves unmutated. The `new-project` playbook drops its mutation-testing job and, from its review and reply, the mutation run and the hand breaks of code no mutation tool mutates.
- [`PR descriptions`](https://github.com/Nusnus/nustack/blob/main/plugin/skills/principle-pr-descriptions/SKILL.md) keeps only what any project can use.
- `language-python` links each of its rules for tests to the principle it gives the Python form of.
- nus-mode's cold read pictures a reader new to the project reading the work.
- nus-mode's cheap-ETA exception moves from its rule for times into its rule to choose quality over session cost, and keeps only the ETA's analysis cheap, never the reading of the live pace.
- nus-mode estimates from observed pace: it reads how fast each job, agent and subagent the work waits on is moving at the time, tries each other way it has when one fails, and states the basis with the ETA, the observed pace or the past runs it fell back on and why.
- The OpenCode plugin puts nus-mode back after a summary in each session that loaded it, whether the user invoked it or the agent loaded it with the skill tool.
- README is a short front page: what nustack is and how it works, how to install, use and update it on each host, each skill with its own description, and a pointer to `AGENTS.md` for contributors.
- The plugin's description, which each host and the marketplaces show, names the Obsidian skills beside the mode.
- Each release page holds the release's changelog section alone: its lead, then its changes.
- For nustack's maintainers:
  - The repository keeps the skills, one manifest per host, the OpenCode plugin, four short scripts, `scripts/check.ts`, `scripts/vendor.sh`, `scripts/hosts.sh` and `scripts/release.ts`, and `scripts/manifests.ts`, the list of manifests two of them read. `bun run check` runs every check but `bun run hosts` in seconds, on macOS as on Linux, and `bun run hosts` installs the plugin in the latest Claude Code, points the latest OpenCode at it, and checks each offers every skill, failing unless OpenCode hides exactly the principle and language skills from the model. Neither takes an argument, and `bun run hosts` ignores an `OPENCODE_PASSWORD` set outside it.
  - A release is a pull request: the `release` skill sets the version, titles the changelog section and opens it with a lead, and once it merges, the release workflow tags `v<version>` and publishes the section as the release page, once, as a pre-release before v0.1.0. A dry run takes the same steps, writing nothing to GitHub, and stops before it tags or publishes. A bump that stopped partway finishes on a rerun, each file it sets landing whole, and the release script fails on any argument it does not take, naming it.
  - `vendor.json` records each vendored copy's upstream, skills and commit, `bun run check` fails when a copy differs from upstream at that commit, and a weekly workflow opens a pull request when a copy differs from upstream, moving its record, with its own changelog entry, only when a copied skill or its LICENSE changed upstream; a rerun of a stopped update finishes it. writing-for-agents' pull request reminds the owner to re-read nustack's agent files against the new version. The workflow reads its copies from `vendor.json`, fills the PR template's sections in its description, linking its run, and copies each vendored skill's description into any README row for it.
  - `bun run check` fails when a copy nustack keeps of a fact differs from its source: a README skills-table row from its skill's description; the marketplaces' plugin description or owner from the manifests'; the two marketplaces' own descriptions from each other; the vendored folders `.markdownlint-cli2.yaml` and `.gitattributes` list, and the paths the vendor workflow commits, from `vendor.json`'s; the manifest the release workflow runs on from the one `scripts/release.ts` reads; the blueprint's Bun from `package.json`'s; README's nus-mode line from the `new-project` playbook's; or the frontmatter pattern `plugin/opencode.ts` and `scripts/vendor.sh` hold from `scripts/check.ts`'s.
  - `bun run check` also fails when a field in an authored plugin skill's frontmatter spans lines or Biome warns. It names each file it reads that is missing, unreadable or not valid JSON or YAML, reporting only those until they are fixed, and each skill folder with no SKILL.md; reports by name each manifest or marketplace field it compares that is missing or not a string; refuses a `vendor.json` record without exactly its five fields, each of its type; and runs the tests in random order under a seed it prints.
  - The Devin blueprint builds a Linux and a macOS machine through the same steps, installing jq where missing and Bun at the version `package.json` names, with a time limit and retries on Bun's download.
  - `.claude/skills` links to `.agents/skills`, so Claude Code offers the release skill in this repository.
  - The PR template opens with a headline, risk, checks and size badges and a summary in plain words, with checks, files and decisions in one fold.
  - `AGENTS.md` asks the owner's OK before adding a script, check, workflow, test or dependency, which earns its place only where a user or maintainer would otherwise meet a silent failure, and puts a lesson from a failed run into a skill's wording first. `REVIEW.md` holds only what review checks beyond `bun run check` and `bun run hosts`.

### Removed

- The Claude Code hook that put nus-mode back after a summary. After a summary, Claude Code re-attaches each skill the session invoked, up to 5,000 tokens of each, as [its docs](https://code.claude.com/docs/en/skills#skill-content-lifecycle) say. They promise nothing for a skill invoked before a session was resumed, and Claude Code 2.1.312 re-attached no such skill, so a session resumed and then summarized can lose nus-mode until the agent loads it again, as can a session whose skills invoked more recently fill the 25,000 tokens Claude Code shares among the skills it re-attaches.
- For nustack's maintainers:
  - The Python command, Make, pre-commit, the release zip, the fake-model smoke tests, the test fixtures and the PR title workflow.

### Fixed

- The OpenCode plugin names the full path of each SKILL.md it cannot read or that is not UTF-8, nus-mode's included, and of a skills folder it cannot read, and stops on a SKILL.md that names no skill or description, and refuses a skill folder that is a symlink, each time saying to reinstall the plugin.

## [0.0.2] - 2026-11-04

<!-- 0.0.2's entry is reworded to AGENTS.md's rule that each entry and lead is written in a timeless manner, so it differs from its published release page: the owner overrode, this once, the rule that a released changelog entry stays as released. -->

nustack's second release adds a principle for tests to nus-mode, the mode that has a coding agent build software to a senior engineer's bar; a principle is a skill, an instruction file the agent reads when its work needs it. When the agent writes or changes a test, or a test passes on some runs and fails on others, it makes the test's outcome depend only on its inputs: the test waits for what the code does rather than for time to pass, and passes or fails the same way on every run, however busy the machine.

### Added

- `principle-deterministic-tests`, a principle nus-mode reads when the agent writes or changes a test or its helpers, or a test passes on some runs and fails on others: a test's outcome depends only on its inputs, the same on every run and under any load. `language-python`, the skill the agent reads for Python work, gives the principle's Python form: a test that interrupts its own code raises the interrupt at the moment the code reaches the point it interrupts, not from a timer, and the agent proves a test under load by running that one test in a loop, where [pytest-randomly](https://github.com/pytest-dev/pytest-randomly) gives each run a new seed, which varies the values `random` gives.

### Changed

- In Python, the agent gives every test the whole of the suite's per-test time limit, the limit that [pytest-timeout](https://github.com/pytest-dev/pytest-timeout)'s `timeout` setting puts on each test, as `principle-deterministic-tests` says. This replaces `language-python`'s rule to give a test that checks some code ends quickly, such as a loop that must end, a shorter limit with `@pytest.mark.timeout`, which a busy machine can outlast.
- The plugin's description, which opens each release page, names its author in full: Tomer Nosrati.
- For nustack's maintainers:
  - `nustack` is nustack's own command-line tool. The release steps replace editing each file whose version `nustack` compares and running `uv lock` with one command that sets the release's version, commitizen's `uv run cz bump --increment PATCH --version-files-only --yes`. `nustack check` fails when the files listed in `pyproject.toml`'s `[tool.commitizen] version_files`, which that command sets, differ from the files whose version `nustack check` compares.

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
