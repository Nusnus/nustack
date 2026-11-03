---
name: principle-dependencies
description: "Dependencies that point one way, one home for each library, the runtimes a project targets, a pinned lockfile, and deciding logic kept pure."
disable-model-invocation: true
triggers:
  - user
---

# Dependencies

Parts that depend one way can be read, tested and replaced one at a time. Cycles and scattered third-party calls let a change anywhere break anything.

- **Dependencies point one way.** Each part depends only on the parts it builds on, never on one that builds on it, so the dependency graph has no cycles.
- **Give each third-party library one home.** One module, named for the library's role, such as storage or the command line, uses the library, and the rest of the code goes through that module and its own types and errors, never the library's, so upgrading or replacing the library touches one place. A framework the code extends or runs in, such as a test framework, and a library whose base classes the code's own types extend are the exception: each module that builds on one uses it directly.
- **Target the newest runtime, or every maintained one.** An application targets the newest stable release of its language's runtime; a library supports and tests on every maintained release.
- **Float the declared range; pin the lockfile.** Where a lockfile records what installs, a dependency is declared with no upper bound and a floor at its newest release that supports every runtime version and platform the project targets, and the lockfile pins the exact version each of the project's own installs uses. A dependency whose ecosystem has no lockfile and installs exactly the version declared, such as a commit hook or a CI action, pins that version, and an update tool proposes each newer one. Any other dependency, and a requirement on the build tool or the package manager itself, takes the bounds its ecosystem or tool documents.
- **Keep deciding logic pure.** Code that decides takes the time, state and input it needs as arguments, and thin modules at the edges do the I/O, so each decision is tested without I/O. Where a tool can enforce it, a check keeps I/O out of pure modules.
