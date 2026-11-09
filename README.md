<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset=".github/assets/wordmark-dark.svg">
    <img alt="nustack" src=".github/assets/wordmark-light.svg" height="72">
  </picture>
</h1>

<p align="center">Trust a coding agent to work like a senior engineer while you're away.</p>

<p align="center">
  <a href="#install">Install</a> · <a href="#use">Use</a> · <a href="#skills">Skills</a> · <a href="CHANGELOG.md">Changelog</a> · <a href="#contributing">Contributing</a>
</p>

<br>

nustack is a plugin for Claude Code, Cursor, Devin and OpenCode. It gives your coding agent nus-mode: Tomer Nosrati's way of building software, as one mode. On each task, nus-mode:

1. follows the [playbook](plugin/skills/nus-mode/SKILL.md#playbooks) that fits, if one does, to start a project, investigate a problem, align existing code, cut lines from a project or audit a project;
2. reads, in full, each principle the work touches;
3. puts your project's own rules first;
4. rereads the work as a newcomer would, and fixes each friction point before it finishes.

## Install

In [Claude Code](https://code.claude.com/docs/en/discover-plugins):

```text
/plugin marketplace add Nusnus/nustack
/plugin install nustack@nustack
```

In [OpenCode](https://opencode.ai/docs/plugins/):

```text
opencode plugin add 'github:Nusnus/nustack#main::path:plugin'
```

In [Devin](https://docs.devin.ai/product-guides/plugins), add a plugin from the repository `Nusnus/nustack`, subdirectory `plugin`.

In [Cursor](https://cursor.com/docs/plugins), an admin on a Teams or Enterprise plan imports `https://github.com/Nusnus/nustack` as a team marketplace with Import from Repo; with the Cursor GitHub App installed, Enable Auto Refresh sends each merge to `main` to the team. To try nustack before that, or on other plans, copy this repository's `plugin` folder to `~/.cursor/plugins/local/nustack` and run Developer: Reload Window, where local plugin imports are allowed; to update, replace the folder and reload.

Each host's link says how to update.

## Use

To have every session in a project work in nus-mode, add this line to the project's AGENTS.md:

```markdown
Work in this repository in nus-mode: load the skill before you start.
```

Claude Code reads AGENTS.md only where no CLAUDE.md, `.claude/CLAUDE.md` or `CLAUDE.local.md` sits in the working directory or above it, [as its docs say](https://code.claude.com/docs/en/memory#when-claude-code-reads-agents-md), so make a project's CLAUDE.md a symlink to AGENTS.md, once AGENTS.md holds any instructions CLAUDE.md held. The [new-project playbook](plugin/skills/nus-mode/playbooks/new-project.md) writes AGENTS.md beside a CLAUDE.md symlinked to it, and symlinks `.claude/skills` to `.agents/skills`, where it keeps the project's own skills.

To use nus-mode for one task, invoke it with the task:

```text
/nustack:nus-mode Start a CLI that tracks expenses.
/nustack:nus-mode Investigate why the nightly export times out.
/nustack:nus-mode Align this repository.
/nustack:nus-mode Polish this repository.
/nustack:nus-mode Audit this repository.
```

| Host | Invoke |
| :-- | :-- |
| Claude Code, Devin | `/nustack:nus-mode <task>` |
| Cursor | Type `/`, pick nus-mode, then type the task; in the Agents Window or the CLI, press Option+Enter, Alt+Enter on Windows, instead of Enter to [keep it for the task](https://cursor.com/docs/agent/prompting#custom-modes) |
| OpenCode | `@nus-mode <task>` |

It asks you about each open decision until you tell it to [work on its own](plugin/skills/nus-mode/SKILL.md#standing-rules); even then, unless you or the project's rules allow it, it asks before an action outside its own work and pull request that others see or it cannot undo, such as a merge.

## Skills

Each row holds the skill's own description. nus-mode reads its principle skills, which together form the Zen of Nusnus, and its language skills itself; the model never loads them on its own.

<details>
<summary>nus-mode, its principles and its languages</summary>

| Skill | Description |
| :-- | :-- |
| [nus-mode](plugin/skills/nus-mode/SKILL.md) | Builds software to a senior engineer's bar. Use when asked for nus-mode, or when the project's AGENTS.md turns it on. |
| [principle-naming](plugin/skills/principle-naming/SKILL.md) | Names that say what a thing is in the domain. |
| [principle-dry](plugin/skills/principle-dry/SKILL.md) | One home for every piece of knowledge. |
| [principle-fail-fast](plugin/skills/principle-fail-fast/SKILL.md) | Code that fails where a wrong state is first detected, with an error that says how to recover, and holds an expected absence in its type. |
| [principle-boundaries](plugin/skills/principle-boundaries/SKILL.md) | Outside data parsed once, where it enters, strictly into the project's domain types. |
| [principle-types](plugin/skills/principle-types/SKILL.md) | Types that hold the contract, so an invalid value cannot exist. |
| [principle-design](plugin/skills/principle-design/SKILL.md) | A design built from proven patterns and SOLID objects that put behaviour with the data it serves, short because it fits the problem. |
| [principle-layout](plugin/skills/principle-layout/SKILL.md) | A folder and file layout that shows the design, and one order inside every file. |
| [principle-dependencies](plugin/skills/principle-dependencies/SKILL.md) | Dependencies that point one way, onto the language's own tools and stable public APIs, one home for each library, the runtimes a project targets, floating ranges with a pinned lockfile, and deciding logic kept pure. |
| [principle-resilience](plugin/skills/principle-resilience/SKILL.md) | Code that comes through failure and load by its design: each failure absorbed by its structure or left to fail, each limit known and accepted. |
| [principle-long-term](plugin/skills/principle-long-term/SKILL.md) | Changes built to last, so they are done once. |
| [principle-deterministic-tests](plugin/skills/principle-deterministic-tests/SKILL.md) | Tests that each fail when, and only when, the behaviour they guard breaks. |
| [principle-self-explanatory-code](plugin/skills/principle-self-explanatory-code/SKILL.md) | Code that explains itself, and docs for what it cannot say. |
| [principle-pr-descriptions](plugin/skills/principle-pr-descriptions/SKILL.md) | PR descriptions a reviewer takes in at a glance. |
| [principle-responses](plugin/skills/principle-responses/SKILL.md) | Replies, status updates, questions and reports a person takes in at a glance. |
| [language-python](plugin/skills/language-python/SKILL.md) | Python's tools, and where Python changes how a principle applies. |

</details>

Steph Ango's [obsidian-skills](https://github.com/kepano/obsidian-skills) ship unchanged, and each loads when a task matches its description.

<details>
<summary>The Obsidian skills</summary>

| Skill | Description |
| :-- | :-- |
| [obsidian-markdown](plugin/skills/obsidian-markdown/SKILL.md) | Create and edit Obsidian Flavored Markdown with wikilinks, embeds, callouts, properties, and other Obsidian-specific syntax. Use when working with .md files in Obsidian, or when the user mentions wikilinks, callouts, frontmatter, tags, embeds, or Obsidian notes. |
| [obsidian-bases](plugin/skills/obsidian-bases/SKILL.md) | Create and edit Obsidian Bases (.base files) with views, filters, formulas, and summaries. Use when working with .base files, creating database-like views of notes, or when the user mentions Bases, table views, card views, filters, or formulas in Obsidian. |
| [json-canvas](plugin/skills/json-canvas/SKILL.md) | Create and edit JSON Canvas files (.canvas) with nodes, edges, groups, and connections. Use when working with .canvas files, creating visual canvases, mind maps, flowcharts, or when the user mentions Canvas files in Obsidian. |
| [obsidian-cli](plugin/skills/obsidian-cli/SKILL.md) | Interact with Obsidian vaults using the Obsidian CLI to read, create, search, and manage notes, tasks, properties, and more. Also supports plugin and theme development with commands to reload plugins, run JavaScript, capture errors, take screenshots, and inspect the DOM. Use when the user asks to interact with their Obsidian vault, manage notes, search vault content, perform vault operations from the command line, or develop and debug Obsidian plugins and themes. |
| [defuddle](plugin/skills/defuddle/SKILL.md) | Extract clean Markdown from HTML pages with Defuddle CLI. |
| [knap](plugin/skills/knap/SKILL.md) | Render Markdown from templates and structured data using Knap CLI. Use when the user asks to apply a Knap template, turn JSON or CSV data into notes, batch-generate Markdown files, or format Defuddle output into a note. |

</details>

## Contributing

Read [AGENTS.md](AGENTS.md) first: it holds the rules for changing nustack and how to run every check. [REVIEW.md](REVIEW.md) lists what review holds each pull request to.

## Acknowledgements

- [pstack](https://github.com/cursor/plugins/tree/main/pstack) gave nustack its name and its mode-and-playbooks shape.
- Matt Pocock's [writing-for-agents](.agents/skills/writing-for-agents/SKILL.md) shapes how nustack words its skills.

## License

[MIT](LICENSE) © Tomer Nosrati
