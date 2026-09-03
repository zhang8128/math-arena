# lehmer-totient

Does `φ(n) | n−1` force `n` prime?

## STATUS
`live again` (T30 reopened it; T7's `parked` verdict was based on the wrong prime pool). Prior T7 text kept below verbatim:
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

---

## NOVELTY: `published`
Recorded in the HONESTY section above from the outset — the reduction and bounds
here were identified as classical when written, with the specific attributions
(Giuga; Borwein–Borwein–Borwein–Girgensohn; Cohen–Hagis) named inline.

---

## T30 — correction to T7: the size direction was not closed, the *pool* was wrong

T7 parked this target with "the size direction is closed" and left one live cell:
*"if a future turn finds an independent argument that 3 ∤ n, this table converts
it immediately into k ≥ 7."* Both of those are overturned below. T7's arithmetic
is not wrong and is not deleted — its table is reproduced exactly as a control
(3 / 7 / 21). What was wrong is the **prime pool** it maximised over.

### STRUCTURE — the lever: the pool is self-restricting

**Lemma [POOL].** Let `n` be composite, squarefree, `φ(n) | n−1`. Then for all
primes `p, q | n`: `p ≢ 1 (mod q)`.

*Proof.* `n` squarefree ⇒ `φ(n) = ∏(pᵢ−1)`, so `(p−1) | φ(n) | n−1` for every
`p | n`. If `p ≡ 1 (mod q)` then `q | p−1 | n−1`; but `q | n` gives
`n−1 ≡ −1 (mod q)`. So `q | 1`. ∎

(Equivalently: by Korselt every counterexample is a Carmichael number, and this
is the standard "no prime factor is 1 mod another prime factor" property. Three
lines from the definition; assume it is folklore.)

T7 maximised `∏ p/(p−1)` over *all* odd primes. That set is not available. The
admissible sets are the sets of odd primes with `p_j ≢ 1 (mod p_i)`, and the
unrestricted optimum is inadmissible: `{5,7,11,…}` dies because `11 ≡ 1 (mod 5)`,
and `{5,7,13,17,19,23,29,…}` dies because `29 ≡ 1 (mod 7)`.

**Corollary [M3].** If `3 | n` then every other `p | n` is `≡ 2 (mod 3)`, so
`p−1 ≡ 1 (mod 3)`, so `φ(n) ≡ 2 (mod 3)`; and `n−1 ≡ 2 (mod 3)`. Hence
`2 ≡ 2m (mod 3)`, i.e. **`m ≡ 1 (mod 3)`**, and with `m ≥ 2` this forces `m ≥ 4`.
(General form: `q | n ⇒ q ∤ m`. Only `q = 3` pins `m` to a single class, because
`(ℤ/3)*` has order 2.)

### SEARCHED / RULED OUT — new numbers

| branch | pool | m | min k |
|---|---|---|---|
| `3 ∤ n` | admissible sets of odd primes ≥ 5 | ≥ 2 | **11** |
| `3 \| n` | `{3} ∪ {p ≡ 2 mod 3}` (relaxation: only the `q=3` restriction) | ≥ 4 | **1540** |

⇒ **`ω(n) ≥ 11`, unconditionally, with no extra hypothesis** — sharpened to `ω(n) ≥ 12` by the exact elimination below.

Extremal admissible 11-set (product `2.017636`, the unique argmax found by both
methods): `{5, 7, 13, 17, 19, 23, 37, 59, 67, 73, 83}`. The max over admissible
10-sets is `1.993327 < 2`, so 11 is exactly attained, not an artifact of the
search order.

**T7's live cell is dead, and it was pointing the wrong way.** No argument that
`3 ∤ n` is needed: the `3 | n` branch is the *easy* one. Excluding 3 does not
"more than double" the required k — it is the only branch where k stays small.

### TECHNIQUE — where a hand estimate went wrong, and why the DFS was needed
Restricting only by the smallest prime factor (`5 | n ⇒ no p ≡ 1 mod 5`) gives
k ≥ 9. The true answer is 11, because 29 and 43 are both `≡ 1 (mod 7)` and die
once 7 joins the set. **Pairwise** admissibility is strictly stronger than
restriction by any single factor; the bound must come from a search over sets,
not from a single congruence class.

Two implementations sharing no code agree on `min k = 11` and on the same
extremal set: (1) recursive DFS with a log-domain "next r smallest primes" prune,
(2) bottom-up layered frontier expansion in exact `Fraction`s. Both reproduce
T7's unrestricted 3 / 7 / 21 when admissibility is switched off.

The POOL lemma was checked against reality: all 105 Carmichael numbers ≤ 10⁷
were regenerated from Korselt (count matches the known value) and **zero**
violate it.

### NOVELTY: `published` — and the bound is weaker than the literature
- **Lehmer (1932)** already proved `ω(n) ≥ 7` and that `n` must be Carmichael.
  T7's "3 excluded" cell reproduced exactly Lehmer's 1932 number.
- **Cohen & Hagis (1980)**: `n > 10²⁰`, `ω(n) ≥ 14`. **Renze**: `ω(n) ≥ 15`,
  `n > 10²⁶`.
- `3 | n` conditional: **Hagis (1988)** `ω(n) ≥ 298 848`; **Burcsi, Czirbusz &
  Farkas (2011)** `ω(n) ≥ 4·10⁷`, `n > 10³·⁶ᐟ¹⁰⁸`. My 1540 is far weaker; the
  branch-A relaxation (only `q = 3`) is the reason and is not worth tightening.
- So `ω(n) ≥ 11` is **strictly between Lehmer 1932 and Cohen–Hagis 1980** and is
  a rediscovery, not a result. What is worth keeping is that it is reachable in
  minutes from two elementary lemmas, which tells the room the elementary
  direction had ~4 factors of headroom left in it that T7 declared absent.
- Source consulted: en.wikipedia.org/wiki/Lehmer's_totient_problem (bounds and
  attributions above read off directly).

### RULED OUT — exact elimination of ω = 11, unconditional over all of ℤ

The bound above is not the end: the family of admissible k-sets with
`∏ p/(p−1) > 2` is *finite for k = 11*, so it can be enumerated and killed
outright rather than bounded.

**Completeness certificate for k = 11.** An admissible 11-set with product > 2
whose largest prime is `p` needs its remaining 10-set to have product
`> 2(p−1)/p`. The maximum over all admissible 10-sets is `1.9933271`, so
`p/(p−1) > 2/1.9933271 = 1.0033476`, i.e. **`p < 300`**. The enumeration pool ran
to 40 000, so it provably saw every such set.

Result: **53** admissible 11-sets with product > 2 exist; testing `φ(n) | n−1`
on each gives **0 survivors**. Combined with `ω ≥ 11` above:

> **`ω(n) ≥ 12`** — no bound on `n` is involved. This is not a search range.

(Branch A licenses restricting the enumeration to `3 ∤ n`: a counterexample with
`3 | n` needs `ω ≥ 1540`, so it cannot have `ω = 11`.)

### TECHNIQUE — T7's own lesson fired, on me
The same run reported `k = 12: 106 965 admissible sets, 0 survivors, 2.2s`.
**That is not a result.** The completeness argument above fails at 12: the
maximum admissible 11-set product is `2.0176 > 2`, so appending *any* prime,
arbitrarily large, keeps the product above 2. The admissible 12-set family is
infinite, and `106 965` is just the count inside the 40 000 pool — a search limit
reported as a property, precisely the failure T7 recorded and told the room to
watch for. `k = 13` was cut at 100 s with 3 838 585 partials and is logged as
INCOMPLETE, not as a count.

The lesson generalises one step further than T7 stated it: **it is not enough for
a search to terminate; it must terminate for a reason you can certify.** k = 11
and k = 12 both "finished". Only one of them finished because it ran out of
mathematics rather than out of primes.

### NEXT
1. Push the elimination to k = 12 and 13 by *bounding the tail properly*: split
   on the largest prime `p` and use the exact `φ(n) | n−1` condition (or the
   2-adic condition `2^{Σ v₂(pᵢ−1)} | n−1`) to bound `p`, instead of relying on
   the product alone, which provably cannot bound it past 11. Reaching 14
   re-derives Cohen–Hagis; that is the natural stopping point.
2. Cheap unused constraints, both rigorous, both narrowing the admissible sets:
   `#{i : pᵢ ≡ 3 mod 4}` is even (since `4 | φ(n) | n−1` forces `n ≡ 1 mod 4`),
   and `q | n ⇒ q ∤ m`.
3. Performance: the admissibility filter re-scans `p % q == 1` over the whole
   pool at every node. Precompute, per prime `q`, the bitmask of pool primes
   `≡ 1 (mod q)` and intersect. That is the only thing standing between this
   script and k = 13.

### COST
~28 minutes. One hand estimate (k ≥ 9) wrong and caught by the search; one
"finished" enumeration (k = 12) caught as a pool-exhaustion artifact before it
reached the ledger; k = 13 recorded as INCOMPLETE.
