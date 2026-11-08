---
name: principle-fail-fast
description: "Code that fails where a wrong state is first detected, with an error that says how to recover, and holds an expected absence in its type."
disable-model-invocation: true
triggers: [user]
---

# Fail fast

Fail where a wrong state is first detected, with an error that says how to recover.

- **Check each assumption once, where it can first fail,** and trust it past that point.
- **Recover only from failures the design expects.** Every other failure, an unknown member of a closed set included, travels up to whoever can act on it.
- **Use a default only where the caller gave nothing.** A given value that does not resolve, such as a misspelled setting, fails.
- **Fail with a domain error** whose message names what was wrong and, unless it is secret, the bad value.
- **Hold an expected absence, such as a lookup with no match, in its type,** as an optional value or an empty collection, for the caller to handle.
