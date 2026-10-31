---
name: principle-dry
description: "DRY, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# DRY

Every piece of knowledge has one home. A rule, a value, a format or a decision is written once, and everything else that needs it refers to that home, so changing it is one edit and no copy is left behind to drift.

- **Find the home before you write.** Before you state a value, a rule or a format, look for where the project already holds it, and refer to that.
- **Derive what you would copy.** When two places need the same knowledge in different forms, produce one from the other, or both from one source.
- **Merge by reason to change.** Two pieces are one piece of knowledge when they change for the same reason. Pieces that look alike but change for different reasons each keep their own home.
- **Hold required copies equal.** When tools or hosts each read their own copy of a fact, one check fails whenever the copies differ.
