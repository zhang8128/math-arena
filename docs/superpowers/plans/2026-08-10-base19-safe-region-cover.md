# Base-19 Safe-Region Cover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Execute inline without subagents.

**Goal:** Decide whether at most six compact, seed-derived Presburger regions
cover all 18 promoted layer-30 inputs while every exact layer-30-to-31
successor from those regions satisfies T30's five-equation predicate `Q0`.

**Architecture:** A T33-local typed layer tightens T31's normalized affine atom
representation to the approved two-variable, coefficient-three grammar. A
primary Z3 runner hash-binds and replays the T29--T32 boundary, derives finite
atom pools from canonical promoted-state pairs, deletion-minimizes named UNSAT
cores, and performs a bounded deterministic cover search. An isolated
standard-library checker independently rebuilds the raw transfer equations,
enumerates all 77,824 layer-30 inputs, and verifies exact safety, coverage,
ownership, extents, and compactness before any PASS artifact is persisted.

**Tech Stack:** Python 3.13 via `uv`, frozen dataclasses, canonical JSON,
`z3-solver` 5.x for primary exact queries and named cores, Python
standard-library generalized arc consistency/backtracking for independent
assurance, pytest 8.x, Ruff, and SHA-256.

## Global Constraints

- Work in `/Users/kairos/Projects/personal/math` inline without subagents.
- Preserve every existing user change. Never stage publication paths,
  `.timeloop/exam/results.jsonl`, `.timeloop/ledger.md`,
  `.timeloop/pool.jsonl`, unrelated notebooks, or `.DS_Store` files.
- Do not modify `publication/base19-radial/preprint/` or
  `publication/base19-radial/preprint.zip`. The ZIP SHA-256 must remain
  `e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33`.
- Bind the approved T33 design SHA-256
  `dadd1fe42f32d6f61b72609394f2172ca4fac3a6979660d03453058a221322a0`.
- Bind raw source hashes: equations
  `ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040`,
  frontier `0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0`,
  and provenances
  `cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302`.
- Bind T29 evidence, trace, dataset, certificate, and independent hashes:
  `c1e3dc4bc4ab07207a6ab49d6a9c9fd86486013abeaf016b6ecd59c9755e1d32`,
  `c56877975293c10575009a691b1d1bbde376838f805d232a2c18a4d00b2c4715`,
  `6603e381805db845ef9388d234e36f31eba510d838ac98c143c238c2ff144995`,
  `1c234891f001cb3a59e5670560ab26e3cb248a943e249aee049aac7d32c7db5a`,
  and `9f926208cc7416e24d811f6cd54485d19741b6f8ffe44f3b365b2f816e579644`.
- Bind T30 evidence, certificate, independent, and report hashes:
  `4b327e826a8b2462eedffa2cf572b77155fc95d8e7b94a4430d7f0331f75bd2a`,
  `3ac0b6ae254ad8bb7c7b19754335ea6a81bea77a0dc808e7eda1cd8994839892`,
  `56037d658f628ffa526f9adb710746231806450717f7bde5c0655f4ed6388639`,
  and `3ea55f8410887d3a522436be38bf3d9b5c010ac3c412d48405cd69f19828b95c`.
- Bind T32 commits `df191a5`, `515bbdd`, `b5ff122`, `e4bc16d`, and
  `9d17f77`, and source hashes: library
  `cf6ad87c8edf3ffa2c86449b9762f8c9d4254645eb71b7f88963a688a1bded11`,
  runner `d9c90e0dc4ce910a6ddef66233b03bff31449a46662fba75628a44dca3ed9e57`,
  independent
  `fb520b513dd5673e145b583ee8a5025c8113890fdb89139a48b528655ed506b5`,
  and test `a6ee921a8ba6304d3a48b0db0b893b6bd8077576acc27146b91d626ac00858bd`.
- Bind the approved T32 design SHA-256
  `93cecb3d3ce2c6a2610454f63302e26e2bbe57c7eba1825474bc808ad9ff76bd`.
- Replay T32 exactly: its first type is phase-0 `digit_order = eq` and
  phase-0 `digit_sum < 19`, with PASS after three inspected witnesses and 31
  tested conjunctions; its family search stops at
  `CANDIDATE_BUDGET_EXHAUSTED`, 10,000 tested conjunctions, and eight exact
  witnesses. Do not require a nonexistent T32 durable artifact.
- Require base 19, removed coordinate `phase=0,n=0,column=82`, the original 12
  layer-30-to-31 equations, T30's immutable five equations `Q0`, and exactly 18
  distinct promoted layer-30 rows.
- Freeze the layer-30 scope as
  `L0,R0,L1,R1,L2,R2,L3,R3,L4,R4,L5,R5,D0`. The first 12 variables have
  domain `{0,1}` and `D0` has domain `0..18`, hence exactly 77,824 bounded
  assignments.
- Permit only normalized `eq`, `le`, and `congruent` atoms with one or two
  scoped variables, nonzero coefficient magnitudes at most three, and
  congruence moduli in `2..19`. A clause has one to six distinct atoms and a
  predicate has one to six distinct clauses.
- Every atom must arise from the approved canonical promoted seed-pair pool.
  Reject state numbers, row hashes/selectors, auxiliaries, direct `Q0` failure
  tests, nonlinear terms, topology changes, domain tautologies, singleton
  regions, and table-shaped minterms.
- Define `B30(u) := exists x,z . T(u,x,z) and not Q0(x)`. A safe clause or
  predicate must make its conjunction with `B30` exactly UNSAT; `UNKNOWN`
  always fails closed.
- The first milestone examines at most 153 canonical seed pairs and at most
  2,000 distinct region safety tests, including every named-core and deletion
  reduction tested. It must find one at-most-six-atom clause that contains its
  two seeds, has bounded extent at least four, and is smaller than the explicit
  table of the promoted rows it covers.
- Full search includes milestone work and tests at most 5,000 distinct regions,
  10,000 distinct candidate families, and six clauses. Every clause must cover
  at least two promoted rows and canonically own at least two first-match rows.
- PASS additionally requires all 18 promoted rows covered, complete-predicate
  safety UNSAT, predicate bytes strictly below T31's 616-byte promoted table,
  and fresh primary/isolated agreement on all recorded counts and bytes.
- A Task 4 STOP forbids Tasks 5--8. A Task 5 or Task 6 STOP forbids all later
  tasks. On STOP, create no durable T33 evidence, certificate, audit, report,
  or notebook section and begin no fallback experiment.
- The only PASS claims are `R30(u) => P30(u)` and
  `P30(u) and T(u,x,z) => Q0(x)`. Do not claim exact reachability, weakestness,
  induction, an unbounded orbit theorem, or a solver core as proof.
- Do not begin lower-layer extension, symbolic base lifting, base comparison,
  topology scans, publication changes, or Lean work.
- Prism remains hypothesis-only. Its status/framing operations failed after
  the `muse-glimmer:30b-mlx` switch; do not repair Prism or fabricate output.

## File Map

- Create `.timeloop/lib/lychrel_safe_region_cover.py` for the strict T33 atom,
  clause, predicate, provenance, reduction-trace, and certificate schemas;
  deterministic seed-pair pool generation; evaluation; compactness; and
  strict parsing.
- Create `.timeloop/runs/t33_base19_safe_region_cover.py` for frozen adapters,
  exact Z3 expressions, seed-pair core generalization, bounded region and cover
  search, fresh primary gates, conditional finalization, and report rendering.
- Create `.timeloop/runs/t33_base19_safe_region_cover_independent.py` for the
  isolated standard-library milestone and full-domain audits.
- Create `.timeloop/tests/test_lychrel_safe_region_cover.py` for grammar,
  boundary replay, pool generation, core minimization, STOP gates, independent
  CSP checks, deterministic search, mutation rejection, and artifact policy.
- Create only after every PASS gate reproduces:
  `.timeloop/runs/t33_base19_safe_region_cover.json`,
  `.timeloop/runs/t33_base19_safe_region_cover_certificate.json`,
  `.timeloop/runs/t33_base19_safe_region_cover_independent.json`, and
  `.timeloop/runs/t33_base19_safe_region_cover_report.md`.
- Modify `.timeloop/notebook/lychrel-bases.md` only after those four PASS
  artifacts reproduce. Do not edit any notebook on STOP.

---

### Task 1: T33 safe-region and certificate language

**Files:**

- Create: `.timeloop/lib/lychrel_safe_region_cover.py`
- Create: `.timeloop/tests/test_lychrel_safe_region_cover.py`

**Interfaces:**

- Reuse `ProjectionAtom` and `P30_VARIABLES` from
  `lychrel_bad_image_projection`, but wrap them in stricter T33 types so T31's
  coefficient-nine and two-clause limits cannot enter T33.
- Produce `SafeRegionClause`, `SafeRegionPredicate`, `SeedPair`,
  `CoreReductionStep`, `SafeRegionProvenance`, `SafeRegionCoverCertificate`,
  `generate_seed_pair_pool()`, `evaluate_safe_clause()`,
  `evaluate_safe_predicate()`, `clause_extent()`, `first_match_ownership()`,
  `compactness_bytes()`, and `parse_safe_region_cover_certificate()`.

- [ ] **Step 1: Write failing strict-grammar and evaluation tests**

Add these boundaries before implementation:

```python
def test_t33_clause_rejects_t31_atoms_outside_the_small_grammar() -> None:
    with pytest.raises(ValueError, match="support"):
        SafeRegionClause((ProjectionAtom("eq", (("L0", 1), ("R0", 1), ("L1", 1)), 0),))
    with pytest.raises(ValueError, match="coefficient"):
        SafeRegionClause((ProjectionAtom("le", (("D0", 4),), 18),))
    with pytest.raises(ValueError, match="scope"):
        SafeRegionClause((ProjectionAtom("eq", (("D1", 1),), 0),))


def test_safe_region_limits_and_canonical_order_are_strict() -> None:
    atoms = tuple(ProjectionAtom("le", (("D0", 1),), value) for value in range(6))
    clause = SafeRegionClause(tuple(reversed(atoms)))
    assert clause.atoms == tuple(sorted(atoms, key=canonical_bytes))
    with pytest.raises(ValueError, match="six atoms"):
        SafeRegionClause(atoms + (ProjectionAtom("eq", (("L0", 1),), 0),))
    with pytest.raises(ValueError, match="six clauses"):
        SafeRegionPredicate(30, P30_VARIABLES, tuple(clause for _ in range(7)))
```

Also test exact assignment keys/domains, all three relations, DNF evaluation,
77,824-domain iteration order, extent, first-match ownership, canonical bytes,
and rejection of repeated atoms/clauses and Boolean-as-integer values.

- [ ] **Step 2: Run Task 1 tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q
```

Expected: import failure for `lychrel_safe_region_cover`.

- [ ] **Step 3: Implement strict immutable types and evaluators**

Use these public shapes:

```python
@dataclass(frozen=True)
class SafeRegionClause:
    atoms: tuple[ProjectionAtom, ...]


@dataclass(frozen=True)
class SafeRegionPredicate:
    layer: int
    variables: tuple[str, ...]
    clauses: tuple[SafeRegionClause, ...]


@dataclass(frozen=True)
class SeedPair:
    indices: tuple[int, int]
    rows: tuple[tuple[int, ...], tuple[int, ...]]


@dataclass(frozen=True)
class CoreReductionStep:
    removed_atom_sha256: str
    candidate_sha256: str
    status: str
    retained: bool


@dataclass(frozen=True)
class SafeRegionProvenance:
    clause: SafeRegionClause
    seed_pair: SeedPair
    pool_size: int
    pool_sha256: str
    solver_version: str
    solver_parameters: tuple[tuple[str, int], ...]
    named_core: tuple[ProjectionAtom, ...]
    named_core_sha256: str
    minimization_trace: tuple[CoreReductionStep, ...]
    promoted_indices: tuple[int, ...]
    bounded_extent: int
```

Require `SafeRegionPredicate.layer == 30` and
`SafeRegionPredicate.variables == P30_VARIABLES`; include both fields in its
canonical payload so compactness is measured on the same representation as
T31's 616-byte table. `SafeRegionCoverCertificate` has exact fields:

```text
schema, status, base, removed,
source_digests, t29_artifact_digests, t30_artifact_digests,
t32_source_digests, t32_commits, t32_design_sha256, t33_design_sha256,
t32_first_type_status, t32_first_type_sha256,
t32_first_type_inspected_witness_count, t32_first_type_tested_candidate_count,
t32_family_status, t32_family_inspected_witness_count,
t32_family_tested_candidate_count,
predicate, provenances, seed_pair_count, region_test_count,
cover_candidate_count, promoted_count, promoted_sha256,
promoted_coverage, first_match_ownership, clause_extents, predicate_extent,
predicate_bytes, promoted_table_bytes, clause_safety_statuses,
primary_safety_status,
independent_status, enumerated_input_count
```

Require schema `t33-base19-safe-region-cover-certificate-v1`, status
`SAFE_REGION_COVER_PASS`, base 19, all frozen bindings, 1..6 clauses, exactly
18 covered promoted indices, ownership counts at least two, extents at least
four, `predicate_bytes < promoted_table_bytes == 616`, both statuses PASS/UNSAT,
every clause safety status UNSAT, and `enumerated_input_count == 77_824`.

- [ ] **Step 4: Implement the canonical finite domain and seed-pair pool**

`bounded_layer30_rows()` iterates the 12 ordered carry variables over
`product((0,1), repeat=12)` and `D0` over `range(19)`, then returns rows in
`P30_VARIABLES` order. `generate_seed_pair_pool(first, second)` must:

1. enumerate support-one and support-two coefficient tuples from
   `{-3,-2,-1,1,2,3}`;
2. retain only primitive forms (`gcd(abs(coefficients)) == 1`);
3. add equality when the two form values agree, tight upper and lower bounds,
   and same-residue congruences for every modulus `2..19`;
4. let `ProjectionAtom` normalize each atom, then deduplicate by canonical
   bytes; and
5. remove atoms true on all 77,824 bounded rows and return canonical order.

Test all 153 canonical promoted pairs later against a second simple reference
generator. For a synthetic pair, assert each emitted atom holds on both seeds,
has permitted support/coefficient/modulus, is primitive after normalization,
and is not a domain tautology.

- [ ] **Step 5: Add strict certificate parsing and mutation tests**

Require exact key sets at every level. Add one mutation test each for an atom,
seed index/row, pool digest, core digest, reduction status, ownership count,
extent, predicate bytes, predecessor digest, T32 status, safety status, and
77,824 count. Round-trip must preserve exact canonical payload bytes.

- [ ] **Step 6: Run focused tests, lint, and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q
uv run --extra dev ruff check \
  .timeloop/lib/lychrel_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git add .timeloop/lib/lychrel_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git commit -m "feat: define base19 safe region cover certificates"
```

---

### Task 2: Frozen T29--T32 adapter and exact bad-input relation

**Files:**

- Create: `.timeloop/runs/t33_base19_safe_region_cover.py`
- Modify: `.timeloop/tests/test_lychrel_safe_region_cover.py`

**Interfaces:**

- Produce `T33Inputs`, `load_t33_inputs()`, `build_bad_input_solver()`,
  `z3_safe_atom()`, `z3_safe_clause()`, `replay_promoted_rows()`, and
  `replay_t32_boundary()`.
- Reuse `load_t32_inputs()`, `find_first_leak_type()`,
  `synthesize_leak_family()`, `build_layer30_relation()`, and T31's exact `Q0`
  expression structure without altering T29--T32 files.

- [ ] **Step 1: Write failing frozen-boundary tests**

```python
def test_t33_adapter_replays_the_committed_t32_stop() -> None:
    inputs = load_t33_inputs(ROOT)
    assert inputs.t32_first_type_status == "PASS"
    assert inputs.t32_first_type.to_payload() == {
        "literals": [
            {"phase": 0, "kind": "digit_order", "relation": "eq"},
            {"phase": 0, "kind": "digit_sum", "relation": "lt19"},
        ]
    }
    assert inputs.t32_first_type_tested_candidate_count == 31
    assert inputs.t32_first_type_inspected_witness_count == 3
    assert inputs.t32_family_status == "CANDIDATE_BUDGET_EXHAUSTED"
    assert inputs.t32_family_tested_candidate_count == 10_000
    assert inputs.t32_family_inspected_witness_count == 8
    assert inputs.promoted_rows == inputs.t32_inputs.t31_inputs.promoted_rows
    assert len(inputs.promoted_rows) == len(set(inputs.promoted_rows)) == 18


def test_bad_input_solver_accepts_no_promoted_row() -> None:
    inputs = load_t33_inputs(ROOT)
    for row in inputs.promoted_rows:
        assert exact_bad_input_status(inputs, row) == "UNSAT"
```

Cache the expensive immutable T32 replay per process, but provide an internal
uncached entry point so a mutation test cannot receive a stale result.

- [ ] **Step 2: Run the adapter tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py \
  -q -k 'adapter or bad_input_solver'
```

- [ ] **Step 3: Implement hash binding and exact T32 replay**

`T33Inputs` stores `t32_inputs`, the 18 promoted rows, all predecessor digest
maps, both T32 replay results, the four T32 source digests/commits, and the T33
design digest. `load_t33_inputs()` must bind raw bytes before imports are
trusted, then assert the exact first-type literals and the exact T32 counts and
STOP detail. It must also rerun all 18 T30 promoted-input implication checks.

Mutation tests append one byte separately to each copied T32 source and the T33
design, inject each path into the uncached loader, and require `EvidenceError`
with the changed component named.

- [ ] **Step 4: Implement `B30` and fresh clause safety expressions**

Build from `build_layer30_relation(inputs.t32_inputs.t31_inputs)`:

```python
def build_bad_input_solver(inputs: T33Inputs, clause: SafeRegionClause | None):
    solver = z3.Solver()
    solver.set(random_seed=0, phase_selection=0)
    solver.add(*relation.assertions)
    solver.add(z3.Not(q0_expression(inputs, relation)))
    if clause is not None:
        solver.add(z3_safe_clause(relation, clause))
    return relation, solver
```

Do not import T32's private `_q0_expression`; rebuild it from the five frozen
atoms. Reject `UNKNOWN`, canonicalize SAT witnesses, and replay all 12 equation
residuals plus the failed `Q0` equation before exposing them.

- [ ] **Step 5: Run focused tests, lint, and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q -k 'adapter or bad_input'
uv run --extra dev ruff check \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git add .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git commit -m "feat: bind base19 safe region boundary"
```

---

### Task 3: Isolated standard-library checker

**Files:**

- Create: `.timeloop/runs/t33_base19_safe_region_cover_independent.py`
- Modify: `.timeloop/tests/test_lychrel_safe_region_cover.py`

**Interfaces:**

- CLI subcommands `milestone` and `full` consume explicit raw paths and one
  candidate JSON path. Both write canonical JSON only to stdout and diagnostics
  only to stderr.
- Import no repository module, Z3, T27--T33 implementation, interpolation
  library, or third-party package.

- [ ] **Step 1: Write failing isolation, parser, and CSP tests**

Assert
`python -I .timeloop/runs/t33_base19_safe_region_cover_independent.py --help`
succeeds and AST import roots are limited to:

```python
{
    "__future__", "argparse", "dataclasses", "hashlib", "itertools",
    "json", "math", "re", "sys", "pathlib",
}
```

Add unit tests for canonical variable mapping, all three affine relations,
literal-target equations in both carry directions, exact five-equation `Q0`
failure, malformed candidate rejection, and a synthetic safe/unsafe clause.

- [ ] **Step 2: Run independent tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py \
  -q -k 'independent'
```

- [ ] **Step 3: Implement raw binding and the independent constraint engine**

Adapt the algorithm, not imports, from T32's checker. Parse exact key sets from
raw equations/frontier/T27--T30 files, validate all frozen SHA-256 values, and
rebuild the 12 transfer constraints. Use deterministic generalized arc
consistency plus smallest-domain/name-ordered backtracking.

`milestone` must independently:

- parse one seed-derived clause and its provenance;
- regenerate that seed pair's complete atom pool;
- verify the pool/core digests and every reduction-trace status by fresh CSP;
- verify both seeds and every claimed promoted row satisfy the clause;
- enumerate all 77,824 bounded inputs to recompute extent; and
- return PASS only when no `not Q0` transfer exists in the clause.

`full` additionally verifies all clauses and the DNF, all 18 promoted rows,
canonical first-match ownership, every extent, the 616-byte table measurement,
predicate compactness, and complete-predicate safety. Testing each disjunct for
a `not Q0` successor is an exact check of DNF safety.

- [ ] **Step 4: Test countermodels and source mutations**

Feed the checker a deliberately weak `D0 <= 18` clause and require a concrete
countermodel rejection. Mutate one equation coefficient, one frontier row, one
`Q0` constant, one core atom, one reduction status, and one claimed extent;
each must fail with a specific diagnostic.

- [ ] **Step 5: Run focused tests, lint, and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q -k 'independent'
uv run --extra dev ruff check \
  .timeloop/runs/t33_base19_safe_region_cover_independent.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git add .timeloop/runs/t33_base19_safe_region_cover_independent.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git commit -m "feat: independently check base19 safe regions"
```

---

### Task 4: First seed-pair safe-region milestone

**Files:**

- Modify: `.timeloop/runs/t33_base19_safe_region_cover.py`
- Modify: `.timeloop/tests/test_lychrel_safe_region_cover.py`

**Interfaces:**

- Produce `RegionSearchBudget`, `FirstSafeRegionResult`,
  `named_seed_pair_core()`, `deletion_minimize_core()`,
  `verify_region_candidate()`, and `find_first_safe_region()`.

- [ ] **Step 1: Write failing core and budget tests**

Use a small synthetic relation to prove that named assertions map one-to-one to
canonical atom bytes and deletion minimization is order-stable. Assert a
deleted atom stays deleted exactly when the reduced conjunction is UNSAT;
otherwise it is retained. Require `UNKNOWN` to raise `EvidenceError`.

Define the counters precisely:

- `seed_pair_count` increments when one of the 153 canonical pairs reaches its
  complete-pool `B30` query;
- `region_test_count` increments once for each distinct canonical conjunction
  submitted to an exact safety query, including the initial named core and each
  deletion trial; and
- duplicate conjunction bytes never consume the counter twice.

Test that pair 154 and distinct region 2,001 are never queried.

- [ ] **Step 2: Implement deterministic named-core extraction**

For each pair `(i,j)` in lexicographic index order:

1. generate and hash the canonical seed-pair pool;
2. assert `B30` plus every atom under name
   `f"a_{hashlib.sha256(canonical_bytes(atom)).hexdigest()}"`;
3. reject a SAT pool after replaying its exact countermodel;
4. on UNSAT, sort the returned named core by canonical atom bytes;
5. fresh-check the core, then deletion-minimize in that same order; and
6. reject it if the final core has more than six atoms or violates the grammar.

Record Z3's exact version, `random_seed=0`, `phase_selection=0`, named core
bytes, and every deletion step. These are provenance; later fresh checks remain
the proof gates.

- [ ] **Step 3: Implement the milestone acceptance gate**

`verify_region_candidate()` must require:

```text
atom_count <= 6
both seed rows satisfy clause
promoted_coverage_count >= 2
bounded_extent >= 4
single_clause_predicate_bytes < explicit_table_bytes(covered promoted rows)
fresh primary C(u) and B30(u) == UNSAT
isolated milestone status == PASS
```

Return one of `PASS`, `NO_SAFE_REGION`, `PAIR_BUDGET_EXHAUSTED`,
`REGION_BUDGET_EXHAUSTED`, `UNKNOWN`, or `INDEPENDENT_DISAGREEMENT`, with a
nonempty STOP detail and all exact counters. A PASS carries one clause and its
full provenance; a STOP carries neither.

- [ ] **Step 4: Run the repository milestone exactly once**

```bash
uv run --extra exact python \
  .timeloop/runs/t33_base19_safe_region_cover.py milestone
```

The CLI prints canonical JSON to stdout and writes no repository artifact.
Capture the result in a temporary file for test inspection.

If status is not `PASS`, verify the exact STOP is deterministic, run Task 4's
tests/lint, commit only source/tests, report `NO_SAFE_REGION` (or the stricter
exact STOP), and **end the experiment here**. Do not perform Tasks 5--8.

- [ ] **Step 5: If PASS, add exact repository assertions**

Freeze only mathematical facts returned by the committed algorithm: clause
payload, seed indices, atom count, promoted coverage, bounded extent, pool/core
digests, counters, primary `UNSAT`, and isolated `PASS`. Do not freeze timing or
filesystem paths.

- [ ] **Step 6: Run focused verification and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q -k 'core or budget or first_safe or milestone'
uv run --extra dev ruff check \
  .timeloop/lib/lychrel_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover_independent.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git add .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git commit -m "exp: find first base19 safe region"
```

---

### Task 5: Verified-region collection and bounded exact cover

**Prerequisite:** Task 4 status is exactly `PASS`.

**Files:**

- Modify: `.timeloop/runs/t33_base19_safe_region_cover.py`
- Modify: `.timeloop/tests/test_lychrel_safe_region_cover.py`

**Interfaces:**

- Produce `RegionCollectionResult`, `CoverSearchResult`,
  `collect_safe_regions()`, `candidate_family_objective()`, and
  `synthesize_safe_region_cover()`.

- [ ] **Step 1: Write failing region-dedup and ownership tests**

Test global deduplication by canonical clause bytes, preservation of the first
canonical provenance, exact inclusion of Task 4 counters in the 5,000-region
budget, and canonical region ordering by:

```python
(atom_count, total_support, coefficient_l1, canonical_bytes(clause))
```

For overlapping synthetic clauses, prove ownership is computed only after
canonical clause ordering and reject any clause owning fewer than two promoted
rows even when it covers more.

- [ ] **Step 2: Collect all verified regions within the inclusive budget**

Continue the Task 4 pair/core process from its saved in-memory trace. Every
retained region must independently satisfy all milestone gates. Never retain a
core merely because it came from Z3, and never spend a second region test on
duplicate bytes. Stop before distinct region test 5,001.

- [ ] **Step 3: Implement deterministic bounded set-cover search**

Represent each region's promoted coverage as an 18-bit integer. Use a
best-first heap of canonical clause-index tuples; canonicalize/deduplicate each
family before counting it. Order heap entries by:

```python
(
    clause_count,
    total_atoms,
    total_support,
    coefficient_l1,
    canonical_bytes(predicate),
)
```

Count every distinct popped family, including incomplete families rejected by
ownership or compactness. Expand only with higher canonical region indices,
prune above six clauses, and stop before family 10,001. The first complete
accepted family need not be claimed globally optimal; the ordering is only the
deterministic selection rule.

- [ ] **Step 4: Enforce the complete cover gate**

Require coverage mask `(1 << 18) - 1`, 1..6 clauses, ownership at least two per
clause, every extent at least four, `predicate_bytes < 616`, and a fresh primary
`P30 and B30` UNSAT query. Return exact STOP statuses for no cover, either
budget, clause limit, noncompactness, `UNKNOWN`, or primary disagreement.

- [ ] **Step 5: Run repository cover search**

```bash
uv run --extra exact python \
  .timeloop/runs/t33_base19_safe_region_cover.py search
```

The CLI still writes only stdout. If status is not `PASS`, verify determinism,
commit only source/tests, report the exact STOP, and end. Do not perform Tasks
6--8 or create durable artifacts.

- [ ] **Step 6: Run focused verification and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q -k 'region or cover or ownership'
uv run --extra dev ruff check \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git add .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git commit -m "exp: synthesize base19 safe region cover"
```

---

### Task 6: Fresh primary and independent full-domain gates

**Prerequisite:** Task 5 produced a complete candidate cover.

**Files:**

- Modify: `.timeloop/runs/t33_base19_safe_region_cover.py`
- Modify: `.timeloop/runs/t33_base19_safe_region_cover_independent.py`
- Modify: `.timeloop/tests/test_lychrel_safe_region_cover.py`

**Interfaces:**

- Produce `FullGateResult`, `run_fresh_primary_gate()`,
  `run_independent_full_gate()`, and `build_pass_certificate()`.

- [ ] **Step 1: Write failing fresh-gate agreement tests**

Require a newly loaded relation and new solver instance for each clause and the
complete predicate. Assert the fresh gate recomputes, rather than copies,
coverage, ownership, all extents, predicate extent, predicate/table bytes, and
safety. Mutate each primary count/status before the independent comparison and
require `INDEPENDENT_DISAGREEMENT`.

- [ ] **Step 2: Implement the fresh primary audit**

Enumerate the canonical 77,824 inputs once to recompute clause/predicate
extents, all promoted memberships, and ownership. Submit one new exact safety
query per clause and one for the DNF. Verify every UNSAT status and all
provenance bindings, then construct the typed certificate in memory.

- [ ] **Step 3: Implement and invoke the isolated full audit**

Serialize the provisional evidence/certificate to a fresh temporary directory.
The primary runner owns the dynamic temporary path and invokes the isolated
checker through an exact `subprocess.run` argument vector. Exercise that path
with:

```bash
uv run --extra exact python \
  .timeloop/runs/t33_base19_safe_region_cover.py audit-full
```

Parse stdout strictly. Require `repository_imports == []`, status
`SAFE_REGION_COVER_PASS`, 77,824 inputs, all 18 promoted rows, identical
coverage/ownership/extents/bytes, clause safety all UNSAT, and DNF safety
UNSAT.

- [ ] **Step 4: Add adversarial full-audit tests**

Reject a removed clause, reordered/noncanonical clause, weakened bound,
altered promoted row, altered ownership, false extent, 616-byte predicate,
source digest mutation, and a candidate with an independently found bad
successor.

- [ ] **Step 5: Execute the full gates twice in separate temporary directories**

Both runs must reproduce byte-identical primary evidence, certificate, and
independent audit. If either run stops or differs, commit tests/source only,
report the exact STOP, and end without Tasks 7--8.

- [ ] **Step 6: Run focused verification and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q -k 'fresh or full or mutation'
uv run --extra dev ruff check \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover_independent.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git add .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover_independent.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git commit -m "exp: verify base19 safe region cover"
```

---

### Task 7: Conditional durable artifacts and byte stability

**Prerequisite:** Both Task 6 temporary runs are byte-identical PASS results.

**Files:**

- Modify: `.timeloop/runs/t33_base19_safe_region_cover.py`
- Modify: `.timeloop/tests/test_lychrel_safe_region_cover.py`
- Create only on PASS: `.timeloop/runs/t33_base19_safe_region_cover.json`
- Create only on PASS:
  `.timeloop/runs/t33_base19_safe_region_cover_certificate.json`
- Create only on PASS:
  `.timeloop/runs/t33_base19_safe_region_cover_independent.json`
- Create only on PASS:
  `.timeloop/runs/t33_base19_safe_region_cover_report.md`

- [ ] **Step 1: Write failing artifact-policy and renderer tests**

Call `finalize` with synthetic STOP results for every STOP class and assert the
destination remains absent/empty. For PASS fixtures, require canonical JSON
with one trailing newline and a report containing the exact claim boundary,
all budgets/counts/digests, each clause, seed/core provenance, ownership,
extents, compactness, primary/independent methods, and explicit nonclaims.

- [ ] **Step 2: Implement transactional PASS-only finalization**

`finalize(output_dir)` reruns Task 6 twice in two fresh temporary directories,
compares all bytes, parses the certificate again, then writes the four files to
a temporary sibling directory and atomically renames each final file. Refuse a
nonempty destination containing any T33 artifact; never overwrite a mismatch.

- [ ] **Step 3: Generate and independently reread the durable artifacts**

```bash
uv run --extra exact python \
  .timeloop/runs/t33_base19_safe_region_cover.py finalize \
  --output-dir .timeloop/runs
uv run --extra exact python -I \
  .timeloop/runs/t33_base19_safe_region_cover_independent.py full \
  publication/base19-radial/instance/equations.json \
  publication/base19-radial/certificates/minimal-core-frontier.json \
  .timeloop/runs/t27_base19_invariant_lift.json \
  .timeloop/runs/t28_base19_tail_quotient.json \
  .timeloop/runs/t28_base19_tail_quotient_independent.json \
  .timeloop/runs/t29_base19_reachability_separator_trace.json \
  .timeloop/runs/t29_base19_reachability_separator_dataset.json \
  .timeloop/runs/t29_base19_reachability_separator.json \
  .timeloop/runs/t29_base19_reachability_separator_certificate.json \
  .timeloop/runs/t29_base19_reachability_separator_independent.json \
  .timeloop/runs/t30_base19_exact_image_refinement.json \
  .timeloop/runs/t30_base19_exact_image_refinement_certificate.json \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.json \
  .timeloop/runs/t33_base19_safe_region_cover_certificate.json
```

Compare the reread canonical output with the durable independent artifact.

- [ ] **Step 4: Run artifact tests and commit only T33 paths**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q -k 'artifact or report or deterministic'
git add .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover.json \
  .timeloop/runs/t33_base19_safe_region_cover_certificate.json \
  .timeloop/runs/t33_base19_safe_region_cover_independent.json \
  .timeloop/runs/t33_base19_safe_region_cover_report.md
git commit -m "exp: certify base19 safe region cover"
```

---

### Task 8: PASS-only regression and restart record

**Prerequisite:** Durable T33 artifacts exist and independently reread as PASS.

**Files:**

- Modify: `.timeloop/tests/test_lychrel_safe_region_cover.py`
- Modify: `.timeloop/notebook/lychrel-bases.md`

- [ ] **Step 1: Add final repository regression assertions**

Assert all four durable hashes, exact predicate bytes, clause count, atom count,
coverage vector, ownership vector, extent vector, search counters, source
bindings, primary UNSAT, independent PASS, and report status. Re-run finalization
into a temporary directory and compare every byte with the committed artifacts.

- [ ] **Step 2: Run focused and predecessor suites**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_reachability_separator.py -q
```

- [ ] **Step 3: Run the complete suite and static checks**

```bash
uv run --extra exact --extra dev pytest -q
uv run --extra dev ruff check .timeloop/lib .timeloop/runs .timeloop/tests
git diff --check
shasum -a 256 publication/base19-radial/preprint.zip
```

Require all tests pass, Ruff is clean, `git diff --check` is silent, and the
protected ZIP hash remains the required value.

- [ ] **Step 4: Append the T33 PASS conclusion to the notebook**

Record the exact claim boundary, predicate, coverage/ownership/extents,
budgets, hashes, independent method, and nonclaims. State that Prism failed and
contributed no artifact. Do not extrapolate below layer 30 or beyond the frozen
base-19 topology.

- [ ] **Step 5: Review scope and commit the PASS record**

```bash
git status --short
git diff --stat HEAD
git diff --check
git add .timeloop/tests/test_lychrel_safe_region_cover.py \
  .timeloop/notebook/lychrel-bases.md
git diff --cached --name-only
git commit -m "docs: record base19 safe region cover outcome"
```

The staged file list must contain only the two named T33 paths. Recompute and
report the four T33 artifact SHA-256 values, final test count, final commit, and
protected ZIP SHA-256.

## Plan Self-Review Gate

Before execution, verify this plan against the approved design:

- [ ] Every design obligation has a named primary test and independent check.
- [ ] The 153-pair, 2,000-region milestone and inclusive 5,000-region,
  10,000-family, six-clause limits have unambiguous counters.
- [ ] Every Task 4--6 failure path ends the experiment without fallback or
  durable artifacts.
- [ ] The independent checker has raw inputs only and enumerates exactly
  77,824 bounded layer-30 assignments.
- [ ] No step modifies T29--T32, publication paths, unrelated notebooks,
  `.DS_Store`, or existing timeloop ledger/pool/exam changes.
- [ ] Confirm no unresolved implementation marker stands in for a path, type,
  counter, status, or algorithm decision.
- [ ] Recheck type names, CLI subcommands, artifact names, hashes, and test
  paths for consistency before starting Task 1.
