---
name: principle-types
description: "Types that hold the contract, so an invalid value cannot exist."
disable-model-invocation: true
triggers:
  - user
---

# Types

A type is a contract that readers, and any tools the language has, check without running the code. The more rules the types hold, the fewer hand-written checks the code needs, and the earlier a mistake shows.

- **Make illegal states unrepresentable.** Shape each type so every value it can hold is valid and needs no further check.
- **Signatures carry the contract.** Each parameter and result takes the project's narrowest domain type that holds every valid value.
- **Enumerate closed sets.** A value from a fixed set, such as a status or a mode, gets a type listing every member.
- **Freeze what never changes.** A value that never changes is immutable all the way down, so no code holding it can change it under other code that holds it.
- **Handle every member.** Code that branches on a closed set handles each member explicitly, in a form the language or its checker proves exhaustive, so a new member fails the check everywhere it is unhandled. Where nothing can prove exhaustiveness, the last branch fails loudly, naming the unexpected member.
