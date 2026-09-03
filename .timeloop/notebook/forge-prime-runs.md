# forge-prime-runs

Prime-run records for integer polynomials, attacked with the
`reduce-to-decidable-family` frame: find a bound beyond which the object cannot
occur, then enumerate exhaustively below it.

## STATUS
`open` — one sharp bound proved and its tightness measured; the r=1 saturation
question is open and concrete.

---

## T29 — the counting bound, its sharp form, and what attains it

### The theorem (elementary, and it is a theorem, not a scan)

Let `f ∈ Z[x]`, `deg f = d ≥ 1`, `p` prime, and

* `R` = the set of residues `x mod p` with `f(x) ≡ 0 (mod p)`, `r = |R| ≥ 1`;
* `A = #{ n ∈ Z : |f(n)| = p }`, which is at most `2d` (roots of `f∓p`).

Suppose `|f(n)|` is prime for every `n` in a window `W = [N, N+L)`.
Every `n ∈ W` with `n mod p ∈ R` has `p | f(n)` and `|f(n)|` prime, hence
`|f(n)| = p`; distinct such `n` are distinct anchors, so

```
        #{ n ∈ W : n mod p ∈ R }  ≤  A.                                (*)
```

Writing `L = qp + s`, `0 ≤ s < p`, the classes `N, N+1, …, N+s−1 (mod p)` meet
`W` in `q+1` integers and the rest in `q`. So the left side of (*) depends only
on `(N mod p, L)` and maximising `L` over the `p` offsets is a **finite**
computation. Call the result `sharp(f,p)`, and `sharp(f) = min_p sharp(f,p)`.

Coarse corollary (drop the offset): `r·⌊L/p⌋ ≤ A ≤ 2d`, hence
`L < p·(⌊2d/r⌋ + 1)`, and with `P(f)` = least prime having a root mod `p`,
**`L < (2d+1)·P(f)`**. `P(f)` always exists (Schur 1912).

The `|f(n)| = p` escape clause is exactly the T10 correction in
`rabinowitsch-families.md`; here it is promoted from an exception to the
quantity `A` that drives the bound.

### DECIDABILITY (this is what the frame buys)

A bound alone does not localise: runs of length `≤ P(f)−1` sit in gaps between
root-class points and those gaps march off to infinity. But a run of length
`L ≥ P(f)` meets every residue class, so it **contains** an anchor `n*` with
`|f(n*)| = P(f)`. There are `≤ 2d` anchors and Cauchy's root bound puts them all
in an explicit interval. Therefore:

> For any `f`, "does `f` admit a run of length `≥ P(f)`?" is decidable by a
> finite scan, and when the answer is yes the scan returns the **exact global
> maximum run over all of Z** — not a windowed sample.

`lib/primerun_bounds.py::certified_max_run` implements this; it flags
`certified: True` exactly when the returned run is the global maximum.

### SEARCHED (every reported run below is certified-global, not windowed)

* Quadratics `a n² + b n + c`, `1 ≤ a ≤ 8`, `0 ≤ b ≤ a` (translation fixes
  `b mod 2a`, reflection fixes the sign), `|c| ≤ 1200`, primitive: **83,979
  polynomials**, of which **1,396** admit a run `≥ P(f)` and are certified.
* Monic cubics `n³ + b n² + c n + d`, `b ∈ {0,1,2}` (translation fixes `b mod 3`),
  `|c| ≤ 40`, `|d| ≤ 300`: **146,043 polynomials**, **4,490** certified.
* The constructed family `f_p(n) = n³ − p²n + p` for every prime `p < 60`.
* Lemma audit at every prime `≤ 60–100` on ~5,000 sampled quadratics: **0
  violations**.

### RULED OUT

1. **`maxrun ≤ 2·P(f)` is FALSE.** The Euler polynomial's `80/41 = 1.95` is not
   the ceiling; it is not even close to the record. Witnesses (all certified
   global maxima, all independently re-verified — see below):

   | `f` | `P` | `r` | `A` | max run | `ρ = run/P` |
   |---|---|---|---|---|---|
   | `2n² + 2n − 71` | 11 | 1 | 2 | **32** | **2.909** |
   | `2n² − 181`     | 19 | 2 | 4 | **55** | 2.895 |
   | `6n² + 6n − 79` | 7  | 1 | 2 | 20 | 2.857 |
   | `2n² − 61`      | 11 | 2 | 4 | 31 | 2.818 |
   | `n³ − 25n + 5`  | 5  | 1 | 3 | **19** | **3.800** |

   The whole region is invisible to the prior notebook, which only searched
   positive-definite forms (`D < 0`) with runs anchored at `n = 0`. Every record
   here is an **indefinite** form with negative constant term, and its run is
   centred on the vertex where the values are negative.

2. **The naive bound is far from sharp.** For `2n²+2n−71`, `L < 5p−1 = 54` while
   the truth is 32. `sharp(f,P)` gives 32 on the nose.

3. **The anchor-chain cubic family does not scale.** `f_p(n) = n³ − p²n + p`
   satisfies `f_p(0) = f_p(±p) = p`, giving three anchors in one root class — the
   mechanism behind the `ρ = 3.8` record. But for every prime `7 ≤ p < 60`,
   `P(f_p) = 5` (a *smaller* prime intrudes) and `A = 0` at that prime, so the
   theorem forces `maxrun ≤ 4`. Only `p = 3` (run 9) and `p = 5` (run 19) survive.
   **Do not extend this family.**

### STRUCTURE — the transferable part

**Run length is governed by anchor supply, not by the size of `P(f)`.** The
quantity that matters is `⌊A/r⌋` — how many times the polynomial can *be* the
obstructing prime, divided by how many residue classes must each be covered. A
long run is bought by stacking anchors in one root class, not by pushing `P(f)`
up. This inverts the T1/T2 story (`rabinowitsch-t2.md`), which optimised `P(f)`
by absorption and got runs of length 8; the record here has `P = 5`.

**`sharp(f,P)` is exactly attained by every record.** Computed independently by
two code paths:

| `f` | max run | `sharp(f,P)` | naive bound |
|---|---|---|---|
| `n² + n + 41` | 80 | **80** | 122 |
| `2n² + 2n − 71` | 32 | **32** | 54 |
| `2n² − 181` | 55 | **55** | 56 |
| `2n² − 61` | 31 | **31** | 32 |
| `n³ − 25n + 5` | 19 | **19** | 34 |
| `7n² + 3n + 7` | 13 | **13** | 34 |

The Euler polynomial saturating the sharp bound at exactly 80 is the strongest
single check: `p=41, r=2, A=2, q=1, s=39`, and `1·41 + 39 = 80`.

**Attainment rate.** Across the 1,396 certified quadratics, 336 (24.1%) attain
`sharp(f,P)` — so attainment is not automatic. But **the top 10 by `ρ` all
attain it**, and the worst shortfalls (`n²+n−109`: run 20 vs bound 56) are all
low-`ρ` polynomials where a larger prime intervenes first. Forged conjecture,
still standing after this turn's attack: *a prime-run record attains the sharp
anchor bound at `P(f)`.*

### TECHNIQUE

* The decisive move was making the search **certified rather than windowed**.
  `primeruns.py::max_consecutive_run` takes an arbitrary `window=400`; nothing
  in it excludes a longer run at `n = 10^6`. Localising via anchors costs three
  lines and upgrades every reported number from a sample to a theorem.
* `A` is computed exactly (not searched): the integer solutions of `f(n) = ±p`
  are bounded by Cauchy's root bound, so the enumeration is complete.
* Cost: 83,979 quadratics in 4.2 s, 146,043 cubics in 8.8 s. The bound is what
  makes it cheap — the scan window is `O(p)`, not a fixed large constant.
* **Independent re-verification** (`runs/t29_independent_check.py`): a second
  implementation sharing no code — `sympy.Poly` evaluation, a fresh run scanner
  over a window `12P+200` wide, anchors and root classes found by brute-force
  integer scan rather than modular arithmetic, and `sharp` recomputed from
  concrete windows. All six witnesses agree on `P`, on the run, and on
  attainment.

### NOVELTY: `not found` (shallow — one round of two web searches)

The coarse bound `L < (2d+1)·P(f)` is an elementary counting argument and should
be assumed folklore; the arena has independently derived elementary facts about
this family three times now (`rabinowitsch-families.md` NOVELTY). What was *not*
located is the offset-aware sharp form `sharp(f,p)`, the `A`-vs-`r` framing, or
the decidability statement.

Queries tried (2026-09-03):
* "prime-generating polynomial bound consecutive prime values least prime divisor
  of value set run length"
* "\"consecutive prime values\" polynomial upper bound \"smallest prime\" root
  modulo p counting argument Rabinowitsch generalization"

Returned: MathWorld *Prime-Generating Polynomial* (states Euler's 40/80 runs, no
bound of this shape); arXiv 2503.07793 and 1307.0766 (largest prime *divisor* of
polynomial values — a different quantity); arXiv 1304.5988 (least modulus making
consecutive polynomial values distinct — related shape, different statement);
arXiv 2011.11054, 1803.11061 (least prime with a root mod p, under GRH — bounds
`P(f)` itself, which is the input to this bound, not the bound).

**Not checked:** OEIS for the record-run sequence, and the `h=2` literature
(Hendy) which `rabinowitsch-families.md` flags as already covering more than the
arena assumed. Treat the sharp bound as unverified-for-novelty.

### NEXT

One concrete action: **decide whether `ρ > 3` is possible for quadratics.**
`ρ > 3` needs `⌊A/r⌋ ≥ 3` with `d = 2`, so `A ≥ 3` and `r = 1` — i.e. a quadratic
taking the value `±P` at three integers in one class mod `P`. Since `f = P` has
≤ 2 roots and `f = −P` has ≤ 2, this forces the ordering
`f=P, f=−P, f=−P, f=P` with consecutive gaps multiples of `P`, hence
discriminant `D ≥ 9a²P² − 4aP`. That is a **one-parameter family per `(a,P)`**:
enumerate it directly for `P ≤ 100`, `a ≤ 20`, and either exhibit `ρ ≥ 3` or
close the quadratic case at `ρ_max = 32/11`. Do not re-scan boxes; the boxes
above are done.

### COST
~30 min wall clock. 230,022 polynomials certified-scanned (13 s of compute), one
library + 9 passing tests, one independent verification path, two web searches.
