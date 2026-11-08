---
name: principle-types
description: "Types that hold the contract, so an invalid value cannot exist."
disable-model-invocation: true
triggers: [user]
---

# Types

Let the types hold the contract: a rule a type holds needs no check in the code, and a break of it shows as early as the language allows.

- **Make illegal states unrepresentable.** Every value a type, parameter or result admits is valid, and every valid value fits.
- **Freeze what never changes,** all the way down.
- **Handle every member of a closed set by name,** in a form a checker proves exhaustive wherever one can.
