#!/usr/bin/env python3
"""Classify arbitrary fixed-digit realizations of the T21 topology."""

from __future__ import annotations

import gc
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import pycosat  # type: ignore[import-not-found]  # noqa: E402

from lychrel_arbitrary_topology import (  # noqa: E402
    CNFFormula,
    assignment_satisfies,
    build_column_constraints,
    compile_one_hot_cnf,
    decode_digit_assignment,
    materialize_cycle,
    reference_assignment,
)
from lychrel_wordproof import (  # noqa: E402
    ParametricWord,
    fixed_palindrome_mismatch,
    reverse_add_digits,
    verify_cycle,
)
from t22_lychrel_affine_lift import base17_reference_cycle  # noqa: E402


def solve_formula(formula: CNFFormula) -> tuple[bool | None, ...] | None:
    """Return a normalized Boolean model, or ``None`` for exact UNSAT."""
    result = pycosat.solve(formula.clauses, vars=formula.variable_count)
    if result == "UNSAT":
        return None
    if not isinstance(result, list):
        raise RuntimeError(f"PicoSAT returned a non-decisive status: {result}")
    return (None,) + tuple(literal > 0 for literal in result)


def _integer_replay_count(words: tuple[ParametricWord, ...]) -> int:
    checks = 0
    for n in range(9):
        for phase, word in enumerate(words):
            next_phase = (phase + 1) % len(words)
            output_n = n + int(phase == len(words) - 1)
            if reverse_add_digits(word.render(n), word.base) != words[
                next_phase
            ].render(output_n):
                raise AssertionError("base-17 integer replay failed")
            checks += 1
    return checks


def _serialize_cycle(words: tuple[ParametricWord, ...]) -> list[dict[str, object]]:
    return [
        {
            "fragments": [list(fragment) for fragment in word.fragments],
            "repeats": list(word.repeats),
        }
        for word in words
    ]


def _classify_base(
    words: tuple[ParametricWord, ...],
    base: int,
) -> dict[str, object]:
    n_zero = compile_one_hot_cnf(words, base, parameters=(0,))
    result: dict[str, object] = {
        "base": base,
        "encoding": "one-hot digits with exact carry transitions",
        "parameters_checked": [0],
        "variable_count": n_zero.variable_count,
        "clause_count": n_zero.clause_count,
        "dimacs_digest": n_zero.digest,
    }
    model = solve_formula(n_zero)
    if model is None:
        result["status"] = "infeasible_at_n_zero"
        return result

    full = compile_one_hot_cnf(words, base, parameters=(0, 1, 2))
    full_model = solve_formula(full)
    result.update(
        {
            "parameters_checked": [0, 1, 2],
            "interpolation_variable_count": full.variable_count,
            "interpolation_clause_count": full.clause_count,
            "interpolation_dimacs_digest": full.digest,
        }
    )
    if full_model is None:
        result["status"] = "infeasible_at_interpolation"
        return result

    digits = decode_digit_assignment(full, full_model)
    cycle = materialize_cycle(words, base, digits)
    witnesses = tuple(fixed_palindrome_mismatch(word) for word in cycle)
    if not verify_cycle(cycle):
        raise AssertionError("SAT candidate failed exact polynomial verification")
    if any(witness is None for witness in witnesses):
        raise AssertionError("SAT candidate lacks a fixed non-palindrome witness")
    result.update(
        {
            "status": "verified_realization",
            "cycle": _serialize_cycle(cycle),
            "nonpalindrome_witnesses": [list(witness) for witness in witnesses],
        }
    )
    return result


def build_evidence() -> dict[str, object]:
    words = base17_reference_cycle()
    reference_formula = compile_one_hot_cnf(words, 17, parameters=(0,))
    reference_model = reference_assignment(words, reference_formula)
    calibration = assignment_satisfies(reference_formula, reference_model)
    if not calibration or not verify_cycle(words):
        raise AssertionError("base-17 positive control failed")

    results = []
    for base in range(18, 41):
        results.append(_classify_base(words, base))
        gc.collect()
    hits = [
        item["base"]
        for item in results
        if item["status"] == "verified_realization"
    ]
    status = "verified_realizations" if hits else "no_n_zero_realizations"
    if not hits and any(
        item["status"] != "infeasible_at_n_zero" for item in results
    ):
        status = "no_verified_realizations"
    return {
        "kind": "arbitrary_digit_topology_classification",
        "status": status,
        "reference": {
            "base": 17,
            "fixed_occurrences": len(reference_formula.digit_keys),
            "integer_replays": _integer_replay_count(words),
            "n_zero_columns": len(
                build_column_constraints(words, 17, parameters=(0,))
            ),
            "one_hot_assignment_verified": calibration,
            "polynomial_verified": verify_cycle(words),
        },
        "scope": {
            "topology": "exact T21 six-phase fragment lengths and repeat locations",
            "fixed_digits": "497 independent values in 0..B-1",
            "repeat_mapping": "0 -> 0 and 16 -> B-1",
            "carry_behavior": "fresh Boolean carry per phase, parameter, and column",
            "negative_logic": "UNSAT at n=0 is a necessary-condition obstruction",
        },
        "solver": {
            "engine": "PicoSAT via pycosat",
            "pycosat_version": getattr(pycosat, "__version__", "unknown"),
        },
        "calibration": {
            "parameters": [0],
            "variable_count": reference_formula.variable_count,
            "clause_count": reference_formula.clause_count,
            "dimacs_digest": reference_formula.digest,
        },
        "scan": {
            "base_start": 18,
            "base_stop": 40,
            "tested": len(results),
            "hits": hits,
            "results": results,
        },
        "prism": {
            "model": "qwen3.6:27b-mlx",
            "prompt_version": 2,
            "seed": 20260806,
            "artifacts": [
                "99415b8fc2a52e62f541c03b93712c1bae61f39ac0d3a61fdf898409c92687ce",
                "8a9c0b6e3bb8539cf2aa022edaeba1508a09281bc562c382f57d4b738758e90c",
            ],
            "accepted_disposition": "layered finite carry states with exact local search and independent audit",
            "unsupported_claims": [
                "carry-flux cut invariant",
                "determinant/resultant Omega invariant",
                "bounded treewidth at most three",
                "higher-base feasible algebraic components",
            ],
            "false_limitation": "outgoing carries remain Boolean for every base in this two-addend problem",
        },
        "limitations": [
            "The negative scope fixes the T21 topology and bases 18..40.",
            "PicoSAT UNSAT results require the independent binary/CaDiCaL audit before final reporting.",
            "No minimal unsatisfiable column core is claimed.",
        ],
    }


def main() -> None:
    print(json.dumps(build_evidence(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
