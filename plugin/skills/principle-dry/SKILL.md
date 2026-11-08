---
name: principle-dry
description: "One home for every piece of knowledge."
disable-model-invocation: true
triggers: [user]
---

# DRY

Every piece of knowledge, such as a rule, value, format or decision, has one home, and everything that needs it, in any form, refers to it or derives from it.

- **Extend the project's mechanism before adding another.** Where a codepath, type, setting, helper or parser already does the work and a small change suffices, extend it.
- **Keep lookalikes apart.** Pieces that look alike but change for different reasons stay separate.
- **Leave documented defaults unwritten.** Code and config leave out each value a library, tool, service or spec documents as its default.
- **Check each copy a reader needs.** Where each reader needs its own copy of a fact, a check fails whenever the copies differ.
