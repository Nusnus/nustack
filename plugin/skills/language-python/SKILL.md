---
name: language-python
description: "Python's tools, and where Python changes how a principle applies."
disable-model-invocation: true
triggers:
  - user
---

# Python

A Python project's tools, and the form a principle takes where Python changes it. Every principle still holds in full.

## Tools

- **Astral's tools** do every job they cover, now or once they cover it, such as installing Python, managing the environment and dependencies, building, formatting, linting and type checking. Ruff's config keeps each import at the top of its module, absolute and on its own line.
- **pytest** runs the tests with **pytest-randomly**, and **pytest-timeout** bounds each test. **import-linter** enforces import contracts.
- **Typer** builds command-line interfaces, **pydantic** parses outside data, and **pydantic-settings** reads settings.

## Code

- [Boundaries](../principle-boundaries/SKILL.md): a pydantic model forbids extra fields in a format the project owns. Where the source is typed, such as JSON or TOML, each value the source has a literal for takes a strict type at every depth, such as `StrictInt` in `tuple[StrictInt, ...]`, and a type it has none for, such as a tuple, enum or `Path`, stays lax.
- [Dependencies](../principle-dependencies/SKILL.md): an import-linter contract keeps I/O modules out of the pure ones, and Ruff's banned-API list adds each outside subpackage import-linter cannot forbid alone, such as `urllib.request` beside `urllib.parse`. Neither sees a pure module call an I/O builtin or method, such as `open` or `Path.read_text`, so keep those out by hand.
- [Types](../principle-types/SKILL.md): data of unknown type is `object` until `isinstance`, `match` or a `TypeIs` function narrows it, code past the boundary states its types instead of using `Any` or a type-ignore, and Ruff's banned-API list holds `typing.cast` and `typing_extensions.cast`.
- [Fail fast](../principle-fail-fast/SKILL.md): `.get(key, default)` and a check for `None` appear only where the type admits the absence, as `X | None` or `NotRequired`, or where a key may validly be missing from a mapping.
- [Resilience](../principle-resilience/SKILL.md): the timeout of `urlopen` or a socket bounds each blocking step, not the whole request nor the DNS lookup before it. `subprocess.run`'s timeout kills only the child, whose output pipes stay open while any process it started lives, so a command that starts its own runs with `start_new_session=True`, and a timeout or an interrupt ends its whole process group.
- [Resilience](../principle-resilience/SKILL.md): a file lands whole when written to a `tempfile.mkstemp` file in the target's folder, given the mode its readers need, since `mkstemp` makes it owner-only, and moved over the target with `Path.replace`. Where it must survive a machine crash, `os.fsync` flushes the file before the move and its folder after.

## Tests

- [Deterministic tests](../principle-deterministic-tests/SKILL.md): the tiers are the folders `tests/unit`, `tests/integration` and `tests/smoke`.
- [Self-explanatory code](../principle-self-explanatory-code/SKILL.md): every test is a method of a `Test<Term>` class named for the domain term whose promises it checks.
- [Layout](../principle-layout/SKILL.md): a test module holds only those classes, and a class's setup is an autouse fixture. A fixture sits in the class that uses it, or in the nearest `conftest.py` above its users within one tier. One that tiers share is a plugin module in the shared helpers folder, and registering those modules is all the root `conftest.py` does.
- [Design](../principle-design/SKILL.md): a fixture that would return a closure returns a small object with methods instead.
