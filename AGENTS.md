# nustack

The rules for changing nustack. [README.md](README.md) shows the layout and how to install it.

Work in this repository in nus-mode: load `plugin/skills/nus-mode/SKILL.md` before you start.

nustack keeps its own rules. Every file nustack's authors write follows nus-mode, the skills it reads and this file, whether code, scripts such as bash scripts, tests, workflows or docs; a vendored copy and a file a tool generates, such as a lockfile, are not theirs, and a released changelog entry stays as released. A break of any of those rules blocks the pull request under review like a failing check, even when that pull request leaves the file unchanged, unless a reason that holds is stated where nus-mode's *strong defaults* rule puts a departure's reason. In a stack, a break that a pull request higher up fixes, or will fix once it opens, blocks that higher pull request instead of the one below it; the lower one's description lists each such break, and it merges only together with the higher one.

Word skill text, this file, REVIEW.md and the PR template by Matt Pocock's [writing-for-agents](.agents/skills/writing-for-agents/SKILL.md). It governs only how a text is worded, never what nustack does or where things live, and where it and this file differ, this file wins. A scheduled workflow proposes his repository's newest version as a pull request that replaces the copy here, so propose any change to it upstream, through the owner.

## Where things live

- `plugin/` is what installs. It holds only what `nustack check` allows there, and the check's problem names each file that does not belong. Nothing outside `plugin/` reaches a user's session.
- A principle is a skill of its own, `plugin/skills/principle-<name>/`, stated in its `SKILL.md` alone. Every other file that needs it links it instead of restating it.
- A language skill, `plugin/skills/language-<name>/`, holds what the principles leave to one language: its tools, and the form a principle takes where that language changes it, under a link to that principle.
- A playbook holds one task as numbered steps. Each step ends on a done condition that an agent can check and that names everything the step covers, not only what it outputs. Where a tool can create a file, such as a config file, a playbook has the agent create it with that tool; where no tool creates the file, the agent writes it as its format's documentation defines it.
- `plugin/skills/` holds exactly one mode, nus-mode, beside the principle and language skills. nus-mode's `SKILL.md` states the goal every principle serves, and lists every playbook, principle and language skill with when it applies.
- Where a file's ecosystem defines no order, config keeps its keys, and each entry whose order changes nothing that runs, in the order its format's documentation shows them, each key, by its full path, at its first place there, then the rest alphabetically; other entries, and entries that depend on one another, keep the order they run in. A format's documentation is that of whoever defines it, whether a tool, a service or a spec, such as npm's for `package.json`. Where it has a reference, a field table or one section per key, each key takes the place of its own row or section in the reference, even where its examples order keys differently. A doc keeps its sections in the order a reader needs them.
- `plugin/` holds instructions, and code only in the OpenCode loader, since OpenCode loads plugins only as code, and in the Claude Code hook in `hooks/`, since only a hook runs after Claude Code summarizes a session. Both put nus-mode's text back in a session that loaded it, once a summarization drops it.

## Writing skill text

- State the target behaviour. A prohibition earns its place only as a guardrail with no positive phrasing, paired with its target. This file holds that rule itself, since each sync can change the copy of writing-for-agents.
- Write for every host: name no agent host, model, host-specific path or date.
- Frontmatter holds `name` and `description`. A principle or language skill also holds `disable-model-invocation: true` and `triggers: [user]`, which between them hide it from the model on every host, so nus-mode reads it as a file. nus-mode leaves both at their defaults, so the user can invoke it and the model can load it when a project's `AGENTS.md` asks. Each field and list entry keeps to one line, and no value holds `---`, since some hosts then drop every field.
- Keep each `SKILL.md` under the line limit `nustack check` enforces.

## Harness code

A `Problem` names the file, the field and the fix. It repeats no value read from a file, since the harness cannot tell a secret from any other value. It may repeat a changelog title, version or date, or a link's target, since each names the entry or link to fix.

The linter settings in `pyproject.toml` decide which docstrings code needs.

Tests sit in the tier folders [language-python](plugin/skills/language-python/SKILL.md) names, tiered and mirrored as [long term](plugin/skills/principle-long-term/SKILL.md) says.

## Pull requests

PR descriptions start from the PR template. A pull request is squash-merged, so it lands on its base branch as one commit named by its title. Whoever merges writes that commit's message, with no `Co-authored-by` line, since GitHub's default message joins the commits' messages, trailers included, and adds one for each commit author other than the pull request's. A stack lands together: once every pull request in it is approved, they merge into `main` one after another, lowest first. Commits follow Conventional Commits, and the commit-msg hook checks each message.

A pull request is done once Devin Review has reviewed its head commit and left no open finding. Fix each finding in a new commit or answer it in its thread, then resolve the thread.

Until v0.1.0, the first version the owner holds to a stable interface, a change replaces an old form outright. This departs from [long term](plugin/skills/principle-long-term/SKILL.md)'s rule to keep old callers working.

## Checks

`make install` sets up the harness and the commit hooks. `make smoke` runs the release zip in Claude Code and OpenCode, at the versions `tests/fixtures/smoke/bun.lock` locks, against a fake model, and checks that nus-mode comes back after each kind of summarization. Of the hosts' install scripts, `tests/fixtures/smoke/package.json` trusts only OpenCode's, which copies its native binary into place; Bun links Claude Code's native binary itself, so its script need not run. `make check` runs every pre-commit-stage hook in `.pre-commit-config.yaml` over every file and fixes what the tools can; each commit runs the same hooks. In `make check` and at each commit, a missing or stale `bun.lock` stops the run before the Bun hooks, and an older Bun fails it. `make mutate` runs mutmut over the harness and fails on each mutant the tests leave alive. Each make target stops when a tool it needs is missing or uv is older than the repository requires, and `make install` also stops when `bun.lock` is missing or stale.

`nustack check`, one of those hooks, enforces the rules its `--help` lists, each with a test in the harness's tests. Review holds the rest, as [REVIEW.md](REVIEW.md) says.

CI runs `make check`, `make mutate` and `make smoke`, holds commit messages to Conventional Commits and builds the release zip. On a pull request it checks each commit, letting through only the commits `cz check` exempts by default, such as `fixup!` and `Merge`, which the squash merge drops. The PR title workflow checks the title, and checks it again on each edit of the pull request. On `main` CI checks every commit, with no exemptions. The release workflow publishes only from a `v<version>` tag on `main`, once CI passes on it. `.github/workflows/` says what triggers each workflow.

## Environment

`.devin/blueprint.yaml` sets up the machine each Devin session on nustack starts from. Other repositories share that machine, so the blueprint installs uv and Bun only where missing, then runs `make install` and installs the commit hooks' environments. A uv or Bun older than the repository requires stops the build with the fix; when the older Bun comes from another repository's blueprint, raise that blueprint's Bun pin to nustack's. Change the blueprint by pull request, like any other file; its merge to `main` starts a build.

### Onboarding a Devin organization

nustack is onboarded once every item below holds; each item about the repository's blueprint is a setting the [Git-backed blueprints](https://docs.devin.ai/onboard-devin/environment/git-backed-blueprints) guide describes. Set up each missing one yourself where your tools allow; otherwise walk the user through it one step at a time, linking the Devin web app page that sets it:

1. The organization installs the plugin from `Nusnus/nustack`, subdirectory `plugin`, following `main`, so the session lists `/nustack:nus-mode`. Install it at organization scope, with the user's approval, or have the user add it, as the [Plugins guide](https://docs.devin.ai/product-guides/plugins) describes.
2. The repository's blueprint is included in the organization's environment. Including it starts a build.
3. The blueprint's source is GitHub, so it reads `.devin/blueprint.yaml` from `main`.
4. The blueprint's setting to build on every commit to the default branch is on, so each commit to `main` starts a build from the blueprint in that commit.

Onboarding is done when the session lists `/nustack:nus-mode` from an organization-scope install of `plugin` on `main`, the blueprint shows each of those settings in place, and a session that starts after the latest build has nustack cloned and passes `make check`.

## Releases

1. Run `uv run cz bump --increment PATCH --version-files-only --yes`. It sets the next patch version in `pyproject.toml`, `uv.lock` and each file `pyproject.toml`'s `[tool.commitizen] version_files` lists, which `nustack check` holds to the files whose version it compares, and makes no commit, tag or changelog entry. `--increment PATCH` keeps the version below 0.1.0, which commitizen would otherwise pick for a `feat` commit in 0.x; for a version the owner chooses, such as 0.1.0, give that version in place of `--increment PATCH`. `--yes` answers commitizen's question whether this is the first release, which it asks because it looks for tags without nustack's `v` prefix; the answer changes nothing the command writes. The step is done when `git status --short` lists exactly `pyproject.toml`, `uv.lock` and the files `version_files` lists as changed, each carrying the new version, and the only problems `make check` names are in `CHANGELOG.md`: that it does not open with the version's entry, and that its links for that version and `[Unreleased]` are missing or wrong.
2. In `CHANGELOG.md`, in the format its header names, retitle the `[Unreleased]` section `[<version>] - <YYYY-MM-DD>` with the release day, add each change since the last release that it misses, and start an empty `[Unreleased]` section above it. Then add or fix each link `make check` names, above the first `##` heading, since `nustack notes` counts a link below an entry as part of that entry. The step is done when the version's entry is dated with the release day and holds every change since the last release, below an empty `[Unreleased]` section, `make check` names no problem in the changelog's titles or links, and each link the step added or fixed sits above the first `##` heading.
3. Shape the entry as the body of the release page, which `nustack notes` prints around it: open it on a lead, a short paragraph that tells a reader who never saw the repository what the release brings, then group its changes under Keep a Changelog's `###` types of change. In each group, list first the changes a plugin user meets, then, where the group has changes that only nustack's own development meets, end on one `For nustack's maintainers:` bullet that nests them. The step is done when a lead paragraph sits above the first `###` group, each group lists its plugin-user changes first and ends on at most one `For nustack's maintainers:` bullet that nests every other change, `make check` passes, and a cold read of the page `nustack notes` prints, as nus-mode's Goal says, finds no friction point.
4. Run `make check`, then squash-merge the pull request into `main`. The step is done when `make check` passes and the merge commit is on `main`.
5. Tag `v<version>` on the commit the merge makes on `main`, and push the tag. The release workflow publishes the release from the tag. The step is done when its run passes and the release is published.
