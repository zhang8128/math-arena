# Base-19 Semantic-Leak Types Restart Design

## Decision

T32 is a bounded diagnostic round over the frozen base-19 radial
layer-30-to-31 relation. It asks whether exact successors violating T30's
five-equation predicate `Q0` admit a small family of structural carry/digit
mechanisms. It does not attempt another layer-30 predicate `P30`, and it does
not resume T31's projection search.

The selected approach is a counterexample-guided **structural mechanism
cover**. Every accepted type must explain a `Q0` failure from the original 12
transfer equations without mentioning a promoted-row identity, a state index,
or a `Q0` failure literal. The round stops at its first failed gate.

## Frozen boundary

Let:

- `u` be the 13 canonical layer-30 input variables;
- `x` be the 14 canonical layer-31 output variables;
- `z` be the ten local digit variables in the exact relation;
- `T(u,x,z)` be the original 12 base-19 equations with exact digit and carry
  domains; and
- `Q0(x)` be T30's immutable five-equation predicate.

T31 ended at `NO_CANDIDATE`: its 26 `qe-light`-derived hypothesis atoms were
domain bounds, and the first canonical exact bad image satisfied all of them.
That witness was constructively replayed with twelve zero residuals and
`Q0 = false`. This establishes only the T31 pool boundary; it does not rule out
all compact layer-30 predicates.

T29, T30, and T31 source bytes are read-only. In particular, all five T29
artifact hashes, all four T30 artifact hashes, and the protected preprint ZIP
hash remain frozen. T32 may use the T31 runner to reconstruct the relation and
replay the canonical witness, but it may not change T31's code, tests, result,
or stop detail.

## Exact claim boundary

A structural type `tau_i(u,x,z)` is a conjunction from the frozen feature
language below. A family `F = (tau_0,...,tau_k)` may receive
`SEMANTIC_LEAK_TYPES_PASS` only if all of these exact obligations hold:

1. **Type soundness:** for every `tau_i`,
   `T and tau_i and Q0` is UNSAT.
2. **Family exhaustiveness:**
   `T and not Q0 and not(tau_0 or ... or tau_k)` is UNSAT.
3. **Structural diversity:** each type has exact witnesses from at least two
   distinct layer-30 inputs and two distinct five-bit `Q0` failure masks.
4. **Compactness:** the canonical family is smaller than the canonical exact
   bad-input table reconstructed during independent full-domain replay.
5. **Independent agreement:** an isolated checker reproduces soundness,
   exhaustiveness, diversity, and compactness from frozen raw inputs.

Types may overlap. For counts and replay, a witness belongs to the first
matching type in canonical family order. PASS therefore claims an exhaustive
mechanism cover, not a unique natural taxonomy, a weakest precondition, a
reachability invariant, or a new reverse-and-add theorem.

T32 does not derive the requested layer-30 predicate `Q`. A successful family
would justify a later, separately approved attempt to project the complement
of its mechanisms toward the input interface.

## Frozen structural feature language

For phase `i`, let `a_i,b_i` be the two digit summands used by that phase's
paired equations, and let `L_i^in,R_i^in,L_i^out,R_i^out` be their canonical
input and output carries. The phase-5 literal target remains the base-19 digit
`18` and is not generalized.

One type contains at most six literals chosen from:

- `a_i = b_i`, `a_i < b_i`, or `a_i > b_i`;
- `a_i + b_i < 19`, `= 18`, or `>= 19`;
- equality or inequality of the paired input carries
  `L_i^in` and `R_i^in`;
- equality or inequality of the paired output carries
  `L_i^out` and `R_i^out`; and
- equality or inequality of the same-side input/output carries
  `L_i^in,L_i^out` or `R_i^in,R_i^out`.

The complete candidate pool is generated deterministically from those schemas
for the six fixed phases. No unary digit-value test, arbitrary affine atom,
congruence, nonlinear term, auxiliary variable, state hash, row number, or
direct test of a `Q0` equation is allowed. Constants other than the structural
base thresholds `18` and `19` are forbidden. A candidate is rejected as a
state minterm if the exact relation plus that candidate permits only one
layer-30 input.

The family contains at most eight types. Candidate ordering is fixed by
`(literal_count, distinct_phase_count, variable_support, canonical_bytes)`.
Discovery may inspect at most 256 distinct canonical uncovered witnesses and
test at most 10,000 candidate conjunctions. The grammar and budgets never
widen in-round.

## First falsifiable milestone

Before family synthesis or durable T32 artifacts, construct one temporary type
`tau_0` satisfying all of the following:

- it contains at most six structural literals;
- the committed T31 canonical bad-image witness satisfies it;
- a second exact bad image with a different layer-30 input and different
  `Q0` failure mask satisfies it;
- `T and tau_0 and Q0` is UNSAT in the primary solver; and
- the isolated checker reconstructs both witnesses, replays all 12 residuals,
  and independently confirms the UNSAT obligation.

Discovery may examine at most 128 canonical exact bad images and 2,000
candidate conjunctions for this milestone. `UNKNOWN`, disagreement, a direct
failure-mask encoding, a singleton mechanism, or exhaustion of either budget
ends T32 at `SEMANTIC_LEAK_TYPES_STOP`. On STOP, do not synthesize a family,
run the full-domain audit, create durable result artifacts, or update the
notebook.

## Bounded construction after the milestone

If and only if `tau_0` passes:

1. Bind the equation manifest, frontier, five T29 artifacts, four T30
   artifacts, and T31 implementation commits `69022cb`, `adc6986`, `619b737`,
   and `6835036` plus their witness boundary.
2. Ask for the lexicographically least model of
   `T and not Q0 and not(any current type)`.
3. Generalize that model using only the frozen structural feature pool. Retain
   a type only after the exact soundness query is UNSAT and two-mask diversity
   has constructive witnesses.
4. Select at most eight types by the canonical objective and repeat until the
   exhaustiveness query is UNSAT or the 256-witness/10,000-candidate budget is
   exhausted.
5. Run independent full-domain assurance only after the primary family is
   sound and exhaustive.

Every SAT or diversity witness contains complete input, output, and local
assignments. Each is replayed immediately against all 12 equations and the
five `Q0` equations. Solver models and feature scores are hypotheses until
that replay succeeds.

## Independent verification

The primary checker may use Z3 and repository adapters. The independent
checker imports no repository module, Z3, or T27--T32 implementation. It uses
only the Python standard library and frozen raw JSON to rebuild the 12
equations and exact domains.

Using generalized arc consistency and deterministic backtracking, it:

- enumerates the complete bounded layer-30 input domain of 77,824 states;
- determines which inputs have at least one exact `not Q0` successor;
- searches for a `Q0` witness inside each proposed type;
- searches for a `not Q0` witness outside the complete family;
- replays the diversity witnesses and canonical first-match ownership; and
- compares canonical family bytes with the exact bad-input table bytes.

Primary and independent results must agree and be byte-stable across two fresh
runs. Mutation tests must reject changes to a feature literal, type order,
witness coordinate, equation residual, source digest, soundness status,
exhaustiveness status, diversity count, or compactness measurement.

## Stop conditions and outputs

T32 stops without fallback if:

- the first type misses its milestone;
- any type is merely a state minterm or renamed `Q0` failure mask;
- more than eight types or six literals per type are required;
- either discovery budget is exhausted;
- an exact query returns SAT where UNSAT is required, or returns `UNKNOWN`;
- the family is not smaller than the exact bad-input table;
- independent replay disagrees; or
- verification would require an unbounded enumeration or a changed topology.

No durable T32 evidence, certificate, independent audit, report, or notebook
entry is written before full primary/independent agreement. An implementation
plan may propose narrowly scoped T32 library, runner, independent-checker, and
test files, but this design authorizes no implementation.

## Ranked approaches

| Rank | Target and claim | First milestone | Independent method | Likely cost | Stop boundary |
| --- | --- | --- | --- | --- | --- |
| 1 | Structural mechanism cover: at most eight sound types exhaust all exact `not Q0` transfers | One six-literal type soundly covers two inputs and two failure masks | Raw-equation backtracking plus complete 77,824-input replay after the milestone | Moderate, bounded | Any milestone, budget, compactness, or agreement failure |
| 2 | Model-based region splitting: disjunctive projected regions characterize the bad input image | One nontrivial projected region that exactly implies a bad successor and is not a domain bound | Compare projected membership with exact successor search on all inputs | High; risks repeating T31 and formula blow-up | Projection timeout, partial quantifiers, domain-only output, or non-compression |
| 3 | Failure-mask quotient: realized subsets of failed `Q0` equations form the types | Fewer canonical masks than the preliminary 27 of 31 | Independently enumerate all realized masks | Low to medium | Stop immediately if the preliminary near-saturation reproduces; masks are not structural explanations |

The selected approach is the only one that directly tests whether local
carry/digit behavior groups semantically different failures without first
requiring another input projection.

## Research and Prism provenance

Prism was checked first with its configured `muse-glimmer:30b-mlx` model.
`frame_status` and a valid four-frame request over the immutable T31 stop
snapshot both failed at the mathematical-frame operation boundary. No frame
application or artifact was returned, and none is reconstructed here.

Primary sources motivate methods only:

- Haase, Krishna, Madnani, Mishra, and Zetzsche prove a singly exponential
  procedure for eliminating one existential Presburger block:
  <https://arxiv.org/abs/2405.01183>.
- Komuravelli, Bjørner, Gurfinkel, and McMillan develop model-based projection
  as finite model-guided under-approximation in SMT verification:
  <https://arxiv.org/abs/1508.01288>.
- D'Antoni, Kincaid, and Wang use symbolic predicates with SAT/SMT-guided
  equivalence checking up to congruence:
  <https://arxiv.org/abs/1610.01722>.
- Becchi, Fedyukovich, Gurfinkel, and Nachmanson give 2026 evidence that
  interrupted model-based projection can expose useful typed partial results,
  but their theory is linear real arithmetic, not this integer problem:
  <https://link.springer.com/chapter/10.1007/978-3-032-22752-2_3>.

None of these sources proves that a compact type family exists or validates a
reverse-and-add claim.

## Preservation boundary

T32 does not begin lower-layer extension, symbolic base lifting, base
comparison, topology scanning, publication work, or Lean formalization. It
must not stage or modify publication paths, unrelated notebooks, `.DS_Store`
files, or the existing Timeloop ledger, pool, and exam changes. The protected
preprint ZIP SHA-256 remains:

```text
e9d1d0d087e37d822cae19b82453dfd6c55031d797b1e5696f4b04a39308ae33
```
