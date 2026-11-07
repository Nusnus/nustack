---
name: principle-deterministic-tests
description: "Tests whose outcome depends only on their inputs, the same on every run and under any load."
disable-model-invocation: true
triggers:
  - user
---

# Deterministic tests

A test that passes or fails without a code change guards nothing on the runs it lies, and every rerun it forces spends trust in the whole suite. A deterministic test's outcome depends only on its inputs: it passes or fails the same way on every run, in any order, on any machine and under any load. [Resilience](../principle-resilience/SKILL.md)'s *bound every wait* already applies to tests; these rules hold the rest.

- **Wait on events, not time.** A test waits for an event the code gives, such as a file written, a line printed or a process exiting. Where behaviour depends on time, the test fakes the clock. It acts the moment the event comes, never after a sleep meant to let something happen.
- **Handshake with the processes it starts.** Before a test acts on a process it started, such as sending it a signal, the process reports that it is ready, for example by writing to a FIFO once its signal handler is set, so the act never lands before the process can take it.
- **Give real-time behaviour a margin load cannot eat.** Where a test runs on real time, work that must time out stalls until its timeout stops it, and work that must finish, such as a wait on a ready event, gets the suite's whole per-test limit.
- **Before it lands, prove under load each test that waits on processes, threads, signals or time.** Run each such test you add or change many times while other work keeps every core busy, and see it pass every run. Other tests need no such proof, as *keep the test suite fast* says.
- **Treat a flake as a failing test.** Find its cause and fix it there, as long term's *remove each problem at its cause* says, rather than retrying it, rerunning it on failure or raising its timeout.

No check tells a deterministic test from one that passed by luck, so review holds these rules.

- **Hold tests to the code's standard.** Tests follow the same names, structure, imports and lint rules as the code they test, departing only where the test framework's conventions require.
- **Keep the test suite fast.** The suite's wall time matters as much as the code's speed: design the tests and choose the tools that run them so the suite stays fast as it grows.
- **Spend each mutation run where it can find something.** A change that touches nothing the mutation run reads runs none, and so does an edit to test code that leaves what it runs as it was, such as one to a comment. A pull request keeps the verdicts of the default branch's last full run and runs again each mutant in code it changed and each mutant a test it changed covers; a change to anything else the run reads, such as a test helper, test data or tool settings, runs every mutant. A run of every mutant from an empty cache follows each merge to the default branch and gates each release, so it catches what a kept verdict misses, such as the effect of a change to one function on the verdicts of another that calls it. On a pull request, the mutation run waits until the cheaper checks pass, and runs once on each head ready for review.
- **Keep the smallest test set that guards every behaviour.** Add a test only for a failure no existing test catches, extend an existing test before adding one, and delete tests that guard nothing new. A negative test's positive pair counts as guarding something new, so it stays.
- **Give every test a way to fail.** Each test asserts behaviour the code could get wrong, through the code's public interface. Its expected value comes from what the behaviour promises, worked out apart from how the code computes it: a literal or an independent model, never a loop or branch inside the test. A loop or parametrized row may build the inputs, and each row writes out its full expected value, such as an error message, never building it from the row's inputs.
- **Fake only the boundaries.** A test runs the project's own code and fakes only the system's boundaries, such as the clock, storage or network, and each hand-written fake has tests showing it behaves like the boundary it fakes.
- **Write each test with or after the code it tests, and see it fail.** Test-first lets a human feel a design's friction while writing it; an agent feels none, so for an agent it only adds steps. Keep what test-first guaranteed: see each new test fail against code broken on purpose, by hand or by a mutation run.
- **Name each test for its promise.** A test's name, read after the name of any class or group that holds it, completes a sentence stating what the code promises, so it never repeats that subject.
- **Pair each negative test with its positive.** Each test that something is refused has a paired test showing the same setup accepted with only the refusal's cause removed; an existing test that differs from it only by that cause is the pair.
- **Guard each promise not to act with a canary.** Where the code promises never to do something, a test sets up what it must leave alone and fails if the code touches it.
- **Replay real replies.** A test that needs an outside system's reply replays one recorded from the real system, never one written by hand.
- **Tier tests by what they touch.** A unit test runs in-process and uses no outside system, reading committed files, such as fixtures, and writing only temporary files; an integration test uses other processes, the network or real tools; a smoke test runs the built artifact. Helpers that tests share, such as fakes, live in a shared helpers folder named for their role, such as `tests/fixtures/`, beside any tier folders. A helper the test framework scopes by where it is defined, such as a fixture in a test class or folder, stays where it applies unless it applies across tiers, so a tier folder holds only its tests and the helpers scoped to them.
- **Mirror the source in the tests.** Each test file mirrors the path of the source file it tests, and a test of a shared helper, such as a fake, mirrors the helper's path inside the tier it runs at; a check fails a test file that mirrors nothing. Tests of the suite's own settings and smoke tests are exempt, and the check skips them, since they test the suite and the built artifact rather than one source file.
- **Make every failure hard.** Tests run in random order under a printed seed, every warning fails, a broken test is fixed or deleted instead of marked as an expected failure, and a test skips only on an environment condition it names.
- **Cover every line and branch.** Coverage, merged from every environment the suite runs in, reaches 100% of the lines and branches in source and tests, excluding only code that never runs by design, such as a branch the type checker proves unreachable.
- **Test the settings that run the tests.** The settings that decide how the suite runs, such as its order, warnings and coverage, have their own tests.
