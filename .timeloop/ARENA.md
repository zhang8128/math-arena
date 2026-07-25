# Building the arena

The conjectures are fuel. The arena is the work.

## What actually made chess engines superhuman

Not search depth. Three things, and it is worth being precise because the mapping
tells you exactly what is missing here:

1. **Volume** — millions of positions, not a curated list.
2. **A free, perfect evaluator** — win/loss is unambiguous and costs nothing to
   compute. This is the one people forget, and it is the one that matters most.
3. **Permanently retired regions** — endgame tablebases. Solved territory that
   nobody ever searches again.

## Where this arena stands

| | chess | arena | state |
|---|---|---|---|
| **volume** | millions of positions | **608 open Erdős problems**, scored and filterable | ✅ built (`bin/intake`) |
| **evaluator** | win/loss, free | "verified computationally over range X" | ❌ **the ceiling** |
| **tablebase** | endgame DBs | `exhausted`/`resolved` notebook entries | ⚠️ real but not queryable |

### Volume — solved

`bin/intake` draws from the Erdős Problems database
(`github.com/teorth/erdosproblems`, 1,217 problems). Scoring favours the
intersection that is actually workable:

- **open** — unsolved, so the work is not a rediscovery
- **OEIS-linked** — computational purchase exists
- **Lean-formalized** — a machine-checkable statement exists to aim at
- **tag affinity** — matches technique the arena has already forged

**307 problems satisfy all of open + OEIS + formalized.** That is the fuel supply,
against 16 hand-typed targets before.

### Evaluator — the ceiling, and it is not built

Every claim this arena has produced is *computationally supported over a stated
range*. That is precisely the classical mode: mathematics done with a computer,
where a human still supplies the proof and the judgement.

Chess had truth for free. Here, truth costs a proof — **unless a proof assistant
supplies it.** Local check on 2026-07-25: no `lean`, no `lake`, no `z3`, no
`cvc5`, no `vampire`. Only sympy. So the arena currently *cannot* produce a
machine-checked result, only evidence.

This is the difference between "classical mathematics, faster" and anything past
it. Everything else in this document is secondary.

**The decision that unblocks it** (operator's call, not mine to make unilaterally):
install Lean + mathlib, and pull `google-deepmind/formal-conjectures`, which
already contains formal statements for open Erdős problems. That converts the
target list from "problems to compute about" into "statements to attack with a
checkable notion of success." A cheaper partial step is `z3`/`cvc5` via pip,
which buys machine-checked results for the decidable fragments — and this arena
has shown a strong preference for decidable families already.

### Tablebase — real, needs to be queryable

The `exhausted` and `resolved` entries are genuine retired territory: the
principal quadratic family is closed by Heegner finiteness, the `d=2` digit-map
law is settled, `L=3` Kaprekar has a closed form. Nothing should ever re-search
those.

But it is prose in markdown files. A turn only benefits if it happens to open the
right notebook. **Next build:** make the closed set queryable — given a candidate
target, answer "has this been retired, and why."

## Priority order

1. ~~**Volume**~~ — done.
2. **Evaluator** — needs the operator's decision on installing a proof assistant.
   This sets the ceiling on everything.
3. **Queryable tablebase** — cheap, and stops the arena re-walking closed ground.
4. **Technique retrieval** — the pool's `forges` field is a flat list. It should
   be matchable: given a new target, surface the techniques that have worked on
   its shape. This is the degenerate first version of the transfer graph.
5. **Instrumentation** — no way currently to tell whether turn 50 is better than
   turn 5. Without it, "improving" is an assertion.

## The moonshot, stated honestly

The target is a version of this that advances mathematical capability far enough
that everything prior reads as "classical" — the chess transition, applied to
mathematics.

The distance from here is enormous and *specific*. It is not compute; every result
in this arena took seconds. It is not target supply; that is now 608 deep. It is
the evaluator. Until a claim can be machine-checked, this arena produces evidence
and a human supplies the judgement — which is the classical arrangement it would
need to surpass.

That makes the next move unambiguous rather than aspirational.
