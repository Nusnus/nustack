---
name: principle-self-explanatory-code
description: "Self-explanatory code, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# Self-explanatory code

Few readers read the code line by line. A human catching up skims the docstrings of modules and classes, and an agent reads only what its goal needs. So the code explains itself, docstrings orient the reader, and comments carry only what the code cannot hold. Every other line of prose is noise to both readers.

- **The code explains itself.** Names, types and structure say what each part does. When a line needs explaining, rename, extract or restructure it until it reads plainly.
- **Docstrings belong to modules and classes.** Each states the responsibility its module or class holds, in the domain's terms. A function's name and signature are its documentation.
- **Comments point outside the code.** A comment holds what the code cannot show: a spec, an upstream issue, an external constraint or a tool's quirk, with its link.
- **Docs hold what the code cannot.** Documentation outside the code states the project's purpose, its concepts and how to run it, and leaves everything the code, its help output or its config states to them.
