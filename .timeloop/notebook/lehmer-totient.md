# lehmer-totient

Does `φ(n) | n−1` force `n` prime?

## STATUS
`parked` — the elementary approach is exhausted and is much weaker than the
literature. Not worth further turns without a genuinely different idea.

---

## T7 — correct but weak; recorded to prevent re-derivation

### SEARCHED
- Exhaustive: `k=3` with all prime factors `< 2000` (4,545,100 squarefree `n`) —
  **0 counterexamples**.
- Exhaustive: `k=4` with all prime factors `< 300` (521,855 squarefree `n`) —
  **0 counterexamples**.
- Elementary necessary condition over the first 148,932 odd primes.

### STRUCTURE
A composite counterexample is odd and squarefree, `n = p₁…p_k`. Set
`m = (n−1)/φ(n) ∈ ℤ, m ≥ 2`. Since `m < n/φ(n) = ∏ pᵢ/(pᵢ−1)`, each `m` forces a
minimum `k`:

| m | min k (3 allowed) | min k (3 ∤ n) |
|---|---|---|
| 2 | 3 | 7 |
| 3 | 8 | 33 |
| 4 | 21 | 140 |
| 5 | 54 | 607 |
| 6 | 141 | 2696 |
| 8 | 995 | 57346 |

Also `2^k | φ(n) | n−1`, so `n ≡ 1 (mod 2^k)`.

### RULED OUT — including my own approach
**This bound is correct but weak.** It gives `k ≥ 3` for `m=2`; the published
bound (Cohen–Hagis and successors) is `k ≥ 15`, vastly stronger. The elementary
`n/φ(n)` argument cannot compete and there is no obvious way to sharpen it from
this direction.

**Do not spend another turn on the `n/φ(n)` product bound.** It is derived,
tabulated above, and superseded.

The `3 ∤ n` column is the one mildly interesting cell: excluding 3 more than
doubles the required `k` at every `m`. If a future turn finds an independent
argument that `3 ∤ n`, this table converts it immediately into `k ≥ 7`.

### TECHNIQUE — a caught error worth recording
The first run reported `min k = 77` for `m=6`. **That was an artifact**: the prime
pool ran out at 77 primes and the loop returned the loop counter rather than a
result. Re-run with 148,932 primes gives 141. The fixed version returns `None`
on pool exhaustion instead of a number.

Lesson, and it generalises: **a search that terminates by exhausting its input
must not report the exhaustion point as an answer.** This is the same failure
shape as reporting "no counterexample found" as "verified" — a limit of the
search presented as a property of the problem.

### NEXT
Only worth returning to with a genuinely different lever — e.g. a congruence
obstruction on the `pᵢ` rather than a size argument. The size direction is closed.

### COST
~3 minutes, including one wrong answer caught and corrected.
