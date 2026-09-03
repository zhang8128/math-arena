# brocard

Brocard's problem: `n! + 1 = m^2`. Known solutions `n = 4, 5, 7` (`m = 5, 11, 71`),
the "Brown numbers". Erdős conjectured there are no others.

## STATUS
`open`. T28 was a **forage turn** — no attack on the target. Six method frames
filed from the literature, each mechanism sanity-checked at toy scale
(`runs/t28_frame_validation.py`).

### CORRECTION to the pool entry (read this before planning a search)
`pool.jsonl` says *"Searched past 10^9 with none further."* That is the
**Berndt–Galway (2000)** bound and is stale by six orders of magnitude. The
literature record is:

| bound on `n` | who | when | cost |
|---|---|---|---|
| 63 | Gupta | 1935 | by hand |
| 10^7 | Wells | 1986 | — |
| 10^9 | Berndt & Galway | 2000 | — |
| 4·10^11 | Matson | 2015 | 4 months, **one core** of an i7-2600 |
| 10^12 | (prior to Epstein–Glickman) | — | — |
| **10^15** | Epstein & Glickman | 2020 | ~5 months, github.com/jhg023/brocard |

Sources: <https://en.wikipedia.org/wiki/Brocard%27s_problem>,
<https://mathworld.wolfram.com/BrocardsProblem.html>,
<http://unsolvedproblems.org/S73.pdf>, <https://github.com/jhg023/brocard>.
**Do not spend a turn "extending past 10^9".** The frontier is 10^15 and it cost
someone five months of wall clock; a turn of this arena cannot move it.

---

## SEARCHED (this turn: the literature, not the integers)

Queries run, and what each returned:

- *"Brocard n!+1=m^2 Overholt abc conjecture"* → Overholt 1993, Dąbrowski 1996,
  Luca 2002. Hit.
- *"Berndt Galway Brocard-Ramanujan quadratic residue sieve"* → the paper exists
  (Ramanujan J. **4** (2000) 41–42) but no method detail online. Found the method
  instead in Matson, who says he used *"the same [approach] as that outlined by
  Berndt & Galway"*.
- *"Berend Osgood P(x)=n! density zero"* → Berend–Osgood 1992, Berend–Harmse 2006.
- *"Epstein Glickman 10^15"* → github.com/jhg023/brocard.
- *"Matson Brocard 2017 algorithm"* → <http://unsolvedproblems.org/S73.pdf>
  (actually 2015). **This is the one document with the algorithm written down.**
- *"Erdős Granville Pomerance Spencer divisors of n!"* → **nothing usable.** I was
  looking for a "does `n!` have a divisor within 2 of `sqrt(n!)`" density statement
  to underwrite a heuristic-count frame. Did not find it; the frame is NOT filed.
  Next turn: try "Erdős–Tenenbaum multiplication table", "H(x,y,z)", "divisors of
  `n!` in short intervals" instead — the four-author attribution was my error and
  sent the search sideways.

### Deliberately not used
`arXiv:2606.23485` (Peixoto, June 2026), *"The Brocard Problem: Structural
Invariants, p-Adic Density, and the Generative Sieve"* — preprint, not
peer-reviewed, does not claim a proof, and its central heuristic self-admits
*"independence between consecutive factorials that is not formally justified."*
Its Theorem 3 ("a Brown number exists iff `n!/8` is triangular") is the elementary
`n! = (m-1)(m+1) = 4a(a+1)` restatement. Recorded so the next turn does not spend
budget rediscovering that it is unusable rather than wrong.

---

## RULED OUT

**Small-modulus congruence sieving is identically vacuous on this target.** For
any prime `p <= n` we have `p | n!`, hence `n! + 1 ≡ 1 (mod p)`, which is a square.
So no fixed modulus, and no finite set of fixed moduli, can reject even one
sufficiently large `n`. Verified exhaustively: all 3766 pairs `(p, n)` with `p` an
odd prime `<= 100` and `p <= n <= 200` give `n!+1 ≡ 1 (mod p)` and Legendre
symbol `+1`. Zero exceptions.

This **contradicts the premise recorded in `pool.jsonl`'s `forges` field**
("cheap modular obstructions as search-space retirement") as usually understood,
and it means the arena's existing `congruence-obstruction` frame ("computing the
object modulo small primes") is actively misleading here. The obstruction exists,
but the modulus must *exceed the entire search range*. Frame
`sieve-above-the-vacuity-floor` records the corrected form.

---

## STRUCTURE

**1. The whole difficulty is that `A = 1` is a square.**
For `n! + A = m^2` with `A` **not** a perfect square, there is a prime `p` with
Legendre symbol `(A|p) = -1`; for every `n >= p`, `n! + A ≡ A (mod p)`, a
non-residue. So `n < p`: the family is finite *with an explicit elementary bound*.
Checked for every non-square `A` in `[2, 200]`: such a `p` always exists, and the
worst case in that range is `A = 91` with `p = 17`, i.e. `n < 17`. The obstruction
is not merely cheap, it is instant.

At `A = 1` the machinery is exactly, identically vacuous, because `(1|p) = +1` for
every prime. Brocard's problem is the single degenerate fibre of a family whose
every other member falls to a two-line argument. That is a sharper statement of
"why it is hard" than any search bound, and it says where *not* to look: any
attack that ultimately reduces to a Legendre/quadratic-character obstruction on a
fixed modulus is dead before it starts.

**2. The reducibility gap.** `n!+1 = m^2` is `P(m) = n!` with `P(x) = x^2 - 1`,
which **factors** as `(x-1)(x+1)`. Berend–Harmse (2006) prove finiteness of
`P(x) = l!` for `P` irreducible (plus some reducible cases under technical
conditions). Whether `x^2 - 1` is inside or outside their covered class is
**UNRESOLVED here** — I could not extract the theorem statement (the arXiv PDFs
for 1903.01076 and 2308.11002 defeated text extraction). If `x^2-1` is outside,
that is precisely the published gap Brocard sits in, and it is worth one search.

**3. Near-miss depth is the real quantitative output of a sieve, not "none found".**
Matson reports the deepest survivors (first `n` passing 38/40, then 39/40) rather
than only the null result; Epstein–Glickman report `602,723,832,772,967` passing
49/50. Those are checkable, comparable numbers; "no solution below X" is one bit.

---

## TECHNIQUE

The Matson/Berndt–Galway sieve, stated exactly (from S73.pdf):

- Test primes `P_i` **all greater than the intended search ceiling** (Matson: the
  first 40 primes above 10^12, for a search aimed at 10^12).
- Maintain `n! mod P_i` incrementally: one modular multiply per `n` per prime.
- Test the Legendre symbol of `n!+1` mod `P_i` by Euler's criterion with
  exponentiation-by-squaring and Montgomery multiplication. `-1` for **any** `i`
  ⇒ `n` is not a solution. `0` (i.e. `P_i | n!+1`) is treated as a pass;
  with `P_i > 10^12` this is negligibly rare.
- Short-circuit on the first `-1`, so the expected number of symbol evaluations
  per `n` is ~2 regardless of battery size.
- **Sizing rule:** each prime rejects with probability ≈ 1/2, so `k` primes leave
  ≈ `N·2^-k` false survivors over a range of size `N`. Choose `k ≈ log2(N)`.
  Matson: 40 primes for `N = 10^12` (`2^40 ≈ 10^12`). Epstein–Glickman: 50 for 10^15.
- Passing all `k` is **necessary, not sufficient** — a full survivor still needs
  an exact check.

Replayed at toy scale (40 primes above 10^4, `n` in `[8, 5000]`, so `P_i > n`
throughout): deepest survivor passed 12 of 40; observed counts at `k >= 1..12` were
2546, 1288, 652, 333, 159, 80, 41, 27, 15, 8, 5, 4 against the prediction
2496, 1248, 624, 312, 156, 78, 39, 20, 10, 5, 2.4, 1.2 — geometric decay confirmed
over four orders of magnitude. Control: `n = 4, 5, 7` each pass 40/40, as they must.
Cost 0.35 s in Python/sympy.

Cost model implication: the sieve is `O(k)` modular multiplies per `n` with a tiny
constant, and it is **embarrassingly parallel in `n`**. It is also why the frontier
moves by months of wall clock, not by cleverness.

---

## NOVELTY
`published` throughout — nothing in this entry is claimed as new. References:

- H. Brocard, *Question 166*, Nouv. Corresp. Math. **2** (1876) 287.
- H. Gupta, *On a Brocard–Ramanujan problem*, Math. Student **3** (1935) 71.
- M. Overholt, *The Diophantine equation `n!+1=m^2`*, Bull. LMS **25** (1993) 104
  — weak Szpiro/abc ⇒ finitely many Brown numbers.
- A. Dąbrowski, *On the Diophantine equation `x!+A=y^2`*, Nieuw Arch. Wisk. (4)
  **14** (1996) 321–324 — finiteness for all fixed `A`; unconditional for `A` a
  non-square, weak-abc-conditional when `A` is a square (per MathWorld).
- D. Berend & C. F. Osgood, *On the equation `P(x)=n!` and a question of Erdős*,
  J. Number Theory **42** (1992) 189–193 — solution set has **density zero**,
  unconditionally, for any `P` of degree `>= 2`.
- D. Berend & J. E. Harmse, *On polynomial-factorial Diophantine equations*,
  Trans. AMS **358** (2006) 1741–1779.
- F. Luca, *The Diophantine equation `P(x)=n!` and a result of M. Overholt*,
  Glasnik Mat. (2002).
- B. Berndt & W. Galway, Ramanujan J. **4** (2000) 41–42 — `n <= 10^9`.
- R. D. Matson, *Brocard's Problem 4th Solution Search Utilizing Quadratic
  Residues*, <http://unsolvedproblems.org/S73.pdf> (2015) — `n < 4·10^11`.
- Epstein & Glickman (2020), <https://github.com/jhg023/brocard> — `n < 10^15`.
- E. F. Bravo, *On Brocard's problem with Padovan and Perrin numbers*,
  arXiv:2606.28577 (2026) — `(n,x)=(4,5)` is the only solution with `x` Padovan
  or Perrin; Matveev linear forms in logarithms + Baker–Davenport reduction.

Not found despite looking: any published density statement about divisors of `n!`
near `sqrt(n!)` (see SEARCHED).

---

## NEXT
One concrete action, in priority order:

1. **Settle the reducibility gap.** Find the exact hypothesis of Berend–Harmse
   (TAMS 358, 2006) and determine whether `P(x) = x^2 - 1` is covered. If it is
   not, that is the precise published frontier for Brocard and every subsequent
   turn should aim at it. Get the statement from TAMS or a survey that quotes it —
   the arXiv PDFs resist text extraction, so use an HTML source
   (`arxiv.org/abs/...` landing pages worked; `/pdf/` did not).
2. If (1) is covered, apply frame `recurrence-slice-baker`: pick a recurrence not
   yet done in the literature (Bravo did Padovan/Perrin; Fibonacci/Lucas is
   arXiv:1509.07898) and close that slice — a real theorem inside one turn.
3. **Do not** extend the numerical search. Frontier 10^15, cost ≈ 5 months.

## COST
~25 min wall clock. 11 web searches/fetches; one 0.35 s validation probe
(`runs/t28_frame_validation.py`, four independent mechanism checks). No search of
the target was run and none is claimed.
