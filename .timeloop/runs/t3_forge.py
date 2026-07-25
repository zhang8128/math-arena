import sys
sys.path.insert(0,'.timeloop/lib')
from digitmaps import cycles
from sympy import factorint

print("d=2, fixed points of T_{b,2} (complete, exhaustive below bound)\n")
print("  b   #fix   fixed points                       b-1 factored")
rows=[]
for b in range(2,61):
    cy=cycles(b,2)
    fx=sorted(c[0] for c in cy if len(c)==1)
    rows.append((b,fx))
    print(f"{b:3}   {len(fx):3}   {str(fx):34} {factorint(b-1)}")
