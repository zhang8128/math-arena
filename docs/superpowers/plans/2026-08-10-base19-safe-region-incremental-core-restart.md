# Base-19 Safe-Region Incremental-Core Restart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace T33 Task 4's pathological complete-pool named-core query with an exact, countermodel-guided search that never submits more than six atoms and terminates within 153 seed pairs and 2,000 distinct conjunctions.

**Architecture:** Keep certificate grammar and finite-domain helpers in `lychrel_safe_region_cover.py`, implement the bounded search and exact Z3 oracle in the T33 runner, and replay the temporary transcript in the isolated standard-library checker. A global query cache records each distinct conjunction once, while pair-local visit traces preserve deterministic branch order and permit independent counter/count replay.

**Tech Stack:** Python 3.13 standard library, `z3-solver` 5.x through the repository's `exact` extra, `pytest`, and Ruff.

## Global Constraints

- Execute inline on `main`; do not create a worktree and do not dispatch subagents.
- Preserve every pre-existing user change. Never stage or modify publication paths, unrelated notebooks, `.DS_Store`, `.timeloop/exam/results.jsonl`, `.timeloop/ledger.md`, or `.timeloop/pool.jsonl`.
- `publication/base19-radial/preprint.zip` must retain SHA-256 `e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33`.
- The existing uncommitted Task 4 edits in `.timeloop/runs/t33_base19_safe_region_cover.py` and `.timeloop/tests/test_lychrel_safe_region_cover.py` belong to this experiment and may be replaced in place; do not revert them with destructive Git commands.
- Bind the approved restart design SHA-256 `10feaf957e889ca33b9f06441f88258179e2674e13248f72355adcd629b9c854` in the primary and isolated milestone payloads.
- Every solver conjunction contains zero through six canonical pool atoms. Pair 154 and distinct conjunction 2,001 are structurally unreachable.
- `SAT` and `UNSAT` are mathematical results. `UNKNOWN`, interruption, timeout, or resource exhaustion never imply either result.
- A Task 4 status other than `PASS` ends T33 immediately. Even after `PASS`, this restart plan does not begin Tasks 5--8 without a new approval.
- Task 4 writes no repository evidence artifact or notebook conclusion.
- Do not begin lower-layer extension, symbolic base lifting, base comparison, topology scans, publication work, or Lean work.

---

## File Structure

- Modify `.timeloop/lib/lychrel_safe_region_cover.py`: strict transcript and acquisition-provenance dataclasses, payload serialization, and parser support.
- Modify `.timeloop/runs/t33_base19_safe_region_cover.py`: bounded countermodel-guided engine, exact query oracle, candidate gate, result schema, and CLI orchestration.
- Modify `.timeloop/runs/t33_base19_safe_region_cover_independent.py`: isolated v2 milestone parser, transcript replay, counter reconstruction, and final exhaustive check.
- Modify `.timeloop/tests/test_lychrel_safe_region_cover.py`: synthetic TDD coverage, primary repository fixtures, isolated corruption tests, and conditional frozen outcome assertions.
- Create no other source, artifact, notebook, or publication file.

---

### Task 1: Define the transcript and bounded search engine

**Files:**

- Modify: `.timeloop/lib/lychrel_safe_region_cover.py:310-420,630-725`
- Modify: `.timeloop/runs/t33_base19_safe_region_cover.py:86-215,529-835`
- Modify: `.timeloop/tests/test_lychrel_safe_region_cover.py:180-340`

**Interfaces:**

- Consumes: `ProjectionAtom`, `SemanticWitness`, `SeedPair`, `CoreReductionStep`, `canonical_bytes()`, and `generate_seed_pair_pool()`.
- Produces: `RegionQueryRecord`, `SearchVisit`, `SeedPairSearchTrace`, `IncrementalSearchTranscript`, the revised `SafeRegionProvenance` fields `core_candidate`, `core_candidate_sha256`, and `acquisition_query_sha256`, plus `RegionSearchBudget`, `CandidateDecision`, `PairSearchResult`, `branch_atoms()`, `countermodel_guided_search()`, and `FirstSafeRegionResult.search_transcript`.

- [ ] **Step 1: Write failing strict-schema tests**

Add imports for the four transcript types and their strict parser functions, then replace named-core fixture fields with acquisition-core fields. Add tests with this shape:

```python
def semantic_witness_for_row(row: tuple[int, ...]) -> SemanticWitness:
    return SemanticWitness(
        input_state=tuple(
            sorted((f"input:{name}", value) for name, value in zip(P30_VARIABLES, row, strict=True))
        ),
        output_state=(("output:D0", 0),),
        local_state=(),
    )


def test_incremental_transcript_rejects_large_or_mutated_queries() -> None:
    atoms = tuple(
        ProjectionAtom("eq", ((f"L{index}", 1),), 0)
        for index in range(6)
    )
    record = RegionQueryRecord.from_query(
        atoms,
        status="SAT",
        witness=semantic_witness_for_row((0,) * len(P30_VARIABLES)),
        equation_residuals=(0,) * 12,
        q0_holds=False,
    )
    payload = record.to_payload()
    payload["conjunction_sha256"] = "0" * 64
    atom_by_sha256 = {
        hashlib.sha256(canonical_bytes(atom)).hexdigest(): atom for atom in atoms
    }
    with pytest.raises(ValueError, match="conjunction digest"):
        parse_region_query_record(payload, atom_by_sha256)
    with pytest.raises(ValueError, match="at most six"):
        RegionQueryRecord.from_query(atoms + (ProjectionAtom("eq", (("R5", 1),), 0),), status="UNSAT")
```

Also assert:

- `SAT` requires a witness, 12 zero residuals, and `q0_holds is False`;
- `UNSAT` forbids witness/replay fields;
- query atoms are canonical, distinct, and may be empty;
- visit digests resolve to a query record and to the pair's regenerated pool;
- exactly one visit has `fresh_query=True` for each global query record;
- pair traces are lexicographically ordered and match `seed_pair_count`;
- unique query digests equal `region_test_count`; and
- a provenance clause is a subset of its `core_candidate`, whose digest matches its acquisition query.

- [ ] **Step 2: Run the new schema tests and verify RED**

Run:

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q \
  -k 'incremental_transcript or acquisition_provenance'
```

Expected: collection or assertion failure because the transcript types and revised provenance fields do not exist.

- [ ] **Step 3: Implement the strict dataclasses and payload parsers**

Import `SemanticWitness` and add these exact public shapes:

```python
@dataclass(frozen=True)
class RegionQueryRecord:
    conjunction: tuple[ProjectionAtom, ...]
    conjunction_sha256: str
    status: str
    witness: SemanticWitness | None
    equation_residuals: tuple[int, ...]
    q0_holds: bool | None

    @classmethod
    def from_query(
        cls,
        conjunction: tuple[ProjectionAtom, ...],
        *,
        status: str,
        witness: SemanticWitness | None = None,
        equation_residuals: tuple[int, ...] = (),
        q0_holds: bool | None = None,
    ) -> "RegionQueryRecord":
        canonical = tuple(sorted(conjunction, key=canonical_bytes))
        if canonical != conjunction or len(set(canonical)) != len(canonical):
            raise ValueError("query conjunction must be canonical and distinct")
        if len(canonical) > 6:
            raise ValueError("query conjunction may contain at most six atoms")
        digest = hashlib.sha256(
            canonical_bytes([atom.to_payload() for atom in canonical])
        ).hexdigest()
        return cls(
            canonical,
            digest,
            status,
            witness,
            equation_residuals,
            q0_holds,
        )


@dataclass(frozen=True)
class SearchVisit:
    purpose: str
    parent_sha256: str | None
    query_sha256: str
    fresh_query: bool
    violated_atom_sha256s: tuple[str, ...]
    branch_atom_sha256s: tuple[str, ...]


@dataclass(frozen=True)
class SeedPairSearchTrace:
    seed_pair: SeedPair
    pool_size: int
    pool_sha256: str
    visits: tuple[SearchVisit, ...]


@dataclass(frozen=True)
class IncrementalSearchTranscript:
    queries: tuple[RegionQueryRecord, ...]
    pairs: tuple[SeedPairSearchTrace, ...]
```

`RegionQueryRecord.from_query()` must reject noncanonical input rather than silently reorder it, reject more than six atoms, hash `canonical_bytes([atom.to_payload() for atom in canonical])`, and enforce the SAT/UNSAT field union. Its temporary JSON payload stores the ordered SHA-256 of each atom rather than repeating atom payloads. Serialize witnesses with `SemanticWitness.to_payload()`.

`SearchVisit.purpose` is exactly one of `ROOT`, `SEARCH`, `REDUCTION`, or `ACCEPTANCE_REPLAY`. Pair traces include every solver submission, including cached deletion trials and the mandatory fresh acceptance replay. Only the first global submission of a conjunction has `fresh_query=True`; acceptance replay bypasses the result cache but remains `fresh_query=False` and does not increment the distinct-region counter.

Revise `SafeRegionProvenance` by replacing `named_core` and `named_core_sha256` with:

```python
core_candidate: tuple[ProjectionAtom, ...]
core_candidate_sha256: str
acquisition_query_sha256: str
```

Require one through six canonical core atoms, membership in the regenerated pool, the clause as a subset, and equality between the acquisition digest and the candidate digest. Keep the minimization trace and every diversity/compactness field unchanged.

In the runner, define the engine result unions exactly once and use them in every later task:

```python
@dataclass(frozen=True)
class CandidateDecision:
    status: str
    provenance: SafeRegionProvenance | None
    detail: str | None


@dataclass(frozen=True)
class PairSearchResult:
    status: str
    provenance: SafeRegionProvenance | None
    trace: SeedPairSearchTrace
    stop_detail: str | None


class SearchTerminated(EvidenceError):
    def __init__(self, status: str, detail: str | None) -> None:
        if status != "UNKNOWN":
            raise ValueError("unsupported terminal search status")
        if not detail:
            raise ValueError("terminal search detail must be nonempty")
        super().__init__(detail)
        self.status = status
        self.detail = detail


class PairBudgetExhausted(EvidenceError):
    """The next canonical seed pair is outside the frozen pair budget."""


class RegionBudgetExhausted(EvidenceError):
    """The next distinct conjunction is outside the frozen region budget."""
```

`CandidateDecision.status` is one of `PASS`, `REJECT`, or `UNKNOWN`; only PASS carries provenance and only non-PASS carries detail. `PairSearchResult.status` is one of `PASS`, `EXHAUSTED`, or `UNKNOWN`; only PASS carries provenance, while UNKNOWN carries stop detail. Independent disagreement is decided only by outer orchestration after it can serialize the complete transcript.

Add `search_transcript: IncrementalSearchTranscript` to `FirstSafeRegionResult`. Every PASS and STOP result must carry a transcript whose pair/query counts equal the result counters; STOP still carries no clause or provenance.

Add and export strict `parse_region_query_record(value, atom_by_sha256)`, `parse_search_visit()`, `parse_seed_pair_search_trace()`, and `parse_incremental_search_transcript()` functions. `parse_incremental_search_transcript()` first parses pair traces, regenerates their seed pools, builds one collision-checked digest-to-atom map, and passes that map into each query-record parser. Each parser requires an exact key set and delegates to the dataclass constructor so parsed and directly constructed values share one validator.

Expose `evaluate_safe_atom(atom, assignment)` as the validated one-atom wrapper around the existing private evaluator. Add `canonical_conjunction(atoms, *, allow_empty, maximum)` to reject duplicates/out-of-grammar atoms and return canonical order, and `canonical_union(conjunction, atom)` to add exactly one absent atom through that validator.

- [ ] **Step 4: Run focused schema tests and the pre-existing certificate tests**

Run:

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q \
  -k 'certificate or parser or provenance or incremental_transcript'
```

Expected: all selected tests pass; old named-core fixtures have been fully migrated rather than accepted under both schemas.

- [ ] **Step 5: Run the schema checkpoint before adding the engine**

Run:

```bash
uv run --extra dev ruff check \
  .timeloop/lib/lychrel_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git diff --check
```

Do not stage yet. The existing uncommitted tests import the uncommitted runner scaffold, so the transcript and engine must form one atomic, independently collectable checkpoint.

- [ ] **Step 6: Replace monolithic-core tests with synthetic search tests**

Delete tests that require `named_seed_pair_core()`. Keep deletion minimization tests and add a finite synthetic oracle:

```python
def finite_oracle(models: tuple[dict[str, int], ...]):
    def decide(atoms: tuple[ProjectionAtom, ...]) -> RegionQueryRecord:
        for model in models:
            if all(evaluate_safe_atom(atom, model) for atom in atoms):
                row = tuple(model[name] for name in P30_VARIABLES)
                return RegionQueryRecord.from_query(
                    atoms,
                    status="SAT",
                    witness=semantic_witness_for_row(row),
                    equation_residuals=(0,) * 12,
                    q0_holds=False,
                )
        return RegionQueryRecord.from_query(atoms, status="UNSAT")
    return decide
```

Use a three-atom pool and finite models to prove:

- the search finds and deletion-minimizes a two-atom UNSAT conjunction;
- each SAT node branches only on atoms its model violates;
- every UNSAT extension in the synthetic powerset contains one of those violated atoms;
- a SAT witness that violates no pool atom closes the pair constructively;
- no queried conjunction exceeds a configurable test depth of two;
- global cache reuse sets only the first matching visit to `fresh_query=True`;
- `region_test_count` counts unique query digests, while `seed_pair_count` counts entered pairs;
- region 2,001 and pair 154 are never invoked; and
- `UNKNOWN` raises `EvidenceError` and becomes an immediate `UNKNOWN` result at the orchestration boundary.

- [ ] **Step 7: Run the engine tests and verify RED**

Run:

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q \
  -k 'countermodel_guided or branch_atoms or region_budget or deletion_minimization'
```

Expected: failures because the old engine still calls the removed complete-pool named-core function.

- [ ] **Step 8: Implement exact counter and branch primitives**

Give `RegionSearchBudget` these responsibilities only:

```python
def enter_pair(self) -> None:
    if self.seed_pair_count >= self.pair_limit:
        raise PairBudgetExhausted
    self.seed_pair_count += 1

def register_query(self, query_sha256: str) -> bool:
    if query_sha256 in self._query_digests:
        return False
    if self.region_test_count >= self.region_limit:
        raise RegionBudgetExhausted
    self._query_digests.add(query_sha256)
    self.region_test_count += 1
    return True
```

Implement `branch_atoms()` to compute the violated pool subset from the replayed input assignment and sort it by the approved four keys:

```python
(
    -excluded_prior_sat_model_count,
    -promoted_row_coverage,
    -singleton_bounded_extent,
    canonical_bytes(atom),
)
```

Hash atoms with `sha256(canonical_bytes(atom)).hexdigest()` everywhere; never hash `repr()` or solver expressions.

Maintain prior SAT models as distinct canonical input-assignment tuples in first-seen order. If two query records minimize to the same input row, that row contributes once to `excluded_prior_sat_model_count`; the independent checker must apply the same deduplication rule.

Implement branch scoring directly from replayed input assignments:

```python
def branch_atoms(
    record: RegionQueryRecord,
    pool: tuple[ProjectionAtom, ...],
    prior_sat_inputs: tuple[tuple[tuple[str, int], ...], ...],
    promoted_assignments: tuple[dict[str, int], ...],
) -> tuple[tuple[ProjectionAtom, ...], tuple[ProjectionAtom, ...]]:
    if record.status != "SAT" or record.witness is None:
        raise ValueError("branching requires a SAT record")
    assignment = input_assignment_from_witness(record.witness)
    violated = tuple(
        atom for atom in pool if not evaluate_safe_atom(atom, assignment)
    )

    def key(atom: ProjectionAtom) -> tuple[object, ...]:
        excluded = sum(
            not evaluate_safe_atom(atom, dict(prior))
            for prior in prior_sat_inputs
        )
        coverage = sum(
            evaluate_safe_atom(atom, promoted)
            for promoted in promoted_assignments
        )
        extent = clause_extent(SafeRegionClause((atom,)))
        return (-excluded, -coverage, -extent, canonical_bytes(atom))

    return violated, tuple(sorted(violated, key=key))
```

Add `input_assignment_from_witness()` to strip the `input:` prefix, require exactly `P30_VARIABLES`, and return a canonical dictionary. Implement `countermodel_guided_search(seed_pair, pool, promoted_assignments, budget, query_cache, query_exact, verify_candidate, *, max_atoms=6) -> PairSearchResult`; `query_exact` accepts one canonical conjunction, and `verify_candidate` accepts `(minimized, core_candidate, reduction_trace, acquisition_record, fresh_acceptance)` and returns `CandidateDecision`.

Inside `countermodel_guided_search()`, define `submit(conjunction, parent, purpose, force_fresh=False)`. It validates/hashes the conjunction, registers a distinct digest unless cached, invokes `query_exact` when fresh or forced, requires a forced replay to agree with the cached mathematical status, computes SAT violation/branch metadata, appends one purpose-tagged visit, and returns the immutable record. Define `status_for()` in terms of `submit(..., purpose="REDUCTION")`. Pass a closure using `submit(..., purpose="ACCEPTANCE_REPLAY", force_fresh=True)` to the candidate verifier.

- [ ] **Step 9: Implement depth-first countermodel-guided search**

Replace `named_seed_pair_core()` with an injected-oracle engine whose recursive node function has this boundary:

```python
def visit(
    conjunction: tuple[ProjectionAtom, ...],
    parent_sha256: str | None,
) -> SafeRegionProvenance | None:
    if len(conjunction) > max_atoms:
        raise AssertionError("search attempted more than six atoms")
    record, fresh = query_cached(conjunction)
    if record.status == "UNSAT":
        minimized, reduction = deletion_minimize_core(conjunction, status_for)
        decision = verify_candidate(
            minimized,
            conjunction,
            reduction,
            record,
            fresh_acceptance,
        )
        if decision.status == "PASS":
            return decision.provenance
        if decision.status == "REJECT":
            return None
        raise SearchTerminated(decision.status, decision.detail)
    violated, branches = branch_atoms(record, pool, prior_sat_models, promoted_rows)
    append_visit(record, parent_sha256, fresh, violated, branches)
    if not violated or len(conjunction) == max_atoms:
        return None
    for atom in branches:
        found = visit(canonical_union(conjunction, atom), record.conjunction_sha256)
        if found is not None:
            return found
    return None
```

The real implementation must append the UNSAT visit before minimization, count deletion-trial conjunctions through the same global cache, continue after a candidate rejected only by finite acceptance gates, and immediately propagate `UNKNOWN` or independent disagreement.

Remove every `assert_and_track`, `unsat_core`, and complete-pool query from Task 4. Add an assertion test using `inspect.getsource()` that the production search path contains none of those calls.

- [ ] **Step 10: Run focused schema/engine tests and Ruff**

Run:

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q \
  -k 'countermodel_guided or branch_atoms or region_budget or deletion_minimization'
uv run --extra dev ruff check \
  .timeloop/lib/lychrel_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git diff --check
```

Expected: all selected tests pass and Ruff reports no errors.

- [ ] **Step 11: Commit the atomic transcript/engine checkpoint**

Verify the ZIP hash and cached file list, then commit the library, runner, and tests together:

```bash
git add -- \
  .timeloop/lib/lychrel_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git commit -m "feat: search base19 cores by exact countermodels"
```

---

### Task 2: Integrate the exact Z3 oracle and milestone gate

**Files:**

- Modify: `.timeloop/runs/t33_base19_safe_region_cover.py:218-530,586-850`
- Modify: `.timeloop/tests/test_lychrel_safe_region_cover.py:330-590,630-665`

**Interfaces:**

- Consumes: Task 1's injected search engine and provenance/transcript schema.
- Produces: `query_safe_conjunction()`, the concrete `CandidateDecision` constructor path in `verify_region_candidate()`, revised `find_first_safe_region()`, and milestone schema `t33-base19-safe-region-milestone-v2`.

- [ ] **Step 1: Write failing exact-oracle and gate tests**

Add tests that load frozen T33 inputs once per process and assert:

```python
def test_exact_empty_conjunction_returns_replayed_sat_record() -> None:
    record = query_safe_conjunction(load_t33_inputs(ROOT), ())
    assert record.status == "SAT"
    assert record.witness is not None
    assert record.equation_residuals == (0,) * 12
    assert record.q0_holds is False


def test_exact_oracle_rejects_more_than_six_atoms() -> None:
    atoms = tuple(
        sorted(
            (
                ProjectionAtom("le", ((name, 1),), 0)
                for name in P30_VARIABLES[:7]
            ),
            key=canonical_bytes,
        )
    )
    with pytest.raises(ValueError, match="at most six"):
        query_safe_conjunction(load_t33_inputs(ROOT), atoms)
```

Also test that:

- minimized SAT witnesses are canonical and replay through all 12 equations;
- `verify_region_candidate()` rejects atom count, seed coverage, promoted coverage, extent, and compactness independently;
- fresh primary `UNSAT` is required even when the cached acquisition query was `UNSAT`;
- independent rejection maps to `INDEPENDENT_DISAGREEMENT`;
- the result carries transcript/counters on both PASS and STOP;
- the v2 payload binds both original T33 design and restart-design digests; and
- `_load_t33_inputs_uncached()` rejects a copied restart design with one mutated byte.

- [ ] **Step 2: Run exact integration tests and verify RED**

Run:

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q \
  -k 'exact_empty_conjunction or exact_oracle or candidate_gate or restart_design'
```

Expected: failures because the old status-only oracle and v1 payload remain.

- [ ] **Step 3: Return full replay records from the exact oracle**

Replace `_safe_atoms_status()` with:

```python
def query_safe_conjunction(
    inputs: T33Inputs,
    atoms: tuple[ProjectionAtom, ...],
) -> RegionQueryRecord:
    canonical = canonical_conjunction(atoms, allow_empty=True, maximum=6)
    relation, solver = build_bad_input_solver(inputs)
    solver.add(*(z3_safe_atom(relation, atom) for atom in canonical))
    status = _solver_status(relation, solver, "incremental safe-region query")
    if status == "UNSAT":
        return RegionQueryRecord.from_query(canonical, status="UNSAT")
    witness = _semantic_witness(
        relation,
        _canonical_assignment(relation, solver, "incremental countermodel"),
    )
    replay = replay_bad_image_witness(inputs.t32_inputs.t31_inputs, witness)
    if replay.equation_residuals != (0,) * 12 or replay.q0_holds:
        raise EvidenceError("incremental countermodel failed exact replay")
    return RegionQueryRecord.from_query(
        canonical,
        status="SAT",
        witness=witness,
        equation_residuals=replay.equation_residuals,
        q0_holds=replay.q0_holds,
    )
```

Do not set a timeout and do not retain a solver object in the global cache; cache only the immutable record.

- [ ] **Step 4: Implement the unchanged candidate acceptance gate**

Add `verify_region_candidate()` as the only constructor path for a primary-accepted `SafeRegionProvenance`. It must recompute promoted indices, bounded extent, predicate/table bytes, invoke the engine-supplied `fresh_acceptance(clause.atoms)` closure, require that fresh record to be `UNSAT`, construct acquisition provenance, and return one of these three concrete records:

```python
CandidateDecision("PASS", provenance, None)
CandidateDecision("REJECT", None, "finite gate detail")
CandidateDecision("UNKNOWN", None, "exact solver detail")
```

Finite rejection resumes the bounded DFS and `UNKNOWN` terminates it. After a pair returns primary PASS, `find_first_safe_region()` must assemble the complete transcript snapshot and call `_run_independent_milestone(inputs, clause, provenance, transcript)`. Isolated PASS produces final PASS; isolated rejection produces `INDEPENDENT_DISAGREEMENT`. Until Task 3 upgrades the checker to v2, orchestration tests must monkeypatch `_run_independent_milestone()` with explicit PASS and REJECT readbacks; do not run the repository milestone against the v1 checker.

- [ ] **Step 5: Bind the restart design and v2 milestone schema**

Add:

```python
T33_RESTART_DESIGN_SHA256 = "10feaf957e889ca33b9f06441f88258179e2674e13248f72355adcd629b9c854"
```

Bind `docs/superpowers/specs/2026-08-10-base19-safe-region-incremental-core-restart-design.md` during input loading, add the digest to `T33Inputs`, and serialize:

Add `"schema": "t33-base19-safe-region-milestone-v2"`, `"t33_restart_design_sha256": inputs.t33_restart_design_sha256`, and `"search_transcript": result.search_transcript.to_payload()` to the existing source-digest, status, counter, clause, provenance, and verification fields.

STOP payloads must include status, exact counters, nonempty detail, and transcript, but no clause or provenance. PASS payloads include the same fields plus clause/provenance and the fresh primary/isolated statuses.

- [ ] **Step 6: Run primary integration tests and commit**

Run:

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q \
  -k 'inputs or replay or exact_oracle or candidate or budget or first_safe'
uv run --extra dev ruff check \
  .timeloop/lib/lychrel_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git diff --check
```

Verify the ZIP hash, stage only runner/tests, inspect the cached patch, and commit:

```bash
git add -- \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git commit -m "feat: bind base19 incremental core milestone"
```

---

### Task 3: Independently replay the incremental transcript

**Files:**

- Modify: `.timeloop/runs/t33_base19_safe_region_cover_independent.py:680-1005`
- Modify: `.timeloop/tests/test_lychrel_safe_region_cover.py:430-590`

**Interfaces:**

- Consumes: the v2 temporary payload, raw T27--T30 sources, and no repository imports.
- Produces: isolated transcript/counter replay and `t33-base19-safe-region-milestone-independent-v2`.

- [ ] **Step 1: Write failing isolated corruption tests**

Extend the milestone fixture to v2 using one exact replayed SAT root record followed by a deliberately false UNSAT acquisition record. Name it `structurally_valid_sat_prefix_payload`: its SAT prefix passes structural, equation, `q0`, violation-set, and branch-order replay, while the unchanged payload is rejected at the claimed UNSAT acquisition. Add one mutation per prefix proof boundary and require that the targeted transcript error occurs before the known acquisition rejection. Assert the root branch list contains at least two atom digests before using the reversal mutation.

```python
@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (lambda p: p["search_transcript"]["queries"][0].__setitem__("conjunction_sha256", "0" * 64), "query digest"),
        (lambda p: p["search_transcript"]["pairs"][0]["visits"][0].__setitem__("fresh_query", False), "fresh-query"),
        (lambda p: p["search_transcript"]["pairs"][0]["visits"][0]["branch_atom_sha256s"].reverse(), "branch order"),
        (lambda p: p.__setitem__("region_test_count", p["region_test_count"] + 1), "region count"),
    ),
)
def test_independent_rejects_corrupted_incremental_transcript(
    structurally_valid_sat_prefix_payload, mutate, message, tmp_path
) -> None:
    payload = copy.deepcopy(structurally_valid_sat_prefix_payload)
    mutate(payload)
    completed = run_independent_payload(payload, tmp_path)
    assert completed.returncode != 0
    assert message in completed.stderr
```

Import `copy` and implement `run_independent_payload(payload, tmp_path)` by writing `canonical_bytes(payload) + b"\n"` with `Path.write_bytes()` to `tmp_path / "candidate.json"`, then passing that path to the existing `run_independent_milestone()` helper.

Retain the existing bad-successor, mutated-equation, import-isolation, pool-regeneration, reduction, extent, and compactness tests.

- [ ] **Step 2: Run isolated tests and verify RED**

Run:

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q \
  -k 'independent and (transcript or milestone or successor or equation)'
```

Expected: v2 payloads are rejected because the isolated checker still requires v1 named-core provenance.

- [ ] **Step 3: Parse and replay every query record without repository imports**

Update the checker constants with the restart-design digest and require schema v2. Implement strict local parsers for query records, visits, pair traces, witnesses, and revised provenance.

For each pair trace:

1. regenerate the canonical seed pool from its promoted rows;
2. resolve visit atom digests against that pool and global query records;
3. reconstruct the full witness assignment from input/output/local sections;
4. require all 12 equation residuals to be zero and `q0` to be false;
5. evaluate the conjunction and every pool atom on the input row;
6. recompute violated atom digests and the four-key branch order from prior distinct pair SAT inputs;
7. verify purpose tags, parent links, deterministic depth-first visit order, deletion submissions, and the fresh acceptance replay;
8. ensure one `fresh_query` per distinct global digest; and
9. recompute pair and unique-region counters exactly.

For each claimed `UNSAT` record, call the existing standard-library `first_bad_solution()` with that record's conjunction and reject if it finds a model. Replay the accepted acquisition and deletion trace, then retain the existing exhaustive 77,824-input final clause check.

- [ ] **Step 4: Emit the v2 independent result and tighten primary readback**

Return:

```python
{
    "schema": "t33-base19-safe-region-milestone-independent-v2",
    "status": "PASS",
    "repository_imports": [],
    "seed_pair_count": seed_pair_count,
    "region_test_count": region_test_count,
    "query_record_count": len(unique_query_digests),
    "transcript_status": "PASS",
    "safety_status": "UNSAT",
    "enumerated_input_count": 77_824,
    "seed_indices": list(seed_indices),
    "promoted_indices": list(promoted_indices),
    "bounded_extent": extent,
    "predicate_bytes": predicate_bytes,
    "covered_table_bytes": table_bytes,
}
```

Require every field in `_run_independent_milestone()`; a missing or mismatched counter is `INDEPENDENT_DISAGREEMENT`.

- [ ] **Step 5: Prove isolation, run tests/lint, and commit**

Run:

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q \
  -k 'independent or transcript or milestone'
uv run --extra dev ruff check \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover_independent.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git diff --check
```

The isolation test must execute the checker with `python -I`, inspect its AST imports, and assert `repository_imports == []`.

Verify the ZIP hash, stage only the independent checker/tests, inspect the cached patch, and commit:

```bash
git add -- \
  .timeloop/runs/t33_base19_safe_region_cover_independent.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git commit -m "feat: independently replay base19 incremental cores"
```

---

### Task 4: Run the repository milestone and enforce the hard gate

**Files:**

- Modify on PASS only: `.timeloop/tests/test_lychrel_safe_region_cover.py:630-665`
- Modify on exact STOP only if an assertion is required: `.timeloop/tests/test_lychrel_safe_region_cover.py:630-665`
- Create: none

**Interfaces:**

- Consumes: committed Tasks 1--3.
- Produces: one exact Task 4 terminal status and, only on PASS, frozen repository assertions for the returned mathematical facts.

- [ ] **Step 1: Verify the pre-run boundary**

Run:

```bash
git status --short --branch
shasum -a 256 publication/base19-radial/preprint.zip
uv run --extra dev ruff check \
  .timeloop/lib/lychrel_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover_independent.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q \
  -k 'not repository_first_safe_region'
```

Expected: ZIP hash exact, Ruff clean, selected tests pass, and only the known protected user changes remain unstaged.

- [ ] **Step 2: Run the revised repository milestone exactly once**

Run:

```bash
uv run --extra exact python \
  .timeloop/runs/t33_base19_safe_region_cover.py milestone
```

Do not run another search in parallel. Capture the tool's stdout as the sole first-run result. Confirm:

- `1 <= seed_pair_count <= 153`;
- `1 <= region_test_count <= 2000`;
- every transcript conjunction has at most six atoms;
- unique query digests equal `region_test_count`; and
- status is exactly one of `PASS`, `NO_SAFE_REGION`, `PAIR_BUDGET_EXHAUSTED`, `REGION_BUDGET_EXHAUSTED`, `UNKNOWN`, or `INDEPENDENT_DISAGREEMENT`.

- [ ] **Step 3A: If status is PASS, freeze only returned mathematical facts**

Replace the broad repository test with direct Python literals copied from the first canonical JSON output. Assert the exact clause payload, seed indices, atom count, promoted indices, bounded extent, pool digest, core-candidate digest, pair count, region count, primary `UNSAT`, and isolated `PASS`. The values cannot be stated before the experiment because discovering them is the milestone's purpose; once returned, copy the literal integers, tuples, dictionaries, and digests directly into the test without symbolic stand-ins. Do not freeze timing, paths, or incidental solver statistics. Then run that exact repository test once.

- [ ] **Step 3B: If status is not PASS, verify the exact STOP and end T33**

Do not add a clause or provenance assertion. Re-run only as required to establish deterministic status, counters, and stop detail. If the second run differs, report `UNKNOWN` with the disagreement and do not create a durable result artifact. Do not execute any later task from the original T33 plan.

- [ ] **Step 4: Run final Task 4 verification**

Run:

```bash
uv run --extra exact --extra dev pytest \
  .timeloop/tests/test_lychrel_safe_region_cover.py -q \
  -k 'core or branch or budget or first_safe or milestone or independent'
uv run --extra dev ruff check \
  .timeloop/lib/lychrel_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover.py \
  .timeloop/runs/t33_base19_safe_region_cover_independent.py \
  .timeloop/tests/test_lychrel_safe_region_cover.py
git diff --check
shasum -a 256 publication/base19-radial/preprint.zip
```

Expected: all selected tests pass, Ruff and diff checks are clean, and the ZIP hash remains exact.

- [ ] **Step 5: Commit only conditional assertions and report the boundary**

If Task 4 changed the test file, stage only that file and inspect the cached patch:

```bash
git add -- .timeloop/tests/test_lychrel_safe_region_cover.py
git commit -m "exp: decide base19 incremental core milestone"
```

If no file changed, create no empty commit. Report the exact status, counters, clause/provenance hashes on PASS, or stop detail on non-PASS. Reconfirm that publication and all unrelated user changes were untouched. Stop and request approval before any Task 5--8 work from the original T33 plan.

---

## Plan Completion Gate

- [ ] Every requirement in the approved restart design maps to a task above.
- [ ] No production query contains more than six atoms.
- [ ] No complete-pool query, tracked assertion set, or Z3 unsat-core call remains in Task 4.
- [ ] Every SAT record has an exact replayed witness; every UNSAT record is independently decided.
- [ ] Transcript branch order, query deduplication, and both counters are independently reconstructed.
- [ ] The v2 payload binds the original T33 design and restart-design hashes.
- [ ] The repository milestone runs alone and exactly once before any deterministic STOP confirmation.
- [ ] Non-PASS status ends T33 without fallback; PASS still pauses before original Tasks 5--8.
- [ ] Only explicitly allowed files are staged in each commit.
- [ ] The protected ZIP hash remains exact.
