import sys, time
sys.path.insert(0,'.timeloop/lib')
from kaprekar import structure, as_int, step

t0=time.time()
print("Complete Kaprekar structure (exhaustive over digit multisets => SETTLED)")
print("  b   L   #fixed   #cycles   cycle lens     the constant (if unique)")
table={}
for b in range(3,17):
    for L in range(2,7):
        from math import comb
        if comb(b+L-1,L) > 200_000: continue
        fx,cy=structure(b,L)
        table[(b,L)]=(len(fx),len(cy))
        lens=sorted(len(c) for c in cy)
        const=""
        if len(fx)==1 and not cy:
            const=f"  {as_int(fx[0],b)} (base{b})"
        elif len(fx)==1:
            const=f"  fixed={as_int(fx[0],b)}"
        print(f"{b:3} {L:3}   {len(fx):5}    {len(cy):5}    {str(lens):14}{const}")
print(f"\n[{time.time()-t0:.0f}s]")
