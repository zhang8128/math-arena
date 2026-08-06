#!/usr/bin/env python3
"""Standalone exhaustive audit of the T23 fixed-base obstruction cores."""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs" / "t21_lychrel_multi_interface.json"

GENERIC_COORDINATES = (
    (1, 40),
    (1, 41),
    (2, 41),
)
BASE33_COORDINATES = (
    (1, 41),
    (2, 40),
    (2, 41),
)
BASE34_COORDINATES = (
    (1, 41),
    (2, 41),
    (2, 42),
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _load_phases() -> list[dict[str, object]]:
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    control = payload["positive_control"]
    if control["base"] != 17 or control["period"] != 6:
        raise AssertionError("unexpected T21 positive-control identity")
    return control["phases"]


def _render_n_zero(
    phase_data: dict[str, object],
    phase: int,
) -> list[tuple[int, str]]:
    result = []
    for fragment_index, fragment in enumerate(phase_data["fragments"]):
        for offset, digit in enumerate(fragment):
            result.append(
                (
                    int(digit),
                    f"p{phase}:f{fragment_index}:d{offset}",
                )
            )
    return result


def _add_term(terms: dict[str, int], variable: str, coefficient: int) -> None:
    terms[variable] = terms.get(variable, 0) + coefficient


def _rebuild_equation(
    phases: list[dict[str, object]],
    base: int,
    phase: int,
    column: int,
) -> dict[str, object]:
    source = _render_n_zero(phases[phase], phase)
    target_phase = phase + 1
    target = _render_n_zero(phases[target_phase], target_phase)
    if column >= len(target):
        raise AssertionError("core column is outside the target word")
    left = source[len(source) - 1 - column] if column < len(source) else (0, "")
    right = source[column] if column < len(source) else (0, "")
    output = target[len(target) - 1 - column]
    delta = base - 17
    constant = left[0] + right[0] - output[0]
    terms: dict[str, int] = {}
    for digit, coefficient in ((left, delta), (right, delta), (output, -delta)):
        if digit[1] and coefficient:
            _add_term(terms, digit[1], coefficient)
    if column:
        _add_term(terms, f"c:p{phase}:n0:col{column - 1}", 1)
    if column + 1 < len(target):
        _add_term(terms, f"c:p{phase}:n0:col{column}", -base)
    return {
        "provenance": f"phase={phase},n=0,column={column}",
        "terms": [
            [variable, coefficient]
            for variable, coefficient in sorted(terms.items())
            if coefficient
        ],
        "rhs": -constant,
    }


def _solution_count(equations: tuple[dict[str, object], ...]) -> int:
    variables = sorted(
        {
            variable
            for equation in equations
            for variable, _ in equation["terms"]
        }
    )
    count = 0
    for values in itertools.product((0, 1), repeat=len(variables)):
        assignment = dict(zip(variables, values))
        if all(
            sum(
                coefficient * assignment[variable]
                for variable, coefficient in equation["terms"]
            )
            == equation["rhs"]
            for equation in equations
        ):
            count += 1
    return count


def _audit_family(
    phases: list[dict[str, object]],
    *,
    family_id: str,
    coordinates: tuple[tuple[int, int], ...],
    bases: tuple[int, ...],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    checks = []
    digest_rows = []
    for base in bases:
        equations = tuple(
            _rebuild_equation(phases, base, phase, column)
            for phase, column in coordinates
        )
        joint_solutions = _solution_count(equations)
        if joint_solutions:
            raise AssertionError(f"{family_id} is feasible in base {base}")
        deletion_counts = [
            _solution_count(equations[:index] + equations[index + 1 :])
            for index in range(len(equations))
        ]
        checks.append(
            {
                "base": base,
                "joint_solutions": joint_solutions,
                "deletion_solution_counts": deletion_counts,
                "deletion_irreducible": all(deletion_counts),
            }
        )
        digest_rows.append(
            {
                "base": base,
                "family": family_id,
                "equations": equations,
            }
        )
    return (
        {
            "id": family_id,
            "coordinates": [
                f"phase={phase},n=0,column={column}"
                for phase, column in coordinates
            ],
            "covered_bases": list(bases),
            "checks": checks,
        },
        digest_rows,
    )


def audit() -> dict[str, object]:
    phases = _load_phases()
    generic_bases = tuple(
        base for base in range(18, 101) if base not in (33, 34)
    )
    specifications = (
        ("generic", GENERIC_COORDINATES, generic_bases),
        ("base-33-exception", BASE33_COORDINATES, (33,)),
        ("base-34-exception", BASE34_COORDINATES, (34,)),
    )
    families = []
    digest_rows = []
    for family_id, coordinates, bases in specifications:
        family, rows = _audit_family(
            phases,
            family_id=family_id,
            coordinates=coordinates,
            bases=bases,
        )
        families.append(family)
        digest_rows.extend(rows)
    covered = sorted(
        base for family in families for base in family["covered_bases"]
    )
    return {
        "kind": "independent_fixed_base_core_audit",
        "implementation": "standalone exhaustive Boolean replay",
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "bases_tested": len(covered),
        "covered_bases": covered,
        "joint_solution_total": sum(
            check["joint_solutions"]
            for family in families
            for check in family["checks"]
        ),
        "equation_digest": hashlib.sha256(
            _canonical_json(digest_rows).encode("utf-8")
        ).hexdigest(),
        "core_families": families,
    }


def main() -> None:
    print(json.dumps(audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
