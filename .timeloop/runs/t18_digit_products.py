#!/usr/bin/env python3
"""Enumerate complete low-base dynamics for digit product plus digit sum."""

from __future__ import annotations

import argparse
import json
import sys
from math import prod
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from digitproducts import cycles, digits, product_plus_sum_bound


def _cycle_features(base: int, cycle: tuple[int, ...]) -> dict[str, object]:
    modulus = base - 1
    digit_lists = [digits(n, base) for n in cycle]
    products = [prod(ds) for ds in digit_lists]
    return {
        "values": list(cycle),
        "length": len(cycle),
        "minimum": min(cycle),
        "maximum": max(cycle),
        "digit_lengths": [len(ds) for ds in digit_lists],
        "residues_mod_base_minus_one": [n % modulus for n in cycle],
        "digit_products": products,
        "all_digit_products_zero_mod_base_minus_one": all(
            value % modulus == 0 for value in products
        ),
    }


def discover(max_base: int) -> dict[str, object]:
    if max_base < 2:
        raise ValueError("max_base must be at least 2")
    bases = list(range(2, max_base + 1))
    bounds: dict[str, int] = {}
    cycle_data: dict[str, list[dict[str, object]]] = {}
    first_nonfixed_product_counterexample: dict[str, int] | None = None
    first_fixed_product_counterexample: dict[str, int] | None = None

    for base in bases:
        key = str(base)
        bounds[key] = product_plus_sum_bound(base)
        found = cycles(base)
        cycle_data[key] = [_cycle_features(base, cycle) for cycle in found]
        for cycle in found:
            for n in cycle:
                product = prod(digits(n, base))
                if product % (base - 1) != 0:
                    if len(cycle) == 1 and first_fixed_product_counterexample is None:
                        first_fixed_product_counterexample = {"base": base, "n": n}
                    if len(cycle) > 1 and first_nonfixed_product_counterexample is None:
                        first_nonfixed_product_counterexample = {"base": base, "n": n}

    fixed_holds = first_fixed_product_counterexample is None
    nonfixed_holds = first_nonfixed_product_counterexample is None
    counterexamples = {
        "fixed_point_digit_product_zero_mod_base_minus_one": (
            None if fixed_holds else first_fixed_product_counterexample
        ),
        "nonfixed_cycle_digit_product_zero_mod_base_minus_one": (
            None if nonfixed_holds else first_nonfixed_product_counterexample
        ),
    }
    return {
        "map": "digit_product_plus_sum",
        "bases": bases,
        "bounds": bounds,
        "cycles": cycle_data,
        "candidate_invariants": {
            "fixed_point_digit_product_zero_mod_base_minus_one": fixed_holds,
            "nonfixed_cycle_digit_product_zero_mod_base_minus_one": nonfixed_holds,
        },
        "counterexamples": counterexamples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-base", type=int, required=True)
    args = parser.parse_args()
    json.dump(discover(args.max_base), sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
