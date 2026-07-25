"""Kaprekar routine in arbitrary base and digit length.

T(n) = desc(digits) - asc(digits), padded back to L digits.

Key optimisation: T depends only on the MULTISET of digits, so the state space
is C(b+L-1, L) multisets rather than b^L integers. That makes large (b,L)
tractable and keeps the family fully decidable -- exhaustive enumeration over
multisets SETTLES each (b,L) completely.
"""

from itertools import combinations_with_replacement


def to_digits(n: int, b: int, L: int) -> tuple[int, ...]:
    d = []
    for _ in range(L):
        d.append(n % b)
        n //= b
    return tuple(reversed(d))


def step(ms: tuple[int, ...], b: int, L: int) -> tuple[int, ...]:
    desc = sorted(ms, reverse=True)
    asc = sorted(ms)
    hi = lo = 0
    for x in desc:
        hi = hi * b + x
    for x in asc:
        lo = lo * b + x
    return tuple(sorted(to_digits(hi - lo, b, L)))


def structure(b: int, L: int):
    """Complete cycle structure. Returns (fixed_points, cycles) as digit multisets.

    Excludes the trivial all-equal-digits states, which all map to zero.
    """
    states = list(combinations_with_replacement(range(b), L))
    nxt = {s: step(s, b, L) for s in states}
    colour = {}
    fixed, cycles = [], []
    for s in states:
        if s in colour:
            continue
        path, seen = [], {}
        cur = s
        while cur not in colour and cur not in seen:
            seen[cur] = len(path)
            path.append(cur)
            cur = nxt[cur]
        if cur in seen:
            cyc = path[seen[cur]:]
            if len(cyc) == 1:
                if any(x != cyc[0][0] for x in cyc[0]):
                    fixed.append(cyc[0])
            else:
                cycles.append(cyc)
        for m in path:
            colour[m] = True
    return fixed, cycles


def as_int(ms: tuple[int, ...], b: int) -> int:
    n = 0
    for x in sorted(ms, reverse=True):
        n = n * b + x
    return n
