#!/usr/bin/env python3
"""Classify fixed-base transplants of Seal's base-17 certificate topology."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_anchor_csp import (  # noqa: E402
    CarryEquation,
    solve_boolean_equations,
)
from lychrel_fixedbase import (  # noqa: E402
    FixedBaseClassification,
    build_fixed_base_carry_equations,
    classify_fixed_base_transplant,
)
from lychrel_wordproof import ParametricWord  # noqa: E402
from t22_lychrel_affine_lift import base17_reference_cycle  # noqa: E402


GENERIC_COORDINATES = (
    "phase=1,n=0,column=40",
    "phase=1,n=0,column=41",
    "phase=2,n=0,column=41",
)
BASE33_COORDINATES = (
    "phase=1,n=0,column=41",
    "phase=2,n=0,column=40",
    "phase=2,n=0,column=41",
)
BASE34_COORDINATES = (
    "phase=1,n=0,column=41",
    "phase=2,n=0,column=41",
    "phase=2,n=0,column=42",
)


def serialize_equation(equation: CarryEquation) -> dict[str, object]:
    return {
        "provenance": equation.provenance,
        "terms": [list(term) for term in equation.terms],
        "rhs": equation.rhs,
    }


def _extract_core(
    words: tuple[ParametricWord, ...],
    base: int,
    coordinates: tuple[str, ...],
) -> tuple[CarryEquation, ...]:
    equations = build_fixed_base_carry_equations(
        words,
        base,
        parameters=range(1),
        phases=(1, 2),
    )
    by_provenance = {equation.provenance: equation for equation in equations}
    return tuple(by_provenance[coordinate] for coordinate in coordinates)


def _core_family(
    words: tuple[ParametricWord, ...],
    *,
    core_id: str,
    coordinates: tuple[str, ...],
    covered_bases: tuple[int, ...],
) -> dict[str, object]:
    checks = []
    for base in covered_bases:
        core = _extract_core(words, base, coordinates)
        if solve_boolean_equations(core):
            raise AssertionError(f"{core_id} is feasible in base {base}")
        deletion_satisfiable = []
        for index in range(len(core)):
            solutions = solve_boolean_equations(core[:index] + core[index + 1 :])
            deletion_satisfiable.append(bool(solutions))
        checks.append(
            {
                "base": base,
                "joint_solutions": 0,
                "deletion_satisfiable": deletion_satisfiable,
                "deletion_irreducible": all(deletion_satisfiable),
            }
        )
    representative = covered_bases[0]
    return {
        "id": core_id,
        "coordinates": list(coordinates),
        "covered_bases": list(covered_bases),
        "representative_base": representative,
        "representative_equations": [
            serialize_equation(equation)
            for equation in _extract_core(words, representative, coordinates)
        ],
        "checks": checks,
    }


def _serialize_result(result: FixedBaseClassification) -> dict[str, object]:
    return {
        "base": result.base,
        "status": result.status,
        "parameters_checked": list(result.parameters_checked),
        "equations": result.equation_count,
        "variables": result.variable_count,
        "solutions": result.solution_count,
        "polynomial_verified": result.polynomial_verified,
        "nonpalindrome_witnesses": [
            list(witness) for witness in result.nonpalindrome_witnesses
        ],
    }


def build_evidence() -> dict[str, object]:
    words = base17_reference_cycle()
    reference = classify_fixed_base_transplant(words, 17)
    if reference.status != "verified_transplant":
        raise AssertionError("the base-17 calibration no longer verifies")

    classifications = tuple(
        classify_fixed_base_transplant(words, base)
        for base in range(18, 101)
    )
    unexpected = tuple(
        result for result in classifications if result.status != "infeasible"
    )
    generic_bases = tuple(
        base for base in range(18, 101) if base not in (33, 34)
    )
    core_families = (
        _core_family(
            words,
            core_id="generic",
            coordinates=GENERIC_COORDINATES,
            covered_bases=generic_bases,
        ),
        _core_family(
            words,
            core_id="base-33-exception",
            coordinates=BASE33_COORDINATES,
            covered_bases=(33,),
        ),
        _core_family(
            words,
            core_id="base-34-exception",
            coordinates=BASE34_COORDINATES,
            covered_bases=(34,),
        ),
    )
    covered = {
        base
        for family in core_families
        for base in family["covered_bases"]
    }
    independent_completed = subprocess.run(
        [sys.executable, str(ROOT / "runs" / "t23_lychrel_fixed_base_independent.py")],
        check=True,
        capture_output=True,
        text=True,
    )
    independent = json.loads(independent_completed.stdout)
    if independent["covered_bases"] != list(range(18, 101)):
        raise AssertionError("independent audit did not cover the complete scan")
    if independent["joint_solution_total"] != 0:
        raise AssertionError("independent audit found a core solution")
    return {
        "kind": "scoped_fixed_base_transplant_classification",
        "status": "no_transplants" if not unexpected else "review_required",
        "reference": {
            "base": 17,
            "period": len(words),
            "interfaces": len(words[0].repeats),
            "status": reference.status,
            "parameters_checked": list(reference.parameters_checked),
            "polynomial_verified": reference.polynomial_verified,
            "nonpalindrome_witnesses": [
                list(witness) for witness in reference.nonpalindrome_witnesses
            ],
        },
        "scope": {
            "topology": "exact T21 six-phase fragment and repeat layout",
            "fixed_digits": "d or d+(B-17), independently by occurrence and base",
            "repeats": "0 maps to 0; 16 maps to B-1",
            "carries": "fresh Boolean variables for every base, phase, n, and column",
            "identity": "carry equations at n=0,1,2 plus exact Z[q] verification",
        },
        "scan": {
            "base_start": 18,
            "base_stop": 100,
            "tested": len(classifications),
            "hits": [result.base for result in unexpected],
            "results": [_serialize_result(result) for result in classifications],
        },
        "obstructions": {
            "level": "n=0 alone",
            "core_families": list(core_families),
            "all_bases_covered": covered == set(range(18, 101)),
        },
        "independent_audit": {
            "kind": independent["kind"],
            "implementation": independent["implementation"],
            "source_sha256": independent["source_sha256"],
            "bases_tested": independent["bases_tested"],
            "covered_bases": independent["covered_bases"],
            "joint_solution_total": independent["joint_solution_total"],
            "equation_digest": independent["equation_digest"],
        },
        "prism": {
            "model": "qwen3.6:27b-mlx",
            "prompt_version": 2,
            "seed": 20260806,
            "artifacts": [
                "8e231924598beca796e4c0e7f5b6a26a7fa1f5e7e4ca65dee41760f872cdb4fa",
                "db50930d3cbc125b9efcbec9716995e9fdba11902a28b5276f1f27b9b3074331",
            ],
            "accepted_disposition": (
                "seek quotient-sized explanations and extremal local obstructions"
            ),
            "unverified_or_falsified_claims": [
                "the proposed reversal-carry signature and symmetry group",
                "the prediction of exactly one valid representative per base",
                "the proposed asymptotic elevation parity invariant",
                "the assumption that carries vanish in the large-base limit",
            ],
        },
        "prior_art_scope": {
            "base17": "Seal's published topology; positive calibration only",
            "base20_and_base26": "known Lychrel bases with different topologies",
            "claim": "no publication claim; scoped internal negative result",
        },
    }


def main() -> None:
    print(json.dumps(build_evidence(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
