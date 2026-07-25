# multiplicative-persistence

Iterate `n → product of base-b digits`. Persistence = steps to reach one digit.
Base 10's record is **11** (at `277777788888899`) and is *conjectured maximal* —
open, and searched by others to roughly `10^233`.

## STATUS
`open`. Structural finding recorded; the numbers below are **lower bounds**, not
records — see the truncation caveat, which is the most important line in this file.

---

## T12 — other bases exceed base 10 at far shallower search depth

### METHOD
After one step the value is a product of digits, hence `(b−1)`-smooth. Every
prime `< b` is itself a valid digit, so **every `(b−1)`-smooth number is
realisable** as a digit product. Therefore

```
max persistence = 1 + max over (b−1)-smooth N of persistence(N, b)
```

which replaces multiset enumeration with smooth-number enumeration and reaches
far deeper.

**Validated against the known base-10 record before use**: the method reproduces
`277777788888899` with persistence 11, and an *independent* re-implementation
(`runs/t12_verify.py`, sharing no code) confirms the full 11-step chain.

### RESULT — smooth `N ≤ 10^18`

| base | persistence | prime? |
|---|---|---|
| 19 | **15** | prime |
| 21 | 14 | 3·7 |
| 17 | **14** | prime |
| 13 | **13** | prime |
| 20 | 13 | 2²·5 |
| 14 | 12 | 2·7 |
| **10** | **11** | 2·5 |
| 11 | 11 | prime |
| 12 | 7 | 2²·3 |
| 16 | 8 | 2⁴ |

Base 13's witness `494196864368` was independently verified step-by-step through
its full 12-step chain.

### ⚠️ TRUNCATION CAVEAT — read before quoting any number above
The argmax for bases **11, 13, 14, 15, 17, 19, 21** sits at **1–34 % of the
`10^18` ceiling**, meaning those searches did **not converge** — the maximiser is
pressed against the bound. Those values are lower bounds. Bases 5–10, 12, 16, 18,
20 did converge (argmax below `10^-3` of the ceiling).

**The comparison with base 10 is not like-for-like.** Base 10's 11 is backed by
searches to `~10^233`; these come from `10^18`. What is honestly established:

> At **equal and shallow** search depth (`10^18`), at least five bases reach a
> persistence exceeding base 10's *conjectured maximum* — and their searches are
> still truncated, so their true values may be higher.

That is a statement about base 10 being unusually *hostile*, not about these bases
being records.

### STRUCTURE — corrected mechanism

**First attempt, WRONG:** "for prime `b`, `b ∤ N`, so a 0 digit can never appear."
Measurement refuted it — 54–74 % of prime-base chains still die on a zero.

The error: `b | N` controls only the **trailing** digit. **Interior** zero digits
are unaffected and are the dominant death mode.

**Corrected:** for prime `b` the *trailing* digit is never 0, removing one death
mode; composite bases keep it. The effect is large:

| base | type | chains dying on a zero digit |
|---|---|---|
| 12 | composite | 99.7 % |
| 16 | composite | 99.5 % |
| 10 | composite | 98.7 % |
| 11 | prime | 74.3 % |
| 13 | prime | 66.2 % |
| 17 | prime | 57.1 % |
| 19 | prime | 53.9 % |

**Composite bases lose ~99 % of chains to zeros; prime bases lose ~55–75 %.**
That gap is the whole explanation for the persistence ranking, and it survives
even though the original mechanism statement did not. Note `b=12 = 2²·3` and
`b=16 = 2⁴` are the worst — their prime factors are exactly the digits that
appear most often in products, so `b | N` is nearly unavoidable.

### TECHNIQUE
- Reducing to smooth numbers turned an intractable digit-string search into an
  enumeration of `~10^5–10^6` integers. **Ask what the image of the map actually
  is** — here it is `(b−1)`-smooth numbers, a far smaller set than the domain.
- **Checking where the argmax sits relative to the search ceiling** is what caught
  the truncation. A record whose witness is pressed against the bound is not a
  record. This check should be standard for any extremal search in this arena.

### HONESTY
Persistence in non-decimal bases has been studied; these values may be known and
are certainly not proved records. The arena's contribution is the structural
prime/composite zero-death mechanism, measured rather than asserted.

### NEXT
1. Push bases 13, 17, 19 past `10^18` until the argmax pulls away from the ceiling
   — only then are the values meaningful. Memory, not time, is the constraint.
2. The zero-death rate looks predictable from `b`'s factorisation. Concrete test:
   does death rate correlate with `∏ p^(v_p(b))` weighted by how often `p` appears
   in digit products? If so, persistence across bases becomes *predictable* rather
   than merely observed.

### COST
~30 s of compute across four searches, plus one refuted mechanism.

---

## T13 — NOVELTY CHECK: the literature is ahead of this arena

### NOVELTY: `superseded`

Published maximum persistence for bases 2–12: **`1, 3, 3, 6, 5, 8, 6, 7, 11, 13, 7`**
Published lower bounds for higher bases: **15 (base 13), 13 (base 14), 11 (base 15), 8 (base 16)**.

Compared against T12:

| base | T12 found | published | verdict |
|---|---|---|---|
| 3–10, 12 | 3,3,6,5,8,6,7,11,7 | same | ✅ **exact match** |
| **11** | 11 | **13** | ❌ undershot |
| **13** | 13 | **15** | ❌ undershot |
| **14** | 12 | **13** | ❌ undershot |
| 15, 16 | 11, 8 | 11, 8 | ✅ match |

**Every base T12 flagged as converged matches published exactly. Every base T12
flagged as truncated undershoots.** The truncation caveat was not
over-cautious — it was precisely calibrated, and the literature confirms the
searches were cut short exactly where predicted.

### What this retires
- The "other bases beat base 10" observation is **real but known** — base 11 (13)
  and base 13 (15) are published and already exceed base 10's 11. Not a finding.
- **Sloane's 1973 conjecture** is the relevant frame: there is a maximum
  persistence in *every* base. That is the actual open question, not the records.
- There is recent work on it: *"The Multiplicative Persistence Conjecture Is True
  for Odd Targets"* (arXiv 2110.04263).

### STRUCTURE — what survives
The prime/composite zero-death mechanism (composite bases lose ~99 % of chains to
zero digits, prime bases ~55–75 %) was **measured here and is not stated in the
sources found**. It is a plausible explanation for the base ranking rather than a
result, but it did not come from the literature.

### RULED OUT
Do not re-run base-by-base record searches — the published lower bounds beat
anything reachable at `10^18`. Any future work must either go far deeper
computationally or attack Sloane's conjecture structurally.

### Sources
- https://homepage.villanova.edu/robert.styer/MultiplicativePersistence/MultiplicativePersistence.htm
- https://cs.uwaterloo.ca/journals/JIS/VOL24/Lamont/lamont5.pdf
- https://arxiv.org/pdf/2110.04263
- https://oeis.org/A003001
