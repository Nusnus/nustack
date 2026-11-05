---
name: principle-pr-descriptions
description: "PR descriptions a reviewer takes in at a glance."
disable-model-invocation: true
triggers:
  - user
---

# PR descriptions

A PR description lets a reviewer reach a confident verdict without redoing the work: what to judge, where to look, what was decided and why, what was checked, what it risks and what they must do. The eye takes in position, colour, shape and icons before it reads a word, so make the cues alone answer every question but why; prose gives the reasons.

- **Size it to the change.** A change the diff explains in a minute gets its lead and the table of its verdict's facts. Other parts join only when the change has them; the whole fits about two screens, its overflow in a `<details>` fold or link.
- **Lead with the change and its reason**, in one or two sentences a reader new to the project can follow, and link the issue it resolves with a closing keyword, such as `Fixes #12`, so its merge into the default branch closes the issue.
- **Put the verdict's facts in a table** under the lead, one per row below a plain header row: the feedback wanted first, then each check with its result, then the risk, or "none known".
- **Give each cue one meaning.** ✅ done, ⏳ pending, ⚠️ needs attention and ❌ failed mean only those states, first in their cell or line, so a column reads at a glance. Each heading opens with one other emoji. A diagram reserves green, amber and red for those states, and gives each role one colour and shape throughout the description.
- **Put the headings in the order the reviewer works:** where to look, one heading per idea, the decisions, then the steps after the merge. Where to look lists the files that carry the design in reading order, and the rest in one line. Steps after the merge are a task list the code host tracks.
- **Give each decision its reason**, and any alternative it beat. Several decisions are a table with a column for why.
- **Show a change users see:** before-and-after screenshots or a short recording, side by side in a table.
- **Draw what prose would take longer to say.** What branches, loops or crosses between actors is a Mermaid diagram that fits the page width: at most four boxes across, two or three words a line, two lines a box. A linear sequence is a numbered list, even when a step is a pass-or-fail check.
- **Compare in a table:** across two or more dimensions, and behaviour or configuration before and after.
- **Write one fact per sentence** and one idea per paragraph of under fifty words, with its key phrase in bold. A longer paragraph becomes a list, a table or a fold.
- **Show code as code:** a short `diff` for a before and after of code, or pseudocode beside the interface it changes. Every block names its language and keeps lines under about ninety characters.
- **Alert only what the reviewer must act on:** one alert, at most two, never adjacent. `[!IMPORTANT]` holds a decision they own, and `[!WARNING]` a breaking change they must prepare for.
- **Link the evidence where it lives:** each check's row links the report of its run, and each thing not checked has its own ⏳ or ⚠️ row. Evidence with no home of its own sits in a `<details>` under the table.
- **Keep it true at the head:** update it when a push makes any of it false.
