---
name: principle-types
description: "Types, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# Types

A type is a contract that readers, and tools wherever the language has them, check without running the code. The more rules the types hold, the less the code checks by hand, and the earlier a mistake shows.

- **Make illegal states unrepresentable.** Shape each type so every value it can hold is valid, and a value that exists needs no further check.
- **Signatures carry the contract.** Each parameter and result takes the narrowest type that holds every valid value, in the project's own domain types.
- **Enumerate closed sets.** A value drawn from a fixed set of options, such as a status or a mode, gets a type that lists every option.
- **Handle every member.** Code that branches on a closed set handles each member explicitly, in a form the language or its checker proves exhaustive, so a new member fails the check until every branch handles it. Where nothing can prove it, the last branch fails loudly, naming the member it did not expect.
