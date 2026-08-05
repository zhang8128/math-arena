# Lychrel Base-17 Affine Lift Design

## Purpose

Determine whether David Seal's verified base-17, period-six, two-interface
reverse-add certificate is the specialization of a certificate valid in every
sufficiently large base. The experiment must either produce an exact family of
new-base certificates or an exact obstruction for the specified lift class.

The user approved autonomous continuation of the T21 next action. Work remains
inline and isolated: model output proposes dispositions, while deterministic
code supplies all evidence.

## Lift Class

Keep the six phase templates, fixed-fragment lengths, repeat-block positions,
and period of the T21 base-17 certificate. A fixed digit occurrence with value
`d` at base 17 may lift in exactly one of two ways:

- lower anchor: `d`;
- upper anchor: `d + (b - 17) = b - (17 - d)`.

The repeated `0` and `16` tokens lift to `0` and `b-1`, respectively. These two
anchors exhaust every integer affine function of `b` that equals `d` at base
17 and remains a digit for every `b >= 17`: its slope must be zero or one.

The result therefore classifies global affine lifts of this exact topology. It
does not classify piecewise lifts, different periods, different fragment
lengths, or certificates existing only at isolated bases.

## Approaches Considered

### 1. Carry-skeleton Boolean CSP plus independent polynomial verifier

Preserve the carries observed in the base-17 certificate. Give every fixed
digit occurrence a Boolean anchor variable. For one addition column, comparison
of the coefficient of `b-17` gives

`anchor(left) + anchor(right) - anchor(output) = carry_out`.

Repeated `0` and `b-1` digits contribute fixed anchor values zero and one. The
constraints have at most three variables and admit a small dependency-free
propagation/backtracking solver. A separate bivariate polynomial compiler then
checks the resulting cycle identically in `b` and `q=b^n`.

This is the selected approach. It keeps discovery and acceptance independent,
and an infeasible system can return a concrete contradictory subset.

If this carry-preserving system is infeasible, run Approach 2 as a required
fallback. That removes the carry-skeleton assumption and decides whether the
word identities themselves can hold with carries that change above base 17.

### 2. Solve global polynomial coefficients directly

Compile unknown anchors into the full `b,q` coefficient identities and solve
the resulting Boolean linear system. This is mathematically direct, but it uses
the same representation for search and proof, obscures local causes of failure,
and makes independent verification harder.

### 3. Infer a smaller connector transducer before lifting

Factor the long fixed fragments into reusable boundary states, then lift the
smaller machine. This may be valuable after the current experiment, but finding
that quotient is a separate research problem and could silently remove
constraints. It is not needed to decide the affine lift class.

## Components

### Affine digit and word representation

Create `.timeloop/lib/lychrel_affine.py`. `AffineDigit` stores an intercept and
a slope in `{0,1}` and evaluates to `intercept + slope*(base-17)`. `AffineWord`
mirrors `ParametricWord`: fixed fragments contain affine digits and repeat
tokens are exactly zero or `b-1`.

The representation validates digit bounds at the reference base and canonical
leading digits at `n=0` and `n=1`.

### Carry constraints

Assign a stable variable identifier to every fixed digit occurrence. Render
symbolic columns for `n=0,1,2,3`; these cases cover absent blocks, block
boundaries, and repeated homogeneous interiors. Reuse the reference base-17
carry bits and emit normalized integer equations over the anchor variables.

The Boolean solver applies domain propagation before branching, chooses the
most constrained remaining variable, and stops after two solutions. If no
solution exists, deletion-minimize the equations to an irreducible infeasible
core and serialize the phase, parameter, and column provenance of every member.

### Independent exact verifier

Represent a polynomial in `b` as an immutable coefficient tuple and a
polynomial in `q` as a tuple of those base polynomials. Compile each affine word
using:

- fixed fragment: `P <- b^len(F) P + value_b(F)`;
- `0^n`: `P <- qP`;
- `(b-1)^n`: `P <- qP + q - 1`.

Reversal is token reversal. Ordinary phase identities compare bivariate
coefficients exactly. The wrap identity substitutes `q -> bq`. This verifier
does not consume the carry equations or their carry assignments.

For the global fallback, linearize every bivariate residual coefficient in the
Boolean anchors: evaluate the all-lower assignment, then flip one anchor at a
time to obtain its exact coefficient. Solve these equations with the same
Boolean engine and deletion-minimize any infeasible core. This classifies the
entire affine lift class without assuming that carries agree with base 17.

### Non-palindrome certificate

For each phase, compare fixed outer digit functions. Record a same-slope,
different-intercept pair when one exists, since that mismatch holds for every
`b >= 17` and every `n`. If no uniform pair exists, compute the finite bases at
which each affine mismatch vanishes and report the exact admissible base set;
never infer non-palindromicity from sampled bases.

### Experiment and evidence

Create `.timeloop/runs/t22_lychrel_affine_lift.py` and persist its deterministic
JSON output as `.timeloop/runs/t22_lychrel_affine_lift.json`. The script loads
the T21 base-17 certificate, builds the carry system, solves it, runs the
independent symbolic verifier, and performs direct integer checks at bases 17,
18, 20, 26, 40, and 100 for `n=0..5` whenever a lift exists.

If infeasible, the evidence contains the minimized contradiction and verifies
that removing any one core equation restores feasibility. If feasible, it
contains every anchor assignment up to the two-solution cap, all exact
coefficient identities, all-base non-palindrome witnesses, and direct replays.

## Prism and Evidence Boundary

Use the Prism modular/local-global and duality artifacts only as hypotheses.
Their proposed modular invariant, carry-period claims, and two-base probes are
not proof. Record a typed Prism outcome only after the deterministic experiment
tests the corresponding narrow prediction. Never attach support to untested
artifact fields.

## Testing

Tests use hand-derived miniature cycles rather than expectations generated by
the production compiler. They cover affine digit evaluation, exact bivariate
arithmetic, wrap substitution, carry-equation extraction, satisfiable and
infeasible Boolean systems, irreducible-core validation, canonical-word
rejection, and the real base-17 fixture.

The final gate compiles both T21 and T22 modules, validates JSON, reruns the
experiment deterministically, runs the complete `.timeloop` test suite, and
checks the Git diff and new files for whitespace errors.

## Success Criteria

The round succeeds with either outcome:

1. a globally valid affine lift, independently verified as an identity in
   `Z[b,q]` and accompanied by all-base non-palindrome witnesses; or
2. an independently checked irreducible infeasible core proving that no lift in
   the stated affine class preserves the base-17 word topology, even if carries
   change with the base.

Any stronger claim requires a mandatory primary-source and exact-phrase novelty
search before it enters the ledger.
