from __future__ import annotations

import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from erdos_straus import factor_pair_solutions, first_solution, is_decomposition


def test_exact_decomposition_predicate() -> None:
    assert is_decomposition(5, 2, 4, 20)
    assert not is_decomposition(5, 2, 4, 19)
    assert not is_decomposition(5, 0, 4, 20)


def test_even_positive_control() -> None:
    for n in range(2, 100, 2):
        assert is_decomposition(n, n // 2, n, n)


def test_three_mod_four_positive_control() -> None:
    for n in range(3, 100, 4):
        assert is_decomposition(n, (n + 1) // 4, n * (n + 1) // 2, n * (n + 1) // 2)


def test_factor_pair_generator_matches_bruteforce_for_small_n() -> None:
    for n in range(2, 30):
        for x in range((n + 3) // 4, (3 * n) // 4 + 1):
            got = set(factor_pair_solutions(n, x))
            residual_numerator = 4 * x - n
            if residual_numerator <= 0:
                want: set[tuple[int, int]] = set()
            else:
                max_y = (2 * n * x) // residual_numerator
                want = set()
                for y in range(x, max_y + 1):
                    remainder = Fraction(4, n) - Fraction(1, x) - Fraction(1, y)
                    if remainder > 0 and remainder.numerator == 1:
                        z = remainder.denominator
                        if y <= z:
                            want.add((y, z))
            assert got == want


def test_first_solution_covers_small_range() -> None:
    for n in range(2, 500):
        solution = first_solution(n)
        assert solution is not None
        assert is_decomposition(n, *solution)
