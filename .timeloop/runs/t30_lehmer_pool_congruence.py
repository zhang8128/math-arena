"""T30 lehmer-totient: restrict the prime pool by a congruence, then re-run the size bound.

LEMMA [POOL] (elementary).  Let n be composite, squarefree, phi(n) | n-1.
  n squarefree => phi(n) = prod (p_i - 1) => (p-1) | phi(n) | n-1 for every p | n.
  If q | n and p | n with p == 1 (mod q), then q | p-1 | n-1.  But q | n gives
  n-1 == -1 (mod q).  So q | 1, contradiction.
  => for all primes p,q | n:  p != 1 (mod q).
  (Equivalently: every such n is a Carmichael number by Korselt, and Carmichael
   numbers have no prime factor congruent to 1 mod another prime factor.)

COROLLARY [M3] (q=3).  If 3 | n then every other p | n is == 2 (mod 3), so
  p-1 == 1 (mod 3), so phi(n) == 2 (mod 3); and n-1 == 2 (mod 3).
  m = (n-1)/phi(n) then satisfies 2 == 2m (mod 3), i.e. m == 1 (mod 3).
  m >= 2 for composite n, so m >= 4.

T7's size bound is m < n/phi(n) = prod p/(p-1).  Re-run it over the RESTRICTED
pool.  "Admissible set" = set of odd primes with p_j != 1 (mod p_i) for all i,j.
"""
import math
from fractions import Fraction


def sieve(limit):
    s = bytearray([1]) * (limit + 1)
    s[0] = s[1] = 0
    for i in range(2, int(limit ** 0.5) + 1):
        if s[i]:
            s[i * i::i] = bytearray(len(s[i * i::i]))
    return [i for i in range(limit + 1) if s[i]]


# ---------------------------------------------------------------- branch B
# 3 does not divide n.  m >= 2.  Full admissibility, exact DFS.

def min_k_admissible(target, pool, kmax=40):
    """Smallest k with an admissible k-subset of `pool` whose prod p/(p-1) > target.
    Exhaustive: the prune is the r smallest remaining primes, an upper bound on
    anything reachable, and it is monotone decreasing in the start index."""
    n = len(pool)
    lg = [math.log(p / (p - 1)) for p in pool]
    suf = [0.0] * (n + 1)                       # suf[i] = sum of lg[i:]
    for i in range(n - 1, -1, -1):
        suf[i] = suf[i + 1] + lg[i]
    ltarget = math.log(target)

    def best_next(i, r):                        # log of r smallest ratios from i
        return suf[i] - suf[min(i + r, n)]

    for k in range(1, kmax + 1):
        found = []

        def dfs(i, chosen, lprod):
            r = k - len(chosen)
            if r == 0:
                pr = Fraction(1)
                for p in chosen:
                    pr *= Fraction(p, p - 1)
                if pr > target:
                    found.append((list(chosen), pr))
                    return True
                return False
            if i + r > n:
                return False
            if lprod + best_next(i, r) <= ltarget - 1e-12:
                return False
            for j in range(i, n - r + 1):
                p = pool[j]
                if any(p % q == 1 for q in chosen):
                    continue
                chosen.append(p)
                ok = dfs(j + 1, chosen, lprod + lg[j])
                chosen.pop()
                if ok:
                    return True
            return False

        if dfs(0, [], 0.0):
            return k, found[0]
    return None, None


# ---------------------------------------------------------------- branch A
# 3 | n.  Relaxation: use only the q=3 restriction (pool = {3} u {p == 2 mod 3}).
# A relaxation of admissibility, so the resulting k is still a valid LOWER bound.

def min_k_mod3_branch(target, primes):
    pool = [3] + [p for p in primes if p % 3 == 2]
    pr, k = Fraction(1), 0
    for p in pool:
        pr *= Fraction(p, p - 1)
        k += 1
        if pr > target:
            return k, pool[:k], pr
    return None, None, pr


def greedy_unrestricted(target, primes, skip3):
    pr, k = Fraction(1), 0
    for p in primes:
        if skip3 and p == 3:
            continue
        pr *= Fraction(p, p - 1)
        k += 1
        if pr > target:
            return k, p
    return None, None


PR_SMALL = [p for p in sieve(20000) if p != 2]
PR_BIG = [p for p in sieve(4_000_000) if p != 2]

print("=" * 74)
print("CONTRAST -- T7's table, full prime pool (reproduced as a control)")
for label, tgt, skip3 in (("m>=2, 3 allowed ", 2, False),
                          ("m>=2, 3 excluded", 2, True),
                          ("m>=4, 3 allowed ", 4, False)):
    k, p = greedy_unrestricted(tgt, PR_SMALL, skip3)
    print(f"  {label}:  k >= {k:4d}   (largest prime used {p})")

print()
print("=" * 74)
print("BRANCH B:  3 does not divide n.  m >= 2.  Full admissibility, exact DFS.")
poolB = [p for p in PR_SMALL if p != 3]
kB, wB = min_k_admissible(2, poolB)
print(f"  min k = {kB}")
print(f"  extremal admissible set: {wB[0]}")
print(f"  prod p/(p-1) = {float(wB[1]):.6f}")

print()
print("=" * 74)
print("BRANCH A:  3 | n.  m == 1 mod 3 and m >= 2, so m >= 4.")
print("  Pool relaxed to {3} u {p == 2 mod 3}  (q=3 restriction only).")
kA, poolA, prA = min_k_mod3_branch(4, PR_BIG)
print(f"  min k = {kA}   (largest prime used {poolA[-1] if poolA else None},"
      f" prod = {float(prA):.6f})")

print()
print("=" * 74)
print(f"UNCONDITIONAL:  omega(n) >= min({kA}, {kB}) = {min(kA, kB)}")
