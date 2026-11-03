---
name: language-python
description: "Python, a nus-mode language skill."
disable-model-invocation: true
triggers:
  - user
---

# Python

A Python project's tools, and the form the principles take in Python. Every principle still holds in full.

## Tools

- **Astral's toolchain** does every job it has a tool for, now or once it gains one, such as installing Python, managing the environment and dependencies, building, formatting, linting and type checking. **import-linter** enforces import contracts, and **mutmut** runs mutation testing; where it does not mutate code, such as a module- or class-level value, break that code by hand, as [long term](../principle-long-term/SKILL.md) says.
- **Typer** builds command-line interfaces, **pydantic** parses outside data, and **pydantic-settings** reads settings.

## Code

- [Long term](../principle-long-term/SKILL.md): imports are absolute, one per line, at the top of the module.
- [Dependencies](../principle-dependencies/SKILL.md): an import-linter contract keeps pure modules from importing I/O modules. Where it cannot forbid an outside subpackage alone, such as `urllib.request` while `urllib.parse` stays allowed, the project's linter config lists that subpackage as a banned API. Neither sees I/O builtins such as `open`, which need no import, so review keeps them out.
- [Types](../principle-types/SKILL.md): branching on each member of an enum or `Literal` is a `match` that ends in `assert_never`. Data of unknown type is `object` until `isinstance`, `match` or a `TypeIs` function narrows it, never `cast`: the project's linter config lists `typing.cast` and `typing_extensions.cast` as banned APIs and selects the banned-API rule, so each use fails the check. Past the boundary the code states its types instead of using `Any` or a type-ignore. A record that never changes is a dataclass with `frozen=True` or a pydantic model with `frozen=True` in its config, and every collection it holds is immutable, such as a tuple or frozenset.
- [Fail fast](../principle-fail-fast/SKILL.md): `.get(key, default)` and every `is not None` check, such as `x if x is not None else default`, appear only where the type declares the absence, as `X | None` or `NotRequired`, or where a mapping lookup's key may validly be missing.

## Tests

[Long term](../principle-long-term/SKILL.md)'s and [layout](../principle-layout/SKILL.md)'s rules for tests, in Python:

- The tiers are the folders `tests/unit`, `tests/integration` and `tests/smoke`, never pytest markers.
- Every test is a method of a `Test<Term>` class named for the domain term whose promises it checks, as in `TestManifest.test_rejects_missing_version`, and a test module holds only those classes. A test file is named `test_<module>.py`, as in `tests/unit/fixtures/test_<module>.py` for a shared helper. A test class holds only data, fixtures and tests, in that order, with any setup in an autouse fixture.
- A fixture lives in the class that uses it, or in the nearest `conftest.py` above all its users; one shared across tiers lives in a plugin module in the shared helpers folder instead, and registering those modules is all the root `conftest.py` does. pytest imports that folder through the project root on its `pythonpath` setting. A fixture that would return a closure returns a small object with methods instead.
- pytest's `filterwarnings` setting turns every warning into an error, every test that runs reports its own pass or fail, with no `xfail` marker, and each skip names its environment condition in its `reason`.
- Coverage excludes only `...` stubs, `if TYPE_CHECKING:` blocks and the `assert_never` arms the type checker proves unreachable; its config replaces the tool's default exclusions and partial-branch patterns, so neither `# pragma: no cover` nor `# pragma: no branch` excludes anything.
