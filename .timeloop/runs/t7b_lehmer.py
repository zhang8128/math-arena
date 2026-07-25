from sympy import primerange
from fractions import Fraction

odd=[p for p in primerange(3,2_000_000)]
print(f"prime pool: {len(odd):,} odd primes up to 2e6\n")

def min_k(m, pool):
    r=Fraction(1)
    for i,p in enumerate(pool,1):
        r*=Fraction(p,p-1)
        if r>m: return i, float(r)
    return None, float(r)   # exhausted pool -> NOT an answer

print("minimal k with prod p/(p-1) > m   (necessary condition, since m < n/phi(n))")
print("   m    min k (3 allowed)    min k (3 excluded, i.e. 3 does not divide n)")
no3=[p for p in odd if p!=3]
for m in range(2,9):
    k1,v1=min_k(m,odd); k2,v2=min_k(m,no3)
    s1=f"{k1:6}" if k1 else f"  >{len(odd)}"
    s2=f"{k2:6}" if k2 else f"  >{len(no3)}"
    print(f"  {m:3}       {s1}              {s2}")
print()
print("Reading: a composite counterexample with (n-1)/phi(n) = m must have at least")
print("that many distinct prime factors. The classical published bound is k >= 15,")
print("which is far stronger than this elementary necessary condition -- so this")
print("bound is CORRECT BUT WEAK. Recorded to stop a later turn re-deriving it.")
