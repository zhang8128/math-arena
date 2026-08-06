# T23 Fixed-Base Lychrel Transplants — Implementation Plan

**Goal:** Exactly classify lower/upper fixed-base transplants of the T21
base-17 topology for bases `18..100`, with independently audited negative
certificates.

**Architecture:** Add one fixed-base carry compiler/classifier beside the T22
affine modules.  Reuse `CarryEquation` and the exact Boolean solver, but do not
preserve reference carries.  Use `n=0,1,2` carry systems as a complete
interpolation decision and `lychrel_wordproof.verify_cycle` as a separate
acceptance oracle.  Emit a deterministic run artifact and audit its tiny cores
with a standalone implementation.

**Tech stack:** Python 3, pytest, exact integer arithmetic, existing T21/T22
certificate libraries.

---

### Task 1: Fixed-base digit materialization

**Files:**
- Create: `.timeloop/lib/lychrel_fixedbase.py`
- Create: `.timeloop/tests/test_lychrel_fixedbase.py`

1. Write a failing test with literal lower/upper digits and repeat mapping.
2. Run the focused test and confirm the missing API is the failure.
3. Implement the minimum materializer.
4. Run the focused test green.

### Task 2: Fresh-carry equation compiler

**Files:**
- Modify: `.timeloop/lib/lychrel_fixedbase.py`
- Modify: `.timeloop/tests/test_lychrel_fixedbase.py`

1. Write a failing hand-derived column-equation test.
2. Confirm the expected failure.
3. Implement symbolic rendering and sparse carry equations, including boundary
   carries and wrap `n -> n+1`.
4. Test invalid bases, parameters, and topology lengths.
5. Run focused tests green.

### Task 3: Exact fixed-base classification

**Files:**
- Modify: `.timeloop/lib/lychrel_fixedbase.py`
- Modify: `.timeloop/tests/test_lychrel_fixedbase.py`

1. Write failing tests for the verified base-17 control and base-18
   infeasibility.
2. Implement classification over `n=0,1,2` and materialize the first exact
   solution.
3. Require the independent polynomial verifier and fixed mismatch witnesses
   for a positive status.
4. Run focused tests green.

### Task 4: Deterministic scan and compact cores

**Files:**
- Create: `.timeloop/runs/t23_lychrel_fixed_base.py`
- Create: `.timeloop/runs/t23_lychrel_fixed_base.json`
- Modify: `.timeloop/tests/test_lychrel_fixedbase.py`

1. Write a failing evidence-shape test covering calibration, inclusive range,
   per-base statuses, and core coverage.
2. Implement the scan and deterministic serialization.
3. Reconstruct and validate the generic and exceptional three-equation cores.
4. Run the evidence generator twice and compare bytes.

### Task 5: Standalone independent audit

**Files:**
- Create: `.timeloop/runs/t23_lychrel_fixed_base_independent.py`
- Modify: `.timeloop/tests/test_lychrel_fixedbase.py`

1. Write a failing subprocess-level audit test.
2. Independently parse T21 fragments, rebuild selected columns, and brute-force
   each core without production fixed-base/CSP imports.
3. Verify every base `18..100` is covered by an unsatisfiable core; audit and
   report deletion-minimality per base without assuming it is uniform.
4. Run the audit green and capture its deterministic summary in the main JSON.

### Task 6: Research record and integration

**Files:**
- Modify: `.timeloop/notebook/lychrel-bases.md`
- Modify: `.timeloop/ledger.md`

1. Record searched scope, exact result, structural obstruction, technique,
   novelty status, limitations, Prism provenance, and next step.
2. Record Prism outcomes only after the independent audit.
3. Run focused and complete `.timeloop` tests plus both run scripts.
4. Review the diff, commit coherent checkpoints, and integrate only verified
   changes into `main` while preserving the pre-existing exam result.
