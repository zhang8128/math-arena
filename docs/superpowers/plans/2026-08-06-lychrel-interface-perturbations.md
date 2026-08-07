# T25 Single-Interface Lychrel Perturbations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` and implement each task test-first.

**Goal:** Exactly classify all one-interface, one-or-two-column perturbations
of the T21 six-phase topology in bases `18..40`.

**Architecture:** A small pure perturbation API preserves flattened fixed
digits while repartitioning adjacent fragments.  A structural reducer proves
that only the eight phase-zero variants can affect the exact `n=0` necessary
condition.  T24's one-hot/PicoSAT compiler performs the primary scan; a
separately implemented JSON perturbation plus binary full-adder/CaDiCaL audit
checks every new instance.  Existing exact polynomial verification accepts
positives.

**Tech stack:** Python 3.9, SageMath 10.9 Python 3.14, PicoSAT/pycosat,
CaDiCaL 3.0.1, pytest, exact integer arithmetic.

## Global constraints

- Preserve `.timeloop/exam/results.jsonl`.
- Use shifts `-2,-1,1,2`; positive moves a boundary right.
- Preserve flattened fixed digits and repeat order; reject empty fragments.
- Represent all fixed occurrences by arbitrary digits in `0..B-1`.
- Treat `n=0` UNSAT as a necessary-condition obstruction.
- Require independent status agreement for all 184 new instances.
- Do not report invalid Prism applications as mathematical artifacts.

### Task 1: Boundary perturbation and structural reduction

**Files:**

- Create: `.timeloop/lib/lychrel_interface_perturbations.py`
- Create: `.timeloop/tests/test_lychrel_interface_perturbations.py`

- [ ] Write literal tests for shifts `+2` and `-1`, preserved flattening,
      preserved repeats, enumeration of 48 moves/eight phase-zero moves, and
      rejection of zero/out-of-range/empty-fragment moves.
- [ ] Run the focused tests and observe RED from the missing module.
- [ ] Implement frozen `InterfaceMove`, `move_interface`, `all_moves`, and
      `n_zero_relevant_moves` with no solver dependency.
- [ ] Add tests that phase-one through phase-five moves preserve the canonical
      `n=0` columns/CNF while every phase-zero move changes the wrap layout.
- [ ] Run focused tests GREEN and commit.

### Task 2: Primary exact classification

**Files:**

- Create: `.timeloop/runs/t25_lychrel_interface_perturbations.py`
- Modify: `.timeloop/tests/test_lychrel_interface_perturbations.py`

- [ ] Write a failing subprocess evidence test asserting 48 scoped moves, 40
      inherited negatives, eight scanned variants, all bases `18..40`, exact
      result counts, survivor escalation metadata, and Prism invalid IDs.
- [ ] Implement deterministic variant IDs and one-hot/PicoSAT classification.
- [ ] For every `n=0` survivor, solve `n=0,1,2`, decode, and require exact
      polynomial plus six non-palindrome witnesses.
- [ ] Generate the primary evidence twice and require byte identity.
- [ ] Run focused tests GREEN and commit.

### Task 3: Independent binary audit

**Files:**

- Create: `.timeloop/runs/t25_lychrel_interface_perturbations_independent.py`
- Modify: `.timeloop/runs/t25_lychrel_interface_perturbations.py`
- Modify: `.timeloop/tests/test_lychrel_interface_perturbations.py`

- [ ] Write a failing isolated subprocess test that copies only the audit,
      T24 standalone binary encoder, and T21 JSON.  Assert 184 decisive
      statuses, CaDiCaL identity, and encoding digests distinct from primary.
- [ ] Implement JSON-only interface movement without importing primary T25
      or arbitrary-topology modules.
- [ ] Audit every phase-zero variant/base with the binary full-adder CNF and
      fail closed on SAT/UNSAT disagreement or UNKNOWN.
- [ ] Embed the audit summary in primary evidence, regenerate twice, run
      focused tests GREEN, and commit.

### Task 4: Research record and integration

**Files:**

- Create: `.timeloop/runs/t25_lychrel_interface_perturbations.json`
- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `.timeloop/ledger.md`

- [ ] Record the exact result, structural reduction, both encodings, limits,
      and invalid Prism applications.
- [ ] If there is a positive, perform current primary-source/OEIS novelty
      research before describing significance.  If negative, state the
      precise newly excluded neighborhood without a novelty claim.
- [ ] Queue the next experiment from the observed obstruction/survivors.
- [ ] Run the entire `.timeloop` test suite, both evidence generators,
      deterministic comparisons, and `git diff --check`.
- [ ] Use verification-before-completion and finishing-a-development-branch;
      integrate locally without touching the unrelated exam ledger change.
