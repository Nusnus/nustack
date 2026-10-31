---
name: principle-fail-fast
description: "Fail fast, a nus-mode principle."
disable-model-invocation: true
triggers:
  - user
---

# Fail fast

A wrong state caught where it starts is cheap to fix. Carried onward, it surfaces later and far away, as a symptom nobody can trace back. So code stops at the first sign that something is wrong, and its error lets whoever meets it, a person or an agent, fix the cause and carry on without help.

- **Stop where the problem is detected.** An unexpected state fails at once and loudly, at the place that notices it, so the failure points at its cause.
- **Check each assumption once, where it can first fail.** Past that point, the code relies on what its types, its parsing at the [boundary](../principle-boundaries/SKILL.md) and its earlier checks guarantee.
- **Recover only from failures the design expects.** A retry, fallback or catch-all handles a case the design plans for, such as a dropped connection, and the code shows which case and why. A retry repeats only work that is safe to run twice, and has a limit; when the limit runs out, the code fails as the next rule says. Every other error travels up to whoever can act on it.
- **The error message alone is enough to recover from.** Fail with an error specific to the domain. Without the code, its message says what was wrong, the value that broke it unless that value is secret, and the next step: `timeout must be at least 1 second, got -3; set it to the seconds to wait, such as 30`.
