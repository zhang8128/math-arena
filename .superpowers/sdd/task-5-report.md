# Task 5 Report: Exact Predicate Registry and Complete Search

## TDD evidence

RED command:

```text
uv run pytest tests/unit/test_integer_search.py tests/unit/test_symbolic.py -q
```

Result before implementation: collection failed with `ModuleNotFoundError: No module named
'mathloop.methods'` for both test modules.

GREEN command:

```text
uv run pytest tests/unit/test_integer_search.py tests/unit/test_symbolic.py -q
```

Result: `6 passed in 0.12s`.

## Files

- Added `src/mathloop/predicates/__init__.py`, `base.py`, and `calibration.py`.
- Added `src/mathloop/methods/__init__.py`, `base.py`, `integer_search.py`, and `symbolic.py`.
- Added `tests/unit/test_integer_search.py` and `tests/unit/test_symbolic.py`.

## Verification

```text
uv run pytest tests/unit/test_integer_search.py tests/unit/test_symbolic.py -q
# 6 passed in 0.12s
uv run ruff check src tests
# All checks passed!
uv run mypy src
# Success: no issues found in 18 source files
uv run pytest -q
# 57 passed in 1.90s
git diff --check
# exit 0
git diff --cached --check
# exit 0
```

## Commit

`488417a73c0fb1e0d122c0e9e2fc9aba6878ad7a feat: add exact integer counterexample search`

## Self-review

- The finite scan is complete over the half-open interval and explicitly returns
  `bounded_no_counterexample` with no claim, witness, or artifact.
- `boundary_first` always traverses from `stop - 1` down to `start`, and its ordering is covered
  by a regression test.
- Invalid configuration, malformed predicate identifiers, and unknown predicate IDs return an
  evidence-free `invalid_config` result.
- `MethodResult.witness` uses `dict[str, object] | None` so both integer counterexamples and the
  symbolic string certificate are represented without casts.

## Concerns

- The local registry intentionally contains only the three calibration predicates; extending the
  corpus requires registering each new predicate with its exact domain semantics.

## Task 5 Review Fix

### TDD evidence

RED command:

```text
uv run pytest tests/unit/test_integer_search.py tests/unit/test_symbolic.py -q
```

Result before the fix: 5 failed, including the out-of-domain `sum_odds` run returning a
candidate, the counterexample artifact containing only the witness, and malformed symbolic
checker contracts returning a certificate.

GREEN command:

```text
uv run pytest tests/unit/test_integer_search.py tests/unit/test_symbolic.py -q
```

Result after the fix: `11 passed in 0.11s`.

### Changes

- Integer counterexample runs now require an integer checker `start` and reject a requested
  interval beginning below that declared lower bound with an evidence-free `invalid_config`.
- Counterexample artifacts include predicate ID, declared start, requested interval, order, and
  the witness; `MethodResult.witness` remains exactly `{"n": ..., "value": ...}`.
- Symbolic induction only certifies the exact `integer_predicate`/`sum_odds`/`start: 0` contract.

### Verification

```text
uv run pytest tests/unit/test_integer_search.py tests/unit/test_symbolic.py -q
# 11 passed in 0.11s
uv run pytest -q
# 62 passed in 1.87s
uv run ruff check src tests
# All checks passed!
uv run mypy src
# Success: no issues found in 18 source files
git diff --check
# exit 0
git diff --cached --check
# exit 0
```

### Commit

`HEAD (this commit): fix: enforce task 5 checker contracts`

### Self-review

- The domain guard runs before predicate evaluation, so an out-of-domain request cannot produce
  a candidate, witness, or artifact.
- The symbolic method rejects wrong kind, absent start, and wrong start regressions.
- Artifacts preserve the downstream witness structure as a nested, unmodified witness object.

### Concerns

- The checker schema remains a flexible dictionary; future predicates must document and enforce
  their own declared-domain contract explicitly.
