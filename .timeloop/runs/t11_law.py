import sys
sys.path.insert(0,'.timeloop/lib')
from kaprekar import structure, to_digits

def constant(ms,b,L):
    """the actual Kaprekar constant: desc - asc for the fixed multiset"""
    hi=lo=0
    for x in sorted(ms,reverse=True): hi=hi*b+x
    for x in sorted(ms): lo=lo*b+x
    return hi-lo

print("L=3: does a unique Kaprekar constant exist?  (exhaustive per base => SETTLED)\n")
print("   b   parity   #fixed  #cycles   constant   digits")
ev=[];od=[]
for b in range(3,61):
    fx,cy=structure(b,3)
    has = (len(fx)==1 and len(cy)==0)
    c = constant(fx[0],b,3) if fx else None
    (ev if b%2==0 else od).append(has)
    if b<=24 or has!=( b%2==0 ):
        mark = "" if has==(b%2==0) else "   <-- BREAKS THE PATTERN"
        print(f"  {b:3}   {'even' if b%2==0 else 'odd ':4}    {len(fx):3}    {len(cy):3}     "
              f"{str(c):>8}   {tuple(sorted(fx[0],reverse=True)) if fx else ''}{mark}")
print()
print(f"even bases 3..60 with a unique constant: {sum(ev)}/{len(ev)}")
print(f"odd  bases 3..60 with a unique constant: {sum(od)}/{len(od)}")
print()
print("base-10 sanity: L=3 constant should be 495, L=4 should be 6174")
for L,exp in ((3,495),(4,6174)):
    fx,cy=structure(10,L)
    print(f"   L={L}: computed {constant(fx[0],10,L)}, expected {exp}  {'OK' if constant(fx[0],10,L)==exp else 'MISMATCH'}")
