# T29 Base-19 Reachability Separator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Execute inline without subagents.

**Goal:** Reconstruct T28's complete layer-31 counterexample trace, determine
whether one compact frozen-language predicate separates the promoted dead
states from successor-bearing look-alikes and live controls, and independently
verify the exact achieved boundary.

**Architecture:** A small immutable library defines trace, dataset, predicate,
and certificate syntax. T28 gains a result-preserving trace-replay interface;
a new T29 runner builds the frozen dataset, synthesizes a lexicographically
minimal bounded DNF, and conditionally checks universal no-successor semantics.
An isolated standard-library checker independently replays finite separation
and the semantic SAT/UNSAT result.

**Tech Stack:** Python 3.13 via `uv`, immutable dataclasses, existing canonical
JSON types, `z3-solver` 5.x for primary synthesis and exact semantic checks,
Python standard-library constraint propagation/backtracking for independent
assurance, pytest 8.x, Ruff, SHA-256, and deterministic JSON/Markdown artifacts.

## Execution outcome (2026-08-09)

- Tasks 1--4 executed: T28 replay produced 221 exact counterexamples before
  candidate 222's depth failure; the frozen dataset has 12 positives, 221
  trace negatives, and six live controls; the deterministic pool has 83 atoms;
  and the finite optimum is one ten-atom conjunction.
- Task 5 semantic branch executed because finite synthesis passed. The exact
  12-equation query returned SAT, so the achieved status is
  `FINITE_SEPARATOR_PASS_SEMANTIC_STOP`; semantic UNSAT promotion was not
  applicable.
- Task 6 executed with an isolated standard-library checker. It replayed all
  239 finite classifications and the complete SAT witness, and mutation tests
  failed closed. The certificate was retained for the finite PASS.
- Task 7 durable artifacts and notebook boundary were completed. Primary
  evidence raw SHA-256 is
  `c1e3dc4bc4ab07207a6ab49d6a9c9fd86486013abeaf016b6ecd59c9755e1d32`;
  independent audit raw SHA-256 is
  `9f926208cc7416e24d811f6cd54485d19741b6f8ffe44f3b365b2f816e579644`.
- The semantic-UNSAT independent search branch and all lower-layer, other-base,
  topology, publication, and Lean branches were skipped as inapplicable or
  out of scope. The broader reachability-invariant target remains open.

## Global Constraints

- Work in `/Users/kairos/Projects/personal/math` inline without subagents.
- Preserve every existing user change and never stage publication paths,
  `.timeloop/exam/results.jsonl`, `.timeloop/ledger.md`, `.timeloop/pool.jsonl`,
  unrelated notebooks, or `.DS_Store` files.
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
  and raw T28 independent-audit SHA-256
  `7f095af25afc02ff48fe4d2ee53b4827ba99fa1548a5d970e475780fdaa1639e`.
- Preserve T28's durable JSON/Markdown bytes and its
  `decision_depth_exceeded` conclusion. A trace interface may not alter
  `build_layer31_milestone`, `build_primary`, or their existing outputs.
- Expect 221 exact counterexamples from iterations 1--221 and a depth failure
  while building candidate 222. Never equate terminal iteration with trace
  length.
- Freeze coefficients at `-3..3`, congruence moduli at `2..20`, at most three
  conjunctions, 12 atoms per conjunction, and 512 candidate atoms.
- Treat Prism and literature only as hypothesis provenance. Prism returned no
  usable artifact and supplies no mathematical premise.
- Fail closed on solver `UNKNOWN`, trace/digest disagreement, pool overflow,
  malformed syntax, missing live controls, a noncanonical witness, mutation
  survival, or primary/independent disagreement.
- A finite-separation PASS is not a reachability, inductive-invariant, or
  semantic dead-region theorem.
- Do not perform lower-layer extension, symbolic base lifting, base comparison,
  topology scans, publication changes, or Lean work in T29.

## File Map

- Create `.timeloop/lib/lychrel_reachability_separator.py` for immutable trace,
  dataset, finite predicate, witness, and certificate types plus evaluation.
- Modify `.timeloop/runs/t28_base19_tail_quotient.py` only to expose
  deterministic trace replay without changing existing results.
- Create `.timeloop/runs/t29_base19_reachability_separator.py` for frozen input
  loading, dataset construction, atom generation, DNF synthesis, semantic
  checking, evidence gating, CLI output, and report rendering.
- Create `.timeloop/runs/t29_base19_reachability_separator_independent.py` for
  isolated standard-library assurance.
- Create `.timeloop/tests/test_lychrel_reachability_separator.py` for all T29
  unit, integration, isolation, determinism, and mutation tests.
- Create durable T29 evidence, optional certificate, independent audit, and
  report only after the assurance checkpoint.
- Modify `.timeloop/notebook/lychrel-bases.md` and this plan only for the final
  achieved conclusion.

---

### Task 1: Immutable trace, dataset, and certificate language

**Files:**

- Create: `.timeloop/lib/lychrel_reachability_separator.py`
- Create: `.timeloop/tests/test_lychrel_reachability_separator.py`

**Interfaces:**

- Consumes `LinearAtom`, `Conjunction`, `LayerPredicate`, and `canonical_bytes`
  from `.timeloop/lib/lychrel_invariant_certificate.py`.
- Produces `TraceStep`, `CounterexampleTrace`, `SeparatorDataset`,
  `SemanticWitness`, `SeparatorCertificate`, `evaluate_predicate`,
  `finite_separation_failures`, `parse_counterexample_trace`, and
  `parse_separator_certificate`.

- [ ] **Step 1: Write strict syntax and evaluation tests**

  Add tests with the real 14-variable scope and small toy states:

  ```python
  def test_trace_distinguishes_terminal_iteration_from_counterexample_count() -> None:
      trace = CounterexampleTrace(
          schema="t29-base19-counterexample-trace-v1",
          variables=("x",),
          steps=(TraceStep(1, (("x", 0),), "DEAD", "dead_has_no_successor", 3, 1, 1),),
          terminal_iteration=2,
          stop_reason="decision_depth_exceeded",
      )
      assert len(trace.steps) == 1
      assert trace.terminal_iteration == 2

  def test_finite_failures_reject_live_control_absorption() -> None:
      predicate = LayerPredicate(31, ("x",), (Conjunction((unit_eq("x", 0),)),))
      dataset = SeparatorDataset(
          variables=("x",), positives=((0,),),
          trace_negatives=((1,),), live_controls=((0,),),
      )
      assert finite_separation_failures(predicate, dataset) == (("live_control", (0,)),)
  ```

  Add mutation tests for unsorted assignments, duplicate iterations or states,
  nonconsecutive trace iterations, a terminal iteration other than
  `len(steps)+1`, overlapping dataset partitions, missing live controls,
  unsupported coefficients/moduli, more than three clauses, a 13-atom clause,
  extra JSON keys, booleans as integers, malformed hashes, and a semantic
  witness whose sections overlap.

- [ ] **Step 2: Run the focused tests and verify RED**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_reachability_separator.py -q
  ```

  Expected: collection fails because
  `lychrel_reachability_separator` does not exist.

- [ ] **Step 3: Implement the minimal immutable types**

  Use frozen dataclasses and exact tuple fields:

  ```python
  @dataclass(frozen=True)
  class TraceStep:
      iteration: int
      input_state: tuple[tuple[str, int], ...]
      rejected_class: str
      obligation: str
      candidate_atom_count: int
      node_count: int
      path_depth: int

  @dataclass(frozen=True)
  class CounterexampleTrace:
      schema: str
      variables: tuple[str, ...]
      steps: tuple[TraceStep, ...]
      terminal_iteration: int
      stop_reason: str

  @dataclass(frozen=True)
  class SeparatorDataset:
      variables: tuple[str, ...]
      positives: tuple[tuple[int, ...], ...]
      trace_negatives: tuple[tuple[int, ...], ...]
      live_controls: tuple[tuple[int, ...], ...]
  ```

  `SeparatorCertificate` must have schema
  `t29-base19-reachability-separator-certificate-v1`, base, removed coordinate,
  six sorted source digests, trace SHA-256, dataset SHA-256, the predicate, the
  finite status, semantic status, and an optional complete `SemanticWitness`.
  Require exactly one witness for semantic `SAT` and no witness for `UNSAT` or
  unattempted semantics.

- [ ] **Step 4: Implement strict parsers and finite evaluation**

  `evaluate_predicate(predicate, assignment)` evaluates DNF exactly with
  integer arithmetic. `finite_separation_failures` returns canonical tagged
  failures in the order positives, trace negatives, then live controls. Parsers
  require exact keys and reconstruct existing `LinearAtom`, `Conjunction`, and
  `LayerPredicate` values rather than accepting raw mappings downstream.

- [ ] **Step 5: Run Task 1 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_reachability_separator.py -q
  uv run --extra exact --extra dev ruff check \
    .timeloop/lib/lychrel_reachability_separator.py \
    .timeloop/tests/test_lychrel_reachability_separator.py
  git diff --check
  git add .timeloop/lib/lychrel_reachability_separator.py \
    .timeloop/tests/test_lychrel_reachability_separator.py
  git commit -m "feat: define base19 reachability separator certificates"
  ```

### Task 2: Result-preserving T28 counterexample trace replay

**Files:**

- Modify: `.timeloop/runs/t28_base19_tail_quotient.py:278-303,1145-1249`
- Modify: `.timeloop/tests/test_lychrel_reachability_separator.py`

**Interfaces:**

- Produces `replay_layer_synthesis(inputs, partition, following, limits) ->
  tuple[LayerSynthesis, CounterexampleTrace]` and
  `replay_layer31_counterexample_trace(root: Path) ->
  tuple[LayerSynthesis, CounterexampleTrace]`.
- Preserves `synthesize_layer(...) -> LayerSynthesis` and
  `build_layer31_milestone(root) -> LayerSynthesis` byte-for-byte at the
  canonical value boundary.

- [ ] **Step 1: Write failing toy trace-capture tests**

  Extract the existing loop behind an internal function accepting
  `capture_trace: bool`. Test a two-iteration fixture where iteration one
  produces a counterexample and iteration two exceeds a depth limit:

  ```python
  result, trace = replay_layer_synthesis(inputs, partition, terminal, limits)
  assert result.iterations == 2
  assert tuple(step.iteration for step in trace.steps) == (1,)
  assert trace.terminal_iteration == 2
  assert trace.stop_reason == "decision_depth_exceeded"
  ```

  Add an assertion that `synthesize_layer` and trace replay return canonically
  identical `LayerSynthesis` values on the same fixture.

- [ ] **Step 2: Run the toy tests and verify RED**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_reachability_separator.py -q -k trace_replay
  ```

  Expected: import failure for `replay_layer31_counterexample_trace`.

- [ ] **Step 3: Refactor one synthesis core without changing decisions**

  Implement `_synthesize_layer_core(...) -> tuple[LayerSynthesis,
  CounterexampleTrace | None]`. After every exact failed obligation and before
  atom refinement, append a `TraceStep` containing the current DAG's node count
  and `layer_path_depth`. When DAG construction fails, return the trace already
  accumulated and set `terminal_iteration` to the failing candidate number.
  Keep `synthesize_layer` as a wrapper discarding the trace.

- [ ] **Step 4: Add the real trace milestone test**

  ```python
  def test_real_t28_trace_has_221_models_before_candidate_222_depth_stop() -> None:
      result, trace = replay_layer31_counterexample_trace(ROOT)
      assert result.status == "STOP"
      assert result.iterations == 222
      assert len(trace.steps) == 221
      assert tuple(step.iteration for step in trace.steps) == tuple(range(1, 222))
      assert len({step.input_state for step in trace.steps}) == 221
      assert {step.obligation for step in trace.steps} == {"dead_has_no_successor"}
      assert trace.terminal_iteration == 222
      assert trace.stop_reason == "decision_depth_exceeded"
  ```

  Require the last trace state to equal T28 evidence's serialized
  counterexample and every step to use rejected class `DEAD`.

- [ ] **Step 5: Prove T28 durable outputs did not change**

  Run existing T28 tests, then run its CLI to temporary files and require raw
  SHA-256 `b0904f...e47` for primary evidence and
  `7f095a...39e` for the durable independent audit. Do not rewrite either
  durable file.

- [ ] **Step 6: Run Task 2 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_reachability_separator.py \
    .timeloop/tests/test_lychrel_quotient_automaton.py -q
  git add .timeloop/runs/t28_base19_tail_quotient.py \
    .timeloop/tests/test_lychrel_reachability_separator.py
  git commit -m "feat: replay base19 layer31 counterexample trace"
  ```

### Task 3: Frozen T29 adapter and 12-positive/227-negative dataset

**Files:**

- Create: `.timeloop/runs/t29_base19_reachability_separator.py`
- Modify: `.timeloop/tests/test_lychrel_reachability_separator.py`

**Interfaces:**

- Produces `T29Inputs`, `SeparatorLimits`, `load_t29_inputs(root)`,
  `build_separator_dataset(inputs, trace)`, `trace_payload(trace)`, and
  `dataset_payload(dataset)`.
- `SeparatorLimits` freezes coefficients `tuple(range(-3, 4))`, moduli
  `tuple(range(2, 21))`, `max_clauses=3`, `max_atoms_per_clause=12`, and
  `max_candidate_atoms=512`.

- [ ] **Step 1: Write failing identity and dataset tests**

  ```python
  def test_real_dataset_has_exact_disjoint_parts() -> None:
      inputs = load_t29_inputs(ROOT)
      _, trace = replay_layer31_counterexample_trace(ROOT)
      dataset = build_separator_dataset(inputs, trace)
      assert len(dataset.positives) == 12
      assert len(dataset.trace_negatives) == 221
      assert len(dataset.live_controls) == 6
      assert not (set(dataset.positives) & set(dataset.trace_negatives))
      assert not (set(dataset.positives) & set(dataset.live_controls))
  ```

  Add digest-mutation tests for every frozen input, wrong T28 status or stop
  reason, 220/222 trace steps, reordered steps, a duplicate counterexample,
  a missing live class, wrong member sizes, and a changed 14-variable scope.

- [ ] **Step 2: Run adapter tests and verify RED**

  Expected: import failure for `t29_base19_reachability_separator`.

- [ ] **Step 3: Implement the strict adapter**

  Reuse T28's frozen equation/frontier loader and quotient discovery, but
  independently read and hash T28 primary/independent JSON before trusting
  them. Select positives from candidate class `DEAD`; flatten the other three
  classes as live controls. Validate sizes `[1,2,3,12]`, labels and outgoing
  terminal families, 221 trace steps, terminal iteration 222, and final trace
  state equality with T28 evidence.

- [ ] **Step 4: Serialize trace and dataset canonically**

  Payloads include schemas, source digests, variables, exact labeled states,
  counts, terminal iteration, and stop reason. Exclude wall-clock timing,
  temporary paths, solver versions, and platform metadata.

- [ ] **Step 5: Run Task 3 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_reachability_separator.py -q -k 'adapter or dataset'
  uv run --extra exact --extra dev ruff check \
    .timeloop/runs/t29_base19_reachability_separator.py \
    .timeloop/tests/test_lychrel_reachability_separator.py
  git add .timeloop/runs/t29_base19_reachability_separator.py \
    .timeloop/tests/test_lychrel_reachability_separator.py
  git commit -m "feat: freeze base19 reachability separator dataset"
  ```

### Task 4: Bounded atom pool and lexicographic finite DNF synthesis

**Files:**

- Modify: `.timeloop/runs/t29_base19_reachability_separator.py`
- Modify: `.timeloop/tests/test_lychrel_reachability_separator.py`

**Interfaces:**

- Produces `AtomPool`, `FiniteSeparatorResult`,
  `build_candidate_atom_pool(inputs, dataset, limits)`,
  `synthesize_finite_separator(dataset, pool, limits)`, and
  `check_finite_separator(dataset, predicate)`.

- [ ] **Step 1: Write deterministic atom-pool tests**

  On a toy two-variable dataset require terminal/T28 seed atoms, a full-positive
  separator, canonical deduplication, order independence, and exact overflow:

  ```python
  with pytest.raises(EvidenceError, match="candidate_atom_pool_exceeded"):
      build_candidate_atom_pool(inputs, dataset, replace(limits, max_candidate_atoms=1))
  ```

  Add a real test requiring `len(pool.atoms) <= 512`, every atom within the
  frozen grammar, and byte identity across two builds.

- [ ] **Step 2: Implement deterministic candidate generation**

  Reconstruct T28's 37-atom final pool deterministically by starting with
  `derive_guard_atoms(partition, (), limits)` and replaying each trace step
  through `separate_counterexample`; assert the resulting count is 37. Add all
  T27 terminal-clause atoms projected to the layer-31 scope when valid and one
  separator for the complete positive set against each negative. Compute seed
  truth vectors on the 12 positives; for each nonempty canonical equivalence
  class, derive one separator against each negative. Canonicalize after each
  source stage and STOP immediately if the union exceeds 512; never truncate by
  insertion order.

- [ ] **Step 3: Write failing one-, two-, and three-clause synthesis tests**

  Construct toy datasets whose lexicographically minimal solutions require
  exactly one, two, and three clauses. Assert the objective tuple:

  ```python
  assert result.objective == (
      clause_count, total_atoms, maximum_width,
      coefficient_support, absolute_sum, relation_code, modulus_code,
      canonical_bytes(result.predicate),
  )
  ```

  Add cases for no separator, clause width 13, solver `UNKNOWN`, atom-order
  independence, and a tempting predicate that absorbs a live control.

- [ ] **Step 4: Implement exact bounded DNF selection**

  Encode three prefix-active clauses and Boolean atom selections in Z3. A
  positive must satisfy at least one active conjunction. Every negative must
  falsify at least one selected atom in every active conjunction. Require
  `1..12` selected atoms per active clause, inactive suffix clauses, and
  canonical clause ordering. Optimize the frozen objective one component at a
  time, replay the model with `check_finite_separator`, and raise on `UNKNOWN`
  or a nonunique canonical optimum.

- [ ] **Step 5: Run the first real falsifiable milestone**

  Execute finite synthesis once. Record exactly one of:

  - `FINITE_SEPARATOR_STOP` with pool size, attempted clause ceiling, and the
    first uncovered/misclassified state; or
  - finite PASS with predicate, objective, 12/221/6 replay counts, and
    canonical certificate hash.

  Run the same command twice and require byte-identical trace, dataset, and
  finite-result JSON. This is the mandatory checkpoint: do not implement or run
  semantic promotion if finite synthesis STOPs.

- [ ] **Step 6: Run Task 4 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_reachability_separator.py -q -k 'atom_pool or finite_separator'
  git add .timeloop/runs/t29_base19_reachability_separator.py \
    .timeloop/tests/test_lychrel_reachability_separator.py
  git commit -m "exp: synthesize base19 reachability separator"
  ```

### Task 5: Conditional exact semantic promotion and primary gate

**Files:**

- Modify: `.timeloop/runs/t29_base19_reachability_separator.py`
- Modify: `.timeloop/tests/test_lychrel_reachability_separator.py`

**Interfaces:**

- Produces `SemanticCheck`, `check_semantic_dead_region(inputs, predicate)`,
  `decide_t29_gate(baseline, finite_result, semantic_result)`,
  `build_t29_primary(root)`, `render_t29_report(evidence)`, and CLI arguments
  `--evidence`, `--trace`, `--dataset`, `--certificate`, and `--report`.

- [ ] **Step 1: Write exact toy semantic tests**

  Use a tiny explicit equation relation where one predicate is UNSAT with all
  transitions and another has one SAT model. Require the SAT result to contain
  complete sorted input/output/local assignments and the lexicographically
  first bounded model. Mutating any witness value must fail integer equation
  replay.

- [ ] **Step 2: Implement the primary semantic query**

  Reconstruct T28's exact layer-32 local formula over the 14 input, 14 output,
  and local variables. Conjoin the finite predicate on the input scope. Return
  semantic `UNSAT` only for solver UNSAT. On SAT, minimize every complete
  assignment coordinate lexicographically, replay all 12 equations with
  integers, and return `SemanticWitness`. Raise `EvidenceError` on UNKNOWN.

- [ ] **Step 3: Write fail-closed primary-gate tests**

  Cover finite STOP, finite PASS with missing predicate, digest mismatch,
  semantic UNKNOWN, malformed SAT witness, semantic UNSAT, and semantic SAT:

  ```python
  evidence, certificate = decide_t29_gate(baseline, finite_pass, semantic_sat)
  assert evidence["status"] == "FINITE_SEPARATOR_PASS_SEMANTIC_STOP"
  assert evidence["semantic_counterexample"] == semantic_sat.witness.to_payload()
  assert certificate is not None
  assert certificate.semantic_status == "SAT"
  ```

  A finite STOP emits no predicate certificate. A finite PASS always preserves
  its finite certificate even if semantic promotion STOPs. Only independently
  confirmed UNSAT may become `SEMANTIC_DEAD_REGION_PASS`.

- [ ] **Step 4: Implement deterministic evidence and report rendering**

  Bind all six source digests, trace/dataset hashes, pool size, frozen limits,
  finite objective, replay counts, semantic obligation, exact witness when
  present, Prism failure record, primary-source provenance, claim boundary,
  limitations, and stop condition. The report must label the finite predicate
  as finite-only whenever semantic status is not UNSAT.

- [ ] **Step 5: Run the real primary command twice if Task 4 passed**

  Write two sets of temporary artifacts and compare every applicable file with
  `cmp -s`. If Task 4 stopped, implement only the finite STOP evidence path and
  assert that semantic-query code was not called.

- [ ] **Step 6: Run Task 5 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_reachability_separator.py -q
  uv run --extra exact --extra dev ruff check \
    .timeloop/runs/t29_base19_reachability_separator.py \
    .timeloop/tests/test_lychrel_reachability_separator.py
  git add .timeloop/runs/t29_base19_reachability_separator.py \
    .timeloop/tests/test_lychrel_reachability_separator.py
  git commit -m "exp: decide base19 reachability separator gate"
  ```

### Task 6: Isolated assurance, mutations, and durable artifacts

**Files:**

- Create: `.timeloop/runs/t29_base19_reachability_separator_independent.py`
- Modify: `.timeloop/tests/test_lychrel_reachability_separator.py`
- Conditionally create: `.timeloop/runs/t29_base19_reachability_separator_certificate.json`
- Create: `.timeloop/runs/t29_base19_reachability_separator.json`
- Create: `.timeloop/runs/t29_base19_reachability_separator_trace.json`
- Create: `.timeloop/runs/t29_base19_reachability_separator_dataset.json`
- Create: `.timeloop/runs/t29_base19_reachability_separator_independent.json`
- Create: `.timeloop/runs/t29_base19_reachability_separator_report.md`

**Interfaces:**

- Command:
  `python3 -I t29_base19_reachability_separator_independent.py EQUATIONS FRONTIER T28_EVIDENCE TRACE DATASET T29_EVIDENCE [CERTIFICATE]`.
- Produces schema `t29-base19-reachability-separator-independent-v1` and status
  equal to the independently replayed primary boundary or `REJECT`.

- [ ] **Step 1: Write isolated positive and mutation tests**

  Copy the checker alone into `tmp_path` and run with `sys.executable -I`.
  Assert `repository_imports == []`. Add one mutation per source digest, trace
  state/order/iteration, positive, live control, predicate atom, clause,
  semantic status, and witness section/value. Every mutation must exit nonzero,
  print `REJECT:` to stderr, and never emit PASS JSON.

- [ ] **Step 2: Implement strict standalone parsing**

  Use only Python's standard library. Require exact schemas/keys, integral
  nonboolean values, canonical sorting, coefficients/moduli/widths inside the
  frozen grammar, six source identities, 221 consecutive trace steps,
  terminal iteration 222, 12 positives, 221 trace negatives, six live controls,
  and exact trace/dataset hashes.

- [ ] **Step 3: Replay finite and semantic obligations independently**

  Evaluate all 239 examples directly. For semantic SAT, rebuild the selected
  12 equations and replay the complete witness. For semantic UNSAT, enumerate
  allowed equation tuples, apply generalized arc consistency, branch on the
  lexicographically first smallest non-singleton domain, memoize residual
  domains, and require no model. A finite STOP checks only the achieved finite
  boundary and must not claim semantic assurance.

- [ ] **Step 4: Run real independent assurance and mutation suite**

  Require independent status to equal primary status. Disagreement changes the
  durable status to STOP with `primary_independent_disagreement`; it never
  promotes a claim.

- [ ] **Step 5: Materialize and validate artifacts**

  Copy the first byte-stable temporary trace, dataset, evidence, report, and
  independent audit to durable paths. Create a certificate only for finite
  PASS. Validate JSON with `python3 -m json.tool`, rerun the isolated checker on
  durable paths, and require byte-identical stdout.

- [ ] **Step 6: Run Task 6 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_reachability_separator.py -q
  uv run --extra exact --extra dev ruff check \
    .timeloop/runs/t29_base19_reachability_separator_independent.py
  git add .timeloop/runs/t29_base19_reachability_separator_independent.py \
    .timeloop/runs/t29_base19_reachability_separator.json \
    .timeloop/runs/t29_base19_reachability_separator_trace.json \
    .timeloop/runs/t29_base19_reachability_separator_dataset.json \
    .timeloop/runs/t29_base19_reachability_separator_independent.json \
    .timeloop/runs/t29_base19_reachability_separator_report.md \
    .timeloop/tests/test_lychrel_reachability_separator.py
  git commit -m "exp: independently audit base19 reachability separator"
  ```

  If finite synthesis passed, stage the certificate with a separate explicit
  `git add .timeloop/runs/t29_base19_reachability_separator_certificate.json`
  before committing. Review `git diff --cached --name-only` in either branch.

### Task 7: Durable conclusion and final verification

**Files:**

- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `docs/superpowers/plans/2026-08-09-base19-reachability-separator.md`
- Verify: every T27--T29 code, test, evidence, certificate, and audit file

**Interfaces:**

- Produces exactly one durable conclusion from the three approved T29 statuses.

- [ ] **Step 1: Regenerate primary and independent artifacts twice**

  Compare trace, dataset, evidence, report, optional certificate, and audit
  byte-for-byte. Require the trace to contain 221 steps and terminal iteration
  222 in every run.

- [ ] **Step 2: Record the exact notebook boundary**

  Add a T29 section with `STATUS`, `CLAIM`, `RELATION TO PREPRINT/T27/T28`,
  `TRACE`, `FINITE SEPARATOR`, `SEMANTIC CHECK`, `INDEPENDENT CHECK`, `PRISM AND
  RESEARCH`, `STOP CONDITION`, `LIMITATIONS`, and `NEXT`. State the exact
  predicate or bounded failure, all counts and hashes, whether semantic
  promotion ran, and that no other base/topology/Lean work ran.

- [ ] **Step 3: Mark executed and skipped plan branches**

  Add `Execution outcome (2026-08-09)` before Global Constraints. Mark semantic
  tasks skipped if finite separation stopped, and never mark the broader
  reachability-invariant target complete solely because T29 ended.

- [ ] **Step 4: Run final compilation, lint, and regressions**

  ```bash
  uv run --extra exact --extra dev python -m py_compile \
    .timeloop/lib/lychrel_reachability_separator.py \
    .timeloop/runs/t28_base19_tail_quotient.py \
    .timeloop/runs/t29_base19_reachability_separator.py \
    .timeloop/runs/t29_base19_reachability_separator_independent.py
  uv run --extra exact --extra dev ruff check \
    .timeloop/lib/lychrel_reachability_separator.py \
    .timeloop/runs/t29_base19_reachability_separator.py \
    .timeloop/runs/t29_base19_reachability_separator_independent.py \
    .timeloop/tests/test_lychrel_reachability_separator.py
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_reachability_separator.py \
    .timeloop/tests/test_lychrel_quotient_automaton.py \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  ```

- [ ] **Step 5: Validate preservation and Git scope**

  Validate all durable JSON and isolated replay; run `git diff --check`, inspect
  `git diff --name-status` and `git status --short`, and require publication ZIP
  SHA-256
  `e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33`.
  Confirm every pre-existing dirty/untracked path remains outside T29 commits.

- [ ] **Step 6: Commit the final conclusion**

  ```bash
  git add .timeloop/notebook/lychrel-bases.md \
    docs/superpowers/plans/2026-08-09-base19-reachability-separator.md
  git commit -m "docs: record base19 reachability separator outcome"
  ```
