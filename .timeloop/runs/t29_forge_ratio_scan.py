"""T29 forge probe: how large can maxrun(f)/P(f) get?

P(f) = least prime with a root of f mod p.  The break-counting lemma in
lib/primerun_bounds.py gives maxrun(f) < P(f)*(floor(2d/r)+1), so the ratio
rho(f) = maxrun(f)/P(f) is capped by 2d+1 (r=1 worst case).  All observed
quadratic records sit near 2 (Euler: 80/41).  This probe measures the true
maximum of rho over explicit boxes so that a sharp conjecture can be forged and
then attacked.

Every reported maxrun is CERTIFIED: when maxrun >= P(f) it is the exact global
maximum over all of Z, by the localization argument in the library docstring.
"""

import json
import sys
import time
from math import gcd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from primerun_bounds import audit_all_primes, certified_max_run, run_bound  # noqa: E402

PRIME_CAP = 300


def scan(family, label, audit_every=0):
    t0 = time.time()
    best = []
    n_poly = n_cert = n_uncert = 0
    violations = []
    for i, coeffs in enumerate(family):
        n_poly += 1
        res = certified_max_run(coeffs, prime_cap=PRIME_CAP)
        if res.get("p") is None:
            n_uncert += 1
            continue
        if res.get("ratio") is None:
            continue
        if res["certified"]:
            n_cert += 1
            best.append((res["ratio"], res["max_run"], res["p"], res["r"], coeffs))
        if audit_every and i % audit_every == 0:
            lo, hi = res.get("window", (-50, 50))
            violations += audit_all_primes(coeffs, lo, hi, prime_cap=100)
    best.sort(reverse=True)
    dt = time.time() - t0
    print(f"\n=== {label} ===")
    print(f"  polynomials: {n_poly}   certified (maxrun >= P): {n_cert}"
          f"   no root prime <= {PRIME_CAP}: {n_uncert}   [{dt:.1f}s]")
    print(f"  lemma audit violations: {len(violations)}")
    print(f"  top 12 by ratio rho = maxrun/P:")
    for ratio, run, p, r, coeffs in best[:12]:
        print(f"    rho={ratio:6.3f}  run={run:4d}  P={p:4d}  r={r}  "
              f"bound={run_bound(len(coeffs)-1, r, p):4d}  f={coeffs}")
    return best, violations


def quadratics(amax, cmax):
    for a in range(1, amax + 1):
        for b in range(0, a + 1):          # translation: b mod 2a; reflection: b -> -b
            for c in range(-cmax, cmax + 1):
                if gcd(gcd(a, b), c) != 1:  # imprimitive: scales the whole value set
                    continue
                yield (a, b, c)


def cubics(bset, cmax, dmax):
    for b in bset:                          # translation on monic cubic: b mod 3
        for c in range(-cmax, cmax + 1):
            for d in range(-dmax, dmax + 1):
                yield (1, b, c, d)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "pilot"
    if which == "pilot":
        qb, qv = scan(quadratics(4, 200), "quadratics a<=4, |c|<=200 (pilot)", audit_every=97)
    elif which == "quad":
        qb, qv = scan(quadratics(8, 1200), "quadratics a<=8, |c|<=1200", audit_every=997)
        Path(".timeloop/runs/t29_quad_top.json").write_text(
            json.dumps([[r, run, p, rr, list(c)] for r, run, p, rr, c in qb[:60]], indent=1))
    elif which == "cubic":
        cb, cv = scan(cubics((0, 1, 2), 40, 300), "monic cubics b in 0..2, |c|<=40, |d|<=300",
                      audit_every=997)
        Path(".timeloop/runs/t29_cubic_top.json").write_text(
            json.dumps([[r, run, p, rr, list(c)] for r, run, p, rr, c in cb[:60]], indent=1))
