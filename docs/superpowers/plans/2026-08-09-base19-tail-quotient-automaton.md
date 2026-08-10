# T28 Base-19 Tail Quotient Automaton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Execute inline without subagents.

**Goal:** Either produce an independently replayed symbolic quotient automaton
for the frozen base-19 obstruction from layer 31 through layer 32 and then
extend it backward through layer 25, or stop at the first exact, readability,
or assurance failure with a deterministic counterexample.

**Architecture:** A strict decision-DAG certificate classifies bounded radial
frontier states into live, dead, terminal, or outside classes. Reachable-state
successor signatures propose the quotient; a counterexample-guided synthesizer
builds readable guards; exact local equations verify every class and edge over
the complete bounded domain. A standalone standard-library checker separately
parses the frozen equations and certificate and replays the achieved claim.

**Tech Stack:** Python 3.13 via `uv`, immutable dataclasses, exact integer
arithmetic, `z3-solver` 5.x for primary synthesis and universal checks, Python
standard-library constraint propagation and backtracking for independent
replay, pytest 8.x, Ruff, deterministic canonical JSON, and SHA-256.

## Global Constraints

- Preserve `.timeloop/exam/results.jsonl` and every unrelated user change.
- Do not modify `publication/base19-radial/preprint/`,
  `publication/base19-radial/preprint.zip`, or publication sources. The ZIP
  preservation digest is
  `e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33`.
- Treat the promoted 408-equation obstruction, removed coordinate
  `phase=0,n=0,column=82`, frontier, and T27 terminal lemma as frozen inputs.
- Require content digests
  `ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040`
  for equations,
  `0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0`
  for the frontier, and
  `cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302`
  for selected provenances. Require raw SHA-256
  `32324c40903b78aec4d787b7e64a6d73d0999e3846d91ca1340c99f8ac2d8686`
  for `.timeloop/runs/t27_base19_invariant_lift.json`.
- Reuse T27's arithmetic atom grammar exactly: coefficients
  `{-3,-2,-1,0,1,2,3}` and congruence moduli `2..20`. Do not enlarge it after
  a failed synthesis.
- Permit at most eight semantic classes and 64 unique decision nodes per
  synthesized layer, and at most ten atom tests on a synthesized evaluation
  path. The frozen layer-32 seed alone retains T27's 12-atom conjunction cap.
- Treat successor-signature partitions, SMT models, quantifier elimination,
  and Prism/literature frames only as hypothesis generators. Exact primary and
  independent checks are authoritative.
- Fail closed on UNKNOWN, malformed syntax, digest mismatch, an unclassified
  promoted state, an invalid live/dead claim, a forbidden successor, a missing
  edge witness, an unsupported atom, or checker disagreement.
- The independent checker imports no repository module, solver package, T24,
  T25, T26, T27, T28, frontier, topology, or synthesis code.
- The first research gate ends at the four-class layer-31 certificate. Do not
  attempt layer 30 unless that certificate passes both verification routes.
- Extend layers sequentially `30,29,28,27,26,25`; never skip a failed layer.
- A PASS requires the canonical guards-and-edges core for the maximal achieved
  interval to be smaller than the canonical explicit state-and-transition
  table it replaces. Witnesses and audit metadata are excluded from this byte
  comparison but remain in the durable artifacts.
- Do not extend toward layer 0, lift symbolically in `b`, compare base 17 with
  base 19, scan other topologies, or resume the Lean bridge in T28.
- A stopped bounded search is not evidence that no readable invariant exists.
- Budget hours to roughly two focused research days for the complete round.
  Checkpoint after every layer and do not buy more time by enlarging the grammar,
  readability limits, topology scope, or claim boundary.

## File Map

- Create `.timeloop/lib/lychrel_quotient_automaton.py` — immutable class,
  decision-DAG, witness, and certificate syntax; strict parsing; evaluation;
  readability metrics; and canonical core serialization.
- Create `.timeloop/runs/t28_base19_tail_quotient.py` — frozen T28 input adapter,
  reachable quotient discovery, exact Z3 verifier, guard synthesis, sequential
  gate orchestration, deterministic evidence generation, and human report.
- Create `.timeloop/runs/t28_base19_tail_quotient_independent.py` — isolated
  standard-library parser, local constraint builder, certificate verifier,
  mutation rejection entry point, and canonical audit output.
- Create `.timeloop/tests/test_lychrel_quotient_automaton.py` — syntax,
  discovery, exact-obligation, synthesis, real-fixture, isolation, mutation,
  determinism, and gate tests.
- Conditionally create
  `.timeloop/runs/t28_base19_tail_quotient_certificate.json` — exported
  machine-readable certificate for the maximal primary PASS interval.
- Create `.timeloop/runs/t28_base19_tail_quotient.json` — primary evidence,
  exact achieved boundary, counters, counterexample or certificate digest,
  measurements, and limitations.
- Create `.timeloop/runs/t28_base19_tail_quotient_independent.json` — isolated
  audit bound to the primary evidence and optional certificate digests.
- Create `.timeloop/runs/t28_base19_tail_quotient_report.md` — deterministic
  human-readable guards, live/dead status, edges, witnesses, representative
  promoted states, measurements, and first failed obligation.
- Modify `.timeloop/notebook/lychrel-bases.md` — scope-calibrated T28 result and
  next research decision.
- Modify this plan only at the final task to record which conditional tasks ran
  and their measured outcomes.

---

### Task 1: Strict quotient-automaton certificate language

**Files:**

- Create: `.timeloop/lib/lychrel_quotient_automaton.py`
- Create: `.timeloop/tests/test_lychrel_quotient_automaton.py`

**Interfaces:**

- Consumes `LinearAtom` and `canonical_bytes` from
  `.timeloop/lib/lychrel_invariant_certificate.py` without modifying the T27
  certificate schema.
- Produces frozen `ClassSpec(label, kind, allowed_next)`,
  `DecisionNode(node_id, atom, when_true, when_false)`,
  `LayerQuotient(layer, variables, root, classes, nodes)`,
  `EdgeWitness(source_layer, source_class, target_class, input_state,
  output_state, local_state)`, and `QuotientCertificate(schema, base, removed,
  source_digests, start_layer, layers, witnesses)`.
- Produces `classify_state(layer, assignment) -> str`, where results are a class
  label or the literal string `outside`; `parse_quotient_certificate(payload)`;
  `layer_path_depth(layer) -> int`; and
  `certificate_core_payload(certificate) -> dict[str, object]`.
- Branch targets serialize as `node:<nonnegative integer>`, `class:<label>`, or
  `outside`. Node IDs are contiguous `0..n-1`; node branches may reference only
  a larger node ID. This makes acyclicity directly checkable.

- [ ] **Step 1: Write the failing decision-DAG evaluation tests**

  ```python
  def test_decision_dag_classifies_two_classes_and_outside() -> None:
      layer = LayerQuotient(
          layer=31,
          variables=("x",),
          root="node:0",
          classes=(
              ClassSpec("DEAD", "dead", ()),
              ClassSpec("P0", "live", ("T0",)),
          ),
          nodes=(
              DecisionNode(
                  0,
                  LinearAtom("le", (("x", 1),), 0),
                  "class:DEAD",
                  "node:1",
              ),
              DecisionNode(
                  1,
                  LinearAtom("le", (("x", 1),), 1),
                  "class:P0",
                  "outside",
              ),
          ),
      )

      assert classify_state(layer, {"x": 0}) == "DEAD"
      assert classify_state(layer, {"x": 1}) == "P0"
      assert classify_state(layer, {"x": 2}) == "outside"
      assert layer_path_depth(layer) == 2
  ```

  Add parameterized rejection tests for a backward/self node edge, missing
  node, unreachable node, repeated `(atom,true,false)` node, equal branches,
  unknown class leaf, duplicate class label, unsupported class kind, live class
  with no allowed edge, dead/terminal class with an edge, more than eight
  classes, more than 64 nodes, a synthesized layer deeper than ten, a missing
  assignment, and a non-integer assignment.

- [ ] **Step 2: Run the focused tests and verify RED**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py -q \
    -k 'decision_dag or rejects'
  ```

  Expected: collection fails because `lychrel_quotient_automaton` does not
  exist.

- [ ] **Step 3: Implement immutable syntax and structural validation**

  Accept class kinds exactly `live`, `dead`, and `terminal`. Require labels to
  match `[A-Z][A-Z0-9_]*`. Sort classes by label and witnesses by
  `(source_layer,source_class,target_class,input_state,output_state,local_state)`.
  Each witness assignment is a variable-sorted tuple of `(name,value)` pairs;
  `local_state` contains every equation variable not present on either
  frontier. Preserve node order by ID. Reject JSON booleans wherever an integer
  is required.

  Validate branch targets with:

  ```python
  def target_kind(target: str) -> tuple[str, str]:
      if target == "outside":
          return ("outside", "")
      kind, separator, value = target.partition(":")
      if separator != ":" or kind not in {"node", "class"} or not value:
          raise ValueError(f"invalid decision target: {target}")
      return kind, value
  ```

  A layer is structurally total because every internal node has two targets and
  every path ends in a known class leaf or `outside`. Reject any unreachable
  node and any node whose two branches are identical. Reject duplicate
  `(atom,when_true,when_false)` triples as an unreduced DAG.

  At certificate level require `start_layer` in `25..31`, one contiguous layer
  sequence from `start_layer` through 32, and only terminal classes at layer 32.
  Every live `allowed_next` label must exist in the following layer. Require
  exactly one canonical witness for every declared edge and no witness for an
  undeclared edge; semantic validity of each witness remains Task 3's job.

- [ ] **Step 4: Implement exact evaluation and readability metrics**

  Evaluate an atom with integer sums and Python modular arithmetic, following
  at most `len(nodes)` branches. Compute maximum path depth recursively with a
  memo indexed by node ID. Enforce depth at construction only for synthesized
  layers below 32: at most 10. The frozen layer-32 seed is exempt from the
  decision-path cap; validate instead that each source T27 conjunction contains
  at most 12 atoms before compiling their shared DAG.

- [ ] **Step 5: Implement strict schema parsing and canonical core output**

  Accept only schema `t28-tail-quotient-certificate-v1` and exact object keys.
  `certificate_core_payload` returns only `start_layer` and each layer's number,
  variables, classes, root, and nodes; exclude source paths, hashes, witnesses,
  obligation results, status, and runtime metadata. Round-trip parsing must
  reproduce identical canonical bytes.

- [ ] **Step 6: Write and pass round-trip, witness, and canonical-size tests**

  ```python
  def test_certificate_round_trip_preserves_canonical_core() -> None:
      certificate = quotient_fixture_certificate()
      parsed = parse_quotient_certificate(certificate.to_payload())
      assert canonical_bytes(parsed) == canonical_bytes(certificate)
      assert certificate_core_payload(parsed) == certificate_core_payload(certificate)
  ```

  The fixture contains one dead class, one live class, a terminal next layer,
  and one exact edge witness. Add mutations for an unknown witness class, a
  witness on an undeclared edge, a wrong source-state width, a wrong output-state
  width, an incomplete or overlapping local assignment, an invalid digest, and
  an extra JSON key.

- [ ] **Step 7: Run Task 1 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py -q
  git add .timeloop/lib/lychrel_quotient_automaton.py \
    .timeloop/tests/test_lychrel_quotient_automaton.py
  git commit -m "feat: define radial quotient automaton certificates"
  ```

### Task 2: Frozen T28 adapter and reachable quotient hypotheses

**Files:**

- Create: `.timeloop/runs/t28_base19_tail_quotient.py`
- Modify: `.timeloop/tests/test_lychrel_quotient_automaton.py`

**Interfaces:**

- Consumes `load_promoted_inputs`, `canonicalize_state`, `GrammarLimits`, and
  `synthesize_terminal_predicate` from
  `.timeloop/runs/t27_base19_invariant_lift.py` in the primary route only.
- Produces frozen `T28Inputs(manifest, frontier, terminal_predicate,
  t27_evidence_sha256)`, `CandidateClass(label, allowed_next, members)`, and
  `CandidatePartition(layer, variables, classes)`.
- Produces `load_t28_inputs(root) -> T28Inputs`,
  `build_terminal_seed(inputs) -> LayerQuotient`,
  `discover_reachable_quotient(inputs, start_layer=25, end_layer=32)
  -> tuple[CandidatePartition, ...]`, and
  `explicit_relation_payload(inputs, start_layer, end_layer)
  -> dict[str, object]`.

- [ ] **Step 1: Write failing real-evidence identity and terminal-seed tests**

  ```python
  def test_t28_inputs_bind_the_frozen_t27_tail() -> None:
      inputs = load_t28_inputs(ROOT)
      assert inputs.manifest.content_sha256 == EQUATIONS_CONTENT_SHA256
      assert inputs.frontier.content_sha256 == FRONTIER_CONTENT_SHA256
      assert inputs.frontier.provenances_sha256 == PROVENANCES_SHA256
      assert inputs.t27_evidence_sha256 == T27_EVIDENCE_SHA256

      seed = build_terminal_seed(inputs)
      layer32 = inputs.frontier.layers_by_number[32]
      labels = [
          classify_state(seed, canonicalize_state(layer32, "output", state))
          for state in layer32.output_states
      ]
      assert sorted(labels.count(label) for label in set(labels)) == [6, 8, 8]
      assert "outside" not in labels
  ```

  Define the four digest constants in the test from Global Constraints. Add a
  copied temporary T27 evidence file with one changed byte and require
  `load_t28_inputs` to reject it before quotient discovery.

- [ ] **Step 2: Run the adapter tests and verify RED**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py -q \
    -k 't28_inputs or terminal_seed'
  ```

  Expected: import fails because the T28 runner does not exist.

- [ ] **Step 3: Implement the frozen adapter and named terminal seed**

  Recompute the raw T27 evidence hash with `hashlib.sha256(path.read_bytes())`.
  Reuse T27's strict parsers for the equation/frontier content hashes. Rebuild
  the three terminal clauses through `synthesize_terminal_predicate`; do not
  deserialize them as trusted proof from the T27 result JSON.

  Name the clause containing the modulus-19 atom `T_RESIDUE`, the clause
  containing the constant-13 four-term equality `T_PHASE_ZERO`, and the clause
  containing the constant-14 `D0` equality `T_HIGH_DIGIT`. Compile the ordered
  clauses into one decision DAG whose effective leaves are those three class
  labels or `outside`. Mark all three classes `terminal` and require exact
  reachable coverage counts 6, 8, and 8.

- [ ] **Step 4: Implement recursive reachable successor signatures**

  For a promoted output state at layer `l`, locate the identical input state in
  `frontier.layers_by_number[l + 1].transitions`. Classify every recorded output
  at `l + 1`, discard duplicate labels, sort the remaining labels, and use the
  resulting tuple as the state's signature. The empty tuple is the dead
  signature. Any recorded successor classified `outside` fails discovery.

  At layer 32 use terminal labels directly. At each earlier layer group states
  by the complete signature and name classes in this order: `DEAD` for empty,
  then `Q00`, `Q01`, ... by lexicographically sorted nonempty signature. Preserve
  each class's signature as `allowed_next`.

- [ ] **Step 5: Write and pass the frozen quotient-count test**

  ```python
  def test_reachable_successor_quotient_reproduces_candidate_counts() -> None:
      partitions = discover_reachable_quotient(load_t28_inputs(ROOT), 25, 32)
      assert [
          (part.layer, sum(len(item.members) for item in part.classes), len(part.classes))
          for part in partitions
      ] == [
          (25, 20, 5), (26, 12, 5), (27, 12, 7), (28, 17, 7),
          (29, 16, 6), (30, 18, 5), (31, 18, 4), (32, 22, 3),
      ]
      layer31 = next(part for part in partitions if part.layer == 31)
      assert sorted(len(item.members) for item in layer31.classes) == [1, 2, 3, 12]
      assert sum(not item.allowed_next for item in layer31.classes) == 1
      assert all(len(item.allowed_next) == 1 for item in layer31.classes if item.allowed_next)
  ```

  This test promotes only the counts as reproducible repository evidence; it
  does not call them a symbolic theorem.

- [ ] **Step 6: Implement the explicit comparison payload**

  Serialize, for every source layer in the interval, canonical source states
  and every exact promoted edge to the next layer. Sort states and edges by
  integer tuples. Include no file path, digest, label, solver field, timestamp,
  or witness metadata. This is the sole denominator for T28 explanatory
  compression.

- [ ] **Step 7: Run Task 2 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  git add .timeloop/runs/t28_base19_tail_quotient.py \
    .timeloop/tests/test_lychrel_quotient_automaton.py
  git commit -m "feat: reproduce base19 tail quotient hypotheses"
  ```

### Task 3: Exact primary class, edge, and terminal verifier

**Files:**

- Modify: `.timeloop/runs/t28_base19_tail_quotient.py`
- Modify: `.timeloop/tests/test_lychrel_quotient_automaton.py`

**Interfaces:**

- Produces frozen `QuotientObligation(kind, layer, class_label, status,
  checked_count, counterexample)` and `QuotientCheck(status, obligations)`.
- Produces frozen `ExplicitTransfer(layer, input_variables, output_variables,
  source_domain, transitions)` and
  `check_explicit_layer(transfer, source_labels, target_labels, classes,
  witnesses) -> QuotientCheck` as the pure finite semantic core used by tests.
- Produces `check_reachable_coverage(inputs, layer)`,
  `check_layer_semantics(inputs, current, following, witnesses)`,
  `check_terminal_classes(inputs, terminal)`, and
  `check_quotient_certificate(inputs, certificate) -> QuotientCheck`.
- Counterexamples use canonical dictionaries and contain `input`, `output`, or
  both as required. UNKNOWN raises `EvidenceError`; it never becomes STOP or
  PASS silently.

- [ ] **Step 1: Write failing semantic-obligation tests on a finite fixture**

  Build a two-layer fixture with source domain `x in {0,1,2}`, target domain
  `y in {0,1}`, and exact relation `{0 -> (), 1 -> (0,), 2 -> (1,)}`. Use the
  same certificate evaluator as the real checker and a finite-relation adapter
  local to the test. Assert these exact cases:

  ```python
  def test_semantics_rejects_a_live_state_without_successor() -> None:
      check = check_explicit_layer(
          transfer=explicit_transfer_fixture(),
          source_labels={0: "LIVE", 1: "LIVE", 2: "outside"},
          target_labels={0: "T0", 1: "T1"},
          classes=(ClassSpec("LIVE", "live", ("T0",)),),
          witnesses=(),
      )
      assert check.status == "FAIL"
      assert check.obligations[-1].kind == "live_has_successor"
      assert check.obligations[-1].counterexample == {"input": {"x": 0}}
  ```

  Add separate tests for a dead state with a successor, a live state reaching a
  forbidden target, a declared edge without a witness, a witness not satisfying
  the relation, a promoted state routed outside, and a passing dead/live pair.
  `check_explicit_layer` is a pure testable semantic core; the Z3 route supplies
  the same queries over the real bounded relation.

- [ ] **Step 2: Run obligation tests and verify RED**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py -q \
    -k 'semantics or witness or promoted_state'
  ```

  Expected: failures naming the obligation result and checker functions.

- [ ] **Step 3: Implement the pure finite semantic core**

  Check obligations in fixed order: promoted coverage, dead has no successor,
  live has a successor, live has no forbidden successor, declared-edge witness,
  terminal exclusion. Sort classes and source states before checking and return
  the lexicographically first counterexample. A witness proves only that the
  declared quotient edge is realized somewhere; it does not replace universal
  source-class checks.

- [ ] **Step 4: Compile decision-DAG leaves into exact Z3 formulas**

  Build one formula per node in reverse ID order:

  ```python
  node_formula[node.node_id] = z3.If(
      z3_atom(node.atom, source_mapping, variables),
      target_code(node.when_true),
      target_code(node.when_false),
  )
  ```

  Assign distinct integer codes to sorted class labels and `-1` to `outside`.
  Rebuild local digit/carry domains and all layer equations directly from the
  T27 `EquationManifest`; do not use promoted transitions in universal checks.

- [ ] **Step 5: Implement universal bounded-domain obligations**

  For each dead class `q`, check `class_q(x) and T(x,y)` is UNSAT. For each live
  class, check `class_q(x) and not Exists(y,local,T(x,y))` is UNSAT after Z3's
  Presburger `qe` tactic removes the existential; independently replay any SAT
  counterexample in integer arithmetic. Check forbidden successors with
  `class_q(x) and T(x,y) and target(y) not in allowed_next(q)`. Check each edge
  witness by substituting its complete input, output, and local assignments into
  every domain and local equation. Require those three variable sets to be
  disjoint and their union to equal the transfer formula's complete variable
  set. Canonicalize SAT counterexamples one variable at a time as T27 does.

  Quantifier elimination is only a decision mechanism here. UNKNOWN, a formula
  that retains a quantifier, or a model that fails integer replay raises
  `EvidenceError`.

- [ ] **Step 6: Verify all three terminal classes separately**

  For each effective terminal leaf, check its full decision-DAG class formula
  against the exact 12 layer-33 equations over the complete
  `2^12 * 19^2 = 1,478,656` frontier domain. Require all three UNSAT. Also
  require the 22 promoted layer-32 states to be covered exactly once by the
  effective classifier.

- [ ] **Step 7: Run real terminal and synthetic obligation tests GREEN**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py -q \
    -k 'semantics or witness or terminal or coverage'
  ```

  Expected: all selected tests pass, including exact terminal exclusion.

- [ ] **Step 8: Commit the exact verifier**

  ```bash
  git add .timeloop/runs/t28_base19_tail_quotient.py \
    .timeloop/tests/test_lychrel_quotient_automaton.py
  git commit -m "feat: verify quotient automaton obligations exactly"
  ```

### Task 4: Counterexample-guided layer-31 guard synthesis

**Files:**

- Modify: `.timeloop/runs/t28_base19_tail_quotient.py`
- Modify: `.timeloop/tests/test_lychrel_quotient_automaton.py`

**Interfaces:**

- Produces frozen `GuardLimits(coefficients, moduli, max_classes=8,
  max_nodes=64, max_depth=10)`, `GuardCounterexample(state, rejected_class,
  reason)`, and `LayerSynthesis(status, layer, quotient, witnesses,
  iterations, candidate_atom_count, stop_reason, counterexample)`.
- Produces `derive_guard_atoms(partition, counterexamples, limits)`,
  `build_reduced_decision_dag(partition, atoms, limits)`, and
  `synthesize_layer(inputs, partition, following, limits) -> LayerSynthesis`.
- Produces `build_layer31_milestone(root) -> LayerSynthesis` as the first real
  research gate.
- Reuses T27's `separate_counterexample` only as a candidate-atom generator;
  every resulting DAG is checked by Task 3.

- [ ] **Step 1: Write failing deterministic learner tests**

  ```python
  def test_guard_learner_builds_a_reduced_two_class_dag() -> None:
      partition = candidate_partition_fixture(
          variables=("x", "y"),
          classes={"DEAD": ((0, 0), (0, 1)), "Q00": ((1, 0), (1, 1))},
          allowed_next={"DEAD": (), "Q00": ("T0",)},
      )
      learned = build_reduced_decision_dag(
          partition,
          atoms=(LinearAtom("eq", (("x", 1),), 0),),
          limits=GuardLimits(),
      )
      assert len(learned.nodes) == 1
      assert {classify_state(learned, {"x": x, "y": y}) for x, y in [(0, 0), (0, 1)]} == {"DEAD"}
      assert {classify_state(learned, {"x": x, "y": y}) for x, y in [(1, 0), (1, 1)]} == {"Q00"}
  ```

  Add tests that canonical input order gives byte-identical DAGs, identical
  subtrees are merged, an inseparable counterexample returns
  `guard_separator_not_found`, depth 11 returns `decision_depth_exceeded`, and
  65 reduced nodes return `decision_node_limit_exceeded`.

- [ ] **Step 2: Run learner tests and verify RED**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py -q -k 'learner or reduced'
  ```

  Expected: failures naming the guard synthesis interfaces.

- [ ] **Step 3: Generate a finite, deterministic atom pool**

  Seed the pool with all atoms from the frozen layer-32 clauses after mapping
  shared variables where possible. For each candidate class, call
  `separate_counterexample` on its complete promoted members and every promoted
  member of another class. Add separators for each universal counterexample as
  it appears. Optionally run Z3 `qe` on the exact weakest-preimage formula and
  parse only affine equalities, inequalities, and congruences already inside
  the frozen grammar. Reject every other generated expression. Canonicalize and
  deduplicate the pool by `canonical_bytes`.

- [ ] **Step 4: Build and reduce the multiclass decision tree**

  Recursively choose the atom that first minimizes the number of conflicting
  label pairs, then the larger branch size, support size, absolute coefficient
  sum, relation rank, modulus, and canonical bytes. A leaf is legal only when
  all required promoted examples at that branch share one label; an empty
  branch becomes `outside`. Hash-cons identical subtrees into a DAG, assign
  forward node IDs in preorder, and revalidate the 64-node/10-depth caps.

- [ ] **Step 5: Refine only from exact semantic counterexamples**

  Run Task 3's universal checker. If state `x` is classified as `q` but violates
  `q`'s live/dead or allowed-successor semantics, add
  `GuardCounterexample(x,q,kind)`, derive an atom true on all promoted members
  of `q` and false on `x`, rebuild, and rerun the complete layer check. Reject
  repeated counterexamples by canonical digest. Stop with
  `guard_separator_not_found`, `decision_depth_exceeded`,
  `decision_node_limit_exceeded`, or `counterexample_cycle` rather than changing
  the arithmetic grammar.

- [ ] **Step 6: Extract and verify quotient-edge witnesses**

  For each declared `(source_class,target_class)` edge, ask the exact local
  solver for the lexicographically first model satisfying both class formulas.
  Serialize complete canonical input/output assignments plus every internal
  local variable assignment, replay all equations with integers, then rerun the
  full verifier with the witnesses attached.

- [ ] **Step 7: Add the falsifiable real layer-31 experiment test**

  ```python
  def test_layer31_experiment_has_a_scoped_exact_outcome() -> None:
      result = build_layer31_milestone(ROOT)
      assert result.status in {"PASS", "STOP"}
      if result.status == "PASS":
          assert result.quotient is not None
          assert len(result.quotient.classes) == 4
          assert result.stop_reason is None
          assert result.counterexample is None
      else:
          assert result.quotient is None
          assert result.stop_reason in {
              "guard_separator_not_found",
              "decision_depth_exceeded",
              "decision_node_limit_exceeded",
              "counterexample_cycle",
          }
          assert result.counterexample is not None
  ```

  `build_layer31_milestone` must always reproduce 18 promoted states, the class
  member sizes `1,2,3,12`, and the three verified terminal classes before
  returning either outcome.

- [ ] **Step 8: Run Task 4 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py -q
  git add .timeloop/runs/t28_base19_tail_quotient.py \
    .timeloop/tests/test_lychrel_quotient_automaton.py
  git commit -m "exp: synthesize base19 layer31 quotient guards"
  ```

### Task 5: Deterministic primary layer-31 gate

**Files:**

- Modify: `.timeloop/runs/t28_base19_tail_quotient.py`
- Modify: `.timeloop/tests/test_lychrel_quotient_automaton.py`

**Interfaces:**

- Produces `build_primary(root, through_layer=31) -> dict[str, object]` and CLI
  `--through-layer 31 --evidence PATH --certificate PATH --report PATH`.
- Produces `decide_primary_gate(baseline, layer_result)
  -> tuple[dict[str, object], QuotientCertificate | None]` as the sole
  fail-closed transition into independent assurance.
- Primary evidence schema is `t28-base19-tail-quotient-evidence-v1`; certificate
  schema is `t28-tail-quotient-certificate-v1`.
- A primary PASS contains a certificate SHA-256, obligation counts, witness
  count, class/node/depth measurements, candidate partition counts, and
  limitations. A primary STOP contains the first deterministic counterexample
  and no certificate claim.

- [ ] **Step 1: Write failing gate-shape and fail-closed tests**

  ```python
  def test_primary_gate_never_promotes_a_failed_layer31_result() -> None:
      evidence, certificate = decide_primary_gate(
          baseline=baseline_fixture(),
          layer_result=failed_layer_fixture("guard_separator_not_found"),
      )
      assert evidence["status"] == "STOP"
      assert evidence["stop_layer"] == 31
      assert evidence["stop_reason"] == "guard_separator_not_found"
      assert certificate is None
      assert "certificate_sha256" not in evidence
  ```

  Add cases for UNKNOWN, digest mismatch, wrong four-class count, a failed
  terminal class, missing witness, and PASS. Every failed case omits claims
  about lower layers, other bases, topology classification, and Lean.

- [ ] **Step 2: Run gate tests and verify RED**

  Expected: failure naming `decide_primary_gate` and `build_primary`.

- [ ] **Step 3: Assemble deterministic primary evidence**

  Bind all four frozen hashes, candidate counts for layers 25--32, Prism's
  fail-closed status string from the approved design, exact grammar limits,
  synthesis counters, class obligations, terminal obligations, and witnesses.
  Serialize counterexamples and limitations in fixed order. Omit wall-clock
  time, solver seeds, temporary paths, and platform-dependent metadata.

  Render a Markdown report from the same in-memory result. For every attempted
  layer list variables, class labels and kinds, the decision DAG as nested
  `if <affine atom>` expressions, outgoing edges, exact witness assignments,
  representative promoted members, node count, maximum path, and obligations.
  A STOP report ends with the exact counterexample and never presents an
  unverified candidate guard as a theorem.

- [ ] **Step 4: Run the primary milestone twice**

  ```bash
  uv run --extra exact python \
    .timeloop/runs/t28_base19_tail_quotient.py \
    --through-layer 31 \
    --evidence /tmp/t28-layer31-a.json \
    --certificate /tmp/t28-layer31-a-certificate.json \
    --report /tmp/t28-layer31-a-report.md
  uv run --extra exact python \
    .timeloop/runs/t28_base19_tail_quotient.py \
    --through-layer 31 \
    --evidence /tmp/t28-layer31-b.json \
    --certificate /tmp/t28-layer31-b-certificate.json \
    --report /tmp/t28-layer31-b-report.md
  cmp -s /tmp/t28-layer31-a.json /tmp/t28-layer31-b.json
  cmp -s /tmp/t28-layer31-a-report.md /tmp/t28-layer31-b-report.md
  ```

  If status is PASS, also require the two certificate files byte-identical. If
  status is STOP, require neither command to leave a certificate file. Preserve
  the first result in `/tmp`; durable artifacts are written only after Task 6.

- [ ] **Step 5: Run Task 5 tests GREEN and commit code only**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py -q
  git add .timeloop/runs/t28_base19_tail_quotient.py \
    .timeloop/tests/test_lychrel_quotient_automaton.py
  git commit -m "exp: decide base19 layer31 quotient gate"
  ```

### Task 6: Standalone layer-31 reconstruction and assurance checkpoint

**Files:**

- Create: `.timeloop/runs/t28_base19_tail_quotient_independent.py`
- Modify: `.timeloop/tests/test_lychrel_quotient_automaton.py`
- Create: `.timeloop/runs/t28_base19_tail_quotient.json`
- Conditionally create:
  `.timeloop/runs/t28_base19_tail_quotient_certificate.json`
- Create: `.timeloop/runs/t28_base19_tail_quotient_independent.json`
- Create: `.timeloop/runs/t28_base19_tail_quotient_report.md`

**Interfaces:**

- Command:
  `python3 -I t28_base19_tail_quotient_independent.py EQUATIONS FRONTIER EVIDENCE [CERTIFICATE]`.
- Produces schema `t28-base19-tail-quotient-independent-v1` with source hashes,
  rebuilt tail counts, primary-evidence hash, optional certificate hash, exact
  obligation counts, mutation scope, `repository_imports: []`, and status
  `PASS`, `STOP`, or `REJECT`.

- [ ] **Step 1: Write failing isolated positive and mutation tests**

  ```python
  def test_independent_checker_runs_in_isolated_mode(tmp_path: Path) -> None:
      checker = tmp_path / "checker.py"
      shutil.copy(INDEPENDENT, checker)
      completed = subprocess.run(
          (
              sys.executable, "-I", str(checker), str(EQUATIONS), str(FRONTIER),
              str(FIXTURE_EVIDENCE), str(FIXTURE_CERTIFICATE),
          ),
          cwd=tmp_path,
          check=True,
          text=True,
          capture_output=True,
      )
      audit = json.loads(completed.stdout)
      assert audit["status"] == "PASS"
      assert audit["repository_imports"] == []
  ```

  Add isolated mutations for one guard atom, class label, live/dead status,
  required edge, witness value, terminal law, evidence digest, and certificate
  digest. Each mutation must exit nonzero, print `REJECT:` on stderr, and emit
  no JSON containing `"status":"PASS"`.

- [ ] **Step 2: Run isolation tests and verify RED**

  Expected: copy fails because the independent checker does not exist.

- [ ] **Step 3: Reimplement strict parsing without repository imports**

  Use only `argparse`, `dataclasses`, `hashlib`, `itertools`, `json`, `re`, and
  `sys`. Recompute equation/frontier content hashes and raw evidence/certificate
  hashes. Duplicate the small atom and decision-DAG evaluators intentionally.
  Reject extra keys, booleans-as-integers, noncanonical targets, cycles,
  unreachable nodes, unsupported coefficients/moduli, width errors, and all
  source-identity mismatches.

- [ ] **Step 4: Rebuild layers 31--33 from exact equations**

  Parse selected provenances and original frontier variable names. Build each
  equation's allowed tuples over carry domains `{0,1}`, ordinary digit domains
  `0..18`, and canonical leading digit domains `1..18`. Use generalized arc
  consistency, branch on the lexicographically first smallest non-singleton
  domain, and memoize canonical residual-domain tuples. Reproduce the promoted
  layer counts `(18,18,22,0)` for source layer 30 through terminal layer 33 and
  the stored output-state digests before reading semantic claims.

- [ ] **Step 5: Replay the exact achieved boundary**

  For a primary PASS, enumerate the complete source frontier domain for every
  certificate layer, classify it, and use the independently built constraint
  system to check dead, live-existence, forbidden-successor, edge-witness, and
  terminal obligations. For a primary STOP, verify the frozen quotient counts,
  grammar/readability limits, and the serialized counterexample against the
  exact local equations; report STOP without claiming synthesis impossibility.

- [ ] **Step 6: Run the real independent audit and mutation suite**

  If `/tmp/t28-layer31-a.json` is PASS:

  ```bash
  python3 -I .timeloop/runs/t28_base19_tail_quotient_independent.py \
    publication/base19-radial/instance/equations.json \
    publication/base19-radial/certificates/minimal-core-frontier.json \
    /tmp/t28-layer31-a.json \
    /tmp/t28-layer31-a-certificate.json \
    > /tmp/t28-layer31-independent.json
  ```

  If it is STOP, omit the certificate argument. Then run the real-artifact
  mutation test selected by `pytest -k 'independent_real_mutation'`. Require
  independent status to equal primary status; any disagreement changes the
  durable status to STOP with `primary_independent_disagreement`.

- [ ] **Step 7: Materialize and validate the layer-31 artifacts**

  Copy the first primary evidence, report, and independent audit into their
  durable paths. Copy the certificate only for joint PASS. Validate all
  materialized JSON with `python3 -m json.tool`, rerun the independent checker
  on the durable paths, and require byte-identical audit output.

- [ ] **Step 8: Apply the mandatory checkpoint**

  If joint status is not PASS, skip Task 7 and continue at Task 8. Record the
  exact stop reason and counterexample without enlarging the grammar. If joint
  status is PASS, Task 7 is authorized; no lower layer is yet claimed.

- [ ] **Step 9: Run Task 6 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py -q
  git add .timeloop/runs/t28_base19_tail_quotient_independent.py \
    .timeloop/runs/t28_base19_tail_quotient.json \
    .timeloop/runs/t28_base19_tail_quotient_independent.json \
    .timeloop/runs/t28_base19_tail_quotient_report.md \
    .timeloop/tests/test_lychrel_quotient_automaton.py
  ```

  For joint PASS, also add
  `.timeloop/runs/t28_base19_tail_quotient_certificate.json`. Commit with:

  ```bash
  git commit -m "exp: independently audit base19 layer31 quotient"
  ```

### Task 7: Conditional sequential extension through layer 25

**Claim boundary:** This task extends only the exact tail lemma for the same
frozen base-19 obstruction. It does not remove the promoted-reachability premise
or create a new end-to-end proof of the 408 equations.

**Files:**

- Modify: `.timeloop/runs/t28_base19_tail_quotient.py`
- Modify: `.timeloop/runs/t28_base19_tail_quotient_independent.py`
- Modify: `.timeloop/tests/test_lychrel_quotient_automaton.py`
- Modify: `.timeloop/runs/t28_base19_tail_quotient.json`
- Modify: `.timeloop/runs/t28_base19_tail_quotient_certificate.json`
- Modify: `.timeloop/runs/t28_base19_tail_quotient_independent.json`
- Modify: `.timeloop/runs/t28_base19_tail_quotient_report.md`

**Interfaces:**

- Extends `build_primary(root, through_layer)` and the independent CLI to any
  `through_layer` in `25..31`, where the value is the earliest source layer in
  the current tail.
- Produces `decide_extension(passed_layers, next_result) -> dict[str, object]`
  as the sole sequential extension gate.
- Produces one `LayerSynthesis` and one primary/independent layer audit per
  attempted extension, ordered `30,29,28,27,26,25`.

- [ ] **Step 1: Write the failing sequential-gate tests**

  ```python
  def test_extension_stops_at_the_first_failed_layer() -> None:
      decision = decide_extension(
          passed_layers=(31, 30),
          next_result=failed_layer_fixture("decision_node_limit_exceeded", layer=29),
      )
      assert decision["status"] == "STOP"
      assert decision["achieved_start_layer"] == 30
      assert decision["stop_layer"] == 29
      assert decision["stop_reason"] == "decision_node_limit_exceeded"
      assert decision["attempted_layers"] == [31, 30, 29]
  ```

  Add tests that layer 30 cannot run without joint layer-31 PASS, no layer may
  be skipped, nine classes stop with `class_limit_exceeded`, depth/node limits
  stop at the responsible layer, and a checker disagreement preserves the
  preceding certificate unchanged.

- [ ] **Step 2: Run sequential-gate tests and verify RED**

  Expected: failure naming `decide_extension`.

- [ ] **Step 3: Generalize synthesis to the next candidate partition**

  At each source layer, use its observed `allowed_next` signature only to name
  candidate classes and required promoted members. Run the same exact CEGIS,
  verifier, and witness extraction used at layer 31. Do not assume the observed
  class count or transition signature is valid outside reachable states. Stop
  before synthesis if the reproduced candidate partition has more than eight
  classes.

- [ ] **Step 4: Extend and audit one layer at a time**

  For each layer in `30,29,28,27,26,25`:

  1. synthesize and primary-check only that layer;
  2. attach it to a copy of the preceding certificate;
  3. rerun the complete primary tail check;
  4. run the isolated checker on the complete candidate certificate;
  5. replace durable artifacts only after joint PASS; and
  6. otherwise preserve the preceding certificate and record the failure.

  Never use a later layer result to revise an already audited earlier guard.

- [ ] **Step 5: Apply initiation and explanatory compression**

  For the maximal verified interval, require every promoted state at the start
  layer classified into a semantic class. Compare
  `canonical_bytes(certificate_core_payload(certificate))` with
  `canonical_bytes(explicit_relation_payload(inputs,start_layer,32))`. Record
  the two integer byte counts and `core_is_smaller`. If layer 25 passes but the
  core is not smaller, final status is STOP with
  `quotient_does_not_compress_relation`. If an earlier layer fails, measure the
  preceding maximal tail and retain its exact compression status as an achieved
  diagnostic, not as permission to cross the failed boundary.

- [ ] **Step 6: Run deterministic conditional extension**

  ```bash
  uv run --extra exact python \
    .timeloop/runs/t28_base19_tail_quotient.py \
    --through-layer 25 \
    --evidence /tmp/t28-tail-a.json \
    --certificate /tmp/t28-tail-a-certificate.json \
    --report /tmp/t28-tail-a-report.md
  uv run --extra exact python \
    .timeloop/runs/t28_base19_tail_quotient.py \
    --through-layer 25 \
    --evidence /tmp/t28-tail-b.json \
    --certificate /tmp/t28-tail-b-certificate.json \
    --report /tmp/t28-tail-b-report.md
  cmp -s /tmp/t28-tail-a.json /tmp/t28-tail-b.json
  cmp -s /tmp/t28-tail-a-certificate.json /tmp/t28-tail-b-certificate.json
  cmp -s /tmp/t28-tail-a-report.md /tmp/t28-tail-b-report.md
  ```

  The command may stop before layer 25 but must still reproduce the same
  achieved certificate and first stop record twice. Run the independent checker
  on that achieved boundary and require byte-identical repeated audit output.

- [ ] **Step 7: Replace durable artifacts only with the jointly audited result**

  Validate temporary JSON, copy the joint result to the three durable JSON
  paths and the durable Markdown report, rerun both checkers from those paths,
  and compare their outputs with the temporary files. Preserve the layer-31
  artifacts if any replacement check fails.

- [ ] **Step 8: Run Task 7 GREEN and commit**

  ```bash
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py \
    .timeloop/tests/test_lychrel_invariant_lift.py -q
  git add .timeloop/runs/t28_base19_tail_quotient.py \
    .timeloop/runs/t28_base19_tail_quotient_independent.py \
    .timeloop/runs/t28_base19_tail_quotient.json \
    .timeloop/runs/t28_base19_tail_quotient_certificate.json \
    .timeloop/runs/t28_base19_tail_quotient_independent.json \
    .timeloop/runs/t28_base19_tail_quotient_report.md \
    .timeloop/tests/test_lychrel_quotient_automaton.py
  git commit -m "exp: extend audited base19 tail quotient"
  ```

### Task 8: Durable conclusion and final verification

**Files:**

- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `docs/superpowers/plans/2026-08-09-base19-tail-quotient-automaton.md`
- Verify: every T28 code, test, evidence, certificate, and audit file

**Interfaces:**

- Consumes the final joint primary/independent result.
- Produces exactly one conclusion: layer-31 synthesis STOP, layer-31 assurance
  STOP, verified maximal tail ending above layer 25, layer-25 PASS without
  explanatory compression, or verified compressed layer-25--32 automaton.

- [ ] **Step 1: Regenerate the final achieved boundary twice**

  Run the primary command with `--through-layer` equal to the earliest jointly
  achieved source layer, write two temporary evidence/certificate pairs, and
  compare them byte-for-byte. Run the isolated checker twice and compare its
  canonical audit output. For STOP without a certificate, omit the certificate
  argument and require the same deterministic stop record.

- [ ] **Step 2: Write the notebook result at the exact claim boundary**

  Add a `T28` section with `STATUS`, `CLAIM`, `RELATION TO T27 AND PREPRINT`,
  `QUOTIENT`, `EXACT CHECK`, `INDEPENDENT CHECK`, `COMPRESSION`, `PRISM AND
  RESEARCH`, `STOP CONDITION`, `LIMITATIONS`, and `NEXT`. Include all attempted
  class/node/depth counts and the first deterministic counterexample. State
  explicitly that reachable quotient counts were hypotheses, the preprint's
  35-layer certificate remains authoritative, Math Prism was unavailable behind
  its fail-closed migration requirement, and no base lift or Lean work ran.
  Cite D'Antoni, Kincaid, and Wang at
  `https://arxiv.org/abs/1610.01722` for symbolic-automata precedent and
  Cimatti, Griggio, and Sebastiani at `https://arxiv.org/abs/0906.4492` for the
  optional interpolation/preimage route, while stating that neither source
  proves this quotient.

- [ ] **Step 3: Mark only executed plan tasks and conditional branches**

  Add an `Execution outcome (2026-08-09)` section immediately before Global
  Constraints. Mark completed tasks `[x]`, skipped conditional Task 7 as
  `[ ] skipped after <exact stop reason>` when applicable, and name the maximal
  jointly audited layer interval. Do not mark a mathematical target complete
  solely because its bounded attempt ended.

- [ ] **Step 4: Run compilation, lint, focused, and adjacent regression checks**

  ```bash
  uv run --extra exact --extra dev python -m py_compile \
    .timeloop/lib/lychrel_quotient_automaton.py \
    .timeloop/runs/t28_base19_tail_quotient.py \
    .timeloop/runs/t28_base19_tail_quotient_independent.py
  uv run --extra exact --extra dev ruff check \
    .timeloop/lib/lychrel_quotient_automaton.py \
    .timeloop/runs/t28_base19_tail_quotient.py \
    .timeloop/runs/t28_base19_tail_quotient_independent.py \
    .timeloop/tests/test_lychrel_quotient_automaton.py
  uv run --extra exact --extra dev pytest \
    .timeloop/tests/test_lychrel_quotient_automaton.py \
    .timeloop/tests/test_lychrel_invariant_lift.py \
    .timeloop/tests/test_lychrel_interface_cores.py \
    .timeloop/tests/test_lychrel_arbitrary_topology.py -q
  ```

  Expected: compilation and lint exit zero and every selected test passes.

- [ ] **Step 5: Validate durable JSON and independent replay**

  ```bash
  python3 -m json.tool \
    .timeloop/runs/t28_base19_tail_quotient.json >/dev/null
  python3 -m json.tool \
    .timeloop/runs/t28_base19_tail_quotient_independent.json >/dev/null
  ```

  For a certificate-bearing result, also validate
  `.timeloop/runs/t28_base19_tail_quotient_certificate.json`. Rerun the isolated
  checker using durable paths and compare stdout byte-for-byte with the durable
  independent audit.

- [ ] **Step 6: Verify preservation boundaries and diff hygiene**

  ```bash
  sha256sum publication/base19-radial/preprint.zip
  git diff --check
  git status --short
  ```

  Require the ZIP digest from Global Constraints. Confirm the pre-existing
  `.timeloop/exam/results.jsonl` modification, `preprint-v2` deletions,
  `.DS_Store` files, untracked `preprint/`, and ZIP remain outside every T28
  commit. Review `git diff --name-status` so only T28 files, the notebook, and
  this executed plan are included.

- [ ] **Step 7: Commit the final conclusion**

  ```bash
  git add .timeloop/notebook/lychrel-bases.md \
    docs/superpowers/plans/2026-08-09-base19-tail-quotient-automaton.md
  git commit -m "docs: record base19 tail quotient outcome"
  ```

  Add a durable evidence/certificate/audit file here only if Task 8 changed it
  after the last audited artifact commit. Never stage publication paths or
  unrelated dirty files.
