"""Prime-run search for integer quadratics, with discriminant bookkeeping.

Reusable across the arena. The lesson from T0 is baked in: always carry the
discriminant alongside the run length, because the run length is a class-number
statement and is uninterpretable without it.
"""

from sympy import isprime, factorint


def run_length(a: int, b: int, c: int, cap: int = 10_000) -> int:
    """Number of consecutive n = 0,1,2,... with |a n^2 + b n + c| prime."""
    n = 0
    while n < cap:
        v = a * n * n + b * n + c
        if v in (0, 1, -1) or not isprime(abs(v)):
            return n
        n += 1
    return cap


def discriminant(a: int, b: int, c: int) -> int:
    return b * b - 4 * a * c


def fundamental_part(d: int) -> tuple[int, int]:
    """Split discriminant d = f^2 * d0 with d0 fundamental. Returns (d0, f)."""
    if d == 0:
        return (0, 0)
    f = 1
    d0 = d
    for p, e in factorint(abs(d)).items():
        while e >= 2 and d0 % (p * p) == 0:
            cand = d0 // (p * p)
            # keep d0 ≡ 0 or 1 mod 4 (a valid discriminant)
            if cand % 4 in (0, 1):
                d0 = cand
                f *= p
                e -= 2
            else:
                break
    return (d0, f)


HEEGNER = {-3, -4, -7, -8, -11, -12, -16, -19, -27, -28, -43, -67, -163}
"""Discriminants of imaginary quadratic ORDERS with class number 1 (all 13).
Note this is the order-level list, not the 9 fundamental field discriminants —
the distinction is exactly what T1 needed to test."""


def class_number(D: int) -> int:
    """Form class number h(D) for D < 0, by counting reduced forms."""
    if D >= 0 or D % 4 not in (0, 1):
        raise ValueError(f"not a negative discriminant: {D}")
    h = 0
    a = 1
    while 3 * a * a <= -D:
        for b in range(-a + 1, a + 1):
            num = b * b - D
            if num % (4 * a):
                continue
            c = num // (4 * a)
            if c < a:
                continue
            if (a == c or abs(b) == a) and b < 0:
                continue
            h += 1
        a += 1
    return h


def max_consecutive_run(a: int, b: int, c: int, window: int = 400) -> int:
    """Longest run of consecutive integers n with |a n^2 + b n + c| prime."""
    best = cur = 0
    for n in range(-window, window + 1):
        v = abs(a * n * n + b * n + c)
        if v > 1 and isprime(v):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best
