#!/usr/bin/env python3
"""Classify global affine lifts of Seal's base-17 certificate topology."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from lychrel_anchor_csp import (  # noqa: E402
    AnchorVariable,
    CarryEquation,
    classify_affine_lift,
    solve_boolean_equations,
)
from lychrel_wordproof import ParametricWord, infer_cycle, verify_cycle  # noqa: E402
from t21_lychrel_multi_interface import base17_start, orbit  # noqa: E402


def base17_reference_cycle() -> tuple[ParametricWord, ...]:
    full_orbit = orbit(base17_start(2), 17, 12)
    cycle = infer_cycle(17, full_orbit[:6], full_orbit[6:12], max_blocks=2)
    if cycle is None or not verify_cycle(cycle):
        raise AssertionError("T21 base-17 control no longer verifies")
    return cycle


def serialize_equation(equation: CarryEquation) -> dict[str, object]:
    return {
        "provenance": equation.provenance,
        "terms": [[variable, coefficient] for variable, coefficient in equation.terms],
        "rhs": equation.rhs,
    }


def reference_digit_map(
    words: tuple[ParametricWord, ...],
) -> dict[str, int]:
    return {
        AnchorVariable(phase, fragment_index, offset).key: digit
        for phase, word in enumerate(words)
        for fragment_index, fragment in enumerate(word.fragments)
        for offset, digit in enumerate(fragment)
    }


def build_evidence() -> dict[str, object]:
    words = base17_reference_cycle()
    result = classify_affine_lift(words)
    if result.status != "infeasible":
        raise AssertionError(
            "the observed classification changed; inspect candidates before reporting"
        )
    core = result.unsat_core
    deletion_witnesses = []
    for index in range(len(core)):
        solutions = solve_boolean_equations(core[:index] + core[index + 1 :])
        if not solutions:
            raise AssertionError("reported core is not deletion-irreducible")
        deletion_witnesses.append(
            {
                "removed": core[index].provenance,
                "satisfying_assignment": solutions[0],
            }
        )
    digits = reference_digit_map(words)
    core_variables = sorted(
        {variable for equation in core for variable, _ in equation.terms}
    )
    return {
        "kind": "scoped_affine_lift_classification",
        "status": result.status,
        "reference": {
            "base": 17,
            "period": len(words),
            "interfaces": len(words[0].repeats),
            "verified_t21_control": True,
        },
        "scope": {
            "base_range": "all integers b >= 17",
            "digit_lifts": "d or d+(b-17) independently at every fixed occurrence",
            "repeat_lifts": "0 -> 0 and 16 -> b-1",
            "topology": "the exact T21 six-phase fragment and repeat layout",
            "carry_skeleton": "the base-17 carries for n=0,1,2,3",
        },
        "system": {
            "equations": result.equation_count,
            "unique_equations": result.unique_equation_count,
            "anchor_variables": sum(len(fragment) for word in words for fragment in word.fragments),
            "solutions": result.solution_count,
        },
        "unsat_core": [serialize_equation(equation) for equation in core],
        "core_variables": [
            {"variable": variable, "base17_digit": digits[variable]}
            for variable in core_variables
        ],
        "core_irreducible": (
            not solve_boolean_equations(core)
            and all(
                solve_boolean_equations(core[:index] + core[index + 1 :])
                for index in range(len(core))
            )
        ),
        "core_deletion_witnesses": deletion_witnesses,
        "human_obstruction": {
            "equations": ["2*x-y=1", "2*y-z=0"],
            "binary_domain": "x,y,z in {0,1}",
            "derivation": (
                "The first equation forces x=y=1; the second then forces z=2, "
                "outside the binary anchor domain."
            ),
            "columns": [
                "phase 4 to 5, n=0, central column 41",
                "phase 5 to 0(n+1), n=0, central column 41",
            ],
        },
        "prism": {
            "model": "qwen3.6:27b-mlx",
            "prompt_version": 2,
            "seed": 20260805,
            "artifacts": [
                "59ed170642587090413cb75598cb99423ef4ef2087dcd759acc196ce6a189f2c",
                "66190c1eeb550a4ab43b2ab9984641277d6cf469bb91f2524b1f4abc9636f8c4",
            ],
            "accepted_disposition": "local carry feasibility plus global exact verification",
            "unverified_claims": [
                "the proposed modular carry-period invariant",
                "the proposed dual Omega invariant",
                "two perturbed-base probes as proof",
            ],
        },
    }


def main() -> None:
    print(json.dumps(build_evidence(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
