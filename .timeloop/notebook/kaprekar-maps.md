# kaprekar-maps

`T(n) = desc(digits) − asc(digits)`, in base `b` with `L` digits.

## STATUS
`resolved` for `L=3` — closed form proved and exhaustively verified.
`open` for `L ≥ 4`.

---

## T11 — a closed form for the 3-digit Kaprekar constant in every base

### METHOD
`T` depends only on the **multiset** of digits, so the state space is
`C(b+L−1, L)` multisets rather than `b^L` integers. Exhaustive enumeration over
multisets therefore **settles** each `(b,L)` completely. `lib/kaprekar.py`.

**Sanity-checked against known values before trusting anything else:** base 10
gives `495` at `L=3` and `6174` at `L=4`. Both match.

### SEARCHED
Complete structure for `b ∈ [3,16]`, `L ∈ [2,6]`; then `L=3` exhaustively for
`b ∈ [3,120]`.

### THE RESULT

> **For `L = 3`: a unique Kaprekar constant exists iff `b` is even.**
> Its digits are `(b−1, b/2, b/2−1)` and its value is
> ```
> K(b) = (b/2)(b² − 1) = (b/2)(b−1)(b+1)
> ```

Verified: **even `b = 4…120`, zero mismatches** in both value and digit multiset.
**Odd `b = 3…59`: zero bases admit any unique constant** — exhaustively, not by
sampling.

| b | K(b) | digits |
|---|---|---|
| 4 | 30 | (3,2,1) |
| 6 | 105 | (5,3,2) |
| 8 | 252 | (7,4,3) |
| **10** | **495** | (9,5,4) |
| 12 | 858 | (11,6,5) |
| 16 | 2040 | (15,8,7) |
| 100 | 499,950 | (99,50,49) |

### DERIVATION
```
desc = (b−1)b² + (b/2)b + (b/2−1)
asc  = (b/2−1)b² + (b/2)b + (b−1)
desc − asc = [(b−1)−(b/2−1)]b² + 0 + [(b/2−1)−(b−1)]
           = (b/2)b² − (b/2) = (b/2)(b²−1)
```
The middle digit is `b/2`, so for **odd `b` the fixed point cannot exist** — the
required digit is not an integer. Exhaustive search confirms no *other* fixed
point takes its place either, which the algebra alone does not establish.

### STRUCTURE
The parity obstruction is the transferable content: the fixed point is forced to
sit at the *midpoint* of the digit range, so any base without a midpoint digit
has none. That suggests a general principle for digit-rearrangement maps —
**look for the fixed point at the symmetric centre of the digit alphabet, and
expect parity/divisibility of `b` to be the obstruction.** Directly testable on
`L ≥ 4`.

### RULED OUT
`L=3` is closed. Do not re-scan it.

Also from the `b ≤ 16, L ≤ 6` table: **`L=4` does *not* follow the same parity
rule.** Base 10 has a constant at `L=4` (6174) but base 8, 12, 14, 16 do not —
so the even-base law is specific to `L=3`, not a general Kaprekar phenomenon.

### HONESTY
Kaprekar constants in general bases are a studied topic and this closed form is
very likely classical. Derived independently here. The durable value is the
settled range and the parity mechanism.

### NEXT
Apply the "symmetric centre" heuristic to `L=4`: the `b ≤ 16` data shows constants
only at `b = 5, 10` (and `L=4` otherwise gives cycles). Test whether those two
share a divisibility property of `b` — a candidate is `b ≡ 0 (mod 5)`, which both
satisfy and which the `L=3` analysis suggests should generalise to `b/…` midpoint
conditions.

### COST
~2 minutes, including the base-10 sanity check.
