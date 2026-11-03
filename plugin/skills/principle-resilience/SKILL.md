---
name: principle-resilience
description: "Code that comes through a stalled or failing dependency, or a crash part way through."
disable-model-invocation: true
triggers:
  - user
---

# Resilience

Whatever lies outside the process, such as a network service, another process or a lock, can fail, stall or answer late, and the process itself can stop at any line. Resilient code bounds what each of those costs, and leaves state that a rerun finishes.

- **Bound every wait.** Each wait on something outside the process has a limit set from the healthy duration: its own timeout, or one around it, such as a test's or a CI job's; a person watching a run they started is that limit for it. A timeout's error names what stalled.
- **Retry only a transient failure, and only work safe to repeat.** A retry handles a failure a later attempt can pass, such as a timeout, a dropped connection or a reply that asks to retry later; a refusal, such as invalid input or a denied permission, fails at once. Attempts are capped in number and in total time, each waits longer than the last, with random jitter where many clients may retry at once, a wait the reply asks for wins, and one layer retries, so retries never multiply across layers. After the last attempt, the last error travels up.
- **Make each operation that may run again idempotent.** Work that a retry, a rerun or a redelivery can repeat has the same effect the second time as the first: it checks what an earlier run already did, or carries a key the receiver uses to drop the duplicate.
- **Land each change whole.** A write that a crash or a timeout can interrupt lands whole or not at all, such as a file written beside its target and moved over it, flushed to disk before the move and its folder after it where it must survive a machine crash, or a transaction. A job interrupted at any step finishes when rerun, working from the state it finds.
- **Degrade visibly, and recover fully.** A reduced mode for when a dependency is down, such as serving a cached copy, is a planned recovery, as [fail fast](../principle-fail-fast/SKILL.md) says; it tells whoever reads the output that it is active, and the full mode returns once the dependency does.
