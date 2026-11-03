# Changelog

All notable changes to nustack are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]: https://github.com/Nusnus/nustack/compare/v0.0.1...HEAD

## [Unreleased]

nus-mode, the nustack plugin's mode that has a coding agent build software to a senior engineer's bar, gains a Python skill, a design principle and sharper rules. A skill is an instruction file the agent loads when its work needs it. When its host, the app the agent runs in, summarizes a long session, nus-mode comes back, or has the agent load it again. For nustack's maintainers, `nustack`, the tool that checks and packages the plugin, checks more rules, the release page's among them, and names problems it used to hide or misname.

### Added

- `language-python`, which nus-mode reads for Python work, and the design principle.
- Rules across nus-mode, its playbooks, each the steps of one task, and its principles, each a skill that holds one area's rules. The agent departs from a rule only with a reason stated beside the departure; where nothing there can hold one, the reason goes in the project's `AGENTS.md`, the file of instructions agents read in a repository. Among them:
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
- For nustack's maintainers:
  - A weekly workflow proposes the changes made [upstream](https://github.com/mattpocock/skills) to `writing-for-agents`, a skill copied into the repository, as a pull request.
  - `nustack check` covers more rules, among them: playbook done conditions; link anchors; skill text that names no host; each marketplace's owner, which must be the plugin's author; one name and description shared by both marketplaces; README's line that turns nus-mode on for a project, which must match the new-project playbook's; and the test layout.
  - `nustack check` holds the release's changelog entry to [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)'s types of change, each once and in order, with each group showing something, and to full URLs for its links and images.
  - `nustack check` holds README to one `### 1️⃣ Install` and one `### 2️⃣ Use` section, each showing something, with full URLs for its links and images, and checks that each reference label those sections and the release's changelog entry use resolves on the release page as it does in their own file.
  - `make mutate` runs mutation tests over `nustack`, and CI runs them on every pull request.
  - The sync and release workflows run tested `nustack` commands instead of shell logic.

### Changed

- The release page opens with what nustack is, then the release's summary and its changes, README's install and use steps and a link to every change since the previous release.
- For nustack's maintainers:
  - `nustack check`, `bundle` and `notes` take each path only as an option, `--root` or `--out`, no longer as an argument, and every command's help says what each option and argument holds.
  - Dependabot's dependency updates raise each dependency's floor to its newest release, and CI installs the Bun that `package.json` names.

### Fixed

- In OpenCode, the nustack plugin refuses more of the broken skills `nustack check` refuses, such as a `SKILL.md` that is not valid UTF-8 or a symlinked skill folder, and names the fix when it cannot read its skills folder.
- For nustack's maintainers:
  - `nustack check` names problems it used to hide, skip or misname, such as a missing `plugin/skills/` folder, a misplaced `[Unreleased]` section or a symlink loop, and reports a frontmatter timestamp too large to read instead of ending in a traceback.
  - `nustack check`, `bundle` and `notes` stop with one problem at a root that is not a folder or lacks a `plugin/` folder, and every `nustack` command refuses an empty option.
  - A `pyproject.toml` parse error no longer repeats the file's contents.
  - `nustack notes` prints a CRLF changelog's entry without carriage returns, and the `writing-for-agents` sync refuses a pull request template that repeats one of the lines the sync fills, instead of filling each repeat.

## [0.0.1] - 2026-10-31

### Added

- First release: `nus-mode`, with its playbooks and principles, installable in Devin, Claude Code, Cursor and OpenCode.

[0.0.1]: https://github.com/Nusnus/nustack/releases/tag/v0.0.1
