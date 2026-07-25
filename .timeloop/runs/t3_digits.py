import sys, time
sys.path.insert(0,'.timeloop/lib')
from digitmaps import cycles, bound
t0=time.time()
print("  b   d   bound     #cycles  #fixedpts   cycle lengths")
data={}
for b in range(2,13):
    for d in range(2,6):
        B=bound(b,d)
        if B > 900_000: continue
        cy=cycles(b,d)
        lens=sorted(len(c) for c in cy)
        fx=sum(1 for c in cy if len(c)==1)
        data[(b,d)]=(len(cy),fx,lens)
        print(f"{b:3} {d:3} {B:8}   {len(cy):6}   {fx:6}     {lens}")
print(f"\n[{time.time()-t0:.0f}s]  SETTLED — exhaustive below bound, so these are complete.")
