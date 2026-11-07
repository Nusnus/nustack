<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/wordmark-dark.svg">
    <img alt="nustack" src=".github/assets/wordmark-light.svg" height="72">
  </picture>
</h1>

<p align="center">Trust a coding agent to work like a senior engineer while you're away.</p>

<p align="center">
  <a href="#1️⃣-install">Install</a> · <a href="#2️⃣-use">Use</a> · <a href="#skills">Skills</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="#contributing">Contributing</a>
</p>

<br>

nustack gives your coding agent nus-mode: Tomer Nosrati's way of building software, as one mode. It works in Devin, Claude Code, Cursor and OpenCode.

- One mode for any task you give
- Playbooks that run whole tasks as checked steps
- One skill per principle, read when the work needs it
- A newcomer's reread before the work is done
- Your project's own rules come first

## Quick start

### 1️⃣ Install

In [Claude Code](https://code.claude.com/docs/en/discover-plugins):

```text
/plugin marketplace add Nusnus/nustack
/plugin install nustack@nustack
```

In [OpenCode](https://opencode.ai/v2/docs/plugins/):

```text
opencode plugin add 'github:Nusnus/nustack#main::path:plugin'
```

In [Devin](https://docs.devin.ai/product-guides/plugins), add a plugin from the repository `Nusnus/nustack`, subdirectory `plugin`.

In [Cursor](https://cursor.com/docs/plugins#test-plugins-locally), copy this repository's `plugin` folder to `~/.cursor/plugins/local/nustack`, then run Developer: Reload Window. To update, replace the folder with a newer copy and reload. On Enterprise, an admin first turns on Allow Local Plugin Imports.

The other hosts' links say how to update. Without repository access, download `nustack-<version>.zip` from [Releases](https://github.com/Nusnus/nustack/releases), then upload it as a zip plugin in Devin or unzip it to `~/.cursor/plugins/local/nustack` in Cursor.

### 2️⃣ Use

Give the agent a task in nus-mode:

```text
/nustack:nus-mode Start a CLI that tracks expenses.
/nustack:nus-mode Investigate why the nightly export times out.
/nustack:nus-mode Align this repository with nus-mode.
```

| Host | Invoke |
| :-- | :-- |
| Claude Code, Devin | `/nustack:nus-mode <task>` |
| Cursor | Type `/`, pick nus-mode, then the task |
| OpenCode | `@nus-mode <task>` |

It asks you about each open decision until you tell it to [work on its own](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/SKILL.md#standing-rules).

### 3️⃣ Turn it on for a project

Add this line to the project's AGENTS.md, and each session there works in nus-mode:

```markdown
Work in this repository in nus-mode: load the skill before you start.
```

Claude Code reads AGENTS.md itself; add `@AGENTS.md` to CLAUDE.md only where the project has one or the session [can't read AGENTS.md](https://code.claude.com/docs/en/memory#agents-md). The [new-project playbook](https://github.com/Nusnus/nustack/blob/main/plugin/skills/nus-mode/playbooks/new-project.md) does both.

## How it works

1. You give the agent a task.
2. nus-mode follows the [playbook](plugin/skills/nus-mode/SKILL.md#playbooks) that fits, if one does.
3. It reads each principle the work touches, in full.
4. Before it finishes, it rereads the work as a newcomer and fixes each snag.

## Skills

nus-mode reads its principle and language skills itself.

<details>
<summary>All skills</summary>

| Skill | What it holds |
| :-- | :-- |
| [nus-mode](plugin/skills/nus-mode/SKILL.md) | The goal, the standing rules, and when each skill applies. |
| [principle-naming](plugin/skills/principle-naming/SKILL.md) | Names that say what a thing is in the domain. |
| [principle-dry](plugin/skills/principle-dry/SKILL.md) | One home for every piece of knowledge. |
| [principle-fail-fast](plugin/skills/principle-fail-fast/SKILL.md) | Code that fails where a wrong state is first detected, with an error that says how to recover, and holds an expected absence in its type. |
| [principle-boundaries](plugin/skills/principle-boundaries/SKILL.md) | Outside data parsed once, where it enters, strictly into the project's domain types. |
| [principle-types](plugin/skills/principle-types/SKILL.md) | Types that hold the contract, so an invalid value cannot exist. |
| [principle-design](plugin/skills/principle-design/SKILL.md) | A design that starts from proven patterns and SOLID objects, short because it fits the problem. |
| [principle-layout](plugin/skills/principle-layout/SKILL.md) | A folder and file layout that shows the design. |
| [principle-dependencies](plugin/skills/principle-dependencies/SKILL.md) | Dependencies that point one way, one home for each library, the runtimes a project targets, a pinned lockfile, and deciding logic kept pure. |
| [principle-resilience](plugin/skills/principle-resilience/SKILL.md) | Code that comes through a stalled or failing dependency, or a crash part way through. |
| [principle-long-term](plugin/skills/principle-long-term/SKILL.md) | Changes built to last, so they are done once. |
| [principle-deterministic-tests](plugin/skills/principle-deterministic-tests/SKILL.md) | Tests whose outcome depends only on their inputs, the same on every run and under any load. |
| [principle-self-explanatory-code](plugin/skills/principle-self-explanatory-code/SKILL.md) | Code that explains itself, and docs for what it cannot say. |
| [principle-pr-descriptions](plugin/skills/principle-pr-descriptions/SKILL.md) | PR descriptions a reviewer takes in at a glance. |
| [principle-responses](plugin/skills/principle-responses/SKILL.md) | Replies, status updates, questions and reports a person takes in at a glance. |
| [language-python](plugin/skills/language-python/SKILL.md) | Python's tools, and where Python changes how a principle applies. |

Steph Ango's [obsidian-skills](https://github.com/kepano/obsidian-skills) ship unchanged, and each loads when a task matches it.

| Skill | What it holds |
| :-- | :-- |
| [obsidian-markdown](plugin/skills/obsidian-markdown/SKILL.md) | Obsidian Flavored Markdown. |
| [obsidian-bases](plugin/skills/obsidian-bases/SKILL.md) | Obsidian Bases, `.base` files. |
| [json-canvas](plugin/skills/json-canvas/SKILL.md) | JSON Canvas, `.canvas` files. |
| [obsidian-cli](plugin/skills/obsidian-cli/SKILL.md) | The Obsidian CLI. |
| [defuddle](plugin/skills/defuddle/SKILL.md) | Web pages to Markdown with the Defuddle CLI. |
| [knap](plugin/skills/knap/SKILL.md) | Markdown from Knap templates and data. |

</details>

## Contributing

Read [AGENTS.md](AGENTS.md) first: it holds the rules for changing nustack and [where each part lives](AGENTS.md#where-things-live). Then, with [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Bun](https://bun.sh/docs/installation) installed, set up and run every check:

```bash
make install
make check
```

Run `make` alone to list the other targets. [REVIEW.md](REVIEW.md) lists what review checks, and the [release](.agents/skills/release/SKILL.md) skill cuts a release.

## Acknowledgements

- [pstack](https://github.com/cursor/plugins/tree/main/pstack) gave nustack its name and its mode-and-playbooks shape.
- Matt Pocock's [writing-for-agents](.agents/skills/writing-for-agents/SKILL.md) shapes how nustack words its skills.

## License

[MIT](LICENSE) © Tomer Nosrati
