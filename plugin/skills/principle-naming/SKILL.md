---
name: principle-naming
description: "Names that say what a thing is in the domain."
disable-model-invocation: true
triggers:
  - user
---

# Naming

Naming lowers the [friction rate](../nus-mode/SKILL.md#goal) more than any other principle: unclear names are the main reason humans lose track of code an agent wrote. Readers believe what a name implies: whoever reads `SessionCache` assumes a scope, a lifetime and an owner, right or wrong.

- **The code is the naming convention.** Before naming, read the names the code and its domain already use, and reuse them exactly. One concept has one name everywhere, including tests, errors and CLI options. Define each new domain term in the docstring of the module or class that introduces it, or in the project's docs where no module or class does.
- **Name what a thing is in the domain**, whether a symbol, file, folder or package: `Invoice`, `RetryPolicy`, `billing/`. A catch-all such as `core` or `utils`, or a metaphor such as `edges`, names no domain thing.
- **Rename when a thing's responsibility changes**, in the same commit, everywhere the name appears.
- **When no honest name fits**, the thing usually has two responsibilities: split it, then name each part.
