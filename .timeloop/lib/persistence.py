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


def best_persistence(b: int, max_len: int):
    """Max persistence over all digit multisets from {2..b-1} of length <= max_len."""
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
