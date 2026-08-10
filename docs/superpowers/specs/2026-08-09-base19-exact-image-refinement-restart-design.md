# Base-19 Exact-Image Refinement Restart Design

## Purpose

T30 tests one reachability-side explanation of T29's semantic leak. It freezes
a compact predicate `Q0` discovered from the affine hull of the 18 promoted
layer-31 outputs and asks whether the existing promoted layer-30 frontier
implies `Q0` through the exact layer-30-to-31 equations. If so, it then asks
whether `Q0`, conjoined with T29's ten-atom separator, is an exact universal
layer-31 dead region.

This is a bounded theorem about the frozen base-19 radial obstruction with
removed coordinate `phase=0,n=0,column=82`. It is not an inductive invariant,
a lower-layer extension, a symbolic-base result, a topology classification, or
a statement about unbounded reverse-and-add orbits.

## Frozen candidate

In the canonical layer-31 variables, `Q0` is the conjunction of these five
affine equalities:

```text
L1 - L4 + L5 - R4 = 0
L1 - 2*L2 - 2*L4 - 2*L5 - 3*R1 + 3*R2 + 2*R3 + R4 = 0
3*L0 + L1 + 2*L2 - 2*L5 - 3*R1 + R3 = 3
D1 + 3*L0 - 2*L1 - 3*L2 + L3 + L4 - R0
   - 3*R1 - 3*R2 + 3*R3 - R4 = 9
D0 - D1 - L0 + R0 + R5 = 1
```

`Q0` has five atoms, maximum coefficient magnitude three, maximum atom support
11, total coefficient support 34, and no disjunction, congruence, nonlinear
term, state identifier, or lookup. Its origin in an affine-hull calculation is
hypothesis provenance only. Exact implication and independent replay, not the
fit, decide whether it is accepted.

T30 does not synthesize, refine, or widen `Q0`. Any failure is a STOP for this
round.

## Mathematical claim boundary

Let:

- `R30(u)` mean that `u` is one of the 18 promoted layer-30 states in the
  frozen minimal-core frontier;
- `T30_31(u, x)` be the original 12 integer equations assigned to frontier
  layer 31, with their exact digit and carry domains;
- `S29(x)` be T29's immutable ten-atom finite separator; and
- `T31_32(x, y)` be the original 12 integer equations assigned to frontier
  layer 32.

T30 may claim PASS only if primary and independent checkers establish all
three obligations:

1. **Earlier-layer implication**

   `R30(u) and T30_31(u, x) implies Q0(x)` for every bounded `u` and `x`.

2. **Frozen finite boundary**

   `Q0` holds on all 12 promoted layer-31 `DEAD` states, rejects all 221 T28
   trace models, and rejects T29's semantic leak. In addition, `S29 and Q0`
   must preserve T29's classification of all 239 serialized states. The six
   promoted live controls may satisfy `Q0`; `S29` must continue to reject them.

3. **Universal no-successor consequence**

   `S29(x) and Q0(x) and T31_32(x, y)` is UNSAT over the complete bounded
   digit/carry domain.

The first obligation is reachability-relative: it depends on the already
promoted layer-30 frontier. T30 does not claim that `Q0` follows from the
layer-30-to-31 equations for arbitrary predecessor interfaces, nor that a
compact predicate characterizing `R30` has been found.

## Preliminary evidence, not a certificate

A read-only Z3 probe before this design found:

- zero `Q0` violations after fixing each of the 18 promoted layer-30
  predecessors in turn;
- five successor-bearing predecessors and 18 distinct promoted outputs;
- finite counts `12` promoted `DEAD` accepted, `0/221` trace models accepted,
  all six live controls accepted, and the T29 semantic leak rejected; and
- `S29 and Q0 and T31_32` UNSAT.

These observations motivate the round but are not durable evidence and were
not independently verified.

## Frozen inputs and preservation

T30 binds the existing equation manifest, minimal-core frontier, T27 and T28
evidence, T28 independent audit, and all T29 durable artifacts before doing
mathematics. In particular, it requires these raw T29 hashes:

```text
evidence     c1e3dc4bc4ab07207a6ab49d6a9c9fd86486013abeaf016b6ecd59c9755e1d32
trace        c56877975293c10575009a691b1d1bbde376838f805d232a2c18a4d00b2c4715
dataset      6603e381805db845ef9388d234e36f31eba510d838ac98c143c238c2ff144995
certificate  1c234891f001cb3a59e5670560ab26e3cb248a943e249aee049aac7d32c7db5a
independent  9f926208cc7416e24d811f6cd54485d19741b6f8ffe44f3b365b2f816e579644
```

T29's predicate, certificate syntax, durable bytes, and conclusion remain
unchanged. T30 stores `Q0` as its own five-atom predicate and references the
T29 certificate by raw SHA-256. It never merges the fifteen logical atoms into
one T29 `LayerPredicate`, so no existing grammar ceiling is changed.

Publication paths, unrelated notebooks, `.DS_Store` files, and the existing
Timeloop ledger, pool, and exam changes remain outside every T30 commit. The
preprint ZIP must retain SHA-256
`e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33`.

## Architecture

### Primary checker

The primary runner uses Z3 and the repository's strict frozen-input loaders.
It performs the gates in order:

1. bind every source identity and parse `Q0` canonically;
2. for each of the 18 promoted layer-30 states, check
   `T30_31 and not Q0` with the predecessor fixed;
3. replay `Q0` and `S29 and Q0` on the frozen T29 dataset and semantic leak;
4. check `S29 and Q0 and T31_32` exactly; and
5. emit a complete canonical witness on SAT, or an UNSAT obligation record on
   PASS.

Solver `UNKNOWN`, a noncanonical witness, a changed predecessor/output count,
or any source disagreement fails closed.

### Constructive implication certificate

The certificate does not copy the predecessor or output tables. It binds the
frontier digest and records one canonical obligation result per promoted
predecessor: predecessor index and digest, exact model count, canonical output
digest, and `Q0`-violation status. The expected aggregate is 18 obligations,
five successor-bearing predecessors, and 18 distinct outputs.

This is a bounded constructive proof over an existing reachability
certificate, not a renamed state predicate. If acceptance would require
embedding explicit state disjunctions into `Q0`, T30 stops.

### Independent checker

An isolated Python standard-library checker imports no repository module, Z3,
or T27--T30 implementation. From the raw equation/frontier JSON and durable
T29/T30 artifacts, it independently:

- recomputes all bound hashes and parses the five equations;
- rebuilds allowed tuples for both 12-equation transfers;
- uses generalized arc consistency and backtracking to enumerate every output
  of each of the 18 fixed predecessors and checks `Q0`;
- evaluates `Q0` and `S29` directly on the 239 frozen states and the T29 leak;
- proves `S29 and Q0 and T31_32` UNSAT over the complete bounded domain; and
- rejects mutations to sources, predicate terms, predecessor obligations,
  finite states, semantic status, and any SAT witness.

Primary and independent disagreement is a STOP.

## Components

- `.timeloop/lib/lychrel_exact_image_refinement.py` owns immutable T30
  obligation and certificate types. It reuses the existing five-atom
  `LayerPredicate` representation without changing its limits.
- `.timeloop/runs/t30_base19_exact_image_refinement.py` owns frozen adapters,
  the fixed `Q0`, primary checks, deterministic evidence, and report rendering.
- `.timeloop/runs/t30_base19_exact_image_refinement_independent.py` owns the
  isolated standard-library replay.
- `.timeloop/tests/test_lychrel_exact_image_refinement.py` owns focused syntax,
  real-artifact, determinism, isolation, and mutation tests.
- T30 JSON, certificate, independent-audit, and Markdown report artifacts are
  written only after primary and independent agreement.

No T27, T28, T29, publication, or topology source file needs modification.
The notebook receives only the final achieved boundary after assurance.

## Outcomes and stop conditions

T30 has two durable outcomes:

1. `EXACT_IMAGE_REFINEMENT_PASS`: every implication and finite obligation
   passes, and both checkers prove the universal successor query UNSAT.
2. `EXACT_IMAGE_REFINEMENT_STOP`: the first failed obligation and any exact
   counterexample are recorded without changing `Q0` or attempting a fallback.

T30 stops on any implication counterexample, finite mismatch, semantic SAT,
independent disagreement, mutation survival, digest mismatch, malformed
syntax, count disagreement, solver `UNKNOWN`, explicit-state encoding inside
`Q0`, or need to widen the fixed five-atom predicate.

A PASS proves only that the already promoted layer-30 reachability condition
implies a compact layer-31 refinement which, together with `S29`, excludes all
exact layer-32 successors. It does not reopen lower-layer extension, symbolic
base lifting, base comparison, topology scans, publication work, or Lean work.

## Verification and checkpoint

Verification requires focused T30 tests, adjacent T27--T29 regression tests,
two byte-identical primary runs, two byte-identical independent runs, direct
CLI replay to temporary paths, mutation tests, Ruff, JSON validation, Git diff
hygiene, frozen artifact hashes, and the protected ZIP hash.

The sole checkpoint is after the independent audit. A PASS may motivate a
separate decision about compactly characterizing the layer-30 reachability
premise. A STOP may motivate weakest-preimage extraction or semantic-leak
typing, but neither fallback is authorized in T30.

## Prism and research provenance

Math Prism was checked first during framing. Both the status request and a
valid diverse-frame request failed at the mathematical-frame operation
boundary. No Prism artifact was created or reconstructed, and Prism supplies
no premise.

Haase, Krishna, Madnani, Mishra, and Zetzsche show that existential-block
elimination in Presburger arithmetic has a singly exponential procedure
<https://arxiv.org/abs/2405.01183>. Cimatti, Griggio, and Sebastiani provide
proof-based interpolation procedures for linear-arithmetic SMT
<https://arxiv.org/abs/0906.4492>. König, Rensink, Stoltenow, and Urrigshardt
provide current CEGAR precedent <https://arxiv.org/abs/2504.08617>. These
sources justify later fallback methods only; none proves `Q0`, the predecessor
implication, or the universal no-successor result.
