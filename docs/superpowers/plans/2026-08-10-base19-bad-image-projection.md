# Base-19 Bad-Image Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Execute inline without subagents.

**Goal:** Decide whether one compact layer-30 predicate `P30`, derived from the
exact bad-successor projection, covers all 18 promoted predecessors and implies
T30's frozen five-equation predicate `Q0` under the exact layer-30-to-31
relation.

**Architecture:** A T31-local predicate and certificate language permits the
approved coefficient bound without widening T27's immutable affine types. A
primary Z3 runner binds T29 and T30, projects the five exact `Q0` failure
relations, performs bounded deterministic counterexample-guided synthesis, and
then rechecks the candidate from scratch. An isolated standard-library checker
enumerates all 77,824 layer-30 interfaces and reconstructs both local relations
before any durable artifact is promoted.

**Tech Stack:** Python 3.13 via `uv`, frozen dataclasses, canonical JSON,
`z3-solver` 5.x for projection and primary semantics, Python standard-library
generalized arc consistency/backtracking for independent assurance, pytest 8.x,
Ruff, and SHA-256.

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
- Require base 19, removed coordinate `phase=0,n=0,column=82`, the original
  12 layer-30-to-31 equations, T29's ten-atom `S29`, and T30's exact five
  equations `Q0`. Never modify T27--T30 code or artifacts.
- Freeze the layer-30 scope in this order:
  `L0,R0,L1,R1,L2,R2,L3,R3,L4,R4,L5,R5,D0`; carries are in `{0,1}` and
  `D0` is in `{0,...,18}`.
- Freeze `P30` to at most two disjunctive clauses, at most six atoms per
  evaluation path, relations `eq`, `le`, and `congruent`, coefficients in
  `{-9,...,9}`, congruence moduli in `{2,...,19}`, and support at most 13.
- Do not reuse or widen `lychrel_invariant_certificate.LinearAtom`, whose
  coefficient limit of three belongs to T27. T31 owns separate predicate types.
- Reject state indices, digests used as selectors, per-state minterms,
  nonlinear terms, auxiliary Booleans, lookup operations, and any predicate
  whose canonical bytes are not strictly fewer than the canonical 18-row table.
- Inspect at most 64 distinct canonical bad-image counterexamples. Do not widen
  the grammar, add clauses, start a generic atom scan, compute/promote the full
  weakest precondition, or fall back to semantic-leak typing.
- PASS claims only promoted coverage and
  `P30(u) and T30_31(u,x) implies Q0(x)`, plus the composed bounded consequence.
  It does not claim exact reachability, `P30 = R30`, or weakest-precondition
  equality.
- Fail closed on solver `UNKNOWN`, malformed projection syntax, digest/count
  mismatch, noncanonical output, mutation survival, byte instability, or
  primary/independent disagreement.
- Do not serialize the exploratory `21,477` bad-input count or `27/31` failure
  masks in durable T31 output unless an independent checker first reproduces
  them. Neither value is a gate.
- Do not begin layer-29 extension, symbolic-base lifting, base comparison,
  topology scans, publication changes, or Lean work.
- Preserve Prism provenance exactly: Ollama default `muse-glimmer:30b-mlx`,
  Prism commit `5629f09`, live probe success, `frame_status` failure on the
  unsupported generation-2 schema, and no fabricated frame artifact.
- Cite discovery motivation, not proof, from
  <https://arxiv.org/abs/2405.01183>,
  <https://arxiv.org/abs/1010.4422>, and
  <https://link.springer.com/chapter/10.1007/978-3-031-57249-4_9>.

## File Map

- Create `.timeloop/lib/lychrel_bad_image_projection.py` for T31-local atoms,
  clauses, predicates, provenance records, witnesses, certificates, strict
  parsers, evaluation, and compactness measurement.
- Create `.timeloop/runs/t31_base19_bad_image_projection.py` for frozen T29/T30
  adapters, exact projection, deterministic synthesis, fresh primary checks,
  gate selection, CLI output, and report rendering.
- Create `.timeloop/runs/t31_base19_bad_image_projection_independent.py` for
  the isolated standard-library full-domain audit.
- Create `.timeloop/tests/test_lychrel_bad_image_projection.py` for syntax,
  binding, projection provenance, synthesis, semantics, isolation, mutation,
  and determinism tests.
- Create only after temporary primary and independent agreement:
  `.timeloop/runs/t31_base19_bad_image_projection.json`,
  `.timeloop/runs/t31_base19_bad_image_projection_certificate.json`,
  `.timeloop/runs/t31_base19_bad_image_projection_independent.json`, and
  `.timeloop/runs/t31_base19_bad_image_projection_report.md`.
- Modify `.timeloop/notebook/lychrel-bases.md` and this plan only after the
  achieved PASS or independently verified STOP boundary is durable.

---

### Task 1: T31-local predicate and certificate language

**Files:**

- Create: `.timeloop/lib/lychrel_bad_image_projection.py`
- Create: `.timeloop/tests/test_lychrel_bad_image_projection.py`

**Interfaces:**

- Consumes only `canonical_bytes` and `SemanticWitness` from existing libraries.
- Produces `ProjectionAtom`, `ProjectionClause`, `Layer30Predicate`,
  `ProjectionOrigin`, `BadImageProjectionCertificate`, `evaluate_p30`,
  `compactness_bytes`, and `parse_bad_image_projection_certificate(payload)`.

- [ ] **Step 1: Write failing grammar and certificate tests**

Create the test module with the same `ROOT` and `sys.path` setup as the T30
tests. Add exact fixtures and these core tests:

```python
P30_VARIABLES = (
    "L0", "R0", "L1", "R1", "L2", "R2", "L3", "R3",
    "L4", "R4", "L5", "R5", "D0",
)


def test_projection_atom_uses_the_t31_grammar_without_widening_t27() -> None:
    atom = ProjectionAtom("le", (("D0", 9), ("L0", -9)), 18)
    assert atom.terms == (("D0", 9), ("L0", -9))
    with pytest.raises(ValueError, match="coefficient"):
        replace(atom, terms=(("D0", 10),))
    with pytest.raises(ValueError, match="modulus"):
        ProjectionAtom("congruent", (("D0", 1),), 0, 20)


def test_layer30_predicate_rejects_table_shaped_syntax() -> None:
    with pytest.raises(ValueError, match="six atoms"):
        ProjectionClause(
            tuple(
                ProjectionAtom("eq", (("D0", 1),), constant)
                for constant in range(7)
            )
        )


def certificate_fixture() -> BadImageProjectionCertificate:
    atom = ProjectionAtom("eq", (("L0", 1),), 0)
    p30 = Layer30Predicate(
        30, P30_VARIABLES, (ProjectionClause((atom,)),)
    )

    def digest_entries(names: set[str]) -> tuple[tuple[str, str], ...]:
        return tuple(
            sorted((name, hashlib.sha256(name.encode()).hexdigest()) for name in names)
        )

    return BadImageProjectionCertificate(
        schema="t31-base19-bad-image-projection-certificate-v1",
        status="BAD_IMAGE_PROJECTION_PASS",
        stop_reason=None,
        base=19,
        removed="phase=0,n=0,column=82",
        source_digests=digest_entries(
            {"equations", "frontier", "provenances", "t27_evidence",
             "t28_evidence", "t28_independent"}
        ),
        t29_artifact_digests=digest_entries(
            {"evidence", "trace", "dataset", "certificate", "independent"}
        ),
        t30_artifact_digests=digest_entries(
            {"evidence", "certificate", "independent", "report"}
        ),
        p30=p30,
        projection_origins=(
            ProjectionOrigin(
                hashlib.sha256(canonical_bytes(atom.to_payload())).hexdigest(),
                0,
                "a" * 64,
                (0,),
                "direct",
            ),
        ),
        promoted_count=18,
        promoted_sha256="b" * 64,
        predicate_bytes=100,
        state_table_bytes=200,
        counterexample_count=1,
        implication_status="UNSAT",
        implication_equation_count=12,
        composed_status="UNSAT",
        composed_equation_count=24,
        failure_witness=None,
    )


def test_t31_certificate_round_trips_with_exact_keys() -> None:
    certificate = certificate_fixture()
    assert parse_bad_image_projection_certificate(
        certificate.to_payload()
    ) == certificate
    payload = certificate.to_payload()
    payload["unexpected"] = True
    with pytest.raises(ValueError, match="certificate keys differ"):
        parse_bad_image_projection_certificate(payload)
```

Also test zero/duplicate terms, empty clauses, more than two clauses, support 14,
unknown variables, noncanonical digest maps, duplicate origins, counterexample
count 65, PASS with fewer than 18 covered states, PASS with non-compression,
PASS with `SAT`/`NOT_RUN`, STOP without a reason, and witness presence exactly
when an exact query is `SAT`.

- [ ] **Step 2: Run the focused test and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q
```

Expected: collection fails because `lychrel_bad_image_projection` does not exist.

- [ ] **Step 3: Implement immutable T31 types and strict parsing**

Use these public shapes:

```python
@dataclass(frozen=True)
class ProjectionAtom:
    relation: str
    terms: tuple[tuple[str, int], ...]
    constant: int
    modulus: int | None = None


@dataclass(frozen=True)
class ProjectionClause:
    atoms: tuple[ProjectionAtom, ...]


@dataclass(frozen=True)
class Layer30Predicate:
    layer: int
    variables: tuple[str, ...]
    clauses: tuple[ProjectionClause, ...]


@dataclass(frozen=True)
class ProjectionOrigin:
    atom_sha256: str
    failed_q0_equation: int
    qe_formula_sha256: str
    expression_path: tuple[int, ...]
    polarity: str


@dataclass(frozen=True)
class BadImageProjectionCertificate:
    schema: str
    status: str
    stop_reason: str | None
    base: int
    removed: str
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    t30_artifact_digests: tuple[tuple[str, str], ...]
    p30: Layer30Predicate
    projection_origins: tuple[ProjectionOrigin, ...]
    promoted_count: int
    promoted_sha256: str
    predicate_bytes: int
    state_table_bytes: int
    counterexample_count: int
    implication_status: str
    implication_equation_count: int
    composed_status: str
    composed_equation_count: int
    failure_witness: SemanticWitness | None
```

Canonicalize terms, atoms, clauses, and origins by `canonical_bytes`; reject
duplicates rather than silently removing them. Normalize equality atoms by
dividing the positive common gcd of coefficients and constant, then make the
first sorted coefficient positive. Normalize `le` only by a positive common
gcd (never sign-flip its direction). Normalize congruence coefficients and
constant to the unique centered residue interval
`[-floor((m-1)/2), floor(m/2)]`, removing zero terms and rejecting an empty
result. Require origin polarity `direct` or `complement` and equation index
`0..4`. Require schema
`t31-base19-bad-image-projection-certificate-v1`, the exact six source, five
T29, and four T30 sorted digest names, status `BAD_IMAGE_PROJECTION_PASS` or
`BAD_IMAGE_PROJECTION_STOP`, the frozen variable tuple, and all grammar limits.
PASS requires
`stop_reason is None`, `promoted_count == 18`, `predicate_bytes <
state_table_bytes`, `counterexample_count <= 64`, implication equation count
12, composed equation count 24, both statuses `UNSAT`, and no witness. STOP
requires a nonempty reason and a witness exactly when either status is `SAT`.

Define compactness against these exact payloads:

```python
def compactness_bytes(
    predicate: Layer30Predicate,
    promoted_rows: tuple[tuple[int, ...], ...],
) -> tuple[int, int]:
    table = {
        "layer": 30,
        "variables": list(predicate.variables),
        "states": [list(row) for row in promoted_rows],
    }
    return len(canonical_bytes(predicate.to_payload())), len(canonical_bytes(table))
```

- [ ] **Step 4: Run Task 1 GREEN and lint**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_bad_image_projection.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py
git diff --check
```

Expected: all Task 1 tests pass and Ruff reports no errors.

- [ ] **Step 5: Commit Task 1**

```bash
git add .timeloop/lib/lychrel_bad_image_projection.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py
git commit -m "feat: define base19 bad-image projection certificates"
```

### Task 2: Frozen T29/T30 adapter and exact bad-image projection

**Files:**

- Create: `.timeloop/runs/t31_base19_bad_image_projection.py`
- Modify: `.timeloop/tests/test_lychrel_bad_image_projection.py`

**Interfaces:**

- Consumes `load_t30_inputs`, `build_q0`, all five T29 artifacts, all four T30
  artifacts, and the frozen layer-31 frontier transfer.
- Produces `T31Inputs`, `ProjectionAtomRecord`, `load_t31_inputs(root,
  **path_overrides)`, `build_layer30_relation(inputs)`, and
  `project_bad_image_atoms(inputs)`.

- [ ] **Step 1: Write failing binding and projection tests**

```python
def test_t31_adapter_binds_the_complete_t30_boundary() -> None:
    inputs = load_t31_inputs(ROOT)
    assert inputs.p30_variables == P30_VARIABLES
    assert len(inputs.promoted_rows) == 18
    assert len(set(inputs.promoted_rows)) == 18
    assert dict(inputs.t30_artifact_digests) == T30_ARTIFACT_DIGESTS
    assert inputs.q0.to_payload() == inputs.t30_certificate.q0.to_payload()


def test_bad_image_atoms_have_exact_projection_provenance() -> None:
    records = project_bad_image_atoms(load_t31_inputs(ROOT))
    assert records == tuple(sorted(records, key=lambda item: canonical_bytes(item.atom)))
    assert records
    assert {item.origin.failed_q0_equation for item in records} <= set(range(5))
    assert all(len(item.origin.qe_formula_sha256) == 64 for item in records)
    assert all(item.holds_on_all_promoted for item in records)
```

Parameterize raw-byte mutations over all T29/T30 files and source-boundary
mutations over base, removed coordinate, T30 status, `Q0`, implication status,
and independent-audit counts. Require `EvidenceError` before projection.
Require two projection runs to return identical record bytes and formula hashes.

- [ ] **Step 2: Run adapter/projection tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q \
  -k 'adapter or projection_provenance'
```

Expected: import failure for `t31_base19_bad_image_projection`.

- [ ] **Step 3: Implement frozen loading and projection**

Use these public containers:

```python
@dataclass(frozen=True)
class T31Inputs:
    t30_inputs: T30Inputs
    t30_certificate: ExactImageRefinementCertificate
    q0: LayerPredicate
    p30_variables: tuple[str, ...]
    promoted_rows: tuple[tuple[int, ...], ...]
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    t30_artifact_digests: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ProjectionAtomRecord:
    atom: ProjectionAtom
    origin: ProjectionOrigin
    holds_on_all_promoted: bool
```

`load_t31_inputs` must call `load_t30_inputs`, independently raw-hash and parse
all four T30 files, require the exact achieved T30 PASS boundary and all
cross-file hashes, derive the 18 layer-30 rows by canonicalizing the input side
of frontier layer 31, and accept keyword-only path overrides for mutation tests.

`build_layer30_relation` reconstructs the original 12 equations and domains,
returning Z3, solver, variables, transfer, equations, input mapping, and output
mapping. For each `Q0` equality `i`, construct

```text
B_i(u) := exists output,local . T30_31(u,output,local) and not Q0_i(output).
```

Apply a fixed `Then("qe", "simplify")` pipeline with all input variables left
free. Canonically walk the resulting AST. Normalize integer `=`, `<=`, `>=`,
strict inequalities, and `mod` equalities into T31 atoms; convert strict integer
bounds exactly (`a < c` to `a <= c - 1`), normalize `>=` by sign reversal, and
derive the exact single-atom complement when the grammar can express it
(`not (a <= c)` becomes `-a <= -c - 1`, and a modulus-two residue becomes the
other residue). Do not approximate disequality or a complemented congruence of
modulus greater than two. Discard unsupported Boolean/arithmetic shapes and
grammar overflow. Record the failed equation index, canonical QE formula
digest, AST child-index path, and polarity for every retained atom; encode
polarity as `direct` or `complement`. Keep only atoms that evaluate true on all
18 promoted rows. Deduplicate by atom bytes, retaining the lexicographically
least origin.

- [ ] **Step 4: Run Task 2 GREEN and audit frozen hashes**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q
shasum -a 256 \
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

Expected: tests pass and every digest equals Global Constraints.

- [ ] **Step 5: Commit Task 2**

```bash
git add .timeloop/runs/t31_base19_bad_image_projection.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py
git commit -m "feat: project base19 bad-successor images"
```

### Task 3: Deterministic bounded synthesis of `P30-v0`

**Files:**

- Modify: `.timeloop/runs/t31_base19_bad_image_projection.py`
- Modify: `.timeloop/tests/test_lychrel_bad_image_projection.py`

**Interfaces:**

- Consumes `T31Inputs` and the immutable projection record pool.
- Produces `CandidateSearchResult` and `synthesize_p30(inputs, records,
  counterexample_limit=64)`.

- [ ] **Step 1: Write failing deterministic-search tests**

```python
def test_repository_projection_produces_p30_v0_or_exact_stop() -> None:
    inputs = load_t31_inputs(ROOT)
    result = synthesize_p30(inputs, project_bad_image_atoms(inputs))
    assert result.status in {
        "UNSAT", "NO_CANDIDATE", "NON_COMPACT", "BUDGET_EXHAUSTED"
    }
    assert len(result.counterexamples) <= 64
    assert result.state_table_bytes > 0
    if result.status == "UNSAT":
        assert result.p30 is not None
        assert result.predicate_bytes is not None
        assert result.predicate_bytes < result.state_table_bytes
        assert all(
            evaluate_p30(result.p30, dict(zip(P30_VARIABLES, row, strict=True)))
            for row in inputs.promoted_rows
        )
    else:
        assert result.stop_detail


def test_candidate_search_is_byte_deterministic() -> None:
    inputs = load_t31_inputs(ROOT)
    records = project_bad_image_atoms(inputs)
    first = synthesize_p30(inputs, records)
    second = synthesize_p30(inputs, records)
    assert canonical_bytes(first.to_payload()) == canonical_bytes(second.to_payload())
```

Add unit-sized synthetic tests proving the hitting-set selector minimizes
`(clause_count, max_path_atoms, total_atoms, total_support, coefficient_l1,
canonical_bytes)`, rejects seven-atom candidates, never admits a non-projected
atom, chooses the lexicographically least complete SAT witness, deduplicates
witnesses, and stops before counterexample 65.

- [ ] **Step 2: Run synthesis tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q -k candidate
```

Expected: import failure for `synthesize_p30`.

- [ ] **Step 3: Implement the exact CEGIS loop**

Use this result shape:

```python
@dataclass(frozen=True)
class CandidateSearchResult:
    status: str
    p30: Layer30Predicate | None
    origins: tuple[ProjectionOrigin, ...]
    counterexamples: tuple[SemanticWitness, ...]
    predicate_bytes: int | None
    state_table_bytes: int
    stop_detail: str | None
```

Implement `to_payload()` with exactly the seven dataclass field names as keys,
serializing `p30`, origins, and witnesses through their strict payload methods.

Start by querying `B(u)` without `P30` and recording its lexicographically least
complete witness as counterexample one; this witness counts against the limit.
At each iteration, enumerate canonical subsets of one to six projected atoms
and select the minimum objective candidate whose
conjunction falsifies every recorded bad input. The approved all-promoted atom
filter makes a second disjunct unable to improve soundness; retain the two-clause
parser boundary but search the logically minimal one-clause candidates first
and never add a redundant second clause. Compute both canonical byte counts for
every candidate and exclude non-compressing candidates before a semantic query;
return `NON_COMPACT` if projection produced candidates but none passes the byte
gate.

For each selected candidate, query a fresh solver for
`P30 and T30_31 and not Q0`. On `SAT`, minimize every original variable in
sorted-name/domain order, replay all 12 residuals, record the complete canonical
`SemanticWitness`, and add its input assignment. On `UNSAT`, return `UNSAT` with
the exact candidate and origins. Return `NO_CANDIDATE` when no subset hits the
recorded inputs, `NON_COMPACT` when only table-sized candidates remain, and
`BUDGET_EXHAUSTED` immediately after the 64th distinct SAT witness. Any
`UNKNOWN`, repeated witness, incomplete model, or residual failure raises
`EvidenceError`; it never triggers grammar expansion.

- [ ] **Step 4: Run the first falsifiable repository milestone**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q \
  -k 'repository_projection_produces_p30_v0 or candidate_search_is_byte_deterministic'
```

PASS path: the repository result is `UNSAT`, covers all 18 rows, and stays
within grammar and is strictly smaller than the canonical state table. STOP
path: preserve the exact `NO_CANDIDATE`, `NON_COMPACT`, or `BUDGET_EXHAUSTED`
result in a temporary directory, report the falsified milestone, and end T31
without Tasks 4--7 or a fallback.

- [ ] **Step 5: Run Task 3 GREEN, lint, and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_bad_image_projection.py \
  .timeloop/runs/t31_base19_bad_image_projection.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py
git diff --check
git add .timeloop/runs/t31_base19_bad_image_projection.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py
git commit -m "exp: synthesize base19 bad-image predicate"
```

### Task 4: Fresh primary coverage, compactness, implication, and composition gates

**Files:**

- Modify: `.timeloop/runs/t31_base19_bad_image_projection.py`
- Modify: `.timeloop/tests/test_lychrel_bad_image_projection.py`

**Interfaces:**

- Consumes a successful `CandidateSearchResult` but trusts only its serialized
  candidate and provenance.
- Produces `CoverageCheck`, `ImageSoundnessCheck`, `CompositionCheck`,
  `check_promoted_coverage`, `check_image_soundness`, `check_composed_semantics`,
  `decide_t31_gate`, `build_t31_primary`, and `render_t31_report`.

- [ ] **Step 1: Write failing fresh-gate tests**

```python
def test_p30_v0_passes_all_fresh_primary_obligations() -> None:
    evidence, certificate = build_t31_primary(ROOT)
    assert evidence["status"] == "BAD_IMAGE_PROJECTION_PASS"
    assert certificate.promoted_count == 18
    assert certificate.predicate_bytes < certificate.state_table_bytes
    assert certificate.implication_status == "UNSAT"
    assert certificate.implication_equation_count == 12
    assert certificate.composed_status == "UNSAT"
    assert certificate.composed_equation_count == 24
    assert certificate.failure_witness is None


def test_mutated_p30_returns_a_complete_image_witness() -> None:
    inputs = load_t31_inputs(ROOT)
    weakened = Layer30Predicate(
        30,
        P30_VARIABLES,
        (ProjectionClause((ProjectionAtom("le", (("D0", 1),), 18),)),),
    )
    check = check_image_soundness(inputs, weakened)
    assert check.status == "SAT"
    assert check.witness is not None
    assert len(check.witness.input_state) == 13
    assert len(check.witness.output_state) == 14
```

Add tests for one uncovered promoted row, equal predicate/table byte counts,
unknown solver status, provenance not matching selected atoms, first-failure
ordering, separate serialization of `P30`, `Q0`, and `S29`, and report language
that states the bounded claim and all exclusions.

- [ ] **Step 2: Run fresh-gate tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q -k 'primary or witness'
```

Expected: import failure for the new checks.

- [ ] **Step 3: Implement fresh checks and the primary CLI**

`check_promoted_coverage` directly evaluates the serialized predicate on the
18 rows and hashes the ordered rows. `check_image_soundness` rebuilds the
layer-30 relation from raw sources, not the discovery solver, and asks
`P30 and T30_31 and not Q0`. `check_composed_semantics` separately rebuilds
layers 31 and 32 and asks

```text
P30(u) and T30_31(u,x) and S29(x) and T31_32(x,y).
```

Record 12 implication equations and 24 composed equations. All SAT results
carry a lexicographically minimized complete witness. Construct
the certificate only after grammar, provenance, coverage, compactness, and both
fresh solver gates have run in that order. The evidence schema is
`t31-base19-bad-image-projection-evidence-v1`; include candidate-search status,
projection formula hashes, selected origins, exact counts/byte sizes, both
solver results, claim limitations, Prism failure provenance, and the three
primary-source URLs listed in Global Constraints.

The CLI requires `--evidence`, `--certificate`, and `--report`. It writes only
canonical JSON plus one newline and deterministic UTF-8 Markdown. Source-binding
failure writes STOP evidence and removes temporary certificate output; it never
touches durable paths implicitly.

- [ ] **Step 4: Run Task 4 GREEN and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_bad_image_projection.py \
  .timeloop/runs/t31_base19_bad_image_projection.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py
git diff --check
git add .timeloop/runs/t31_base19_bad_image_projection.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py
git commit -m "exp: decide base19 bad-image projection gate"
```

### Task 5: Isolated full-domain independent assurance

**Files:**

- Create: `.timeloop/runs/t31_base19_bad_image_projection_independent.py`
- Modify: `.timeloop/tests/test_lychrel_bad_image_projection.py`

**Interfaces:**

- Consumes raw equation/frontier JSON, five T29 artifacts, four T30 artifacts,
  and temporary T31 evidence/certificate paths.
- Produces an isolated CLI with schema
  `t31-base19-bad-image-projection-independent-v1` and no repository imports.

- [ ] **Step 1: Write failing isolation, acceptance, and mutation tests**

```python
def test_independent_checker_starts_under_isolated_python() -> None:
    completed = subprocess.run(
        [sys.executable, "-I", str(INDEPENDENT), "--help"],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0
    assert "--t31-certificate" in completed.stdout


def test_independent_checker_accepts_temporary_primary_artifacts(
    tmp_path: Path,
) -> None:
    evidence, certificate, _ = run_primary_cli(tmp_path)
    completed, audit = run_independent_cli(
        tmp_path, evidence=evidence, certificate=certificate
    )
    assert completed.returncode == 0
    assert audit["status"] == "BAD_IMAGE_PROJECTION_PASS"
    assert audit["repository_imports"] == []
    assert audit["enumerated_input_count"] == 77_824
    assert audit["promoted_count"] == 18
    assert audit["implication_status"] == "UNSAT"
    assert audit["composed_status"] == "UNSAT"
```

Parameterize mutations of a `P30` coefficient, constant, modulus, clause,
source digest, T29/T30 digest, promoted count/digest, predicate bytes, table
bytes, implication status, composition status, and witness. Every mutation must
return nonzero with a specific rejection message.

- [ ] **Step 2: Run independent tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q -k independent
```

Expected: the isolated checker file is absent.

- [ ] **Step 3: Implement the standard-library audit**

The script may import only Python's standard library. Copy no repository module.
Strictly parse raw JSON keys and raw hashes; independently parse T29's `S29`,
T30's `Q0`, and T31's `P30` with their separate grammar limits. Reconstruct the
12 equations for layers 31 and 32 from raw manifest provenance.

Enumerate inputs in exact product order:

```python
P30_VARIABLES = (
    "L0", "R0", "L1", "R1", "L2", "R2", "L3", "R3",
    "L4", "R4", "L5", "R5", "D0",
)
domains = [range(2)] * 12 + [range(19)]
for values in itertools.product(*domains):
    input_state = dict(zip(P30_VARIABLES, values, strict=True))
```

For every input satisfying `P30`, use generalized arc consistency and
deterministic backtracking to decide whether layer 31 has a successor violating
`Q0`. Independently replay promoted coverage and the two canonical byte counts.
For composition, enumerate every exact layer-31 output of each accepted input;
for outputs satisfying both `Q0` and `S29`, decide exact layer-32 successor
existence. Fail on the first lexicographically ordered witness. Emit counts and
raw bindings only after all 77,824 inputs are visited.

- [ ] **Step 4: Run the independent milestone**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q \
  -k 'independent_checker_accepts or independent_checker_rejects'
```

Expected PASS path: the checker independently returns both `UNSAT` results.
Any disagreement ends T31 at `BAD_IMAGE_PROJECTION_STOP`; do not write durable
artifacts or attempt a fallback.

- [ ] **Step 5: Run Task 5 GREEN, lint, and commit**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q
uv run --extra exact --extra dev ruff check \
  .timeloop/lib/lychrel_bad_image_projection.py \
  .timeloop/runs/t31_base19_bad_image_projection.py \
  .timeloop/runs/t31_base19_bad_image_projection_independent.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py
git diff --check
git add .timeloop/runs/t31_base19_bad_image_projection_independent.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py
git commit -m "exp: independently audit base19 bad-image projection"
```

### Task 6: Byte-stable durable T31 artifacts

**Files:**

- Modify: `.timeloop/tests/test_lychrel_bad_image_projection.py`
- Create: `.timeloop/runs/t31_base19_bad_image_projection.json`
- Create: `.timeloop/runs/t31_base19_bad_image_projection_certificate.json`
- Create: `.timeloop/runs/t31_base19_bad_image_projection_independent.json`
- Create: `.timeloop/runs/t31_base19_bad_image_projection_report.md`

**Interfaces:**

- Consumes both T31 CLIs after the independent milestone agrees.
- Produces four mutually bound, reproducible artifacts and raw SHA-256 values.

- [ ] **Step 1: Write failing two-run determinism and durable-binding tests**

```python
def test_primary_and_independent_outputs_are_byte_deterministic(
    tmp_path: Path,
) -> None:
    first = run_complete_temporary_pipeline(tmp_path / "first")
    second = run_complete_temporary_pipeline(tmp_path / "second")
    assert [path.read_bytes() for path in first] == [path.read_bytes() for path in second]


def test_durable_t31_artifacts_are_bound_and_parseable() -> None:
    certificate = parse_bad_image_projection_certificate(
        json.loads(T31_CERTIFICATE.read_bytes())
    )
    assert certificate.status == "BAD_IMAGE_PROJECTION_PASS"
    assert raw_sha256(T31_CERTIFICATE) == json.loads(
        T31_INDEPENDENT.read_bytes()
    )["certificate_file_sha256"]
```

Also assert every JSON file is canonical bytes plus one newline, the report ends
with one newline and has no trailing whitespace, evidence binds certificate
content hash, independent audit binds raw evidence/certificate hashes, and all
four files reproduce from a new temporary run.

- [ ] **Step 2: Run determinism tests and verify RED**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q -k 'deterministic or durable'
```

Expected: temporary outputs agree, while durable-binding fails because the four
durable files do not exist.

- [ ] **Step 3: Generate temporary artifacts twice and compare bytes**

```bash
T31_TMP_A="$(mktemp -d)"
T31_TMP_B="$(mktemp -d)"
uv run --extra exact python .timeloop/runs/t31_base19_bad_image_projection.py \
  --evidence "$T31_TMP_A/evidence.json" \
  --certificate "$T31_TMP_A/certificate.json" \
  --report "$T31_TMP_A/report.md"
uv run --extra exact python .timeloop/runs/t31_base19_bad_image_projection_independent.py \
  --root . --t31-evidence "$T31_TMP_A/evidence.json" \
  --t31-certificate "$T31_TMP_A/certificate.json" \
  --output "$T31_TMP_A/independent.json"
uv run --extra exact python .timeloop/runs/t31_base19_bad_image_projection.py \
  --evidence "$T31_TMP_B/evidence.json" \
  --certificate "$T31_TMP_B/certificate.json" \
  --report "$T31_TMP_B/report.md"
uv run --extra exact python .timeloop/runs/t31_base19_bad_image_projection_independent.py \
  --root . --t31-evidence "$T31_TMP_B/evidence.json" \
  --t31-certificate "$T31_TMP_B/certificate.json" \
  --output "$T31_TMP_B/independent.json"
diff -rq "$T31_TMP_A" "$T31_TMP_B"
```

Expected: both primary exits are zero, both independent exits are zero, and
`diff` reports no differences. If any command returns STOP, end T31 without
copying outputs into the repository.

- [ ] **Step 4: Promote exact bytes and rerun durable tests**

After byte agreement, use `cp` for the four already verified files; do not
rerun with durable output paths:

```bash
cp "$T31_TMP_A/evidence.json" \
  .timeloop/runs/t31_base19_bad_image_projection.json
cp "$T31_TMP_A/certificate.json" \
  .timeloop/runs/t31_base19_bad_image_projection_certificate.json
cp "$T31_TMP_A/independent.json" \
  .timeloop/runs/t31_base19_bad_image_projection_independent.json
cp "$T31_TMP_A/report.md" \
  .timeloop/runs/t31_base19_bad_image_projection_report.md
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q
```

Expected: all focused tests pass.

- [ ] **Step 5: Audit hashes, scope, and commit artifacts**

```bash
shasum -a 256 \
  publication/base19-radial/preprint.zip \
  .timeloop/runs/t29_base19_reachability_separator.json \
  .timeloop/runs/t29_base19_reachability_separator_trace.json \
  .timeloop/runs/t29_base19_reachability_separator_dataset.json \
  .timeloop/runs/t29_base19_reachability_separator_certificate.json \
  .timeloop/runs/t29_base19_reachability_separator_independent.json \
  .timeloop/runs/t30_base19_exact_image_refinement.json \
  .timeloop/runs/t30_base19_exact_image_refinement_certificate.json \
  .timeloop/runs/t30_base19_exact_image_refinement_independent.json \
  .timeloop/runs/t30_base19_exact_image_refinement_report.md \
  .timeloop/runs/t31_base19_bad_image_projection.json \
  .timeloop/runs/t31_base19_bad_image_projection_certificate.json \
  .timeloop/runs/t31_base19_bad_image_projection_independent.json \
  .timeloop/runs/t31_base19_bad_image_projection_report.md
git diff --check
git add .timeloop/runs/t31_base19_bad_image_projection.json \
  .timeloop/runs/t31_base19_bad_image_projection_certificate.json \
  .timeloop/runs/t31_base19_bad_image_projection_independent.json \
  .timeloop/runs/t31_base19_bad_image_projection_report.md \
  .timeloop/tests/test_lychrel_bad_image_projection.py
git diff --cached --name-only
git commit -m "exp: certify base19 bad-image projection"
```

Expected: protected hashes equal Global Constraints and the staged list contains
only the five Task 6 paths.

### Task 7: Adjacent regression, full assurance, and bounded conclusion

**Files:**

- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `docs/superpowers/plans/2026-08-10-base19-bad-image-projection.md`

**Interfaces:**

- Consumes the four durable T31 artifacts and all prior frozen evidence.
- Produces the exact T31 notebook boundary and execution record; no new claim.

- [ ] **Step 1: Run focused T27--T31 regression**

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_invariant_lift.py \
  .timeloop/tests/test_lychrel_quotient_automaton.py \
  .timeloop/tests/test_lychrel_reachability_separator.py \
  .timeloop/tests/test_lychrel_exact_image_refinement.py \
  .timeloop/tests/test_lychrel_bad_image_projection.py -q
```

Expected: zero failures.

- [ ] **Step 2: Run the complete Timeloop suite and lint**

```bash
uv run --extra exact --extra dev pytest .timeloop/tests -q
uv run --extra exact --extra dev ruff check .timeloop
git diff --check
```

Expected: zero pytest failures and zero Ruff errors.

- [ ] **Step 3: Reproduce artifacts once more and record raw hashes**

Run the complete temporary primary/independent pipeline from Task 6, compare all
four temporary files byte-for-byte with the durable files, then run the Task 6
hash command. Record exact test counts, durations, T31 status, predicate text,
selected projection origins, counterexample count, byte counts, and four T31
raw hashes in this plan's `Execution outcome` section.

- [ ] **Step 4: Append only the achieved T31 boundary to the notebook**

Add one `## T31 STATUS` section to `.timeloop/notebook/lychrel-bases.md` stating:
the exact PASS or independently verified STOP status; the compact predicate if
one exists; 18-row coverage; exact implication and composition results; the
independent 77,824-input method; four artifact hashes; the claim boundary; and
the no-fallback stop rule. Do not restate T27--T30 or propose T32.

- [ ] **Step 5: Final protected-scope audit and documentation commit**

```bash
git status --short
git diff --check
shasum -a 256 publication/base19-radial/preprint.zip
git add .timeloop/notebook/lychrel-bases.md \
  docs/superpowers/plans/2026-08-10-base19-bad-image-projection.md
git diff --cached --name-only
git commit -m "docs: record base19 bad-image projection outcome"
```

Expected: the ZIP hash is the protected value, exactly the notebook and plan are
staged, and all pre-existing publication, notebook, `.DS_Store`, and Timeloop
ledger/pool/exam changes remain unstaged and untouched.

## Execution handoff

Execute inline with `superpowers:executing-plans`, in task order, with the
milestone stops in Tasks 3 and 5. Do not dispatch subagents. A mathematical STOP
is a completed T31 outcome; it does not authorize an alternative experiment.
