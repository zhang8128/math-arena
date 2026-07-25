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
| **evaluator** | win/loss, free | **Lean 4.32.1 + mathlib**, validated both directions | ✅ built 2026-07-25 |
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

### Evaluator — BUILT

Lean 4.32.1 + mathlib (8,639 cached modules, 7.3 GB) at `.timeloop/lean/arena`.
Operator authorised the install; `elan` manages the toolchain.

**Validated in both directions**, which is the only validation that means
anything:

- *Accepts truth* — `Nat.exists_infinite_primes` (mathlib genuinely loaded, not
  merely imported), plus four arena results proved by `decide`.
- *Rejects falsehood* — a deliberate negative control, `∀ x : ZMod 6, x^2 = x`,
  was **rejected**: Lean reported that `decide` proved the proposition false.
  The arena's own theory says `M_2 = 2`, not 6, so the checker disagreed with a
  plausible-looking statement exactly where it should.

The first machine-checked arena results are T5's congruence mechanism —
`∀ x : ZMod 6, x³ = x`, `∀ x : ZMod 30, x⁵ = x`, `∀ x : ZMod 2, x² = x` — which
were *measured* on 2026-07-25 and are now *proved*. That transition, from
"verified over a range" to "checked", is the whole point.

Rebuild from a clean checkout: `cd .timeloop/lean/arena && lake exe cache get && lake build`.
The 7.3 GB `.lake` directory is gitignored; only sources and the manifest are tracked.

### What the evaluator does NOT yet do

Having a checker is not the same as being able to reach the targets. The
`decide` tactic settles finite statements; the open Erdős problems are not
finite. What the evaluator changes is that **success now has a definition** —
a Lean proof either compiles or it does not, with no human in the verification
path.

Next step on this axis: pull `google-deepmind/formal-conjectures`, which contains
Lean statements for open Erdős problems. That converts the intake list from
"problems to compute about" into "statements with a checkable notion of success",
and the two halves of the arena — intake and evaluator — meet.

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
