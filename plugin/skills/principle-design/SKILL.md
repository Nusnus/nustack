---
name: principle-design
description: "A design built from proven patterns and SOLID objects that put behaviour with the data it serves, short because it fits the problem."
disable-model-invocation: true
triggers:
  - user
---

# Design

Build from proven designs that fit the problem: each part has one responsibility and sits with the data it serves, and the code is short because its structure fits.

- **Invent a structure only where no battle-tested design pattern fits.**
- **Fix the general path, not one variant.** When shared code branches on one provider, client or kind, find why the general path is wrong for it and fix that; prefer a fix that removes an exception to one that adds one.
- **Start from object-oriented design that follows SOLID,** and build another shape only where it fits better. A class exposes only what its clients use, and depends on an abstraction once a dependency has a second implementation, even a test double.
- **Earn a low line count through design;** where fewer lines read worse, keep the clearer code.
- **Put behaviour with the data it serves.** A function that serves the data of a type the project can edit is that type's method, or sits beside it where it cannot hold methods, unless it belongs to an abstraction's interface, which keeps it in the abstraction and each implementation. A value a module needs is a member of the type or enum that uses it. Other functions, and what a framework or entry point calls or reads by name, may stay at module level; a class that holds no data is a namespace for functions only where it is a test class or the language or a framework requires it.
