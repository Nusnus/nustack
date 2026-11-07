---
name: principle-boundaries
description: "Outside data parsed once, where it enters, strictly into the project's domain types."
disable-model-invocation: true
triggers:
  - user
---

# Boundaries

Parse data from outside the system, settings from the environment included, once, where it enters.

- **Parse it into the project's [domain types](../principle-types/SKILL.md), and fail on what does not fit them exactly,** such as an unknown field in a format the project owns, or a value of the wrong type.
