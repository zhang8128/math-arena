import sys
sys.path.insert(0,'.timeloop/lib')
from sympy import primerange, isprime, factorint

def persistence(n,b):
    s=0
    while n>=b:
        p=1;m=n
        while m: p*=m%b; m//=b
        n=p; s+=1
    return s

def smooth_upto(primes,LIM):
    out=[1]
    for p in primes:
        new=[]
        for v in out:
            x=v
            while x<=LIM//p: x*=p; new.append(x)
        out+=new
    return out

print("MECHANISM: for PRIME b, the digit product N is (b-1)-smooth, so b never")
print("divides N -- a 0 digit can NEVER appear after step 1. Composite b can die early.\n")
print("   b   prime?  factorisation   best pers   argmax N          N/1e18   converged?")
for b in range(5,22):
    ps=[p for p in primerange(2,b)]
    sm=smooth_upto(ps,10**18)
    best=0; arg=1
    for n in sm:
        p=persistence(n,b)
        if p>best: best,arg=p,n
    # converged if the best witness is far below the search ceiling
    ratio=arg/10**18
    print(f"  {b:3}   {str(isprime(b)):5}  {str(dict(factorint(b))):14}  {1+best:6}     {arg:>18}  {ratio:7.1e}  "
          f"{'yes' if ratio<1e-3 else 'NO - truncated'}")

print("\nzero-digit deaths: fraction of smooth N whose chain hits a 0 digit")
for b in (10,11,12,13,16,17,19):
    ps=[p for p in primerange(2,b)]
    sm=smooth_upto(ps,10**12)
    def hits_zero(n):
        while n>=b:
            m=n; p=1; z=False
            while m:
                d=m%b
                if d==0: z=True
                p*=d; m//=b
            if z: return True
            n=p
        return False
    dead=sum(1 for n in sm if hits_zero(n))
    print(f"   base {b:3} ({'prime' if isprime(b) else 'composite':9}): {dead:6}/{len(sm):6} = {dead/len(sm):5.1%}")
