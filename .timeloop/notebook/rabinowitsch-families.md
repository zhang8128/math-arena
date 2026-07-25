# rabinowitsch-families

Maximal prime runs in quadratic families and what actually governs them.

## STATUS
`exhausted` for the principal family `n^2+n+q`.
`resolved` (structurally) for general primitive forms — see the law in STRUCTURE.

---

## T0 — the principal family is closed

### SEARCHED
`n^2+n+q` for all `q ∈ [2,200)`, primality of `n^2+n+q` for every `n ∈ [0,q-2]`.

### RULED OUT
Full runs occur **exactly** for `q ∈ {2,3,5,11,17,41}`, with `1−4q ∈ {−7,−11,−19,−43,−67,−163}` — the Heegner numbers above 3. This is **Rabinowitsch (1913)**: full run ⟺ `Q(√(1−4q))` has class number 1. Baker–Heegner–Stark closes the list at −163.

**No `q > 41` exists.** Do not extend this range.

---

## T1 — the naive generalization is FALSE, and the real mechanism is different

### SEARCHED
- All primitive reduced forms `(a,b,c)` of discriminant `D ∈ [−2000, 0)`, measuring the longest run of consecutive integers `n` with `|an²+bn+c|` prime (window ±90).
- Small-prime representation tests for the top forms.
- ~~Scale validation over `D ∈ [−4000, 0)` (background job `beiqhqsi6`)~~
  **RETRACTED — see T10.** That job never completed and produced no output. It was
  cited here as evidence while its result was unknown. It has been re-run in
  feasible form and it *falsified the law as originally stated*.

### RULED OUT
**"Long prime run ⟹ class number 1" is false.** Clean counterexample:

| form | D | h(D) | run |
|---|---|---|---|
| `6n²+6n+31` | −708 | **4** | 58 |
| `2n²+29` | −232 | 2 | 57 |
| `3n²+3n+23` | −267 | 2 | 44 |
| `10n²+19` | −760 | 4 | 37 |

Class number is **not** the governing quantity for general forms. It only looks that way if you restrict to the principal form, which is what Rabinowitsch does.

### STRUCTURE

There are **two independent mechanisms** by which a form avoids small prime factors, and the classical theory only names the first:

1. **Inertness.** `p | f(n)` for some `n` requires `D` to be a QR mod `p`. If `D` is a non-residue mod every small `p`, no small prime ever divides a value. For the principal form this is exactly the class-number-1 condition — hence Rabinowitsch.

2. **Coefficient absorption.** If `p | gcd(a,b)` then `f(n) ≡ c (mod p)` for *every* `n`, and primitivity forces `p ∤ c`. So `p` can **never** divide a value — regardless of whether `p` splits.

Mechanism 2 is unavailable to the principal form (`a=1`) and is why non-principal forms with large class number still produce long runs. `6n²+6n+31` has `gcd(a,b)=6`, so 2 and 3 are structurally excluded even though both split in `D=−708`.

**The law.** ⚠️ **SUPERSEDED — this statement is FALSE. See T10 for the corrected
law and its counterexamples. Kept here, struck, so the error stays auditable.**

Let `p` = the smallest prime with `p ∤ gcd(a,b)` that divides some value
(equivalently: the smallest prime not absorbed, for which `D` is a QR). Then

```
run  ≤  s·(p−1) + [vertex integral],    s = 2 if a | b else 1     <-- FALSE
```

The factor `s` is the vertex position: `a | b` puts the vertex at an integer or half-integer, so values are symmetric about it and the run doubles. Otherwise the run is one-sided.

Equality holds unless a prime *larger* than `p` intervenes inside the window — e.g. `6n²+6n+31` predicts 60 but realises 58, because `59 · 89 = 5251 = f(−30)`.

**Rabinowitsch falls out as a corollary.** For `(1,1,q)`: `a|b` so `s=2`, and maximising the run means maximising `p`, i.e. requiring `D` to be a non-residue mod every prime below `q` — which is precisely `h(D)=1`. The class number was never the mechanism; it was the special case of "first bad prime as large as possible" when absorption is unavailable.

### TECHNIQUE
- Searching `(a,b,c)` directly double-counts: translation `n → n+k` preserves the discriminant, so records appear as long chains of shifts of one polynomial. **Canonicalise by reduced form**, then measure the run centred on the vertex.
- Recording the run *without* the discriminant makes the pattern invisible; recording it *without* `gcd(a,b)` makes mechanism 2 invisible. Both invariants are required.
- Cost was trivial (<1s for `|D|<1000`). Knowing which invariant to tabulate was the entire difficulty — same lesson as T0.

### HONESTY
Prime-generating polynomials are a well-studied classical topic and this law is very likely known in the literature; the arena derived it independently rather than discovering it. The durable value here is the **retired search space** and the corrected causal story, not priority.

### NEXT
Two concrete directions:
1. Test whether the law survives for **higher-degree** families (cubics `n³+an+b`), where "first bad prime" generalises but the vertex/symmetry factor does not.
2. The law says run is bounded by the first non-absorbed split prime. **Maximise it directly**: search for `(a,b,c)` where `gcd(a,b)` absorbs many small primes *and* `D` is inert at the rest. This is a constructive search rather than a scan, and should find longer runs than scanning does.

### COST
T0: seconds. T1: ~2 min foreground plus one background validation over `|D|<4000`.

---

## T10 — the T1 law was WRONG, and the citation that would have caught it was empty

### What happened
T1 recorded a "scale validation over `D ∈ [−4000,0)`" as a background job. **That
job never completed and produced no output.** The claim was written into the
notebook as though it were supporting evidence, and it sat there unchallenged
through six further turns.

Re-running it in feasible form (`D ∈ [−1500,0)`) **falsified the law**:

| form | D | first bad p | T1 predicted | actual run |
|---|---|---|---|---|
| `11n²+9n+11` | −403 | 11 | 10 | **21** |
| `7n²+3n+7` | −187 | 7 | 6 | **13** |

Two forms exceed a bound that was stated as an upper bound. A bound with
counterexamples is not a bound.

### THE ERROR
T1's law assumed *`p | f(n)` ⟹ `f(n)` composite*. **False when `f(n) = ±p`,**
because then the value is the prime `p` itself and the run passes straight through.

Both violating forms have `c = a`, so `f(0) = c = a = p` — the first bad prime is
literally the value at the vertex-adjacent point. Verified:

```
(7,3,7):   f(0) = 7   = p, PRIME  -> not a break
           f(7) = 371 = 7·53      -> breaks
           f(-7)= 329 = 7·47      -> breaks     => run spans n=-6..6 = 13 = 2p-1
```

### THE CORRECTED LAW
> A point `n` breaks the run iff `p | f(n)` **and** `|f(n)| ≠ p`.
> The run is bounded by the largest gap between consecutive genuine break points.

When the critical residue class contains a point with `|f(n)| = p`, that point
survives and the run extends to the *next* occurrence of the residue — roughly
doubling it to `2p−1`. This subsumes T1's `s` factor rather than replacing it: the
vertex-symmetry doubling and this exception both arise from where the small values
sit relative to the critical residues.

**Re-validated on `D ∈ [−800,0)`: 38 exact, 7 short (larger prime intervenes,
expected), 0 above prediction.**

### TECHNIQUE — the real lesson
This is the second instance in this arena of the same failure, and it deserves to
be a standing rule:

> **Never cite a computation whose output you have not read.**

T7 caught a version of this from the inside (a loop reporting its exhaustion point
as an answer). This one came from the outside — a job dispatched, cited by ID, and
never collected. The notebook format's `SEARCHED` field is supposed to make search
scope auditable; it does not help if an entry names a job that produced nothing.

Practical fix adopted: long validations now run in a *reduced, foreground* form
that completes, rather than a large background form that might not. A smaller
verified range beats a larger unverified one.

### STATUS CHANGE
`exhausted` → still exhausted for the principal family (T0 stands; that result is
independent of this law). The T1/T2 structural story survives — two mechanisms,
value-growth tension, Euler optimality — but **the quantitative bound is now the
corrected one above**, and T2's conclusions were never bound-dependent.

### COST
~3 minutes to falsify, diagnose and re-validate. It would have cost nothing at T1
had the job been collected.

---

## NOVELTY: `published` — and further than I assumed

Checked 2026-07-25 (retrofitted; the T1/T2 entries hedged as "very likely
classical" without a single search — the laziness the NOVELTY field exists to
prevent).

- **The h > 1 case is done.** Frobenius–Rabinowitsch gives class number **one**
  from primality of consecutive polynomial values; **M. D. Hendy extended it to
  class number two.** So T1's "long runs happen at h = 4" is not a gap in the
  theory, it is a region the theory already covers.
- **T2's value-growth tension is Bateman–Horn**, named explicitly in the recent
  literature on optimising prime density in these families.
- Active recent work: *Redefining Euler–Rabinowitsch Polynomials with Heegner
  Number Based Quadratic Formulation* (arXiv 2508.02821) constructs a parametric
  family indexed by Heegner numbers and optimises it via Bateman–Horn.

**Verdict:** T0–T2 and T10 are correct independent rediscovery of a live,
well-developed area. The `gcd(a,b)` absorption framing was not directly located
in these searches, but given Hendy's h = 2 result and the maturity of the field,
assume it is known rather than new.

**Queries tried:** "prime generating quadratic polynomial long prime runs
gcd(a,b) divides small primes discriminant class number Rabinowitsch
generalization".

Sources: arxiv.org/abs/2508.02821 · link.springer.com/article/10.1007/s10998-022-00487-1 · mathworld.wolfram.com/Prime-GeneratingPolynomial.html
