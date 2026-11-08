---
name: principle-dependencies
description: "Dependencies that point one way, onto the language's own tools and stable public APIs, one home for each library, the runtimes a project targets, floating ranges with a pinned lockfile, and deciding logic kept pure."
disable-model-invocation: true
triggers: [user]
---

# Dependencies

Depend one way.

- **Give each third-party library one home:** a module named for its role, such as storage or the command line, through which the rest of the code reaches it, in the project's own types and errors. A framework the code runs in, such as a test framework, and a library whose classes the project's types extend are used directly wherever the code builds on them.
- **Target the newest runtime, or every maintained one:** an application, the newest stable release; a library, every maintained release, tested on each.
- **Float the declared range; pin the lockfile.** Where a lockfile records what installs, a dependency has no upper bound and a floor at its newest release that supports every runtime and platform the project targets, and the lockfile pins the exact version. A dependency that installs exactly the version declared, such as a commit hook or a CI action, pins it, and an update tool proposes each newer one. Anything else, the build tool and the package manager included, takes the bounds its documentation gives.
- **Keep deciding logic pure.** Code that decides takes the time, state and input it needs as arguments, thin modules at the edges do the I/O, and a check keeps I/O out of the pure modules where a tool can.
- **Use what the language and its standard tools provide before writing your own.**
- **Build on stable public APIs and documented behaviour.**
