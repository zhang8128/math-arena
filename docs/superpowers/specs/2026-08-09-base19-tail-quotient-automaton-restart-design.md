# T28 Base-19 Tail Quotient Automaton — Restart Design

## Decision

The next research round attempts to replace T27's failed literal predicate
transport with a small, phase-indexed symbolic quotient automaton.  It starts
with the exact layer-31 weakest preimage of the three verified layer-32
terminal families and, only after that passes, extends backward one layer at a
time through layer 25.

This is a deeper explanation of the same frozen obstruction, not a second
base-19 problem and not a replacement for the preprint.  The preprint retains
the end-to-end 35-layer frontier certificate for the deletion-minimal
408-equation core.  T28 asks whether a readable relational certificate can
explain a bounded tail of that computation.  It does not run an undirected SAT
scan, alter the publication package, lift the result in the base, or resume the
Lean bridge.

## Ranked research programs

1. **Layered symbolic quotient automaton — selected.**  Claim boundary: an
   exact relational certificate for layers 31--32, then conditionally 25--32,
   of the frozen base-19 obstruction.  First falsifiable milestone: four
   layer-31 classes (dead plus one predecessor type for each terminal family)
   with universal bounded-domain transition checks.  Verification: an exact
   primary checker and a repository-independent standard-library replay.
   Likely cost: hours to roughly two focused days.  Stop if the first layer
   fails the frozen arithmetic grammar or any later layer exceeds the agreed
   readability bounds.
2. **Full Presburger weakest precondition — semantic fallback only.**  Claim
   boundary: a quantifier-eliminated description of the exact preimage of the
   terminal relation.  First milestone: eliminate the layer-31 local variables
   without enumerating frontier states.  Verification: substitute the result
   back into the original bounded formula and exhaust counterexamples.
   Likely cost: one to three focused days with substantial expression-growth
   risk.  Stop if elimination does not yield a finite expression within the
   round or merely serializes the state table.  T28 may use this route to check
   automaton guards, but it will not promote an unreadable formula as success.
3. **Phase-cyclic symbolic base lift — deferred.**  Claim boundary: explain,
   for this exact topology, why the relevant algebra closes in base 17 but not
   base 19 and determine whether the explanation classifies other bases.
   First milestone: lift a verified layer-31/32 transition law to symbolic
   `b` and recover both concrete bases.  Verification: exact arithmetic plus
   independent concrete instantiation.  Likely cost: three to seven focused
   days.  Stop if cases grow with `b` or no finite threshold/residue partition
   emerges.  This target is not started until the automaton supplies stable
   mathematics to lift.

## Frozen evidence and hypotheses

The authoritative input remains the promoted 408-equation base-19 obstruction
with removed coordinate `phase=0,n=0,column=82`.  T27 bound the following
content digests:

- equations:
  `ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040`;
- frontier:
  `0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0`;
- provenances:
  `cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302`.

T27 proved that all 22 promoted layer-32 states fall into three arithmetic
families of sizes 8, 8, and 6 and that each family is inconsistent with the 12
terminal equations.  Its independent audit passed.  T27 stopped because
literal transport did not produce an accepted layer-31 predicate and the
terminal predicate compressed the layer-25--32 state payload by only about
2.42 times, below that round's tenfold gate.  T28 preserves that negative
result: it broadens Boolean structure from a three-clause DNF to a relational
automaton while keeping the arithmetic atoms bounded.

A read-only successor-signature diagnostic produced the following candidate
quotient sizes on promoted reachable states:

| Layer | Raw states | Candidate classes |
|---:|---:|---:|
| 32 | 22 | 3 |
| 31 | 18 | 4 |
| 30 | 18 | 5 |
| 29 | 16 | 6 |
| 28 | 17 | 7 |
| 27 | 12 | 7 |
| 26 | 12 | 5 |
| 25 | 20 | 5 |

At layer 31 the observed classes contain 12 dead states and 1, 2, and 3
states whose successors enter only terminal families 0, 1, and 2,
respectively.  These counts are discovery hypotheses only.  They must be
reproduced from frozen evidence and confer no validity on a symbolic guard.

The untracked `publication/base19-radial/preprint/` package and
`publication/base19-radial/preprint.zip` remain user-owned and out of scope.
The ZIP's preservation digest at design time is
`e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33`.

## Exact claim boundary

The first theorem sought is:

> Every promoted reachable layer-31 state belongs to one of four disjoint
> symbolic classes.  Every state in the dead class has no exact bounded local
> successor.  Every state in a live class has an exact successor, and all of
> its exact successors belong to the designated layer-32 terminal family.
> Every recorded quotient edge has an exact witness.

Together with T27's independently checked terminal exclusions, this is an
exact tail lemma.  If it passes, repeat the construction backward through
layer 25 and initiate the resulting automaton on all 20 promoted layer-25
states.

The result continues to depend on the promoted frontier for its reachability
premise.  It does not independently reprove the complete 408-equation core,
establish uniqueness or minimality of the quotient, classify other
topologies or bases, prove anything about an unbounded reverse-and-add orbit,
or create a new Lean theorem.

## Certificate architecture

For each layer `l`, the certificate contains a finite class set `Q_l`, a
symbolic guard for every semantic class, and an allowed edge relation into
`Q_(l+1)`.  Guards are partial over the complete bounded frontier domain.  The
complement of their union is an explicit outside sink, so the transition
system is total without treating arbitrary states as invariant states.

Semantic guards must be pairwise disjoint.  A dead guard admits no exact local
successor.  Every state satisfying a live guard admits at least one exact
local successor, and every such successor satisfies a class on an allowed
edge.  Every serialized edge also carries or references a concrete exact
witness, preventing harmless-but-spurious edges from being reported as
structure.

Guards use the T27 arithmetic atom vocabulary: affine equalities and
inequalities with coefficients in `{-3,-2,-1,0,1,2,3}`, congruences with
moduli 2 through 20, and canonical digit/carry frontier variables.  Their
Boolean representation is a reduced, shared decision DAG whose leaves are
class labels or the outside sink.  This preserves disjunction structure and
shares tests instead of forcing each class into an independent conjunction or
three-clause DNF.

The machine-readable artifact is accompanied by a compact report listing each
class guard, live/dead status, outgoing edges, witnesses, representative
reachable states, and failed simplifications.  Synthesis traces stay separate
from proof evidence.

## Construction and data flow

1. A frozen-evidence adapter checks the source digests and loads the equations,
   promoted reachable states, exact local relations, and T27 terminal
   exclusions.
2. A discovery pass labels layer-32 states by terminal family and recursively
   groups earlier reachable states by exact successor signature.  It proposes
   partitions but proves nothing.
3. Guard synthesis builds a shared decision DAG for the proposed partition,
   using exact counterexamples from the complete bounded domain to refine or
   reject candidate guards.
4. The primary verifier checks guard disjointness, promoted-state coverage,
   live/dead semantics, universal edge soundness, edge witnesses, and terminal
   exclusion.  UNKNOWN, a digest mismatch, or an unclassified promoted state
   fails closed.
5. An isolated standard-library checker consumes only frozen JSON and the
   exported certificate.  It rebuilds the required bounded relations without
   importing the synthesizer, primary verifier, T24--T28 modules, or repository
   solver helpers.

The primary route may use SMT to refute counterexamples.  The independent
route must use separately implemented exact enumeration, constraint
propagation, and backtracking.  Agreement is required; solver narratives are
not evidence.

## Gates and measurements

1. **Evidence identity.**  Recompute and match every frozen content digest and
   structural count before synthesis.
2. **Layer 31.**  Produce exactly four semantic classes, cover all 18 promoted
   states, and pass every exact and independent obligation.  Failure stops the
   automaton program for this grammar; it is not an impossibility theorem.
3. **Backward extension.**  Attempt layers 30 through 25 sequentially.  A
   failing layer preserves the longest already verified tail and its first
   exact counterexample.
4. **Explanatory value.**  Permit at most eight semantic classes and 64 unique
   decision nodes per synthesized layer.  Newly synthesized layers may test
   at most ten atoms on any evaluation path.  The frozen layer-32 seed is
   exempt from that path cap because its already verified conjunctions contain
   11, 11, and 10 atoms; it retains T27's 12-atom clause cap.  For the maximal
   successful interval, canonical guards and edges must occupy fewer UTF-8
   bytes than the canonical explicit state-and-transition table they replace.
   Witnesses and audit metadata are retained but excluded from this explanatory
   compression comparison.
5. **Independent assurance.**  Primary and independent checkers must agree.
   Mutating a guard atom, class label, live/dead status, required edge, witness,
   or terminal law must cause rejection.

Stop rather than expand the grammar when the layer-31 milestone fails, a later
layer exceeds a readability bound, a counterexample cannot be repaired without
changing the semantic partition, the checkers disagree, or the certificate
does not compress the explicit relation.  A stopped round records the longest
verified tail, the precise boundary, and a deterministic counterexample.

Success at layer 25 ends T28.  Extending toward layer 0, lifting symbolically
in `b`, comparing base 17 with base 19, or packaging the result in Lean each
requires a separate research decision.

## Prism and primary-source boundary

The newly updated Math Prism was checked before selecting this program.
`frame_status` and a valid framing request both failed closed with
`MathFrameStoreOfflineMigrationRequired`, reason
`unrecognized_structural_layout_exceeds_inline_cap`, generation 2, schema
cookie 150.  No migration or database mutation was authorized, no current
Prism frame artifact was obtained, and no output was fabricated.

The problem was therefore compared manually through three falsifiable frames:
finite-state quotient/bisimulation, full Presburger weakest precondition, and
phase-cyclic algebraic lift.  The repository diagnostic favored the first;
the second remains a semantic checker and the third is deferred.  These are
research hypotheses, not premises.

D'Antoni, Kincaid, and Wang's symbolic alternating-automata procedure provides
primary-source precedent for symbolic transition representations and
bisimulation-up-to-congruence reasoning:
<https://arxiv.org/abs/1610.01722>.  Cimatti, Griggio, and Sebastiani provide
the proof-based interpolation background relevant to the fallback preimage
route: <https://arxiv.org/abs/0906.4492>.  Neither source proves or predicts
this reverse-and-add quotient.

## Durable output and restart point

The round should produce one deterministic T28 evidence JSON, one exported
automaton certificate, an isolated independent checker and audit JSON,
focused positive and mutation tests, and a concise notebook update.  Exact
paths and implementation tasks belong in the subsequent execution plan.

Restart by writing that plan.  Its first implementation milestone must stop
after reproducing the frozen evidence and proving or falsifying the four-class
layer-31 certificate.  Do not begin layer 30, a base lift, a topology scan, or
Lean work before that milestone passes both verification routes.
