# Lychrel Affine Lift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide exactly whether the verified base-17 two-interface certificate has a global integer-affine digit lift with the same six-phase topology for every base `b >= 17`.

**Architecture:** A local Boolean carry CSP discovers lower/upper digit anchors while retaining equation provenance. A separately implemented bivariate polynomial compiler accepts a candidate only through coefficient equality in `Z[b,q]`, where `q=b^n`; an infeasible CSP is reduced to an independently rechecked irreducible core.

**Tech Stack:** Python 3.14 standard library, immutable dataclasses, exact integer tuples, pytest, the existing T21 parametric-word fixture.

## Global Constraints

- Preserve `.timeloop/exam/results.jsonl` untouched.
- Use `qwen3.6:27b-mlx` for Prism disposition generation only.
- Treat Prism artifacts and carry-CSP solutions as hypotheses, never proof.
- Add no solver dependency; the Boolean equations have arity at most three.
- Accept a lift only through exact bivariate coefficient equality and exact non-palindrome witnesses.
- State negative scope precisely: same topology and integer affine digits valid for every `b >= 17`; use global coefficient equations so carries may change with the base.
- Run all work inline because the user selected isolated autonomous execution.

---

### Task 1: Exact bivariate certificate algebra

**Files:**
- Create: `.timeloop/lib/lychrel_affine.py`
- Create: `.timeloop/tests/test_lychrel_affine.py`

**Interfaces:**
- Consumes: `AffineDigit(intercept, slope, reference_base=17)` and `AffineWord(fragments, repeats)`.
- Produces: `evaluate_digit`, `render_affine_word`, `value_bivariate`, `reverse_affine_word`, `shift_q_parameter`, and `verify_affine_cycle`.

- [x] **Step 1: Write the failing affine-evaluation and polynomial tests**

```python
def test_affine_digits_are_lower_or_upper_anchored() -> None:
    assert AffineDigit(5, 0).evaluate(23) == 5
    assert AffineDigit(5, 1).evaluate(23) == 11


def test_two_interface_bivariate_compiler_matches_literal_values() -> None:
    word = AffineWord(
        fragments=((AffineDigit(1, 0),), (AffineDigit(2, 1),), (AffineDigit(3, 0),)),
        repeats=(0, 1),
    )
    polynomial = value_bivariate(word)
    for base in (17, 18, 31):
        for n in range(4):
            assert evaluate_bivariate(polynomial, base, base**n) == digits_value(
                word.render(base, n), base
            )
```

- [x] **Step 2: Run the tests and verify the missing-module failure**

Run: `pytest -q .timeloop/tests/test_lychrel_affine.py -k 'affine_digits or bivariate_compiler'`

Expected: collection fails because `lychrel_affine` does not exist.

- [x] **Step 3: Implement immutable base-polynomial and q-polynomial arithmetic**

Use tuples in ascending degree. Implement trim, add, scale, multiplication by `b^k`, multiplication by `q`, and `q -> bq`. Compile a fixed affine digit as `(intercept - 17*slope, slope)` in `b`.

- [x] **Step 4: Implement affine words, reversal, canonical validation, and cycle verification**

`verify_affine_cycle` must reject empty or leading-zero renderings at `n=0,1`, compare each ordinary phase coefficient-wise, and apply `q -> bq` only on the last phase.

- [x] **Step 5: Run Task 1 tests**

Run: `pytest -q .timeloop/tests/test_lychrel_affine.py`

Expected: all Task 1 tests pass.

### Task 2: Provenance-bearing carry CSP

**Files:**
- Create: `.timeloop/lib/lychrel_anchor_csp.py`
- Modify: `.timeloop/tests/test_lychrel_affine.py`

**Interfaces:**
- Consumes: a tuple of T21 `ParametricWord` phases and reference base 17.
- Produces: `AnchorVariable`, `CarryEquation`, `build_carry_equations`, `solve_boolean_equations`, `irreducible_unsat_core`, and `materialize_affine_cycle`.

- [x] **Step 1: Write failing literal Boolean-system tests**

```python
def test_boolean_solver_finds_the_hand_solution() -> None:
    equations = (
        CarryEquation((("x", 1), ("y", 1)), 1, provenance="sum"),
        CarryEquation((("x", 1), ("y", -1)), -1, provenance="difference"),
    )
    assert solve_boolean_equations(equations, limit=2) == ({"x": 0, "y": 1},)


def test_unsat_core_is_irreducible() -> None:
    equations = (
        CarryEquation((("x", 1),), 0, provenance="x=0"),
        CarryEquation((("x", 1),), 1, provenance="x=1"),
        CarryEquation((("y", 1),), 0, provenance="irrelevant"),
    )
    core = irreducible_unsat_core(equations)
    assert tuple(item.provenance for item in core) == ("x=0", "x=1")
    assert all(solve_boolean_equations(core[:i] + core[i + 1 :]) for i in range(len(core)))
```

- [x] **Step 2: Run the solver tests and verify missing-symbol failures**

Run: `pytest -q .timeloop/tests/test_lychrel_affine.py -k 'boolean_solver or unsat_core'`

Expected: failures naming the absent CSP interfaces.

- [x] **Step 3: Implement normalized equations and arc-consistent backtracking**

Combine repeated coefficients, drop zeros, propagate domains by enumerating the at-most-three unknown bits in each equation, branch on the highest-frequency unresolved variable, and return lexicographically ordered solutions up to `limit`.

- [x] **Step 4: Implement deletion-minimized infeasible cores**

Starting with all equations, remove an equation whenever the remainder is still infeasible. Recheck the final core by asserting the core is infeasible and every one-equation deletion is feasible.

- [x] **Step 5: Write and run a failing carry-extraction fixture**

Use a hand-derived one-column base-17 addition whose constants satisfy the reference equation and whose affine coefficient requires `x_left+x_right-x_output=carry_out`. Assert exact coefficients, right-hand side, and `(phase,n,column)` provenance.

- [x] **Step 6: Implement symbolic column rendering and carry extraction for `n=0..3`**

Fixed occurrences reuse their stable variable IDs under reversal. Repeat zero and `b-1` tokens contribute constant slopes zero and one. The wrap phase renders phase zero at `n+1`; all other outputs use `n`.

- [x] **Step 7: Run Task 2 tests and the existing T21 tests**

Run: `pytest -q .timeloop/tests/test_lychrel_affine.py .timeloop/tests/test_lychrel_wordproof.py`

Expected: all tests pass.

### Task 3: Base-17 topology classification experiment

**Files:**
- Modify: `.timeloop/tests/test_lychrel_affine.py`
- Create: `.timeloop/runs/t22_lychrel_affine_lift.py`
- Create: `.timeloop/runs/t22_lychrel_affine_lift.json`

**Interfaces:**
- Consumes: the T21 `calibrate_base17()` phase fragments and repeats.
- Produces: deterministic JSON containing system size, solution count or minimized obstruction, exact verification, non-palindrome evidence, and direct replay checks.

- [x] **Step 1: Write the failing real-fixture classification test**

```python
def test_base17_topology_has_exact_affine_classification() -> None:
    reference = base17_reference_cycle()
    result = classify_affine_lift(reference, reference_base=17)
    assert result.status in {"verified_lift", "infeasible"}
    if result.status == "verified_lift":
        assert all(verify_affine_cycle(cycle) for cycle in result.cycles)
    else:
        assert not solve_boolean_equations(result.unsat_core)
        assert all(
            solve_boolean_equations(result.unsat_core[:i] + result.unsat_core[i + 1 :])
            for i in range(len(result.unsat_core))
        )
```

- [x] **Step 2: Run the fixture test and verify the missing-classifier failure**

Run: `pytest -q .timeloop/tests/test_lychrel_affine.py -k base17_topology -vv`

Expected: failure naming `classify_affine_lift`.

- [x] **Step 3: Implement classification and independent acceptance**

First classify the base-17 carry skeleton. If it is infeasible, linearize every global `Z[b,q]` residual coefficient in the anchors and solve that system, removing the carry-skeleton assumption. For every solution, materialize affine words and retain it only if the independent bivariate verifier succeeds. For a verified lift, require a same-slope fixed outer mismatch in every phase and replay all transitions at bases `17,18,20,26,40,100`, `n=0..5`. For no solution, compute and recheck the global irreducible core.

- [x] **Step 4: Implement and run the deterministic evidence script**

Run: `python3 .timeloop/runs/t22_lychrel_affine_lift.py > .timeloop/runs/t22_lychrel_affine_lift.json`

Expected: JSON status `verified_lift` or `infeasible`, with every claimed check explicitly true.

- [x] **Step 5: Run focused tests**

Run: `pytest -q .timeloop/tests/test_lychrel_affine.py`

Expected: all focused tests pass.

### Task 4: Evaluation, Prism outcome, and durable record

**Files:**
- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `.timeloop/ledger.md`
- Modify: `.timeloop/pool.jsonl`
- Modify: this plan to mark completed steps.

**Interfaces:**
- Consumes: deterministic T22 JSON and primary-source searches.
- Produces: a scope-calibrated research conclusion and the next falsifiable action.

- [x] **Step 1: Independently audit the result**

If feasible, implement a direct integer replay path that does not call the bivariate compiler. If infeasible, parse the serialized core in a fresh process, verify the reference base-17 arithmetic for every core column, and independently brute-force each core deletion.

- [x] **Step 2: Perform mandatory novelty searches**

Search David Seal's page, OEIS, the Lychrel classification paper, and exact phrases for affine base-parametric reverse-add certificates. A negative lift classification is reported only as a scoped internal result unless directly matched by prior art.

- [x] **Step 3: Record only a narrow typed Prism outcome**

Attach `computationally_supported` only if the local carry-feasibility prediction was independently validated. Use `falsified` if the artifact's explicit predicted all-base carry closure fails. Include scope and non-endorsement fields in verifier metadata; do not support the proposed modular invariant or two-base proof.

- [x] **Step 4: Update notebook, ledger, and target next action**

Record `STATUS`, `SEARCHED`, `RULED OUT`, `STRUCTURE`, `TECHNIQUE`, `NOVELTY`, `NEXT`, and `COST`. Distinguish an all-base theorem from an obstruction confined to this affine topology.

- [x] **Step 5: Run final verification**

Run:

```bash
python3 -m py_compile .timeloop/lib/lychrel_affine.py .timeloop/lib/lychrel_anchor_csp.py .timeloop/runs/t22_lychrel_affine_lift.py
python3 -m json.tool .timeloop/runs/t22_lychrel_affine_lift.json >/dev/null
python3 .timeloop/runs/t22_lychrel_affine_lift.py >/tmp/t22-rescan.json
cmp -s .timeloop/runs/t22_lychrel_affine_lift.json /tmp/t22-rescan.json
pytest -q .timeloop/tests
git diff --check
```

Expected: compilation and JSON validation succeed, the rescan is byte-identical, all arena tests pass, and the diff check emits no output.
