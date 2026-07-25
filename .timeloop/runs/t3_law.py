import sys
sys.path.insert(0,'.timeloop/lib')
from digitmaps import cycles
from sympy import factorint
from math import isqrt

def predicted(b):
    """Fixed points of T_{b,2} predicted from reps of b^2+1 = u^2+v^2."""
    N=b*b+1; out=set()
    for u in range(-b, b+1):
        r=N-u*u
        if r<0: continue
        v=isqrt(r)
        if v*v!=r or v%2==0 or v<0: continue
        if (u+b)%2: continue
        a=(u+b)//2; c=(v+1)//2
        if 1<=a<=b-1 and 0<=c<=b-1:
            out.add(a*b+c)
    out.add(1)
    return sorted(out)

bad=0
for b in range(2,121):
    actual=sorted(c[0] for c in cycles(b,2) if len(c)==1)
    pred=predicted(b)
    if actual!=pred:
        bad+=1
        if bad<=6:
            print(f"MISMATCH b={b}: actual={actual}\n            pred  ={pred}")
print(f"\nb=2..120 : {'ALL MATCH — law validated' if bad==0 else f'{bad} mismatches'}")
print()
print("Out-of-sample prediction check (b^2+1 factorisation drives the count):")
print("  b     b^2+1 factored                #fix   primes=1 mod 4")
for b in (47,57,43,97,107,110,117):
    f=factorint(b*b+1)
    p1=sum(e for p,e in f.items() if p%4==1)
    print(f"{b:4}   {str(f):32}  {len(predicted(b)):4}      {p1}")
