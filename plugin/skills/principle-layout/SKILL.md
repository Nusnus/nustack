---
name: principle-layout
description: "A folder and file layout that shows the design."
disable-model-invocation: true
triggers:
  - user
---

# Layout

The folder and file layout is as much a part of the design as the code inside it, and the part a reader new to the project sees first: on its own, it says what the parts are and which belong together.

- **Fit the shape to the project.** Choose the top-level split, by domain area, by layer or both, that makes this design readable.
- **Split by responsibility.** Each folder is one area of the design, and each file holds one responsibility you can state in a line. A second responsibility splits the file; size alone does not.
- **Put behaviour with the data it serves.** A function is a method of the type it serves, or sits beside that type where the language has no methods, and a value a module needs is a member of the type or enum that uses it, so no module holds loose helpers or globals. What a framework or entry point calls or reads by name, such as a command, a test, a test class, the app object or a list of test plugins, may stay at module level. A function that serves no type's data stays at module level too, since the module is its namespace: a class that holds no data is never a namespace for functions, except a test class or a class a framework requires.
- **Nest by area.** When two or more files serve one area, such as a domain concept, an outside system or a stage, put them in a package named for it, so a path says where each file belongs and how far it reaches. Files in one folder whose names share a prefix no tool requires are a missing package.
- **Show the dependency direction.** Where parts form layers, the layout shows which build on which, in the direction [dependencies](../principle-dependencies/SKILL.md) holds them to.
- **Earn each level of structure.** A folder, package or module exists once it has content, and a package holds more than one module. A module becomes a package once its parts are concepts of their own.
- **Design the layout with the rest of the design.** Plan the folders and files the design needs before writing them, and move a file whenever its responsibility moves.
- **Give every file one consistent internal order.** Code and tests keep it as strictly as config and docs. Sections, keys, imports, definitions and members follow the order the file's ecosystem defines, enforced by its tools where they can. Where the ecosystem defines none, code follows this skill's rule for ordering code, and every other file follows one order the project picks and writes down with its standards. Readers find each thing where they expect it, and diffs show only what changed.
- **Order code so state reads up and behaviour reads down.** Where the language leaves the order of definitions open, a module holds imports, then types and module-level objects, then functions; a type holds constants, fields and derived values, then methods; a test module holds shared setup, then tests in the order of the code they test. Within each of those parts, and in anything else, state comes after the state it builds on or reads, and behaviour before the behaviour it calls.
