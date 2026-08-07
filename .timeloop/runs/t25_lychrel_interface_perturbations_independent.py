#!/usr/bin/env python3
"""Independent binary-CNF audit of T25 phase-zero perturbations."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path


_BINARY_PATH = Path(__file__).with_name(
    "t24_lychrel_arbitrary_topology_independent.py"
)
_BINARY_SPEC = importlib.util.spec_from_file_location(
    "t25_standalone_binary_encoder",
    _BINARY_PATH,
)
if _BINARY_SPEC is None or _BINARY_SPEC.loader is None:
    raise RuntimeError("cannot load the adjacent binary encoder")
_BINARY = importlib.util.module_from_spec(_BINARY_SPEC)
sys.modules[_BINARY_SPEC.name] = _BINARY
_BINARY_SPEC.loader.exec_module(_BINARY)

SOURCE = _BINARY.SOURCE
BinaryCNF = _BINARY.BinaryCNF
load_phases = _BINARY.load_phases
solve_cadical = _BINARY.solve_cadical


SHIFTS = (-2, -1, 1, 2)


def variant_id(interface: int, shift: int) -> str:
    sign = "plus" if shift > 0 else "minus"
    return f"phase0-interface{interface}-{sign}{abs(shift)}"


def move_phase_zero(
    phases: list[dict[str, object]],
    interface: int,
    shift: int,
) -> list[dict[str, object]]:
    """Move one phase-zero boundary using only parsed JSON structures."""
    if interface not in (0, 1) or shift not in SHIFTS:
        raise ValueError("unsupported interface move")
    copied = json.loads(json.dumps(phases))
    fragments = copied[0]["fragments"]
    repeats = copied[0]["repeats"]
    if not isinstance(fragments, list) or not isinstance(repeats, list):
        raise ValueError("phase zero has invalid fragments or repeats")
    if len(fragments) != len(repeats) + 1:
        raise ValueError("phase zero has inconsistent fragments and repeats")
    left = fragments[interface]
    right = fragments[interface + 1]
    if not isinstance(left, list) or not isinstance(right, list):
        raise ValueError("phase-zero fragments must be lists")
    if shift > 0:
        if len(right) <= shift:
            raise ValueError("move would empty the right fragment")
        fragments[interface] = left + right[:shift]
        fragments[interface + 1] = right[shift:]
    else:
        amount = -shift
        if len(left) <= amount:
            raise ValueError("move would empty the left fragment")
        fragments[interface] = left[:-amount]
        fragments[interface + 1] = left[-amount:] + right
    return copied


def build_audit() -> dict[str, object]:
    phases = load_phases()
    version = subprocess.run(
        ["cadical", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    variants = []
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        for interface in (0, 1):
            for shift in SHIFTS:
                moved = move_phase_zero(phases, interface, shift)
                results = []
                for base in range(18, 41):
                    formula = BinaryCNF(base, moved)
                    formula.build()
                    path = temporary / (
                        f"interface{interface}-shift{shift}-base{base}.cnf"
                    )
                    digest = formula.dimacs_digest_and_write(path)
                    results.append(
                        {
                            "base": base,
                            "parameters_checked": 0,
                            "status": solve_cadical(path),
                            "variable_count": len(formula.ids),
                            "clause_count": len(formula.clauses),
                            "dimacs_digest": digest,
                        }
                    )
                variants.append(
                    {
                        "variant_id": variant_id(interface, shift),
                        "phase": 0,
                        "interface": interface,
                        "shift": shift,
                        "fragment_lengths": [
                            len(fragment) for fragment in moved[0]["fragments"]
                        ],
                        "results": results,
                    }
                )

    unsatisfiable = [
        {"variant_id": variant["variant_id"], "base": result["base"]}
        for variant in variants
        for result in variant["results"]
        if result["status"] == "unsatisfiable"
    ]
    satisfiable = [
        {"variant_id": variant["variant_id"], "base": result["base"]}
        for variant in variants
        for result in variant["results"]
        if result["status"] == "satisfiable"
    ]
    return {
        "kind": "independent_binary_interface_audit",
        "implementation": (
            "JSON-only interface movement plus standalone binary full adders"
        ),
        "source": {
            "file": SOURCE.name,
            "sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        },
        "solver": {"engine": "CaDiCaL", "version": version},
        "variants_tested": len(variants),
        "instances_tested": sum(len(item["results"]) for item in variants),
        "variants": variants,
        "unsatisfiable_instances": unsatisfiable,
        "satisfiable_instances": satisfiable,
    }


def main() -> None:
    print(json.dumps(build_audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
