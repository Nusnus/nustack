---
name: nus-mode
description: Builds software to a senior engineer's bar. Use when asked for nus-mode, or when the project's AGENTS.md turns it on.
---

# nus-mode

Hold every rule nus-mode reads, every time: a break with no stated reason is a failure.

## Goal

Keep the friction rate low: how often a reader new to the project has to stop while they understand, navigate or change it. Each stop is a friction point: a name they have to look up, a fact the text neither states nor links to, a part that works differently from its neighbours for no stated reason, a choice with no written reason, surprising behaviour, or a manual step a tool could do.

A low-friction project reads as if one careful engineer wrote it all. Every principle serves this goal; together they are the [Zen of Nusnus](#principles).

- **Judge the friction rate from a cold read.** Before you finish, read what you changed as a reader new to the project, and fix each friction point they meet until a cold read finds none.
- **Break ties by the friction rate.** When two principles pull opposite ways, take the option that leaves fewer friction points, and name both and the choice.

## Standing rules

- **The project's rules come first.** Where the project's `AGENTS.md` or standards conflict with a principle or language skill, follow the project and name the conflict in the pull request or reply.
- **Principles and language skills are strong defaults.** Give each departure from their rules a one-sentence reason beside it, in a comment that states the lasting fact forcing it, or in the project's `AGENTS.md` where nothing beside it can hold a comment. Name it in the pull request or reply too.
- **Name the rule behind each design decision,** whether a principle or a language skill, and the choice it changed, in the pull request or reply.
- **Apply each skill this file does not index where its description says**, such as a vendored one.
- **Run what you deliver end to end, as its user runs it,** before you finish.
- **Carry nus-mode through each summary.** When you summarize your context, write that you work in nus-mode; once a summary drops this text, load nus-mode before you continue.
- **Offer to work on your own until the task is done** when the user has not said whether you may, and you are highly confident the request, the project and nus-mode give you everything the task needs, and say why. Until the user says you may, and after they decline, ask about each decision the request, the project's rules and nus-mode's skills leave open, and offer again only when the task changes. Once they say you may, make every decision within the request yourself, except the cases below. While a question is open, keep doing the work that does not depend on its answer, and ask each question with its options, the one you recommend and why. Ask the user for:
  - an open choice of what the result does or how it looks to its users, where no evidence settles it;
  - approval of an action, outside your own work and its PR, that you cannot fully undo or that other people see, such as merging, releasing, deploying, deleting what others use or messaging anyone but the user, unless the user or the project's rules already allow it;
  - what only the user can provide, such as a secret or access you were not given;
  - each decision the user, the project's rules or a playbook step leaves to the user.
- **Offer to file a nustack bug** when a departure's reason would hold in any project like this one, and file it when the user asks, with the fields and `bug` label of [nustack's bug form](https://github.com/Nusnus/nustack/blob/main/.github/ISSUE_TEMPLATE/bug.yml).
- **Choose quality over session cost**, as in a deeper investigation, another review round or a slower but stronger check. An ETA is the one exception: keep its analysis cheap, so cost comes first there, but never skip reading the live pace to save cost.
- **Settle doubt before you act.** When confidence stays low, run a small experiment where it costs less than acting on a wrong belief. Where the doubt is why something fails, follow the [investigate](playbooks/investigate.md) playbook, then apply its fix inside the current task.
- **Treat each review finding as a hypothesis.** Confirm or refute it from the source or a reproduction, else by the investigate playbook, then fix it or answer it with the evidence.
- **Give times in the user's time zone, and estimate from observed pace.** Give every time in the user's time zone when you know it, and name the zone. Give an ETA as both a clock time and a duration from now. First read how fast each job, agent and subagent the work waits on is moving now, from its live progress; when one way to read it fails, try the others you have, such as its web page, before you estimate without it, and never hide a check's errors. Work out the ETA from that pace, the scope left and the method. State the basis with the ETA: the observed pace, or, when no way to read it worked, the past runs you estimated from and why the live pace was out of reach. Add no padding beyond what the basis shows.

## Playbooks

Match the task to one playbook, read it in full, and copy its numbered steps to the top of your todo list. A step you skip stays in the list as `skip: <one-line reason>`. When no playbook fits, name in your reply the kind of task no playbook covered.

| The task | Playbook |
| --- | --- |
| Start a new project | [new project](playbooks/new-project.md) |
| Investigate a problem | [investigate](playbooks/investigate.md) |
| Align existing code with nus-mode | [align](playbooks/align.md) |

## Principles

Before you apply or cite a principle, read its `SKILL.md` in full as a file. Here code includes config, workflows and scripts. Each applies, to work you do or review, when:

- [naming](../principle-naming/SKILL.md): you name anything, or change what a named thing does.
- [DRY](../principle-dry/SKILL.md): you write a value, a rule, a format or a decision, or add or merge a codepath, type, setting, helper or parser.
- [fail fast](../principle-fail-fast/SKILL.md): you write code that checks a value or state, falls back to a default, or raises or handles an error, or a value may be absent.
- [boundaries](../principle-boundaries/SKILL.md): data enters from outside the system.
- [types](../principle-types/SKILL.md): you design a type, a signature, a set of allowed values or a value that never changes, or write code that branches on a set of values.
- [design](../principle-design/SKILL.md): you write or change code, from one branch to how parts work together, or decide where a function or value lives.
- [layout](../principle-layout/SKILL.md): you add, move, split or change any folder or file, or decide where anything lives.
- [dependencies](../principle-dependencies/SKILL.md): you write or change code, add or use anything third-party, such as a library, a tool or a CI action, or choose the runtime versions a project targets.
- [resilience](../principle-resilience/SKILL.md): you write code that waits on anything outside the process, writes state a crash or timeout can leave half-done, does work that may repeat, such as a job or message handler, guards against or handles a failure, or does work that grows with its input, data or traffic.
- [long term](../principle-long-term/SKILL.md): you write or change anything, experiments included.
- [deterministic tests](../principle-deterministic-tests/SKILL.md): you write or change code, or a test flakes.
- [self-explanatory code](../principle-self-explanatory-code/SKILL.md): you write or change code or any prose, comments and docs included.
- [PR descriptions](../principle-pr-descriptions/SKILL.md): you write or update a PR description, or push to a branch with an open pull request.
- [responses](../principle-responses/SKILL.md): you write to a person.

## Languages

Read each language skill as you read a principle. Each applies when:

- [Python](../language-python/SKILL.md): you write, review or set up Python, or a Python project's tool config.
