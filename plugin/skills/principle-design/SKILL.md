---
name: principle-design
description: "Design, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# Design

Experienced engineers recognise a good design: built from proven ideas, each part with one responsibility, and short because it fits the problem.

- **Start from a design pattern.** Solve each problem with a battle-tested pattern that fits; invent a structure only where none does.
- **Question a branch on one variant.** When shared code branches on one provider, client or kind, find why the general path is wrong for it and fix the general path; prefer a fix that removes an exception to one that adds one.
- **Separate concerns.** Give each concern its own class or function, and its own file as [layout](../principle-layout/SKILL.md) splits them, so a reader working on one concern sees only its code, finds it by name, and sees what each part does at a glance. Code that mixes concerns makes every reader hold all of them at once, which slows each change and invites mistakes.
- **Start from object-oriented design that follows SOLID.** Each class has one reason to change, gains variants by extension rather than by editing working code, can stand in for its base type, exposes only what its clients use, and depends on an abstraction once a dependency has a second implementation, even a test double. Where another shape fits better, build that instead.
- **Earn a low line count through design.** Get the fewest lines from a structure that fits the problem, never from packing code tighter or exploiting language quirks. Where fewer lines read worse, keep the clearer code.
