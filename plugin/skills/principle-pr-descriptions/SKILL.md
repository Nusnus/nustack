---
name: principle-pr-descriptions
description: "PR descriptions a reviewer takes in at a glance."
disable-model-invocation: true
triggers:
  - user
---

# PR descriptions

A PR description is a page a person scans to judge a change, so it looks like a well-designed app screen: calm, spacious, the same parts in the same places on every pull request, and about one screen tall at any size of change. It tells a reviewer what changed, what it risks, where to start, what the checks found, which decisions they could take otherwise and what follows the merge. Word it as [responses](../principle-responses/SKILL.md) says; the rules below set the page, and where the two differ, these rules win. The owner set its look; the visual rules below carry the owner's taste as their reason.

- **Open with a centered header**, a `<div align="center">` block that holds, in this order:
  - a `###` headline that names the change in a few plain words;
  - one line that says what the change does for its reader, as [Google's guide to CL descriptions](https://google.github.io/eng-practices/review/developer/cl-descriptions.html) asks a description to open on a short summary of what is being done;
  - one row of status badges;
  - `<sub>Closes #12</sub>`, only when the pull request resolves an issue, with that issue's number, which [closes that issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/linking-a-pull-request-to-an-issue) when the pull request merges into the default branch. An image's text closes nothing, so this line stays text.
- **Show risk, checks and size as three badges**, in that order, each a [shields.io static badge](https://shields.io/badges/static-badge) in `flat-square` style, such as `![Risk: low](https://img.shields.io/badge/risk-low-1f883d?style=flat-square)`:
  - `risk` reads `none`, `low`, `medium` or `high`;
  - `checks` counts the checks that passed, then names each other check by its state, such as `5 passed, CI not run`;
  - `size` counts the files the change touches, such as `25 files`.
- **Colour each badge by its state:** `1f883d` green for no or low risk and for every check passed, `9a6700` amber for medium risk and for a check pending or not run, `cf222e` red for high risk and for a failed check, and `6e7781` grey for size. Each keeps white text above the 4.5:1 contrast [WCAG](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) asks of text, and a badge brings its own background, so it reads the same in GitHub's light and dark themes. The words carry the state too, since WCAG's [use of colour](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html) has colour never be the only means of conveying information.
- **Give each badge alt text that states its fact**, such as `Risk: low` or `Checks: 5 passed, CI not run`, since WCAG's [non-text content](https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html) gives an image a text alternative that serves its purpose. A screen reader reads it, and GitHub shows it where shields.io serves no image, so the page reads the same without images.
- **Write a badge's words as shields.io's URL takes them:** `%20` for each space, `--` for each dash and `__` for each underscore, as its static badge page says.
- **Follow with four sections, in this order, each only when the change has it**, each under a plain `####` heading: What changed, Risk, Review first and After merge. Each keeps its name and place on every pull request, so a reviewer finds each part by where it sits.
  - What changed lists at most five one-line bullets, each a change a reader meets, so a reader has a sense of what is changing without reading the whole change, as Google's guide asks.
  - Risk says in at most two lines what could break and how to undo it, when the badge reads above `low`.
  - Review first names what to read first and what feedback would help most, as GitHub's [helping others review your changes](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/getting-started/helping-others-review-your-changes) asks.
  - After merge is a task list, which GitHub [tracks](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#task-lists) as each box is ticked.
- **Write the page above the fold in plain words:** name a file, command or setting in words, with no code span, bold or emoji there, so each line reads as a sentence. The headline and headings already mark what a reviewer must see, which leaves bold nothing to mark.
- **Fold the rest under one `<details>`** at the end, whose `<summary>` names what it holds, such as `Checks, files and 13 decisions`, since GitHub's [collapsed sections](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections) hold details not every reader needs. Inside it, under `####` headings and in this order, put:
  - Checks: one bullet per check the badge counts, its name linked to its run and then its result, and one bullet for each thing not checked;
  - Files: each file by its path, in reading order, then the rest in one bullet;
  - Decisions: one bullet per decision a reviewer could take otherwise, the choice and then its reason, since Google's guide has a description record decisions the source code does not show;
  - anything else the change needs, such as before-and-after screenshots or proof;
  - last, when anything outgrows the page, one bullet that links a comment on the pull request holding it and says what it holds: a check's full output, a measurement, a decision's longer reasoning, and the rule names and citations, which stay off the page.
  The fold keeps to bullets and plain words too: a path or command reads as plain text, and a code span holds only text that must stay literal, such as a placeholder in angle brackets or text quoted from elsewhere.
- **Use a table only for three or more facts per item**, with at most three columns, since Google's [tables](https://developers.google.com/style/tables) guide keeps lists for simpler data; checks, files and decisions each carry two facts, so they are lists.
- **Keep the page one screen tall at any size.** A paragraph holds at most two lines, and each bullet in the fold one line. A large change keeps the same page: its detail goes in the fold, and whatever outgrows a one-line bullet goes in the linked comment.
- **Keep sources and rule names off the page.** Give each decision's reason in plain words, since a name a reviewer has to look up is a [friction point](../nus-mode/SKILL.md#goal).
- **Fix a reader's friction by cutting, restructuring or moving detail into the fold or a linked comment**, never by adding explanation to the page, so the page stays one screen.
- **Use only what GitHub renders in a description**, checked through GitHub's Markdown rendering in its light and dark themes. Add one [`[!WARNING]`](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts) alert under the header only for a breaking change the reviewer must prepare for, since GitHub keeps alerts for what is crucial and limits their number.
- **Keep it true at the head:** update it when a push makes any of it false.
