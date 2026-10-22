# Python client contributor guide

Apply these conventions to new code and the code you change. Preserve published interfaces and avoid unrelated typing or formatting migrations.

## Python and validation

- Support Python 3.10 and later. Use keyword arguments for new helpers with more than two parameters or easily swapped options. Do not make existing public callables keyword-only as a style change.
- Annotate new functions, including argument and return types. Use `TypedDict` for records this package builds, with required base records and `total=False` extensions for optional fields; do not import Python 3.11-only typing names without a compatible dependency.
- This lightweight HTTP client does not depend on Pydantic. Validate at boundaries using the existing helpers and build typed records explicitly; do not add a runtime schema dependency merely to mirror another repository.
- Prefer f-strings and pathlib for filesystem work. Keep logging's deferred formatting. Use comprehensions for simple collection building and `next()` for the first match.
- Start boolean variable names with `is` or `has`, using the language’s casing: `is_valid_motion`, `has_frame_range` in Python; `isValidMotion`, `hasFrameRange` in TypeScript. Prefer names that read as a clear predicate. Preserve published parameter and field names for compatibility.
- Name predicates for the domain rule they express, then combine names at a shared error, return, or continuation. Keep simple type-narrowing guards inline before field access. Do not compute an unsafe or expensive predicate eagerly just to give it a name.
- Treat untrusted values as `object` in Python or `unknown` in TypeScript until validated. Build owned normalized records with declared types; a cast is not runtime validation. Keep any necessary assertion local to the checks that justify it.
- Distinguish omitted fields from explicit null, zero, and false. Apply defaults only where the contract permits them. Validation must not mutate caller-owned nested data.
- Name domain limits and non-obvious numeric tolerances, including units. Keep equivalent cross-language contracts aligned with shared acceptance, rejection, and normalization fixtures.
- Keep runtime validation in normal control flow; do not use Python `assert` for caller input, permissions, or side-effect preconditions. Assertions may narrow already-proven internal invariants, but prefer a type design that avoids repeating the proof.
- Use module-level imports, including TypeScript `import type`. Local imports need a circular-dependency or measurable startup-cost reason. Keep module summaries accurate when a file serves both current and legacy interfaces.
- Preserve published signatures, error categories, unknown-outcome recovery, and side-effect order during style changes. Do not retrofit unrelated existing code. Add tests for changed behavior or meaningful gaps, not for a cosmetic rewrite of the same implementation.

## Verification and review

Use the checked-in Ruff configuration (100-character lines), mypy, and pytest:

```sh
uv sync --locked
uv run --locked ruff check src scripts tests
uv run --locked ruff format --check src scripts tests
uv run --locked mypy src scripts
uv run --locked pytest
uv build --clear
```

Keep tests offline and deterministic. Live tests must be explicitly configured; do not make paid calls as routine verification. There is no configured coverage-percentage gate to invent or lower. For documentation-only changes, validate examples, links, and formatting; executable changes require relevant regression tests and the normal checks.

Review the full PR diff for style, bugs, security, unnecessary abstractions, and compatibility. Report the checks actually run and distinguish manual review from automated tooling. Keep detailed feature documentation under `docs/`, use simple then advanced examples, and keep each guide self-contained. Never merge or publish without authorization.
