from __future__ import annotations

import json
import subprocess
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
from t23_lychrel_fixed_base import build_evidence  # noqa: E402


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


def test_evidence_scans_the_inclusive_range_and_covers_every_negative() -> None:
    evidence = build_evidence()

    assert evidence["kind"] == "scoped_fixed_base_transplant_classification"
    assert evidence["status"] == "no_transplants"
    assert evidence["reference"]["base"] == 17
    assert evidence["reference"]["status"] == "verified_transplant"
    assert evidence["scan"]["base_start"] == 18
    assert evidence["scan"]["base_stop"] == 100
    assert evidence["scan"]["tested"] == 83
    assert evidence["scan"]["hits"] == []
    assert {
        item["base"] for item in evidence["scan"]["results"]
    } == set(range(18, 101))
    assert {
        item["status"] for item in evidence["scan"]["results"]
    } == {"infeasible"}
    assert evidence["obstructions"]["all_bases_covered"] is True
    covered = {
        base
        for core in evidence["obstructions"]["core_families"]
        for base in core["covered_bases"]
    }
    assert covered == set(range(18, 101))
    assert evidence["independent_audit"]["joint_solution_total"] == 0
    assert evidence["independent_audit"]["covered_bases"] == list(range(18, 101))


def test_standalone_audit_rebuilds_and_exhausts_every_core() -> None:
    script = (
        Path(__file__).resolve().parents[1]
        / "runs"
        / "t23_lychrel_fixed_base_independent.py"
    )

    completed = subprocess.run(
        [sys.executable, str(script)],
        check=True,
        capture_output=True,
        text=True,
    )
    audit = json.loads(completed.stdout)

    assert audit["kind"] == "independent_fixed_base_core_audit"
    assert audit["implementation"] == "standalone exhaustive Boolean replay"
    assert audit["bases_tested"] == 83
    assert audit["covered_bases"] == list(range(18, 101))
    assert audit["joint_solution_total"] == 0
    assert len(audit["equation_digest"]) == 64
