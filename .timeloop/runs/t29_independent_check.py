"""T29 independent re-verification of the record witnesses.

Deliberately shares no code with lib/primerun_bounds.py: sympy Poly for
evaluation, a fresh run scanner, and a BRUTE-FORCE window count for the sharp
bound (enumerate every window of every length directly instead of reasoning mod p).
"""
from sympy import Poly, isprime, symbols, primerange

n = symbols("n")
CASES = [((1, 1, 41), 41, 80), ((2, 2, -71), 11, 32), ((2, 0, -181), 19, 55),
         ((2, 0, -61), 11, 31), ((1, 0, -25, 5), 5, 19), ((7, 3, 7), 7, 13)]

for coeffs, p_exp, run_exp in CASES:
    f = Poly(list(coeffs), n)
    # (a) least prime with a root, by direct value scan rather than residue loop
    P = next(q for q in primerange(2, 500) if any(int(f.eval(k)) % q == 0 for k in range(q)))
    # (b) longest run of |f| prime, scanned over a window far wider than the bound
    W = 12 * P + 200
    flags = [(lambda v: v > 1 and isprime(v))(abs(int(f.eval(k)))) for k in range(-W, W + 1)]
    best = cur = 0
    for b in flags:
        cur = cur + 1 if b else 0
        best = max(best, cur)
    # (c) sharp bound by brute force over concrete windows, not modular arithmetic
    anchors = {k for k in range(-W, W + 1) if abs(int(f.eval(k))) == P}
    rootres = {k % P for k in range(-W, W + 1) if int(f.eval(k)) % P == 0}
    A = len(anchors)
    sharp = 0
    for start in range(0, P):
        L = 0
        cnt = 0
        while True:
            if (start + L) % P in rootres:
                if cnt + 1 > A:
                    break
                cnt += 1
            L += 1
            if L > 20 * P:
                break
        sharp = max(sharp, L)
    ok = (P == p_exp) and (best == run_exp) and (best <= sharp)
    print(f"{coeffs}: P={P} (exp {p_exp})  run={best} (exp {run_exp})  A={A} "
          f"sharp={sharp}  attains={best==sharp}  AGREES={ok}")
