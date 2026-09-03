#!/usr/bin/env python3
"""T27 -- independent check of the bit-length RH machine (.timeloop/runs/t27_riemann_bitlen.nql).

Two things must hold for the variant to be a valid RH machine:

  (A) Its halt predicate really is  (H_L - x)^2 > x * k^4,  L = lcm(1..x),
      k = bit-length of x.  Checked by re-executing the NQL statement list
      under exact integer semantics (monus, floor division) and comparing
      against the closed form -- and against the ORIGINAL machine's predicate
      (H_L - x)^2 > x * H_x^4 -- for every x in a stated range.

  (B) k >= H_x for every x > 253, so the variant is strictly harder to trip
      than the original and inherits its soundness (RH => never halts) with
      the same x > 253 guard.  Proved analytically; range-checked here.

Range is deliberately small because L = lcm(1..x) is the loop bound: the
machine's own H_L loop runs L times, so x <= 12 (L = 27720) is what fits.
That is enough -- the check is of the ALGEBRA, which does not depend on x.
"""
from fractions import Fraction
from math import gcd, log, log2


def nql_exec(x, use_bitlen):
    """Execute the machine body for one value of x under NQL semantics.

    '-' is monus (clamped at 0), '/' is floor division, all values are
    non-negative integers.  Returns the boolean the final `if` evaluates.
    """
    def monus(p, q):
        return p - q if p > q else 0

    L = 1
    for j in range(1, x + 1):
        L = L * j // gcd(L, j)

    num, denom, i = 0, 1, 1
    while i <= L:
        num = num * i + denom
        denom = denom * i
        i += 1

    a = monus(num, denom * x)
    a = a * a

    if use_bitlen:
        c = 0
        i = x
        while i != 0:
            i = i // 2
            c = c + 1
        c = c * c
        c = c * c * x
        return a > denom * denom * c
    else:
        b = denom * denom
        c, d, i = 0, 1, 1
        while i <= x:
            c = c * i + d
            d = d * i
            i += 1
        c = c * c
        c = c * c * x
        d = d * d
        d = d * d
        return a * d > b * c


def closed_form(x, use_bitlen):
    """The inequality each machine is SUPPOSED to be testing."""
    L = 1
    for j in range(1, x + 1):
        L = L * j // gcd(L, j)
    HL = sum(Fraction(1, j) for j in range(1, L + 1))
    lhs = max(Fraction(0), HL - x) ** 2
    if use_bitlen:
        k = x.bit_length()
        return lhs > x * Fraction(k) ** 4
    Hx = sum(Fraction(1, j) for j in range(1, x + 1))
    return lhs > x * Hx ** 4


def main():
    print("(A) statement-level execution vs closed form, x = 1..12")
    print("%4s %10s %8s %8s %8s %8s %8s" %
          ("x", "lcm(1..x)", "orig", "orig_cf", "bitlen", "bit_cf", "ok"))
    all_ok = True
    for x in range(1, 13):
        L = 1
        for j in range(1, x + 1):
            L = L * j // gcd(L, j)
        o, ocf = nql_exec(x, False), closed_form(x, False)
        b, bcf = nql_exec(x, True), closed_form(x, True)
        ok = (o == ocf) and (b == bcf) and (not b or o)   # bitlen halts => orig halts
        all_ok &= ok
        print("%4d %10d %8s %8s %8s %8s %8s" % (x, L, o, ocf, b, bcf, "OK" if ok else "MISMATCH"))
    print("(A) all match, and bitlen-halt implies orig-halt:", all_ok)
    print()

    print("(B) k = bit_length(x) >= H_x ?")
    Hx = 0.0
    worst = None
    bad = []
    for x in range(1, 10 ** 7 + 1):
        Hx += 1.0 / x
        k = x.bit_length()
        if x >= 4 and k < Hx:
            bad.append(x)
            if len(bad) > 5:
                break
        if x >= 4:
            m = k - Hx
            if worst is None or m < worst[1]:
                worst = (x, m)
    print("    failures for 4 <= x <= 10^7:", bad if bad else "none")
    print("    tightest margin k - H_x at x = %d: %.6f" % worst)
    print("    analytic: k > log2 x = log x / log 2 and H_x <= log x + gamma + 1/(2x),")
    thresh = int(__import__('math').exp((0.5772156649 + 0.125) / (1 / log(2) - 1))) + 1
    print("    so k > H_x whenever log x * (1/log 2 - 1) >= gamma + 1/8, i.e. x >= %d." % thresh)
    print()
    print("CONSEQUENCE: threshold_bitlen = sqrt(x)*k^2 >= sqrt(x)*H_x^2 = threshold_orig")
    print("  => RH true  => orig never halts => bitlen never halts (same x>253 guard)")
    print("  => RH false => psi(x)-x = Omega_+(x^Theta), Theta>1/2, and sqrt(x)k^2 =")
    print("     O(sqrt(x) log^2 x) = o(x^Theta), so bitlen halts.  Both directions hold.")


if __name__ == "__main__":
    main()
