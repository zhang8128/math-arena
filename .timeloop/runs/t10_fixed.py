import sys, time
sys.path.insert(0,'.timeloop/lib')
from primeruns import max_consecutive_run
from sympy import primerange
from math import gcd

PR=list(primerange(2,400))
def first_bad_prime(a,b,c):
    g=gcd(a,b)
    for p in PR:
        if g%p==0: continue
        if any((a*n*n+b*n+c)%p==0 for n in range(p)): return p
    return None

def predicted(a,b,c,p,W=200):
    """CORRECTED: a point breaks the run only if p|f(n) AND |f(n)| != p."""
    breaks=[n for n in range(-W,W+1)
            if (a*n*n+b*n+c)%p==0 and abs(a*n*n+b*n+c)!=p]
    if not breaks: return None
    best=0
    for i in range(len(breaks)-1):
        best=max(best, breaks[i+1]-breaks[i]-1)
    return best

t0=time.time(); ok=short=over=0; overs=[]
for D in range(-1500,0):
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
            r=max_consecutive_run(a,b,c,window=60)
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
print(f"CORRECTED LAW, D in [-1500,0)   [{time.time()-t0:.0f}s]")
print(f"  exactly at prediction : {ok}")
print(f"  short of prediction   : {short}   (larger prime intervenes - expected)")
print(f"  ABOVE prediction      : {over}   <-- must be 0")
for o in overs: print("   VIOLATION", o)
