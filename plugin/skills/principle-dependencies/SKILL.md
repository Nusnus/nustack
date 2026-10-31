---
name: principle-dependencies
description: "Dependencies, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# Dependencies

Parts that depend in one direction can be read, tested and replaced one at a time. Cycles and scattered third-party calls tie every part to every other, so a change anywhere can break anything.

- **Dependencies point one way.** Each part depends only on the parts it builds on, and never on a part that builds on it, so the dependency graph has no cycles. Where the parts form layers, the [layout](../principle-layout/SKILL.md) shows the same direction.
- **Give each third-party library one home.** One module uses the library, named for the role the library plays in the project, such as storage or the command line, and the rest of the code goes through that module. Upgrading or replacing the library then touches one place.
- **Use a framework directly where it runs the code.** A framework the code extends, or one that runs it, such as a test framework, is used directly by each module that builds on it.
