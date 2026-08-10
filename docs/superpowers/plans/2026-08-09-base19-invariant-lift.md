# T27 Base-19 Invariant and Base-Lift Research Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Execute inline without subagents.

**Goal:** Either produce a compact, independently replayed inductive
certificate for the frozen 408-equation base-19 obstruction and then attempt
its symbolic lift, or stop with a precise falsification record at the first
failed gate.

**Architecture:** A small typed predicate language sits between the promoted
frontier data and two derivation routes: state-driven CEGIS and exact
pseudo-Boolean elimination. The primary program synthesizes and minimizes
candidates; a standalone program rebuilds radial layers directly from the
equation manifest and checks every obligation. Gate B runs only after Gate A
passes, first searching bases `41..200` for a counterexample and then accepting
an infinite-range conclusion only through explicit algebraic case certificates.

**Tech Stack:** Python 3.13 via `uv`, standard-library exact integers and
`fractions.Fraction`, `z3-solver` 5.x for primary finite synthesis only,
CaDiCaL 3.0.1 for the conditional concrete scan, pytest 8.x, deterministic
JSON, SHA-256, and the existing one-hot and compact binary topology encodings.

## Execution outcome (2026-08-09)

- [x] Tasks 1 through 3: typed certificate language, frozen evidence replay,
  and universal local obligation checker.
- [x] Task 4 achieved boundary: a three-clause layer-32 tail invariant passes
  exact initiation and terminal exclusion; bounded backward synthesis finds no
  accepted layer-31 predicate.
- [x] Task 5 hard stop: Gate A records
  `backward_extension_layer_31_not_found`, sub-tenfold compression, and
  `gate_b_authorized: false`.
- [x] Task 6 achieved-claim audit: an isolated standard-library checker
  independently verifies the terminal tail lemma and rejects mutation. It does
  not claim to reconstruct the absent inductive certificate.
- [x] Tasks 7 and 8 skipped because Gate A did not pass.
- [x] Task 9 durable evidence and scope-calibrated notebook conclusion.
- [ ] A layer-25-to-32 inductive certificate and symbolic base lift remain
  unachieved; no unchecked plan item is implicitly claimed complete.

## Global Constraints

- Preserve `.timeloop/exam/results.jsonl` and every unrelated user change.
- Do not modify `publication/base19-radial/preprint/`, its ZIP, or publication
  sources.
- Treat the 409-equation manifest, its frozen removed coordinate, and the
  resulting promoted 408-equation frontier as frozen inputs; never silently
  regenerate or rewrite them.
- Keep coefficients in `{-3,-2,-1,0,1,2,3}`, congruence moduli in `2..20`, at
  most 12 atoms per conjunction, and at most three conjunctions per predicate.
- Measure compression as UTF-8 byte lengths of key-sorted, whitespace-free
  canonical JSON.
- Require at least tenfold compression for the late-layer milestone and the
  full Gate A certificate; a renamed state table is failure.
- Treat solver output, interpolants, cutting planes, and Prism output only as
  candidate generators; direct exact checking is authoritative.
- Fail closed on UNKNOWN, malformed input, digest mismatch, missed transition,
  unsupported certificate syntax, or disagreement between checkers.
- The independent checker imports no T24, T25, T26, frontier, topology, solver,
  or synthesis module.
- Run Gate B only when the independently checked Gate A status is `PASS`.
- Gate A concerns the phase-zero interface-shifted fragment lengths
  `(26,25,31)`; Gate B concerns the original T21 lengths `(28,23,31)`. Require
  an exact base-19 topology-transport certificate before symbolic base lifting.
- A SAT result at any base `b >= 18` falsifies the universal Gate B target; keep
  the exact assignment and pivot to an exceptional-base statement.
- Never infer an infinite-base theorem from a finite scan.
- Keep the Lean bridge outside the critical path.
- Budget one to two focused research days for Tasks 1 through 6. If Gate A
  passes, budget two to five additional days for Tasks 7 through 9; do not buy
  more time by expanding the approved grammar or claim boundary.

## File Map

- Create `.timeloop/lib/lychrel_invariant_certificate.py` — immutable predicate
  syntax, canonical serialization, finite evaluation, and compression metrics.
- Create `.timeloop/runs/t27_base19_invariant_lift.py` — frozen-input loader,
  two-route synthesis, minimization, Gate A orchestration, conditional Gate B
  counterexample search, and deterministic evidence generation.
- Create `.timeloop/runs/t27_base19_invariant_lift_independent.py` — standalone
  equation parser, radial enumerator, certificate checker, and symbolic-case
  checker using only the standard library.
- Create `.timeloop/tests/test_lychrel_invariant_lift.py` — unit, mutation,
  isolation, and bounded real-fixture tests.
- Create `.timeloop/runs/t27_base19_invariant_lift.json` — one evidence chain
  containing source digests, both gates, certificate payloads, counterexamples,
  and exact stop reason.
- Modify `.timeloop/notebook/lychrel-bases.md` — narrow result, limitations,
  verification commands, and next action.

---

### Task 1: Typed certificate language and canonical size measure

**Files:**

- Create: `.timeloop/lib/lychrel_invariant_certificate.py`
- Create: `.timeloop/tests/test_lychrel_invariant_lift.py`

**Interfaces:**

- Produces frozen `LinearAtom(relation, terms, constant, modulus=None)`,
  `Conjunction(atoms)`, `LayerPredicate(layer, variables, clauses)`, and
  `InvariantCertificate(schema, base, removed, source_digests, predicates,
  obligations)`.
- Produces `parse_certificate(payload) -> InvariantCertificate`,
  `evaluate_predicate(predicate, assignment) -> bool`,
  `canonical_bytes(value) -> bytes`, and
  `compression_record(certificate_payload, state_payload) -> dict[str, object]`.

- [ ] **Step 1: Write failing literal syntax and evaluation tests**

  ```python
  def test_linear_congruence_and_carry_literal_evaluation() -> None:
      assignment = {"c0": 1, "c1": 0, "d": 7}
      predicate = LayerPredicate(
          layer=25,
          variables=("c0", "c1", "d"),
          clauses=(Conjunction((
              LinearAtom("eq", (("c0", 1), ("c1", -1)), 1),
              LinearAtom("le", (("d", 1),), 8),
              LinearAtom("congruent", (("d", 1), ("c0", 1)), 0, modulus=4),
          )),),
      )
      assert evaluate_predicate(predicate, assignment)


  def test_canonical_bytes_fix_key_and_sequence_order() -> None:
      left = {"b": 2, "a": [{"terms": [["y", -1], ["x", 1]]}]}
      right = {"a": [{"terms": [["x", 1], ["y", -1]]}], "b": 2}
      assert canonical_bytes(left) == canonical_bytes(right)
  ```

  Add rejection tests for zero coefficients, duplicate variables, coefficient
  magnitude above three, modulus outside `2..20`, more than 12 atoms, more
  than three clauses, missing assignments, and non-canonical residues.

- [ ] **Step 2: Run the focused tests and verify RED**

  Run:

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py -q \
    -k 'evaluation or canonical_bytes or rejects'
  ```

  Expected: collection fails because `lychrel_invariant_certificate` does not
  exist.

- [ ] **Step 3: Implement normalized atoms and disjunctive predicates**

  Normalize terms by variable name, combine repeated coefficients, remove
  zeros, divide equalities and inequalities by the positive coefficient GCD,
  and normalize congruence residues into `0..modulus-1`. Define semantics as:

  ```python
  total = sum(coefficient * assignment[name] for name, coefficient in atom.terms)
  if atom.relation == "eq":
      return total == atom.constant
  if atom.relation == "le":
      return total <= atom.constant
  if atom.relation == "congruent":
      return (total - atom.constant) % atom.modulus == 0
  raise ValueError(f"unsupported relation: {atom.relation}")
  ```

  A `LayerPredicate` is true when any clause is true; a `Conjunction` is true
  when every atom is true. Empty clause or predicate lists are invalid.

- [ ] **Step 4: Implement strict parsing and canonical serialization**

  Accept only schema `t27-invariant-certificate-v1`; reject unknown keys and
  JSON booleans where integers are required. Sort terms, atoms, clauses, and
  layer predicates by their canonical JSON bytes. `canonical_bytes` must use
  `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
  plus UTF-8 encoding and must canonicalize semantically unordered sequences
  before dumping.

- [ ] **Step 5: Implement the exact compression record**

  Compute the byte counts once, then return:

  ```python
  certificate_bytes = len(canonical_bytes(certificate_payload))
  state_bytes = len(canonical_bytes(state_payload))
  {
      "certificate_bytes": certificate_bytes,
      "state_table_bytes": state_bytes,
      "compression_numerator": state_bytes,
      "compression_denominator": certificate_bytes,
      "at_least_tenfold": state_bytes >= 10 * certificate_bytes,
  }
  ```

  Do not serialize a float ratio.

- [ ] **Step 6: Run Task 1 tests GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  git add .timeloop/lib/lychrel_invariant_certificate.py \
    .timeloop/tests/test_lychrel_invariant_lift.py
  git commit -m "feat: define compact invariant certificate language"
  ```

### Task 2: Frozen evidence loader and canonical radial coordinates

**Files:**

- Create: `.timeloop/runs/t27_base19_invariant_lift.py`
- Modify: `.timeloop/tests/test_lychrel_invariant_lift.py`

**Interfaces:**

- Consumes `publication/base19-radial/instance/equations.json` and
  `publication/base19-radial/certificates/minimal-core-frontier.json`.
- Produces `EvidenceError`, `Equation`, `FrontierLayer`,
  `load_promoted_inputs(root)`, `reproduce_structural_baseline(inputs)`,
  `canonical_variable(name, layer, side) -> str`,
  `canonicalize_state(layer, side, state) -> dict[str, int]`, and
  `state_table_payload(layers) -> dict[str, object]`.

- [ ] **Step 1: Write failing frozen-input and coordinate tests**

  ```python
  def test_promoted_base19_inputs_have_frozen_identity() -> None:
      equations, frontier = load_promoted_inputs(ROOT)
      assert equations.content_sha256 == (
          "ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040"
      )
      assert frontier.content_sha256 == (
          "0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0"
      )
      assert frontier.provenances_sha256 == (
          "cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302"
      )
      assert frontier.removed == "phase=0,n=0,column=82"
      assert len(frontier.layers) == 35


  def test_canonical_state_orders_phase_carries_before_digits() -> None:
      layer = load_promoted_inputs(ROOT)[1].layers_by_number[32]
      state = canonicalize_state(layer, "output", layer.output_states[0])
      assert list(state)[:4] == ["L0", "R0", "L1", "R1"]
      assert list(state)[-2:] == ["D0", "D1"]
  ```

  Add mutation tests for a changed source digest, duplicated equation
  provenance, an output-state width mismatch, a transition referring to an
  unknown state, layer numbers other than `-1..33`, and the wrong late-layer
  counts `(20,12,12,17,16,18,18,22,0)`. Add a broken-pair fixture that fails
  the structural baseline rather than silently lowering the pair count.

- [ ] **Step 2: Run the loader tests and verify RED**

  Run:

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py -q -k 'promoted or canonical_state'
  ```

  Expected: import fails because the T27 primary module does not exist.

- [ ] **Step 3: Implement strict frozen-input parsing**

  Parse atoms as exactly one of `{"literal": int}` or `{"variable": str}`.
  Recompute canonical content hashes using the same convention encoded by each
  manifest and require base 19, 409 source equations, 408 selected equations,
  status `UNSAT`, and the exact removed provenance. Verify every layer state
  digest and reconstruct each next input set from the preceding transitions.
  Derive fixed-fragment lengths from the full manifest and require phase zero
  `(26,25,31)` and phases one through five `(29,23,31)`. Treat each
  `p<phase>:f0:d0` as a canonical leading digit with domain `1..18`; every other
  digit has domain `0..18`.

- [ ] **Step 4: Implement phase-relative frontier names**

  For each side, sort carries by `(phase, column)`, then name the smaller
  column in each phase `L<phase>` and the larger column `R<phase>`; sort live
  digits by `(phase, fragment, offset)` and name them `D0`, `D1`. Store the
  reversible original-to-canonical map in each certificate predicate. Reject a
  layer with more than two carries per phase or more than two live digits.

- [ ] **Step 5: Reproduce the structural baseline**

  Before exposing states to synthesis, reproduce the structural baseline. Pair
  the selected 408 equations by identical unordered addend atoms, requiring
  exactly 203 disjoint two-equation groups plus the exact singleton boundaries
  `phase=5,n=0,column=0` and `phase=5,n=0,column=83`; within each group require
  distinct provenances and distinct target/carry rows, but do not require equal
  radial layers. Replace every pair by the exact difference of its two integer
  column equations, retain both boundaries, map manifest literal 18 to `b-1`,
  and use Z3 only to find one exact satisfying assignment at every base
  `17..40`; replay all assignments with integer arithmetic and the leading
  nonzero domains. At terminal layer 33, delete each of its 12 equations in
  turn, enumerate completions of all 22 input states, and require at least two
  surviving states for each deletion. Serialize the pair map, witnesses, and
  survivor counts so the independent checker can replay them. Any mismatch
  stops before synthesis.

- [ ] **Step 6: Implement the state-table comparison payload**

  Serialize only mathematical content:

  ```python
  {
      "layers": [
          {"layer": layer.number, "variables": canonical_names,
           "states": canonical_state_rows}
          for layer in selected_layers
      ]
  }
  ```

  Use layers `25..32` for the milestone denominator and `-1..32` for the full
  Gate A denominator; never include source paths, digests, timestamps, or
  solver metadata in the size comparison.

- [ ] **Step 7: Run Task 2 tests GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  git add .timeloop/runs/t27_base19_invariant_lift.py \
    .timeloop/tests/test_lychrel_invariant_lift.py
  git commit -m "feat: load frozen base19 radial evidence"
  ```

### Task 3: Direct obligation checker and counterexample reporting

**Files:**

- Modify: `.timeloop/lib/lychrel_invariant_certificate.py`
- Modify: `.timeloop/runs/t27_base19_invariant_lift.py`
- Modify: `.timeloop/tests/test_lychrel_invariant_lift.py`

**Interfaces:**

- Produces `ObligationResult(kind, layer, status, checked_count,
  counterexample)`, `check_initiation`, `check_consecution`,
  `check_exclusion`, and `check_certificate(frontier, certificate)`.

- [ ] **Step 1: Write failing initiation, consecution, and exclusion tests**

  ```python
  def test_checker_reports_the_first_bad_transition() -> None:
      certificate = fixture_certificate(predicate_for_25="D0 <= 6")
      result = check_certificate(fixture_frontier(), certificate)
      assert result.status == "FAIL"
      assert result.obligations[-1].kind == "consecution"
      assert result.obligations[-1].counterexample == {
          "input": {"L0": 0, "D0": 6},
          "output": {"L0": 1, "D0": 7},
      }
  ```

  Use a hand-authored three-layer fixture with one passing certificate, one
  failing initiation, one failing transition, and one terminal state satisfying
  the terminal relation. Assert deterministic first-counterexample ordering.

- [ ] **Step 2: Run the checker tests and verify RED**

  Expected: failures naming `check_certificate` and `ObligationResult`.

- [ ] **Step 3: Implement exact finite obligation checks**

  Initiation checks every stored output state at the first named predicate.
  Consecution iterates the promoted transition list in sorted input/output
  order and requires `P_layer(input) -> P_next(output)`. Exclusion checks every
  state admitted by the last predicate against exact terminal local models;
  for finite validation enumerate carry values in `{0,1}` and digit values in
  `0..18` for variables not fixed by the frontier state.

- [ ] **Step 4: Require coverage rather than sampled agreement**

  Verify that transition inputs equal the complete stored input state set and
  transition outputs equal the complete next state set. Each result records
  exact checked counts. Missing mappings, duplicate transitions, or variables
  outside a predicate scope raise `EvidenceError`; they do not return PASS.

- [ ] **Step 5: Run Task 3 tests GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  git add .timeloop/lib/lychrel_invariant_certificate.py \
    .timeloop/runs/t27_base19_invariant_lift.py \
    .timeloop/tests/test_lychrel_invariant_lift.py
  git commit -m "feat: check radial invariant obligations exactly"
  ```

### Task 4: Bounded two-route predicate synthesis

**Files:**

- Modify: `.timeloop/runs/t27_base19_invariant_lift.py`
- Modify: `.timeloop/tests/test_lychrel_invariant_lift.py`

**Interfaces:**

- Produces `enumerate_atoms(states, variables, limits)`,
  frozen `GrammarLimits(coefficients, moduli, max_atoms, max_clauses)`,
  `synthesize_cegis(layers, limits)`,
  `derive_cut_candidates(equations, layer, limits)`,
  `minimize_predicate(predicate, obligation)`, and
  `synthesize_late_certificate(inputs) -> SynthesisResult`, where
  `SynthesisResult` stores status, route provenance, candidate, checked
  obligations, compression, and the first deterministic stop reason.

- [ ] **Step 1: Write failing bounded-grammar tests**

  ```python
  def test_atom_enumerator_respects_the_closed_grammar() -> None:
      atoms = tuple(enumerate_atoms(
          states=({"L0": 0, "R0": 1, "D0": 5},),
          variables=("L0", "R0", "D0"),
          limits=GrammarLimits(),
      ))
      assert atoms == tuple(sorted(set(atoms), key=canonical_bytes))
      assert all(max(abs(c) for _, c in atom.terms) <= 3 for atom in atoms)
      assert all(atom.modulus is None or 2 <= atom.modulus <= 20 for atom in atoms)
  ```

  Add a two-layer fixture where a single equality is discoverable by CEGIS and
  a separate fixture where eliminating one local variable from two equations
  yields `L0 + R0 - D0 = 0`. Assert `route` is respectively `state_cegis` and
  `pb_elimination`.

- [ ] **Step 2: Run synthesis tests and verify RED**

  Expected: failures naming the grammar limits and synthesis functions.

- [ ] **Step 3: Implement deterministic atom enumeration and CEGIS**

  Generate normalized coefficient vectors lexicographically, first equalities
  and inequalities, then moduli `2..20`, discarding atoms true on every point
  of the complete bounded domain. For one conjunction, choose a deterministic
  nonempty component of reachable positive states and retain only atoms true on
  every state in that component. Add the cheapest atom false on the largest
  number of currently admitted bad states, and recheck the full obligation
  after every addition. Stop at 12 atoms; build at most three clauses by
  repeating on reachable positive states not admitted by earlier clauses.
  Tie-break by canonical bytes and reject a clause that admits no reachable
  state.

- [ ] **Step 4: Implement exact pseudo-Boolean elimination**

  Convert each local column to
  `left + right + carry_in - target - 19*carry_out = 0` and add exact digit and
  carry bounds. At each radial cut, eliminate local variables by equal-and-
  opposite integer combinations of equalities and Fourier-Motzkin combinations
  of inequalities. Normalize after every operation, discard a result when a
  retained coefficient exceeds three, and retain only consequences over the
  shared frontier with congruence modulus at most 20. Record the two parent row
  hashes and integer multipliers for every derived candidate.

- [ ] **Step 5: Verify proof-derived candidates before admitting them**

  Replay every parent combination with `Fraction` arithmetic and exhaust every
  exact local model from the promoted transition. A candidate with an invalid
  derivation record or one false on a local model is rejected. Merge candidates
  from the two routes only after canonical normalization.

- [ ] **Step 6: Minimize predicates against obligations**

  Delete atoms, then clauses, in canonical order whenever the same obligation
  still passes. Reject a minimized predicate with more than 12 atoms in a
  clause, more than three clauses, or canonical bytes no smaller than its
  pre-minimized form.

- [ ] **Step 7: Run bounded late-layer synthesis**

  Run:

  ```bash
  uv run --extra exact python \
    .timeloop/runs/t27_base19_invariant_lift.py \
    --gate-a-milestone > /tmp/t27-gate-a-milestone.json
  python3 -m json.tool /tmp/t27-gate-a-milestone.json >/dev/null
  ```

  Expected: a deterministic `PASS` or `STOP` record for layers `25..33`; no
  command is allowed to expand the grammar after `STOP`.

- [ ] **Step 8: Run Task 4 tests GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  git add .timeloop/runs/t27_base19_invariant_lift.py \
    .timeloop/tests/test_lychrel_invariant_lift.py
  git commit -m "exp: synthesize bounded base19 frontier predicates"
  ```

### Task 5: Gate A milestone, backward extension, and hard stop

**Claim boundary:** Gate A proves only that the frozen 408 selected equations
in base 19 are jointly unsatisfiable. It does not prove minimum cardinality,
anything about the unbounded reverse-and-add orbit, other base-19 topologies,
or another base.

**Files:**

- Modify: `.timeloop/runs/t27_base19_invariant_lift.py`
- Modify: `.timeloop/tests/test_lychrel_invariant_lift.py`
- Create: `.timeloop/runs/t27_base19_invariant_lift.json`

**Interfaces:**

- Produces `build_gate_a() -> dict[str, object]` with `status` in
  `{"PASS", "STOP"}`, the exact grammar-exhaustion record, late and full
  compression records, primary obligations, and a complete certificate only
  for PASS. Produces `decide_gate_a(...) -> dict[str, object]` as the sole gate
  transition.

- [ ] **Step 1: Write the failing Gate A decision tests**

  ```python
  def test_gate_a_stops_when_late_certificate_is_too_large() -> None:
      result = decide_gate_a(
          milestone_check=passing_check(),
          milestone_compression={"at_least_tenfold": False},
      )
      assert result == {
          "status": "STOP",
          "stop_reason": "late_certificate_below_tenfold_compression",
          "gate_b_authorized": False,
      }
  ```

  Add cases for grammar exhaustion, failed obligation, failed derivation replay,
  full-certificate compression below tenfold, and PASS. Every STOP case must
  have `gate_b_authorized: false` and omit symbolic claims.

- [ ] **Step 2: Run the decision tests and verify RED**

  Expected: failure naming `decide_gate_a`.

- [ ] **Step 3: Freeze the milestone before backward extension**

  Synthesize predicates for output layers `25..32`, use layer 25 reachable
  states for milestone initiation, and exclude all exact terminal models at
  layer 33. Store counts `(20,12,12,17,16,18,18,22)` and both canonical byte
  lengths. If the check or tenfold threshold fails, emit STOP immediately.

- [ ] **Step 4: Extend the same grammar backward to initiation**

  Only after the milestone passes, synthesize predicates for output layers
  `-1..24`, minimizing backward from the already frozen layer-25 predicate.
  Check initiation at layer `-1`, all 33 consecutive transfers for local layers
  `0..32`, and terminal exclusion at 33. Re-minimize globally only by deletion; do
  not add a fourth clause, a thirteenth atom, a coefficient of magnitude four,
  or modulus 21.

- [ ] **Step 5: Enforce the full-certificate decision**

  PASS requires every primary obligation true, all derivation records replayed,
  and the full certificate at least ten times smaller than the full explicit
  state payload. Otherwise record the first deterministic stop reason and the
  smallest failed counterexample.

- [ ] **Step 6: Emit deterministic preliminary evidence**

  Run twice and compare:

  ```bash
  uv run --extra exact python \
    .timeloop/runs/t27_base19_invariant_lift.py --gate-a \
    > /tmp/t27-gate-a-1.json
  uv run --extra exact python \
    .timeloop/runs/t27_base19_invariant_lift.py --gate-a \
    > /tmp/t27-gate-a-2.json
  cmp -s /tmp/t27-gate-a-1.json /tmp/t27-gate-a-2.json
  ```

  Expected: byte-identical files. Copy the first file to the durable JSON only
  after Task 6 independent verification has run.

- [ ] **Step 7: Run Task 5 tests GREEN and commit code only**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  git add .timeloop/runs/t27_base19_invariant_lift.py \
    .timeloop/tests/test_lychrel_invariant_lift.py
  git commit -m "exp: decide compact base19 invariant gate"
  ```

### Task 6: Standalone Gate A reconstruction and audit

**Files:**

- Create: `.timeloop/runs/t27_base19_invariant_lift_independent.py`
- Modify: `.timeloop/tests/test_lychrel_invariant_lift.py`
- Create or modify: `.timeloop/runs/t27_base19_invariant_lift.json`

**Interfaces:**

- Command:
  `python3 -I t27_base19_invariant_lift_independent.py EQUATIONS EVIDENCE`.
- Primary attachment command:
  `t27_base19_invariant_lift.py --attach-audit EVIDENCE AUDIT`.
- Produces canonical JSON with source hashes, rebuilt layer/state hashes,
  initiation/consecution/exclusion counts, compression recomputation, mutation
  status, and `status` in `{"PASS", "STOP", "REJECT"}`.

- [ ] **Step 1: Write a failing isolated-subprocess test**

  ```python
  def test_independent_checker_runs_without_repository_imports(tmp_path: Path) -> None:
      checker = tmp_path / "checker.py"
      shutil.copy(INDEPENDENT, checker)
      completed = subprocess.run(
          (sys.executable, "-I", str(checker), str(FIXTURE_EQUATIONS),
           str(FIXTURE_EVIDENCE)),
          cwd=tmp_path, check=True, text=True, capture_output=True,
      )
      audit = json.loads(completed.stdout)
      assert audit["status"] == "PASS"
      assert audit["repository_imports"] == []
  ```

  Add mutations that change one equation coefficient, one predicate constant,
  one layer mapping, one source digest, and one obligation status. Each must
  return nonzero with no PASS JSON.

- [ ] **Step 2: Run the isolation tests and verify RED**

  Expected: copy fails because the independent script does not exist.

- [ ] **Step 3: Reimplement strict equation and certificate parsing**

  Use only `argparse`, `dataclasses`, `fractions`, `hashlib`, `itertools`,
  `json`, `re`, and `sys`. Reject extra keys, booleans-as-integers, malformed
  atom unions, duplicate provenances, non-Boolean carries, digits outside
  `0..base-1`, and any source hash mismatch. Do not add repository paths to
  `sys.path`.

- [ ] **Step 4: Rebuild radial layers from equations**

  Parse `(phase,column)` from provenance. From all 409 manifest equations,
  before removing the frozen coordinate, derive each contiguous source length
  as the number of columns whose addends are not both literal zero and require
  ordinary columns `0..source_length-1`. Then remove exactly the declared row.
  Identify the overflow boundary by its two literal-zero addends and absent
  outgoing carry; assign it layer `-1`. Assign every selected ordinary equation
  layer
  `min(column, source_length - 1 - column)`. Recompute input/output frontiers
  from first and last occurrence. For each input state, initialize digit domains
  to `0..18`, canonical `p<phase>:f0:d0` leading domains to `1..18`, and carry
  domains to `{0,1}`. Enforce generalized arc consistency by enumerating each
  equation's at-most `2*19^2` local tuples, branch on the lexicographically
  first smallest remaining domain, and project sorted output states. Require
  the rebuilt 35 layer digests to match the evidence claims.

- [ ] **Step 5: Check all certificate obligations independently**

  Duplicate the small predicate evaluator intentionally. Enumerate initiation,
  every transition at every named layer, and terminal exclusion directly from
  the equations. Replay the 203 equation pairs, all base-`17..40` difference
  assignments, all proof-derived parent-row combinations, and all 12
  terminal-deletion survivor counts. Recompute both compression records from
  its own canonical serializer. A primary PASS becomes independent PASS only
  when every count, digest, and Boolean result agrees.

- [ ] **Step 6: Materialize the durable Gate A record**

  Run:

  ```bash
  cp /tmp/t27-gate-a-1.json .timeloop/runs/t27_base19_invariant_lift.json
  python3 -I .timeloop/runs/t27_base19_invariant_lift_independent.py \
    publication/base19-radial/instance/equations.json \
    .timeloop/runs/t27_base19_invariant_lift.json \
    > /tmp/t27-gate-a-independent.json
  ```

  Add the independent audit to the evidence through the primary program's
  `--attach-audit` command, then rerun the independent checker on the combined
  artifact. The command must reject an audit whose `evidence_sha256` does not
  match the certificate-bearing portion.

- [ ] **Step 7: Apply the Gate A stop checkpoint**

  If either primary or independent status is not PASS, commit the measured STOP
  artifact, skip Tasks 7 and 8, perform Task 9 with a Gate A failure conclusion,
  and end the round. Do not reinterpret a failed grammar as evidence that no
  human-readable invariant exists.

- [ ] **Step 8: Run Task 6 tests GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  git add .timeloop/runs/t27_base19_invariant_lift_independent.py \
    .timeloop/runs/t27_base19_invariant_lift.json \
    .timeloop/tests/test_lychrel_invariant_lift.py
  git commit -m "exp: independently audit base19 invariant certificate"
  ```

### Task 7: Conditional base `41..200` counterexample search

**Gate:** Execute only when Task 6 independently reports Gate A PASS.

**Files:**

- Modify: `.timeloop/runs/t27_base19_invariant_lift.py`
- Modify: `.timeloop/runs/t27_base19_invariant_lift_independent.py`
- Modify: `.timeloop/tests/test_lychrel_invariant_lift.py`
- Modify: `.timeloop/runs/t27_base19_invariant_lift.json`

**Interfaces:**

- Produces `scan_counterexamples(words, bases=range(41, 201))` and per-base
  records containing both encoding digests, exact status, and a decoded exact
  assignment for SAT. Produces
  `replay_assignment(base, equations, assignment) -> bool`.

- [ ] **Step 1: Write failing range, positive-control, and SAT-witness tests**

  ```python
  def test_counterexample_scan_is_inclusive_and_preserves_sat_witnesses() -> None:
      result = scan_counterexamples(fixture_words(), bases=range(41, 44))
      assert [item["base"] for item in result] == [41, 42, 43]
      sat = next(item for item in result if item["status"] == "SAT")
      assert replay_assignment(sat["base"], sat["assignment"])
  ```

  Add a base-17 positive control using the published T21 digits, and a fixture
  requiring the one-hot and compact encodings to agree on SAT/UNSAT.

- [ ] **Step 2: Run the scan tests and verify RED**

  Expected: failure naming `scan_counterexamples`.

- [ ] **Step 3: Implement the primary exact scan**

  Reuse `base17_reference_cycle`, `compile_one_hot_cnf`, and the existing
  compact binary encoder. Write both CNFs to temporary files and solve only
  `n=0` with CaDiCaL, strictly parsing `s` and `v` records. For each base in
  inclusive `41..200`, require decisive status agreement. On SAT, decode all
  497 digits and every Boolean carry, then make the assignment canonical by
  fixing semantic variables lexicographically to 0 whenever a repeated solve
  remains SAT. Replay every integer column, store that complete assignment, and
  stop the universal scan at that base.

- [ ] **Step 4: Reimplement the scan in the standalone checker**

  Extend the independent script with its own compact Boolean-digit encoding
  already patterned on T24's standalone audit, but copy no imports or code at
  runtime. Check base 17, then all reported negative bases; for a reported SAT
  base ignore the status claim and replay the serialized assignment directly.

- [ ] **Step 5: Set the theorem target from the result**

  If SAT occurs, set `gate_b.target = "exceptional_base_classification"`,
  `universal_claim = "FALSIFIED"`, and preserve the witness. If no SAT occurs,
  set `universal_claim = "UNRESOLVED"`; never set it to PROVED here.

- [ ] **Step 6: Run Task 7 tests GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  git add .timeloop/runs/t27_base19_invariant_lift.py \
    .timeloop/runs/t27_base19_invariant_lift_independent.py \
    .timeloop/runs/t27_base19_invariant_lift.json \
    .timeloop/tests/test_lychrel_invariant_lift.py
  git commit -m "exp: search higher bases for topology counterexamples"
  ```

### Task 8: Conditional symbolic-base certificate

**Gate:** Execute only when Gate A passes. If Task 7 finds SAT, classify the
exceptional base rather than attempting the falsified universal statement.

**Claim boundary:** For the exact T21 six-phase, two-interface incidence
topology with arbitrary fixed digits, repeat digits `0` and `b-1`, canonical
leading digits, and fresh Boolean carries, prove that base 17 is feasible and
every integer base `b >= 18` is infeasible at `n=0`. If this is falsified, the
replacement target is the exact feasible set for `b >= 18`, with constructive
assignments for feasible cases and algebraic infeasibility certificates for
its complement. No other topology, repeat alphabet, or `n > 0` theorem enters.

**Files:**

- Modify: `.timeloop/lib/lychrel_invariant_certificate.py`
- Modify: `.timeloop/runs/t27_base19_invariant_lift.py`
- Modify: `.timeloop/runs/t27_base19_invariant_lift_independent.py`
- Modify: `.timeloop/tests/test_lychrel_invariant_lift.py`
- Modify: `.timeloop/runs/t27_base19_invariant_lift.json`

**Interfaces:**

- Produces `AffineForm(slope, intercept)`, `BaseInterval(lower, upper=None)`,
  `SymbolicRow(relation, terms, constant, modulus=None)`,
  `AlgebraicWitness(kind, combinations, conclusion)`,
  `transport_to_t21`, `lift_gate_a_certificate`, `partition_base_cases`, and
  `check_algebraic_witness`.

- [ ] **Step 1: Write failing exact affine and interval tests**

  ```python
  def test_tail_sign_is_proved_from_affine_coefficients() -> None:
      form = AffineForm(slope=3, intercept=-50)
      assert form.minimum_on(BaseInterval(lower=18, upper=None)) == 4


  def test_farkas_witness_replays_to_contradiction() -> None:
      rows = (
          SymbolicRow("le", (("x", AffineForm(0, 1)),), AffineForm(0, 0)),
          SymbolicRow("le", (("x", AffineForm(0, -1)),), AffineForm(0, -1)),
      )
      witness = AlgebraicWitness(
          kind="farkas", combinations=((0, Fraction(1)), (1, Fraction(1))),
          conclusion=SymbolicRow("le", (), AffineForm(0, -1)),
      )
      assert check_algebraic_witness(rows, witness, BaseInterval(18, None))
  ```

  Add modular-combination tests, a bad multiplier mutation, overlapping or
  gapped intervals, and an affine form whose sign changes inside the interval.

- [ ] **Step 2: Run symbolic tests and verify RED**

  Expected: failures naming the symbolic certificate types.

- [ ] **Step 3: Transport the invariant to the exact T21 topology at base 19**

  Rebuild the original T21 base-19 equations with phase-zero fragment lengths
  `(28,23,31)` and the other five phases `(29,23,31)`. Map the two shifted
  phase-zero fixed occurrences back across the first interface, recompute
  radial layers and variable maps, and attempt to replay or locally resynthesize
  every Gate A predicate within the unchanged grammar. Require initiation, all
  transfers, terminal exclusion, and tenfold compression for this transported
  base-19 certificate. A failure records `topology_transport_failure` and stops
  Gate B; it is not evidence against a symbolic theorem by another method.

- [ ] **Step 4: Lift transported syntax without assuming it remains valid**

  Replace base-19 coefficients and digit bounds by affine forms in `b`; keep
  carry bounds Boolean and repeat digits `0` and `b-1`. For each Gate A atom,
  derive a candidate symbolic atom from its recorded parent equations. If no
  derivation exists, mark that atom `not_lifted` and stop that branch rather
  than guessing a modulus or constant.

- [ ] **Step 5: Build finite interval cases from actual sign changes**

  Collect integer roots of every affine coefficient, bound, and witness
  conclusion. Partition `b >= 18` at those roots into disjoint inclusive
  intervals. Merge adjacent intervals only when their normalized obligations
  and witness hashes are identical. Reject a partition with a gap, overlap, or
  number of cases increasing after the upper counterexample-search bound is
  doubled from 200 to 400.

- [ ] **Step 6: Attach exact algebraic witnesses**

  For each negated initiation, consecution, or exclusion branch, attach either:

  - a Farkas combination with nonnegative rational multipliers whose exact row
    sum has zero variable coefficients and a contradictory affine constant
    throughout the interval; or
  - an integer row combination producing `0 congruent r (mod m)` with
    `r % m != 0` throughout the interval.

  Store parent row hashes, exact numerator/denominator pairs, the normalized
  conclusion, and the interval. Do not accept sampled evaluation as a witness.

- [ ] **Step 7: Verify the positive and boundary cases concretely**

  Require the published base-17 witness to satisfy every column. Instantiate
  every finite singleton/boundary base in both the existing one-hot and compact
  encodings and require status agreement with the symbolic case. The tail case
  is accepted only by algebraic witness replay, not enumeration.

- [ ] **Step 8: Enforce the symbolic stop conditions**

  Set Gate B PASS only when cases cover every integer `b >= 18`, every witness
  replays in the standalone checker without invoking Z3 or CaDiCaL, all required
  concrete boundary cases agree in both encodings, and base 17 passes.
  Otherwise set STOP with one of:
  `topology_transport_failure`, `unlifted_gate_a_atom`,
  `nonclosing_case_partition`,
  `algebraic_witness_failure`, `checker_disagreement`, or
  `counterexample_found`. Preserve the strongest narrower exact result.

- [ ] **Step 9: Run Task 8 tests GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  git add .timeloop/lib/lychrel_invariant_certificate.py \
    .timeloop/runs/t27_base19_invariant_lift.py \
    .timeloop/runs/t27_base19_invariant_lift_independent.py \
    .timeloop/runs/t27_base19_invariant_lift.json \
    .timeloop/tests/test_lychrel_invariant_lift.py
  git commit -m "exp: attempt symbolic lift of base19 invariant"
  ```

### Task 9: Durable conclusion and full verification

**Files:**

- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `.timeloop/runs/t27_base19_invariant_lift.json`
- Modify: this plan to mark executed steps

**Interfaces:**

- Consumes the final primary evidence and standalone audit.
- Produces one scope-calibrated conclusion: Gate A STOP, Gate A PASS with Gate B
  STOP, universal topology theorem, or exact exceptional-base classification.

- [ ] **Step 1: Regenerate and independently replay the final artifact**

  ```bash
  uv run --extra exact python \
    .timeloop/runs/t27_base19_invariant_lift.py --final \
    > /tmp/t27-final.json
  python3 -I .timeloop/runs/t27_base19_invariant_lift_independent.py \
    publication/base19-radial/instance/equations.json \
    /tmp/t27-final.json > /tmp/t27-final-audit.json
  ```

  Attach the audit, rerun both programs, and require byte-identical evidence
  after stripping only a documented `runtime_seconds` field; preferably omit
  that field entirely.

- [ ] **Step 2: Write the notebook result at the exact achieved boundary**

  Add a `T27` section with `STATUS`, `CLAIM`, `FALSIFIABLE MILESTONE`,
  `INDEPENDENT CHECK`, `COMPRESSION`, `STOP CONDITION`, `LIMITATIONS`, and
  `NEXT`. State explicitly that Prism outputs supplied no mathematical premise,
  the Lean bridge was not required, and the result concerns only the exact T21
  topology when Gate B is discussed.

- [ ] **Step 3: Run focused and regression verification**

  ```bash
  uv run --extra exact --extra dev python -m py_compile \
    .timeloop/lib/lychrel_invariant_certificate.py \
    .timeloop/runs/t27_base19_invariant_lift.py \
    .timeloop/runs/t27_base19_invariant_lift_independent.py
  python3 -m json.tool .timeloop/runs/t27_base19_invariant_lift.json >/dev/null
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_invariant_lift.py \
    .timeloop/tests/test_lychrel_interface_cores.py \
    .timeloop/tests/test_lychrel_arbitrary_topology.py -q
  git diff --check
  ```

  Expected: compilation and JSON validation succeed, all focused and adjacent
  regressions pass, and `git diff --check` emits no output.

- [ ] **Step 4: Verify preservation boundaries**

  Run `git status --short` and compare the preprint ZIP SHA-256 with
  `e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33`.
  Ensure `.timeloop/exam/results.jsonl`, publication deletions, untracked
  `preprint/`, and all `.DS_Store` files remain outside every T27 commit.

- [ ] **Step 5: Commit the final evidence and notebook**

  ```bash
  git add .timeloop/runs/t27_base19_invariant_lift.json \
    .timeloop/notebook/lychrel-bases.md \
    docs/superpowers/plans/2026-08-09-base19-invariant-lift.md
  git commit -m "docs: record base19 invariant lift outcome"
  ```
