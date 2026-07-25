import sys
sys.path.insert(0,'.timeloop/lib')
from sympy import isprime, factorint

for (a,b,c,p) in [(11,9,11,11),(7,3,7,7)]:
    print(f"form ({a},{b},{c})  first bad prime p={p}")
    print(f"   f(n) mod {p} = ", [(a*n*n+b*n+c)%p for n in range(p)])
    crit=[n for n in range(p) if (a*n*n+b*n+c)%p==0]
    print(f"   p divides f(n) exactly when n = {crit} (mod {p})")
    for n in (0,p,-p):
        v=a*n*n+b*n+c
        print(f"   f({n:3}) = {v:7}  {'= p, PRIME -> run NOT broken' if abs(v)==p else f'= {factorint(abs(v))} composite -> breaks'}")
    print()

print("CAUSE: the law assumed p | f(n) implies f(n) composite.")
print("But when f(n) = +-p exactly, the value is PRIME and the run passes through.")
print("Both violating forms have c = a, so f(0) = c = a = p is itself the bad prime.")
