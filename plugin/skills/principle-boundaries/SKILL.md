---
name: principle-boundaries
description: "Boundaries, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# Boundaries

Data from outside the system arrives in whatever shape its source sends: user input, files, network replies, the environment. Turned into the program's own types once, where it enters, it can be trusted everywhere else, and every rule about its shape lives in one place.

- **Parse where data enters.** Turn outside data into the program's own types at the point it enters the system. What does not fit fails there, as [fail fast](../principle-fail-fast/SKILL.md) holds.
- **Expected absence is data.** When a value may be missing in the normal course, such as a lookup with no match or an optional setting, the type holds the absence, as an optional value or an empty collection, and the caller handles it.
