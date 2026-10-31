---
name: principle-pr-descriptions
description: "PR descriptions, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# PR descriptions

A PR description lets a reviewer reach a confident verdict without redoing the work: what to judge, where to look, what was decided and why, what was checked, what it risks and what they must do. The eye takes in position, colour, shape and icons at a glance, before it reads a word, so each visual cue carries one meaning, and the cues alone answer every question but why. Prose carries the reasons, for the reader who stops to read them.

- **Size it to the change.** A change the diff explains in a minute gets its lead and a table of its checks and its risk. Every other part joins only when the change has it, and the whole fits about two screens, with the rest in a fold or a link.
- **Lead with the change and its reason**, in one or two sentences a newcomer to the project can follow, and link the issue it resolves.
- **Put the verdict's facts in a table** under the lead, below a plain header, one per row: the feedback wanted first, then each check with what passed, then the risk, or "none known".
- **Give each cue one meaning.** ✅ done, ⏳ pending, ⚠️ needs attention and ❌ failed mark state alone, first in their cell or line, so a column of them reads at a glance. Each heading opens with one other emoji as its signpost. A diagram keeps green, amber and red for those states, and gives each role one colour and one shape throughout the description.
- **Make the headings a map, in the order the reviewer works:** where to look, then one heading per idea, then the decisions, then the steps after the merge. Where to look lists the files that carry the design in reading order, and the rest in one line.
- **Give each decision its reason**, and the alternative it beat when there was one. Several decisions are a table with a column for why.
- **Show what users see:** a change to what users see gets a before-and-after screenshot or a short recording, side by side in a table.
- **Draw what prose would take longer to say.** What branches, loops or crosses between actors is a Mermaid diagram that reads at the page's width: at most four boxes across, two or three words a line, two lines a box. A sequence, even one with a check that passes or fails, is a numbered list.
- **Compare in a table:** a comparison across two or more dimensions, and a before and after of behaviour or configuration.
- **Write one fact per sentence** and one idea per paragraph, in under fifty words, with bold on the phrase that matters. A longer one becomes a list, a table or a fold.
- **Show code as code:** a short `diff` for a before and after of code, or pseudocode beside the interface it changes. Every block names its language and keeps its lines under about ninety characters.
- **Alert only what the reviewer must act on:** one alert, two at most, never two in a row. `[!IMPORTANT]` holds a decision they own, and `[!WARNING]` a breaking change they must prepare for. Steps after the merge are a task list, so the code host tracks them as checkboxes.
- **Link the evidence where it lives:** each check's row links the run that produced it, whose report holds its logs and full output, and each thing not checked has its own ⏳ or ⚠️ row. Evidence with no home of its own sits in a `<details>` under the table.
- **Keep it true at the head:** a description holds what is true at the commit it describes, so when a push changes what it says, update it.
