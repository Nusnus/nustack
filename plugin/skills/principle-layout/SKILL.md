---
name: principle-layout
description: "Layout, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# Layout

The layout of folders and files is part of the design, as much as the code inside them, and the first view of it a newcomer gets. Read alone, the layout says what the parts are and which belong together.

- **Split by responsibility.** Each folder is one area of the design, and each file holds one responsibility you can state in a line. A second responsibility splits the file; size alone does not.
- **Nest to show structure.** Nested folders show which parts belong together and which part contains which.
- **Show the dependency direction.** Where parts build on one another in layers, the layout makes plain which build on which, in the direction [dependencies](../principle-dependencies/SKILL.md) holds them to.
- **Fit the shape to the project.** Choose the top-level split, by domain area, by layer or both, that makes this design readable.
- **Design the layout with the rest of the design.** Lay out the folders and files the design needs before writing them, and move a file whenever its responsibility moves.
