# nustack

The rules for changing nustack. [README.md](README.md) shows the layout and how to install it.

Work in this repository in nus-mode: load `plugin/skills/nus-mode/SKILL.md` before you start.

Choose quality over session cost: when a choice trades one for the other, such as another review round or a slower but stronger check, take the one that raises quality.

## Where things live

- `plugin/` is what installs: a manifest for each host, `skills/`, a copy of the repository's `LICENSE`, and the OpenCode loader, `opencode.ts` with its `package.json`. Everything else in the repository is for working on nustack and never reaches a user's session.
- A principle is a skill of its own, `plugin/skills/principle-<name>/`, stated in its `SKILL.md` alone. nus-mode's `SKILL.md` and its playbooks name it and never restate it.
- A playbook holds one task as numbered steps, and ends each step on a done condition an agent can check.
- `plugin/skills/` holds exactly one mode, nus-mode, beside the principle skills.
- nus-mode's `SKILL.md` states the goal every principle serves, and lists every playbook and principle skill, each with when it applies.
- `plugin/` holds instructions, and code only in the OpenCode loader, since OpenCode loads plugins only as code. What a tool generates or its docs own, such as config files, a playbook tells the agent to produce from the tool itself.

## Writing skill text

- State the target behaviour. A prohibition earns its place only as a guardrail with no positive phrasing, paired with its target.
- Write for every host: name no agent host, model, host-specific path or date.
- Write for a reader who never saw the conversation that produced the text: state each rule in general terms and in your own words, and keep an example from the conversation only when it generalises.
- Frontmatter holds `name` and `description`. A principle skill also holds `disable-model-invocation: true`, which Claude Code and Cursor read and the OpenCode loader follows, and `triggers: [user]`, which Devin reads, so the model never invokes it as a skill and nus-mode reads it as a file. nus-mode leaves both at their defaults, so the user can invoke it and the model can load it when a project's `AGENTS.md` asks. Each field and list entry keeps to one line, and no value holds `---`, since some hosts then drop every field.
- Keep each `SKILL.md` under the line limit `nustack check` enforces.

## Harness code

The OpenCode loader and its tests are held to the same principles in TypeScript.

A problem names the file, the field and the fix. It never repeats a value read from a file, since the harness cannot tell a secret from any other value. The exceptions are a changelog title, version or date, and a link's target, since each says which entry or link to fix.

Ruff enforces a docstring on every public module and class. Every file follows one order, which no tool enforces. State reads up from what it is built on, and behaviour reads down from where it starts:

- A module holds its docstring, its imports and its module-level objects, then its classes, each before the classes that use it, then its functions, each before the functions it calls.
- A class holds its class constants, its fields, its properties and cached properties, each after the ones it reads, then its methods, each before the methods it calls.
- A test module holds its helpers, then its tests in the order of the code they test.

## Pull requests

PR descriptions start from the PR template. A pull request is squash-merged, so it lands on `main` as one commit named by its title.

## Checks

`make install` sets up the harness and the commit hooks. `make check` runs every pre-commit hook in `.pre-commit-config.yaml` over every file, and fixes what the tools can fix. Both first stop with the fix when Bun is missing. `bun test` fails when Bun is older than the version `package.json` pins, and uv refuses to run below the `required-version` in `pyproject.toml`. On each commit, the pre-commit hook runs the same hooks.

`nustack check`, one of those hooks, enforces the structural rules above:

- the manifests and versions agree;
- `plugin/` holds only the host manifests, skills, playbooks, the OpenCode loader with its `package.json`, and a `LICENSE` equal to the repository's;
- `plugin/` holds no symlink and no folder the check cannot open, and either stops the check before it reads anything else, since every later check would read through the symlink or see only part of the plugin;
- each skill's frontmatter and triggers follow Writing skill text, and its `SKILL.md` stays under the line limit;
- the mode indexes every principle and playbook;
- every relative link in `plugin/` reaches a file.

Review holds the rest, and [REVIEW.md](REVIEW.md) says how.

CI runs `make check` and checks commit messages. On a pull request, it checks each commit and the title, which a squash merge makes the commit on `main`, and lets through the commits `cz check` exempts by default, such as `fixup!` and `Merge` commits, since the squash drops them. Each commit pushed to `main` must be a Conventional Commit, with no exemptions. The release workflow builds the zip on every pull request, and publishes a release only from a tag.

## Environment

`.devin/blueprint.yaml` sets up the machine each Devin session on nustack starts from. Other repositories share that machine, so the blueprint installs uv and Bun only where the machine lacks them, then runs `make install` and installs the commit hooks' environments. Where the uv it finds is older than `pyproject.toml` requires, the build stops at `make install` with the fix. A change to the blueprint goes through review like any other file. After it merges, sync the blueprint and trigger a build, as [Git-backed blueprints](https://docs.devin.ai/onboard-devin/environment/git-backed-blueprints) describes.

## Releases

1. Set the new version in every manifest under `plugin/`, in `plugin/package.json` and in `pyproject.toml`, run `uv lock`, and add the version's entry at the top of `CHANGELOG.md`, titled `[<version>] - <YYYY-MM-DD>` with the release day, as [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) does. `make check` fails until all of them agree.
2. Run `make check`, then squash-merge the pull request into `main`.
3. Tag `v<version>` on the commit the merge makes on `main`, and push the tag. The release workflow checks the tag against the manifests, builds `nustack-<version>.zip`, and publishes the GitHub release with the zip and the changelog entry.

## Commits

Commits follow Conventional Commits, and the commit-msg hook checks each message.
