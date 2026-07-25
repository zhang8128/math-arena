import sys
from sympy import primerange
from itertools import combinations
from math import prod
from fractions import Fraction

# Lehmer: phi(n) | n-1  =>  n prime?  A composite counterexample must be odd and
# squarefree (standard), so n = p1...pk with distinct odd primes.
# Let m = (n-1)/phi(n), an integer >= 2 for composite n.
# Since m < n/phi(n) = prod p/(p-1), we get a LOWER BOUND on k for each m.

print("m-bound: minimal k with prod_{smallest k odd primes} p/(p-1) > m\n")
odd=[p for p in primerange(3,400)]
print("   m   min k   product achieved   primes used")
for m in range(2,7):
    r=Fraction(1); k=0
    for p in odd:
        r*=Fraction(p,p-1); k+=1
        if r>m: break
    print(f"  {m:3}    {k:4}    {float(r):8.4f}        {odd[:k][:8]}{'...' if k>8 else ''}")

print("\nexhaustive check, k=3 and k=4, all prime factors below bound:")
for k,B in ((3,2000),(4,300)):
    odd=[p for p in primerange(3,B)]
    found=0; tested=0
    for combo in combinations(odd,k):
        n=prod(combo); ph=prod(p-1 for p in combo)
        tested+=1
        if (n-1)%ph==0:
            found+=1; print("   COUNTEREXAMPLE", combo)
    print(f"   k={k}, primes<{B}: {tested:,} squarefree n tested, {found} counterexamples")

# necessary condition: 2^k | phi(n) and phi(n) | n-1  =>  2^k | n-1
print("\nstructural: each p_i odd => 2^k | phi(n) | n-1, so n = 1 mod 2^k.")
print("combined with the m-bound, a counterexample with m=2 needs k>=3 and n=1 mod 8.")
