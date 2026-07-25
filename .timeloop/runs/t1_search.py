import sys, time
sys.path.insert(0, '.timeloop/lib')
from primeruns import run_length, discriminant, fundamental_part, HEEGNER
from math import gcd

t0=time.time()
best = []
A, B, C = 6, 90, 2000   # a in 1..A, b in -B..B, c in 1..C
for a in range(1, A+1):
    for b in range(-B, B+1):
        for c in range(2, C+1):
            if gcd(gcd(a,b),c) != 1:      # primitive forms only
                continue
            if not (c > 1):
                continue
            r = run_length(a,b,c, cap=200)
            if r >= 20:
                best.append((r,a,b,c))
best.sort(reverse=True)
print(f"search time {time.time()-t0:.1f}s, {len(best)} families with run>=20")
print()
print(" run   a    b     c      disc      d0     f   d0 in H1?")
seen=set()
for r,a,b,c in best[:30]:
    d = discriminant(a,b,c)
    d0,f = fundamental_part(d)
    print(f"{r:4}  {a:2}  {b:4}  {c:5}   {d:8}  {d0:6}  {f:3}   {d0 in HEEGNER}")
