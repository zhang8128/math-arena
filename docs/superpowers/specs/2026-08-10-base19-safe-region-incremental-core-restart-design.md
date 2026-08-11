# Base-19 Safe-Region Incremental-Core Restart Design

**Date:** 2026-08-10

**Scope:** T33 Task 4 only

**Status:** Approved design amendment; implementation remains review-gated

## Decision

Replace Task 4's monolithic complete-pool named-core query with a bounded,
countermodel-guided search over conjunctions of at most six atoms. Every atom
still comes from the frozen canonical seed-pair pool, every solver answer is
replayed exactly, and the existing primary and isolated acceptance gates remain
mandatory.

The terminated repository run is operationally inconclusive. Its exit status
143 records a graceful `SIGTERM`; it is neither a mathematical `PASS` nor a
T33 `STOP`, and it produces no artifact or notebook conclusion.

This amendment supersedes only Task 4's complete-pool extraction algorithm and
the associated `seed_pair_count` definition in the existing T33 plan. It does
not authorize Tasks 5--8 or any other research direction.

## Evidence for the restart

The original run spent more than six hours in its first seed-pair query without
returning `SAT`, `UNSAT`, or `UNKNOWN`. Process sampling placed every observed
sample below `Z3_solver_check_assumptions`, in the integer-arithmetic
Diophantine solver's recursive fresh-variable dependency processing. The query
asserted the complete pool, including the modulus-2-through-19 congruence
family, under tracked names.

This is evidence of a pathological encoding boundary, not evidence about the
existence of a compact safe region. Continuing that run would not strengthen
the mathematical claim.

## Considered approaches

1. **Countermodel-guided depth-six search — selected.** Query only canonical
   conjunctions of zero through six atoms. A replayed SAT model determines the
   only atoms on which a successful descendant can branch. This is sound,
   bounded, and avoids ever constructing the complete conjunction.
2. **Atom-family batching.** Add equalities, inequalities, and congruence
   families in fixed batches. This is simpler, but a large batch can recreate
   the same solver pathology and the batch boundary has no mathematical
   significance.
3. **Direct enumeration of all one-through-six-atom subsets.** This is simple
   and complete before the query budget, but the combinatorial frontier is too
   large to be a coherent bounded experiment.

## Search algorithm

Process the 153 seed pairs in lexicographic index order. For each pair:

1. Regenerate and hash its frozen canonical atom pool.
2. Start from the empty conjunction and perform deterministic depth-first
   search over canonical conjunctions containing at most six distinct atoms.
3. Submit each previously unseen conjunction `C` to the exact query
   `B30(u) and C(u)`.
4. On `SAT`, minimize and exactly replay the countermodel. Evaluate every pool
   atom on that concrete assignment and form the set `V` of violated atoms.
5. If `V` is empty, the countermodel satisfies the complete pool. It is a
   constructive certificate that no subset of this pair's pool is safe; end
   the pair without submitting a complete-pool query.
6. Otherwise branch only to `C union {a}` for `a` in `V`. Any safe extension
   of `C` must contain at least one member of `V`, so this branching rule loses
   no candidate within the six-atom grammar.
7. Order branches deterministically by: decreasing number of already replayed
   SAT models excluded, decreasing promoted-row coverage, decreasing bounded
   singleton extent, then canonical atom bytes.
8. On `UNSAT`, deletion-minimize the conjunction in canonical atom order and
   submit the reduced conjunction to the existing milestone acceptance gate.
   An accepted clause ends the search with `PASS`. A rejected clause is not
   expanded because supersets cannot improve safety, extent, or compactness.

Canonical conjunction bytes are globally memoized. Reaching the same node by
different countermodels never repeats a solver query or consumes the budget
twice.

## Exact counters and terminal statuses

- `seed_pair_count` increments when a canonical pair enters the search and
  consumes the empty-root result, whether that result is fresh or globally
  cached. Pair 154 is never entered.
- `region_test_count` increments once for each distinct canonical conjunction
  first submitted to an exact safety query, including empty roots, branch
  nodes, and deletion trials. A mandatory fresh acceptance replay of an
  already-counted conjunction does not increment the distinct-conjunction
  counter. Conjunction 2,001 is never submitted.
- Every submitted conjunction contains at most six atoms. The implementation
  must make a larger query structurally impossible.
- `SAT` and `UNSAT` are the only mathematical solver results. `UNKNOWN` ends
  Task 4 immediately with the existing `UNKNOWN` status and no candidate.
- Exhausting 2,000 distinct region queries returns
  `REGION_BUDGET_EXHAUSTED`. Exhausting the allowed pair prefix returns
  `PAIR_BUDGET_EXHAUSTED`. Exhaustively closing all 153 bounded search trees
  returns `NO_SAFE_REGION`.
- `INDEPENDENT_DISAGREEMENT` remains an immediate hard stop.

No timeout, interruption, or resource exhaustion is reinterpreted as `SAT`,
`UNSAT`, or `NO_SAFE_REGION`.

## Provenance

Replace named-core acquisition provenance with an incremental search transcript
containing, for every queried node:

- canonical conjunction digest and ordered atom digests, resolved against the
  independently regenerated seed-pair pool;
- exact status;
- for `SAT`, the minimized countermodel, exact equation residuals, `q0` result,
  and canonical digests of all violated pool atoms;
- deterministic branch order and parent digest; and
- for `UNSAT`, the deletion-minimization trace and reduced clause digest.

The transcript is returned in the milestone's temporary JSON result. Task 4
still writes no durable evidence artifact. The existing source hashes, seed
pool digest, Z3 version, `random_seed=0`, and `phase_selection=0` remain bound.

## Acceptance and independent verification

The acceptance boundary is unchanged:

```text
atom_count <= 6
both seed rows satisfy clause
promoted_coverage_count >= 2
bounded_extent >= 4
single_clause_predicate_bytes < explicit_table_bytes(covered promoted rows)
fresh primary C(u) and B30(u) == UNSAT
isolated milestone status == PASS
```

The isolated standard-library checker independently regenerates the seed pool,
replays every transcript SAT assignment against the 12 equations and `q0`,
recomputes each violated-atom set and branch order, replays deletion steps, and
enumerates all 77,824 layer-30 inputs to confirm the final clause is disjoint
from `B30`. It imports no repository module.

## First falsifiable milestone

Run the revised repository `milestone` command exactly once. It must terminate
with one of the existing exact Task 4 statuses and counters within 153 pairs and
2,000 distinct conjunctions. `PASS` requires the unchanged primary and isolated
gates. Any other status ends T33 without Tasks 5--8.

Before that repository run, synthetic tests must prove the branching lemma:
for a replayed SAT model of `B30 and C`, every UNSAT extension of `C` drawn from
the pool contains an atom the model violates. Tests must also prove canonical
deduplication, the six-atom structural ceiling, exact counter boundaries, and
rejection of corrupted transcripts.

## Stop conditions and exclusions

Stop without fallback if the revised method returns a non-`PASS` status,
requires a conjunction larger than six atoms, fails exact countermodel replay,
exceeds either frozen counter, changes the atom pool or layer topology, or
cannot be reproduced by the isolated checker.

This restart does not authorize lower-layer extension, symbolic base lifting,
base comparison, topology scans, publication changes, unrelated notebooks, or
Lean work. Existing publication, ledger, pool, exam, notebook, and `.DS_Store`
changes remain outside the staging boundary.
