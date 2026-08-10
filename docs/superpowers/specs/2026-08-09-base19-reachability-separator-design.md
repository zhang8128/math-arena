# Base-19 Reachability-Aware Separator Design

## Purpose

T29 tests whether the failure exposed by T28 has a compact explanation.  T28
found that the four successor-signature classes on 18 promoted layer-31 states
do not extend to a readable semantic quotient over the full bounded frontier:
states classified as `DEAD` can still have exact layer-32 successors.  T29 asks
for a compact predicate distinguishing the 12 promoted `DEAD` states from
those successor-bearing look-alikes.

The round is limited to the frozen base-19 radial obstruction, removed
coordinate `phase=0,n=0,column=82`, and the exact layer-31-to-layer-32 local
relation.  It does not change the preprint's obstruction certificate, T27's
terminal lemma, or T28's bounded STOP conclusion.

## Mathematical claim boundary

T29 separates two claims.

1. **Finite separation.** A specified predicate is true on all 12 promoted
   `DEAD` states and false on the complete deterministic T28 counterexample
   trace plus the six promoted live states.
2. **Semantic dead region.** The same predicate universally implies that no
   layer-32 successor exists under the original 12 local equations.

Finite separation is not a reachability invariant, inductive invariant, or
dead-region theorem.  Semantic promotion is claimed only if the universal
query passes both primary and independent verification.  Neither outcome
classifies other bases, topologies, or unbounded reverse-and-add orbits.

## Frozen inputs and preservation

The equation manifest, promoted frontier, selected provenances, T27 evidence,
T28 evidence, and T28 independent audit are immutable inputs.  T29 binds their
raw or content SHA-256 values before replay.  The pre-existing publication
package and ZIP, publication deletions, Timeloop ledger/exam/pool changes,
notebook files, and `.DS_Store` files remain outside every T29 commit.

T28 may gain one deterministic trace-replay interface.  Its durable evidence,
report, independent audit, schemas, hashes, and conclusion must not change.

## Prism and research provenance

The updated Math Prism was checked before this design.  Both `frame_status` and
a valid four-frame `frame_problem` request failed at the mathematical-frame
operation boundary.  No migration or database mutation is authorized, no
frame artifact is available, and no Prism output is reconstructed or used as
a premise.

Three manual frames remain hypothesis generators:

- backward reachable-set separation;
- counterexample-guided abstract-interpretation refinement;
- symbolic-automata congruence refinement.

König, Rensink, Stoltenow, and Urrigshardt provide current precedent for
counterexample-guided predicate refinement in reactive systems
<https://arxiv.org/abs/2504.08617>.  D'Antoni, Kincaid, and Wang provide
symbolic-automata and bisimulation-up-to-congruence precedent
<https://arxiv.org/abs/1610.01722>.  Cimatti, Griggio, and Sebastiani provide
the optional proof-based interpolation route
<https://arxiv.org/abs/0906.4492>.  None proves or predicts a T29 result.

## Architecture

### 1. Deterministic T28 trace reconstruction

Rerun the exact T28 layer-31 synthesis and export every distinct
`dead_has_no_successor` counterexample in discovery order.  The trace records
the iteration, canonical 14-coordinate input state, rejected class,
obligation, candidate-atom count, and readability measurements available
before rebuilding the next candidate.  Replay twice and require byte identity.

The expected achieved trace contains 221 distinct counterexamples.  T28 stops
while building candidate 222, before that candidate can produce another exact
counterexample, and ends at `decision_depth_exceeded`.  These counts are
falsifiable repository expectations, not assumptions: a different count,
order, state, iteration, or terminal reason fails closed before separator
synthesis.

### 2. Frozen finite dataset

The positive set is exactly the 12 promoted layer-31 states in T28's `DEAD`
successor-signature class.  The negative set is the reconstructed 221-state
counterexample trace plus the six promoted live layer-31 states.  The adapter
requires the two sets to be canonical, duplicate-free, disjoint, and scoped to
the same 14 variables.

The live controls prevent a predicate that merely distinguishes promoted from
unpromoted states while accidentally absorbing a verified live class.

### 3. Readable separator synthesis

Candidate atoms use T27/T28's frozen arithmetic grammar:

- integral coefficients in `{-3,-2,-1,0,1,2,3}`;
- affine equality and inequality;
- congruence moduli `2..20`;
- no products, nonlinear terms, lookup tables, or renamed state identifiers.

The predicate is a disjunction of at most three conjunctions, each containing
at most 12 atoms.  Simpler one-clause and two-clause sublanguages are attempted
first, but the ceiling is frozen before execution and is never enlarged after
failure.  Candidate generation may use pairwise separators, exact preimage
expressions already inside the grammar, or proof-derived interpolation only as
hypothesis sources.

The canonical atom pool is capped at 512.  Synthesis minimizes, in order,
clause count, total atom count, maximum clause width, coefficient support,
absolute coefficient sum, relation rank, modulus, and canonical bytes.  Solver
`UNKNOWN`, a pool overflow, or nondeterministic optimum is a STOP, not PASS.

### 4. Exact semantic promotion

Only a finite-separation PASS reaches semantic promotion.  The primary checker
asks whether the predicate and the original 12 layer-32 equations have a joint
model.  UNSAT establishes the bounded semantic dead-region claim.  SAT returns
the lexicographically first complete input/output/local assignment as a new
counterexample.  T29 does not silently feed that model back into a larger
grammar; it records the semantic STOP at the approved boundary.

### 5. Independent assurance

An isolated Python standard-library checker consumes only frozen JSON inputs
and the T29 evidence/certificate.  It imports no repository module, Z3, or
T27--T29 implementation.  It independently:

- recomputes source and trace hashes;
- reconstructs the promoted positive and live-control sets;
- evaluates the predicate on all 239 finite examples;
- enforces the grammar and readability limits;
- rebuilds allowed tuples for the 12 local equations;
- proves semantic UNSAT by constraint propagation and backtracking, or replays
  the primary SAT witness exactly.

Primary and independent disagreement changes the durable conclusion to STOP.

## Components

- `.timeloop/lib/lychrel_reachability_separator.py` owns immutable trace,
  dataset, predicate, and certificate syntax plus canonical evaluation.
- `.timeloop/runs/t29_base19_reachability_separator.py` owns frozen adapters,
  trace replay, atom generation, separator synthesis, primary semantic checks,
  deterministic evidence, and report rendering.
- `.timeloop/runs/t29_base19_reachability_separator_independent.py` owns the
  standalone parser and independent finite/semantic replay.
- `.timeloop/tests/test_lychrel_reachability_separator.py` owns focused unit,
  real-artifact, isolation, and mutation tests.
- Durable T29 JSON and Markdown artifacts are created only after primary and
  independent agreement.

## Outcomes and stop conditions

T29 produces exactly one of these conclusions:

1. `FINITE_SEPARATOR_STOP`: no predicate is accepted within the frozen finite
   grammar, or finite construction/assurance fails.
2. `FINITE_SEPARATOR_PASS_SEMANTIC_STOP`: finite separation passes, but the
   exact semantic query is SAT or semantic assurance fails.
3. `SEMANTIC_DEAD_REGION_PASS`: finite separation passes and both checkers
   establish semantic UNSAT.

Digest mismatch, malformed evidence, trace disagreement, missing controls,
unsupported syntax, candidate-pool overflow, solver `UNKNOWN`, a noncanonical
witness, mutation survival, or checker disagreement fails closed.  A bounded
STOP is not evidence that no human-readable reachability invariant exists.

## First falsifiable milestone

Before semantic promotion, reproduce exactly 221 unique T28 counterexamples
and determine whether a frozen-language predicate separates the resulting 12
positive and 227 negative states.  The milestone ends with a deterministic
finite certificate or a precise bounded STOP.  No semantic theorem is implied
by this milestone alone.

## Verification and mutations

Tests must reject mutation of any reconstructed counterexample, promoted
label, live control, atom term, constant, relation, modulus, clause membership,
source hash, trace hash, semantic status, or exact witness value.  Two primary
runs and two independent runs must be byte-identical.  Compilation, Ruff,
focused T29 tests, adjacent T27/T28 tests, JSON validation, independent replay,
Git diff hygiene, and the existing publication-ZIP digest are required before
the final conclusion.

## Cost and checkpoint

The expected cost is several focused hours when a simple separator exists and
up to roughly one research day if three-clause synthesis or independent
semantic checking dominates.  Checkpoint immediately after finite separation.
No lower-layer extension, symbolic base lift, base comparison, topology scan,
publication update, or Lean bridge is authorized by T29.

## Next decision

If semantic promotion passes, a later round may ask whether the predicate is
implied by a compact earlier-layer reachability condition.  If it stops, the
durable trace and first new semantic counterexample determine whether to study
exact weakest preimages, refine the semantic partition, or end this line.  T29
itself performs none of those expansions.
