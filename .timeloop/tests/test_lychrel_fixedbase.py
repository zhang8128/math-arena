from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runs"))

from lychrel_anchor_csp import AnchorVariable, CarryEquation  # noqa: E402
from lychrel_fixedbase import (  # noqa: E402
    build_fixed_base_carry_equations,
    classify_fixed_base_transplant,
    materialize_fixed_base_cycle,
)
from lychrel_wordproof import ParametricWord, verify_cycle  # noqa: E402
from t22_lychrel_affine_lift import base17_reference_cycle  # noqa: E402


def test_materialization_anchors_each_occurrence_and_maps_repeat_extremes() -> None:
    reference = (
        ParametricWord(
            17,
            fragments=((3,), (0, 16)),
            repeats=(16,),
        ),
    )
    assignment = {
        AnchorVariable(0, 0, 0).key: 0,
        AnchorVariable(0, 1, 0).key: 1,
        AnchorVariable(0, 1, 1).key: 0,
    }

    materialized = materialize_fixed_base_cycle(reference, 20, assignment)

    assert materialized == (
        ParametricWord(
            20,
            fragments=((3,), (3, 16)),
            repeats=(19,),
        ),
    )
    assert materialized[0].render(1) == (3, 19, 3, 16)


def test_carry_compiler_matches_a_hand_derived_fixed_base_column() -> None:
    reference = (
        ParametricWord(17, fragments=((3, 5),), repeats=()),
        ParametricWord(17, fragments=((8, 8),), repeats=()),
    )

    equations = build_fixed_base_carry_equations(
        reference,
        20,
        parameters=range(1),
        phases=(0,),
    )

    assert equations[0] == CarryEquation(
        terms=(
            (AnchorVariable(0, 0, 0).key, 3),
            (AnchorVariable(0, 0, 1).key, 3),
            (AnchorVariable(1, 0, 1).key, -3),
            ("c:p0:n0:col0", -20),
        ),
        rhs=0,
        provenance="phase=0,n=0,column=0",
    )


@lru_cache(maxsize=1)
def reference_cycle() -> tuple[ParametricWord, ...]:
    return base17_reference_cycle()


def test_classifier_reconstructs_the_exact_base17_control() -> None:
    result = classify_fixed_base_transplant(reference_cycle(), 17)

    assert result.status == "verified_transplant"
    assert result.parameters_checked == (0, 1, 2)
    assert result.polynomial_verified is True
    assert result.cycle is not None
    assert verify_cycle(result.cycle)
    assert len(result.nonpalindrome_witnesses) == 6


def test_classifier_rejects_base18_with_fresh_carries_at_n_zero() -> None:
    result = classify_fixed_base_transplant(reference_cycle(), 18)

    assert result.status == "infeasible"
    assert result.parameters_checked == (0,)
    assert result.solution_count == 0
    assert result.cycle is None
    assert result.polynomial_verified is False
