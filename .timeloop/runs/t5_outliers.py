import sys
sys.path.insert(0,'.timeloop/lib')
from digitmaps import fixed_points
from sympy import factorint

def dlen(n,b):
    k=0
    while n: k+=1; n//=b
    return k

print("Where do the outlier fixed points live? (digit-length breakdown, d=3)\n")
print("  b  #fix   by digit length {len: count}      b factored")
for b in list(range(2,46)):
    fx=fixed_points(b,3)
    dist={}
    for n in fx: dist[dlen(n,b)]=dist.get(dlen(n,b),0)+1
    tag=""
    if len(fx)>=10: tag="  <-- OUTLIER"
    print(f"{b:3}  {len(fx):3}   {str(dist):30} {factorint(b)}{tag}")
