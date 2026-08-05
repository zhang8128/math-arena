from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runs"))

from lychrel_affine import (  # noqa: E402
    AffineDigit,
    AffineWord,
    evaluate_bivariate,
    reverse_affine_word,
    shift_q_parameter,
    value_bivariate,
    verify_affine_cycle,
)
from lychrel_anchor_csp import (  # noqa: E402
    CarryEquation,
    build_carry_equations,
    classify_affine_lift,
    irreducible_unsat_core,
    solve_boolean_equations,
)
from lychrel_wordproof import ParametricWord  # noqa: E402
from lychrel_wordproof import digits_value, infer_cycle  # noqa: E402
from t21_lychrel_multi_interface import base17_start, orbit  # noqa: E402
from t22_lychrel_affine_lift import build_evidence  # noqa: E402


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


def test_boolean_solver_finds_the_hand_solution() -> None:
    equations = (
        CarryEquation((("x", 1), ("y", 1)), 1, provenance="sum"),
        CarryEquation((("x", 1), ("y", -1)), -1, provenance="difference"),
    )
    assert solve_boolean_equations(equations, limit=2) == ({"x": 0, "y": 1},)


def test_unsat_core_is_irreducible() -> None:
    equations = (
        CarryEquation((("x", 1),), 0, provenance="x=0"),
        CarryEquation((("x", 1),), 1, provenance="x=1"),
        CarryEquation((("y", 1),), 0, provenance="irrelevant"),
    )
    core = irreducible_unsat_core(equations)
    assert tuple(item.provenance for item in core) == ("x=0", "x=1")
    assert not solve_boolean_equations(core)
    assert all(
        solve_boolean_equations(core[:index] + core[index + 1 :])
        for index in range(len(core))
    )


def binary_reference_cycle() -> tuple[ParametricWord, ...]:
    def make(fragments: tuple[str, ...], repeats: str) -> ParametricWord:
        return ParametricWord(
            2,
            tuple(tuple(int(digit) for digit in fragment) for fragment in fragments),
            tuple(int(digit) for digit in repeats),
        )

    return (
        make(("10", "1101", "00"), "10"),
        make(("11", "1000", "01"), "01"),
        make(("10", "11010", "00"), "10"),
        make(("11", "00101", "01"), "01"),
    )


def test_carry_extraction_matches_a_hand_derived_binary_column() -> None:
    equations = build_carry_equations(
        binary_reference_cycle(),
        parameters=range(1),
    )
    first = next(
        equation
        for equation in equations
        if equation.provenance == "phase=0,n=0,column=0"
    )
    assert first.terms == (
        ("p0:f0:d0", 1),
        ("p0:f2:d1", 1),
        ("p1:f2:d1", -1),
    )
    assert first.rhs == 0


def base17_reference_cycle() -> tuple[ParametricWord, ...]:
    full_orbit = orbit(base17_start(2), 17, 12)
    cycle = infer_cycle(17, full_orbit[:6], full_orbit[6:12], max_blocks=2)
    assert cycle is not None
    return cycle


def test_base17_topology_has_an_exact_affine_classification() -> None:
    result = classify_affine_lift(base17_reference_cycle())
    assert result.status == "infeasible"
    assert not result.cycles
    assert result.unsat_core
    assert not solve_boolean_equations(result.unsat_core)
    assert all(
        solve_boolean_equations(
            result.unsat_core[:index] + result.unsat_core[index + 1 :]
        )
        for index in range(len(result.unsat_core))
    )


def test_evidence_records_the_two_equation_obstruction() -> None:
    evidence = build_evidence()
    assert evidence["status"] == "infeasible"
    assert evidence["unsat_core"] == [
        {
            "provenance": "phase=4,n=0,column=41",
            "terms": [["p4:f1:d12", 2], ["p5:f1:d12", -1]],
            "rhs": 1,
        },
        {
            "provenance": "phase=5,n=0,column=41",
            "terms": [["p0:f1:d13", -1], ["p5:f1:d12", 2]],
            "rhs": 0,
        },
    ]
    assert evidence["core_irreducible"] is True
