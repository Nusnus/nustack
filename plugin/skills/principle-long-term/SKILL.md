---
name: principle-long-term
description: "Long term, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# Long term

Build every change to stand for years, whatever the task's size and whatever state the surrounding code is in. Work built to last is done once; work built for today comes back to you.

- **Give every file one consistent internal order.** Code and tests keep it as strictly as config and docs: sections, keys, imports, definitions and members sit in the order the file's ecosystem defines, enforced by its tools where they can. Where the ecosystem defines none, the project picks one order, writes it down with its other standards, and every file follows it. Readers find each thing where they expect it, and diffs show only what changed.
- **Use the language's own mechanisms.** Reach for what the language, its standard library and its standard tools already provide, before writing your own. They keep working as the language moves on.
- **Build on what is public and documented.** Stable public APIs and documented behaviour survive upgrades.
- **Remove each problem at its cause.** Change the place where the problem starts, so it cannot happen again.
- **Finish what you touch.** Settle every nitpick in the code, docs, tests and config you change, in the same change. A nitpick left today is a return visit tomorrow.
- **Hold tests to the code's standard.** Tests follow the same names, structure, imports and lint rules as the code they test, departing only where the test framework's own conventions require it.
- **Give every test a way to fail.** Each test asserts behaviour the code could get wrong, observed through the code's public interface. Its expected value comes from what the behaviour promises, worked out apart from how the code computes it.
- **Move everything a change implies.** Docs, tests, names and examples change in the same commit as the code they describe.
- **Write prose that stays true.** A docstring, comment, doc, changelog entry or skill says only what stays true until its subject's purpose changes, and points to the home of each count, list, step, default, version or value it needs, as [DRY](../principle-dry/SKILL.md) says.
- **Write for a reader who never saw the conversation.** State each rule in general terms and in your own words, and keep an example from the conversation only when it generalises.
- **Keep working material in the PR description or the session.** Plans, specs, design notes and task checklists serve the work in progress. The repository holds what stays true after the work lands.
- **Done means durable.** A change is done when nothing in it needs another visit.
