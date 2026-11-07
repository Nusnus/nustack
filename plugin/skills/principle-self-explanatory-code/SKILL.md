---
name: principle-self-explanatory-code
description: "Code that explains itself, and docs for what it cannot say."
disable-model-invocation: true
triggers:
  - user
---

# Self-explanatory code

The code says what it does through its names, types and structure; its comments and docs say only what it cannot.

- **Docstrings belong to modules and classes.** In domain terms, a module's docstring summarizes everything the file holds, and a class's states its responsibility, or in tests its domain term's promises and edge cases; a test group that cannot hold a docstring names its term. A function's or method's name and signature are its documentation, and no docstring repeats what the path, the imports or the names already say.
- **Define each new domain term** in the docstring of the module or class that introduces it, or in the project's docs where none does.
- **Comments point outside the code,** to what it cannot show, such as a spec, an upstream issue, an external constraint or a tool quirk, with its link where one exists.
- **Use the fewest words that say it clearly.** In every text, cut each word that changes nothing for the reader; where fewer words read less clearly, keep the clearer text.
- **Write for a reader who never saw the conversation.** State each rule in general terms, and keep an example from the conversation only where it generalises.
