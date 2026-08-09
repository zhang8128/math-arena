#!/usr/bin/env python3
"""Render the 408-equation minimal core as a proof-producing BV problem."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "base19-radial-equations-v1"
REMOVED = "phase=0,n=0,column=82"
SLOT_WIDTH = 6


def canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def validate_digest(payload: dict[str, Any]) -> None:
    unsigned = dict(payload)
    expected = unsigned.pop("content_sha256", None)
    actual = hashlib.sha256(canonical_bytes(unsigned)).hexdigest()
    if expected != actual:
        raise ValueError("equation manifest content digest mismatch")


def atom_variable(atom: object) -> str | None:
    if not isinstance(atom, dict):
        raise ValueError("manifest atom is malformed")
    if set(atom) == {"variable"} and isinstance(atom["variable"], str):
        return atom["variable"]
    if set(atom) == {"literal"} and type(atom["literal"]) is int:
        if not 0 <= atom["literal"] < 19:
            raise ValueError("manifest literal is outside the base-19 digit range")
        return None
    raise ValueError("manifest atom is malformed")


def append_unique(items: list[str], value: str | None) -> None:
    if value is not None and value not in items:
        items.append(value)


def render(manifest: dict[str, Any], manifest_sha256: str) -> str:
    validate_digest(manifest)
    if manifest.get("schema") != SCHEMA or manifest.get("base") != 19:
        raise ValueError("unsupported equation manifest")
    equations = manifest.get("equations")
    if not isinstance(equations, list) or len(equations) != 409:
        raise ValueError("manifest must contain exactly 409 equations")
    if manifest.get("equation_count") != 409:
        raise ValueError("manifest equation count field is invalid")

    removed = [equation for equation in equations if equation.get("provenance") == REMOVED]
    if len(removed) != 1:
        raise ValueError("minimal-core removal is not unique")
    retained = [equation for equation in equations if equation.get("provenance") != REMOVED]
    if len(retained) != 408:
        raise ValueError("minimal core must contain exactly 408 equations")

    digit_names: list[str] = []
    carry_names: list[str] = []
    for equation in retained:
        if not isinstance(equation, dict) or not isinstance(
            equation.get("provenance"), str
        ):
            raise ValueError("manifest equation is malformed")
        for key in ("left", "right", "target"):
            append_unique(digit_names, atom_variable(equation.get(key)))
        for key in ("carry_in", "carry_out"):
            carry = equation.get(key)
            if carry is not None and (
                not isinstance(carry, str) or not carry.startswith("c:")
            ):
                raise ValueError("manifest carry is malformed")
            append_unique(carry_names, carry)
    if len(digit_names) != 409 or len(carry_names) != 410:
        raise ValueError("minimal-core active-variable counts changed")

    variable_names = digit_names + carry_names
    variable_ids = {name: index for index, name in enumerate(variable_names)}

    def slot(name: str) -> str:
        return f"packedSlot assignment {variable_ids[name]}"

    def atom(expression: dict[str, Any]) -> str:
        variable = atom_variable(expression)
        return (
            slot(variable)
            if variable is not None
            else f"({expression['literal']} : BitVec {SLOT_WIDTH})"
        )

    def carry(name: str | None) -> str:
        return (
            f"(0 : BitVec {SLOT_WIDTH})" if name is None else slot(name)
        )

    constraints: list[str] = []
    for name in digit_names:
        constraints.append(f"{slot(name)} < (19 : BitVec {SLOT_WIDTH})")
        if name in {f"p{phase}:f0:d0" for phase in range(6)}:
            constraints.append(f"{slot(name)} ≠ (0 : BitVec {SLOT_WIDTH})")
    for name in carry_names:
        constraints.append(f"{slot(name)} < (2 : BitVec {SLOT_WIDTH})")
    for equation in retained:
        constraints.append(
            f"{atom(equation['left'])} + {atom(equation['right'])} + "
            f"{carry(equation['carry_in'])} = {atom(equation['target'])} + "
            f"(19 : BitVec {SLOT_WIDTH}) * {carry(equation['carry_out'])}"
        )
    if len(constraints) != 1233:
        raise ValueError("minimal-core constraint count changed")

    packed_width = len(variable_names) * SLOT_WIDTH
    lines = [
        "import Std.Tactic.BVDecide",
        "",
        "set_option maxRecDepth 1000000",
        "set_option maxHeartbeats 0",
        "",
        "namespace Base19Radial",
        "",
        f'def packedCoreManifestSha256 : String := "{manifest_sha256}"',
        f'def packedCoreRemovedProvenance : String := "{REMOVED}"',
        "",
        "def packedSlot "
        f"(assignment : BitVec {packed_width}) (index : Nat) : BitVec {SLOT_WIDTH} :=",
        f"  assignment.extractLsb' (index * {SLOT_WIDTH}) {SLOT_WIDTH}",
        "",
        "/--",
        "The frozen 408-equation core has no assignment in its exact finite",
        "six-bit encoding.  `bv_decide` checks a CaDiCaL LRAT certificate with",
        "Lean's proved-sound LRAT checker; `#print axioms` below exposes the",
        "native certificate-evaluation axiom used by the tactic.",
        "-/",
        f"theorem packedMinimalCoreUnsat (assignment : BitVec {packed_width}) : ¬ (",
    ]
    lines.extend(
        f"  {constraint}{' ∧' if index + 1 < len(constraints) else ''}"
        for index, constraint in enumerate(constraints)
    )
    lines.extend(
        [
            ") := by",
            "  bv_decide (config := { timeout := 300 })",
            "",
            "#print axioms packedMinimalCoreUnsat",
            "",
            "end Base19Radial",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest_bytes = args.manifest.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict):
        raise ValueError("equation manifest must be an object")
    source = render(manifest, hashlib.sha256(manifest_bytes).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
