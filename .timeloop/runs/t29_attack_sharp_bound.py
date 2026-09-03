"""T29 attack: the sharp anchor bound, and whether records attain it.

Conjecture forged from the T29 pilot data (all seven record polynomials met it
with equality, including n^2+n+41 at exactly 80):

    C1  maxrun(f) <= sharpbound(f)              -- a THEOREM (counting lemma)
    C2  every prime-run record attains it        -- the thing to attack

C1 is checked here as a consistency test on the code, not as evidence.
C2 is attacked: measure the attainment rate across whole boxes and, in
particular, whether polynomials with the LARGEST ratio maxrun/P attain it.
"""

import sys
from math import gcd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from primerun_bounds import (  # noqa: E402
    certified_max_run, roots_mod_p, sharp_run_bound_at_p, value_equals_prime_points,
)
from t29_forge_ratio_scan import cubics, quadratics  # noqa: E402


def attack(family, label):
    tot = viol = attained = short = 0
    worst = []          # largest shortfall (bound - run) among certified cases
    best_ratio = []
    for coeffs in family:
        res = certified_max_run(coeffs, prime_cap=300)
        if not res.get("certified") or res.get("max_run") is None:
            continue
        p = res["p"]
        R = roots_mod_p(coeffs, p)
        A = len(value_equals_prime_points(coeffs, p))
        sb = sharp_run_bound_at_p(p, R, A)
        run = res["max_run"]
        tot += 1
        if run > sb:
            viol += 1
            print(f"  !! VIOLATION {coeffs}: run={run} > sharp={sb} (p={p},r={len(R)},A={A})")
        elif run == sb:
            attained += 1
        else:
            short += 1
            worst.append((sb - run, run, sb, p, len(R), A, coeffs))
        best_ratio.append((run / p, run, sb, p, len(R), A, coeffs))
    worst.sort(reverse=True)
    best_ratio.sort(reverse=True)
    print(f"\n=== {label} ===")
    print(f"  certified polynomials: {tot}")
    print(f"  C1 violations (must be 0, it is a theorem): {viol}")
    print(f"  attain the sharp bound: {attained} ({100*attained/max(tot,1):.1f}%)")
    print(f"  fall short:             {short}")
    print("  --- top 10 by ratio maxrun/P, with attainment ---")
    for ratio, run, sb, p, r, A, c in best_ratio[:10]:
        tag = "ATTAINS" if run == sb else f"short by {sb-run}"
        print(f"    rho={ratio:6.3f} run={run:4d} sharp={sb:4d} p={p:4d} r={r} A={A}  {c}  [{tag}]")
    print("  --- worst shortfalls (C2 counterexamples if any are records) ---")
    for gapv, run, sb, p, r, A, c in worst[:6]:
        print(f"    run={run:4d} sharp={sb:4d} gap={gapv:4d} p={p:4d} r={r} A={A}  {c}")
    return best_ratio


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "quad"
    if which == "quad":
        attack(quadratics(8, 1200), "quadratics a<=8, |c|<=1200")
    elif which == "cubic":
        attack(cubics((0, 1, 2), 40, 300), "monic cubics b in 0..2, |c|<=40, |d|<=300")
    elif which == "family":
        # The cubic mechanism found by the box scan: f_p(n) = n^3 - p^2 n + p has
        # f(0) = f(p) = f(-p) = p, three anchors in one root class mod p.
        from sympy import primerange
        print("=== f_p(n) = n^3 - p^2 n + p : anchor-chain family ===")
        for q in primerange(2, 60):
            coeffs = (1, 0, -q * q, q)
            res = certified_max_run(coeffs, prime_cap=300)
            R = roots_mod_p(coeffs, res["p"]); A = len(value_equals_prime_points(coeffs, res["p"]))
            sb = sharp_run_bound_at_p(res["p"], R, A)
            run = res.get("max_run")
            if run is None:
                # P(f) != p and no value equals P(f): the lemma forces run <= P(f)-1.
                print(f"  p={q:3d}  P(f)={res['p']:3d}  r={len(R)}  A=0   "
                      f"anchor chain BROKEN by a smaller prime; run <= {res['p']-1}")
                continue
            print(f"  p={q:3d}  P(f)={res['p']:3d}  r={len(R)}  A={A}  "
                  f"run={run:4d}  sharp={sb:4d}  "
                  f"{'ATTAINS' if run==sb else 'short'}  rho={run/res['p']:.3f}")
