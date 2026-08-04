# Overnight Conjecture Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run two bounded conjecture attacks through `.timeloop`, producing independently verified mathematical evidence and a Lean-checked theorem whenever the evidence supports one.

**Architecture:** Track A implements a finite-state digit-product-plus-sum map, explores its complete low-base dynamics, and independently rechecks every promoted pattern. Track B implements an exact Erdős–Straus identity verifier, reproduces positive controls, and searches the difficult `n = 1 mod 24` residue structure without confusing finite coverage with proof. Each track writes its own notebook and raw artifacts; Lean files contain only exact statements that have survived independent checks.

**Tech Stack:** Python 3.13, pytest 8.4, standard-library integer arithmetic, SymPy 1.14 for symbolic identity reduction, Lean 4.32.1, mathlib, Markdown/JSONL durable records.

## Global Constraints

- End the run no later than `2026-08-04 08:00 America/Los_Angeles`.
- Preserve the user's existing modification at `.timeloop/exam/results.jsonl` untouched.
- Treat every Math Prism output as a hypothesis only; the eight applications already run produced zero contract-valid artifacts and supply no mathematical premise.
- Independently reproduce every counterexample before recording it.
- State the exact computational range for every bounded result.
- Assign novelty only after a current primary-literature and OEIS search using `published`, `not found`, or `superseded`.
- Reject any Lean result whose `#print axioms` output contains `sorryAx`.
- Do not publish, submit, or externally represent any result without a separate human gate.

---

## File Structure

- `.timeloop/lib/digitproducts.py`: validated digit extraction, the product-plus-sum map, its eventual-decrease bound, and complete cycle enumeration.
- `.timeloop/tests/test_digitproducts.py`: unit and exhaustive small-base tests for the Track A kernel.
- `.timeloop/runs/t18_digit_products.py`: discovery enumeration and machine-readable candidate summary.
- `.timeloop/runs/t18_digit_products_independent.py`: independent arithmetic recheck that imports none of the Track A kernel.
- `.timeloop/notebook/forge-digit-products.md`: exact Track A scope, results, negative evidence, novelty, and next action.
- `.timeloop/lib/erdos_straus.py`: exact decomposition predicate and factor-pair generation for a fixed first denominator.
- `.timeloop/tests/test_erdos_straus.py`: positive, negative, and exhaustive cross-checks for Track B.
- `.timeloop/runs/t19_erdos_residues.py`: documented residue exploration for primes `n = 24m + 1`.
- `.timeloop/runs/t19_erdos_independent.py`: independent bounded verification of any promoted identity or class.
- `.timeloop/notebook/erdos-straus.md`: exact Track B scope, identities, failures, novelty, and next action.
- `.timeloop/lean/arena/Arena/DigitProducts.lean`: exact fixed-point obstruction for the product-plus-sum map.
- `.timeloop/lean/arena/Arena/ErdosStraus.lean`: exact positive-control decompositions plus any surviving explicit identity.
- `.timeloop/lean/arena/Arena.lean`: imports the two new checked modules.
- `.timeloop/ledger.md`: two append-only experiment records.
- `.timeloop/pool.jsonl`: update only `reps` or `status` fields justified by the notebooks.

---

### Task 1: Finite Digit-Product Kernel

**Files:**
- Create: `.timeloop/tests/test_digitproducts.py`
- Create: `.timeloop/lib/digitproducts.py`

**Interfaces:**
- Produces: `digits(n: int, base: int) -> tuple[int, ...]`, least-significant digit first.
- Produces: `product_plus_sum_step(n: int, base: int) -> int`.
- Produces: `product_plus_sum_bound(base: int) -> int`.
- Produces: `cycles(base: int) -> tuple[tuple[int, ...], ...]`, with every cycle rotated to its least element and the collection sorted.

- [ ] **Step 1: Write validation and arithmetic tests**

```python
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from digitproducts import cycles, digits, product_plus_sum_bound, product_plus_sum_step


def test_digits_are_little_endian_and_preserve_zero() -> None:
    assert digits(0, 10) == (0,)
    assert digits(105, 10) == (5, 0, 1)
    assert digits(13, 2) == (1, 0, 1, 1)


@pytest.mark.parametrize(("n", "base"), [(-1, 10), (0, 1), (3, 0)])
def test_digits_reject_invalid_inputs(n: int, base: int) -> None:
    with pytest.raises(ValueError):
        digits(n, base)


def test_product_plus_sum_examples() -> None:
    assert product_plus_sum_step(123, 10) == 12
    assert product_plus_sum_step(105, 10) == 6
    assert product_plus_sum_step(7, 10) == 14


def test_bound_implies_strict_decrease_for_next_two_digit_lengths() -> None:
    for base in range(2, 9):
        bound = product_plus_sum_bound(base)
        for n in range(bound + 1, bound + 10_000):
            assert product_plus_sum_step(n, base) < n


def test_base_two_cycles_are_complete() -> None:
    assert cycles(2) == ((0,), (1, 2), (3,))
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest .timeloop/tests/test_digitproducts.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'digitproducts'`.

- [ ] **Step 3: Implement the minimal finite-state kernel**

```python
from __future__ import annotations

from math import prod
from typing import Callable


def digits(n: int, base: int) -> tuple[int, ...]:
    if n < 0:
        raise ValueError("n must be nonnegative")
    if base < 2:
        raise ValueError("base must be at least 2")
    if n == 0:
        return (0,)
    out: list[int] = []
    while n:
        out.append(n % base)
        n //= base
    return tuple(out)


def product_plus_sum_step(n: int, base: int) -> int:
    ds = digits(n, base)
    return prod(ds) + sum(ds)


def product_plus_sum_bound(base: int) -> int:
    if base < 2:
        raise ValueError("base must be at least 2")
    width = 1
    while True:
        image_max = (base - 1) ** width + width * (base - 1)
        if image_max < base ** (width - 1):
            return image_max
        width += 1


def _canonical_cycle(values: list[int]) -> tuple[int, ...]:
    least = min(range(len(values)), key=values.__getitem__)
    return tuple(values[least:] + values[:least])


def _cycles_below(bound: int, step: Callable[[int], int]) -> tuple[tuple[int, ...], ...]:
    settled: set[int] = set()
    found: set[tuple[int, ...]] = set()
    for start in range(bound + 1):
        if start in settled:
            continue
        path: list[int] = []
        positions: dict[int, int] = {}
        n = start
        while n not in positions and n not in settled:
            positions[n] = len(path)
            path.append(n)
            n = step(n)
        if n in positions:
            found.add(_canonical_cycle(path[positions[n] :]))
        settled.update(path)
    return tuple(sorted(found))


def cycles(base: int) -> tuple[tuple[int, ...], ...]:
    bound = product_plus_sum_bound(base)
    return _cycles_below(bound, lambda n: product_plus_sum_step(n, base))
```

- [ ] **Step 4: Run the focused tests**

Run: `uv run pytest .timeloop/tests/test_digitproducts.py -q`

Expected: all tests pass. If the asserted base-two cycle is wrong, inspect the independently hand-enumerable states `0..5`, correct the test to the exact cycle set, and record the correction in the notebook rather than changing the implementation to fit it.

- [ ] **Step 5: Commit the kernel**

```bash
git add .timeloop/lib/digitproducts.py .timeloop/tests/test_digitproducts.py
git commit -m "feat: add finite mixed digit-map kernel"
```

---

### Task 2: Track A Discovery and Independent Recheck

**Files:**
- Create: `.timeloop/runs/t18_digit_products.py`
- Create: `.timeloop/runs/t18_digit_products_independent.py`
- Create: `.timeloop/notebook/forge-digit-products.md`

**Interfaces:**
- Consumes: `product_plus_sum_bound(base)` and `cycles(base)` from Task 1.
- Produces: `.timeloop/runs/t18_digit_products.json` with keys `map`, `bases`, `bounds`, `cycles`, `candidate_invariants`, and `counterexamples`.
- Produces: an independent recheck line for every candidate as `PASS`, `FAIL`, or `OUT_OF_SCOPE`.

- [ ] **Step 1: Write a failing subprocess contract test**

Append to `.timeloop/tests/test_digitproducts.py`:

```python
import json
import subprocess


def test_discovery_script_emits_scoped_json() -> None:
    script = Path(__file__).resolve().parents[1] / "runs" / "t18_digit_products.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--max-base", "4"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["map"] == "digit_product_plus_sum"
    assert payload["bases"] == [2, 3, 4]
    assert set(payload["bounds"]) == {"2", "3", "4"}
    assert set(payload["cycles"]) == {"2", "3", "4"}
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run: `uv run pytest .timeloop/tests/test_digitproducts.py::test_discovery_script_emits_scoped_json -q`

Expected: FAIL because `t18_digit_products.py` does not exist.

- [ ] **Step 3: Implement the discovery script**

The script must parse `--max-base`, enumerate every base in `range(2, max_base + 1)`, and emit only JSON to standard output. For each cycle, compute these candidate features without filtering the raw cycle set: length, minimum, maximum, digit lengths, residues modulo `base - 1`, and whether every state satisfies `product(digits(state, base)) % (base - 1) == 0`. Preserve the first counterexample to each universal-looking feature rather than deleting the feature.

Run: `uv run python .timeloop/runs/t18_digit_products.py --max-base 6 > .timeloop/runs/t18_digit_products.json`

Expected: valid JSON covering bases 2 through 6, with complete cycle sets below the proved bound for each base. Do not extend to base 7: its proved bound exceeds one billion states, so exhaustive traversal would violate the overnight checkpoint policy.

- [ ] **Step 4: Implement the independent verifier without imports from `.timeloop/lib`**

The independent script must transcribe base conversion using `divmod`, compute products with an explicit loop rather than `math.prod`, scan every state from `0` through the recorded bound, reconstruct cycles with a separate tortoise/path algorithm, and compare canonical cycle sets to `t18_digit_products.json`. It must exit nonzero on any mismatch and print one `PASS base=<b> states=0..<B>` line per base.

Run: `uv run python .timeloop/runs/t18_digit_products_independent.py .timeloop/runs/t18_digit_products.json`

Expected: one `PASS` line for every recorded base and exit code 0.

- [ ] **Step 5: Write the Track A notebook from evidence**

Create all required sections: `STATUS`, `SEARCHED`, `RULED OUT`, `STRUCTURE`, `TECHNIQUE`, `NOVELTY`, `NEXT`, and `COST`. Include the exact base range, every independently reproduced counterexample, the proof of the eventual-decrease bound, and the Math Prism invalid-artifact result. Do not mark the target `resolved` unless the notebook precisely limits resolution to the selected map family.

- [ ] **Step 6: Commit the independently checked Track A evidence**

```bash
git add .timeloop/runs/t18_digit_products.py \
  .timeloop/runs/t18_digit_products_independent.py \
  .timeloop/runs/t18_digit_products.json \
  .timeloop/notebook/forge-digit-products.md \
  .timeloop/tests/test_digitproducts.py
git commit -m "exp: map mixed digit-product dynamics"
```

---

### Task 3: Lean-Check the Track A Fixed-Point Obstruction

**Files:**
- Create: `.timeloop/lean/arena/Arena/DigitProducts.lean`
- Modify: `.timeloop/lean/arena/Arena.lean`

**Interfaces:**
- Consumes: the mathematical definition `P(ds) + S(ds)` used by Tasks 1 and 2.
- Produces: `digitProductPlusSum_modEq` and `digitProductPlusSum_fixed_product_zero`.

- [ ] **Step 1: Add the theorem statement with `by` holes represented as `sorry`**

```lean
import Arena.Basic

open Nat List

theorem digitProductPlusSum_modEq (base n : ℕ) (hb : 2 ≤ base) :
    (base.digits n).prod + (base.digits n).sum ≡
      (base.digits n).prod + n [MOD base - 1] := by
  sorry

theorem digitProductPlusSum_fixed_product_zero (base n : ℕ) (hb : 2 ≤ base)
    (hfix : (base.digits n).prod + (base.digits n).sum = n) :
    (base.digits n).prod ≡ 0 [MOD base - 1] := by
  sorry
```

- [ ] **Step 2: Compile to confirm the file is the only unproved boundary**

Run: `cd .timeloop/lean/arena && lake env lean Arena/DigitProducts.lean`

Expected: exit code 0 with declarations warning that they use `sorry`.

- [ ] **Step 3: Replace `sorry` with proofs built from `Nat.modEq_digits_sum`**

Handle `base = 2` explicitly as in `digitPow_modEq`; for `base = k + 1`, derive `n ≡ (base.digits n).sum [MOD k]`, add the product to both sides, and use `hfix` to rewrite the fixed-point equation. Do not weaken the statement to a finite modulus or insert `native_decide` over bounded inputs.

- [ ] **Step 4: Add axiom audits and import the module**

Append:

```lean
#print axioms digitProductPlusSum_modEq
#print axioms digitProductPlusSum_fixed_product_zero
```

Change `.timeloop/lean/arena/Arena.lean` to:

```lean
import Arena.Basic
import Arena.DigitProducts
```

- [ ] **Step 5: Build and inspect the audit**

Run: `cd .timeloop/lean/arena && lake build 2>&1 | tee ../../../runs/t18_lean_build.txt`

Expected: exit code 0; both audit lines omit `sorryAx`.

- [ ] **Step 6: Commit the checked obstruction**

```bash
git add .timeloop/lean/arena/Arena.lean \
  .timeloop/lean/arena/Arena/DigitProducts.lean \
  .timeloop/runs/t18_lean_build.txt
git commit -m "proof: check mixed digit-map obstruction"
```

---

### Task 4: Exact Erdős–Straus Kernel and Positive Controls

**Files:**
- Create: `.timeloop/tests/test_erdos_straus.py`
- Create: `.timeloop/lib/erdos_straus.py`

**Interfaces:**
- Produces: `is_decomposition(n: int, x: int, y: int, z: int) -> bool` using cross-multiplication only.
- Produces: `factor_pair_solutions(n: int, x: int) -> tuple[tuple[int, int], ...]` for ordered `x <= y <= z` solutions.
- Produces: `first_solution(n: int) -> tuple[int, int, int] | None` over `ceil(n/4) <= x <= floor(3n/4)`.

- [ ] **Step 1: Write exact positive and negative tests**

```python
from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from erdos_straus import factor_pair_solutions, first_solution, is_decomposition


def test_exact_decomposition_predicate() -> None:
    assert is_decomposition(5, 2, 4, 20)
    assert not is_decomposition(5, 2, 4, 19)
    assert not is_decomposition(5, 0, 4, 20)


def test_even_positive_control() -> None:
    for n in range(2, 100, 2):
        assert is_decomposition(n, n // 2, n, n)


def test_three_mod_four_positive_control() -> None:
    for n in range(3, 100, 4):
        assert is_decomposition(n, (n + 1) // 4, n * (n + 1) // 2, n * (n + 1) // 2)


def test_factor_pair_generator_matches_bruteforce_for_small_n() -> None:
    for n in range(2, 30):
        for x in range((n + 3) // 4, (3 * n) // 4 + 1):
            got = set(factor_pair_solutions(n, x))
            residual_numerator = 4 * x - n
            if residual_numerator <= 0:
                want: set[tuple[int, int]] = set()
            else:
                max_y = (2 * n * x) // residual_numerator
                want = set()
                for y in range(x, max_y + 1):
                    remainder = Fraction(4, n) - Fraction(1, x) - Fraction(1, y)
                    if remainder > 0 and remainder.numerator == 1:
                        z = remainder.denominator
                        if y <= z:
                            want.add((y, z))
            assert got == want


def test_first_solution_covers_small_range() -> None:
    for n in range(2, 500):
        solution = first_solution(n)
        assert solution is not None
        assert is_decomposition(n, *solution)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest .timeloop/tests/test_erdos_straus.py -q`

Expected: collection fails with `ModuleNotFoundError: No module named 'erdos_straus'`.

- [ ] **Step 3: Implement exact factor-pair generation**

For fixed `n, x`, set `a = 4*x - n` and `q = n*x`. Use the identity
`(a*y - q)(a*z - q) = q^2`. Factor `q` with `sympy.factorint`, double every exponent to obtain the factorization of `q^2`, generate its positive divisors combinatorially, pair each `d` with `q*q // d`, and retain only values for which `(d + q) % a == 0`, `(q*q // d + q) % a == 0`, `x <= y <= z`, and `is_decomposition` succeeds. Reject nonpositive inputs and `a <= 0`. In `first_solution`, return the explicit even and `3 mod 4` positive controls before entering the generic `x` scan.

- [ ] **Step 4: Run and optimize the focused tests without weakening them**

Run: `uv run pytest .timeloop/tests/test_erdos_straus.py -q`

Expected: all tests pass. The brute-force oracle is finite because ordered solutions satisfy `y <= 2*n*x/(4*x-n)`; do not replace it with a sampled oracle.

- [ ] **Step 5: Commit the exact kernel**

```bash
git add .timeloop/lib/erdos_straus.py .timeloop/tests/test_erdos_straus.py
git commit -m "feat: add exact Erdos-Straus verifier"
```

---

### Task 5: Residue Exploration, Independent Identity Check, and Lean Controls

**Files:**
- Create: `.timeloop/runs/t19_erdos_residues.py`
- Create: `.timeloop/runs/t19_erdos_independent.py`
- Create: `.timeloop/notebook/erdos-straus.md`
- Create: `.timeloop/lean/arena/Arena/ErdosStraus.lean`
- Modify: `.timeloop/lean/arena/Arena.lean`

**Interfaces:**
- Consumes: `factor_pair_solutions`, `first_solution`, and `is_decomposition` from Task 4.
- Produces: `.timeloop/runs/t19_erdos_residues.json` with `m_range`, `prime_n`, `solutions`, `wild`, `modulus`, and `residue_summary`.
- Produces: Lean theorems `erdosStraus_even` and `erdosStraus_three_mod_four`.

- [ ] **Step 1: Implement the scoped residue explorer**

Parse `--max-m`, `--modulus`, `--checkpoint`, and optional `--resume`. For every prime `n = 24*m + 1` with `1 <= m <= max_m`, scan `x = 6*m + k` for `1 <= k <= 12*m`, stop at the first exact factor-pair solution, and otherwise record `n` in `wild`. Group `m` by residue modulo the requested modulus and record solved/total counts without inferring an infinite class. Write the checkpoint path atomically after every 25 values of `m`; `--resume` must validate the stored modulus and continue at the next unprocessed `m`.

Run: `uv run python .timeloop/runs/t19_erdos_residues.py --max-m 200 --modulus 840 --checkpoint .timeloop/runs/t19_erdos_checkpoint.json > .timeloop/runs/t19_erdos_residues.json`

Expected: valid JSON with every tested `n`, exact denominators for solved cases, and an explicit `wild` list comparable to Xu's 2026 definition. If the `m <= 200` run completes in less than 30 minutes, rerun with `--max-m 2000 --resume .timeloop/runs/t19_erdos_checkpoint.json --checkpoint .timeloop/runs/t19_erdos_checkpoint.json`; otherwise preserve the smaller exact range and move to identity analysis.

- [ ] **Step 2: Implement an independent verifier**

The verifier must not import `.timeloop/lib/erdos_straus.py`. It must parse each stored triple as integers, check positivity and ordering, and verify `4*x*y*z == n*(x*y + x*z + y*z)`. It must independently recompute primality by trial division through `isqrt(n)` and confirm each `n` has the stored form `24*m + 1`. Print exact failures and exit nonzero on the first mismatch.

Run: `uv run python .timeloop/runs/t19_erdos_independent.py .timeloop/runs/t19_erdos_residues.json`

Expected: exit code 0 and a summary naming the exact tested `m` range and number of checked triples.

- [ ] **Step 3: Search for a parameterized identity only inside structurally uniform solution data**

Group stored solutions by `(m mod 840, k, factor-pair shape)`. Use SymPy to fit candidate polynomial denominators in `t = (m-r)/840` only when at least six consecutive examples share the same shape. Symbolically simplify

```python
4 / n(t) - 1 / x(t) - 1 / y(t) - 1 / z(t)
```

to zero, factor all denominators, and derive explicit integer and positivity assumptions. Reject a fit when symbolic simplification is nonzero, when any denominator is nonintegral on its claimed class, or when the independent verifier finds a counterexample among the first 1,000 admissible `t` values beyond the fitting sample.

- [ ] **Step 4: Lean-check the two positive-control families**

Create the following statements and prove them with `field_simp`, `ring`, and positivity side conditions:

```lean
import Mathlib

theorem erdosStraus_even (k : ℕ) (hk : 0 < k) :
    (4 : ℚ) / (2 * k) = 1 / k + 1 / (2 * k) + 1 / (2 * k) := by
  push_cast
  field_simp
  ring

theorem erdosStraus_three_mod_four (k : ℕ) :
    (4 : ℚ) / (4 * k + 3) =
      1 / (k + 1) +
      1 / (((4 * k + 3) * (k + 1)) * 2) +
      1 / (((4 * k + 3) * (k + 1)) * 2) := by
  push_cast
  field_simp
  ring
```

Before accepting the second theorem, cross-check its denominators against the Python positive control; if the algebra reveals a factor-of-four discrepancy, correct the Lean and Python formula together and record it as a caught design error.

- [ ] **Step 5: Promote one discovered identity only if all gates pass**

Add a third Lean theorem only when the identity has: six fitting examples, symbolic zero residual, explicit integrality/positivity assumptions, 1,000 independent out-of-sample checks, and a completed novelty query. Name the theorem for its exact residue class rather than `erdosStraus_general`. If no identity passes, leave the file with the two controls and record `no promoted identity` in the notebook.

- [ ] **Step 6: Audit and build**

Append `#print axioms` for every theorem, import `Arena.ErdosStraus` from `Arena.lean`, and run:

`cd .timeloop/lean/arena && lake build 2>&1 | tee ../../../runs/t19_lean_build.txt`

Expected: exit code 0 and no `sorryAx` in the audit output.

- [ ] **Step 7: Write the Track B notebook and commit**

Include `STATUS`, `SEARCHED`, `RULED OUT`, `STRUCTURE`, `TECHNIQUE`, `NOVELTY`, `NEXT`, and `COST`. Distinguish finite tame coverage from a residue identity and from the full conjecture.

```bash
git add .timeloop/lib/erdos_straus.py \
  .timeloop/tests/test_erdos_straus.py \
  .timeloop/runs/t19_erdos_residues.py \
  .timeloop/runs/t19_erdos_independent.py \
  .timeloop/runs/t19_erdos_residues.json \
  .timeloop/runs/t19_lean_build.txt \
  .timeloop/notebook/erdos-straus.md \
  .timeloop/lean/arena/Arena.lean \
  .timeloop/lean/arena/Arena/ErdosStraus.lean
git commit -m "exp: test Erdos-Straus residue structure"
```

---

### Task 6: Novelty Search, Durable State, and Final Verification

**Files:**
- Modify: `.timeloop/notebook/forge-digit-products.md`
- Modify: `.timeloop/notebook/erdos-straus.md`
- Modify: `.timeloop/ledger.md`
- Modify: `.timeloop/pool.jsonl`

**Interfaces:**
- Consumes: checked outputs and candidate statements from Tasks 2, 3, and 5.
- Produces: two complete notebook records, two append-only ledger lines, and pool state consistent with the evidence.

- [ ] **Step 1: Run current novelty searches**

For Track A, search the exact map name, its recurrence, every promoted cycle sequence, and the fixed-point congruence in OEIS, arXiv, and Google Scholar or publisher indexes. For Track B, search the exact residue class, parameterized denominators, factor-pair identity, arXiv:2605.23601, and the cited primary references. Save exact queries and direct sources in each notebook.

- [ ] **Step 2: Assign typed novelty outcomes**

Use `published` when an exact or stronger statement is located, `superseded` when current literature goes beyond the experiment, and `not found` only with the complete query list. Never convert `not found` to `novel`.

- [ ] **Step 3: Update durable state**

Append exactly one `T18` line for `forge-digit-products` and one `T19` line for `erdos-straus`. Update `reps` from `untried` to `done` for each attempted target. Change `status` only when the notebook's scope supports the new value; a bounded Erdős–Straus search remains `open`.

- [ ] **Step 4: Run all experiment checks**

```bash
uv run pytest .timeloop/tests/test_digitproducts.py .timeloop/tests/test_erdos_straus.py -q
.timeloop/bin/exam
.timeloop/bin/lint
cd .timeloop/lean/arena && lake build
```

Expected: pytest passes; the exam reports all items passing; arena lint reports `arena lint: clean`; Lean exits 0 with no `sorryAx` in the new theorem audits.

- [ ] **Step 5: Confirm process and worktree hygiene**

Run:

```bash
.timeloop/bin/reap
git diff --check
git status --short
```

Expected: no orphaned arena process, no whitespace errors, and the user's pre-existing `.timeloop/exam/results.jsonl` modification still present and unstaged unless the exam appends a new record. Any new exam record belongs to this run and must be described separately rather than folded into the user's prior modification.

- [ ] **Step 6: Commit only verified durable records**

```bash
git add .timeloop/ledger.md .timeloop/pool.jsonl \
  .timeloop/notebook/forge-digit-products.md \
  .timeloop/notebook/erdos-straus.md
git commit -m "docs: record overnight conjecture outcomes"
```

- [ ] **Step 7: Report calibrated outcomes**

Report machine-checked theorems, independently reproduced counterexamples, exact bounded ranges, novelty lookup outcomes, and unresolved blockers separately. Do not summarize the whole run as a success merely because the verification machinery passed.
