# Changelog

All notable changes to nustack are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]: https://github.com/Nusnus/nustack/compare/v0.0.1...HEAD

## [Unreleased]

### Added

- `language-python`, which nus-mode reads for Python work, and the design principle.
- Rules across nus-mode, its playbooks and the principles, among them nesting by area, module docstrings that summarize their whole file, each review finding treated as a hypothesis to confirm or refute, fixing a flaw everywhere it appears, the fewest words that say it clearly, documented defaults left unwritten, no data-less class as a namespace, test names that complete their class's sentence, parametrized rows that write out their expected values, decisions nothing else settles taken by the Zen of Python, ETAs from the pace the work keeps, and quality over session cost. A break of these rules blocks unless a reason that holds is stated beside the break, or in AGENTS.md where nothing beside it can hold one.
- A weekly workflow that proposes the vendored `writing-for-agents` skill's upstream changes as a pull request describing them.
- `nustack check` holds each playbook step to a done condition, the mode to its name, each link to an anchor its target has, nus-mode's links to their headings, skill text to naming no host or date, the marketplaces' names, owners and descriptions to the manifests, README's activation line to the new-project playbook's, the vendored copy's exclusions to the sync workflow's destination, each test module to a tier folder that mirrors its source, and each tier folder to holding only tests and `conftest.py`.
- `make mutate` runs mutmut over the harness, and CI runs it on every pull request.
- `nustack sync`, `nustack release-tag` and `nustack publish` hold the sync and release workflows' decisions, so the workflows run tested commands instead of shell logic.
- nus-mode comes back, with the folder its links are relative to, after Claude Code or OpenCode summarizes a session that loaded it.
- On other hosts, nus-mode tells the agent to load it again once a summary drops it.

### Changed

- The `nustack` command runs on Typer instead of cyclopts. `check`, `bundle` and `notes` take each path as an option only, `--root` or `--out`, and their help shows each default. Every command's help says what each option and argument holds.
- Dependabot raises each dependency's floor to its newest release, and CI installs the Bun that `package.json` names.

### Fixed

- A missing `plugin/skills/` folder no longer hides the plugin's other problems, and a pyproject.toml parse error no longer repeats its contents.
- `nustack check` asks to move an `[Unreleased]` section that sits below a release above the releases, no longer asks nus-mode to index a skill folder without a `SKILL.md`, reports a manifest's repeated keys together with its other errors, compares the release files with the valid manifests when one is invalid and the rest agree, names every frontmatter line and value it refuses, and counts a description of only zero-width spaces or word joiners as blank.
- `nustack check`, `bundle` and `notes` stop with one problem at a root that is not a folder or a missing `plugin/` folder, `nustack bundle` names an `--out` path that is a file or cannot be written instead of ending in a traceback, and `nustack notes` prints a CRLF changelog's entry without carriage returns.
- `nustack check` names a file where a folder belongs, an entry that is neither a file nor a folder where a file belongs, and a file, root, plugin folder or test folder whose folder it cannot open, instead of calling each one missing or skipping it, and the `writing-for-agents` sync refuses a pull request template that repeats an anchor instead of filling each copy.
- Every `nustack` command refuses an empty value instead of reading it as a default, such as the folder it runs in.
- `nustack check` names the file, the folder it cannot open or the symlink loop that blocks a required file, instead of calling the file missing.
- `nustack check` reports a frontmatter timestamp too large to read beside the plugin's other problems instead of ending in a traceback, and names a tab in an unquoted frontmatter value with its fix.
- The OpenCode loader refuses, as `nustack check` does, a `SKILL.md` that opens with a byte order mark or is not valid UTF-8, a symlinked skill folder, and a description of only zero-width spaces or word joiners. It keeps the error code of a skill it cannot read, names the fix when it cannot read its skills folder, calls a blank field blank, and lists failing skills in path order.

## [0.0.1] - 2026-10-31

### Added

- First release: `nus-mode`, with its playbooks and principles, installable in Devin, Claude Code, Cursor and OpenCode.

[0.0.1]: https://github.com/Nusnus/nustack/releases/tag/v0.0.1
