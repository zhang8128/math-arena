# T25 Single-Interface Lychrel Perturbations — Design

## Goal and claim boundary

Start from the exact six-phase T21 base-17 topology used by T24.  In exactly
one phase, move exactly one of its two repeat interfaces by one or two fixed
columns.  Preserve the ordered fixed occurrences, the ordered repeat symbols,
the six-phase successor relation, arbitrary target-base digits, canonical
leading digits, and fresh Boolean carries.  Classify bases `18..40`.

A positive must pass exact encodings at `n = 0, 1, 2`, decode to legal digits,
verify all six identities in `Z[q]`, and expose a fixed non-palindrome witness
in every phase.  A negative at `n = 0` is decisive only for the stated moved
topology.  This experiment says nothing about two simultaneous moves, larger
moves, different fragment order, another number of phases, or general Lychrel
behavior.

## Perturbation semantics

For adjacent fragments `F_i, F_(i+1)` separated by repeat `R_i`, a signed
shift `s` moves the boundary while preserving the concatenated fixed word:

- `s > 0`: append the first `s` digits of `F_(i+1)` to `F_i`;
- `s < 0`: move the last `-s` digits of `F_i` to the front of `F_(i+1)`.

The allowed shifts are `{-2,-1,1,2}`.  Every resulting fixed fragment must be
nonempty.  T21 has three sufficiently long fragments in every phase, so there
are `6 * 2 * 4 = 48` syntactically admissible single moves.  Phase zero has
fragment lengths `(28,23,31)`, producing eight phase-zero variants.

## Exact structural reduction at `n = 0`

At repeat count zero, every repeat block vanishes from each source word.  It
also vanishes from the output of phases zero through four because those
transitions target the next phase at parameter zero.  The sole repeated
output at this filter is the wrap transition from phase five at `n = 0` to
phase zero at `n = 1`.

Moving an interface in phases one through five therefore changes neither the
flattened source digits nor any repeated output in the complete `n = 0`
system.  Up to the deterministic renaming induced by fragment coordinates,
its exact columns and CNF are the already-proved T24 system.  All 40 such
moves inherit T24's bases `18..40` obstruction without another solver call.
Only a phase-zero move changes where the two repeat digits occur in the wrap
output.  The genuinely new search is consequently eight variants times 23
bases, or 184 formulas per encoding.

The implementation records this reduction explicitly and tests it by
canonical column/CNF equality.  It does not silently discard the other 40
moves.

## Selected method: bounded dual-SAT classification

The primary path reuses T24's deterministic one-hot digit compiler and
PicoSAT solver.  For each phase-zero `(interface, shift)` and base, solve the
exact `n = 0` formula.  Escalate a survivor to the combined `n = 0,1,2`
formula, decode it, and invoke the existing polynomial and non-palindrome
verifiers.

The independent audit reads the saved T21 JSON, applies its own boundary-move
routine, and uses T24's standalone binary full-adder encoding with CaDiCaL.
It imports neither the primary perturbation helper nor the one-hot compiler.
Every one of the 184 primary statuses must agree with its independently
encoded counterpart.  Counts and DIMACS digests are retained, and the two
encodings must remain physically distinct.

This route is preferred over incremental SAT.  The common five transitions
could be shared, but 184 bounded instances do not justify adding an
incremental-solver lifecycle or weakening deterministic per-instance
evidence.  A custom carry transducer could yield a shorter proof, but it would
be a new implementation with more validation risk.  It becomes the next step
if the scan reveals a reusable obstruction or a small set of survivors.

## Prism disposition

Prism was applied with `qwen3.6:27b-mlx`, long thinking, and the
information-encoding, modular-local-global, and invariants-monovariants
dispositions.  All three applications failed Prism's artifact schema and are
recorded as invalid, not as mathematical output.  The useful change of
disposition was nevertheless to ask for a boundary-local carry/residue
certificate and for redundant SAT state.  No generated invariant or theorem
is available to accept.  Exact structural reduction and dual encodings remain
the evidence boundary.

## Evidence and stop conditions

The deterministic T25 JSON records all 48 moves, identifies the 40 inherited
negatives with their exact reduction, classifies all 184 new `(variant, base)`
instances, and embeds the independent audit and Prism application IDs.  Any
solver disagreement fails closed.  Any SAT candidate that fails interpolation
or exact verification is reported with that narrower status and is not called
an infinite family.  If all variants are UNSAT at `n = 0`, the result is a
complete negative classification only for single moves of at most two
columns in bases `18..40`.
