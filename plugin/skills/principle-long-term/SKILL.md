---
name: principle-long-term
description: "Changes built to last, so they are done once."
disable-model-invocation: true
triggers:
  - user
---

# Long term

Build every change to stand for years, whatever the task's size or the surrounding code's state. Work built to last is done once; work built for today comes back.

- **Give every file one consistent internal order.** Code and tests keep it as strictly as config and docs. Sections, keys, imports, definitions and members follow the order the file's ecosystem defines, enforced by its tools where they can. Where the ecosystem defines none, code follows this skill's rule for ordering code, and every other file follows one order the project picks and writes down with its standards. Readers find each thing where they expect it, and diffs show only what changed.
- **Order code so state reads up and behaviour reads down.** Where the language leaves the order of definitions open, a module holds imports, then types and module-level objects, then functions; a type holds constants, fields and derived values, then methods; a test module holds shared setup, then tests in the order of the code they test. Within each of those parts, and in anything else, state comes after the state it builds on or reads, and behaviour before the behaviour it calls.
- **Use the language's own mechanisms.** Use what the language, its standard library and its standard tools provide instead of writing your own; they keep working as the language moves on.
- **Build on stable public APIs and documented behaviour:** they survive upgrades.
- **Treat performance as a requirement.** Choose designs, data structures and tools for speed as well as clarity, from the first version.
- **Keep the full bar on temporary code.** Temporary code, such as a prototype or experiment, meets the quality bar of code that ships, performance included.
- **Keep the full bar through backward compatibility.** Find the design that keeps old callers working at full quality: compatibility constrains the design and never lowers the bar.
- **Remove each problem at its cause.** Change the place where the problem starts, so it cannot happen again; when a fix feels like a patch, fix the flaw behind it, higher in the design.
- **Fix the flaw everywhere it appears.** Each problem you fix, whether a review finding or your own catch, is one instance of a flaw. Name the flaw, search the whole project for every other instance in any form it takes, and fix them all in the same change: a fix's scope is the flaw, not the place it was found.
- **Finish what you touch.** Settle every nitpick and take every polish opportunity in each file the change touches, in the same change. Elsewhere, fix each instance of a flaw you fixed, as the rule above says, and list each other one you spot in the PR description or your reply.
- **Hold tests to the code's standard.** Tests follow the same names, structure, imports and lint rules as the code they test, departing only where the test framework's conventions require.
- **Keep the test suite fast.** The suite's wall time matters as much as the code's speed: design the tests and choose the tools that run them so the suite stays fast as it grows.
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
- **Keep each exemption narrow.** An exemption from a check covers as little as the tool allows, and states its reason beside it.
- **Write down what a check cannot reach.** Where a check cannot see some code, state the limit beside the rule, and follow the rule there anyway.
- **Update everything a change implies.** Docs, tests, names and examples change in the same commit as the code they describe.
- **Write prose that stays true.** A docstring, comment, doc, changelog entry or skill says only what stays true until its subject's purpose changes, and points to the home of each count, list, step, default, version or value it needs, as [DRY](../principle-dry/SKILL.md) says.
- **Use the fewest words that say it clearly.** Each doc, comment, docstring, skill, PR description or changelog entry carries its whole meaning in as few words as can carry it clearly: cut every word that changes nothing for the reader, and where fewer words read less clearly, keep the clearer text.
- **Write for a reader who never saw the conversation.** State each rule in general terms, in your own words, and keep an example from the conversation only when it generalises.
- **Keep working material in the PR description or the session.** Plans, specs, design notes and task checklists serve the work in progress; the repository holds what stays true after it lands.
- **Done means durable:** nothing in the change needs another visit.
