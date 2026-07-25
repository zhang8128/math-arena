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
            sym=(b%a==0); integral=(b%(2*a)==0)
            pred=(2*(p-1)+1) if (sym and integral) else (2*(p-1) if sym else (p-1))
            if r==pred: ok+=1
            elif r<pred: short+=1
            else:
                over+=1
                if len(overs)<5: overs.append((r,pred,D,(a,b,c),p))
        a+=1
print(f"D in [-1500,0), primitive reduced forms with run>=10   [{time.time()-t0:.0f}s]")
print(f"  exactly at prediction : {ok}")
print(f"  short of prediction   : {short}   (expected: a larger prime intervenes)")
print(f"  ABOVE prediction      : {over}   <-- must be 0 if the bound is valid")
for o in overs: print("   VIOLATION", o)
