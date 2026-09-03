"""T30 independent re-derivation of the branch-B bound, sharing no code with
t30_lehmer_pool_congruence.py.

Method 2: bottom-up layered enumeration (no recursion, no log-prune).  For each
k, enumerate ALL admissible k-sets whose product p/(p-1) can still reach 2, by
keeping a frontier of partial sets and extending with primes that are (a) larger
than the last, (b) admissible, (c) not already hopeless under an exact rational
optimism bound built from the next available primes.  Reports the maximum
product at each k.  Also: sanity-checks the POOL lemma against real Carmichael
numbers, which are exactly the n satisfying the divisibility hypothesis's
consequence p-1 | n-1.
"""
from fractions import Fraction
from sympy import primerange, factorint

PRIMES = [p for p in primerange(3, 20000)]
IDX = {p: i for i, p in enumerate(PRIMES)}

# exact optimism: best product obtainable from r primes strictly after index i,
# ignoring admissibility (an over-estimate, so safe)
def optimism(i, r):
    v = Fraction(1)
    for j in range(i + 1, min(i + 1 + r, len(PRIMES))):
        v *= Fraction(PRIMES[j], PRIMES[j] - 1)
    return v

def layered(kmax, exclude3, parity=False):
    """frontier entries: (tuple_of_primes, last_index, product)"""
    out = {}
    frontier = [((), -1, Fraction(1))]
    for k in range(1, kmax + 1):
        nxt = []
        best = Fraction(0)
        bestset = None
        for st, li, pr in frontier:
            for j in range(li + 1, len(PRIMES)):
                p = PRIMES[j]
                if exclude3 and p == 3:
                    continue
                if any(p % q == 1 for q in st):
                    continue
                np_ = pr * Fraction(p, p - 1)
                ns = st + (p,)
                if np_ > best:
                    best, bestset = np_, ns
                # keep only if it can still reach 2 within kmax factors
                if np_ * optimism(j, kmax - k) > 2:
                    nxt.append((ns, j, np_))
        ok = best > 2
        if parity:
            ok = ok and (sum(1 for p in bestset if p % 4 == 3) % 2 == 0)
        out[k] = (best, bestset, len(nxt))
        print(f"  k={k:3d}  max prod = {float(best):.6f}  {'>2 REACHED' if best>2 else ''}"
              f"   frontier {len(nxt)}   argmax {bestset}")
        if best > 2:
            return k, bestset
        frontier = nxt
        if not frontier:
            print("   frontier empty -- EXHAUSTED INPUT, not an answer (T7 lesson)")
            return None, None
    return None, None

print("METHOD 2 (layered, exact rationals): branch B, 3 excluded, target 2")
k2, w2 = layered(14, exclude3=True)
print(f"\n  METHOD 2 answer: min k = {k2}, witness {w2}\n")

print("=" * 74)
print("POOL LEMMA sanity check on real Carmichael numbers (n <= 10^7).")
print("Every Lehmer counterexample is Carmichael (Korselt), so the lemma must")
print("hold on all of them.  A single violation would refute the derivation.")
N = 10 ** 7
spf = list(range(N + 1))
for i in range(2, int(N ** 0.5) + 1):
    if spf[i] == i:
        for j in range(i * i, N + 1, i):
            if spf[j] == j:
                spf[j] = i
carms, viol = [], []
n = 561
while n <= N:
    m, fs, sqfree = n, [], True
    while m > 1:
        p = spf[m]
        c = 0
        while m % p == 0:
            m //= p; c += 1
        if c > 1:
            sqfree = False; break
        fs.append(p)
    if sqfree and len(fs) >= 3 and all((n - 1) % (p - 1) == 0 for p in fs):
        carms.append((n, fs))
        for a in fs:
            for b in fs:
                if a != b and a % b == 1:
                    viol.append((n, a, b))
    n += 2
print(f"  Carmichael numbers found <= 10^7: {len(carms)}  (expected 105)")
print(f"  POOL-lemma violations: {len(viol)}   {'-- LEMMA HOLDS' if not viol else viol[:5]}")
print(f"  min omega over them: {min(len(f) for _, f in carms)}")
print(f"  3 | n for {sum(1 for n_,f in carms if 3 in f)} of them")
mx = max(carms, key=lambda t: Fraction(t[0]) / Fraction(t[0] - 1))
print(f"  max (n-1)/phi(n) over them: "
      f"{max(float(Fraction(n_-1, 1) / Fraction(1).__class__(1)*0+ (n_-1)/__import__('sympy').totient(n_)) for n_, f in carms):.6f}"
      "   (needs to be an integer >=2 for a Lehmer counterexample)")
