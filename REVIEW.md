# REVIEW.md

What Devin Review holds every pull request to. [AGENTS.md](AGENTS.md) holds the rules for changing nustack, and this file says where review finds what `make check` cannot. Report each defect on the line that has it: what is wrong, what would make it right, and the file and line of the rule it breaks.

## What review holds

- **AGENTS.md and nus-mode's principles, on every file the pull request changes.** AGENTS.md puts all work here in nus-mode, so each principle applies where its line in `plugin/skills/nus-mode/SKILL.md` says, the Python harness, the TypeScript OpenCode loader and their tests included. Where a principle and AGENTS.md conflict, AGENTS.md wins, as nus-mode's standing rules say. Read a principle's `SKILL.md` in full before you cite it.
- **What no tool checks.** AGENTS.md › Checks lists what `make check` enforces, and CI runs it on every pull request, so review spends its findings on the rest.

## The harness and the loader

- **Each rule `nustack check` enforces has a test that fails without it.** For each rule a pull request adds or changes, find the test that breaks a copy of the repository in exactly that way and asserts the `Problem` it reports. Coverage shows a line ran; only that test shows the rule holds.
- **A check reports every input its rule forbids as a `Problem`.** Look for what the parsing lets through: an empty value, a duplicate, an unknown key, a wrong type or YAML shape, a file that is not UTF-8, a path outside the folder it belongs to. Each one ends as a `Problem`, and the check still reports the rest. The exceptions are a symlink under `plugin/`, which every later check would read through, and a folder there the check cannot open, past which every later check would see only part of the plugin: the check reports them and stops.
- **A change that widens what a model or check accepts says why** in the pull request description.
- **Every module, class and test module under `src/` and `tests/`, and `plugin/opencode.ts`, keeps the order in AGENTS.md › Harness code.**
- **Tool configuration does what it says.** Check each setting in every tool's configuration file, and in `.github/`, against the documentation of the version the repository pins, including the stages each hook runs at. Every package the harness imports is a direct dependency in `pyproject.toml`, and every package the loader or its tests import is one in `package.json`.

## The plugin

Everything under `plugin/` reaches a user's session.

- **Every host reads the same plugin.** Devin, Claude Code and Cursor read it through their manifests, and OpenCode through `plugin/opencode.ts`. A change to one host's files keeps the others loading every skill, with each principle hidden from the model, and README.md's install table matches each host's current documentation.
- **Every line under `plugin/skills/` follows AGENTS.md › Writing skill text.**
- **A principle's rule lives in its own `SKILL.md`.** Look for it restated in another principle, in nus-mode's `SKILL.md`, in a playbook, in the PR template or in README.md, each of which names and links it instead.
- **Each playbook step ends on a condition the agent can check before it moves on.**
- **Each principle and playbook serves the goal in nus-mode's `SKILL.md`,** and the line there that says when a principle applies matches what the principle covers.
- **The mode has one name** in its folder, its frontmatter, README.md and every link.

## Claims about the outside world

- **A claim that a library, tool or host behaves some way is checked first**, in the source or documentation of the version the repository runs (`uv.lock`, a hook's `rev`, an action's pinned commit) or the host's current documentation, and the finding links it. A claim you could not check is a question for the author.
- **A choice the code, a comment or a docstring gives a reason for is a decision.** Report it with the evidence that its reason does not hold.

## Pull request description

- **The description starts from `.github/pull_request_template.md` and matches the diff at the commit under review:** each change it claims is in the diff, and each check it reports carries its mark.

## Leave alone

- What `make check` reports.
- `uv.lock` and `bun.lock`, unless the dependencies in `pyproject.toml` or `package.json` change.
- A function or method without a docstring: [self-explanatory code](plugin/skills/principle-self-explanatory-code/SKILL.md) puts docstrings on modules and classes.
- The entries of released versions in `CHANGELOG.md`.
