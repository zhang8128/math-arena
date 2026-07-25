import sys, time
sys.path.insert(0,'.timeloop/lib')
from digitmaps import fixed_points, cycles
from sympy import factorint

# sanity: multiset method must agree with exhaustive iteration
for b in range(2,13):
    a=sorted(c[0] for c in cycles(b,2) if len(c)==1)
    m=fixed_points(b,2)
    assert a==m, (b,a,m)
print("multiset method agrees with exhaustive iteration for d=2, b=2..12  [verified]\n")

t0=time.time()
print("d=3 fixed points (complete)")
print("  b  #fix   fixed points                             b^3-1 / b^3+1 factored")
for b in range(2,46):
    fx=fixed_points(b,3)
    f1=factorint(b**3-1); f2=factorint(b**3+1)
    print(f"{b:3}  {len(fx):3}   {str(fx[:7]):40} {dict(list(f1.items())[:3])} / {dict(list(f2.items())[:3])}")
print(f"\n[{time.time()-t0:.0f}s]")
