---
name: principle-naming
description: "Names that say what a thing is in the domain."
disable-model-invocation: true
triggers:
  - user
---

# Naming

Every name, even of a file, folder or package, says what its thing is in the domain, and everything it implies holds.

- **The code is the naming convention.** One concept has one name everywhere, including tests, errors and CLI options: the name the code and its domain already use.
- **Where no honest name fits, the thing usually has two responsibilities: split it, then name each part.** A catch-all such as `core` or `utils`, or a metaphor such as `edges`, names no domain thing.
- **Rename a thing when its responsibility changes.**
