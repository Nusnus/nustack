---
name: principle-deterministic-tests
description: "Tests that each fail when, and only when, the behaviour they guard breaks."
disable-model-invocation: true
triggers:
  - user
---

# Deterministic tests

Each test fails when, and only when, the behaviour it guards breaks: the same way on every run, in any order, on any machine and under any load.

- **Keep the smallest test set that guards every behaviour.** Add a test only for a failure no other test catches, and extend a test before adding one.
- **Give every test a way to fail, and see each new one fail.** It checks behaviour through the public interface against an expected value worked out from the promise apart from the code, as a literal or from an independent model, never computed by a loop or branch in the test; a parametrized row writes its expected value out in full, never building it from the row's inputs. Each new test fails against code broken on purpose, by hand or by a mutation run.
- **Fake only the system's boundaries,** such as the clock, storage or the network. Test each hand-written fake against the boundary it fakes, and replay each outside system's reply as recorded from the real system.
- **Wait on events, not time,** and fake the clock where behaviour depends on time. Prove each test you add or change that waits on processes, threads, signals or time before it lands: it passes many runs while other work keeps every core busy. Fix a flake at its cause, rather than retrying it, rerunning it or raising its timeout.
- **Make every failure hard.** Tests run in random order under a printed seed, every warning fails, a broken test is fixed or deleted, and a test skips only on an environment condition it names.
- **Cover every line and branch** of source and tests, merged from every environment the suite runs in, excluding only code that never runs by design.
- **Tier and mirror tests.** A unit test runs in-process, reads committed files and writes only temporary ones; an integration test uses other processes, the network or real tools; a smoke test runs the built artifact. Each test file mirrors the path of the source file it tests.
- **Run mutation testing where it can find something.** On a pull request, once the cheaper checks pass on a head ready for review, it runs only the mutants the changes reach, or every mutant when they change anything else the tests read. Every mutant runs from an empty cache after each merge to the default branch, and that run gates each release.
