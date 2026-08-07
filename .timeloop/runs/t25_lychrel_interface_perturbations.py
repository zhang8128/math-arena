#!/usr/bin/env python3
"""Classify one-interface perturbations of the T21 Lychrel topology."""

from __future__ import annotations

import gc
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import pycosat  # type: ignore[import-not-found]  # noqa: E402

from lychrel_arbitrary_topology import (  # noqa: E402
    CNFFormula,
    compile_one_hot_cnf,
    decode_digit_assignment,
    materialize_cycle,
)
from lychrel_interface_perturbations import (  # noqa: E402
    InterfaceMove,
    all_moves,
    move_interface,
    n_zero_relevant_moves,
)
from lychrel_wordproof import (  # noqa: E402
    ParametricWord,
    fixed_palindrome_mismatch,
    verify_cycle,
)
from t22_lychrel_affine_lift import base17_reference_cycle  # noqa: E402
from t25_lychrel_interface_perturbations_independent import (  # noqa: E402
    build_audit,
)


T24_EVIDENCE = Path(__file__).with_name("t24_lychrel_arbitrary_topology.json")


def variant_id(move: InterfaceMove) -> str:
    sign = "plus" if move.shift > 0 else "minus"
    return f"phase{move.phase}-interface{move.interface}-{sign}{abs(move.shift)}"


def solve_formula(formula: CNFFormula) -> tuple[bool | None, ...] | None:
    result = pycosat.solve(formula.clauses, vars=formula.variable_count)
    if result == "UNSAT":
        return None
    if not isinstance(result, list):
        raise RuntimeError(f"PicoSAT returned a non-decisive status: {result}")
    return (None,) + tuple(literal > 0 for literal in result)


def _serialize_cycle(words: tuple[ParametricWord, ...]) -> list[dict[str, object]]:
    return [
        {
            "fragments": [list(fragment) for fragment in word.fragments],
            "repeats": list(word.repeats),
        }
        for word in words
    ]


def classify_instance(
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


def _load_t24_obstruction() -> tuple[dict[str, object], str]:
    raw = T24_EVIDENCE.read_bytes()
    evidence = json.loads(raw)
    results = evidence["scan"]["results"]
    covered = [
        item["base"]
        for item in results
        if item["status"] == "infeasible_at_n_zero"
    ]
    if covered != list(range(18, 41)):
        raise AssertionError("T24 evidence does not cover bases 18..40")
    if not evidence["independent_audit"]["status_agreement"]:
        raise AssertionError("T24 evidence lacks independent agreement")
    return evidence, hashlib.sha256(raw).hexdigest()


def build_evidence() -> dict[str, object]:
    words = base17_reference_cycle()
    moves = all_moves(words, max_shift=2)
    relevant = n_zero_relevant_moves(words, max_shift=2)
    _, t24_digest = _load_t24_obstruction()

    inherited = [
        {
            "variant_id": variant_id(move),
            "phase": move.phase,
            "interface": move.interface,
            "shift": move.shift,
            "status": "infeasible_at_n_zero_by_t24_reduction",
        }
        for move in moves
        if move.phase != 0
    ]
    variants = []
    for move in relevant:
        moved = move_interface(words, move)
        results = []
        for base in range(18, 41):
            results.append(classify_instance(moved, base))
            gc.collect()
        variants.append(
            {
                "variant_id": variant_id(move),
                "phase": move.phase,
                "interface": move.interface,
                "shift": move.shift,
                "fragment_lengths": [
                    len(fragment) for fragment in moved[move.phase].fragments
                ],
                "results": results,
            }
        )

    n_zero_survivors = [
        {"variant_id": variant["variant_id"], "base": result["base"]}
        for variant in variants
        for result in variant["results"]
        if result["status"] != "infeasible_at_n_zero"
    ]
    verified = [
        {"variant_id": variant["variant_id"], "base": result["base"]}
        for variant in variants
        for result in variant["results"]
        if result["status"] == "verified_realization"
    ]
    status = "no_n_zero_realizations"
    if verified:
        status = "verified_realizations"
    elif n_zero_survivors:
        status = "no_verified_realizations"

    evidence = {
        "kind": "single_interface_topology_classification",
        "status": status,
        "scope": {
            "source_topology": "T21 six-phase base-17 certificate",
            "total_moves": len(moves),
            "interfaces_per_phase": 2,
            "allowed_shifts": [-2, -1, 1, 2],
            "fixed_digits": "arbitrary independent values in 0..B-1",
            "repeat_mapping": "0 -> 0 and 16 -> B-1",
        },
        "structural_reduction": {
            "inherited_moves": len(inherited),
            "relevant_phase": 0,
            "scanned_moves": len(relevant),
            "reason": (
                "at n=0 only the wrap output contains repeats, and it targets phase 0"
            ),
            "t24_bases": list(range(18, 41)),
        },
        "inherited_evidence": {
            "file": T24_EVIDENCE.name,
            "sha256": t24_digest,
        },
        "inherited_variants": inherited,
        "solver": {
            "engine": "PicoSAT via pycosat",
            "pycosat_version": getattr(pycosat, "__version__", "unknown"),
        },
        "scan": {
            "base_start": 18,
            "base_stop": 40,
            "instances": len(relevant) * 23,
            "variants": variants,
            "n_zero_survivors": n_zero_survivors,
            "verified_realizations": verified,
        },
        "prism": {
            "model": "qwen3.6:27b-mlx",
            "applications": [
                {
                    "id": "application:0fe7f4314d3eb2e146848f308b389f631b506529af1e23cefa3f12d6f8e6934d",
                    "status": "invalid",
                },
                {
                    "id": "application:a18fe26dad217803b98d9302f2ee61ea287f099c4b65ab1716cf92c00396bc21",
                    "status": "invalid",
                },
                {
                    "id": "application:ea5b80592f8dea1b92191ee186cdab0be1a7eced1b3081fac976ab1e2bdbc9d4",
                    "status": "invalid",
                },
            ],
            "artifacts": [],
        },
        "limitations": [
            "The search covers one moved interface by at most two columns and bases 18..40.",
            "Inherited negatives depend on the exact T24 n=0 obstruction.",
            "Solver agreement is not a checked DRAT or LRAT proof trace.",
        ],
    }
    audit = build_audit()
    audit_variants = audit["variants"]
    if len(audit_variants) != len(variants):
        raise AssertionError("primary and independent variant counts disagree")
    agreement = True
    distinct = True
    for primary_variant, audit_variant in zip(variants, audit_variants):
        if primary_variant["variant_id"] != audit_variant["variant_id"]:
            raise AssertionError("primary and independent variant IDs disagree")
        primary_results = primary_variant["results"]
        audit_results = audit_variant["results"]
        if len(primary_results) != len(audit_results):
            raise AssertionError("primary and independent base counts disagree")
        for primary_result, audit_result in zip(primary_results, audit_results):
            if primary_result["base"] != audit_result["base"]:
                raise AssertionError("primary and independent bases disagree")
            primary_unsat = primary_result["status"] == "infeasible_at_n_zero"
            audit_unsat = audit_result["status"] == "unsatisfiable"
            agreement = agreement and primary_unsat == audit_unsat
            distinct = distinct and (
                primary_result["dimacs_digest"] != audit_result["dimacs_digest"]
            )
    audit["status_agreement"] = agreement
    audit["encodings_distinct"] = distinct
    if not agreement:
        raise AssertionError("primary and independent statuses disagree")
    if not distinct:
        raise AssertionError("primary and independent encodings are not distinct")
    evidence["independent_audit"] = audit
    return evidence


def main() -> None:
    print(json.dumps(build_evidence(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
