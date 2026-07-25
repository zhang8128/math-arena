from sympy import factorint, isprime
from math import prod

def carmichael_upto(N):
    out=[]
    for n in range(3,N,2):
        if isprime(n): continue
        f=factorint(n)
        if any(e>1 for e in f.values()): continue
        ps=list(f)
        if len(ps)<3: continue
        if all((n-1)%(p-1)==0 for p in ps): out.append((n,ps))
    return out

N=2_000_000
cars=carmichael_upto(N)
print(f"Carmichael numbers below {N:,}: {len(cars)}")
hits=[]
for n,ps in cars:
    if all((n//p - 1) % p == 0 for p in ps):
        hits.append((n,ps))
print(f"of these, satisfying the GIUGA condition p | (n/p - 1) for all p : {len(hits)}")
print()
# how CLOSE do they get?  count how many primes satisfy the Giuga condition
best=[]
for n,ps in cars:
    good=sum(1 for p in ps if (n//p - 1) % p == 0)
    best.append((good/len(ps), good, len(ps), n))
best.sort(reverse=True)
print("closest approaches (fraction of prime factors meeting the Giuga condition):")
print("   frac  good/k        n           factors")
for fr,g,k,n in best[:8]:
    print(f"  {fr:5.2f}   {g}/{k}   {n:>10,}   {sorted(factorint(n))}")
print()
zero=sum(1 for fr,g,k,n in best if g==0)
print(f"Carmichaels where NO prime factor meets the Giuga condition: {zero}/{len(cars)}")
