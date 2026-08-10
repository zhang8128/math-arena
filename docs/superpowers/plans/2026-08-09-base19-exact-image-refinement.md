# Base-19 Exact-Image Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Execute inline without subagents.

**Goal:** Certify whether the frozen five-equation predicate `Q0` is implied by
the promoted layer-30 frontier and, together with T29's separator, universally
excludes exact layer-32 successors.

**Architecture:** A new immutable T30 certificate language records one exact
image obligation per promoted predecessor. A primary Z3 runner binds all
T27--T29 artifacts, checks predecessor implication, finite behavior, and the
refined successor query; an isolated standard-library checker reconstructs
both local relations and independently replays the same boundary. T29 remains
byte-for-byte immutable and is referenced by digest rather than rewritten.

**Tech Stack:** Python 3.13 via `uv`, frozen dataclasses, existing canonical
JSON and affine-predicate types, `z3-solver` 5.x for primary checks, Python
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
- Bind equation content SHA-256
  `ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040`,
  frontier content SHA-256
  `0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0`,
  provenance SHA-256
  `cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302`,
  raw T27 evidence SHA-256
  `32324c40903b78aec4d787b7e64a6d73d0999e3846d91ca1340c99f8ac2d8686`,
  raw T28 evidence SHA-256
  `b0904f68fda4ad7990ac1d474ec157cf671567cdf02869d9ae2cceebe1814e47`,
  and raw T28 independent SHA-256
  `7f095af25afc02ff48fe4d2ee53b4827ba99fa1548a5d970e475780fdaa1639e`.
- Bind raw T29 evidence, trace, dataset, certificate, and independent hashes,
  respectively:
  `c1e3dc4bc4ab07207a6ab49d6a9c9fd86486013abeaf016b6ecd59c9755e1d32`,
  `c56877975293c10575009a691b1d1bbde376838f805d232a2c18a4d00b2c4715`,
  `6603e381805db845ef9388d234e36f31eba510d838ac98c143c238c2ff144995`,
  `1c234891f001cb3a59e5670560ab26e3cb248a943e249aee049aac7d32c7db5a`,
  and `9f926208cc7416e24d811f6cd54485d19741b6f8ffe44f3b365b2f816e579644`.
- Preserve every T27, T28, and T29 durable byte and conclusion. T30 may import
  their public interfaces but may not modify their source files.
- Require the exact removed coordinate `phase=0,n=0,column=82` in every bound
  source and T30 artifact.
- Freeze `Q0` at one five-atom conjunction, coefficient magnitude at most
  three, maximum atom support 11, and total coefficient support 34. Do not
  synthesize, refine, widen, or replace it after a counterexample.
- Keep `S29` and `Q0` as separate predicates. Do not merge their fifteen atoms
  into one T29 `LayerPredicate` or change the existing 12-atom ceiling.
- Expect 18 promoted layer-30 predecessors, five successor-bearing
  predecessors, 18 exact local models, and 18 distinct layer-31 outputs.
- Treat the promoted layer-30 frontier as the reachability premise. Do not
  claim `Q0` for arbitrary predecessor interfaces or claim a compact formula
  for the premise.
- Fail closed on solver `UNKNOWN`, digest/count mismatch, malformed syntax,
  noncanonical witnesses, mutation survival, explicit-state encoding inside
  `Q0`, or primary/independent disagreement.
- Do not begin lower-layer extension, weakest-preimage fallback, semantic-leak
  typing, symbolic base lifting, base comparison, topology scans, publication
  changes, or Lean work.

## File Map

- Create `.timeloop/lib/lychrel_exact_image_refinement.py` for immutable
  predecessor obligations, T30 certificates, strict parsing, and canonical
  serialization.
- Create `.timeloop/runs/t30_base19_exact_image_refinement.py` for frozen input
  loading, the fixed `Q0`, primary implication/finite/semantic checks, gating,
  CLI output, and report rendering.
- Create
  `.timeloop/runs/t30_base19_exact_image_refinement_independent.py` for the
  isolated standard-library assurance checker.
- Create `.timeloop/tests/test_lychrel_exact_image_refinement.py` for syntax,
  real-artifact, exact-relation, isolation, determinism, and mutation tests.
- Create four durable T30 artifacts only after assurance agrees:
  `.timeloop/runs/t30_base19_exact_image_refinement.json`,
  `.timeloop/runs/t30_base19_exact_image_refinement_certificate.json`,
  `.timeloop/runs/t30_base19_exact_image_refinement_independent.json`, and
  `.timeloop/runs/t30_base19_exact_image_refinement_report.md`.
- Modify `.timeloop/notebook/lychrel-bases.md` and this plan only after the
  achieved boundary is independently verified.

---

### Task 1: Immutable T30 obligation and certificate language

**Files:**

- Create: `.timeloop/lib/lychrel_exact_image_refinement.py`
- Create: `.timeloop/tests/test_lychrel_exact_image_refinement.py`

**Interfaces:**

- Consumes `LayerPredicate`, `SemanticWitness`, and `canonical_bytes` from the
  existing T27/T29 libraries.
- Produces `PredecessorImageObligation`,
  `ExactImageRefinementCertificate`, and
  `parse_exact_image_refinement_certificate(payload)`.

- [ ] **Step 1: Write strict failing syntax tests**

Create the test module with repository path setup matching the T29 test file.
Add a `q0_fixture()` containing the exact five equations from the approved
spec, then add these tests:

```python
def test_predecessor_obligation_requires_canonical_identity() -> None:
    obligation = PredecessorImageObligation(
        predecessor_index=0,
        predecessor_sha256="a" * 64,
        exact_model_count=0,
        output_count=0,
        output_sha256=hashlib.sha256(canonical_bytes([])).hexdigest(),
        q0_violation_status="UNSAT",
    )
    assert obligation.to_payload()["predecessor_index"] == 0
    with pytest.raises(ValueError, match="predecessor index"):
        replace(obligation, predecessor_index=-1)
    with pytest.raises(ValueError, match="q0 violation status"):
        replace(obligation, q0_violation_status="UNKNOWN")


def test_exact_image_certificate_round_trips_strictly() -> None:
    certificate = certificate_fixture()
    assert parse_exact_image_refinement_certificate(
        certificate.to_payload()
    ) == certificate
    mutated = certificate.to_payload()
    mutated["unexpected"] = True
    with pytest.raises(ValueError, match="certificate keys differ"):
        parse_exact_image_refinement_certificate(mutated)
```

Add validation tests for duplicate/skipped predecessor indices, malformed
SHA-256 values, noncanonical digest maps, a predicate with two clauses, a
predicate with four or six atoms, a non-equality atom, semantic `SAT` without
a witness, semantic `UNSAT` with a witness, and PASS without exactly 18
obligations.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q
```

Expected: collection fails because `lychrel_exact_image_refinement` does not
exist.

- [ ] **Step 3: Implement the immutable types and strict parser**

Use these exact public shapes:

```python
@dataclass(frozen=True)
class PredecessorImageObligation:
    predecessor_index: int
    predecessor_sha256: str
    exact_model_count: int
    output_count: int
    output_sha256: str
    q0_violation_status: str


@dataclass(frozen=True)
class ExactImageRefinementCertificate:
    schema: str
    status: str
    base: int
    removed: str
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    q0: LayerPredicate
    predecessor_obligations: tuple[PredecessorImageObligation, ...]
    implication_status: str
    finite_status: str
    semantic_status: str
    implication_witness: SemanticWitness | None
    semantic_witness: SemanticWitness | None
```

Require schema `t30-base19-exact-image-refinement-certificate-v1`, base 19,
the frozen removed coordinate, exactly six sorted source digests, exactly five
sorted T29 artifact digests, and a layer-31 `q0` with one five-atom equality
clause. Require predecessor indices to be consecutive from zero. A PASS
requires 18 obligations, implication `UNSAT`, finite `PASS`, semantic `UNSAT`,
and no witnesses. Permit certificate status only
`EXACT_IMAGE_REFINEMENT_PASS` or `EXACT_IMAGE_REFINEMENT_STOP`; implication
status only `SAT`, `UNSAT`, or `NOT_RUN`; finite status only `PASS`, `STOP`, or
`NOT_RUN`; and semantic status only `SAT`, `UNSAT`, or `NOT_RUN`. Enforce this
exact first-failure state machine:

```text
PASS          implication=UNSAT finite=PASS semantic=UNSAT, 18 obligations
implication   implication=SAT   finite=NOT_RUN semantic=NOT_RUN, prefix + witness
finite        implication=UNSAT finite=STOP semantic=NOT_RUN, 18 obligations
semantic      implication=UNSAT finite=PASS semantic=SAT, 18 obligations + witness
```

An implication or semantic `SAT` requires its corresponding complete
`SemanticWitness`; every other state forbids that witness. A source-binding
failure produces STOP evidence but no certificate because its premises could
not be authenticated.

Implement exact-key parsing for the certificate, predicate, obligations, and
witnesses. Reconstruct `LinearAtom`, `Conjunction`, and `LayerPredicate`
instances instead of retaining raw mappings.

- [ ] **Step 4: Run syntax tests GREEN and lint**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git diff --check
```

Expected: all Task 1 tests pass and Ruff reports no errors.

- [ ] **Step 5: Commit Task 1**

```bash
git add .timeloop/lib/lychrel_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git commit -m "feat: define base19 exact-image refinement certificates"
```

### Task 2: Frozen T29 adapter and exact five-equation `Q0`

**Files:**

- Create: `.timeloop/runs/t30_base19_exact_image_refinement.py`
- Modify: `.timeloop/tests/test_lychrel_exact_image_refinement.py`

**Interfaces:**

- Consumes `load_t29_inputs`, `parse_separator_certificate`,
  `SeparatorDataset`, and the five durable T29 files.
- Produces `T30Inputs`, `build_q0(variables)`, and
  `load_t30_inputs(root, **path_overrides)`.

- [ ] **Step 1: Write failing frozen-adapter tests**

```python
def test_q0_is_the_exact_five_atom_closed_grammar_candidate() -> None:
    inputs = load_t30_inputs(ROOT)
    q0 = build_q0(inputs.variables)
    atoms = q0.clauses[0].atoms
    assert q0.layer == 31
    assert len(q0.clauses) == 1
    assert len(atoms) == 5
    assert {atom.relation for atom in atoms} == {"eq"}
    assert max(abs(c) for atom in atoms for _, c in atom.terms) == 3
    assert max(len(atom.terms) for atom in atoms) == 11
    assert sum(len(atom.terms) for atom in atoms) == 34


def test_t30_adapter_binds_the_complete_t29_boundary() -> None:
    inputs = load_t30_inputs(ROOT)
    assert len(inputs.dataset.positives) == 12
    assert len(inputs.dataset.trace_negatives) == 221
    assert len(inputs.dataset.live_controls) == 6
    assert dict(inputs.t29_artifact_digests) == T29_ARTIFACT_DIGESTS
    assert dict(inputs.t29_leak) == {
        "D0": 5, "D1": 6,
        "L0": 0, "L1": 1, "L2": 1, "L3": 0, "L4": 1, "L5": 1,
        "R0": 0, "R1": 0, "R2": 1, "R3": 0, "R4": 0, "R5": 1,
    }
```

Add parameterized mutations for each raw T29 file, T29 status, certificate
predicate, dataset count, leak value, source digest, and removed coordinate.
Each must raise `EvidenceError` before `Q0` checking.

- [ ] **Step 2: Run adapter tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q -k 'q0 or adapter'
```

Expected: import failure for `t30_base19_exact_image_refinement`.

- [ ] **Step 3: Implement `T30Inputs`, frozen hashes, and `Q0`**

Use this exact container:

```python
@dataclass(frozen=True)
class T30Inputs:
    t29_inputs: T29Inputs
    t29_certificate: SeparatorCertificate
    dataset: SeparatorDataset
    variables: tuple[str, ...]
    t29_leak: tuple[tuple[str, int], ...]
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
```

Define `_SOURCE_DIGESTS` and `_T29_ARTIFACT_DIGESTS` from Global Constraints.
`load_t30_inputs` must read and raw-hash evidence, trace, dataset, certificate,
and independent audit; require the exact T29 achieved statuses and cross-file
hashes; parse the certificate with the existing strict parser; reconstruct the
`SeparatorDataset`; and derive the canonical leak from the complete T29 SAT
witness. Accept keyword-only path overrides for all five files so mutations
never overwrite durable artifacts.

Construct `Q0` only from these atoms:

```python
LinearAtom("eq", (("L1", 1), ("L4", -1), ("L5", 1), ("R4", -1)), 0)
LinearAtom("eq", (("L1", 1), ("L2", -2), ("L4", -2), ("L5", -2),
                  ("R1", -3), ("R2", 3), ("R3", 2), ("R4", 1)), 0)
LinearAtom("eq", (("L0", 3), ("L1", 1), ("L2", 2), ("L5", -2),
                  ("R1", -3), ("R3", 1)), 3)
LinearAtom("eq", (("D1", 1), ("L0", 3), ("L1", -2), ("L2", -3),
                  ("L3", 1), ("L4", 1), ("R0", -1), ("R1", -3),
                  ("R2", -3), ("R3", 3), ("R4", -1)), 9)
LinearAtom("eq", (("D0", 1), ("D1", -1), ("L0", -1),
                  ("R0", 1), ("R5", 1)), 1)
```

- [ ] **Step 4: Run Task 2 GREEN and prove T29 bytes unchanged**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q
shasum -a 256 \
  .timeloop/runs/t29_base19_reachability_separator.json \
  .timeloop/runs/t29_base19_reachability_separator_trace.json \
  .timeloop/runs/t29_base19_reachability_separator_dataset.json \
  .timeloop/runs/t29_base19_reachability_separator_certificate.json \
  .timeloop/runs/t29_base19_reachability_separator_independent.json
git diff --check
```

Expected: tests pass and the five hashes equal Global Constraints.

- [ ] **Step 5: Commit Task 2**

```bash
git add .timeloop/runs/t30_base19_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git commit -m "feat: freeze base19 exact-image refinement inputs"
```

### Task 3: Primary exact predecessor-image implication

**Files:**

- Modify: `.timeloop/runs/t30_base19_exact_image_refinement.py`
- Modify: `.timeloop/tests/test_lychrel_exact_image_refinement.py`

**Interfaces:**

- Consumes `T30Inputs` and `PredecessorImageObligation`.
- Produces `PredecessorImplicationCheck` and
  `check_predecessor_implication(inputs, q0)`.

- [ ] **Step 1: Write the failing exact-image tests**

```python
def test_real_predecessor_image_implies_q0_exactly() -> None:
    inputs = load_t30_inputs(ROOT)
    result = check_predecessor_implication(
        inputs, build_q0(inputs.variables)
    )
    assert result.status == "UNSAT"
    assert result.witness is None
    assert len(result.obligations) == 18
    assert [item.exact_model_count for item in result.obligations] == [
        0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 4, 4, 0, 4, 2, 0,
    ]
    assert sum(item.output_count for item in result.obligations) == 18
    assert sum(item.output_count > 0 for item in result.obligations) == 5
    assert {item.q0_violation_status for item in result.obligations} == {"UNSAT"}


def test_mutated_q0_returns_a_complete_implication_witness() -> None:
    inputs = load_t30_inputs(ROOT)
    q0 = build_q0(inputs.variables)
    atoms = list(q0.clauses[0].atoms)
    atom = atoms[-1]
    atoms[-1] = LinearAtom(atom.relation, atom.terms, atom.constant + 1)
    mutated = LayerPredicate(31, q0.variables, (Conjunction(tuple(atoms)),))
    result = check_predecessor_implication(inputs, mutated)
    assert result.status == "SAT"
    assert result.witness is not None
    assert len(result.witness.input_state) == 13
    assert len(result.witness.output_state) == 14
```

Also require two runs to return equal immutable results and require every
predecessor/output digest to be lowercase SHA-256.

- [ ] **Step 2: Run implication tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q \
  -k predecessor
```

Expected: import failure for `check_predecessor_implication`.

- [ ] **Step 3: Implement deterministic exact model enumeration**

Add:

```python
@dataclass(frozen=True)
class PredecessorImplicationCheck:
    status: str
    obligations: tuple[PredecessorImageObligation, ...]
    witness: SemanticWitness | None
```

Build the frontier-layer-31 Z3 relation from the original 12 equations and
exact carry/digit domains. For each predecessor in serialized frontier order:

1. fix all 13 input variables;
2. enumerate every complete relation model by blocking the complete sorted
   assignment after each `SAT` result;
3. collect and sort complete assignments and their canonical 14-variable
   output projections;
4. compare exact model/output counts and the canonical output digest with the
   corresponding frozen frontier transition;
5. evaluate `Q0` on every projection; and
6. return the lexicographically first complete `SemanticWitness` immediately
   if `T30_31 and not Q0` is satisfiable.

Hash a predecessor as `sha256(canonical_bytes(list(state)))` and outputs as
`sha256(canonical_bytes([list(row) for row in sorted(outputs)]))`. Treat Z3
`UNKNOWN`, duplicate complete models, unbound variables, or any frontier
disagreement as `EvidenceError`.

- [ ] **Step 4: Run Task 3 GREEN and lint**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q -k predecessor
uv run --extra exact --extra dev ruff check \
  .timeloop/runs/t30_base19_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git diff --check
```

- [ ] **Step 5: Commit Task 3**

```bash
git add .timeloop/runs/t30_base19_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git commit -m "exp: prove base19 predecessor-image implication"
```

### Task 4: Finite boundary, refined semantic gate, and primary evidence

**Files:**

- Modify: `.timeloop/runs/t30_base19_exact_image_refinement.py`
- Modify: `.timeloop/tests/test_lychrel_exact_image_refinement.py`

**Interfaces:**

- Produces `FiniteBoundaryCheck`, `RefinedSemanticCheck`,
  `check_finite_boundary(inputs, q0)`,
  `check_refined_semantics(inputs, q0)`,
  `decide_t30_gate(inputs, implication, finite, semantic)`,
  `build_t30_primary(root)`, and `render_t30_report(evidence)`.

- [ ] **Step 1: Write failing finite and semantic tests**

```python
def test_real_q0_passes_the_frozen_finite_boundary() -> None:
    inputs = load_t30_inputs(ROOT)
    result = check_finite_boundary(inputs, build_q0(inputs.variables))
    assert result.status == "PASS"
    assert result.q0_positive_count == 12
    assert result.q0_trace_accepted == 0
    assert result.q0_live_count == 6
    assert result.q0_leak_holds is False
    assert result.combined_failures == ()


def test_real_refined_successor_query_is_unsat() -> None:
    inputs = load_t30_inputs(ROOT)
    result = check_refined_semantics(inputs, build_q0(inputs.variables))
    assert result.status == "UNSAT"
    assert result.equation_count == 12
    assert result.witness is None
```

Add a semantic control using only the first two `Q0` equations and require
`SAT` with a complete 14-input/14-output witness. Add gate tests for an
implication SAT STOP, a finite STOP, a semantic SAT STOP, and the exact PASS.
Require the PASS certificate to retain `S29` only by its T29 certificate hash,
not as fifteen merged atoms.

- [ ] **Step 2: Run gate tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q \
  -k 'finite or semantic or gate'
```

Expected: missing finite and semantic interfaces.

- [ ] **Step 3: Implement finite replay and the exact refined query**

Use these result types:

```python
@dataclass(frozen=True)
class FiniteBoundaryCheck:
    status: str
    q0_positive_count: int
    q0_trace_accepted: int
    q0_live_count: int
    q0_leak_holds: bool
    combined_failures: tuple[tuple[str, tuple[int, ...]], ...]


@dataclass(frozen=True)
class RefinedSemanticCheck:
    status: str
    equation_count: int
    witness: SemanticWitness | None
```

`check_finite_boundary` evaluates `Q0` directly on the frozen dataset and leak,
then evaluates `S29 and Q0` with separate predicate calls. Positives must
satisfy both. Trace states must fail `Q0`; live controls may satisfy `Q0` but
must fail `S29`; the leak must fail `Q0`.

`check_refined_semantics` builds the exact frontier-layer-32 relation and adds
both predicate formulas separately. On SAT, lexicographically minimize every
complete input/output/local variable using the existing T29 domain order and
return a complete witness. On UNSAT, return no witness. Never serialize a
combined 15-atom predicate.

- [ ] **Step 4: Implement the gate, primary builder, report, and CLI**

`decide_t30_gate` must select the first failure in this order: source binding,
implication, finite boundary, refined semantics. Produce only:

```text
EXACT_IMAGE_REFINEMENT_PASS
EXACT_IMAGE_REFINEMENT_STOP
```

The evidence schema is `t30-base19-exact-image-refinement-evidence-v1` and
records source/T29 hashes, exact `Q0`, all counts, obligation summaries,
statuses, stop reason, optional witnesses, claim boundary, limitations, Prism
failure provenance, and research URLs from the spec. The certificate uses the
Task 1 type. The CLI requires `--evidence`, `--certificate`, and `--report`;
it writes canonical JSON plus a trailing newline and removes a stale
certificate when no certificate is produced.

`render_t30_report` must say that PASS is relative to the promoted layer-30
premise and must not use the words inductive, symbolic-base, or publication as
positive claims.

- [ ] **Step 5: Run Task 4 GREEN and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_exact_image_refinement.py \
  .timeloop/runs/t30_base19_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git diff --check
git add .timeloop/runs/t30_base19_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git commit -m "exp: decide base19 exact-image refinement gate"
```

### Task 5: Isolated standard-library assurance

**Files:**

- Create: `.timeloop/runs/t30_base19_exact_image_refinement_independent.py`
- Modify: `.timeloop/tests/test_lychrel_exact_image_refinement.py`

**Interfaces:**

- Consumes raw equation/frontier JSON; T27 evidence; T28 evidence and audit;
  all five T29 artifacts; and temporary T30 evidence/certificate.
- Produces one canonical stdout audit with schema
  `t30-base19-exact-image-refinement-independent-v1`.

- [ ] **Step 1: Write failing isolation and acceptance tests**

Add `independent_command(...)` with positional paths in this exact order:

```text
EQUATIONS FRONTIER T27_EVIDENCE T28_EVIDENCE T28_INDEPENDENT
T29_TRACE T29_DATASET T29_EVIDENCE T29_CERTIFICATE T29_INDEPENDENT
T30_EVIDENCE T30_CERTIFICATE
```

Then add:

```python
def test_independent_checker_starts_under_isolated_python() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", str(INDEPENDENT), "--help"],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0
    assert "T30_CERTIFICATE" in completed.stdout


def test_independent_checker_accepts_primary_temporary_artifacts(
    tmp_path: Path,
) -> None:
    evidence, certificate = write_primary_fixture(tmp_path)
    completed = subprocess.run(
        independent_command(evidence=evidence, certificate=certificate),
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    audit = json.loads(completed.stdout)
    assert audit["status"] == "EXACT_IMAGE_REFINEMENT_PASS"
    assert audit["repository_imports"] == []
    assert audit["predecessor_obligation_count"] == 18
    assert audit["successor_bearing_predecessor_count"] == 5
    assert audit["exact_model_count"] == 18
    assert audit["semantic_status"] == "UNSAT"
```

Add parameterized rejection tests for equation/frontier/T27/T28/T29/T30 hash
mutations, a `Q0` constant, an obligation predecessor digest, exact model
count, output digest, T29 dataset row, T29 leak, semantic status, and a forged
SAT witness.

- [ ] **Step 2: Run independent tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q \
  -k independent
```

Expected: the independent script is missing.

- [ ] **Step 3: Implement strict isolated parsing and source binding**

The script must use only `argparse`, `hashlib`, `itertools`, `json`, `re`,
`sys`, and `pathlib`. Copy no repository imports. Require exact top-level keys,
schemas, statuses, raw hashes, content hashes, count fields, canonical order,
and cross-artifact identities. Parse `S29` and `Q0` independently and require
five equality atoms in `Q0`, coefficient magnitude at most three, maximum
support 11, and total support 34.

- [ ] **Step 4: Implement independent exact-relation replay**

Adapt the T27 independent checker's `_equation_variables`, `_equation_holds`,
`_allowed_equation_tuples`, `_allowed_atom_tuples`, `_propagate`, and recursive
CSP search into this isolated file. Add `_enumerate_solutions` that branches in
the same deterministic domain-size/degree/name order and returns sorted
complete assignments.

For frontier layer 31, fix each serialized predecessor, enumerate all complete
models of its 12 equations, project/deduplicate canonical outputs, evaluate
`Q0`, and reproduce every primary obligation digest and count. For frontier
layer 32, combine equation constraints with atom constraints for `S29` and
`Q0` and require `_csp_satisfiable(...) is False`. Independently evaluate the
239 finite rows and the T29 leak before accepting semantic UNSAT.

- [ ] **Step 5: Return the canonical audit and run GREEN**

On PASS, the audit must contain raw primary/certificate hashes, all frozen
source/T29 hashes, `repository_imports: []`, counts `18/5/18/18`, finite
counts `12/0/6`, semantic equation count 12, semantic status `UNSAT`, and
overall status `EXACT_IMAGE_REFINEMENT_PASS`. Reject errors on stderr with
prefix `REJECT:` and exit code 2. Also implement the certificate state machine
from Task 1: if the fixed real inputs yield a mathematical STOP, independently
reproduce its first exact failure and witness, emit
`EXACT_IMAGE_REFINEMENT_STOP`, and reject any later-stage result that should
have been `NOT_RUN`. A source-binding STOP has no certificate and therefore
terminates before this checker is invoked.

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q -k independent
uv run --extra exact --extra dev ruff check \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git diff --check
```

- [ ] **Step 6: Commit Task 5**

```bash
git add .timeloop/runs/t30_base19_exact_image_refinement_independent.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git commit -m "exp: independently audit base19 exact-image refinement"
```

### Task 6: Deterministic CLI checkpoint and durable artifacts

**Files:**

- Modify: `.timeloop/tests/test_lychrel_exact_image_refinement.py`
- Create: `.timeloop/runs/t30_base19_exact_image_refinement.json`
- Create: `.timeloop/runs/t30_base19_exact_image_refinement_certificate.json`
- Create: `.timeloop/runs/t30_base19_exact_image_refinement_independent.json`
- Create: `.timeloop/runs/t30_base19_exact_image_refinement_report.md`

**Interfaces:**

- Consumes both T30 CLIs.
- Produces byte-stable durable T30 evidence only after the temporary primary
  and independent checkpoint agrees.

- [ ] **Step 1: Write failing CLI determinism tests**

```python
def test_primary_and_independent_cli_are_byte_deterministic(
    tmp_path: Path,
) -> None:
    first = run_primary_cli(tmp_path / "first")
    second = run_primary_cli(tmp_path / "second")
    assert first.evidence.read_bytes() == second.evidence.read_bytes()
    assert first.certificate.read_bytes() == second.certificate.read_bytes()
    assert first.report.read_bytes() == second.report.read_bytes()
    audit_one = run_independent_cli(first, tmp_path / "audit-one.json")
    audit_two = run_independent_cli(second, tmp_path / "audit-two.json")
    assert audit_one.read_bytes() == audit_two.read_bytes()
```

Add a durable-artifact test that parses all four expected files, recomputes
their raw SHA-256 values, and requires the independent audit to bind the raw
primary evidence and certificate hashes.

- [ ] **Step 2: Run the determinism tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q \
  -k 'deterministic or durable'
```

Expected: durable artifacts do not exist.

- [ ] **Step 3: Run the primary checkpoint twice to temporary paths**

```bash
t30_tmp_one="$(mktemp -d)"
t30_tmp_two="$(mktemp -d)"
uv run --extra exact python .timeloop/runs/t30_base19_exact_image_refinement.py \
  --evidence "$t30_tmp_one/evidence.json" \
  --certificate "$t30_tmp_one/certificate.json" \
  --report "$t30_tmp_one/report.md"
uv run --extra exact python .timeloop/runs/t30_base19_exact_image_refinement.py \
  --evidence "$t30_tmp_two/evidence.json" \
  --certificate "$t30_tmp_two/certificate.json" \
  --report "$t30_tmp_two/report.md"
cmp "$t30_tmp_one/evidence.json" "$t30_tmp_two/evidence.json"
cmp "$t30_tmp_one/certificate.json" "$t30_tmp_two/certificate.json"
cmp "$t30_tmp_one/report.md" "$t30_tmp_two/report.md"
```

Expected: all comparisons succeed and the temporary status is
`EXACT_IMAGE_REFINEMENT_PASS`. If it is STOP, do not alter `Q0`; continue only
far enough to obtain an independent replay of the exact STOP witness.

- [ ] **Step 4: Run isolated assurance twice on the temporary artifacts**

```bash
uv run --extra exact python -I \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.py \
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
  "$t30_tmp_one/evidence.json" "$t30_tmp_one/certificate.json" \
  > "$t30_tmp_one/independent.json"
uv run --extra exact python -I \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.py \
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
  "$t30_tmp_two/evidence.json" "$t30_tmp_two/certificate.json" \
  > "$t30_tmp_two/independent.json"
cmp "$t30_tmp_one/independent.json" "$t30_tmp_two/independent.json"
```

Expected: both exit codes are zero and `cmp` succeeds. Do not write durable
artifacts if either invocation rejects or the outputs differ.

- [ ] **Step 5: Write and independently read back durable artifacts**

```bash
uv run --extra exact python .timeloop/runs/t30_base19_exact_image_refinement.py \
  --evidence .timeloop/runs/t30_base19_exact_image_refinement.json \
  --certificate \
    .timeloop/runs/t30_base19_exact_image_refinement_certificate.json \
  --report .timeloop/runs/t30_base19_exact_image_refinement_report.md
uv run --extra exact python -I \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.py \
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
  > .timeloop/runs/t30_base19_exact_image_refinement_independent.json

t30_replay="$(mktemp -d)"
uv run --extra exact python .timeloop/runs/t30_base19_exact_image_refinement.py \
  --evidence "$t30_replay/evidence.json" \
  --certificate "$t30_replay/certificate.json" \
  --report "$t30_replay/report.md"
uv run --extra exact python -I \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.py \
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
  "$t30_replay/evidence.json" "$t30_replay/certificate.json" \
  > "$t30_replay/independent.json"
cmp .timeloop/runs/t30_base19_exact_image_refinement.json \
  "$t30_replay/evidence.json"
cmp .timeloop/runs/t30_base19_exact_image_refinement_certificate.json \
  "$t30_replay/certificate.json"
cmp .timeloop/runs/t30_base19_exact_image_refinement_report.md \
  "$t30_replay/report.md"
cmp .timeloop/runs/t30_base19_exact_image_refinement_independent.json \
  "$t30_replay/independent.json"
shasum -a 256 \
  .timeloop/runs/t30_base19_exact_image_refinement.json \
  .timeloop/runs/t30_base19_exact_image_refinement_certificate.json \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.json \
  .timeloop/runs/t30_base19_exact_image_refinement_report.md
```

Expected: both CLIs exit zero, all four comparisons succeed, and four raw
SHA-256 values are printed for Task 7.

- [ ] **Step 6: Run Task 6 GREEN and commit artifacts with their tests**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_exact_image_refinement.py \
  .timeloop/runs/t30_base19_exact_image_refinement.py \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git diff --check
git add .timeloop/tests/test_lychrel_exact_image_refinement.py \
  .timeloop/runs/t30_base19_exact_image_refinement.json \
  .timeloop/runs/t30_base19_exact_image_refinement_certificate.json \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.json \
  .timeloop/runs/t30_base19_exact_image_refinement_report.md
git commit -m "exp: certify base19 exact-image refinement"
```

### Task 7: Final regression, notebook boundary, and execution record

**Files:**

- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify:
  `docs/superpowers/plans/2026-08-09-base19-exact-image-refinement.md`

**Interfaces:**

- Consumes the independently verified durable status and four raw hashes.
- Produces the concise T30 notebook conclusion and completed plan record.

- [ ] **Step 1: Run focused and adjacent regressions**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_reachability_separator.py \
  .timeloop/tests/test_lychrel_quotient_automaton.py \
  .timeloop/tests/test_lychrel_invariant_lift.py -q
```

Expected: every focused T27--T30 test passes.

- [ ] **Step 2: Run the complete Timeloop suite and lint**

```bash
uv run --extra exact --extra dev pytest .timeloop/tests -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_exact_image_refinement.py \
  .timeloop/runs/t30_base19_exact_image_refinement.py \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py
git diff --check
```

Record the exact test count and elapsed time. A failure blocks the final docs
commit.

- [ ] **Step 3: Recheck every frozen and protected hash**

```bash
shasum -a 256 \
  .timeloop/runs/t29_base19_reachability_separator.json \
  .timeloop/runs/t29_base19_reachability_separator_trace.json \
  .timeloop/runs/t29_base19_reachability_separator_dataset.json \
  .timeloop/runs/t29_base19_reachability_separator_certificate.json \
  .timeloop/runs/t29_base19_reachability_separator_independent.json \
  publication/base19-radial/preprint.zip \
  .timeloop/runs/t30_base19_exact_image_refinement.json \
  .timeloop/runs/t30_base19_exact_image_refinement_certificate.json \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.json \
  .timeloop/runs/t30_base19_exact_image_refinement_report.md
```

Require the six protected values from Global Constraints and retain the four
new T30 values for documentation.

- [ ] **Step 4: Append the exact achieved T30 boundary to the notebook**

Add one `## T30 STATUS` section containing: durable status, the five equations,
the earlier-layer implication claim and its `18/5/18/18` counts, finite
`12/0/6` counts, semantic result, independent method, four T30 hashes, exact
test count, stop conditions, limitations, and the next decision. State
explicitly that the reachability premise is the promoted layer-30 frontier and
that no lower layer, base lift, comparison, topology, publication, or Lean
work ran.

- [ ] **Step 5: Add the execution outcome to this plan**

Insert `## Execution outcome (2026-08-09)` after the Tech Stack paragraph.
Record each task's achieved status, the independent result, four raw artifact
hashes, exact test count, protected ZIP hash, and skipped out-of-scope work.
Use the actual durable values only.

- [ ] **Step 6: Verify the final staged scope and commit**

```bash
git diff --check
git status --short
git add .timeloop/notebook/lychrel-bases.md \
  docs/superpowers/plans/2026-08-09-base19-exact-image-refinement.md
git diff --cached --name-only
git diff --cached --check
git commit -m "docs: record base19 exact-image refinement outcome"
```

Expected staged paths: exactly the notebook and this plan. Recheck
`publication/base19-radial/preprint.zip` after the commit and require its
protected hash.

## Execution handoff

Execute this plan inline with `superpowers:executing-plans`. Review the diff,
tests, artifact hashes, and commit after each task. Stop at the first specified
gate; do not substitute any fallback experiment inside T30.
