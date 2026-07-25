import sys, time
sys.path.insert(0,'.timeloop/lib')
from primeruns import max_consecutive_run
from sympy import primerange
from math import gcd

PR=list(primerange(2,200))
def first_bad_prime(a,b,c):
    g=gcd(a,b)
    for p in PR:
        if g%p==0: continue
        if any((a*n*n+b*n+c)%p==0 for n in range(p)): return p
    return None

def predicted(a,b,c,p):
    """breaks = n with p|f(n) AND |f(n)| != p.  Max gap between consecutive breaks."""
    res=[r for r in range(p) if (a*r*r+b*r+c)%p==0]
    W=3*p+5
    breaks=sorted(n for n in range(-W,W+1) if n%p in res
                  and abs(a*n*n+b*n+c)!=p)
    if len(breaks)<2: return None
    return max(breaks[i+1]-breaks[i]-1 for i in range(len(breaks)-1))

t0=time.time(); ok=short=over=0; overs=[]
for D in range(-800,0):
    if D%4 not in (0,1): continue
    a=1
    while 3*a*a <= -D:
        for b in range(-a+1,a+1):
            num=b*b-D
            if num%(4*a): continue
            c=num//(4*a)
            if c<a: continue
            if (a==c or abs(b)==a) and b<0: continue
            if gcd(gcd(a,b),c)!=1: continue
            r=max_consecutive_run(a,b,c,window=50)
            if r<10: continue
            p=first_bad_prime(a,b,c)
            if p is None: continue
            pred=predicted(a,b,c,p)
            if pred is None: continue
            if r==pred: ok+=1
            elif r<pred: short+=1
            else:
                over+=1
                if len(overs)<5: overs.append((r,pred,D,(a,b,c),p))
        a+=1
print(f"CORRECTED LAW, D in [-800,0)   [{time.time()-t0:.0f}s]")
print(f"  exactly at prediction : {ok}")
print(f"  short  (larger prime) : {short}")
print(f"  ABOVE prediction      : {over}   <-- must be 0")
for o in overs: print("   VIOLATION", o)
