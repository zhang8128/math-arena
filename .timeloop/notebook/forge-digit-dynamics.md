# forge-digit-dynamics

Digit-power maps `T_{b,d}(n) = Σ (base-b digits)^d`. Chosen because they are
**fully decidable**: above a computable bound `T(n) < n`, so exhaustive search
below it settles the structure completely. Results here are proofs, not searches.

## STATUS
`resolved` for `d=2` fixed points — exact law derived and validated.
`open` for `d ≥ 3` cycle structure.

---

## T3 — settled cycle structure, then an exact law for d=2

### SEARCHED
- **Complete cycle structure** for all `(b,d)` with `b ∈ [2,12]`, `d ∈ [2,5]`,
  bound ≤ 900k. 42 pairs, exhaustive below the decidability bound. These are
  complete answers: no cycle of `T_{b,d}` exists outside what was enumerated.
- **Complete fixed-point sets** for `d=2`, `b ∈ [2,120]`.

### THE LAW (derived, then validated)

For a two-digit fixed point `n = ab + c` with digits `a ∈ [1,b−1]`, `c ∈ [0,b−1]`:

```
ab + c = a² + c²   ⟺   a(b−a) = c(c−1)
```

Substituting `u = 2a − b` and `v = 2c − 1` completes both squares:

```
u² + v² = b² + 1
```

**So the fixed points of `T_{b,2}` are exactly the representations of `b²+1` as a
sum of two squares**, subject to `v` odd, `u ≡ b (mod 2)`, and the digit-range
constraints `1 ≤ (u+b)/2 ≤ b−1`, `0 ≤ (v+1)/2 ≤ b−1`.

**Validation: `b = 2…120`, predicted set equals actual set exactly, zero
mismatches.** Not "no counterexample found" — the actual sets were computed
exhaustively and compared elementwise.

### STRUCTURE

The count is therefore governed by the **factorisation of `b²+1`**, since the
number of representations as a sum of two squares is determined by the primes
`≡ 1 (mod 4)` dividing it (with multiplicity). This explains every outlier in the
raw data:

| b | b²+1 | # fixed pts |
|---|---|---|
| 47 | 2·5·13·17 | 15 |
| 57 | 2·5³·13 | 15 |
| 43 | 2·5²·37 | 11 |
| 117 | 2·5·37² | 11 |
| 97 | 2·5·941 | 7 |
| 110 | 12101 (prime) | 1 |

Bases with `b²+1` rich in primes `≡ 1 mod 4` have many fixed points; bases where
`b²+1` is prime or has few such factors have essentially none. The counts are
always odd because representations pair up under sign, with the trivial fixed
point `1` unpaired.

`b = 110` is the instructive case: `b²+1 = 12101` is prime and `≡ 1 mod 4`, so a
representation exists — but it falls outside the digit-range constraint, leaving
only the trivial fixed point. **The arithmetic supplies candidates; the digit
ranges filter them.** A prediction from factorisation alone would be wrong.

### TECHNIQUE
- Choosing a *decidable* family was the highest-leverage decision. Everything
  else in this arena produces "no counterexample below X"; this produces theorems.
  When picking targets, prefer families with a provable search bound.
- The pattern was invisible in the cycle-count table and obvious once restricted
  to `d=2` fixed points and the defining equation was written out. **Reducing to
  the smallest sub-case with algebraic structure beat looking harder at the data.**
- Completing the square (`u = 2a−b`, `v = 2c−1`) is what converted a digit
  problem into a classical one. Worth trying reflexively on any digit-positional
  Diophantine condition.

### HONESTY
Perfect digital invariants are a studied topic and this law is very likely known.
The arena derived and verified it independently. What is durable is the verified
range (`b ≤ 120`, exact set equality) and the reduction itself.

### NEXT
Two concrete directions:
1. **`d=3` fixed points.** The analogous equation is `a(b²−a²) = c(c²−1)` for
   two-digit `n = ab+c`, i.e. `a(b−a)(b+a) = c(c−1)(c+1)`. This is a genuine
   cubic Diophantine condition, not a sum of two squares — does it reduce to
   anything classical, or is the cubic case structurally harder? Testable: compute
   `d=3` fixed points for `b ≤ 120` and check whether counts track a factorisation
   invariant of `b³±1` the way `d=2` tracks `b²+1`.
2. The cycle-length data for `d ≥ 3` shows large outliers — `(b,d) = (11,5)` has
   **49** cycles versus 16 for `(10,5)` and 13 for `(9,5)`. Nothing yet explains
   the outliers. Suspicion worth testing: `gcd(d, b−1)`, since `x^d ≡ x (mod b−1)`
   when `d ≡ 1 (mod λ(b−1))` forces cycles to preserve residues mod `b−1`.

### COST
~3 minutes total. The settled 42-pair table took 1 second; the law took one
substitution.

---

## T4 — the d=3 analogue fails, but a constructive family is proved

### SEARCHED
Complete fixed-point sets for `d=3`, `b ∈ [2,45]`, via digit-multiset enumeration
(verified against exhaustive iteration for `d=2`, `b ≤ 12`).

### RULED OUT
**T3's first next-action does not pan out.** The `d=3` two-digit condition is
`a(b−a²) = c(c²−1)`, and completing the square does nothing — there is no
sum-of-two-squares reduction, and the counts do not track any factorisation
invariant of `b³±1` that survived inspection. Counts scatter from 1 to 24 with
outliers at `b = 16, 25, 22, 31` that the `d=2` story cannot explain.

**The `d=2` law is special to `d=2`.** It exists because the defining condition
is a *conic*; for `d=3` it is a cubic curve and the classical machinery changes
entirely. Do not look for a `d=3` analogue of the same shape.

### STRUCTURE — a proved constructive family

Visible in the raw data: `b=4 → {8,9}`, `b=9 → {27,28}`, `b=16 → {64,65}`,
`b=25 → {125,126}`, `b=36 → {216,217}`. These are `k³, k³+1` at `b = k²`.

**Claim.** For `d ≥ 3` and `k ≥ 2`, base `b = k^(d−1)` has fixed points `k^d` and
`k^d + 1`.

*Proof.* Take `n = k·b + m` with `0 ≤ m < b` and `k < b`, so the base-`b` digits
are exactly `(k, m)`. Then `T(n) = k^d + m^d`, and `n` is fixed iff
`k·b + m = k^d + m^d`. Substituting `b = k^(d−1)` gives `k·b = k^d`, so the
condition collapses to `m^d = m`, whose only non-negative solutions are `m ∈ {0,1}`.
The side condition `k < b = k^(d−1)` holds precisely when `d > 2` — which is why
`d=2` has no such family. ∎

Verified: every case with `d ∈ {3,4,5}`, `k ≤ 6`, `b ≤ 60` — the predicted pair is
present in the complete fixed-point set, and exhaustive check confirms no other
`m` works.

This also explains why `d=2` was tractable and `d=3` is not: **the same
substitution that made `d=2` a conic makes `d ≥ 3` a higher-genus curve.** The
constructive family survives because it avoids the curve entirely — it is a
degenerate solution where `k·b` and `k^d` coincide by fiat.

### TECHNIQUE
- **Digit-multiset enumeration** beats iterating every `n` below the bound:
  `O(C(b+k−1, k))` instead of `O(bound)`, and it extends to bases where full
  iteration is hopeless. Verified equivalent on `d=2, b ≤ 12` before trusting it.
  Now in `lib/digitmaps.py` as `fixed_points`.
- Scanning the *values* rather than the counts is what exposed the family. The
  count column showed noise; the fixed-point lists showed `64, 65` sitting next
  to each other at `b=16`.

### NEXT
The outlier counts remain unexplained — `b=16` has 24 fixed points, far beyond
the two the construction supplies. Concrete: for `b=16, d=3`, factor the 24 fixed
points by digit-length and check whether the excess is concentrated in 3-digit
solutions, which would point at a different mechanism than the 2-digit conic.

### COST
~2 minutes. The failed reduction was cheap to establish; the construction came
from reading the values rather than the summary statistics.
