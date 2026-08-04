"""Exact arithmetic helpers for the Erdős–Straus conjecture."""

from __future__ import annotations

from sympy import factorint


def is_decomposition(n: int, x: int, y: int, z: int) -> bool:
    if min(n, x, y, z) <= 0:
        return False
    return 4 * x * y * z == n * (x * y + x * z + y * z)


def _square_divisors_at_most_root(q: int) -> list[int]:
    divisors = [1]
    for prime, exponent in factorint(q).items():
        powers = [prime**power for power in range(2 * int(exponent) + 1)]
        divisors = [divisor * power for divisor in divisors for power in powers]
    return sorted(divisor for divisor in divisors if divisor <= q)


def factor_pair_solutions(n: int, x: int) -> tuple[tuple[int, int], ...]:
    if n <= 0 or x <= 0:
        raise ValueError("n and x must be positive")
    a = 4 * x - n
    if a <= 0:
        return ()
    q = n * x
    square = q * q
    found: set[tuple[int, int]] = set()
    for divisor in _square_divisors_at_most_root(q):
        paired = square // divisor
        if (divisor + q) % a or (paired + q) % a:
            continue
        y = (divisor + q) // a
        z = (paired + q) // a
        if x <= y <= z and is_decomposition(n, x, y, z):
            found.add((y, z))
    return tuple(sorted(found))


def first_solution(n: int) -> tuple[int, int, int] | None:
    if n < 2:
        raise ValueError("n must be at least 2")
    if n % 2 == 0:
        return n // 2, n, n
    if n % 4 == 3:
        denominator = n * (n + 1) // 2
        return (n + 1) // 4, denominator, denominator
    for x in range((n + 3) // 4, (3 * n) // 4 + 1):
        solutions = factor_pair_solutions(n, x)
        if solutions:
            y, z = solutions[0]
            return x, y, z
    return None
