"""Exact arithmetic helpers for the Erdős–Straus conjecture."""

from __future__ import annotations

from collections.abc import Mapping

from sympy import factorint


def is_decomposition(n: int, x: int, y: int, z: int) -> bool:
    if min(n, x, y, z) <= 0:
        return False
    return 4 * x * y * z == n * (x * y + x * z + y * z)


def _validated_factorization(q: int, factors: Mapping[int, int]) -> None:
    reconstructed = 1
    for prime, exponent in factors.items():
        reconstructed *= int(prime) ** int(exponent)
    if reconstructed != q:
        raise ValueError("q_factorization does not factor n*x")


def _square_divisors_at_most_root(
    q: int,
    factors: Mapping[int, int] | None = None,
) -> list[int]:
    divisors = [1]
    selected_factors = factorint(q) if factors is None else factors
    _validated_factorization(q, selected_factors)
    for prime, exponent in selected_factors.items():
        powers = [prime**power for power in range(2 * int(exponent) + 1)]
        divisors = [divisor * power for divisor in divisors for power in powers]
    return sorted(divisor for divisor in divisors if divisor <= q)


def _divisors_from_factorization(factors: Mapping[int, int]) -> list[int]:
    divisors = [1]
    for prime, exponent in factors.items():
        powers = [int(prime) ** power for power in range(int(exponent) + 1)]
        divisors = [divisor * power for divisor in divisors for power in powers]
    return sorted(divisors)


def factor_pair_solutions(
    n: int,
    x: int,
    q_factorization: Mapping[int, int] | None = None,
) -> tuple[tuple[int, int], ...]:
    if n <= 0 or x <= 0:
        raise ValueError("n and x must be positive")
    a = 4 * x - n
    if a <= 0:
        return ()
    q = n * x
    square = q * q
    found: set[tuple[int, int]] = set()
    for divisor in _square_divisors_at_most_root(q, q_factorization):
        paired = square // divisor
        if (divisor + q) % a or (paired + q) % a:
            continue
        y = (divisor + q) // a
        z = (paired + q) // a
        if x <= y <= z and is_decomposition(n, x, y, z):
            found.add((y, z))
    return tuple(sorted(found))


def first_tame_solution(
    n: int,
    x: int,
    q_factorization: Mapping[int, int] | None = None,
) -> tuple[int, int] | None:
    """Return the first solution whose y and z both divide q = n*x."""
    if n <= 0 or x <= 0:
        raise ValueError("n and x must be positive")
    a = 4 * x - n
    if a <= 0:
        return None
    q = n * x
    factors = factorint(q) if q_factorization is None else q_factorization
    _validated_factorization(q, factors)
    for y in _divisors_from_factorization(factors):
        if y < x:
            continue
        denominator = a * y - q
        if denominator <= 0 or q * y % denominator:
            continue
        z = q * y // denominator
        if z < y or q % z:
            continue
        if is_decomposition(n, x, y, z):
            return y, z
    return None


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
