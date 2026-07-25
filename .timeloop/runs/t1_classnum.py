import sys, time
sys.path.insert(0,'.timeloop/lib')
from primeruns import class_number, max_consecutive_run
t0=time.time()
rows=[]
for D in range(-1000, 0):
    if D % 4 not in (0,1): continue
    h = class_number(D)
    # enumerate reduced forms of discriminant D, take best centered run
    best=0; arg=None
    a=1
    while 3*a*a <= -D:
        for b in range(-a+1, a+1):
            num=b*b-D
            if num % (4*a): continue
            c=num//(4*a)
            if c<a: continue
            if (a==c or abs(b)==a) and b<0: continue
            r=max_consecutive_run(a,b,c,window=120)
            if r>best: best, arg = r,(a,b,c)
        a+=1
    rows.append((best,D,h,arg))
rows.sort(reverse=True)
print(f"{time.time()-t0:.1f}s\n")
print(" run     D    h(D)   best form (a,b,c)")
for r,D,h,arg in rows[:22]:
    print(f"{r:4}  {D:6}   {h:2}    {arg}")
