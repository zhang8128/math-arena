import sys
sys.path.insert(0,'.timeloop/lib')
from primeruns import class_number
from sympy import primerange, isprime

def reduced_forms(D):
    out=[]; a=1
    while 3*a*a <= -D:
        for b in range(-a+1,a+1):
            num=b*b-D
            if num%(4*a): continue
            c=num//(4*a)
            if c<a: continue
            if (a==c or abs(b)==a) and b<0: continue
            out.append((a,b,c))
        a+=1
    return out

def represents(f,p,B=60):
    a,b,c=f
    for x in range(-B,B+1):
        for y in range(-B,B+1):
            if a*x*x+b*x*y+c*y*y==p: return True
    return False

# HYPOTHESIS: a long-run form avoids representing the SMALL primes;
# when h>1 those primes are absorbed by OTHER classes of the same discriminant.
cases=[(-163,(1,1,41),80),(-708,(6,6,31),58),(-232,(2,0,29),57),
       (-267,(3,3,23),44),(-652,(4,-2,41),40),(-760,(10,0,19),37)]
for D,f,run in cases:
    h=class_number(D); forms=reduced_forms(D)
    small=[p for p in primerange(2,32)]
    by_f=[p for p in small if represents(f,p)]
    by_other=[p for p in small if any(represents(g,p) for g in forms if g!=f)]
    print(f"D={D:6} h={h}  form={f}  run={run}")
    print(f"    small primes represented BY this form : {by_f}")
    print(f"    represented by SOME OTHER class       : {by_other}")
    print(f"    #classes={len(forms)}")
    print()
