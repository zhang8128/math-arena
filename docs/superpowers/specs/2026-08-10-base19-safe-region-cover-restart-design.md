# Base-19 Safe-Region Cover Restart Design

## Decision

T33 is a bounded reachability-side refinement over the frozen base-19 radial
layer-30-to-31 boundary. It seeks a compact disjunction of input regions that
covers the 18 promoted layer-30 interfaces while admitting no exact successor
that violates T30's five-equation predicate `Q0`.

The selected method is a **proof-guided safe-region cover**. It grows small
Presburger regions from pairs of promoted inputs, checks each region against
the original transfer equations, and then asks whether at most six verified
regions cover the promoted premise. It does not resume T31's one-conjunction
search or T32's semantic-mechanism family search.

## Frozen evidence boundary

Let:

- `u` be the 13 canonical layer-30 input variables;
- `x` be the 14 canonical layer-31 output variables;
- `z` be the ten local digit variables;
- `T(u,x,z)` be the original 12 base-19 layer-30-to-31 equations with exact
  digit and carry domains;
- `Q0(x)` be T30's immutable five-equation predicate; and
- `R30` be exactly the 18 promoted layer-30 interfaces already certified by
  T30.

Define the exact bad-input image

```text
B30(u) := exists x,z . T(u,x,z) and not Q0(x).
```

T30 proved that every member of `R30` has only `Q0` successors. Its exact
model-count vector is
`(0,0,0,0,0,4,0,0,0,0,0,0,4,4,0,4,2,0)`.
T31 then found no admissible one-conjunction separator in its 26-atom
`qe-light` pool. T32 found one sound two-literal semantic type but stopped the
complete family search at `CANDIDATE_BUDGET_EXHAUSTED` after 10,000 tested
conjunctions and eight exact witnesses. Its first milestone was
`a0 = b0 and a0 + b0 < 19`, independently accepted after three inspected
witnesses and 31 tested conjunctions. T32 created no durable result artifact,
so T33 binds and deterministically replays this committed source boundary:

```text
library      cf6ad87c8edf3ffa2c86449b9762f8c9d4254645eb71b7f88963a688a1bded11
runner       d9c90e0dc4ce910a6ddef66233b03bff31449a46662fba75628a44dca3ed9e57
independent  fb520b513dd5673e145b583ee8a5025c8113890fdb89139a48b528655ed506b5
test         a6ee921a8ba6304d3a48b0db0b893b6bd8077576acc27146b91d626ac00858bd
```

The relevant T32 commits are `df191a5`, `515bbdd`, `b5ff122`, `e4bc16d`, and
`9d17f77`. The earlier source and artifact hashes remain:

```text
equations        ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040
frontier         0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0
provenances      cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302
T29 evidence     c1e3dc4bc4ab07207a6ab49d6a9c9fd86486013abeaf016b6ecd59c9755e1d32
T29 trace        c56877975293c10575009a691b1d1bbde376838f805d232a2c18a4d00b2c4715
T29 dataset      6603e381805db845ef9388d234e36f31eba510d838ac98c143c238c2ff144995
T29 certificate  1c234891f001cb3a59e5670560ab26e3cb248a943e249aee049aac7d32c7db5a
T29 independent  9f926208cc7416e24d811f6cd54485d19741b6f8ffe44f3b365b2f816e579644
T30 evidence     4b327e826a8b2462eedffa2cf572b77155fc95d8e7b94a4430d7f0331f75bd2a
T30 certificate  3ac0b6ae254ad8bb7c7b19754335ea6a81bea77a0dc808e7eda1cd8994839892
T30 independent  56037d658f628ffa526f9adb710746231806450717f7bde5c0655f4ed6388639
T30 report       3ea55f8410887d3a522436be38bf3d9b5c010ac3c412d48405cd69f19828b95c
```

## Exact claim boundary

A safe-region predicate is a DNF

```text
P30(u) := C0(u) or ... or C(k-1)(u),  1 <= k <= 6,
```

where each `Ci` is a conjunction from the grammar below. T33 may return
`SAFE_REGION_COVER_PASS` only if all of these obligations hold:

1. **Promoted coverage:** every one of the 18 members of `R30` satisfies
   `P30`.
2. **Universal safety:** `P30(u) and B30(u)` is UNSAT over the exact bounded
   relation.
3. **Non-table regions:** each clause covers at least two promoted inputs and
   permits at least four distinct bounded layer-30 inputs.
4. **Canonical ownership:** in canonical clause order, every clause owns at
   least two promoted inputs not owned by an earlier clause.
5. **Compactness:** canonical `P30` bytes are strictly smaller than the
   canonical 18-row promoted-state table, whose T31 measurement is 616 bytes.
6. **Independent agreement:** an isolated standard-library checker reproduces
   coverage, safety, ownership, extents, and compactness from frozen raw data.

On PASS, T33 proves only

```text
R30(u) => P30(u)
P30(u) and T(u,x,z) => Q0(x).
```

Combined with T30 and T29, this transports the frozen promoted premise through
the existing no-successor result. It does not prove that `P30` is exactly the
reachable set, that it is weakest or inductive, or that it applies to an
unbounded reverse-and-add orbit.

## Safe-region grammar

T33 reuses T31's canonical layer-30 Presburger atom syntax with a smaller,
seed-derived coefficient language:

- relations are `eq`, `le`, or `congruent`;
- variables are exactly
  `L0,R0,L1,R1,L2,R2,L3,R3,L4,R4,L5,R5,D0`;
- support is one or two variables;
- coefficient magnitudes are at most three;
- congruence moduli lie in `2..19`, with centered coefficients; and
- atoms are primitive, normalized, sorted, and distinct.

One clause contains one to six atoms. A family contains one to six clauses.
No state number, row hash, Boolean selector, auxiliary variable, direct `Q0`
failure test, nonlinear term, or changed base threshold is permitted.

For a canonical promoted pair `(r,s)`, generate the finite atom pool from
every primitive one- or two-variable linear form `ell` with nonzero
coefficients in `-3..3`:

- include `ell = c` when `ell(r) = ell(s) = c`;
- include the tight bounds `ell <= max(ell(r),ell(s))` and
  `-ell <= -min(ell(r),ell(s))`; and
- include `ell congruent c mod m` for `m in 2..19` when the two seed values
  have the same residue.

Normalize and deduplicate the pool, then remove atoms true on the entire
bounded layer-30 domain. No other atom can enter T33. This makes discovery
finite, directed by promoted seeds, and independently reproducible rather
than an open-ended guard scan.

To propose a region, assert the complete seed-pair pool together with `B30`,
using one named assertion per atom. A SAT result rejects the pair. On UNSAT,
extract the canonical named core and deletion-minimize it in canonical atom
order, retaining a deletion exactly when the reduced conjunction remains
UNSAT. Reject cores that cannot reach six atoms within the candidate budget.
The solver core is provenance only; the minimized region still faces fresh
primary and independent semantic checks.

## First falsifiable milestone

Before cover synthesis or durable T33 artifacts, construct one temporary
region `C0` satisfying all of the following:

- `C0` contains at most six canonical atoms;
- it contains two distinct promoted seed inputs;
- it permits at least four distinct bounded layer-30 inputs;
- `C0(u) and B30(u)` is UNSAT in a fresh primary solver;
- its canonical bytes are smaller than the explicit table of the promoted
  rows it covers; and
- the isolated checker independently confirms its seeds, bounded extent, and
  universal safety.

Discovery considers the 153 promoted seed pairs in canonical order and may
test at most 2,000 distinct core reductions. UNSAT cores and minimization
order are hypotheses only. Every candidate advances solely through the exact
original-equation query and independent replay.

If no such multi-input region appears within either bound, T33 stops at
`NO_SAFE_REGION`. It does not try singleton regions, widen coefficients,
change the topology, switch to the positive-QE alternative, or write durable
results.

## Bounded cover construction

If and only if `C0` passes:

1. Continue the same canonical seed-pair procedure, deduplicating candidate
   bytes globally.
2. Retain only regions with fresh primary and isolated safety agreement.
3. Solve the finite set-cover problem over the 18 promoted inputs, ordering
   candidates by
   `(clause_count, total_atoms, total_support, coefficient_l1,
   canonical_bytes)`.
4. Recheck canonical first-match ownership after every insertion. Overlap is
   allowed, but every retained clause must own at least two promoted inputs.
5. Stop before testing region 5,001, cover candidate 10,001, or clause seven.
6. Run fresh full-domain primary and independent gates only after a complete
   cover exists.

The 5,000-region bound includes every core reduction tested during the first
milestone. The 10,000-cover bound counts every distinct candidate family,
including incomplete families rejected by ownership or compactness.

The finite set-cover step may use SAT as an optimizer, but SAT selection is not
proof. The final coverage and safety obligations are always re-established
from fresh exact loaders.

## Independent verification

The primary implementation may use Z3 for named-core discovery. The exact Z3
version, solver parameters, random seeds, named assertions, core bytes, and
minimization trace are recorded. None is trusted as a certificate.

The independent checker imports no repository module, Z3, T27--T33
implementation, or interpolation library. Using only the standard library and
raw JSON, it rebuilds the 12 equations and finite domains, then:

- evaluates every clause on all 18 promoted inputs;
- enumerates all 77,824 bounded layer-30 inputs to determine each clause's
  exact extent;
- searches by generalized arc consistency and deterministic backtracking for
  a `not Q0` successor inside each clause and inside the complete `P30`;
- recomputes canonical first-match ownership;
- recomputes predicate and promoted-table bytes; and
- rejects all malformed syntax, source mutations, count changes, and status
  changes.

Primary and independent certificate bytes must reproduce in two fresh
temporary directories before any durable artifact is written.

## Hard STOP conditions

T33 stops without fallback when:

- the first safe-region milestone fails;
- a candidate is a singleton/minterm or is not derived from the frozen
  seed-pair pool and canonical core procedure;
- a region has fewer than four bounded inputs or owns fewer than two promoted
  inputs;
- more than six atoms, six clauses, 5,000 regions, or 10,000 cover candidates
  are required;
- a required query is SAT or `UNKNOWN`;
- `P30` is at least 616 bytes;
- any source or predecessor hash changes;
- primary and independent results disagree; or
- progress would require lower-layer extension, an unbounded enumeration, or
  a changed topology.

On any early STOP, create no durable T33 evidence, certificate, audit, report,
or notebook section, and begin no alternate experiment.

## Ranked alternatives

| Rank | Target | First falsifiable milestone | Independent method | Likely cost | Stop condition |
| --- | --- | --- | --- | --- | --- |
| 1 | Proof-guided safe-region cover | One universally safe six-atom region covering two promoted and at least four bounded inputs | Complete bounded-input extent plus raw-equation CSP safety | Medium to high | Milestone, provenance, budget, ownership, compression, or agreement failure |
| 2 | Exact positive-premise quantifier elimination | One semilinear formula equivalent to the promoted premise and smaller than its table | Compare formula membership over all 77,824 inputs | High; exponential output is plausible | Timeout, 18-minterm output, or non-compression |
| 3 | T32 obstruction-core taxonomy | A compact set of countermodel signatures explains the rejected candidate frontier | Replay every recorded candidate/signature incidence | Low to medium, diagnostic only | Near-saturation, no compression, or no route to `P30` |

T33 selects rank 1 because it directly seeks the missing reachability-side
predicate while permitting the smallest structural relaxation not already
refuted by T31 or T32.

## Research and Prism provenance

Prism was checked after the T32 STOP using its configured
`muse-glimmer:30b-mlx` model. Both `frame_status` and a valid request using
invariant, graph/hypergraph, duality, and information-encoding frames failed at
the mathematical-operation boundary. No frame artifact was returned or
reconstructed.

Primary sources motivate discovery methods only:

- Brillout, Kroening, and Wahl give a complete interpolation method for
  quantifier-free Presburger arithmetic, with the exact separator obligations
  `A => I` and `I and B` inconsistent:
  <https://arxiv.org/abs/0811.3521>.
- Haase, Krishna, Madnani, Mishra, and Zetzsche give a singly exponential
  elimination procedure for one existential Presburger block while also
  proving that exponential output growth cannot generally be avoided:
  <https://arxiv.org/abs/2405.01183>.
- Komuravelli, Bjørner, Gurfinkel, and McMillan use model-based projection as
  a model-guided under-approximation in SMT verification:
  <https://arxiv.org/abs/1508.01288>.
- Hozzová and Bjørner extend model-based projection with witness production in
  a 2025 synthesis setting:
  <https://arxiv.org/abs/2504.16536>.

None proves that a compact safe-region cover exists for this repository
instance.

## Preservation boundary

T33 does not begin lower-layer extension, symbolic base lifting, base
comparison, topology scanning, publication work, or Lean formalization. It
must not stage or modify publication paths, unrelated notebooks, `.DS_Store`
files, `.timeloop/exam/results.jsonl`, `.timeloop/ledger.md`, or
`.timeloop/pool.jsonl`.

The protected preprint ZIP SHA-256 remains:

```text
e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33
```

This document authorizes only a subsequent implementation plan after user
review. It authorizes no T33 implementation or durable mathematical claim.
