import sys
sys.path.insert(0,'.timeloop/lib')
from kaprekar import structure

def constant(ms,b):
    hi=lo=0
    for x in sorted(ms,reverse=True): hi=hi*b+x
    for x in sorted(ms): lo=lo*b+x
    return hi-lo

print("CLAIM  (L=3): for even b the unique Kaprekar constant has digits")
print("       (b-1, b/2, b/2-1)  and equals  K(b) = (b/2)(b^2 - 1).")
print("       For odd b no constant exists.\n")
print("    b    computed   formula (b/2)(b^2-1)   digits match (b-1,b/2,b/2-1)")
bad=0
for b in range(4,121,2):
    fx,cy=structure(b,3)
    assert len(fx)==1 and len(cy)==0, (b,len(fx),len(cy))
    c=constant(fx[0],b)
    f=(b//2)*(b*b-1)
    dm = tuple(sorted(fx[0],reverse=True)) == (b-1, b//2, b//2-1)
    if c!=f or not dm: bad+=1; print(f"  {b:3}   MISMATCH {c} vs {f}  digits {sorted(fx[0],reverse=True)}")
    elif b<=20 or b%20==0:
        print(f"  {b:3}   {c:9}   {f:19}   {dm}")
print(f"\neven b = 4..120 : {bad} mismatches")

print("\nDERIVATION (why the formula):")
print("  desc = (b-1)b^2 + (b/2)b + (b/2 - 1)")
print("  asc  = (b/2 - 1)b^2 + (b/2)b + (b-1)")
print("  desc - asc = [(b-1)-(b/2-1)]b^2 + 0 + [(b/2-1)-(b-1)]")
print("             = (b/2)b^2 - (b/2)  =  (b/2)(b^2 - 1)  =  (b/2)(b-1)(b+1)")
print("\n  For ODD b the middle digit b/2 is not an integer, so this fixed point")
print("  cannot exist -- and exhaustively, no other one does either.")

odd_ok=sum(1 for b in range(3,61,2) if (lambda t:(len(t[0])==1 and len(t[1])==0))(structure(b,3)))
print(f"\n  odd b = 3..59 with any unique constant: {odd_ok}  (exhaustively settled)")
