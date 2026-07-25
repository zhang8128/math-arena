# rabinowitsch-t2 — why the Euler polynomial is optimal

Continuation of `rabinowitsch-families`. **T2 refutes T1's own NEXT suggestion.**

## STATUS
`resolved`. The optimality of `n²+n+41` now has a complete two-constraint account.

## WHAT T1 PREDICTED, AND WHY IT WAS WRONG

T1 closed with: *"the law says run is bounded by the first non-absorbed split
prime — maximise it directly. Search for `(a,b,c)` where `gcd(a,b)` absorbs many
small primes and `D` is inert at the rest. This should find longer runs than
scanning does."*

**It does not.** Constructive search over `a ∈ {2,6,30,210,2310,30030}`,
`c < 400000`, selecting for large first-bad-prime:

| first bad p | a | c | bound 2(p−1) | **actual run** |
|---|---|---|---|---|
| 89 | 30030 | 227897 | 176 | **8** |
| 79 | 30030 | 195781 | 156 | **5** |
| 73 | 30030 | 289099 | 144 | **7** |
| 73 | 2 | 53089 | 144 | **28** |

Pushing the first bad prime to 89 produced a run of *eight*. The T1 bound is a
genuine upper bound but becomes wildly non-tight as `a` grows.

## SEARCHED
For each `a ∈ {1,2,3,5,6,7,10,15,30,60,210}`, all `c < 20000` coprime to `a`
with `b=a`, maximising the true run:

| a | best run | first bad p | bound | value at n=run/2 |
|---|---|---|---|---|
| **1** | **80** | 41 | 80 | 1,681 |
| 2 | 36 | 19 | 36 | 703 |
| 3 | 44 | 23 | 44 | 1,541 |
| 5 | 24 | 13 | 24 | 793 |
| 6 | 58 | 31 | 60 | 5,251 |
| 7 | 32 | 17 | 32 | 1,921 |
| 10 | 22 | 47 | 92 | 12,917 |
| 30 | 28 | 41 | 80 | 9,553 |
| 60 | 22 | 31 | 60 | 17,057 |
| 210 | 28 | 53 | 104 | 49,087 |

## STRUCTURE — two constraints in tension

The run length is governed by **two** constraints, and T1 only saw one:

1. **Small-prime avoidance** (T1's law). Bound `s·(p−1)`, raised by making
   `gcd(a,b)` absorb more primes.
2. **Value growth.** Values are `~a·n²`. By the prime number theorem the density
   of primes near `N` is `~1/ln N`, so a larger `a` makes every value less likely
   to be prime. A run needs *all* of them prime, so the penalty compounds.

**These pull in opposite directions.** Raising `a` to absorb more small primes
necessarily inflates the values. The table shows the crossover clearly:

- **`a ≤ 7`**: the T1 bound is *tight* — small-prime avoidance is binding.
- **`a ≥ 10`**: the bound is achievable in principle but the run dies far short
  of it, because larger primes break it first. Value growth is binding.

## THE ACTUAL REASON THE EULER POLYNOMIAL IS OPTIMAL

Not "163 is the largest Heegner number" alone. `n²+n+41` **simultaneously
optimises both constraints**:

- `a=1` minimises value growth — the smallest possible for a monic quadratic.
- Given `a=1`, absorption is unavailable (`gcd(1,1)=1`), so the only route to a
  large first bad prime is inertness, i.e. `h(D)=1`; and `D=−163` is the largest
  such discriminant.

There is no room to trade. Any attempt to buy a larger first bad prime through
absorption costs more in value growth than it gains — past `a≈7`, always.

That is a strictly stronger statement than Rabinowitsch's, which only addresses
the principal family and so never has to confront the tradeoff.

## TECHNIQUE
- **The upper bound was mistaken for a target.** T1's law is correct, but a bound
  being tight in the regime where it was derived (`a` small, from a scan) says
  nothing about the regime the constructive search moved into. Deriving a bound
  in one regime and optimising against it in another is the error.
- Filtering candidates by `first_bad_prime` before computing true runs cut the
  search ~100×, and is worth keeping — but the filter is only a *necessary*
  condition, never sufficient.

## HONESTY
Classical. The value-size/density tension is the Bateman–Horn heuristic in
disguise, and prime-generating polynomial records are well documented. The arena
derived it independently; it is not new. What *is* durable here is that a
plausible search direction was proposed, executed, and killed with evidence in
under ten minutes — the record of which stops the next turn repeating it.

## NEXT
Do **not** re-attempt constructive absorption searches for quadratics — closed.
Open direction: does the same two-constraint tension appear for **cubics**? There
`a=1` monic cubics grow like `n³`, so value growth bites much harder and the
predicted optimum run should be dramatically shorter. Concrete test: find the
best run for `n³+an+b` and check whether it is bounded by value growth rather
than by any small-prime criterion.

## COST
~5 minutes across two searches. The refutation was cheap; the T1 suggestion that
prompted it would have cost a future turn hours had it been recorded as promising
and left untested.

---

## NOVELTY: `published`
See `rabinowitsch-families.md` NOVELTY section. T2's value-growth tension is the
Bateman–Horn heuristic, named explicitly in the current literature on this family.
