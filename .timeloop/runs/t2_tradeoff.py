import sys, time
sys.path.insert(0,'.timeloop/lib')
from sympy import isprime, primerange, legendre_symbol
from math import gcd, log

PRIMES=list(primerange(2,2000))
def first_bad_prime(a,b,c):
    g=gcd(a,b); D=b*b-4*a*c
    for p in PRIMES:
        if g%p==0: continue
        if p==2 or a%p==0:
            if any((a*n*n+b*n+c)%p==0 for n in range(p)): return p
            continue
        if D%p==0: return p
        if legendre_symbol(D%p,p)==1: return p
    return None

def true_run(a,b,c,window=120):
    best=cur=0
    for n in range(-window,window+1):
        v=abs(a*n*n+b*n+c)
        if v>1 and isprime(v): cur+=1; best=max(best,cur)
        else: cur=0
    return best

t0=time.time()
print("  a   best actual run   at c      first_bad_p   2(p-1) bound   value at n=run/2")
for a in (1,2,3,5,6,7,10,15,30,60,210):
    bestr=0; arg=None
    for c in range(2, 20000):
        if gcd(c,a)!=1: continue
        p=first_bad_prime(a,a,c)
        if not p or 2*(p-1) <= bestr:   # cannot beat current best
            continue
        r=true_run(a,a,c)
        if r>bestr: bestr, arg = r,(c,p)
    c,p=arg
    half=bestr//2
    val=a*half*half+a*half+c
    print(f"{a:3}   {bestr:8}        {c:7}   {p:8}      {2*(p-1):8}       {val:,}")
print(f"\n[{time.time()-t0:.0f}s]")
