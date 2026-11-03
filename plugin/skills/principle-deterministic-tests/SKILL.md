---
name: principle-deterministic-tests
description: "Tests whose outcome depends only on their inputs, the same on every run and under any load."
disable-model-invocation: true
triggers:
  - user
---

# Deterministic tests

A test that passes or fails without a code change guards nothing on the runs it lies, and every rerun it forces spends trust in the whole suite. A deterministic test's outcome depends only on its inputs: it passes or fails the same way on every run, in any order, on any machine and under any load. [Long term](../principle-long-term/SKILL.md)'s *fake only the boundaries* and *make every failure hard*, and [resilience](../principle-resilience/SKILL.md)'s *bound every wait*, already apply to tests; these rules hold the rest.

- **Wait on events, not time.** A test waits for an event the code gives, such as a file written, a line printed or a process exiting. Where behaviour depends on time, the test fakes the clock. It acts the moment the event comes, never after a sleep meant to let something happen.
- **Handshake with the processes it starts.** Before a test acts on a process it started, such as sending it a signal, the process reports that it is ready, for example by writing to a FIFO once its signal handler is set, so the act never lands before the process can take it.
- **Give real-time behaviour a margin load cannot eat.** Where a test runs on real time, work that must time out stalls until its timeout stops it, and work that must finish, such as a wait on a ready event, gets the suite's whole per-test limit.
- **Before it lands, prove under load each test that waits on processes, threads, signals or time.** Run each such test you add or change many times while other work keeps every core busy, and see it pass every run. Other tests need no such proof, as long term's *keep the test suite fast* says.
- **Treat a flake as a failing test.** Find its cause and fix it there, as long term's *remove each problem at its cause* says, rather than retrying it, rerunning it on failure or raising its timeout.

No check tells a deterministic test from one that passed by luck, so review holds these rules.
