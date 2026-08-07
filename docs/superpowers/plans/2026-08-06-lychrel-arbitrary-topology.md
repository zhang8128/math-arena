# T24 Arbitrary-Digit Lychrel Topology Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exactly classify arbitrary fixed-digit realizations of the T21 six-phase topology in bases `18..40`, with a base-17 calibration and independently encoded negative audit.

**Architecture:** A pure-Python library renders the immutable topology and compiles deterministic one-hot CNF for concrete parameters. A Sage/PicoSAT run performs the primary `n=0` scan and only escalates survivors to `n=0,1,2`; a standalone JSON-driven binary encoding is solved by CaDiCaL as an independent audit. Existing polynomial and integer verifiers remain the acceptance boundary for positives.

**Tech Stack:** Python 3.9, SageMath 10.9 Python 3.14, PicoSAT/pycosat, CaDiCaL 3.0.1, pytest, exact integer arithmetic.

## Global Constraints

- Preserve the exact T21 six-phase fragment lengths and repeat locations.
- Map repeat digits `0 -> 0` and `16 -> B-1`.
- Give every one of the 497 fixed occurrences an independent domain `0..B-1`.
- Use fresh Boolean carries and classify every base in the inclusive range `18..40`.
- Treat `n=0` UNSAT as decisive; use `n=0,1,2` plus exact `Z[q]` verification for every survivor.
- Do not modify `.timeloop/exam/results.jsonl`.
- Do not report Prism hypotheses as verified mathematics.

---

### Task 1: Topology renderer and exact column constraints

**Files:**
- Create: `.timeloop/lib/lychrel_arbitrary_topology.py`
- Create: `.timeloop/tests/test_lychrel_arbitrary_topology.py`

**Interfaces:**
- Consumes: `ParametricWord` from `lychrel_wordproof`.
- Produces: `DigitAtom`, `ColumnConstraint`, `render_arbitrary(words, phase, n, base)`, and `build_column_constraints(words, base, parameters=(0,))`.

- [ ] **Step 1: Write failing hand-derived renderer and column tests**

```python
def test_renderer_maps_repeats_but_not_fixed_occurrences():
    word = ParametricWord(17, ((3,), (4,), (5,)), (0, 16))
    assert render_arbitrary((word,), 0, 1, 20) == (
        DigitAtom("p0:f0:d0"), DigitAtom(None, 0),
        DigitAtom("p0:f1:d0"), DigitAtom(None, 19),
        DigitAtom("p0:f2:d0"),
    )

def test_column_constraint_is_hand_derived():
    words = (
        ParametricWord(17, ((3, 5),), ()),
        ParametricWord(17, ((8, 8),), ()),
    )
    assert build_column_constraints(words, 20, parameters=(0,), phases=(0,))[0] == ColumnConstraint(
        left=DigitAtom("p0:f0:d0"), right=DigitAtom("p0:f0:d1"),
        target=DigitAtom("p1:f0:d1"), carry_in=None,
        carry_out="c:p0:n0:col0", provenance="phase=0,n=0,column=0",
    )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m pytest .timeloop/tests/test_lychrel_arbitrary_topology.py -q`

Expected: collection fails because `lychrel_arbitrary_topology` does not exist.

- [ ] **Step 3: Implement the immutable renderer and compiler**

Implement frozen dataclasses, base/phase/parameter validation, wrap `n -> n+1`, fixed-zero boundary atoms, and stable occurrence/carry keys. No SAT dependency enters this module.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run: `python3 -m pytest .timeloop/tests/test_lychrel_arbitrary_topology.py -q`

Expected: renderer and literal column tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add .timeloop/lib/lychrel_arbitrary_topology.py .timeloop/tests/test_lychrel_arbitrary_topology.py
git commit -m "feat: compile arbitrary-digit topology columns"
```

### Task 2: Deterministic one-hot CNF and calibration assignment

**Files:**
- Modify: `.timeloop/lib/lychrel_arbitrary_topology.py`
- Modify: `.timeloop/tests/test_lychrel_arbitrary_topology.py`

**Interfaces:**
- Consumes: `tuple[ColumnConstraint, ...]` from Task 1.
- Produces: `CNFFormula`, `compile_one_hot_cnf(words, base, parameters=(0,))`, `reference_assignment(words, formula)`, `assignment_satisfies(formula, assignment)`, `decode_digit_assignment(formula, model)`, and `materialize_cycle(words, base, digits)`.

- [ ] **Step 1: Write failing tests for a literal truth table and base-17 reference assignment**

Use a two-digit, two-phase fixture to assert literal domain clauses, one valid transition implication, one invalid boundary implication, stable DIMACS bytes, and a 64-character digest. Add a T21 test requiring exactly 497 digit keys, 499 `n=0` constraints, and satisfaction by the published base-17 digit/carry assignment.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python3 -m pytest .timeloop/tests/test_lychrel_arbitrary_topology.py -q`

Expected: failures name the missing CNF APIs.

- [ ] **Step 3: Implement one-hot allocation and transition implications**

Allocate variables deterministically by semantic key; emit at-least-one and pairwise at-most-one clauses; forbid zero at each leading fixed occurrence; and force target/carry outputs for every legal `(left, right, carry_in)` combination. Expose DIMACS serialization and SHA-256 without importing a solver.

- [ ] **Step 4: Implement the independent reference assignment builder**

Read actual base-17 rendered digits, replay each column to derive carries, map every semantic Boolean to a truth value, and make `assignment_satisfies` reject missing variables or unsatisfied clauses.

Add decoding from a SAT model to one integer per fixed occurrence and materialization into six `ParametricWord` values with repeats mapped to `0` and `B-1`.

- [ ] **Step 5: Run focused and regression tests GREEN**

Run: `python3 -m pytest .timeloop/tests/test_lychrel_arbitrary_topology.py .timeloop/tests/test_lychrel_wordproof.py -q`

Expected: all tests pass, including exact base-17 polynomial verification.

- [ ] **Step 6: Commit Task 2**

```bash
git add .timeloop/lib/lychrel_arbitrary_topology.py .timeloop/tests/test_lychrel_arbitrary_topology.py
git commit -m "feat: encode arbitrary-digit topology as CNF"
```

### Task 3: Primary PicoSAT scan and evidence

**Files:**
- Create: `.timeloop/runs/t24_lychrel_arbitrary_topology.py`
- Create: `.timeloop/runs/t24_lychrel_arbitrary_topology.json`
- Modify: `.timeloop/tests/test_lychrel_arbitrary_topology.py`

**Interfaces:**
- Consumes: Task 2 CNF APIs and the T22 reference cycle.
- Produces: `solve_formula(formula)`, `build_evidence()`, and deterministic T24 JSON.

- [ ] **Step 1: Write a failing Sage subprocess evidence test**

Run the script with `/usr/local/bin/sage -python`; assert base-17 assignment calibration, inclusive bases `18..40`, 23 results, early-exit parameters `[0]` for every UNSAT base, no hits, exact clause/DIMACS metadata, and two Prism provenance hashes.

- [ ] **Step 2: Verify the evidence test is RED**

Run: `python3 -m pytest .timeloop/tests/test_lychrel_arbitrary_topology.py::test_primary_evidence_scans_every_base -q`

Expected: failure because the T24 run script is absent.

- [ ] **Step 3: Implement lazy pycosat solving and survivor escalation**

Import `pycosat` only inside the Sage run. Map `UNSAT` to a negative result; for a satisfying `n=0` assignment, rebuild parameters `(0,1,2)`, solve again, decode a cycle, and require `verify_cycle` plus six `fixed_palindrome_mismatch` witnesses before reporting a hit.

- [ ] **Step 4: Generate deterministic evidence twice**

```bash
/usr/local/bin/sage -python .timeloop/runs/t24_lychrel_arbitrary_topology.py > /tmp/t24-a.json
/usr/local/bin/sage -python .timeloop/runs/t24_lychrel_arbitrary_topology.py > /tmp/t24-b.json
cmp /tmp/t24-a.json /tmp/t24-b.json
cp /tmp/t24-a.json .timeloop/runs/t24_lychrel_arbitrary_topology.json
```

Expected: byte-identical generated artifacts.

- [ ] **Step 5: Run focused tests GREEN and commit Task 3**

```bash
python3 -m pytest .timeloop/tests/test_lychrel_arbitrary_topology.py -q
git add .timeloop/runs/t24_lychrel_arbitrary_topology.py .timeloop/runs/t24_lychrel_arbitrary_topology.json .timeloop/tests/test_lychrel_arbitrary_topology.py
git commit -m "exp: scan arbitrary-digit base17 topology"
```

### Task 4: Standalone binary/CaDiCaL audit

**Files:**
- Create: `.timeloop/runs/t24_lychrel_arbitrary_topology_independent.py`
- Modify: `.timeloop/runs/t24_lychrel_arbitrary_topology.py`
- Modify: `.timeloop/tests/test_lychrel_arbitrary_topology.py`

**Interfaces:**
- Consumes: `.timeloop/runs/t21_lychrel_multi_interface.json` only.
- Produces: standalone JSON with binary encoding, CaDiCaL identity, per-base status/count/digest, and agreement summary.

- [ ] **Step 0: Install the pinned independent solver if absent**

Run: `command -v cadical >/dev/null || brew install cadical`

Expected: `cadical --version` reports `3.0.1`.

- [ ] **Step 1: Write a failing subprocess audit test**

Assert the script imports no production T24 module, tests exactly bases `18..40`, reports 23 UNSAT results, uses binary digit domains, and emits a different DIMACS digest from the primary encoding for base 18.

- [ ] **Step 2: Verify the audit test is RED**

Run: `python3 -m pytest .timeloop/tests/test_lychrel_arbitrary_topology.py::test_standalone_binary_audit -q`

Expected: failure because the audit script is absent.

- [ ] **Step 3: Implement the JSON-driven binary encoder**

Parse phase fragments/repeats directly; allocate `ceil(log2(B))` bits per digit; forbid values `B..2**k-1`; forbid all-zero leading bits; enumerate legal inputs/carry to imply literal target bits and outgoing carries; and serialize DIMACS in a temporary directory.

- [ ] **Step 4: Solve with CaDiCaL and cross-check all bases**

Invoke `cadical --quiet <cnf>` and accept only exit `20` plus `s UNSATISFIABLE`. Record `cadical --version`, counts, and SHA-256; print elapsed time only as a non-artifact diagnostic. Fail closed on a missing solver or any SAT/UNKNOWN status.

- [ ] **Step 5: Add audit summary to primary evidence and run GREEN**

Run both scripts twice and compare their bytes, then run the focused pytest file. Require exact base/status agreement while retaining distinct encoding counts and digests.

- [ ] **Step 6: Commit Task 4**

```bash
git add .timeloop/runs/t24_lychrel_arbitrary_topology.py .timeloop/runs/t24_lychrel_arbitrary_topology.json .timeloop/runs/t24_lychrel_arbitrary_topology_independent.py .timeloop/tests/test_lychrel_arbitrary_topology.py
git commit -m "test: independently audit arbitrary topology scan"
```

### Task 5: Research record, Prism outcomes, and integration verification

**Files:**
- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `.timeloop/ledger.md`

**Interfaces:**
- Consumes: verified T24 primary and audit JSON.
- Produces: scoped mathematical record and one explicit next experiment.

- [ ] **Step 1: Record the exact scoped result**

Document 497 arbitrary digit variables, the 499-column `n=0` obstruction, bases `18..40`, base-17 calibration, both encodings/solvers/digests, the absence of an optimization stage, and the fact this is not a theorem about other topologies or Lychrel numbers.

- [ ] **Step 2: Record Prism outcomes after verification**

Mark the layered carry-hypergraph disposition useful; mark predicted feasible components, carry-flux invariant, determinant/resultant invariant, and bounded-treewidth claim unsupported or falsified as appropriate. Do not evolve frames from a claim lacking independent evidence.

- [ ] **Step 3: Record the next experiment**

Queue a bounded topology relaxation: move one repeat interface by at most two columns while retaining six phases, then use the same `n=0` dual-encoding filter before all-`n` verification.

- [ ] **Step 4: Run full verification**

```bash
python3 -m pytest .timeloop/tests -q
/usr/local/bin/sage -python .timeloop/runs/t24_lychrel_arbitrary_topology.py > /tmp/t24-final.json
python3 .timeloop/runs/t24_lychrel_arbitrary_topology_independent.py > /tmp/t24-audit-final.json
git diff --check
```

Expected: all tests pass; both scripts report 23 independently UNSAT bases; no whitespace errors.

- [ ] **Step 5: Commit the research record**

```bash
git add .timeloop/notebook/lychrel-bases.md .timeloop/ledger.md docs/superpowers/specs/2026-08-06-lychrel-arbitrary-topology-design.md docs/superpowers/plans/2026-08-06-lychrel-arbitrary-topology.md
git commit -m "docs: record arbitrary topology obstruction"
```

- [ ] **Step 6: Complete the branch workflow**

Use `superpowers:verification-before-completion`, then `superpowers:finishing-a-development-branch`; integrate the verified branch into `main` without changing the pre-existing `.timeloop/exam/results.jsonl` modification.
