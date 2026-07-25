# INDEPENDENT verification -- deliberately does not import lib/persistence.py
def digits_b(n, b):
    d=[]
    while n: d.append(n%b); n//=b
    return d[::-1]

def chain(n, b):
    out=[n]
    while n >= b:
        p=1
        for d in digits_b(n,b): p*=d
        n=p; out.append(n)
    return out

for n,b,claim in [(277777788888899,10,11), (494196864368,13,12)]:
    c=chain(n,b)
    print(f"base {b}, n = {n}")
    for i,v in enumerate(c):
        print(f"   step {i:2}: {v:>18}   digits {digits_b(v,b)}")
    print(f"   persistence = {len(c)-1}   (claimed {claim})  "
          f"{'VERIFIED' if len(c)-1==claim else 'MISMATCH'}\n")
