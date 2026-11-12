---
name: principle-layout
description: "A folder and file layout that shows the design, and one order inside every file."
disable-model-invocation: true
triggers: [user]
---

# Layout

The layout is part of the design: on its own, it says what the parts are, which belong together, and where each thing sits in a file.

- **Give each folder one area and each file one responsibility you can state in a line,** and move a file when its responsibility moves. A second responsibility splits the file; size alone does not.
- **Choose the top-level split, by domain, by layer or both, that makes the design readable, and nest by area within it.** Two or more files that serve one area, such as a domain concept, an outside system or a stage, share a package named for it, and a package holds more than one module. A module whose parts are concepts of their own becomes a package. Files in one folder whose names share a prefix no tool requires are a missing package.
- **Where parts form layers, show in the layout which build on which.**
- **Helpers that tests share sit in one folder beside the [test tiers](../principle-deterministic-tests/SKILL.md),** except one the test framework scopes by place, which stays with the tests it serves while they share a tier.
- **A folder or module exists once it has content.**
- **Give every file one order,** its ecosystem's, enforced by its tools where they can. Where the ecosystem defines none, code follows the next rule, and any other file one order the project writes down.
- **Order code so state reads up and behaviour reads down.** Where the language leaves it open, a module holds imports, then types and module-level objects, then functions; a type holds constants, fields and derived values, then methods; a test module holds shared setup, then tests in the order of the code they test. Within each part, and in anything else, state follows the state it builds on or reads, and behaviour precedes the behaviour it calls.
