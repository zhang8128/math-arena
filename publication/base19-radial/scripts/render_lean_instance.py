#!/usr/bin/env python3
"""Render the canonical equation manifest as transparent Lean data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _atom_variable(atom: dict[str, Any]) -> str | None:
    keys = set(atom)
    if keys == {"variable"} and isinstance(atom["variable"], str):
        return atom["variable"]
    if keys == {"literal"} and type(atom["literal"]) is int:
        return None
    raise ValueError("manifest atom is malformed")


def _append_unique(items: list[str], seen: set[str], value: str | None) -> None:
    if value is not None and value not in seen:
        seen.add(value)
        items.append(value)


def _lean_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _render_atom(atom: dict[str, Any], variable_ids: dict[str, int]) -> str:
    variable = _atom_variable(atom)
    if variable is not None:
        return f".var {variable_ids[variable]}"
    return f".lit {atom['literal']}"


def _render_optional_name(value: Any, variable_ids: dict[str, int]) -> str:
    if value is None:
        return "none"
    if not isinstance(value, str) or value not in variable_ids:
        raise ValueError("manifest carry name is malformed")
    return f"some {variable_ids[value]}"


def render(manifest: dict[str, Any]) -> str:
    if manifest.get("schema") != "base19-radial-equations-v1":
        raise ValueError("unsupported equation manifest schema")
    equations = manifest.get("equations")
    if not isinstance(equations, list) or len(equations) != 409:
        raise ValueError("manifest must contain exactly 409 equations")
    digit_names: list[str] = []
    carry_names: list[str] = []
    seen_digits: set[str] = set()
    seen_carries: set[str] = set()
    for equation in equations:
        if not isinstance(equation, dict):
            raise ValueError("manifest equation is malformed")
        for key in ("left", "right", "target"):
            atom = equation.get(key)
            if not isinstance(atom, dict):
                raise ValueError("manifest equation atom is malformed")
            _append_unique(digit_names, seen_digits, _atom_variable(atom))
        for key in ("carry_in", "carry_out"):
            carry = equation.get(key)
            if carry is not None and not isinstance(carry, str):
                raise ValueError("manifest carry is malformed")
            _append_unique(carry_names, seen_carries, carry)
    if len(digit_names) != 409 or len(carry_names) != 410:
        raise ValueError("manifest active-variable counts changed")
    variable_names = digit_names + carry_names
    variable_ids = {name: index for index, name in enumerate(variable_names)}
    leading = [
        variable_ids[name]
        for phase in range(6)
        if (name := f"p{phase}:f0:d0") in variable_ids
    ]

    lines = [
        "import Base19Radial.Model",
        "",
        "namespace Base19Radial",
        "",
        "def generatedVariableNames : List String := [",
    ]
    lines.extend(f"  {_lean_string(name)}," for name in variable_names[:-1])
    lines.append(f"  {_lean_string(variable_names[-1])}")
    lines.extend(
        [
            "]",
            "",
            "def generatedCandidate : Problem := {",
            "  base := 19",
            "  kinds := List.replicate 409 .digit ++ List.replicate 410 .carry",
            f"  leading := {leading}",
            "  equations := [",
        ]
    )
    for index, equation in enumerate(equations):
        suffix = "," if index + 1 < len(equations) else ""
        lines.extend(
            [
                "    {",
                f"      left := {_render_atom(equation['left'], variable_ids)}",
                f"      right := {_render_atom(equation['right'], variable_ids)}",
                f"      target := {_render_atom(equation['target'], variable_ids)}",
                "      carryIn := "
                + _render_optional_name(equation.get("carry_in"), variable_ids),
                "      carryOut := "
                + _render_optional_name(equation.get("carry_out"), variable_ids),
                f"      provenance := {_lean_string(equation['provenance'])}",
                f"    }}{suffix}",
            ]
        )
    lines.extend(["  ]", "}", "", "end Base19Radial", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest root must be an object")
    args.output.write_text(render(manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
