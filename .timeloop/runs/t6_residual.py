import sys, statistics
sys.path.insert(0,'.timeloop/lib')
from digitmaps import fixed_points
from math import gcd
from sympy import primerange, factorint

def universal_M(d):
    M=1
    for p in primerange(2,200):
        if (d-1)%(p-1)==0: M*=p
    return M

for d in (3,5):
    M=universal_M(d)
    hi=46
    rows=[]
    for b in range(2,hi):
        g=gcd(b-1,M); c=len(fixed_points(b,d))
        rows.append((b,g,c,c/g))
    groups={}
    for b,g,c,r in rows: groups.setdefault(g,[]).append(r)
    print(f"d={d}  M_d={M}   RESIDUAL c/g by congruence class")
    print("   g    #bases   mean(c/g)   stdev")
    for g in sorted(groups):
        v=groups[g]
        sd=statistics.stdev(v) if len(v)>1 else 0
        print(f"  {g:3}     {len(v):4}      {statistics.mean(v):6.2f}     {sd:5.2f}")
    allr=[r for _,_,_,r in rows]
    print(f"  overall mean residual {statistics.mean(allr):.2f}, stdev {statistics.stdev(allr):.2f}")
    print()
