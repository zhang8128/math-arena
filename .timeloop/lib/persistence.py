"""Multiplicative persistence in base b: iterate n -> product of digits.

Persistence depends only on the digit MULTISET (product is order-independent),
and any digit 0 collapses immediately, so the search space is multisets drawn
from {2,...,b-1}. Digits equal to 1 leave the product unchanged, so they only
inflate n without affecting persistence -- excluded.
"""

from itertools import combinations_with_replacement


def persistence(n: int, b: int) -> int:
    steps = 0
    while n >= b:
        p = 1
        m = n
        while m:
            p *= m % b
            m //= b
        n = p
        steps += 1
    return steps


def smallest_with_multiset(ms: tuple[int, ...], b: int) -> int:
    n = 0
    for d in sorted(ms):
        n = n * b + d
    return n


def max_persistence(b: int, limit: int = 10**18) -> tuple[int, int]:
    """Authoritative maximum persistence for base `b`. Returns (value, witness N).

    Correct method: after one step the value is a product of digits, hence
    (b-1)-smooth; and every prime < b is itself a valid digit, so EVERY
    (b-1)-smooth number is realisable as a digit product. Therefore

        max persistence = 1 + max over (b-1)-smooth N <= limit of persistence(N)

    Use this, not `best_persistence`. The result is still bounded by `limit`;
    check the witness against it before calling anything a record.
    """
    from sympy import primerange

    primes = [p for p in primerange(2, b)]
    smooth = [1]
    for p in primes:
        new = []
        for v in smooth:
            x = v
            while x <= limit // p:
                x *= p
                new.append(x)
        smooth += new
    best, arg = 0, 1
    for n in smooth:
        q = persistence(n, b)
        if q > best:
            best, arg = q, n
    return 1 + best, arg


def best_persistence(b: int, max_len: int):
    """LENGTH-LIMITED search over digit multisets. Returns (value, multiset).

    ⚠️ This under-reports and does NOT signal it. Found by the blind exam on
    2026-07-25: it returns 5 for base 5 at every `max_len` below 22, while the
    true value is 6 — because the witness is 2^40 * 3^2, which needs 22 digits
    drawn from {2,3,4}. A bare `5` reads as an answer and means "best within
    12 digits".

    That is this arena's characteristic failure — a limit of the search reported
    as a property of the world — committed by its own library. Prefer
    `max_persistence`. Kept only because the multiset witness is sometimes
    wanted; callers must treat the value as a LOWER BOUND.
    """
    best = (0, None)
    digits = list(range(2, b))
    if not digits:
        return best
    for L in range(1, max_len + 1):
        for ms in combinations_with_replacement(digits, L):
            p = 1
            for d in ms:
                p *= d
            pers = 1 + persistence(p, b)
            if pers > best[0]:
                best = (pers, ms)
    return best
