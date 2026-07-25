# Time Loop Room — first run

Nine turns, three targets, ~2 hours. Everything below is reproducible from
`runs/` and `lib/`; every claim's search range is recorded in `notebook/`.

## The honest headline

**Nothing here is new mathematics.** Every result is classical — Rabinowitsch,
Heegner/Baker–Stark, perfect digital invariants, Giuga's reduction, the Lehmer
size bound. The arena derived them independently and, in several cases, derived
them *wrong first* and corrected itself.

That is the actual finding worth reporting: **the loop's self-correction rate was
high, and the corrections came from the durable layer, not from memory.** Three of
nine turns overturned an earlier turn's own recommendation. A queue of independent
problem attempts would not have done that.

## What was produced

### Quadratic prime runs (T0–T2) — target closed

- `n²+n+q` has a full prime run exactly for `q ∈ {2,3,5,11,17,41}`, matching the
  Heegner discriminants. Search space permanently retired: **no larger `q` exists.**
- **Broke the naive generalisation.** "Long run ⟹ class number 1" is false:
  `6n²+6n+31` has `h(D)=4` and runs 58. The real mechanism is two routes to
  avoiding small primes — inertness, and *coefficient absorption* (`p | gcd(a,b)`
  forces `f(n) ≡ c mod p` always). Rabinowitsch is the `a=1` corollary.
- **T2 refuted T1's own next-action.** T1 proposed maximising the bound
  constructively; T2 showed it fails — forms with first-bad-prime 89 have runs of
  *eight*, because a second constraint (value growth `~a·n²`) dominates past `a≈7`.
  The Euler polynomial is optimal because it uniquely satisfies both.

### Digit-power maps (T3–T6) — target resolved

- **42 `(b,d)` pairs settled exhaustively** below a provable decidability bound.
  These are theorems, not searches.
- Derived an exact law for `d=2` fixed points: completing the square turns the
  digit condition into `u² + v² = b² + 1`, so fixed points *are* the
  sum-of-two-squares representations of `b²+1`. **Validated `b = 2…120` with exact
  set equality, zero mismatches.**
- **T4 refuted T3's next-action** (no `d=3` analogue — the conic becomes a cubic)
  but proved a constructive family: for `d ≥ 3`, base `b = k^(d−1)` has fixed
  points `k^d` and `k^d+1`.
- **T5 proved the general law.** With `M_d = ∏{p : (p−1)|(d−1)}`, one shows
  `T(n) ≡ n (mod gcd(b−1, M_d))` for *every* `n` — so the fixed-point equation gets
  one congruence free. Verified: mean count is monotone in `g = gcd(b−1,M_d)` for
  every `d`, with `d=5` spanning `g=1…30` and means rising 2.92 → 50.00.
- **T6 showed this is most of the story** — normalising by `g` collapses a 17×
  spread to 1.8×. It also retroactively explains T3: `d=2` has `M_2=2`, too
  degenerate to reveal the general law.

### Lehmer's totient problem (T7) — parked

Elementary bound derived and tabulated, then **honestly assessed as weaker than
the literature** (`k ≥ 3` versus the published `k ≥ 15`). Recorded so no future
turn re-derives it. Exhaustive checks at `k=3` (4.5M candidates) and `k=4` (522k)
found nothing.

### Giuga's conjecture (T8–T9) — usefully reduced

- **Reduction recorded**: a counterexample must be simultaneously Carmichael and
  Giuga. Carmichael numbers are odd; every known Giuga number is even. So the
  conjecture holds unless an **odd Giuga number** exists — a far more concrete
  question.
- Any odd Giuga number has ≥ 9 prime factors and exceeds 3,234,846,615.
- All 55 Carmichael numbers below `2×10⁶` tested: **zero** meet the Giuga
  condition, and 46 of 55 have *no* prime factor meeting it. The two conditions
  are measurably antagonistic, which is weak evidence *for* the conjecture of a
  kind the reduction alone does not supply.

## What the durable layer actually bought

The design bet was that recording *reusable structure* beats recording outcomes.
Concrete returns:

1. **Three self-refutations.** T2 killed T1's proposal, T4 killed T3's, T6 closed
   T5's open question. Each cost minutes because the prior turn had written down a
   *specific testable* next action rather than "investigate further."
2. **Two permanently retired search spaces** — the principal quadratic family, and
   the `n/φ(n)` bound for Lehmer. Both are recorded as closed *with the reason*, so
   the closure survives without the reasoning being redone.
3. **A cross-target pattern only the ledger could see.** T7 and T8 failed the
   *same way* — a reciprocal/size bound that cannot be sharpened. Noting that in
   the ledger is what makes "the next lever must be a congruence obstruction" a
   usable heuristic rather than a per-target observation.
4. **A caught artifact.** T7's first run reported `min k = 77`, which was the
   prime pool running out, not an answer. Recorded as a general rule: *a search
   that terminates by exhausting its input must never report the exhaustion point
   as a result.* Same failure shape as reporting "no counterexample found" as
   "verified."

## Honest limits

- **Zero new theorems.** Everything is rediscovery. The arena is currently a good
  instrument for retiring search space and correcting itself, not for producing
  novel results.
- **No conjecture was broken in the sense you meant.** T1 and T4 broke conjectures
  the arena had itself just formed. That is a real and useful loop, but it is not
  the same as falsifying something the literature believes.
- **Target selection is the bottleneck, not compute.** Every result here took
  seconds to minutes of CPU. What took judgment was choosing *which invariant to
  tabulate* — and that is exactly the part a bigger machine does not help with.
- **The two famous open problems attacked (Lehmer, Giuga) both hit walls the
  literature hit decades ago**, which is the expected outcome and worth saying
  plainly rather than dressing up.

## State

| target | status |
|---|---|
| `rabinowitsch-families` | exhausted |
| `forge-digit-dynamics` | resolved |
| `lehmer-totient` | parked — needs a congruence lever, not a size lever |
| `giuga` | open, reduced to "does an odd Giuga number exist?" |
| `idoneal-numbers`, `brocard`, `singmaster`, `forge-aliquot`, `forge-prime-runs`, `forge-recurrence-primality` | untouched |
