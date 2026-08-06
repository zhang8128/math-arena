# T23 Fixed-Base Lychrel Transplants — Design

## Goal

Classify bases `18..100` for one sharply defined construction class: retain the
exact six-phase, two-interface topology reconstructed in T21 from Seal's
base-17 certificate.  At a fixed base `B`, replace every fixed occurrence of a
base-17 digit `d` independently by either

```text
d                       (lower anchor)
d + (B - 17)            (upper anchor)
```

and replace repeat tokens `0` and `16` by `0` and `B-1`.  Carries may change
independently with `B`.  A positive requires all six reverse-add identities for
every parameter `n >= 0` and an explicit non-palindrome witness in every phase.

This does not search the different published base-20 or base-26 topologies.

## Exact reduction

Let `delta = B-17`.  Every fixed digit is `d + delta*x` for a Boolean anchor
`x`.  For a rendered transition and a least-significant-first column, exact
addition gives

```text
left + right + carry_in = output + B*carry_out.
```

Both anchor and carry variables are Boolean.  One column therefore becomes a
sparse integer equation in at most three digit anchors and two carries.  No
reference carry is preserved: every `(phase, n, column)` receives fresh carry
variables.

Each word has two repeat interfaces, so its value is a polynomial of degree at
most two in `q=B^n`.  A residual polynomial that vanishes at `n=0,1,2`, hence at
the three distinct values `q=1,B,B^2`, is identically zero.  Thus the carry
systems for exactly `n=0,1,2` decide the infinite family; this is interpolation,
not a bounded heuristic.  Every surviving Boolean solution is still compiled
through the existing independent `Z[q]` verifier before acceptance.

For a negative base, infeasibility at `n=0` alone is already decisive because
an infinite certificate must include that member.

## Method comparison

### Selected: local carry CSP plus polynomial acceptance

Sparse column equations make propagation cheap and keep carries explicit.  The
three-parameter interpolation argument makes the method complete.  Exact
`Z[q]` verification remains a separate acceptance boundary and catches an
incorrect equation compiler.

### Rejected as primary: direct global coefficient CSP

Compiling coefficient identities directly is exact, but a fixed-base
coefficient collapses many positional powers into one high-arity Boolean
equation.  The current exact Boolean solver enumerates local supports and is
well suited to sparse carry equations, not hundreds of anchors in one row.

### Rejected: unconstrained digit/topology search

Allowing arbitrary digits or altering interfaces could find other
certificates, but it changes the question and destroys the direct relationship
to T22's failed global affine lift.  It belongs to a later round.

## Compact obstruction strategy

The full solver classifies every base, but a durable negative result should not
rest on 83 opaque solver exits.  Minimize the propagation trace for a
representative base, reuse its column coordinates across the range, and
identify exceptional bases where that core becomes feasible.  Produce separate
small cores for those exceptions.  A standalone audit must reconstruct the
core equations directly from the saved T21 fragments and exhaust every Boolean
assignment without importing the production fixed-base module or Boolean
solver.

Exploration predicts one three-equation core covers every target base except
33 and 34, each of which has a separate three-equation core.  The uniform core
need not be deletion-minimal in every covered base; its purpose is a stable,
tiny certificate family, with minimality recorded rather than assumed.  This
prediction is not a result until the production scan and independent audit
reproduce it.

## Prism disposition and safeguards

Prism problem `lychrel-bases:base17-fixed-base-transplants`, version 1, used
seed `20260806`, prompt version 2, model `qwen3.6:27b-mlx`, and the 32K
disposition budget.  Symmetry/group-action and extremal-principle frames were
applied.

The useful disposition is to quotient redundant explanations and seek a small
boundary obstruction.  The proposed reversal-carry signature, group action,
asymptotic elevation parity, zero-carry limit, and predictions of positive
bases are unverified.  In particular, phase rotation is not automatically a
symmetry of an occurrence-labelled fixed topology, and large-base carries do
not simply vanish.  None of these claims enters acceptance.

## Evidence and output

The run JSON records:

- immutable reference topology and scan scope;
- per-base exact status for 17 through 100;
- equation and variable counts;
- exact polynomial-verifier result for every positive control or hit;
- phase-wise non-palindrome witnesses for every accepted cycle;
- the three compact core families and their coverage;
- independent exhaustive core-audit counts;
- Prism provenance and explicit unverified/falsified suggestions;
- literature scope distinguishing known constructions from this transplant.

If no base survives, the claim is only: no lower/upper occurrence mask
transplants this exact T21 topology to a base in `18..100`.  It says nothing
about arbitrary digits, other periods, other repeat layouts, or Lychrel
existence in those bases.
