---
name: principle-resilience
description: "Code that comes through failure and load by its design: each failure absorbed by its structure or left to fail, each limit known and accepted."
disable-model-invocation: true
triggers:
  - user
---

# Resilience

Resilient code comes through failure and load by its design, not by scattered guards: each failure and edge case it can meet is absorbed by its structure or left to fail on purpose, as [fail fast](../principle-fail-fast/SKILL.md) says, and each limit it has is known and accepted.

- **Build for the load the code will grow into,** and know the larger load at which it breaks, so that limit is chosen rather than found.
- **Leave state a rerun finishes, whatever line the process stops at:** work that may run again is idempotent, and each change lands whole or not at all.
- **Bound every wait** on anything outside the process, by a limit set from its healthy duration: its own, or one around it; a person watching a run they started is that limit.
- **Retry in one layer only,** waiting at least as long as a reply asks.
- **Degrade visibly.** A reduced mode, such as serving a cached copy, says so in its output and ends once the dependency is back.
