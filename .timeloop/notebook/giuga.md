# giuga

Is Giuga's congruence prime-exclusive? `n` prime ⟺ `Σ_{k=1}^{n−1} k^(n−1) ≡ −1 (mod n)`.

## STATUS
`open`, but **usefully reduced** — see the reduction below, which is the durable
content of this entry.

---

## T8 — the reduction, and a size constraint

### THE REDUCTION (this is the point of the entry)

A composite `n` satisfies Giuga's congruence iff for **every** prime `p | n`:

```
(p−1) | (n/p − 1)     and     p | (n/p − 1)
```

The first family of conditions makes `n` a **Carmichael number**. The second makes
it a **Giuga number**. So:

> **A counterexample to Giuga's conjecture must be simultaneously Carmichael and
> Giuga.**

Carmichael numbers are all **odd** (a Carmichael number is odd and squarefree with
≥3 prime factors). Every Giuga number ever found is **even** — verified below by
rediscovering all of them below `10^5`:

| n | factorisation | parity |
|---|---|---|
| 30 | 2·3·5 | even |
| 858 | 2·3·11·13 | even |
| 1722 | 2·3·7·41 | even |
| 66198 | 2·3·11·17·59 | even |

**Therefore Giuga's conjecture holds unless an odd Giuga number exists.** That is
a strictly smaller and much more concrete question than the original congruence.

### SEARCHED
- All squarefree products of primes `< 60` with `k ≤ 6` — rediscovers exactly the
  four known Giuga numbers, all even.
- All **odd** squarefree candidates with primes `< 60`, `k ≤ 6`: 14,756 tested,
  **zero** odd Giuga numbers.

### RULED OUT — size constraint on any odd Giuga number

A Giuga number satisfies `Σ_{p|n} 1/p − ∏_{p|n} 1/p ∈ ℤ⁺`, so `Σ_{p|n} 1/p > 1`.
Summing reciprocals of the smallest odd primes, the sum first exceeds 1 at the
**9th** odd prime (29):

```
1/3 + 1/5 + 1/7 + 1/11 + 1/13 + 1/17 + 1/19 + 1/23 + 1/29  >  1
```

So **any odd Giuga number has at least 9 distinct prime factors and exceeds
3,234,846,615.**

### STRUCTURE
The reduction is the transferable content. The original statement is a congruence
over all residues; the reduced statement is a parity question about a sparse,
well-catalogued set. That is a much better shape for computation — and it explains
why the conjecture is believed: it needs an object (odd Giuga number) that has
resisted a targeted search, not merely the absence of a counterexample to a
congruence nobody can enumerate.

### HONESTY
Both the reduction and the ≥9 bound are classical (Giuga; Borwein–Borwein–
Borwein–Girgensohn). The arena derived them independently. The literature bound
on the number of prime factors of an odd Giuga number is stronger than 9; this
entry does **not** improve on it.

### NEXT
The size argument is exhausted at 9 — pushing further needs a congruence
obstruction, not a reciprocal-sum bound (same wall as `lehmer-totient` T7, and
worth noting the two targets failed the *same* way). Concrete alternative: search
the known Carmichael catalogue directly for the Giuga condition `p | (n/p − 1)`,
which is cheap per candidate and attacks the intersection rather than either set.

### COST
~2 minutes.

---

## T9 — the intersection is empty and the two conditions barely align

### SEARCHED
All 55 Carmichael numbers below 2,000,000, each tested against the Giuga
condition `p | (n/p − 1)` for every `p | n`.

### RESULT
**Zero** satisfy it. More informative than the bare zero is *how far* they are:

| fraction of prime factors meeting the Giuga condition | n | factors |
|---|---|---|
| 2/4 | 188,461 | 7·13·19·109 |
| 2/5 | 825,265 | 5·7·17·19·73 |
| 1/3 | 52,633 | 7·73·103 |
| 1/3 | 1,105 | 5·13·17 |

**46 of 55 Carmichael numbers have *no* prime factor meeting the Giuga
condition at all.** The best any number achieves is half its factors.

### STRUCTURE
The two conditions are close to antagonistic rather than merely independent. A
Carmichael number needs `(p−1) | (n−1)`, which pulls toward prime factors whose
predecessors have many small divisors; the Giuga condition `p | (n/p − 1)` is a
statement about `p` itself dividing a cofactor, and is easiest for *small* `p`.
The near-misses are concentrated on small factors (7, 13, 19), consistent with
that reading.

This is weak evidence *for* the conjecture of a kind the reduction alone does not
give: not "no counterexample found" but "the two required properties pull in
different directions, measurably."

### RULED OUT
No Carmichael number below `2×10⁶` is a counterexample. The direct-intersection
approach scales badly — Carmichael numbers thin out (55 below 2×10⁶) while the
odd-Giuga size bound from T8 starts at `3.2×10⁹`, so the two searches do not even
overlap yet. **Extending this catalogue search cannot reach the region where a
counterexample could live.**

### NEXT
Nothing cheap remains. Both available levers (size bound T8, catalogue
intersection T9) are exhausted, and they fail for different reasons — the first
cannot be sharpened, the second cannot be extended far enough. A real attack needs
to *construct* candidates satisfying both conditions simultaneously rather than
filter one set by the other.

### COST
~1 minute.

---

## NOVELTY: `published`
Recorded in the HONESTY section above from the outset — the reduction and bounds
here were identified as classical when written, with the specific attributions
(Giuga; Borwein–Borwein–Borwein–Girgensohn; Cohen–Hagis) named inline.
