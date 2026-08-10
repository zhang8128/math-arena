# Base-19 Bad-Image Projection Restart Design

## Decision

T31 attempts to replace T30's explicit 18-state layer-30 premise with one
compact Presburger predicate `P30`.  Candidate discovery is directed by the
exact bad-successor image of T30's five-equation predicate `Q0`; it is not a
second undirected guard scan and does not fit an unrestricted atom pool to the
18 promoted rows.

This is a bounded theorem about the frozen base-19 radial obstruction with
removed coordinate `phase=0,n=0,column=82`.  T31 neither extends to layer 29
nor changes T29, T30, the topology, the base, the publication package, or the
Lean boundary.

## Exact claim boundary

Let:

- `R30(u)` mean that `u` is one of the 18 promoted layer-30 frontier states;
- `T30_31(u,x)` be the original 12 layer-30-to-31 integer equations with the
  exact digit and carry domains; and
- `Q0(x)` be T30's immutable five-equation layer-31 predicate.

T31 may claim `BAD_IMAGE_PROJECTION_PASS` only for a serialized predicate
`P30(u)` satisfying all of these obligations:

1. **Promoted coverage:** `R30(u) implies P30(u)` for all 18 promoted states.
2. **Exact image soundness:**
   `P30(u) and T30_31(u,x) implies Q0(x)` over the complete bounded domain.
3. **Compactness:** the canonical predicate is smaller than the canonical
   18-state table and stays within the frozen T31 grammar below.
4. **Independent agreement:** a standard-library checker independently
   reproduces coverage, compactness, and the universal image implication.

PASS does not assert that `P30` equals `R30`, equals the complete set of
reachable layer-30 interfaces, or is the weakest precondition of `Q0`.
`P30` is a compact, sound generalization of the promoted premise.  The exact
weakest precondition is a diagnostic oracle only.

Combined with T30, PASS permits the same bounded consequence:

```text
P30(u) and T30_31(u,x) and S29(x) and T31_32(x,y) is UNSAT.
```

T31 replays this composition as a consistency check but does not modify or
merge `P30`, `Q0`, or `S29`.

## Frozen predicate grammar and readability gate

`P30` uses the canonical 13-variable layer-30 interface

```text
L0,R0,L1,R1,L2,R2,L3,R3,L4,R4,L5,R5,D0
```

with carry variables in `{0,1}` and `D0` in `{0,...,18}`.  The grammar is
fixed before synthesis:

- at most two disjunctive clauses;
- at most six atoms on either evaluation path;
- affine equality, affine `<=`, and congruence atoms only;
- integer coefficients in `{-9,...,9}`;
- congruence moduli in `{2,...,19}`;
- at most 13 variables in one atom; and
- no state index, digest, per-state selector, nonlinear term, auxiliary
  Boolean, or lookup operation.

The coefficient ceiling is T31-local.  It does not widen the immutable T27,
T29, or T30 predicate types.  Canonical predicate bytes must be strictly fewer
than canonical bytes for the 18 promoted rows.  A candidate that is an
explicit-state disjunction, a collection of state minterms, or otherwise a
renamed state table is rejected even if its byte count passes.

Synthesis may inspect at most 64 canonical bad-image counterexamples.  It may
not widen the grammar, add clauses, restart from a generic atom scan, or relax
the compactness gate when that budget is exhausted.

The likely cost is moderate and explicitly bounded: at most 64 primary
counterexample refinements, one complete independent pass over 77,824 inputs
with local constraint solving, four narrowly scoped implementation files, and
four durable artifacts only after agreement.  The first milestone deliberately
precedes report, notebook, and broad-regression work so a failed candidate does
not incur the rest of the round.

## Preliminary repository evidence

The following read-only probes selected the round but are not certificates:

- The 18 promoted layer-30 states have affine dimension ten in the
  13-variable interface.
- Their affine hull has two small equalities and one digit-bearing base-19
  congruence.  No digit-bearing congruence with coefficients bounded by three
  holds on all 18 states.
- The natural three-atom hull accepts 384 bounded interfaces and has an exact
  `not Q0` successor.  Therefore affine-hull transport is already falsified.
- Z3 projection found 21,477 of the 77,824 bounded layer-30 interfaces with at
  least one `not Q0` successor.
- Exact satisfiability probes found 27 of the 31 possible nonempty subsets of
  violated `Q0` equations.  A small semantic-leak-type partition is therefore
  not the lead program.

The 21,477 count and 27-type observation must be independently reproduced
before they may appear as durable diagnostics.  Neither count is a PASS gate,
and neither may be used as a substitute for the universal implication.

## Directed construction

Define the exact bad-image formula

```text
B(u) := exists x,local . T30_31(u,x) and not Q0(x).
```

The primary discovery route proceeds as follows:

1. Bind the equation manifest, minimal-core frontier, all five T29 artifacts,
   and all four T30 artifacts by their existing raw hashes.
2. Decompose `not Q0` by the five failed equations and project each resulting
   relation toward the 13 input variables.  Quantifier elimination,
   proof-derived arithmetic consequences, and interpolation may propose
   atoms; their output remains hypothesis-only.
3. Keep only canonical atoms that hold on all 18 promoted states and arise
   from one recorded bad-image projection.  Do not add an atom merely because
   it separates the finite table.
4. Assemble candidates deterministically by objective:
   `(clause_count, max_path_atoms, total_atoms, total_support,
   coefficient_l1, canonical_bytes)`.
5. Ask for a model of `P30 and B`.  On SAT, record the lexicographically least
   complete input/output/local witness and refine from its failed-equation
   projection.  On UNSAT, advance the candidate to independent verification.

Projection is a discovery mechanism, not proof.  The accepted implication is
decided only by the exact universal solver query and the independent checker.
No raw solver proof, interpolation narrative, or synthesis score is treated
as evidence.

## First falsifiable milestone

Before creating any durable T31 artifact, produce one repository-derived
candidate `P30-v0` and a temporary constructive certificate containing:

- the canonical predicate and its projection provenance;
- direct evaluation on all 18 promoted states;
- the exact result of `P30 and T30_31 and not Q0`;
- the candidate and state-table byte counts; and
- a complete canonical witness if the implication is SAT.

The milestone passes only when the implication is UNSAT and the independent
checker agrees.  A SAT witness, grammar overflow, table-shaped predicate,
non-compression, solver `UNKNOWN`, or independent disagreement ends T31 with
`BAD_IMAGE_PROJECTION_STOP`.  T31 does not attempt exact weakest-precondition
elimination or semantic-leak typing as an in-round fallback.

## Certificate architecture

The T31 certificate binds the frozen source, T29, and T30 hashes and records:

- the canonical `P30` predicate;
- its grammar and compactness measurements;
- promoted coverage count and digest;
- the exact implication status and equation count;
- bad-image discovery provenance and counterexample count;
- the composed T30 consequence status; and
- a complete witness for the first failed obligation, or `null` on PASS.

The certificate does not copy the 18 promoted states or the projected bad
set.  It references the frontier and T30 certificate by digest.  Discovery
traces remain separate from proof evidence.

## Primary and independent verification

The primary checker uses Z3 and the repository's strict frozen-input loaders.
It checks hashes and grammar before mathematics, evaluates all promoted rows,
proves or refutes the exact image implication, replays the composed T30
consequence, and emits a lexicographically canonical witness on SAT.  Every
solver `UNKNOWN` fails closed.

The independent checker imports no repository module, Z3, or T27--T31
implementation.  From raw JSON it rebuilds the 12 local equations and exact
domains, parses `P30` and `Q0` separately, and uses generalized arc
consistency plus deterministic backtracking to:

- evaluate `P30` on the 18 promoted states;
- enumerate the complete 77,824-state layer-30 input domain;
- reject any `P30` input with an exact `not Q0` successor;
- reproduce compactness measurements; and
- replay the composed T30 consequence.

Mutation tests must reject a coefficient, constant, modulus, clause, source
digest, coverage count, implication status, compactness value, and SAT/UNSAT
witness mutation.  Primary and independent outputs must be byte-stable across
two fresh runs before promotion.

## Components and durable outputs

The implementation plan should create narrowly scoped T31 files:

- `.timeloop/lib/lychrel_bad_image_projection.py` for immutable T31 predicate,
  result, and certificate types;
- `.timeloop/runs/t31_base19_bad_image_projection.py` for frozen adapters,
  directed discovery, exact checks, and report rendering;
- `.timeloop/runs/t31_base19_bad_image_projection_independent.py` for the
  isolated standard-library replay; and
- `.timeloop/tests/test_lychrel_bad_image_projection.py` for syntax, real
  evidence, determinism, isolation, and mutation tests.

Only after primary and independent agreement may the round write T31
evidence, certificate, independent-audit, and report artifacts.  The notebook
receives only the achieved PASS or STOP boundary after full assurance.

## Frozen preservation boundary

T31 may read but never modify T27--T30 artifacts.  It must preserve all five
raw T29 hashes, all four raw T30 hashes, and the protected preprint ZIP hash

```text
e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33
```

Publication paths, unrelated notebooks, `.DS_Store` files, and the existing
Timeloop ledger, pool, and exam changes stay outside every T31 commit.  No
lower-layer extension, symbolic-base lift, base comparison, topology scan,
publication change, or Lean work is authorized.

## Ranked alternatives and stop boundaries

1. **Selected: targeted bad-image projection.**  Its exact claim is the
   coverage, compactness, and image-soundness theorem above.  Its first
   falsifiable milestone is `P30-v0`; its independent method is complete
   77,824-input standard-library replay; its likely cost is the bounded
   moderate workload above; and any failed milestone obligation stops T31.

2. **Exact weakest-precondition elimination.**  Its claim would be a formula
   `W30(u)` equivalent over the complete bounded interface to `not B(u)`, not
   merely sound on the promoted states.  Its first milestone would be one
   canonical eliminated formula that is smaller than the state table.  An
   isolated enumerator would compare `W30` with exact successor search on all
   77,824 inputs.  Its likely cost is high because elimination can cause
   exponential formula growth.  Stop if elimination is unknown,
   nondeterministic, exceeds the selected round's resource bound, or fails the
   grammar, byte-size, or full-domain equivalence check.

Full Presburger elimination of `B(u)` remains the nearest alternative.  It
would characterize the exact weakest precondition, but its result may grow
exponentially and serialize much of the 77,824-state domain.  Projected
subformulas may propose candidate atoms in T31, but the full exact weakest
precondition is neither an accepted result nor an in-round fallback.  A
proposal derived from elimination still has to meet the frozen grammar,
compactness, and independent-verification gates.

3. **Semantic-leak type extraction.**  Its claim would be a small, exhaustive
   family of structural bad-successor types, each defined independently of
   row identity, whose complement covers the 18 promoted inputs.  Its first
   milestone would compress the observed 27 nonempty failed-equation subsets
   into fewer canonical structural types while preserving an exact witness for
   every member.  Independent verification would classify every bad input by
   full-domain enumeration and reject missing or overlapping provenance.  Its
   likely cost is medium to high because 27 of 31 failure masks are already
   realized.  Stop if the first family is no smaller than the equation-failure
   masks, depends on state identities, or is not exhaustive.  This is not a
   separate T31 target and would require a new decision after T31.

Haase, Krishna, Madnani, Mishra, and Zetzsche give current primary-source
support for singly exponential elimination of one existential Presburger
block: <https://arxiv.org/abs/2405.01183>.  Griggio, Le, and Sebastiani give
proof-based interpolation methods for linear integer arithmetic:
<https://arxiv.org/abs/1010.4422>.  Prabhu et al. provide infer-check-weaken
precedent for nondeterministic weakest-precondition synthesis:
<https://link.springer.com/chapter/10.1007/978-3-031-57249-4_9>.  These methods
motivate discovery only; none proves `P30` or any reverse-and-add claim.

## Prism provenance

Prism's Ollama default was changed to `muse-glimmer:30b-mlx` in Prism commit
`5629f09`, and that model answered a live probe.  Mathematical `frame_status`
still failed closed because the existing `~/.prism/math-frames.db` schema is
not accepted by the current store or its supported offline migrator.  No live
database migration ran, no frame artifact was created, and no Prism output is
a premise of T31.

## Verification checkpoint

The implementation plan must stop at the temporary `P30-v0` milestone until
both verification routes agree.  A PASS then authorizes deterministic durable
artifacts, adjacent T27--T30 regression, full Timeloop tests, Ruff, JSON and
Git-diff hygiene, raw-hash audits, and the concise notebook conclusion.  A
STOP records the first exact failure and ends the round without a fallback.
