---
name: principle-pr-descriptions
description: "PR descriptions a reviewer takes in at a glance."
disable-model-invocation: true
triggers: [user]
---

# PR descriptions

A PR description is a page a reviewer scans to judge a change: the same parts in the same places on every pull request, about one screen tall at any size of change. It is a [response](../principle-responses/SKILL.md) too, and where the two differ, these rules win.

- **Start from the project's PR template,** whose layout and look win over the defaults below, and keep only the parts the change has.
- **Open on what the change does for its reader,** in a line, before how it does it.
- **Give each part, in the fold too, a heading that says what it holds,** so its list opens straight under it.
- **Above the fold, show the change in four parts:** what changed, as a few one-line changes a reader meets; what could break and how to undo it, only once the risk is more than low, since every change risks something; what to read first and which feedback helps most; and the steps after the merge as a task list.
- **Fold the rest into one collapsed section whose summary names what it holds:** each check with its run linked and its result, and each thing not checked; the files, those to read first in reading order; for a change people see, screenshots before and after; and each decision a reviewer could take otherwise, with its reason, since the code does not record why.
- **Put what outgrows the fold in one linked comment,** such as a check's full output, longer reasoning, and the names of the rules and sources behind a reason; the page gives each reason in plain words.
- **Make images and colours readable to every reader:** an image states its fact in its alt text, so the page reads the same where images do not load and through a screen reader. Text on a colour keeps a contrast of 4.5:1 or more.
- **Link the issue the change resolves with its closing keyword,** which closes it only once the pull request merges into the default branch.
- **Use only what the review site renders in a description,** checked in its light and dark themes.
- **Keep alerts for a breaking change** the reviewer must prepare for.
- **Fix a reader's friction by cutting, restructuring or moving detail down,** never by adding explanation to the page.
- **Keep it true at the head:** update it whenever a push makes any of it false.
