import sys, time
sys.path.insert(0,'.timeloop/lib')
from sympy import primerange

def persistence(n,b):
    s=0
    while n>=b:
        p=1; m=n
        while m: p*=m%b; m//=b
        n=p; s+=1
    return s

def smooth_upto(primes, LIM):
    """all products of the given primes that are <= LIM"""
    out=[1]
    for p in primes:
        new=[]
        for v in out:
            x=v
            while x<=LIM//p:
                x*=p; new.append(x)
        out+=new
    return out

# Any digit product is a product of primes < b, and every prime < b IS a valid
# digit, so EVERY (b-1)-smooth number is realisable as a digit product.
# Hence  max persistence = 1 + max over (b-1)-smooth N of persistence(N,b).
LIM=10**18
t0=time.time()
print(f"deep search: (b-1)-smooth N <= 1e18, max persistence = 1 + max persistence(N,b)\n")
print("   b   primes<b        #smooth      best persistence")
res={}
for b in range(3,21):
    ps=[p for p in primerange(2,b)]
    sm=smooth_upto(ps, LIM)
    best=max(persistence(n,b) for n in sm)
    res[b]=1+best
    print(f"  {b:3}   {str(ps):16} {len(sm):9}       {1+best}")
print(f"\n[{time.time()-t0:.0f}s]")
print("\nbases beating base 10's famous 11:")
for b,v in sorted(res.items(), key=lambda kv:-kv[1]):
    if v>=11: print(f"   base {b:3} : persistence {v}{'   <-- base 10 reference' if b==10 else ''}")
