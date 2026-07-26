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

1. ~~**Volume**~~ — done (`bin/intake`, 608 open problems).
2. ~~**Evaluator**~~ — done (Lean 4.32.1 + mathlib, validated both directions).
3. **Join the two halves** — pull `formal-conjectures` so intake yields *Lean
   statements*, not just problem numbers. This is now the highest-leverage move:
   both halves exist and nothing connects them.
4. **Queryable tablebase** — cheap, and stops the arena re-walking closed ground.
5. **Technique retrieval** — the pool's `forges` field is a flat list. It should
   be matchable: given a new target, surface the techniques that have worked on
   its shape. The degenerate first version of the transfer graph.
6. **Instrumentation** — no way currently to tell whether turn 50 is better than
   turn 5. Without it, "improving" is an assertion.

## The moonshot, stated honestly

The target is a version of this that advances mathematical capability far enough
that everything prior reads as "classical" — the chess transition, applied to
mathematics.

The distance from here is enormous and *specific*, and as of 2026-07-25 it is one
item shorter. It is not compute; every result in this arena took seconds. It is
not target supply; that is 608 deep. It is no longer the evaluator either — a
claim can now be machine-checked, with no human in the verification path.

What remains is the part neither volume nor verification supplies: **the ability
to actually prove a hard theorem.** The arena can now state a target formally and
check an attempt. It cannot yet produce attempts that succeed on anything an
Erdős problem would recognise as difficult. `decide` settles finite statements;
the open problems are infinite.

So the honest frontier is now: *given a formal statement and a checker, can this
thing generate proofs?* That is a much better question than the one we had this
morning, because it is answerable by trying — and every failed attempt costs
nothing but compute and returns an unambiguous verdict.

That is the same loop chess had. It is not a guarantee of the moonshot. It is the
first arrangement in which the moonshot is even measurable.

---

## Baseline measurement, 2026-07-25 — the generator is the bottleneck

With intake and evaluator both built, the two halves were joined:
`google-deepmind/formal-conjectures` (510 Erdős problems, 850 conjecture files,
8.5 MB) sits at `.timeloop/lean/formal-conjectures`. Every unproved statement is
marked by `sorry` and tagged by category, which makes the open frontier
machine-readable:

| category | total | **unproved** | meaning |
|---|---|---|---|
| `research open` | 1,173 | **1,173** | genuinely open — a proof is new mathematics |
| `research solved` | 1,140 | **1,076** | known true, not yet formalised |
| `textbook` | 154 | **77** | exercises |
| `test` | 697 | **51** | small checkable facts |
| `API` | 179 | **16** | infrastructure |
| | | **2,393** | |

`bin/attempt` fires candidate tactics at a `sorry`, compiles that one file, and
records the verdict. The working tree is restored after every attempt.

### The result

**1 proved out of 16 attempted (6%)**, over the *smallest* statements in the most
tractable tier, with six tactics each (`rfl`, `decide`, `norm_num`, `simp`,
`omega`, `native_decide`). 529 seconds, ~33 s per candidate.

The single success — `a 1 = 1` in OEIS A317940, by `rfl` — is a base case that
unfolds definitionally. It is a genuine closed `sorry` and it is not mathematics.

### What that measures

The failures are not noise. `BB_1` is Busy Beaver, `τ_two` is Ramanujan tau,
`P_subset_NP` is exactly what it looks like. These are *short to state and hard to
prove* — which is the normal condition of mathematics and precisely why a
statement's length is a bad tractability proxy.

So: **breadth alone does not work.** Firing generic tactics at formal statements
has a ~6 % hit rate on the easiest tier and would be lower elsewhere. The
bottleneck is now located, and it is neither of the two things built today:

- volume — 608 open problems, ✅
- evaluator — Lean + mathlib, validated both directions, ✅
- compute — every arena result took seconds, never binding
- **generation** — ❌ *this is the wall*

### The economics, which are genuinely favourable

At ~33 s per candidate, a naive sweep of all 128 test/textbook statements is
**~70 minutes**. A sweep of every one of the 2,393 unproved statements in the
repository is **~22 hours** — one overnight run, on one laptop.

That is the useful thing about a cheap unambiguous evaluator: exhaustively
establishing what naive methods *cannot* do costs one night. Every attempt that
fails costs nothing and returns a verdict, and the failures map the wall exactly.

**Next measurement, not next assertion:** does a non-naive generator beat 6 %?
That question is now answerable by running it, which is the entire point of
having built the apparatus.

---

## The control group, 2026-07-26 — and the number that actually matters

The filtered sweep ran to its 9-hour cap: **402 of 875 attempted, 1 proved (0.2%)**.
Resumable; `sweep2.jsonl` is the permanent baseline.

| tier | attempted | proved |
|---|---|---|
| `research solved` | 301 | **0** |
| `textbook` | 59 | **0** |
| `test` | 42 | 1 |

The single proof — `a 1 = 1` by `rfl` — was **audited**, not assumed:
`#print axioms` gives `[propext, Classical.choice, Quot.sound]`, no `sorryAx`.
It is a definitional unfolding.

The 6% figure reported earlier is **retracted**: it came from the broken harness
over a 16-statement sample. The corrected number, over 402 statements already
filtered to remove the provably hopeless, is 0.2%.

### The comparison that reframes the project

| approach | attempts | machine-checked theorems | wall-clock |
|---|---|---|---|
| blind tactic sweep | 402 | 1 (trivial) | 9 hours |
| **guided pipeline** (T14, T16) | **2** | **2** | **40 min** |

Same evaluator, same library, same machine. The difference is entirely whether
the mathematics came first.

In both guided successes, **zero** failed compile cycles were mathematical — they
were mathlib navigation and statement shape. The checker was not the obstacle;
it was the guide.

**So "can this system prove theorems?" was the wrong question.** It can, reliably,
given something to prove. The bottleneck is upstream: generating results worth
formalising. The arena already does that (T0–T12 found real structure
repeatedly); the two halves simply were not connected until T16.

### Consequence for what to build next
Do **not** invest further in tactic search — 402 attempts say what it is worth.
Invest in the *predict → confirm → prove* loop, and point it at the forge track,
where the parameter spaces are genuinely unexplored.
