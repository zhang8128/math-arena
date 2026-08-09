# T27 Base-19 Invariant and Base-Lift — Restart Design

## Decision

The next research round compresses the verified base-19 obstruction into a
small mathematical certificate before attempting any broader topology search.
It has two gates:

1. derive and independently check a non-tabular inductive explanation of the
   frozen 408-equation base-19 core; then
2. only if that explanation succeeds, lift it symbolically in the base.

The round does not run another undirected topology SAT census.  Completing the
Lean bridge remains assurance work and does not enter the critical path unless
the new mathematics exposes a bridge that is both small and reusable.

## Evidence baseline

The promoted evidence is
`publication/base19-radial/instance/equations.json` together with
`certificates/minimal-core-frontier.json`.  The fixed core is a
408-equation, deletion-minimal UNSAT system in base 19.  Exact radial
elimination has 35 layers, at most 12 live carries and two live digits, at most
314 reachable states, and 22 reachable inputs at terminal layer 33 with no
local model.

Repository-only analysis adds two structural facts that the next round must
reproduce before using them:

- 406 equations form 203 reversal-paired, same-addend column pairs; the other
  two are boundary equations; and
- replacing every pair by only its difference equation, even with the two
  boundary equations retained, is SAT for every tested base 17 through 40.

Thus a residue-only invariant is insufficient.  Any successful explanation
must retain carry-threshold or digit-sum information.  At the terminal layer,
all 12 equations are collectively essential for excluding the 22 reachable
states: deleting any one lets at least two states survive.  A uniform terminal
argument must therefore see the full six-phase cycle rather than blame one
column.

## Gate A: compact inductive obstruction

### Claim boundary

Produce an explicit certificate proving that the frozen base-19 408-equation
system is unsatisfiable.  The certificate must be expressed over canonical
radial-frontier coordinates and must establish:

1. **initiation:** the first reachable frontier satisfies the certificate;
2. **consecution:** every exact local radial transfer preserves the applicable
   certificate predicate; and
3. **exclusion:** no state satisfying the final predicate can satisfy the 12
   terminal equations.

This is not a theorem about the unbounded reverse-and-add process, all base-19
topologies, minimum-cardinality cores, or other bases.  The existing serialized
state sets remain the exact computational proof; Gate A succeeds only if it
compresses them into an independently checkable mathematical explanation.

### First falsifiable milestone

Work first on layers 25 through 33, where the reachable frontier contracts from
288 states to sets of size 20, 12, 12, 17, 16, 18, 18, and 22 before becoming
empty.  Canonicalize each state as phase-ordered left and right carry vectors
plus the one or two live digit coordinates.  Search the following bounded
predicate grammar in order:

1. integer linear equalities and inequalities with coefficients in
   `{-3,-2,-1,0,1,2,3}`;
2. congruences with moduli at most 20 using the same coefficients; and
3. conjunctions of at most 12 such atoms, and disjunctions of at most three
   such conjunctions, with explicit Boolean carry literals.

The milestone passes only if a predicate set derived from layers 25 through 32
excludes the terminal relation and is at least ten times smaller than the
corresponding explicit state tables.  Measure both as UTF-8 byte lengths of
canonical, key-sorted, whitespace-free JSON.  The milestone fails if the
bounded grammar is exhausted without such a certificate.  A failed milestone
is a valid measured result and stops Gate A before expanding the grammar.

### Derivation routes

Use two complementary routes, neither authoritative by itself:

- **state-driven synthesis:** counterexample-guided predicate synthesis over
  the promoted transition relation; and
- **proof-driven synthesis:** partition the exact bounded formula at radial
  cuts and extract candidate Craig interpolants or pseudo-Boolean
  cutting-plane consequences over the shared frontier variables.

Candidates from either route are simplified against the exact transition
relation.  Solver proofs may suggest a predicate, but the durable result is the
small predicate and its direct arithmetic verification, not a solver trace or
model narrative.

### Independent verification

The primary implementation may reuse the promoted frontier and solver
infrastructure.  The independent checker must read only the frozen equation
JSON and the proposed certificate.  It must not import T24, T25, T26, the
frontier generator, or the synthesis code.  It rebuilds each named radial
layer, exhausts the bounded digit/carry domains needed for each certificate
obligation, and checks initiation, consecution, and exclusion directly.

Every predicate is serialized with its scope, coefficient vector, modulus if
any, and exact layer mapping.  UNKNOWN, a missed transition, a mismatched state
digest, or disagreement between the two implementations fails closed.

## Gate B: symbolic lift in the base

### Claim boundary

Conditional on Gate A, attempt the theorem:

> For the exact T21 six-phase, two-interface incidence topology with arbitrary
> fixed digits, fixed repeat digits `0` and `b-1`, canonical leading digits,
> and fresh Boolean carries, base 17 is feasible and every integer base
> `b >= 18` is infeasible already at `n = 0`.

This extends the existing independently duplicated negative classification for
bases 18 through 40.  It does not classify other interface layouts, periods,
repeat alphabets, proof grammars, or Lychrel numbers.

### First falsifiable milestone

Rewrite every Gate A predicate and transfer obligation with symbolic base `b`.
Before attempting a universal proof, use the existing independent compact
encoding on bases 41 through 200 solely as a counterexample search.  A single
SAT base falsifies the universal theorem immediately; preserve its assignment
and replace the target with an exceptional-base classification rather than
continuing the universal proof.

If no counterexample appears, partition the symbolic obligations only where
digit bounds or carry thresholds change.  A successful lift must reduce the
infinite range to a finite, explicitly justified collection of Presburger or
integer-inequality cases.  Finite testing alone is never reported as an
all-base proof.

### Independent verification

The symbolic derivation is checked by a separate exact-arithmetic program that
does not call the synthesis solver.  It verifies each algebraic reduction,
checks the base-17 published witness as a positive control, and instantiates
every finite exceptional or boundary case in both existing concrete encodings.
If the derivation uses a periodic residue partition, the checker verifies both
the period argument and all representatives.

## Costs and stop conditions

Budget one to two focused research days for Gate A and an additional two to
five days for Gate B after Gate A passes.  Stop and report without weakening
the claim when any of the following occurs:

- the Gate A grammar yields only a renamed state table or less than tenfold
  compression;
- certificate obligations cannot be replayed without the synthesis code;
- the primary and independent checkers disagree;
- a base `b >= 18` satisfies the symbolic topology;
- symbolic case splitting grows with the tested base instead of closing into a
  finite argument; or
- the claimed explanation depends on a Prism-generated modulus, multiplier,
  or classification that has not been independently derived.

Success has two levels.  Level one is a compact independently replayed
base-19 inductive obstruction.  Level two is the all-base topology theorem, or
an exact exceptional-base classification if the universal statement is
falsified.

## Prism, literature, and assurance boundary

The live Prism frame database was unavailable behind a fail-closed offline
migration requirement, so no migration was attempted.  An isolated clean
ecology supplied invariant, modular/local-global, duality, and composed trial
frames.  One application was schema-invalid; every concrete invariant or base
classification from the three valid artifacts was independently falsified.
No Prism claim enters this design.  Its only retained influence is the choice
to test proof compression before expanding search.

Proof interpolation, current proof-derived UNSAT explanation tools, and
pseudo-Boolean cutting-plane certificates justify the two derivation routes.
They do not prove this obstruction.  PBLean or the existing `bv_decide` route
may later package a successful certificate in Lean, but formalizing the
integer-to-packed bridge remains a separate assurance project.  It is resumed
only after Gate A or Gate B yields a stable mathematical statement whose reuse
justifies the cost.

## Durable outputs

The round should add
`.timeloop/runs/t27_base19_invariant_lift.json`, containing the certificate,
obligation results, source digests, compression measurement, and precise claim
status; `.timeloop/runs/t27_base19_invariant_lift_independent.py`; focused
positive and negative tests; and a concise update to
`.timeloop/notebook/lychrel-bases.md`.  Gate B adds symbolic cases and concrete
counterexample-search results to the same evidence chain.  Publication sources,
the untracked `publication/base19-radial/preprint/` package, and its ZIP remain
out of scope.
