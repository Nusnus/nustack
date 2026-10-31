---
name: principle-naming
description: "Naming, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# Naming

Names lower the [friction rate](../nus-mode/SKILL.md) more than any other principle in this mode. A name hides assumptions and pulls in others: whoever reads `SessionCache` assumes a scope, a lifetime and an owner, right or wrong. Unclear names are the main reason humans lose track of code an agent wrote.

- **The code is the naming convention.** A project's vocabulary lives in its identifiers, defined by the docstrings of the modules and classes that introduce them.
- **Read before naming.** Learn the names the code and its domain already use, and reuse them exactly. One concept has one name everywhere: modules, classes, variables, tests, errors and CLI options.
- **Name what a thing is in the domain:** `Invoice`, `RetryPolicy`.
- **Rename when the meaning moves.** When a thing's job changes, its name changes in the same commit, everywhere it appears.
- **A name that resists you is a design signal.** When no honest name fits, the thing usually has two responsibilities: split it, then name each part.
