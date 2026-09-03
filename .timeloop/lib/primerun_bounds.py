"""Certified prime-run bounds for integer polynomials of any degree.

Background. `primeruns.py` scans quadratics and reports the longest observed run
of consecutive n with |f(n)| prime. That is a *sample*: the scan window is
arbitrary, so a longer run outside the window is never excluded. This module
supplies the missing bound, so the same question becomes a finite check.

The whole thing rests on the correction recorded in
`notebook/rabinowitsch-families.md` (T10): `p | f(n)` does NOT break a run when
|f(n)| = p, because then the value is the prime p itself.

LEMMA (break counting).  Let f in Z[x] have degree d >= 1 and let
r = #{ x in Z/p : f(x) = 0 mod p } >= 1.  Suppose |f(n)| is prime for all n in a
window W of L consecutive integers.  Every n in W with n mod p a root of f mod p
has p | f(n), hence |f(n)| = p.  The window meets each of the r root classes in
at least floor(L/p) integers, and |f(n)| = p has at most 2d integer solutions
(the roots of f - p and of f + p).  Therefore

        r * floor(L / p)  <=  2d       so      L  <  p * (floor(2d/r) + 1).

Taking p = P(f), the least prime for which f has a root mod p, gives
L < P(f) * (2d + 1).  P(f) exists for every nonconstant f (Schur 1912: the set of
prime divisors of the value set of a nonconstant integer polynomial is infinite).

LOCALIZATION.  The lemma bounds a run's length but not its position: a run of
length <= P(f) - 1 can sit in any gap between consecutive root-class points, and
those gaps run off to infinity.  But a run of length L >= P(f) meets every
residue class mod P(f), so it CONTAINS a point n* with |f(n*)| = P(f).  There are
at most 2d such n*, and Cauchy's bound puts all of them in an explicit interval.
So the run lies within distance P(f)*(2d+1) of an explicitly computable finite
set.  Hence:

  * "is there a run of length >= P(f)?" is DECIDABLE by a finite scan, and
  * when the answer is yes, the scan returns the exact global maximum run over Z.

That is the only regime worth searching anyway, since the interesting quantity is
the ratio rho(f) = maxrun(f) / P(f) and the lemma caps it at 2d + 1.
"""

from sympy import isprime, nextprime

__all__ = [
    "poly_eval",
    "roots_mod_p",
    "least_root_prime",
    "run_bound",
    "cauchy_bound",
    "value_equals_prime_points",
    "certified_max_run",
    "audit_all_primes",
]


def poly_eval(coeffs: tuple[int, ...], n: int) -> int:
    """Evaluate f(n) for coeffs given HIGHEST degree first (Horner)."""
    v = 0
    for c in coeffs:
        v = v * n + c
    return v


def degree(coeffs: tuple[int, ...]) -> int:
    return len(coeffs) - 1


def roots_mod_p(coeffs: tuple[int, ...], p: int) -> list[int]:
    return [x for x in range(p) if poly_eval(coeffs, x) % p == 0]


def least_root_prime(coeffs: tuple[int, ...], cap: int = 1000) -> int | None:
    """Least prime p such that f has a root mod p, or None if none is <= cap."""
    p = 2
    while p <= cap:
        if roots_mod_p(coeffs, p):
            return p
        p = nextprime(p)
    return None


def run_bound(d: int, r: int, p: int) -> int:
    """Largest L not excluded by the break-counting lemma: L < p*(floor(2d/r)+1)."""
    return p * (2 * d // r + 1) - 1


def cauchy_bound(coeffs: tuple[int, ...]) -> int:
    """Every integer root n of the polynomial satisfies |n| <= this."""
    lead = abs(coeffs[0])
    rest = max((abs(c) for c in coeffs[1:]), default=0)
    return 1 + (rest + lead - 1) // lead  # ceil(rest/lead) + 1, an integer upper bound


def value_equals_prime_points(coeffs: tuple[int, ...], p: int) -> list[int]:
    """All integers n with |f(n)| = p.  Complete: uses Cauchy's root bound."""
    out = []
    for sign in (-p, p):
        shifted = list(coeffs)
        shifted[-1] -= sign  # roots of f(n) - sign
        b = cauchy_bound(tuple(shifted))
        for n in range(-b, b + 1):
            if poly_eval(coeffs, n) == sign:
                out.append(n)
    return sorted(set(out))


def _scan_max_run(coeffs: tuple[int, ...], lo: int, hi: int) -> tuple[int, int | None]:
    """Longest run of consecutive n in [lo, hi] with |f(n)| prime; and its start."""
    best, best_start = 0, None
    cur, cur_start = 0, lo
    for n in range(lo, hi + 1):
        v = abs(poly_eval(coeffs, n))
        if v > 1 and isprime(v):
            if cur == 0:
                cur_start = n
            cur += 1
            if cur > best:
                best, best_start = cur, cur_start
        else:
            cur = 0
    return best, best_start


def certified_max_run(coeffs: tuple[int, ...], prime_cap: int = 1000) -> dict:
    """Decide the >= P regime exactly.

    Returns a dict with:
      p            least prime with a root mod p (None if > prime_cap)
      r            number of root classes mod p
      bound        L < bound+1 by the lemma
      anchors      the complete set of n with |f(n)| = p
      max_run      exact global max run over Z when it is >= p; otherwise the best
                   found inside the certified window
      certified    True iff max_run >= p, i.e. the value is the true maximum over Z
      ratio        max_run / p
    """
    d = degree(coeffs)
    p = least_root_prime(coeffs, prime_cap)
    if p is None:
        return {"p": None, "certified": False, "reason": f"no root prime <= {prime_cap}"}
    r = len(roots_mod_p(coeffs, p))
    bound = run_bound(d, r, p)
    anchors = value_equals_prime_points(coeffs, p)
    if not anchors:
        # No n has |f(n)| = p, so no run may contain a root-class point at all:
        # every run has length <= p - 1.  Nothing of ratio >= 1 exists.
        return {
            "p": p, "r": r, "bound": bound, "anchors": [], "max_run": None,
            "certified": True, "certified_claim": "max_run <= p-1", "ratio": None,
        }
    reach = bound
    lo, hi = min(anchors) - reach, max(anchors) + reach
    best, start = _scan_max_run(coeffs, lo, hi)
    return {
        "p": p, "r": r, "bound": bound, "anchors": anchors,
        "max_run": best, "start": start, "window": (lo, hi),
        "certified": best >= p,
        "certified_claim": ("global max over Z" if best >= p else "max_run <= p-1"),
        "ratio": best / p,
    }


def audit_all_primes(coeffs: tuple[int, ...], lo: int, hi: int, prime_cap: int = 200) -> list[dict]:
    """Check the lemma against every prime <= prime_cap for the observed run.

    Returns the list of violations (empty list = lemma held on this instance).
    Used as a live consistency test of the counting argument, not as a proof.
    """
    d = degree(coeffs)
    best, start = _scan_max_run(coeffs, lo, hi)
    bad = []
    p = 2
    while p <= prime_cap:
        rs = roots_mod_p(coeffs, p)
        if rs and best > run_bound(d, len(rs), p):
            bad.append({"p": p, "r": len(rs), "run": best, "bound": run_bound(d, len(rs), p)})
        p = nextprime(p)
    return bad


# ---------------------------------------------------------------------------
# T29 refinement: the sharp form of the counting lemma.
#
# The lemma above throws away where the window sits.  Sharpen it:
#
#   Let W = [N, N+L) and write L = qp + s, 0 <= s < p.  Residue class c mod p
#   meets W in q+1 integers when c is one of the s consecutive classes
#   N, N+1, ..., N+s-1 (mod p), and in q integers otherwise.  Let R be the set of
#   root classes (|R| = r) and let
#
#       A = #{ n in Z : |f(n)| = p }            (computed exactly, A <= 2d)
#
#   Every root-class integer in W must be one of those A anchors, and distinct
#   integers are distinct anchors, so
#
#       #(root-class integers in W)  <=  A.
#
#   That count depends only on (N mod p, L), so maximising L over the p possible
#   window offsets is a finite computation.  Minimising over all primes p with
#   r >= 1 gives the bound.  It is strictly sharper than run_bound: for the Euler
#   polynomial, run_bound gives 122 while this gives 80, the exact run.
# ---------------------------------------------------------------------------

__all__ += ["sharp_run_bound_at_p", "sharp_run_bound", "anchor_data"]


def _root_class_count(p: int, roots: frozenset, offset: int, L: int) -> int:
    """#{ n in [offset, offset+L) : n mod p in roots }, offset taken mod p."""
    q, s = divmod(L, p)
    total = q * len(roots)
    for k in range(s):
        if (offset + k) % p in roots:
            total += 1
    return total


def sharp_run_bound_at_p(p: int, roots, A: int) -> int:
    """Largest L not excluded at this prime, over all window offsets.

    Incremental: extending the window by one integer adds a root-class point iff
    the new residue is a root, so each offset costs O(L) rather than O(L*p).
    """
    roots = frozenset(roots)
    if not roots:
        return None  # p imposes no constraint
    best = 0
    limit = (A + 2) * p
    for offset in range(p):
        count = 0
        L = 0
        while L < limit:
            if (offset + L) % p in roots:
                if count + 1 > A:
                    break
                count += 1
            L += 1
        best = max(best, L)
    return best


def anchor_data(coeffs: tuple[int, ...], p: int) -> tuple[list[int], int]:
    roots = roots_mod_p(coeffs, p)
    anchors = value_equals_prime_points(coeffs, p)
    return roots, len(anchors)


def sharp_run_bound(coeffs: tuple[int, ...], prime_cap: int = 60) -> dict:
    """min over primes p <= prime_cap (with a root mod p) of the sharp bound."""
    best = None
    witness = None
    p = 2
    while p <= prime_cap:
        roots = roots_mod_p(coeffs, p)
        if roots:
            A = len(value_equals_prime_points(coeffs, p))
            b = sharp_run_bound_at_p(p, roots, A)
            if best is None or b < best:
                best, witness = b, {"p": p, "r": len(roots), "A": A}
        p = nextprime(p)
    return {"bound": best, "witness": witness}
