# Overnight Conjecture Experiment Design

**Date:** 2026-08-03  
**Deadline:** 2026-08-04 08:00 America/Los_Angeles  
**Repository:** `/Users/kairos/Projects/personal/math`

## Objective

Run the existing `.timeloop` arena on two complementary conjecture tracks. The
first track optimizes for a genuinely novel, exactly checked theorem. The second
optimizes for honest structural progress on a famous open problem. A complete
solution and machine check are ideal, but the experiment must preserve exact
negative results and must not inflate bounded evidence into a proof or a novelty
claim.

## Success Criteria

The run is successful if it produces at least one of the following, in descending
order of value:

1. A theorem with an independently checked mathematical derivation, a compiling
   Lean proof, and a clean axiom audit.
2. A plausible novel structural lead that survives two independent falsification
   paths and an explicit literature/OEIS novelty search.
3. A precise structural reduction or residue-class identity for a famous open
   conjecture, with exact assumptions and machine-checkable verification.
4. A durable negative result that closes a tempting approach and prevents later
   turns from repeating it.

No minimum theorem count is imposed. A correctly recorded failure is preferable
to an unsupported claim.

## Track A: Digit-Product and Mixed Digit Maps

Allocate approximately 60 percent of the useful experiment time to the untouched
`forge-digit-products` target.

The starting point is the arena's proved congruence law for digit-power sums:
digit-value congruences can descend through the base representation to a modulus
derived from `base - 1` or `base + 1`. The experiment will test whether an exact
analogue or a sharply delimited failure mode exists for digit products, weighted
digit products, or another minimal adjacent map.

The lane proceeds in this order:

1. Define one small parameterized map family with an exact finite state bound.
2. Derive candidate invariants before running a broad search.
3. Run a bounded falsification search and preserve counterexamples.
4. Reimplement the decisive test through an independent code path that does not
   import the search implementation.
5. Reduce any surviving pattern to an explicit mathematical statement.
6. Attempt a Lean proof only after the statement survives the independent check.
7. Audit the proof's axioms and reject any result depending on `sorryAx`.

The lane stops expanding a family when it lacks a provable finite bound, when the
strongest pattern repeatedly breaks without leaving reusable structure, or when
the remaining work cannot be verified before the deadline.

## Track B: Erdős–Straus

Allocate approximately 40 percent of the useful experiment time to
`erdos-straus`.

The goal is not to extend an already enormous numerical verification range. It is
to find an explicit identity, transformation, or parameterized residue class for

\[
\frac{4}{n}=\frac{1}{x}+\frac{1}{y}+\frac{1}{z},
\]

with positive integer denominators and precisely stated assumptions. Work should
focus on the difficult prime regime `n = 1 mod 24` and compare any tame-solution
or congruence-class result against the current literature, including Xiaoping
Xu's 2026 tame-solution paper (arXiv:2605.23601).

The lane proceeds in this order:

1. Reproduce known easy residue identities as positive controls.
2. Enumerate the currently resistant residue structure under a documented
   modulus rather than searching raw integers blindly.
3. Generate candidate rational identities or recursive reductions.
4. Check identities symbolically and test positivity/integrality conditions.
5. Verify the covered class using a separate enumerator.
6. Search primary literature for the exact identity, parameterization, and
   residue class before assigning novelty status.
7. Formalize any exact identity in Lean if time remains; otherwise preserve a
   statement shaped for the next formalization turn.

The lane must not report finite numerical coverage as progress unless it reveals
a reusable structural distinction. It must not call an identity novel when only
the precise literature query is absent.

## Math Prism Boundary

Math Prism was invoked before target selection on both Lychrel-base dynamics and
Erdős–Straus. Six broad-frame and two narrow-frame applications returned zero
contract-valid artifacts. Those applications are evidence about the framing
pipeline, not mathematical leads. No invalid output may enter the experiment as
an untracked hypothesis.

If Math Prism becomes available later in the run, a new artifact may be used only
when it passes Prism's own schema validation. The artifact must then be reduced
to a minimal falsifiable test and independently verified in `.timeloop` before
affecting conclusions or frame evolution.

## Verification and Novelty Protocol

Every positive mathematical claim must carry:

- the exact statement and assumptions;
- the code, symbolic derivation, or Lean file that checks it;
- an independent verification path;
- the precise search range when computation is involved;
- a novelty status of `published`, `not found`, or `superseded`, with exact
  queries and sources;
- a cost record and one concrete next action.

A counterexample must be reproduced independently before it is recorded. A Lean
proof must compile in `.timeloop/lean/arena`, and `#print axioms` must show no
`sorryAx`. Literature searches should prefer primary papers and OEIS entries,
with current sources checked because the research landscape is time-sensitive.

## Checkpoints and Resource Control

The run ends no later than 2026-08-04 08:00 America/Los_Angeles. Work is divided
into bounded foreground probes and resumable checkpoints. No single computation
may consume the remaining window without first producing a readable artifact.
Jobs that exceed their checkpoint without useful output are stopped and recorded
as negative technique evidence.

The existing `.timeloop/bin/reap` safeguards remain active. The pre-existing
working-tree modification at `.timeloop/exam/results.jsonl` belongs to the user
and must be preserved untouched.

## Durable Outputs

The experiment may add or update only artifacts needed to reproduce its work:

- `.timeloop/notebook/forge-digit-products.md`;
- `.timeloop/notebook/erdos-straus.md`;
- bounded probes under `.timeloop/runs/`;
- reusable, independently tested code under `.timeloop/lib/`;
- Lean statements and proofs under `.timeloop/lean/arena/`;
- append-only entries in `.timeloop/ledger.md`;
- status corrections in `.timeloop/pool.jsonl` only when supported by the
  recorded outcome.

No result will be published, submitted, or represented as a public mathematical
claim without a separate human gate.
