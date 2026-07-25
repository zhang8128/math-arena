import sys, time
sys.path.insert(0,'.timeloop/lib')
from persistence import best_persistence, smallest_with_multiset, persistence

# sanity: base 10 record is 11, at 277777788888899
n=277777788888899
print(f"sanity: persistence({n}, 10) = {persistence(n,10)}  (known record 11)\n")

t0=time.time()
print("max multiplicative persistence found, by base")
print("   b   maxlen   best persistence   witness digits          smallest witness")
for b in range(3,17):
    ml = 16 if b<=10 else (12 if b<=13 else 10)
    p,ms = best_persistence(b, ml)
    w = smallest_with_multiset(ms,b) if ms else None
    print(f"  {b:3}   {ml:4}      {p:6}           {str(ms):22} {w}")
print(f"\n[{time.time()-t0:.0f}s]  (search bounded by max digit-length shown)")
