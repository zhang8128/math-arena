"""Digit-power maps T_{b,d}(n) = sum of d-th powers of base-b digits.

These are fully decidable: above a computable bound T(n) < n, so every cycle
lies below it and exhaustive search below the bound SETTLES the structure
completely. That makes this family useful for the arena — results are proofs,
not searches.
"""

def bound(b: int, d: int) -> int:
    """Smallest B such that every n > B has T(n) < n. All cycles lie in [1,B]."""
    k = 1
    while True:
        # a (k+1)-digit number is >= b^k ; its image is at most (k+1)*(b-1)^d
        if b**k > (k + 1) * (b - 1) ** d:
            return (k + 1) * (b - 1) ** d
        k += 1


def step(n: int, b: int, d: int) -> int:
    s = 0
    while n:
        s += (n % b) ** d
        n //= b
    return s


def cycles(b: int, d: int) -> list[list[int]]:
    """Complete list of cycles of T_{b,d}. Exhaustive below the bound => proof."""
    B = bound(b, d)
    state = [0] * (B + 1)          # 0 unknown, 1 in progress, 2 settled
    found: list[list[int]] = []
    for start in range(1, B + 1):
        if state[start]:
            continue
        path = []
        seen = {}
        n = start
        while n <= B and state[n] == 0:
            seen[n] = len(path)
            path.append(n)
            state[n] = 1
            n = step(n, b, d)
        if n <= B and state[n] == 1 and n in seen:
            found.append(path[seen[n]:])
        for m in path:
            state[m] = 2
    return found


def fixed_points(b: int, d: int) -> list[int]:
    """All n with T_{b,d}(n) = n, via digit-multiset enumeration.

    Far faster than iterating every n below the bound: a fixed point's digits
    are a multiset, so enumerate multisets and check whether the resulting
    power-sum has exactly those digits. Cuts the search from O(bound) to
    O(C(b+k-1, k)).
    """
    from itertools import combinations_with_replacement

    # max digit count k that can still reach a k-digit number
    k = 1
    while (k + 1) * (b - 1) ** d >= b ** k:
        k += 1
    kmax = k

    out = []
    for size in range(1, kmax + 1):
        for combo in combinations_with_replacement(range(b), size):
            s = sum(x ** d for x in combo)
            if s < 1:
                continue
            digs = []
            t = s
            while t:
                digs.append(t % b)
                t //= b
            if len(digs) == size and sorted(digs) == list(combo):
                out.append(s)
    return sorted(set(out))
