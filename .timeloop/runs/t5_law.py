import sys, statistics
sys.path.insert(0,'.timeloop/lib')
from digitmaps import fixed_points
from math import gcd
from sympy import primerange

def universal_M(d):
    """Largest M with x^d = x (mod M) for ALL x: product of primes p with (p-1)|(d-1)."""
    M=1
    for p in primerange(2, 200):
        if (d-1) % (p-1) == 0: M*=p
    return M

# MECHANISM: n = sum d_i b^i = sum d_i (mod b-1), so
#   T(n) - n = sum (d_i^d - d_i)  (mod b-1),
# and x^d = x (mod M_d) for all x. Hence T(n) = n (mod gcd(b-1, M_d)) AUTOMATICALLY.
# One congruence is satisfied for free => solution density boosted by that factor.
# PREDICTION: mean fixed-point count scales with g = gcd(b-1, M_d).
for d in (2,3,4,5):
    M=universal_M(d)
    print(f"\nd={d}   universal modulus M_d = {M}   (x^{d} = x mod {M} for all x)")
    groups={}
    hi = 46 if d>=3 else 121
    for b in range(2,hi):
        g=gcd(b-1,M)
        cnt=len(fixed_points(b,d))
        groups.setdefault(g,[]).append(cnt)
    print("   g=gcd(b-1,M_d)   #bases   mean #fixed points")
    for g in sorted(groups):
        v=groups[g]
        print(f"        {g:4}        {len(v):4}        {statistics.mean(v):6.2f}")
