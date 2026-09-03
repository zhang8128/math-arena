"""T28 (forage turn) — validation of the MECHANISMS behind the frames filed for
`brocard`.  This is NOT a search of the target; every range here is tiny and
chosen only to check that a filed method does what its source says it does.

Checks:
  (1) sanity: the three known Brown pairs.
  (2) vacuity floor: for p <= n the test "is n!+1 a QR mod p" is identically
      +1, so no fixed modulus can reject any tail.  (frame: sieve-above-the-vacuity-floor)
  (3) Matson battery replay at toy scale: 40 test primes > 10^4, n <= 5000,
      survivor counts vs the N*2^-k prediction.  (frame: size-the-filter-battery)
  (4) Dabrowski mechanism for n!+A: least prime p with (A|p) = -1 bounds n,
      and A=1 has no such prime.  (frame: nonsquare-shift-obstruction)
"""
from math import isqrt
from sympy import nextprime, jacobi_symbol

def is_square(x):
    r = isqrt(x)
    return r * r == x

print("=== (1) known Brown pairs ===")
for n in (4, 5, 7):
    f = 1
    for i in range(2, n + 1):
        f *= i
    print(f"  n={n}: n!+1={f+1}, square={is_square(f+1)}, m={isqrt(f+1)}")

print("=== (2) vacuity floor: p <= n forces n!+1 = 1 mod p ===")
bad = 0
checked = 0
p = 3                                 # jacobi_symbol needs an odd modulus
while p <= 100:
    f = 1
    for n in range(2, 201):
        f = (f * n) % p
        if n >= p:
            checked += 1
            if (f + 1) % p != 1 or jacobi_symbol((f + 1) % p, p) != 1:
                bad += 1
    p = nextprime(p)
print(f"  (p,n) pairs with p odd prime <= 100, p <= n <= 200: {checked} checked, "
      f"{bad} where n!+1 mod p != 1 or is a non-residue")

print("=== (3) Matson battery replay: 40 primes > 10^4, n = 8..5000 ===")
primes = []
q = nextprime(10**4)
while len(primes) < 40:
    primes.append(q)
    q = nextprime(q)
fact = [1] * 40                      # running n! mod p_i
N0, N1 = 8, 5000
passed_hist = {}
for n in range(2, N1 + 1):
    for i, p in enumerate(primes):
        fact[i] = (fact[i] * n) % p
    if n < N0:
        continue
    k = 0
    for i, p in enumerate(primes):    # short-circuit on first -1
        if jacobi_symbol((fact[i] + 1) % p, p) == -1:
            break
        k += 1
    passed_hist[k] = passed_hist.get(k, 0) + 1
N = N1 - N0 + 1
print(f"  n in [{N0},{N1}] ({N} values); max tests passed = {max(passed_hist)}")
print("   k   #(exactly k)   #(>=k)   predicted N*2^-k")
cum = 0
for k in sorted(passed_hist, reverse=True):
    cum += passed_hist[k]
    print(f"  {k:2d}  {passed_hist[k]:8d}   {cum:8d}   {N * 2.0**-k:14.2f}")

print("  known solutions must pass all 40 (n!+1 is a genuine square):")
for n in (4, 5, 7):
    f = 1
    for i in range(2, n + 1):
        f *= i
    k = sum(1 for p in primes if jacobi_symbol((f + 1) % p, p) != -1)
    print(f"    n={n}: passes {k}/40")

print("=== (4) Dabrowski mechanism for n!+A = m^2, A non-square ===")
worst = (0, 0)
for A in range(2, 201):
    if is_square(A):
        continue
    p = 3
    while jacobi_symbol(A % p, p) != -1:
        p = nextprime(p)
    if p > worst[1]:
        worst = (A, p)
    # every n >= p has n!+A = A (mod p), a non-residue -> no solution
    f = 1
    for i in range(2, p + 1):
        f *= i
    assert not is_square(f + A), (A, p)
print(f"  all non-square A in [2,200]: least prime p with (A|p)=-1 exists; "
      f"worst case A={worst[0]} needs p={worst[1]}, so n < {worst[1]}")
none_found = all(jacobi_symbol(1 % p, p) == 1
                 for p in [nextprime(x) for x in range(2, 2000, 7)])
print(f"  A=1 degeneracy: (1|p)=+1 for every prime tested -> no such p exists: {none_found}")
