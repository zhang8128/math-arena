import sys
sys.path.insert(0,'.timeloop/lib')
from primeruns import class_number, max_consecutive_run
from sympy import primerange
from math import gcd

def first_bad_prime(a,b,c,limit=500):
    """Smallest p that can divide f(n) for some n. Primitive form assumed."""
    g=gcd(a,b)
    for p in primerange(2,limit):
        if g % p == 0:      # p | gcd(a,b) and p /| c  => p never divides f(n)
            continue
        if any((a*n*n+b*n+c) % p == 0 for n in range(p)):
            return p
    return None

# PREDICTION: run length is governed by the first bad prime, NOT by h(D).
rows=[]
for D in range(-2000,0):
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
            r=max_consecutive_run(a,b,c,window=90)
            if r>=30:
                rows.append((r,D,class_number(D),(a,b,c),first_bad_prime(a,b,c)))
        a+=1
rows.sort(reverse=True)
print(" run     D   h(D)   form            first bad p   run/p")
for r,D,h,f,p in rows[:18]:
    print(f"{r:4}  {D:6}  {h:3}   {str(f):16} {str(p):>6}      {r/p:.2f}" if p else f"{r:4}  {D:6}  {h:3}   {str(f):16}   none")
print()
import statistics
ratios=[r/p for r,D,h,f,p in rows if p]
print(f"n={len(ratios)} forms with run>=30")
print(f"run/first_bad_prime: min={min(ratios):.2f} max={max(ratios):.2f} mean={statistics.mean(ratios):.2f}")
