# Base-19 Semantic-Leak Types Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Execute inline without subagents.

**Goal:** Decide whether at most eight compact structural carry/digit types
soundly and exhaustively cover every exact layer-30-to-31 transfer violating
T30's predicate `Q0`.

**Architecture:** A T32-local schema freezes an 84-literal structural feature
pool and strict type/family limits. A primary Z3 runner binds and replays the
T29--T31 boundary, then performs deterministic, budgeted witness-guided type
synthesis. An isolated standard-library checker first validates the one-type
milestone and, only after a complete primary family exists, independently
enumerates all 77,824 layer-30 inputs and proves soundness, exhaustiveness,
diversity, and compactness.

**Tech Stack:** Python 3.13 via `uv`, frozen dataclasses, canonical JSON,
`z3-solver` 5.x for primary exact queries, Python standard-library generalized
arc consistency/backtracking for independent assurance, pytest 8.x, Ruff, and
SHA-256.

## Global Constraints

- Work in `/Users/kairos/Projects/personal/math` inline without subagents.
- Preserve every existing user change. Never stage publication paths,
  `.timeloop/exam/results.jsonl`, `.timeloop/ledger.md`,
  `.timeloop/pool.jsonl`, unrelated notebooks, or `.DS_Store` files.
- Do not modify `publication/base19-radial/preprint/` or
  `publication/base19-radial/preprint.zip`. The ZIP SHA-256 must remain
  `e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33`.
- Bind source hashes: equations
  `ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040`,
  frontier `0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0`,
  provenances `cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302`,
  T27 evidence `32324c40903b78aec4d787b7e64a6d73d0999e3846d91ca1340c99f8ac2d8686`,
  T28 evidence `b0904f68fda4ad7990ac1d474ec157cf671567cdf02869d9ae2cceebe1814e47`,
  and T28 independent
  `7f095af25afc02ff48fe4d2ee53b4827ba99fa1548a5d970e475780fdaa1639e`.
- Bind raw T29 evidence, trace, dataset, certificate, and independent hashes:
  `c1e3dc4bc4ab07207a6ab49d6a9c9fd86486013abeaf016b6ecd59c9755e1d32`,
  `c56877975293c10575009a691b1d1bbde376838f805d232a2c18a4d00b2c4715`,
  `6603e381805db845ef9388d234e36f31eba510d838ac98c143c238c2ff144995`,
  `1c234891f001cb3a59e5670560ab26e3cb248a943e249aee049aac7d32c7db5a`,
  and `9f926208cc7416e24d811f6cd54485d19741b6f8ffe44f3b365b2f816e579644`.
- Bind raw T30 evidence, certificate, independent, and report hashes:
  `4b327e826a8b2462eedffa2cf572b77155fc95d8e7b94a4430d7f0331f75bd2a`,
  `3ac0b6ae254ad8bb7c7b19754335ea6a81bea77a0dc808e7eda1cd8994839892`,
  `56037d658f628ffa526f9adb710746231806450717f7bde5c0655f4ed6388639`,
  and `3ea55f8410887d3a522436be38bf3d9b5c010ac3c412d48405cd69f19828b95c`.
- Bind T31 commits `69022cb`, `adc6986`, `619b737`, and `6835036` and raw
  hashes: library
  `62e46be94c8ce27f538257fd8d1a61fb5e582fa23b80ccfbf9b8bdd6ac3375e1`,
  runner
  `da4ceebd20cf11e164a1e3228d96c53136fcbce8071055867a72d3869b60a732`,
  and test
  `3b88dadc423f41ec1ca81a2aea4df60071ad0d1a1165fc229c902012babc6b3e`.
- Bind the approved T32 design hash
  `93cecb3d3ce2c6a2610454f63302e26e2bbe57c7eba1825474bc808ad9ff76bd`.
- Require base 19, removed coordinate `phase=0,n=0,column=82`, the original
  12 layer-30-to-31 equations, and T30's immutable five equations `Q0`.
- Freeze the layer-30 input scope as
  `L0,R0,L1,R1,L2,R2,L3,R3,L4,R4,L5,R5,D0` and layer-31 output scope as
  `D0,D1,L0,L1,L2,L3,L4,L5,R0,R1,R2,R3,R4,R5`.
- Freeze the feature pool to the six schemas and six phases in the approved
  design: digit order (three relations), digit sum (three relations), and four
  carry comparisons (two relations each), exactly 84 canonical literals.
- Limit one type to six distinct literals and one family to eight types. Reject
  direct `Q0` tests, unary digit values, arbitrary affine or congruence atoms,
  nonlinear terms, auxiliary variables, row identities, hashes as selectors,
  and candidates permitting only one layer-30 input.
- The first milestone may inspect at most 128 canonical bad images and test at
  most 2,000 conjunctions. The complete search, including milestone work, may
  inspect at most 256 bad images and test at most 10,000 conjunctions.
- PASS requires each type to satisfy `T and type and Q0` UNSAT, the family to
  satisfy `T and not Q0 and not(any type)` UNSAT, two-input/two-mask diversity
  per type, strict compression against the exact bad-input table, and isolated
  agreement.
- Types may overlap; canonical first-match order owns counts. PASS is only an
  exhaustive structural mechanism cover, not a partition, weakest precondition,
  reachability invariant, layer-30 predicate `Q`, or reverse-and-add theorem.
- Fail closed on solver `UNKNOWN`, malformed syntax, source mutation, repeated
  or incomplete witnesses, nonzero replay residuals, budget exhaustion,
  nondeterministic bytes, or primary/independent disagreement.
- A Task 4 STOP forbids Tasks 5--8. A Task 5 STOP forbids Tasks 6--8. Do not
  create durable T32 evidence, certificate, audit, report, or notebook text on
  either STOP, and do not start a fallback experiment.
- Do not begin lower-layer extension, symbolic base lifting, base comparison,
  topology scans, publication changes, or Lean work.
- Prism remains hypothesis-only. Its model is `muse-glimmer:30b-mlx`; the
  mathematical service currently stops before model invocation with
  `MathFrameStoreOfflineMigrationRequired` for generation 2/schema cookie 150.
  Do not repair Prism or fabricate a frame artifact in this plan.

## File Map

- Create `.timeloop/lib/lychrel_semantic_leak_types.py` for T32 structural
  literals, types, families, diversity records, certificate schema, strict
  parsing, canonical ordering, and evaluation.
- Create `.timeloop/runs/t32_base19_semantic_leak_types.py` for frozen adapters,
  phase layout, exact witness replay, milestone and family synthesis, fresh
  primary gates, CLI finalization, and report rendering.
- Create `.timeloop/runs/t32_base19_semantic_leak_types_independent.py` for the
  isolated standard-library milestone and full-domain audits.
- Create `.timeloop/tests/test_lychrel_semantic_leak_types.py` for grammar,
  binding, witness replay, synthesis, STOP gates, isolation, mutation,
  determinism, and durable-artifact tests.
- Create only after all primary and independent gates agree:
  `.timeloop/runs/t32_base19_semantic_leak_types.json`,
  `.timeloop/runs/t32_base19_semantic_leak_types_certificate.json`,
  `.timeloop/runs/t32_base19_semantic_leak_types_independent.json`, and
  `.timeloop/runs/t32_base19_semantic_leak_types_report.md`.
- Modify `.timeloop/notebook/lychrel-bases.md` and this plan only after durable
  PASS artifacts reproduce. No repository document records an early STOP.

---

### Task 1: T32 structural type and certificate language

**Files:**

- Create: `.timeloop/lib/lychrel_semantic_leak_types.py`
- Create: `.timeloop/tests/test_lychrel_semantic_leak_types.py`

**Interfaces:**

- Consumes `canonical_bytes` and `SemanticWitness` from existing libraries.
- Produces `StructuralLiteral`, `LeakType`, `LeakTypeFamily`,
  `TypeDiversityRecord`, `SemanticLeakTypesCertificate`,
  `generate_literal_pool()`, `evaluate_literal()`, `evaluate_leak_type()`,
  `evaluate_leak_family()`, `type_objective()`, and
  `parse_semantic_leak_types_certificate(payload)`.

- [ ] **Step 1: Write failing grammar, ordering, and parser tests**

Create the test module with the `ROOT` and `sys.path` setup used by the T31
tests. Add these exact boundary tests:

```python
def test_literal_pool_is_the_frozen_84_literal_language() -> None:
    pool = generate_literal_pool()
    assert len(pool) == len(set(pool)) == 84
    assert pool == tuple(sorted(pool, key=canonical_bytes))
    assert {literal.phase for literal in pool} == set(range(6))
    assert {literal.kind for literal in pool} == {
        "digit_order", "digit_sum", "input_carry_pair",
        "output_carry_pair", "left_carry_flow", "right_carry_flow",
    }


def test_type_and_family_limits_are_strict() -> None:
    pool = generate_literal_pool()
    with pytest.raises(ValueError, match="six literals"):
        LeakType(pool[:7])
    one = LeakType((pool[0],))
    with pytest.raises(ValueError, match="eight types"):
        LeakTypeFamily(tuple(one for _ in range(9)))


def test_no_generic_atom_can_enter_the_structural_schema() -> None:
    with pytest.raises(ValueError, match="kind"):
        StructuralLiteral(0, "q0_failure", "eq")
    with pytest.raises(ValueError, match="relation"):
        StructuralLiteral(0, "digit_order", "value_0")
```

Add fixtures for all certificate fields. Require exact key sets, strict
integer-versus-Boolean checks, sorted/distinct literals, family canonical
order, exactly two diversity witnesses and two distinct five-bit masks per
type, `UNSAT` soundness/exhaustiveness statuses, `77_824` enumerated inputs,
positive byte counts, and `family_bytes < bad_input_table_bytes`. Mutation
tests must reject one altered literal, type order, witness, failure mask,
digest, status, count, and byte measurement.

- [ ] **Step 2: Run Task 1 tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q
```

Expected: import failure for `lychrel_semantic_leak_types`.

- [ ] **Step 3: Implement the immutable schema and evaluators**

Use these public shapes:

```python
@dataclass(frozen=True)
class StructuralLiteral:
    phase: int
    kind: str
    relation: str


@dataclass(frozen=True)
class LeakType:
    literals: tuple[StructuralLiteral, ...]


@dataclass(frozen=True)
class LeakTypeFamily:
    types: tuple[LeakType, ...]


@dataclass(frozen=True)
class TypeDiversityRecord:
    type_index: int
    witnesses: tuple[SemanticWitness, SemanticWitness]
    failure_masks: tuple[tuple[bool, bool, bool, bool, bool], ...]
```

`StructuralLiteral` permits exactly:

```python
RELATIONS = {
    "digit_order": ("eq", "lt", "gt"),
    "digit_sum": ("lt19", "eq18", "ge19"),
    "input_carry_pair": ("eq", "ne"),
    "output_carry_pair": ("eq", "ne"),
    "left_carry_flow": ("eq", "ne"),
    "right_carry_flow": ("eq", "ne"),
}
```

Generate every phase/kind/relation triple, sort by `canonical_bytes`, and
require all type literals to be distinct and in that order. Define
`type_objective(tau)` as
`(literal_count, distinct_phase_count, variable_support, canonical_bytes)`;
family order is ascending by that objective. Evaluation accepts only a mapping
whose keys equal this generated tuple and whose values satisfy exact domains:

```python
STRUCTURAL_KEYS = tuple(
    name
    for phase in range(6)
    for name in (
        f"a{phase}", f"b{phase}", f"Lin{phase}", f"Rin{phase}",
        f"Lout{phase}", f"Rout{phase}",
    )
)
```

Define `SemanticLeakTypesCertificate` with exact fields:

```python
schema, status, base, removed,
source_digests, t29_artifact_digests, t30_artifact_digests,
t31_source_digests, t31_commits, design_sha256,
family, milestone_witnesses, type_soundness,
exhaustiveness_status, diversity,
discovery_witness_count, tested_candidate_count,
enumerated_input_count, bad_input_count,
family_bytes, bad_input_table_bytes
```

Require schema `t32-base19-semantic-leak-types-certificate-v1`, status
`SEMANTIC_LEAK_TYPES_PASS`, base 19, the frozen removed coordinate, one to
eight types, `type_soundness == ("UNSAT",) * len(types)`, and every PASS gate.
Serialize mappings as sorted JSON objects and tuples as arrays.

- [ ] **Step 4: Run Task 1 GREEN and lint**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_semantic_leak_types.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git diff --check
```

Expected: all Task 1 tests pass and Ruff reports no errors.

- [ ] **Step 5: Commit Task 1**

```bash
git add .timeloop/lib/lychrel_semantic_leak_types.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git diff --cached --name-only
git commit -m "feat: define base19 semantic leak types"
```

Expected staged paths: exactly the two Task 1 files.

### Task 2: Frozen T29--T31 adapter and structural witness view

**Files:**

- Create: `.timeloop/runs/t32_base19_semantic_leak_types.py`
- Modify: `.timeloop/tests/test_lychrel_semantic_leak_types.py`

**Interfaces:**

- Consumes `load_t31_inputs`, `project_bad_image_atoms`, `synthesize_p30`,
  `build_layer30_relation`, and `replay_bad_image_witness` without modifying
  T31.
- Produces `PhaseLayout`, `T32Inputs`, `load_t32_inputs(root,
  **path_overrides)`, `reconstruct_witness_assignment(inputs, witness)`,
  `structural_view(inputs, witness)`, `q0_residuals(inputs, witness)`, and
  `failure_mask(inputs, witness)`.

- [ ] **Step 1: Write failing frozen-boundary tests**

```python
def test_t32_adapter_replays_the_complete_t31_stop_boundary() -> None:
    inputs = load_t32_inputs(ROOT)
    assert inputs.t31_status == "NO_CANDIDATE"
    assert inputs.t31_projected_atom_count == 26
    assert inputs.t31_stop_detail == (
        "no projected atom excludes the first exact bad image"
    )
    assert inputs.t31_replay_residuals == (0,) * 12
    assert inputs.t31_q0_holds is False
    assert failure_mask(inputs, inputs.t31_witness) == (
        True, True, False, True, True
    )


def test_canonical_t31_witness_has_the_expected_structural_digits() -> None:
    inputs = load_t32_inputs(ROOT)
    view = structural_view(inputs, inputs.t31_witness)
    assert tuple(view[f"a{i}"] for i in range(6)) == (0, 1, 1, 2, 4, 9)
    assert tuple(view[f"b{i}"] for i in range(6)) == (0, 1, 1, 2, 4, 9)
    assert tuple(view[f"Lin{i}"] for i in range(6)) == (0, 0, 0, 0, 1, 0)
    assert tuple(view[f"Rin{i}"] for i in range(6)) == (0, 0, 0, 0, 0, 1)
    assert tuple(view[f"Lout{i}"] for i in range(6)) == (0, 0, 0, 0, 0, 0)
    assert tuple(view[f"Rout{i}"] for i in range(6)) == (0, 0, 0, 0, 1, 1)
```

Parameterize raw-byte mutations over every T29/T30 artifact, all three bound
T31 files, and the approved design. Also mutate base, removed coordinate,
equation count, T31 status/detail, witness coordinate, and expected file hash.
Require `EvidenceError` before feature construction.

- [ ] **Step 2: Run adapter tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q -k adapter
```

Expected: import failure for `t32_base19_semantic_leak_types`.

- [ ] **Step 3: Implement strict loading and the six-phase layout**

Use:

```python
@dataclass(frozen=True)
class PhaseLayout:
    phase: int
    a_original: str
    b_original: str
    lin_original: str
    rin_original: str
    lout_original: str
    rout_original: str


@dataclass(frozen=True)
class T32Inputs:
    t31_inputs: T31Inputs
    q0: LayerPredicate
    phases: tuple[PhaseLayout, ...]
    t31_witness: SemanticWitness
    t31_status: str
    t31_projected_atom_count: int
    t31_stop_detail: str
    t31_replay_residuals: tuple[int, ...]
    t31_q0_holds: bool
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    t30_artifact_digests: tuple[tuple[str, str], ...]
    t31_source_digests: tuple[tuple[str, str], ...]
    t31_commits: tuple[str, ...]
    design_sha256: str
```

`load_t32_inputs` raw-binds every file before mathematics. Rerun T31 from the
frozen source: require 26 records, `NO_CANDIDATE`, `p30 is None`, exactly one
counterexample, the exact stop detail, 616 state-table bytes, all 12 residuals
zero, and `Q0 = false`. Accept keyword-only path overrides for every bound file
so mutations never touch repository evidence.

Build the phase layout directly from the paired equation provenances. Require
the left/right summands to be the same unordered pair, exact adjacent target
chain, canonical carries, and phase-5 literal target 18. Do not identify phase
variables by hard-coded witness values. `reconstruct_witness_assignment`
requires an exact, duplicate-free assignment of all 37 relation variables and
replays domains and residuals. `q0_residuals` returns the five signed affine
residuals; `failure_mask` is their nonzero mask.

- [ ] **Step 4: Run Task 2 GREEN and audit frozen hashes**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_semantic_leak_types.py \
  .timeloop/runs/t32_base19_semantic_leak_types.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
shasum -a 256 publication/base19-radial/preprint.zip \
  .timeloop/runs/t29_base19_reachability_separator.json \
  .timeloop/runs/t29_base19_reachability_separator_trace.json \
  .timeloop/runs/t29_base19_reachability_separator_dataset.json \
  .timeloop/runs/t29_base19_reachability_separator_certificate.json \
  .timeloop/runs/t29_base19_reachability_separator_independent.json \
  .timeloop/runs/t30_base19_exact_image_refinement.json \
  .timeloop/runs/t30_base19_exact_image_refinement_certificate.json \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.json \
  .timeloop/runs/t30_base19_exact_image_refinement_report.md
git diff --check
```

Expected: tests/lint pass and every digest equals Global Constraints.

- [ ] **Step 5: Commit Task 2**

```bash
git add .timeloop/runs/t32_base19_semantic_leak_types.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git diff --cached --name-only
git commit -m "feat: bind base19 semantic leak boundary"
```

### Task 3: Isolated exact checker for the first-type milestone

**Files:**

- Create: `.timeloop/runs/t32_base19_semantic_leak_types_independent.py`
- Modify: `.timeloop/tests/test_lychrel_semantic_leak_types.py`

**Interfaces:**

- Consumes only raw JSON paths and one temporary milestone JSON file.
- Produces an isolated CLI mode `milestone` and schema
  `t32-base19-semantic-leak-types-independent-milestone-v1`.

- [ ] **Step 1: Write failing isolation and synthetic-CSP tests**

```python
def test_independent_checker_starts_under_isolated_python() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", str(INDEPENDENT), "--help"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0
    assert "milestone" in completed.stdout
    assert "full" in completed.stdout


def test_independent_milestone_rejects_a_q0_countermodel(
    tmp_path: Path,
) -> None:
    candidate = write_synthetic_milestone(
        tmp_path, sound_type=False,
    )
    completed = run_independent_milestone(candidate)
    assert completed.returncode != 0
    assert "type soundness counterexample" in completed.stderr
```

Add small synthetic equation fixtures proving propagation handles digit
domains `0..18`, carry domains `{0,1}`, literal target 18, both directions of
each equation, canonical lexicographic search, all six literal kinds, and the
five-equation failure mask. Use an AST/import scan plus `python -I` to require
standard-library imports only and zero repository imports.

- [ ] **Step 2: Run isolated tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q -k independent
```

Expected: the independent script is absent.

- [ ] **Step 3: Implement raw parsing and deterministic constraint search**

The script must duplicate no imports from repository code. Implement strict
canonical JSON parsing, SHA-256 binding, equation parsing, `Q0` parsing,
structural literal/type parsing, and `SemanticWitness` parsing locally.

Represent each local equation as a finite constraint over at most five
variables. Repeatedly remove domain values without supporting tuples until a
fixed point; branch on the smallest remaining domain, breaking ties by original
variable name and values ascending. For milestone soundness, search exactly:

```text
T(u,x,z) and tau_0(u,x,z) and Q0(x)
```

Return `UNSAT` only after the finite search exhausts. Replay both diversity
witnesses independently, require twelve zero residuals, distinct input tuples,
distinct five-bit masks, and type satisfaction. Output exactly:

```python
{
    "schema": "t32-base19-semantic-leak-types-independent-milestone-v1",
    "status": "PASS",
    "repository_imports": [],
    "soundness_status": "UNSAT",
    "witness_residuals": [[0] * 12 for _ in witnesses],
    "failure_masks": [list(mask) for mask in failure_masks],
    "source_digests": dict(source_digests),
    "t29_artifact_digests": dict(t29_artifact_digests),
    "t30_artifact_digests": dict(t30_artifact_digests),
    "t31_source_digests": dict(t31_source_digests),
}
```

Every malformed input or SAT counterexample exits nonzero; no STOP result is
promoted to PASS.

- [ ] **Step 4: Run Task 3 GREEN, lint, and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/runs/t32_base19_semantic_leak_types_independent.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git diff --check
git add .timeloop/runs/t32_base19_semantic_leak_types_independent.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git commit -m "feat: independently replay base19 leak types"
```

### Task 4: First structural type milestone — critical STOP gate

**Files:**

- Modify: `.timeloop/runs/t32_base19_semantic_leak_types.py`
- Modify: `.timeloop/tests/test_lychrel_semantic_leak_types.py`

**Interfaces:**

- Consumes `T32Inputs`, the 84-literal pool, and the isolated milestone CLI.
- Produces `FirstTypeMilestoneResult` and
  `find_first_leak_type(inputs, witness_limit=128, candidate_limit=2000)`.

- [ ] **Step 1: Write failing deterministic milestone tests**

```python
def test_repository_first_type_reaches_pass_or_exact_stop(tmp_path: Path) -> None:
    result = find_first_leak_type(load_t32_inputs(ROOT))
    assert result.status in {
        "PASS", "NO_SOUND_TYPE", "NO_DIVERSE_TYPE",
        "WITNESS_BUDGET_EXHAUSTED", "CANDIDATE_BUDGET_EXHAUSTED",
        "INDEPENDENT_DISAGREEMENT",
    }
    assert 1 <= result.inspected_witness_count <= 128
    assert 0 <= result.tested_candidate_count <= 2_000
    if result.status == "PASS":
        assert result.leak_type is not None
        assert len(result.leak_type.literals) <= 6
        assert len(result.witnesses) == 2
        assert result.failure_masks[0] != result.failure_masks[1]
        assert result.soundness_status == "UNSAT"
        assert run_independent_milestone_payload(tmp_path, result)["status"] == "PASS"
    else:
        assert result.leak_type is None
        assert result.stop_detail


def test_first_type_search_is_byte_deterministic() -> None:
    inputs = load_t32_inputs(ROOT)
    assert canonical_bytes(find_first_leak_type(inputs).to_payload()) == (
        canonical_bytes(find_first_leak_type(inputs).to_payload())
    )
```

Add synthetic tests that choose the minimum objective conjunction, reject a
candidate with a `Q0` countermodel, reject a one-input minterm, require a
different failure mask, stop exactly at witness 128/candidate 2,000, replay
every solver model, and convert solver `UNKNOWN` to a STOP status.

- [ ] **Step 2: Run milestone tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q -k first_type
```

Expected: import failure for `find_first_leak_type`.

- [ ] **Step 3: Implement bounded pair-generalization search**

Use:

```python
@dataclass(frozen=True)
class FirstTypeMilestoneResult:
    status: str
    leak_type: LeakType | None
    witnesses: tuple[SemanticWitness, ...]
    failure_masks: tuple[tuple[bool, ...], ...]
    inspected_witness_count: int
    tested_candidate_count: int
    soundness_status: str | None
    independent_status: str | None
    stop_detail: str | None
```

Seed witness one with the exact T31 witness. Enumerate canonical exact bad
images with a different input and failure mask. For each pair, intersect the
structural literals they satisfy, enumerate conjunctions of sizes one through
six in `type_objective` order, and globally deduplicate candidate bytes.

For every candidate, first require a second input model of `T and type`; then
ask a fresh solver for `T and type and Q0`. SAT rejects the candidate after
canonical complete-witness replay. UNSAT makes it a primary candidate. Select
the first minimum-objective primary candidate, serialize it with its two bad
witnesses to a temporary milestone file, invoke the independent CLI, and
return PASS only on independent agreement. All inspected bad images and tested
conjunctions count against the exact budgets, including the seed.

- [ ] **Step 4: Run the repository milestone and obey its gate**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q \
  -k 'repository_first_type or first_type_search_is_byte_deterministic'
```

PASS path: one type has two distinct inputs/masks, primary exact soundness is
UNSAT, and the isolated checker agrees. STOP path: report the exact status and
detail, run Step 5, commit the code, and end T32. Do **not** run Tasks 5--8,
write durable result files, update the notebook, widen the grammar, or try a
different experiment.

- [ ] **Step 5: Run Task 4 GREEN, audit, and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_semantic_leak_types.py \
  .timeloop/runs/t32_base19_semantic_leak_types.py \
  .timeloop/runs/t32_base19_semantic_leak_types_independent.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git diff --check
shasum -a 256 publication/base19-radial/preprint.zip
git add .timeloop/runs/t32_base19_semantic_leak_types.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git commit -m "exp: find first base19 semantic leak type"
```

### Task 5: Complete bounded structural mechanism family — second STOP gate

**Precondition:** Task 4 returned PASS. Otherwise this task is forbidden.

**Files:**

- Modify: `.timeloop/runs/t32_base19_semantic_leak_types.py`
- Modify: `.timeloop/tests/test_lychrel_semantic_leak_types.py`

**Interfaces:**

- Consumes the successful `FirstTypeMilestoneResult`.
- Produces `FamilySearchResult` and
  `synthesize_leak_family(inputs, milestone, witness_limit=256,
  candidate_limit=10000, type_limit=8)`.

- [ ] **Step 1: Write failing family CEGIS tests**

```python
def test_repository_family_reaches_pass_or_exact_stop() -> None:
    inputs = load_t32_inputs(ROOT)
    milestone = find_first_leak_type(inputs)
    assert milestone.status == "PASS"
    result = synthesize_leak_family(inputs, milestone)
    assert result.status in {
        "PASS", "NO_SOUND_TYPE", "NO_DIVERSE_TYPE", "TYPE_LIMIT_EXCEEDED",
        "WITNESS_BUDGET_EXHAUSTED", "CANDIDATE_BUDGET_EXHAUSTED", "UNKNOWN",
    }
    assert result.inspected_witness_count <= 256
    assert result.tested_candidate_count <= 10_000
    if result.status == "PASS":
        assert 1 <= len(result.family.types) <= 8
        assert result.exhaustiveness_status == "UNSAT"
        assert result.type_soundness == ("UNSAT",) * len(result.family.types)
        assert len(result.diversity) == len(result.family.types)
    else:
        assert result.stop_detail
```

Add synthetic tests for canonical uncovered-witness selection, first-match
ownership, overlapping types, global milestone-inclusive budgets, the ninth
type STOP, repeated witnesses, missing diversity, SAT soundness, UNSAT
exhaustiveness, and deterministic payload bytes.

- [ ] **Step 2: Run family tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q -k family
```

Expected: import failure for `synthesize_leak_family`.

- [ ] **Step 3: Implement the exact family CEGIS loop**

Use:

```python
@dataclass(frozen=True)
class FamilySearchResult:
    status: str
    family: LeakTypeFamily | None
    diversity: tuple[TypeDiversityRecord, ...]
    uncovered_witnesses: tuple[SemanticWitness, ...]
    type_soundness: tuple[str, ...]
    exhaustiveness_status: str | None
    inspected_witness_count: int
    tested_candidate_count: int
    stop_detail: str | None
```

Start with `tau_0` and its counters. Query the lexicographically least complete
model of `T and not Q0 and not(any current type)`. If UNSAT, return PASS. On
SAT, replay the witness and find a second bad witness with a different input
and mask that shares a structural candidate. Reuse the Task 4 pair
generalizer, counting only globally new witnesses/candidates. Accept only an
exactly sound, diverse, non-minterm type. Re-sort the family by
`type_objective` after insertion and recompute canonical first-match ownership.

Stop before adding type nine, witness 257, or candidate 10,001. Do not delete
or weaken earlier types to evade a budget. Every solver call is fresh;
`UNKNOWN`, repeated uncovered models, incomplete assignments, nonzero
residuals, or inconsistent masks returns the exact STOP status.

- [ ] **Step 4: Run the repository family gate**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q \
  -k 'repository_family or family_search_is_byte_deterministic'
```

PASS path: at most eight sound/diverse types make the exact uncovered query
UNSAT. STOP path: run Step 5, commit the bounded result implementation, and end
T32 without Tasks 6--8, durable artifacts, notebook changes, or fallback.

- [ ] **Step 5: Run Task 5 GREEN, lint, and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_semantic_leak_types.py \
  .timeloop/runs/t32_base19_semantic_leak_types.py \
  .timeloop/runs/t32_base19_semantic_leak_types_independent.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git diff --check
git add .timeloop/runs/t32_base19_semantic_leak_types.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git commit -m "exp: synthesize base19 semantic leak family"
```

### Task 6: Fresh primary gates and isolated full-domain assurance

**Precondition:** Task 5 returned PASS. Otherwise this task is forbidden.

**Files:**

- Modify: `.timeloop/runs/t32_base19_semantic_leak_types.py`
- Modify: `.timeloop/runs/t32_base19_semantic_leak_types_independent.py`
- Modify: `.timeloop/tests/test_lychrel_semantic_leak_types.py`

**Interfaces:**

- Consumes only the serialized family and diversity witnesses from Task 5;
  reruns every proof from fresh loaders.
- Produces `PrimaryGateResult`, `check_type_soundness`,
  `check_family_exhaustiveness`, `enumerate_bad_inputs`,
  `check_family_compactness`, `build_t32_certificate`, and independent CLI mode
  `full` with schema `t32-base19-semantic-leak-types-independent-v1`.

- [ ] **Step 1: Write failing fresh-gate and full-audit tests**

```python
def test_fresh_primary_gate_accepts_the_repository_family() -> None:
    family_result = repository_family_result()
    gate = run_fresh_primary_gate(load_t32_inputs(ROOT), family_result)
    assert gate.status == "PASS"
    assert gate.type_soundness == ("UNSAT",) * len(family_result.family.types)
    assert gate.exhaustiveness_status == "UNSAT"
    assert gate.enumerated_input_count == 77_824
    assert gate.bad_input_count > 0
    assert gate.family_bytes < gate.bad_input_table_bytes


def test_independent_full_checker_agrees(tmp_path: Path) -> None:
    certificate = write_temporary_primary_certificate(tmp_path)
    completed, audit = run_independent_full(certificate)
    assert completed.returncode == 0
    assert audit["status"] == "SEMANTIC_LEAK_TYPES_PASS"
    assert audit["repository_imports"] == []
    assert audit["enumerated_input_count"] == 77_824
    assert audit["type_soundness"] == ["UNSAT"] * len(audit["type_counts"])
    assert audit["exhaustiveness_status"] == "UNSAT"
```

Parameterize mutations of a literal, type order, witness coordinate, equation
residual, failure mask, source/T29/T30/T31 digest, soundness/exhaustiveness
status, diversity count, input/bad count, family bytes, and table bytes. Every
mutation must fail both the relevant fresh primary parser and independent CLI.

- [ ] **Step 2: Run full-gate tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q \
  -k 'fresh_primary or independent_full'
```

Expected: missing fresh-gate and `full` interfaces.

- [ ] **Step 3: Implement fresh primary enumeration and certificate build**

Reparse the serialized family; do not reuse live solver objects or cached
statuses from discovery. Prove each `T and type and Q0` UNSAT and the complete
uncovered query UNSAT. Re-find two canonical diversity witnesses per type.

Enumerate the input product in exact order:

```python
domains = [range(2)] * 12 + [range(19)]
for values in itertools.product(*domains):
    input_state = dict(zip(P30_VARIABLES, values, strict=True))
```

For each input, decide `exists x,z . T and not Q0` with a fresh push/pop scope.
Build only this temporary canonical bad-input table:

```python
bad_input_table = {
    "variables": list(P30_VARIABLES),
    "states": [list(row) for row in bad_input_rows],
}
```

Record its count and byte length, then discard its rows after certificate
construction. Compute family bytes from
`canonical_bytes(family.to_payload())` and require strict inequality.

- [ ] **Step 4: Extend the isolated checker to complete assurance**

In `full` mode, raw-bind every source and artifact independently, parse the
certificate with local code, and enumerate the same 77,824 inputs. Use the
Task 3 constraint engine to:

- find no `Q0` transfer inside any type;
- find no `not Q0` transfer outside the family;
- determine exact bad-input membership and table bytes;
- replay two distinct inputs/masks per type; and
- count first-match ownership in canonical family order.

Emit source bindings, certificate raw hash, input/bad counts, type counts,
soundness/exhaustiveness statuses, diversity digests, and byte counts. Never
emit the full bad-input table. Require byte-identical output from two fresh
processes.

- [ ] **Step 5: Run the independent gate and obey disagreement STOP**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q \
  -k 'fresh_primary or independent_full or mutation'
```

Expected: PASS and exact primary/independent agreement. Any disagreement,
non-compression, SAT proof obligation, or `UNKNOWN` ends T32 without durable
artifacts, notebook changes, or fallback.

- [ ] **Step 6: Run Task 6 GREEN, lint, and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_semantic_leak_types.py \
  .timeloop/runs/t32_base19_semantic_leak_types.py \
  .timeloop/runs/t32_base19_semantic_leak_types_independent.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git diff --check
git add .timeloop/runs/t32_base19_semantic_leak_types.py \
  .timeloop/runs/t32_base19_semantic_leak_types_independent.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git commit -m "exp: audit base19 semantic leak family"
```

### Task 7: Byte-stable durable T32 artifacts

**Precondition:** Task 6 primary and independent gates agree. Otherwise this
task is forbidden.

**Files:**

- Modify: `.timeloop/runs/t32_base19_semantic_leak_types.py`
- Modify: `.timeloop/tests/test_lychrel_semantic_leak_types.py`
- Create: `.timeloop/runs/t32_base19_semantic_leak_types.json`
- Create: `.timeloop/runs/t32_base19_semantic_leak_types_certificate.json`
- Create: `.timeloop/runs/t32_base19_semantic_leak_types_independent.json`
- Create: `.timeloop/runs/t32_base19_semantic_leak_types_report.md`

**Interfaces:**

- Primary CLI `certify` writes the certificate only; independent CLI `full`
  binds it and writes the audit; primary CLI `finalize` verifies both and
  writes evidence/report. This avoids circular hashes.
- Produces four canonical, mutually bound, reproducible artifacts.

- [ ] **Step 1: Write failing CLI, determinism, and durable-binding tests**

```python
def test_complete_temporary_pipeline_is_byte_deterministic(tmp_path: Path) -> None:
    first = run_complete_t32_pipeline(tmp_path / "first")
    second = run_complete_t32_pipeline(tmp_path / "second")
    assert [path.read_bytes() for path in first] == [path.read_bytes() for path in second]


def test_durable_t32_artifacts_bind_each_other() -> None:
    certificate = parse_semantic_leak_types_certificate(
        json.loads(T32_CERTIFICATE.read_bytes())
    )
    audit = json.loads(T32_INDEPENDENT.read_bytes())
    evidence = json.loads(T32_EVIDENCE.read_bytes())
    assert certificate.status == audit["status"] == evidence["status"]
    assert raw_sha256(T32_CERTIFICATE) == audit["certificate_file_sha256"]
    assert raw_sha256(T32_INDEPENDENT) == evidence["independent_file_sha256"]
```

Require canonical JSON plus one newline, report one final newline and no
trailing whitespace, evidence bindings to raw certificate/audit hashes, and
fresh reproduction of every byte.

- [ ] **Step 2: Implement certificate/finalization CLIs and report rendering**

`certify` performs the complete fresh primary gate and writes only a canonical
certificate. `full` performs the isolated audit and binds the raw certificate.
`finalize` reparses both, requires exact agreement, and writes evidence schema
`t32-base19-semantic-leak-types-evidence-v1` plus a concise report. No command
writes a STOP artifact.

- [ ] **Step 3: Generate two temporary pipelines and compare**

```bash
T32_TMP_A="$(mktemp -d)"
T32_TMP_B="$(mktemp -d)"
uv run --extra exact python .timeloop/runs/t32_base19_semantic_leak_types.py \
  certify --certificate "$T32_TMP_A/certificate.json"
uv run --extra exact python \
  .timeloop/runs/t32_base19_semantic_leak_types_independent.py full \
  --root . --certificate "$T32_TMP_A/certificate.json" \
  --output "$T32_TMP_A/independent.json"
uv run --extra exact python .timeloop/runs/t32_base19_semantic_leak_types.py \
  finalize --certificate "$T32_TMP_A/certificate.json" \
  --independent "$T32_TMP_A/independent.json" \
  --evidence "$T32_TMP_A/evidence.json" --report "$T32_TMP_A/report.md"
uv run --extra exact python .timeloop/runs/t32_base19_semantic_leak_types.py \
  certify --certificate "$T32_TMP_B/certificate.json"
uv run --extra exact python \
  .timeloop/runs/t32_base19_semantic_leak_types_independent.py full \
  --root . --certificate "$T32_TMP_B/certificate.json" \
  --output "$T32_TMP_B/independent.json"
uv run --extra exact python .timeloop/runs/t32_base19_semantic_leak_types.py \
  finalize --certificate "$T32_TMP_B/certificate.json" \
  --independent "$T32_TMP_B/independent.json" \
  --evidence "$T32_TMP_B/evidence.json" --report "$T32_TMP_B/report.md"
diff -rq "$T32_TMP_A" "$T32_TMP_B"
```

Expected: all commands exit zero and `diff` reports no differences.

- [ ] **Step 4: Generate durable paths and compare with verified bytes**

Run the same three commands with the four durable paths, then compare each
durable file with its corresponding `T32_TMP_A` file using `cmp`. This uses the
verified generators rather than a shell copy. Any difference aborts before
staging.

- [ ] **Step 5: Audit exact scope and commit artifacts**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q
shasum -a 256 publication/base19-radial/preprint.zip \
  .timeloop/runs/t32_base19_semantic_leak_types.json \
  .timeloop/runs/t32_base19_semantic_leak_types_certificate.json \
  .timeloop/runs/t32_base19_semantic_leak_types_independent.json \
  .timeloop/runs/t32_base19_semantic_leak_types_report.md
git diff --check
git add .timeloop/runs/t32_base19_semantic_leak_types.py \
  .timeloop/runs/t32_base19_semantic_leak_types.json \
  .timeloop/runs/t32_base19_semantic_leak_types_certificate.json \
  .timeloop/runs/t32_base19_semantic_leak_types_independent.json \
  .timeloop/runs/t32_base19_semantic_leak_types_report.md \
  .timeloop/tests/test_lychrel_semantic_leak_types.py
git diff --cached --name-only
git commit -m "exp: certify base19 semantic leak types"
```

Expected staged paths: exactly the six Task 7 paths; protected ZIP hash exact.

### Task 8: Full regression and bounded PASS conclusion

**Precondition:** Durable Task 7 artifacts reproduce. Early STOP outcomes do
not execute this task or modify documentation.

**Files:**

- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `docs/superpowers/plans/2026-08-10-base19-semantic-leak-types.md`

**Interfaces:**

- Consumes the four durable T32 artifacts and all frozen prior evidence.
- Produces only the exact T32 PASS boundary and execution record.

- [ ] **Step 1: Run focused T27--T32 regression**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_invariant_lift.py \
  .timeloop/tests/test_lychrel_quotient_automaton.py \
  .timeloop/tests/test_lychrel_reachability_separator.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py \
  .timeloop/tests/test_lychrel_semantic_leak_types.py -q
```

Expected: zero failures.

- [ ] **Step 2: Run complete Timeloop assurance**

```bash
uv run --extra exact --extra dev pytest .timeloop/tests -q
uv run --extra exact --extra dev ruff check .timeloop
git diff --check
```

Expected: zero pytest failures and zero Ruff errors.

- [ ] **Step 3: Reproduce T32 artifacts and collect exact execution facts**

Run one fresh temporary Task 7 pipeline and compare all four files byte for
byte with durable outputs. Record test counts/durations, family text, type
count, diversity masks, discovery counters, exact bad-input count, type
ownership counts, byte counts, and four artifact hashes in an `Execution
outcome` section appended to this plan using `apply_patch`.

- [ ] **Step 4: Append only the achieved T32 PASS boundary to the notebook**

Using `apply_patch`, add one `## T32 STATUS` section stating the exact family,
per-type soundness, family exhaustiveness, diversity, full 77,824-input
independent method, compactness, artifact hashes, and strict claim boundary.
State explicitly that T32 did not derive `Q`; projection of the safe complement
would require a new approved round. Do not restate T27--T31.

- [ ] **Step 5: Final protected-scope audit and documentation commit**

```bash
git status --short
git diff --check
shasum -a 256 publication/base19-radial/preprint.zip
git add .timeloop/notebook/lychrel-bases.md \
  docs/superpowers/plans/2026-08-10-base19-semantic-leak-types.md
git diff --cached --name-only
git commit -m "docs: record base19 semantic leak types outcome"
```

Expected: exact ZIP hash, exactly two staged documentation paths, and all
pre-existing publication, notebook, `.DS_Store`, and ledger/pool/exam changes
remain unstaged and untouched.

## Execution handoff

Execute inline with `superpowers:executing-plans`, in task order. Do not
dispatch subagents. Task 4 and Task 5 are hard mathematical STOP gates; a STOP
is a completed T32 outcome and does not authorize Tasks after that gate or an
alternative experiment.
