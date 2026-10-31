---
name: nus-mode
description: nus-mode builds software to a senior engineer's bar. Use when asked for nus-mode, or when the project's AGENTS.md turns it on.
---

# nus-mode

## Goal

Keep the friction rate low: how often a reader new to the code has to stop while they understand it, find their way around it and change it. Each such stop is a friction point:

- a name whose meaning they have to look up;
- a fact the text neither states nor links to;
- a part that works differently from its neighbours for no stated reason;
- a choice whose reason is written nowhere;
- behaviour that surprises them;
- a step they have to do by hand that a tool could do.

Code with a low friction rate reads as if one careful engineer wrote all of it. Every principle serves this goal.

- **Judge the friction rate from a cold read.** Before you finish, read what you changed as someone who has never seen the project, list each friction point that reader would meet, and fix each one at its cause, until a cold read finds none.
- **Break ties by the friction rate.** When two principles pull different ways, choose the option that leaves fewer friction points, and name both principles and the choice in the PR description or your reply.

## Standing rules

- **The project's own rules come first.** Where the project's `AGENTS.md` or standards conflict with a principle, follow the project and name the conflict in your reply.
- **Principles are strong defaults.** A departure from one gets a one-sentence reason in the PR description or your reply, naming the principle it departs from.
- **Name the principle behind each design decision**, and the choice it changed, in the PR description or your reply. Cite only principles whose file you read in full.
- **The user's request sets the scope.** The request decides what changes, and the principles apply in full to everything that changes.
- **Give every time and ETA in the user's local time zone**, with the zone named. When that zone is unknown, give times as you otherwise would, still naming the zone.

## Playbooks

Match the task to one playbook, open it, and copy its numbered steps into your todo list before any other item. A step you leave out stays in the list as `skip: <one-line reason>`. When no playbook fits, do the task under the standing rules and the principles it triggers, and name in your reply the kind of task no playbook covered.

| The task | Playbook |
| --- | --- |
| Start a new project | [new project](playbooks/new-project.md) |
| Investigate a problem | [investigate](playbooks/investigate.md) |

## Principles

Each principle is a skill of its own. Read its `SKILL.md` in full, as a file, before you apply it, so this mode stays loaded. Each one applies when:

- [naming](../principle-naming/SKILL.md): you name anything.
- [DRY](../principle-dry/SKILL.md): you write a value, a rule, a format or a decision.
- [fail fast](../principle-fail-fast/SKILL.md): you write code that checks a value or a state, or that raises, catches, reports or recovers from an error.
- [boundaries](../principle-boundaries/SKILL.md): data enters the system from outside it, or a value may be absent.
- [types](../principle-types/SKILL.md): you design a type, a signature or a set of allowed values, or write code that branches on one.
- [layout](../principle-layout/SKILL.md): you add, move or split folders and files.
- [dependencies](../principle-dependencies/SKILL.md): you make one part depend on another, or use a third-party library.
- [long term](../principle-long-term/SKILL.md): you change anything: code, docs, tests or config.
- [self-explanatory code](../principle-self-explanatory-code/SKILL.md): you write or change code, or the docs that describe it.
- [PR descriptions](../principle-pr-descriptions/SKILL.md): you write or update a PR description.
