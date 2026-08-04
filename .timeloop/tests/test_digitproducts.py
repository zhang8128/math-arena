from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from digitproducts import cycles, digits, product_plus_sum_bound, product_plus_sum_step


def test_digits_are_little_endian_and_preserve_zero() -> None:
    assert digits(0, 10) == (0,)
    assert digits(105, 10) == (5, 0, 1)
    assert digits(13, 2) == (1, 0, 1, 1)


@pytest.mark.parametrize(("n", "base"), [(-1, 10), (0, 1), (3, 0)])
def test_digits_reject_invalid_inputs(n: int, base: int) -> None:
    with pytest.raises(ValueError):
        digits(n, base)


def test_product_plus_sum_examples() -> None:
    assert product_plus_sum_step(123, 10) == 12
    assert product_plus_sum_step(105, 10) == 6
    assert product_plus_sum_step(7, 10) == 14


def test_bound_implies_strict_decrease_for_next_two_digit_lengths() -> None:
    for base in range(2, 9):
        bound = product_plus_sum_bound(base)
        for n in range(bound + 1, bound + 10_000):
            assert product_plus_sum_step(n, base) < n


def test_base_two_cycles_are_complete() -> None:
    assert cycles(2) == ((0,), (1, 2), (3,))
