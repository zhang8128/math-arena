#!/usr/bin/env python3
"""Independent audit of the T22 two-equation affine-lift obstruction."""

from __future__ import annotations

import itertools
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = re.compile(r"phase=(\d+),q_degree=(\d+),base_degree=(\d+)")


Polynomial = dict[tuple[int, int], int]


def add(left: Polynomial, right: Polynomial, factor: int = 1) -> Polynomial:
    result = dict(left)
    for monomial, coefficient in right.items():
        result[monomial] = result.get(monomial, 0) + factor * coefficient
        if not result[monomial]:
            del result[monomial]
    return result


def shift_base(polynomial: Polynomial, power: int) -> Polynomial:
    return {
        (q_degree, base_degree + power): coefficient
        for (q_degree, base_degree), coefficient in polynomial.items()
    }


def shift_q(polynomial: Polynomial) -> Polynomial:
    return {
        (q_degree + 1, base_degree): coefficient
        for (q_degree, base_degree), coefficient in polynomial.items()
    }


def compile_word(
    phase: int,
    phase_data: dict[str, object],
    assignment: dict[str, int],
    *,
    reverse: bool,
) -> Polynomial:
    fragments = [
        [
            (digit, f"p{phase}:f{fragment_index}:d{offset}")
            for offset, digit in enumerate(fragment)
        ]
        for fragment_index, fragment in enumerate(phase_data["fragments"])
    ]
    repeats = list(phase_data["repeats"])
    if reverse:
        fragments = [list(reversed(fragment)) for fragment in reversed(fragments)]
        repeats.reverse()
    polynomial: Polynomial = {}
    for fragment_index, fragment in enumerate(fragments):
        polynomial = shift_base(polynomial, len(fragment))
        fragment_polynomial: Polynomial = {}
        for digit, variable in fragment:
            fragment_polynomial = shift_base(fragment_polynomial, 1)
            slope = assignment.get(variable, 0)
            fragment_polynomial = add(
                fragment_polynomial,
                {
                    (0, 0): digit - 17 * slope,
                    (0, 1): slope,
                },
            )
        polynomial = add(polynomial, fragment_polynomial)
        if fragment_index < len(repeats):
            polynomial = shift_q(polynomial)
            if repeats[fragment_index] == 16:
                polynomial = add(polynomial, {(0, 0): -1, (1, 0): 1})
    return polynomial


def derive_equation(
    phases: list[dict[str, object]],
    provenance: str,
) -> tuple[list[list[object]], int]:
    match = PROVENANCE.fullmatch(provenance)
    if match is None:
        raise AssertionError("malformed provenance")
    phase, q_degree, base_degree = map(int, match.groups())
    next_phase_index = (phase + 1) % len(phases)

    def residual(assignment: dict[str, int]) -> int:
        value = compile_word(phase, phases[phase], assignment, reverse=False)
        value = add(
            value,
            compile_word(phase, phases[phase], assignment, reverse=True),
        )
        expected = compile_word(
            next_phase_index,
            phases[next_phase_index],
            assignment,
            reverse=False,
        )
        if phase == len(phases) - 1:
            expected = {
                (q_power, b_power + q_power): coefficient
                for (q_power, b_power), coefficient in expected.items()
            }
        return add(value, expected, -1).get((q_degree, base_degree), 0)

    variables = sorted(
        f"p{phase_index}:f{fragment_index}:d{offset}"
        for phase_index, phase_data in enumerate(phases)
        for fragment_index, fragment in enumerate(phase_data["fragments"])
        for offset, _ in enumerate(fragment)
    )
    baseline = residual({})
    terms = []
    for variable in variables:
        coefficient = residual({variable: 1}) - baseline
        if coefficient:
            terms.append([variable, coefficient])
    return terms, -baseline


def main() -> None:
    t21 = json.loads((ROOT / "runs/t21_lychrel_multi_interface.json").read_text())
    t22 = json.loads((ROOT / "runs/t22_lychrel_affine_lift.json").read_text())
    phases = t21["positive_control"]["phases"]
    core = t22["unsat_core"]
    variables = sorted(
        {variable for equation in core for variable, _ in equation["terms"]}
    )

    satisfying = []
    for values in itertools.product((0, 1), repeat=len(variables)):
        assignment = dict(zip(variables, values))
        if all(
            sum(assignment[variable] * coefficient for variable, coefficient in equation["terms"])
            == equation["rhs"]
            for equation in core
        ):
            satisfying.append(assignment)
    if satisfying:
        raise AssertionError("the serialized core is feasible")

    deletion_counts = []
    for removed in range(len(core)):
        remainder = core[:removed] + core[removed + 1 :]
        count = 0
        for values in itertools.product((0, 1), repeat=len(variables)):
            assignment = dict(zip(variables, values))
            count += all(
                sum(
                    assignment[variable] * coefficient
                    for variable, coefficient in equation["terms"]
                )
                == equation["rhs"]
                for equation in remainder
            )
        if not count:
            raise AssertionError("the serialized core is not irreducible")
        deletion_counts.append(count)

    for equation in core:
        terms, rhs = derive_equation(phases, equation["provenance"])
        if terms != equation["terms"] or rhs != equation["rhs"]:
            raise AssertionError("independent column derivation disagrees")

    print(
        json.dumps(
            {
                "core_equations": len(core),
                "core_variables": len(variables),
                "deletion_solution_counts": deletion_counts,
                "independent_coefficient_derivations": len(core),
                "joint_solutions": 0,
                "verified": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
