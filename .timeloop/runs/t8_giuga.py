from sympy import primerange, factorint
from fractions import Fraction
from itertools import combinations
from math import prod

# n is a Giuga number iff composite squarefree and p | (n/p - 1) for every p|n,
# equivalently  sum_{p|n} 1/p  -  prod_{p|n} 1/p  is a positive integer.
def is_giuga(ps):
    n=prod(ps)
    return all((n//p - 1) % p == 0 for p in ps)

print("known Giuga numbers, rediscovered by direct search over small prime sets:")
found=[]
small=list(primerange(2,60))
for k in range(3,7):
    for combo in combinations(small,k):
        if is_giuga(combo):
            found.append((prod(combo),combo))
for n,c in sorted(found)[:8]:
    print(f"   {n:>12,}  = {' * '.join(map(str,c))}   {'ODD' if n%2 else 'even'}")

# A Giuga counterexample must ALSO be Carmichael, and Carmichael numbers are odd.
# So: does an ODD Giuga number exist?  Necessary size condition:
print("\nnecessary condition for an ODD Giuga number (sum 1/p must exceed 1):")
odd=[p for p in primerange(3,10**6)]
s=Fraction(0)
for k,p in enumerate(odd,1):
    s+=Fraction(1,p)
    if s>1:
        print(f"   sum of 1/p over the {k} smallest odd primes first exceeds 1 at p={p}")
        print(f"   => any odd Giuga number has AT LEAST {k} distinct prime factors")
        print(f"   => it exceeds {prod(odd[:k]):.3e}" if False else
              f"   => it is at least {prod(odd[:k])}")
        break

print("\nexhaustive: no odd Giuga number with all prime factors < 60 and k <= 6")
odd_small=[p for p in primerange(3,60)]
cnt=0
for k in range(3,7):
    for combo in combinations(odd_small,k):
        cnt+=1
        if is_giuga(combo): print("   ODD GIUGA FOUND", combo)
print(f"   {cnt:,} odd squarefree candidates tested, 0 found")
