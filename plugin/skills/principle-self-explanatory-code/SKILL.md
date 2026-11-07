---
name: principle-self-explanatory-code
description: "Code that explains itself, and docs for what it cannot say."
disable-model-invocation: true
triggers:
  - user
---

# Self-explanatory code

Few readers read code line by line: a human catching up skims module and class docstrings, and an agent reads only what its goal needs. So code and its docs hold only the prose the rules below call for.

- **The code explains itself.** Names, types and structure say what each part does. Rename, extract or restructure until each part reads plainly.
- **Docstrings belong to modules and classes.** A module's docstring does for the module what frontmatter does for a skill: it summarizes, in domain terms, everything the file holds, so a reader learns from it alone whether their goal needs the rest of the file. A class's docstring states the class's responsibility in domain terms. A function's or method's name and signature are its documentation. In tests, a module's docstring summarizes what its classes or groups verify together, and a class's states its domain term's promises and its edge cases; a test group that cannot hold a docstring names its term. No docstring repeats what the path, the imports or the test names already say.
- **Comments point outside the code.** Each holds what the code cannot show, with its link where one exists: a spec, upstream issue, external constraint or tool quirk.
- **Docs hold what the code cannot.** Docs outside the code state the project's purpose, concepts and how to run it.
- **Use the fewest words that say it clearly.** Each doc, comment, docstring, skill, PR description or changelog entry carries its whole meaning in as few words as can carry it clearly: cut every word that changes nothing for the reader, and where fewer words read less clearly, keep the clearer text.
- **Write for a reader who never saw the conversation.** State each rule in general terms, in your own words, and keep an example from the conversation only when it generalises.
