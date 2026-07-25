import sys
sys.path.insert(0,'.timeloop/lib')
from digitmaps import fixed_points

# CLAIM: for d>=3 and k>=2, base b = k^(d-1) has fixed points exactly k^d and k^d+1
# arising from the two-digit representations (k,0) and (k,1).
# Proof sketch: n = k*b + m has digits (k,m) provided k<b; sum of d-th powers is
# k^d + m^d; fixed <=> k*b + m = k^d + m^d.  With b = k^(d-1), k*b = k^d, so the
# condition collapses to m^d = m, i.e. m in {0,1} for a nonneg digit.
print("verifying construction b = k^(d-1) -> fixed points k^d, k^d+1\n")
print("  d   k     b       predicted        present in complete set?")
ok=True
for d in (3,4,5):
    for k in (2,3,4,5,6):
        b=k**(d-1)
        if b>60 or b<=k: continue
        fx=set(fixed_points(b,d))
        pred={k**d, k**d+1}
        good=pred<=fx
        ok &= good
        print(f"{d:3} {k:3} {b:6}   {sorted(pred)!s:16}   {good}")
print(f"\nconstruction holds in every checked case: {ok}")

# and confirm m in {0,1} is exhaustive: no other two-digit (k,m) fixed point at b=k^(d-1)
print("\nchecking no OTHER two-digit fixed point of form (k,m) exists at b=k^(d-1):")
for d in (3,4):
    for k in (2,3,4):
        b=k**(d-1)
        if b<=k: continue
        extra=[m for m in range(b) if k*b+m == k**d + m**d and m not in (0,1)]
        print(f"  d={d} k={k} b={b}: extra m values = {extra}")
