"""T30: from a bound to an exact elimination.

For a fixed k, the set of admissible k-sets of odd primes with prod p/(p-1) > 2
is FINITE and (it turns out) small.  Enumerate all of them and test the actual
hypothesis phi(n) | n-1 on each.  If none passes, there is NO Lehmer
counterexample with exactly k prime factors -- with no upper bound on n at all.

This is unconditional over all of Z, not a search range -- BUT ONLY WHEN THE
POOL IS PROVABLY BIG ENOUGH.  That holds at k=11 and FAILS at k>=12:

  max product over admissible 10-sets = 1.9933271 < 2, so an 11-set reaching 2
  needs its largest prime p to satisfy p/(p-1) > 2/1.9933271, i.e. p < 300.
  The pool runs to 40000, so k=11 is COMPLETE: 53 sets, 0 survivors.

  max product over admissible 11-sets = 2.0176 > 2, so appending ANY prime,
  arbitrarily large, keeps a 12-set above 2.  The admissible 12-set family is
  INFINITE.  The "106965" this script prints for k=12 is the count inside the
  pool, NOT a count of admissible sets, and its "0 survivors" is NOT a proof.
  Do not quote the k>=12 lines as results.  See notebook TECHNIQUE, T30.
"""
import sys, time
from fractions import Fraction

def sieve(limit):
    s = bytearray([1]) * (limit + 1); s[0] = s[1] = 0
    for i in range(2, int(limit ** .5) + 1):
        if s[i]:
            s[i*i::i] = bytearray(len(s[i*i::i]))
    return [i for i in range(limit + 1) if s[i]]

P = [p for p in sieve(40000) if p != 2]
R = [Fraction(p, p - 1) for p in P]
# opt[i][r] handled on the fly: product of r best ratios after index i
import functools
PREF = [Fraction(1)]
for r in R:
    PREF.append(PREF[-1] * r)
def optimism(j, r):
    """best product from r primes with index > j"""
    a, b = j + 1, min(j + 1 + r, len(P))
    return PREF[b] / PREF[a]

def eliminate(k, exclude3, tlimit=100):
    t0 = time.time()
    cnt_full = 0
    survivors = []
    stack = [((), -1, Fraction(1))]
    total_nodes = 0
    while stack:
        st, li, pr = stack.pop()
        d = len(st)
        if d == k:
            cnt_full += 1
            n = 1
            for p in st: n *= p
            phi = 1
            for p in st: phi *= (p - 1)
            if (n - 1) % phi == 0:
                survivors.append(st)
            continue
        if time.time() - t0 > tlimit:
            return None, cnt_full, survivors, "TIMEOUT"
        need = k - d
        for j in range(li + 1, len(P)):
            p = P[j]
            if exclude3 and p == 3: continue
            if any(p % q == 1 for q in st): continue
            np_ = pr * R[j]
            if np_ * optimism(j, need - 1) <= 2:
                # ratios decrease in j, so no larger j works either
                break
            total_nodes += 1
            stack.append((st + (p,), j, np_))
    return True, cnt_full, survivors, f"{time.time()-t0:.1f}s nodes={total_nodes}"

for k in range(11, 17):
    done, nfull, surv, note = eliminate(k, exclude3=True)
    if done is None:
        print(f"k={k:3d}  INCOMPLETE ({note}) -- partial count {nfull}, NOT a result")
        break
    print(f"k={k:3d}  admissible sets with prod>2: {nfull:12d}   "
          f"phi|n-1 survivors: {len(surv)}   [{note}]")
    if surv:
        print("   SURVIVORS:", surv[:5]); break
    sys.stdout.flush()
