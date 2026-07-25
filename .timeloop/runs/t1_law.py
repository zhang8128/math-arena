import sys
sys.path.insert(0,'.timeloop/lib')
from primeruns import max_consecutive_run
from sympy import primerange, factorint
from math import gcd

def first_bad_prime(a,b,c,limit=2000):
    g=gcd(a,b)
    for p in primerange(2,limit):
        if g%p==0: continue
        if any((a*n*n+b*n+c)%p==0 for n in range(p)): return p
    return None

# LAW (candidate):  run <= s*(p-1) + [vertex integral],  s = 2 if a|b else 1
# with equality unless a prime LARGER than p divides a value inside the window.
ok=exc=0; exceptions=[]
for D in range(-4000,0):
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
            r=max_consecutive_run(a,b,c,window=80)
            if r<12: continue
            p=first_bad_prime(a,b,c)
            if p is None: continue
            sym = (b % a == 0)
            integral = (b % (2*a) == 0)
            pred = (2*(p-1)+1) if (sym and integral) else (2*(p-1) if sym else (p-1))
            if r == pred: ok+=1
            else:
                exc+=1
                if len(exceptions)<8: exceptions.append((r,pred,D,(a,b,c),p))
print(f"forms with run>=12 : law exact in {ok}, short of prediction in {exc}")
print(f"prediction is an UPPER BOUND — violated above prediction? "
      f"{'NO' if all(r<=pr for r,pr,_,_,_ in exceptions) else 'YES'}")
print()
print("  run  pred      D   form            p    why short")
for r,pred,D,f,p in exceptions:
    a,b,c=f
    # find the larger prime that broke it early
    vals={}
    for n in range(-60,61):
        v=abs(a*n*n+b*n+c)
        if v>1:
            fac=factorint(v)
            if len(fac)>1 or list(fac.values())[0]>1:
                sm=min(fac)
                if sm>p: vals[n]=sm
    br=sorted(vals.items(), key=lambda kv: abs(kv[0]))[:1]
    print(f"{r:5} {pred:5}  {D:6}  {str(f):15} {p:3}   larger prime {br[0][1] if br else '?'} at n={br[0][0] if br else '?'}")
