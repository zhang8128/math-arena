# erdos-straus

T19 studied the restricted `tame` family introduced by Xu for the remaining
prime case `n = 24m + 1`. With `x = 6m+k`, `1 <= k <= 12m`, a solution is tame
when both later denominators divide `n*x`. A prime is `wild` when no such tame
solution exists. Wild does **not** mean counterexample to Erdős--Straus.

## STATUS

`open`

The conjecture remains open. The run independently reproduces the published
wild census through its known boundary and gives two apparently new,
independently verified wild candidates beyond it.

## SEARCHED

- Every `m` from 1 through **1,000,000**.
- All **187,948** primes `n = 24m+1` in that range.
- Every admissible `x = 6m+k`, `1 <= k <= 12m`, until a tame certificate was
  found or the complete range was exhausted.
- Primary output: `.timeloop/runs/t19_erdos_residues.json`.
- Discovery implementation: `.timeloop/runs/t19_erdos_residues.py`.
- Independent verifier: `.timeloop/runs/t19_erdos_independent.py`.

The independent implementation uses trial-division primality and factorization,
its own divisor generator, and direct cross-multiplication. It imports none of
the discovery kernel. Its final replay returned:

`PASS range=1..1000000 primes=187948 triples=187934 wild=14 identity_checks=1000`

The complete wild list is:

`409, 577, 5569, 9601, 23929, 83449, 102001, 329617, 712321, 1134241, 1724209, 1726201, 5212561, 8813281`.

This exactly reproduces Xu's nine cases through `m <= 30,000`, and exactly
reproduces the 12 exceptional integers listed by Maiti through `m <= 100,000`.

## RULED OUT

The first implementation accidentally searched all factor-pair solutions while
failing to enforce the defining tame conditions `y | n*x` and `z | n*x`. It
therefore reported zero wild primes. A regression test exposed the semantic
error; after the divisibility filter was added, the published five wild cases
through `m <= 2,000` and nine through `m <= 30,000` appeared exactly. Never use
the earlier all-solutions output as evidence about tame/wild structure.

Also ruled out: treating a wild prime as an Erdős--Straus counterexample. The two
new candidates have exact ordinary, non-tame decompositions:

\[
\frac4{5212561}=\frac1{1303143}+\frac1{617519307252}
 +\frac1{7640493702695576827004},
\]

\[
\frac4{8813281}=\frac1{2203321}+\frac1{6472829035494}
 +\frac1{447304438314532718777574}.
\]

Both identities are covered by exact regression tests.

## STRUCTURE

For `q = n*x` and `a = 4x-n`, the two-denominator remainder obeys

\[
(ay-q)(az-q)=q^2.
\]

The exact kernel uses this identity for general solutions. For tame search it is
more efficient to enumerate only divisors `y | q`, solve
`z = q*y/(a*y-q)`, and then require `z | q`. The optimized implementation
validates the supplied factorization of `q`, checks ordering, divisibility, and
the original unit-fraction identity. Equivalence tests compare it against the
general factor-pair kernel on small complete ranges.

A parameter family recovered during the search is

\[
n=120t+73,\quad x=30t+20,\quad y=(6t+4)n,\quad z=(15t+10)n.
\]

Direct algebra gives `4/n = 1/x + 1/y + 1/z`; the independent verifier checks
the first 1,000 parameters and Lean proves the identity for every natural `t`.
The family is classical/published rather than novel.

## TECHNIQUE

- Math Prism was invoked on Erdős--Straus in both broad and narrow modes. All
  applications failed Prism's artifact contract, so no invalid frame was used.
- Exact integer arithmetic only: no floating-point comparisons.
- Checkpoints are atomic and resumable. The checkpoint interval is configurable
  and covered by a CLI regression test.
- A performance failure at `m = 71,005` revealed repeated factorization of the
  fixed prime `n`; the corrected kernel factors `x`, inserts the known prime
  factor, reconstructs `n*x` as a guard, and enumerates only tame-relevant
  divisors.
- Positive controls include complete small brute force, even `n`, `n = 3 mod 4`,
  the published wild prefixes, and the parameterized `120t+73` identity.

## NOVELTY

`apparently new computational extension; unreviewed`

The two additional wild primes found after the published `m <= 100,000` boundary
are:

| `m` | `n = 24m+1` | status |
|---:|---:|---|
| 217,190 | 5,212,561 | independently verified wild; ordinary decomposition above |
| 367,220 | 8,813,281 | independently verified wild; ordinary decomposition above |

Queries run on 2026-08-03 included exact searches for each integer with
`Erdos-Straus`, `Erdős--Straus`, `Egyptian fraction`, `unit fraction`, `tame
solution`, the corresponding `m`, the complete known prefix, and OEIS. Neither
integer produced a relevant mathematical hit. This is negative search evidence,
not a proof of priority; public use requires expert review and broader database
checking.

Sources:

- Xu, *Congruence Classes of Supporting the Erdös-Straus Conjecture I: Tame
  Solutions* (2026): <https://arxiv.org/abs/2605.23601>.
- Maiti, *A Study on Erdős-Straus conjecture on Diophantine equation...* (2021):
  <https://arxiv.org/abs/2101.00975>.

## NEXT

1. Ask an Erdős--Straus specialist to verify that the tame definition and search
   bounds match Xu exactly and to audit the two independent implementations.
2. Submit the 14-term sequence to OEIS only after that review.
3. Analyze `m` modulo the Xu congruence systems for the two new cases; identify
   the first missing parameter family rather than merely extending the census.
4. If more compute is useful, resume from `m=1,000,000`; do not discard the
   complete absence checks or replace them with probabilistic sampling.

## COST

Roughly three hours of investigation and verification. The optimized primary
extension from `m=500,000` to `1,000,000` took 24 seconds. The final independent
million-range replay took about 21 minutes wall time and 146 CPU seconds. The
earlier slow paths were retained as diagnostic evidence rather than quoted as
final performance.
