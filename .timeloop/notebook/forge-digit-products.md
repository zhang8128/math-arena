# forge-digit-products

The selected adjacent map is

\[
F_b(n)=\prod_i d_i+\sum_i d_i,
\]

where the `d_i` are the base-`b` digits of `n`, including internal zeroes.

## STATUS

`open`

Fixed points are classified in every base, while general cycle structure remains
unresolved.

## SEARCHED

- Complete functional graphs for bases `b = 2..6`, from `0` through the proved
  eventual-decrease bounds:
  - `b=2`: `0..5`
  - `b=3`: `0..24`
  - `b=4`: `0..747`
  - `b=5`: `0..65,568`
  - `b=6`: `0..9,765,675`
- The discovery implementation is `.timeloop/runs/t18_digit_products.py`; its
  exact output is `.timeloop/runs/t18_digit_products.json`.
- A second implementation importing none of `.timeloop/lib` independently
  recomputed every bound and every cycle set. It returned `PASS` for all five
  bases and all **27 cycles**.

The bound is exact enough to settle each listed base. For a `k`-digit number,
`F_b(n) <= (b-1)^k + k(b-1)`. Once this is below `b^(k-1)`, it remains below the
minimum number of every larger digit length, so all later states strictly
decrease. The returned bound is the image maximum at the first such `k`.

## RULED OUT

The T5 digit-power mechanism does **not** extend from fixed points to complete
cycles. The tempting claim

`product(digits(n)) = 0 mod (b-1)` for every periodic state

fails already in base 3: `n=1` lies on the cycle `(1,2,4,3)`, and its digit
product is `1`, not `0 mod 2`. The independent enumerator reproduced the cycle.

Do not search for a direct cycle-wide analogue of the T5 congruence using this
map. The nonlinear product term destroys the additive congruence except at a
fixed point, where the equation itself restores it.

## STRUCTURE

### Fixed points are completely classified

For every base `b >= 2`, the fixed points are exactly

\[
0\quad\text{and}\quad a b+(b-1),\qquad 1\le a<b.
\]

Equivalently, every nonzero fixed point has exactly two digits, and its final
digit is `b-1`.

**Proof.** Let `n` have digits `d_0,...,d_k`, with `d_k > 0`. The fixed-point
equation is

\[
\sum_{i=0}^k d_i b^i=\prod_{i=0}^k d_i+\sum_{i=0}^k d_i,
\]

so

\[
\sum_{i=1}^k d_i(b^i-1)=\prod_{i=0}^k d_i.
\]

If `k >= 2`, the leading term alone is
`d_k(b^k-1) > d_k(b-1)^k`, while the full digit product is at most
`d_k(b-1)^k`; therefore equality is impossible. A one-digit fixed point obeys
`d_0=2d_0`, hence is zero. For two digits `ab+c`, the equation reduces to
`ab+c=ac+a+c`, hence `a(b-c-1)=0`; since `a>0`, `c=b-1`. Conversely every such
two-digit number satisfies the equation. ∎

The complete low-base tables agree exactly:

| base | fixed points | non-fixed cycle lengths |
|---:|---|---|
| 2 | `0, 3` | `2` |
| 3 | `0, 5, 8` | `4` |
| 4 | `0, 7, 11, 15` | `3, 3` |
| 5 | `0, 9, 14, 19, 24` | `6, 2` |
| 6 | `0, 11, 17, 23, 29, 35` | `10` |

The weaker fixed-point obstruction also follows immediately: the digit product
is divisible by `b-1` at every fixed point.

## TECHNIQUE

- Select a mixed map with a provable eventual-decrease bound before enumerating.
- Preserve both the strongest surviving statement and the first counterexample
  to the stronger statement. Here the same run produced a complete fixed-point
  theorem and killed the cycle-wide congruence generalization.
- The independent verifier uses its own `divmod` transcription and state table;
  it shares only the JSON evidence format with the discovery implementation.
- Math Prism was invoked before the experiment, but six broad and two narrow
  applications across the candidate domains produced zero contract-valid
  artifacts. No Prism output influenced this derivation.

## NOVELTY

`published` in the public mathematical record, not novel.

The exact arbitrary-base classification and essentially the same inequality
proof appeared in a Mathematics Stack Exchange answer on 2017-06-01:
<https://math.stackexchange.com/questions/2304977/number-equal-to-the-sum-of-digits-product-of-digits>.
The answer explicitly gives
`{0, a*b + (b-1) | 1 <= a < b}`. A second 2022 question independently records
the same general-base classification:
<https://math.stackexchange.com/questions/4482101/prove-that-there-exists-no-integer-x-99-s-t-x-textproduct-of-digits-of>.

Queries tried on 2026-08-03:

- `"product of the digits" "sum of the digits" iteration fixed points`
- `"digit product plus digit sum" mathematics`
- `site:oeis.org "product of its digits" "sum of its digits"`
- `site:arxiv.org digit product sum dynamical map digits`

OEIS A062237 and A380873 concern **concatenating** the digit sum and product,
not adding them, so they are a different dynamical map. No primary paper or OEIS
entry for the complete bases `2..6` cycle tables was found, but a small table is
not treated as a novelty claim.

## NEXT

Find a parameterized description of the non-fixed cycles, beginning with why
the principal cycle lengths for bases `2..6` are `2,4,3,6,10`. First falsify
simple dependencies on `b-1`, Euler phi, and multiplicative order; do not extend
the exhaustive base range past 6 without replacing state-by-state traversal.

## COST

About 20 minutes of wall-clock work. The complete discovery traversal took
4.7 seconds; the independent full traversal took 4.0 seconds. The remaining
time was derivation, test construction, and novelty lookup.
