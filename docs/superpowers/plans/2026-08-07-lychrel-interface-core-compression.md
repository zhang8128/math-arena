# T26 Lychrel Interface-Core Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and implement each task test-first.  This
> experiment must run inline without subagents.

**Goal:** Replace T25's 184 opaque UNSAT statuses with complete,
deletion-irreducible column-core families and an independent finite-domain
replay, then promote a symbolic obstruction only if one survives both checks.

**Architecture:** Refactor the existing one-hot compiler to emit hard clauses
and selector-guarded column groups without changing its unguarded formula.  A
small C++ CaDiCaL API client seeds and minimizes group MUSes in the calibrated
compact binary encoding, then verifies the exact resulting columns in the
one-hot encoding.  A Python orchestrator discovers representative core
families across the eight variants and 23 bases.  A standalone JSON-driven CSP
implementation rebuilds and exhaustively replays every core and deletion
witness.

**Tech Stack:** Python 3.9, SageMath 10.9 Python 3.14, C++17, Homebrew
CaDiCaL 3.0.1 static library, optional `z3-solver` 5.x radial projection,
pytest, exact integer arithmetic.

## Global Constraints

- Preserve `.timeloop/exam/results.jsonl`.
- Keep all 497 arbitrary digit domains and six leading-nonzero constraints
  hard; group only exact `n=0` transition columns.
- Report deletion-irreducible group cores, never minimum-cardinality cores.
- Cover every phase-zero move and every base in the inclusive range `18..40`.
- Fail closed on SAT/UNSAT disagreement, UNKNOWN, malformed mappings, missing
  deletion witnesses, incomplete coverage, or arithmetic replay failure.
- The independent checker imports no T24, T25, T26, topology, or SAT module.
- Invalid Prism applications are provenance only, never mathematical evidence.
- Do not claim an all-base symbolic theorem from finite-range coverage.

---

### Task 1: Grouped one-hot column encoding

**Files:**

- Modify: `.timeloop/lib/lychrel_arbitrary_topology.py`
- Create: `.timeloop/tests/test_lychrel_interface_cores.py`

**Interfaces:**

- Consumes: `build_column_constraints(words, base, parameters=(0,))` and the
  current deterministic one-hot allocation.
- Produces: frozen `CNFGroup(provenance: str, clauses:
  tuple[tuple[int,...],...])`, frozen `GroupedCNFFormula(base, parameters,
  hard_clauses, groups, semantic_keys, digit_keys, selector_keys)`,
  `GroupedCNFFormula.guarded_formula() -> CNFFormula`, and
  `compile_grouped_one_hot_cnf(words, base, parameters=(0,))`.

- [x] **Step 1: Write literal grouped-formula tests**

  Use a two-phase, two-digit fixture.  Assert that digit-domain and
  leading-nonzero clauses are hard, every transition implication is in the
  exact provenance group, selector keys follow column order, and each guarded
  clause is `(-selector, *original_clause)`.

- [x] **Step 2: Run the focused tests and verify RED**

  Run:
  `python3 -m pytest .timeloop/tests/test_lychrel_interface_cores.py -q`

  Expected: collection fails because grouped APIs do not exist.

- [x] **Step 3: Refactor the compiler around labeled clauses**

  Add one private builder that performs the existing deterministic variable
  allocation once and returns hard clauses plus ordered column groups.
  `compile_one_hot_cnf` must flatten those clauses in the original order;
  `compile_grouped_one_hot_cnf` must append selectors after every original
  semantic variable and guard only grouped clauses.

- [x] **Step 4: Add exact T25 calibration tests**

  For each of the eight phase-zero moves at base 18, strip the leading selector
  from every guarded clause, flatten hard clauses and groups, and assert exact
  equality with `compile_one_hot_cnf`.  Assert 499 groups with unique
  provenances and deterministic guarded DIMACS digest.

- [x] **Step 5: Run focused and T24/T25 regression tests GREEN**

  Run:
  `python3 -m pytest .timeloop/tests/test_lychrel_interface_cores.py .timeloop/tests/test_lychrel_arbitrary_topology.py .timeloop/tests/test_lychrel_interface_perturbations.py -q -k 'not primary_evidence and not standalone_binary_audit'`

  Expected: all tests pass and existing unguarded digests remain unchanged.

- [x] **Step 6: Commit Task 1**

  ```bash
  git add .timeloop/lib/lychrel_arbitrary_topology.py .timeloop/tests/test_lychrel_interface_cores.py
  git commit -m "feat: group topology CNF by addition column"
  ```

### Task 2: Incremental CaDiCaL group-MUS client

**Files:**

- Create: `.timeloop/runs/t26_group_mus.cpp`
- Modify: `.timeloop/tests/test_lychrel_interface_cores.py`

**Interfaces:**

- Consumes: DIMACS CNF and a UTF-8 selector file containing one positive
  selector literal per line.
- Produces: `t26_group_mus FORMULA SELECTORS MODE`, where `MODE` is `extract`
  or `verify`, and canonical JSON with `status`, `cadical_version`,
  `input_variables`, `input_clauses`, `requested_selectors`, `core_selectors`,
  `deletion_statuses`, and `solve_calls`.

- [x] **Step 1: Write failing compiled-client tests**

  In a temporary directory compile with:

  ```bash
  clang++ -std=c++17 -O2 .timeloop/runs/t26_group_mus.cpp \
    -I/opt/homebrew/opt/cadical/include \
    /opt/homebrew/opt/cadical/lib/libcadical.a \
    -o "$TMPDIR/t26_group_mus"
  ```

  Feed a hand-derived grouped CNF with three selectors whose full set is UNSAT
  and whose unique irreducible core has two selectors.  Assert `extract`
  returns those two and two SAT deletion statuses; assert `verify` preserves a
  requested nonminimal set and reports the UNSAT deletion accurately.

- [x] **Step 2: Verify RED**

  Run the two compiled-client tests.  Expected: compilation fails because the
  C++ source is absent.

- [x] **Step 3: Implement strict DIMACS and selector parsing**

  Reject duplicate/zero/out-of-range selectors, clause counts differing from
  the header, literals outside the variable range, trailing non-whitespace,
  unsupported mode, and unreadable files.  Emit errors to stderr and return a
  nonzero process status without partial JSON.

- [x] **Step 4: Implement seed, parallel extraction, and verification**

  Use assumption-based `seed` mode on compact binary groups, deterministic
  chunk and parallel deletion batches in `extract`, and incremental
  assumption replay in `verify`.  After each removable group, restart from the
  canonically first proven deletion.  Finally require joint UNSAT and solve
  every one-selector deletion, recording exact SAT/UNSAT statuses.  Treat
  status 0 as fatal.

- [x] **Step 5: Run compiled-client tests GREEN and commit**

  ```bash
  python3 -m pytest .timeloop/tests/test_lychrel_interface_cores.py -q
  git add .timeloop/runs/t26_group_mus.cpp .timeloop/tests/test_lychrel_interface_cores.py
  git commit -m "feat: extract column group MUSes with CaDiCaL"
  ```

### Task 3: Representative core-family discovery

**Files:**

- Create: `.timeloop/runs/t26_lychrel_interface_cores.py`
- Modify: `.timeloop/tests/test_lychrel_interface_cores.py`

**Interfaces:**

- Consumes: grouped compiler, T25 `move_interface`/`variant_id`, T21 reference
  cycle, and the compiled Task 2 executable.
- Produces: `build_primary_evidence() -> dict[str, object]`,
  `discover_variant_families(words, move, bases, extractor)`, and deterministic
  family records keyed by exact provenance and canonical incidence digests.

- [ ] **Step 1: Write failing bounded discovery tests**

  Inject a real compiled extractor but restrict a fixture run to one T25 move
  and bases `(18,19)`.  Assert the first representative is 18, every base is
  covered by a family whose exact core is jointly UNSAT and deletion-SAT, no
  base appears twice in the final disjoint assignment, and repeated runs
  produce identical JSON.

- [ ] **Step 2: Verify RED**

  Expected: import fails because the T26 orchestrator is absent.

- [ ] **Step 3: Implement temporary build and grouped-file serialization**

  Compile the C++ extractor once per evidence run in a temporary directory.
  Serialize deterministic guarded DIMACS plus ordered selector lines and map
  returned literals back to exact group provenances.  Record `clang++
  --version`, CaDiCaL version, formula digest, and selector-map digest.

- [ ] **Step 4: Implement representative-first family coverage**

  Maintain ordered uncovered bases.  Extract at the least uncovered base;
  verify that exact core in every remaining base; assign to the family only
  bases with joint UNSAT and all deletion statuses SAT.  Repeat until none are
  uncovered.  Reject duplicate coordinates, empty cores, non-progress, or any
  primary status inconsistent with T25.

- [ ] **Step 5: Implement canonical incidence serialization**

  Convert digit keys to `(phase, flattened_fixed_index)`, constants to literal
  digits or symbolic `B-1`, and carries to `(phase,column)`.  Hash sorted exact
  constraints.  Merge labels across variants only when these canonical rows
  are identical; otherwise retain separate families even when provenance
  strings match.

- [ ] **Step 6: Run bounded discovery GREEN and commit**

  ```bash
  python3 -m pytest .timeloop/tests/test_lychrel_interface_cores.py -q
  git add .timeloop/runs/t26_lychrel_interface_cores.py .timeloop/tests/test_lychrel_interface_cores.py
  git commit -m "exp: discover interface obstruction core families"
  ```

**Verified research checkpoint (not Task 3 completion):** the base-18
156-column family is SAT unchanged at base 19.  The fresh base-19 seed folds
into 34 radial layers plus two overflow equations; removing phase-five column
82 leaves a 409-equation candidate with a frontier of at most 12 carries and
two digits.  Exact layer projection peaks at 314 reachable states and proves
joint UNSAT at layer 33.  Deleting phase-zero column 0 instead peaks at 1,480
states and yields a replayed 408-equation witness.  All remaining deletions
must still be witnessed before the 409-column candidate is called
deletion-irreducible or used as a representative family.

### Task 4: Standalone finite-domain core audit

**Files:**

- Create: `.timeloop/runs/t26_lychrel_interface_cores_independent.py`
- Modify: `.timeloop/tests/test_lychrel_interface_cores.py`

**Interfaces:**

- Consumes: copied `t21_lychrel_multi_interface.json` and a copied primary T26
  JSON path supplied as command arguments.
- Produces: canonical JSON containing source hashes, rebuilt family hashes,
  joint solution counts, deletion solution counts, projected deletion
  witnesses, arithmetic replay statuses, and complete coverage.

- [ ] **Step 1: Write a failing isolated subprocess test**

  Copy only the independent script, T21 JSON, and a small hand-authored family
  artifact to a temporary directory; run `python3 -I`.  Assert it rejects a
  false UNSAT core, accepts a literal small irreducible core, and emits an
  explicit arithmetically valid witness for every deletion.

- [ ] **Step 2: Verify RED**

  Expected: copy or subprocess launch fails because the independent script is
  absent.

- [ ] **Step 3: Independently rebuild moves and named columns**

  Parse JSON with strict type/range checks.  Reimplement signed phase-zero
  boundary movement, flattened digit naming, `n=0` sources, the phase-five
  wrap target at `n=1`, and exact column equations.  Do not import repository
  code or invoke an external solver.

- [ ] **Step 4: Implement deterministic finite-domain solving**

  Initialize digit domains to `range(B)` and carries to `{0,1}`, apply leading
  nonzero domains, enforce generalized arc consistency by enumerating each
  column's at most `2*B^2` local tuples, and branch on the lexicographically
  first variable of smallest remaining domain.  Return the first projected
  model or zero models; replay every returned tuple against the integer column
  equation before serialization.

- [ ] **Step 5: Audit joint cores and every deletion**

  For each family/base require no joint model.  For every deleted column
  require a model, serialize only variables used by the remaining core, and
  verify leading/non-domain constraints.  Recompute canonical incidence
  digests and reject disagreement with primary evidence.

- [ ] **Step 6: Run isolated and focused tests GREEN and commit**

  ```bash
  python3 -m pytest .timeloop/tests/test_lychrel_interface_cores.py -q
  git add .timeloop/runs/t26_lychrel_interface_cores_independent.py .timeloop/tests/test_lychrel_interface_cores.py
  git commit -m "test: independently replay interface core families"
  ```

### Task 5: Full evidence and conditional symbolic analysis

**Files:**

- Modify: `.timeloop/runs/t26_lychrel_interface_cores.py`
- Create: `.timeloop/runs/t26_lychrel_interface_cores.json`
- Modify: `.timeloop/tests/test_lychrel_interface_cores.py`

**Interfaces:**

- Consumes: Tasks 1–4 and T25 evidence hash.
- Produces: `build_evidence()` with complete eight-variant/23-base coverage,
  independent audit agreement, Prism provenance, and either a checked
  symbolic obstruction or explicit `not_derived` status.

- [ ] **Step 1: Write the failing full-evidence acceptance test**

  Run the Sage/Python evidence script with a 3600-second timeout.  Assert eight
  variants, bases `18..40`, no uncovered instances, every family jointly
  UNSAT and deletion-irreducible in both implementations, matching canonical
  digests, valid independent witnesses, exact T25 source hash, and Prism
  applications
  `application:488172c10ae616ec153970c96f6484a0a1df67c1a908fbeed4b1f84df8a8da6d`
  and
  `application:30c0bd06a50fc50ba49770b6674ccb5e3a8d096e3aba69bbc775af2939bc52f6`
  marked invalid with no artifacts.

- [ ] **Step 2: Verify RED**

  Expected: the complete evidence fields and saved artifact are absent.

- [ ] **Step 3: Add conditional symbolic analysis**

  Group identical canonical families.  When one spans at least two variants or
  all 23 bases of one variant, serialize support-propagation reductions and
  attempt to express the final empty domain as exact integer bounds in `B`.
  Set status `verified_bounded_symbolic_obstruction` only after standalone
  algebraic replay; otherwise emit `not_derived` with the exact failed stage.

- [ ] **Step 4: Generate deterministic evidence twice**

  Run two complete generators concurrently, require byte equality, and copy
  one generated file to the tracked JSON.  Record SHA-256 and exclude timings
  from deterministic evidence.

- [ ] **Step 5: Run focused acceptance tests GREEN and commit**

  ```bash
  python3 -m pytest .timeloop/tests/test_lychrel_interface_cores.py -q
  git add .timeloop/runs/t26_lychrel_interface_cores.py .timeloop/runs/t26_lychrel_interface_cores.json .timeloop/tests/test_lychrel_interface_cores.py
  git commit -m "exp: compress interface topology obstructions"
  ```

### Task 6: Research record, verification, and integration

**Files:**

- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `.timeloop/ledger.md`

**Interfaces:**

- Consumes: verified T26 artifact and literature/method sources.
- Produces: exact scoped result, limitations, Prism disposition, and one next
  experiment determined by whether a symbolic obstruction was found.

- [ ] **Step 1: Record the exact outcome**

  Document family counts/sizes/coverage, representative bases, independent
  witness totals, canonical sharing or non-sharing, artifact hash, and the
  distinction between irreducible and minimum cores.

- [ ] **Step 2: Record research and Prism provenance**

  Cite the CaDiCaL API and group-MUS/MARCO sources as method prior art.  Record
  both T26 Prism applications as schema-invalid and do not call frame evolution
  because there are no valid artifact hashes.

- [ ] **Step 3: Choose the next mathematical step**

  If a uniform symbolic obstruction verifies, test its stated base range
  beyond 40 with independent arithmetic.  Otherwise use measured core
  incidence to choose between a targeted symbolic elimination and two
  simultaneous interface moves; do not expand topology blindly.

- [ ] **Step 4: Run final verification**

  ```bash
  python3 -m py_compile .timeloop/lib/lychrel_arbitrary_topology.py \
    .timeloop/runs/t26_lychrel_interface_cores.py \
    .timeloop/runs/t26_lychrel_interface_cores_independent.py \
    .timeloop/tests/test_lychrel_interface_cores.py
  python3 -m pytest .timeloop/tests -q
  git diff --check
  ```

  Then regenerate T26 once and compare it byte-for-byte with the tracked
  artifact.

- [ ] **Step 5: Commit the research record**

  ```bash
  git add .timeloop/notebook/lychrel-bases.md .timeloop/ledger.md
  git commit -m "docs: record interface core compression"
  ```

- [ ] **Step 6: Complete the branch workflow**

  Use `superpowers:verification-before-completion` and
  `superpowers:finishing-a-development-branch`.  Honor the standing local
  merge choice, verify merged `main`, remove only the T26 worktree/branch, and
  preserve `.timeloop/exam/results.jsonl`.
