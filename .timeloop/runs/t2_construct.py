import sys, time
sys.path.insert(0,'.timeloop/lib')
from sympy import primerange, isprime, legendre_symbol
from math import gcd

PRIMES=list(primerange(2,4000))

def first_bad_prime(a,b,c):
    """smallest p not absorbed by gcd(a,b) that can divide f(n)"""
    g=gcd(a,b); D=b*b-4*a*c
    for p in PRIMES:
        if g%p==0: continue
        if p==2:
            if any((a*n*n+b*n+c)%2==0 for n in range(2)): return 2
            continue
        if a%p==0:
            if any((a*n*n+b*n+c)%p==0 for n in range(p)): return p
            continue
        if D%p==0: return p
        if legendre_symbol(D%p,p)==1: return p
    return None

def true_run(a,b,c,window=200):
    best=cur=0
    for n in range(-window,window+1):
        v=abs(a*n*n+b*n+c)
        if v>1 and isprime(v): cur+=1; best=max(best,cur)
        else: cur=0
    return best

t0=time.time()
best=[]
# a = primorial-ish so gcd(a,b)=a absorbs many small primes; b=a => vertex at -1/2 => s=2
for a in (2,6,30,210,2310,30030):
    for c in range(2, 400000):
        if gcd(c,a)!=1: continue
        p=first_bad_prime(a,a,c)
        if p and p>=37:
            best.append((p,a,c))
    print(f"a={a:6} scanned, best-so-far {max([b[0] for b in best], default=0)}  [{time.time()-t0:.0f}s]")
best.sort(reverse=True)
print()
print(" first_bad_p    a       c      predicted 2(p-1)   ACTUAL run")
seen=set()
for p,a,c in best[:14]:
    r=true_run(a,a,c)
    print(f"{p:9}  {a:6}  {c:8}      {2*(p-1):6}          {r:5}")
