---
name: principle-boundaries
description: "Outside data parsed once, where it enters, and an expected absence held as data."
disable-model-invocation: true
triggers:
  - user
---

# Boundaries

Data from outside the system, such as user input, files, network replies or the environment, arrives in whatever shape its source sends. Parsed once, it can be trusted everywhere else, and every rule about its shape lives in one place.

- **Parse where data enters.** There, turn outside data into the project's [domain types](../principle-types/SKILL.md), and fail on what does not fit, as [fail fast](../principle-fail-fast/SKILL.md) says.
- **Expected absence is data.** When a value may validly be missing, such as a lookup with no match or an optional setting, its type holds the absence, as an optional value or an empty collection, and the caller handles it.
