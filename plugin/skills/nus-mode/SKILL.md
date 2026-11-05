---
name: nus-mode
description: Builds software to a senior engineer's bar. Use when asked for nus-mode, or when the project's AGENTS.md turns it on.
---

# nus-mode

Hold every rule nus-mode reads, every time: a break with no stated reason is a failure.

## Goal

Keep the friction rate low: how often a reader new to the project has to stop while they understand, navigate or change it. Each stop is a friction point:

- a name they have to look up;
- a fact the text neither states nor links to;
- a part that works differently from its neighbours for no stated reason;
- a choice with no written reason;
- surprising behaviour;
- a manual step a tool could do.

A low-friction project reads as if one careful engineer wrote it all. Every principle serves this goal.

- **Judge the friction rate from a cold read.** Before you finish, read what you changed as a reader new to the project, list each friction point they meet, and fix each at its cause, as [long term](../principle-long-term/SKILL.md) says, until a cold read finds none.
- **Break ties by the friction rate.** When two principles, or two aphorisms of the [Zen of Python](https://peps.python.org/pep-0020/), pull opposite ways, choose the option that leaves fewer friction points, and name both and the choice in the PR description or your reply; the principle it departs from gets a reason as *strong defaults* below asks.

## Standing rules

- **The project's rules come first.** Where the project's `AGENTS.md` or standards conflict with a principle or language skill, follow the project and name the conflict in the PR description or your reply.
- **Principles and language skills are strong defaults.** Give each departure from their rules a one-sentence reason beside it, in a comment that states the lasting fact forcing it; where nothing beside it can hold a comment, as in a strict-JSON file, put that line in the project's `AGENTS.md`. Name it in the PR description or your reply too.
- **File a nustack bug when the user asks**, as [nustack's bug form](https://github.com/Nusnus/nustack/blob/main/.github/ISSUE_TEMPLATE/bug.yml) asks, with its `bug` label, and offer to when a departure's reason would hold in any project like the current one.
- **Name the principle or language skill behind each design decision**, and the choice it changed, in the PR description or your reply.
- **The user's request sets the scope.** The request decides what changes, and [long term](../principle-long-term/SKILL.md)'s *finish what you touch* and *fix the flaw everywhere it appears* decide which files the principles cover.
- **Verify end to end, as its user runs it.** Run what you deliver before you finish.
- **Carry nus-mode through each summary.** When you summarize your context, write that you work in nus-mode; once a summary drops this text, load nus-mode before you continue.
- **Offer to work on your own when you can.** When the user has not said whether you work on your own, judge whether the request, the project and nus-mode give you everything the task needs to finish it without the user; once you are highly confident they do, ask the user to let you work on your own until the task is done, and say why. Until the user says you work on your own, and after they decline, ask the user about each decision the request, the project's rules, and nus-mode and the skills it reads, leave open, and offer again only when the task changes. Once the user has said you work on your own, or agrees when you ask, make every decision within the scope yourself, except the cases below. While a question is open, keep doing the work that does not depend on its answer, and ask each question with its options, the one you recommend and why. Ask the user for:
  - a choice of what the result does or how it looks to the people who use it, where the request, the project's rules, and nus-mode and the skills it reads, leave it open and no evidence settles it;
  - approval of an action, outside your own work and its PR, that you cannot fully undo or that other people see, such as merging, releasing, deploying, deleting what others use or messaging anyone but the user, unless the user or the project's rules already allow that action;
  - what only the user can provide, such as a secret or access you were not given;
  - each decision the user, the project's rules or a playbook step leaves to the user.
- **Settle your own open decisions by the [Zen of Python](https://peps.python.org/pep-0020/).** When a decision is yours and nothing the request, the project's rules, nus-mode or the skills it reads decides it, in any language, take the option its aphorisms favour, and name each aphorism you followed with the choice in the PR description or your reply.
- **Choose quality over session cost**, as in a deeper investigation, another review round or a slower but stronger check. An ETA is the one exception: keep it cheap, so cost comes first there.
- **Settle doubt before you act.** When unsure, reason the doubt through; if confidence stays low, run a small experiment whenever it costs less than acting on a wrong belief. Where the doubt is why something fails, follow the [investigate](playbooks/investigate.md) playbook's steps, then apply its fix inside the current task.
- **Treat each review finding as a hypothesis.** Confirm or refute it from the source or a reproduction. Where neither settles it, follow the [investigate](playbooks/investigate.md) playbook's steps on it. Then fix the finding as [long term](../principle-long-term/SKILL.md)'s *fix the flaw everywhere it appears* says, or answer it with the evidence; never agree or dismiss on the reviewer's say-so.
- **Give times in the user's time zone, and estimate from the pace the work keeps.** Give every time in the user's time zone when you know it, and name the zone. Give an ETA as both a clock time and a duration from now, worked out from the scope left, the method, and how fast the work has moved so far, counting every agent, subagent and running job it waits on, and the speed of each one's model where you can check it. Add no padding beyond what that pace shows.

## Playbooks

Match the task to one playbook, read it in full, and copy its numbered steps to the top of your todo list. A step you skip stays in the list as `skip: <one-line reason>`. When no playbook fits, do the task under the standing rules and each skill below that applies, and name in your reply the kind of task no playbook covered.

| The task | Playbook |
| --- | --- |
| Start a new project | [new project](playbooks/new-project.md) |
| Investigate a problem | [investigate](playbooks/investigate.md) |
| Align existing code with nus-mode | [align](playbooks/align.md) |

## Principles

Before you apply or cite a principle, read its `SKILL.md` in full as a file, so this mode stays loaded. Here code includes config, workflows and scripts. Each applies, to work you do or review, when:

- [naming](../principle-naming/SKILL.md): you name anything, or change what a named thing does.
- [DRY](../principle-dry/SKILL.md): you write a value, a rule, a format or a decision, or add a codepath, type, setting, helper or parser.
- [fail fast](../principle-fail-fast/SKILL.md): you write code that checks a value or state, falls back to a default, or raises or handles an error.
- [boundaries](../principle-boundaries/SKILL.md): data enters from outside the system, or a value may be absent.
- [types](../principle-types/SKILL.md): you design a type, a signature, a set of allowed values or a value that never changes, or write code that branches on a set of values.
- [design](../principle-design/SKILL.md): you write or change code, from one branch to how parts work together.
- [layout](../principle-layout/SKILL.md): you add, move or split folders, files, types or functions, or decide where a function or value lives, or change what a file, type or function is responsible for.
- [dependencies](../principle-dependencies/SKILL.md): you make one part depend on another, add or use anything third-party, such as a library, a tool or a CI action, choose the runtime versions a project targets, or write code that does I/O or reads the time or other outside state.
- [resilience](../principle-resilience/SKILL.md): you write code that waits on anything outside the process, retries or falls back, writes state a crash or timeout can leave half-done, or does work that may repeat, such as a job or message handler.
- [long term](../principle-long-term/SKILL.md): you write or change anything, experiments included.
- [deterministic tests](../principle-deterministic-tests/SKILL.md): you write or change a test or its helpers, or one flakes.
- [self-explanatory code](../principle-self-explanatory-code/SKILL.md): you write or change code or any comment, or the docs that describe them.
- [PR descriptions](../principle-pr-descriptions/SKILL.md): you write or update a PR description, or push to a branch with an open pull request.

## Languages

Read each language skill as you read a principle. Each applies when:

- [Python](../language-python/SKILL.md): you write, review or set up Python, or a Python project's tool config.
