---
name: principle-dry
description: "DRY, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# DRY

Every piece of knowledge, such as a rule, value, format or decision, has one home that everything needing it refers to, so a change is one edit and leaves no copy to drift.

- **Find the home before you write.** Look for where the project already holds the knowledge you are about to write, and refer to that.
- **Extend the mechanism before adding one.** Before adding a codepath, type, setting, helper or parser, find the project's mechanism that already does that work, and extend it where a small change suffices. [Design](../principle-design/SKILL.md)'s SOLID rule governs how a new variant joins it.
- **Leave documented defaults unwritten.** Code and config never restate a value a library, tool, service or spec documents as its default, unless a comment beside it says why the project depends on that value.
- **Derive what you would copy.** When two places need the same knowledge in different forms, derive one from the other, or both from one source.
- **Merge by reason to change.** Pieces that change for the same reason are one piece of knowledge; lookalikes that change for different reasons stay separate.
- **Hold required copies equal.** When tools or hosts each read their own copy of a fact, have one check fail whenever the copies differ.
