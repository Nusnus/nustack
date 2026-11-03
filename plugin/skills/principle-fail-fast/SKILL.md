---
name: principle-fail-fast
description: "Code that stops where a problem starts, with an error that says how to recover."
disable-model-invocation: true
triggers:
  - user
---

# Fail fast

A wrong state caught where it starts is cheap to fix. Carried onward, it surfaces later and elsewhere, as a symptom that hides its cause.

- **Stop where the problem is detected.** An unexpected state fails there, at once, with an error that points at its cause.
- **Check each assumption once, where it can first fail.** Past that point, code trusts what its types, [boundary](../principle-boundaries/SKILL.md) parsing and earlier checks guarantee.
- **Recover only from failures the design expects.** A retry, fallback or catch-all handles a planned case, such as serving a cached copy while a dependency is down, and the code shows which case and why. Every other error travels up to whoever can act on it. [Resilience](../principle-resilience/SKILL.md) says how a retry or a reduced mode recovers.
- **Use a default only when the caller gave nothing.** A value the caller gave that does not resolve, such as an unknown name or path, fails loudly and is never replaced by the default.
- **Whoever meets the error, person or agent, can recover from its message alone.** Fail with a domain-specific error whose message says what was wrong, the bad value unless it is secret, and the next step: `timeout must be at least 1 second, got -3; set it to the seconds to wait, such as 30`.
