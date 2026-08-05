from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from lychrel_affine import (  # noqa: E402
    AffineDigit,
    AffineWord,
    evaluate_bivariate,
    reverse_affine_word,
    shift_q_parameter,
    value_bivariate,
    verify_affine_cycle,
)
from lychrel_wordproof import digits_value  # noqa: E402


def test_affine_digits_are_lower_or_upper_anchored() -> None:
    assert AffineDigit(5, 0).evaluate(23) == 5
    assert AffineDigit(5, 1).evaluate(23) == 11
    with pytest.raises(ValueError, match="slope"):
        AffineDigit(5, 2)


def test_two_interface_bivariate_compiler_matches_literal_values() -> None:
    candidate = AffineWord(
        fragments=(
            (AffineDigit(1, 0),),
            (AffineDigit(2, 1),),
            (AffineDigit(3, 0),),
        ),
        repeats=(0, 1),
    )
    polynomial = value_bivariate(candidate)
    for base in (17, 18, 31):
        for n in range(4):
            assert evaluate_bivariate(polynomial, base, base**n) == digits_value(
                candidate.render(base, n), base
            )


def test_parameter_shift_substitutes_q_with_base_times_q() -> None:
    polynomial = ((1,), (2,))
    assert shift_q_parameter(polynomial) == ((1,), (0, 2))
    for base in (17, 29):
        for q in (1, base, base**2):
            assert evaluate_bivariate(shift_q_parameter(polynomial), base, q) == (
                evaluate_bivariate(polynomial, base, base * q)
            )


def test_reversing_affine_tokens_reverses_every_rendered_word() -> None:
    candidate = AffineWord(
        fragments=(
            (AffineDigit(1, 0), AffineDigit(2, 1)),
            (AffineDigit(3, 0),),
        ),
        repeats=(1,),
    )
    reversed_candidate = reverse_affine_word(candidate)
    for base in (17, 23):
        for n in range(3):
            assert reversed_candidate.render(base, n) == tuple(
                reversed(candidate.render(base, n))
            )


def test_cycle_verifier_rejects_noncanonical_zero_padding() -> None:
    zero = AffineDigit(0, 0)
    canonical_zero = AffineWord(((zero,),), ())
    padded_zero = AffineWord(((zero, zero, zero),), ())
    assert verify_affine_cycle((canonical_zero,))
    assert not verify_affine_cycle((padded_zero,))
