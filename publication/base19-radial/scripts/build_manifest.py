#!/usr/bin/env python3
"""Build the frozen base-19 equation statement without T26 imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Atom:
    variable: str | None = None
    literal: int | None = None

    def __post_init__(self) -> None:
        if (self.variable is None) == (self.literal is None):
            raise ValueError("an atom is exactly one of variable or literal")

    def row(self) -> dict[str, object]:
        if self.variable is not None:
            return {"variable": self.variable}
        return {"literal": self.literal}


@dataclass(frozen=True)
class Equation:
    provenance: str
    left: Atom
    right: Atom
    target: Atom
    carry_in: str | None
    carry_out: str | None

    def row(self) -> dict[str, object]:
        return {
            "provenance": self.provenance,
            "left": self.left.row(),
            "right": self.right.row(),
            "target": self.target.row(),
            "carry_in": self.carry_in,
            "carry_out": self.carry_out,
        }


@dataclass(frozen=True)
class Phase:
    fragments: tuple[tuple[int, ...], ...]
    repeats: tuple[int, ...]


@dataclass(frozen=True)
class Topology:
    schema: str
    base: int
    phases: tuple[Phase, ...]
    removed_from_seed: str
    canonical_sha256: str


def canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _expect_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _expect_int_list(value: Any, label: str) -> tuple[int, ...]:
    if not isinstance(value, list) or any(type(item) is not int for item in value):
        raise ValueError(f"{label} must be an integer list")
    return tuple(value)


def load_topology(path: Path) -> Topology:
    raw = json.loads(path.read_text(encoding="utf-8"))
    payload = _expect_mapping(raw, "topology")
    if set(payload) != {"schema", "base", "phases", "removed_from_seed"}:
        raise ValueError("topology keys do not match schema v1")
    if payload["schema"] != "base19-radial-topology-v1" or payload["base"] != 19:
        raise ValueError("topology schema or base is not the frozen instance")
    raw_phases = payload["phases"]
    if not isinstance(raw_phases, list) or len(raw_phases) != 6:
        raise ValueError("topology must contain exactly six phases")
    phases = []
    for phase_index, raw_phase in enumerate(raw_phases):
        phase = _expect_mapping(raw_phase, f"phase {phase_index}")
        if set(phase) != {"fragments", "repeats"}:
            raise ValueError(f"phase {phase_index} keys do not match schema v1")
        raw_fragments = phase["fragments"]
        if not isinstance(raw_fragments, list):
            raise ValueError(f"phase {phase_index} fragments must be a list")
        fragments = tuple(
            _expect_int_list(fragment, f"phase {phase_index} fragment {fragment_index}")
            for fragment_index, fragment in enumerate(raw_fragments)
        )
        repeats = _expect_int_list(phase["repeats"], f"phase {phase_index} repeats")
        if len(fragments) != len(repeats) + 1 or any(not fragment for fragment in fragments):
            raise ValueError(f"phase {phase_index} fragment/repeat shape is invalid")
        if any(digit < 0 or digit >= 17 for fragment in fragments for digit in fragment):
            raise ValueError(f"phase {phase_index} contains a non-base-17 fixed digit")
        if any(repeat not in (0, 16) for repeat in repeats):
            raise ValueError(f"phase {phase_index} repeat is not 0 or 16")
        phases.append(Phase(fragments, repeats))
    removed = payload["removed_from_seed"]
    if removed != "phase=5,n=0,column=82":
        raise ValueError("topology records the wrong removed seed equation")
    return Topology(
        schema=payload["schema"],
        base=payload["base"],
        phases=tuple(phases),
        removed_from_seed=removed,
        canonical_sha256=hashlib.sha256(canonical_bytes(payload)).hexdigest(),
    )


def render_phase(topology: Topology, phase: int, n: int) -> tuple[Atom, ...]:
    if phase < 0 or phase >= len(topology.phases) or n < 0:
        raise ValueError("phase and repeat length must be in range")
    word = topology.phases[phase]
    rendered: list[Atom] = []
    for fragment_index, fragment in enumerate(word.fragments):
        if fragment_index:
            repeat = word.repeats[fragment_index - 1]
            literal = topology.base - 1 if repeat == 16 else 0
            rendered.extend(Atom(literal=literal) for _ in range(n))
        rendered.extend(
            Atom(variable=f"p{phase}:f{fragment_index}:d{offset}")
            for offset in range(len(fragment))
        )
    return tuple(rendered)


def _candidate_provenances() -> tuple[str, ...]:
    bands = {
        0: ((0, 33), (48, 82)),
        1: ((0, 33), (49, 82)),
        2: ((0, 33), (49, 82)),
        3: ((0, 33), (49, 82)),
        4: ((0, 33), (49, 82)),
        5: ((0, 33), (49, 83)),
    }
    return tuple(
        f"phase={phase},n=0,column={column}"
        for phase, ranges in bands.items()
        for start, stop in ranges
        for column in range(start, stop + 1)
        if (phase, column) != (5, 82)
    )


def build_equations(topology: Topology) -> list[dict[str, object]]:
    selected = set(_candidate_provenances())
    equations: list[Equation] = []
    for phase in range(6):
        source = render_phase(topology, phase, n=0)
        output_n = 1 if phase == 5 else 0
        output = render_phase(topology, (phase + 1) % 6, n=output_n)
        if len(output) not in (len(source), len(source) + 1):
            raise ValueError(f"phase {phase} has an invalid output length")
        for column in range(len(output)):
            provenance = f"phase={phase},n=0,column={column}"
            if provenance not in selected:
                continue
            left = source[column] if column < len(source) else Atom(literal=0)
            right = source[-1 - column] if column < len(source) else Atom(literal=0)
            equations.append(
                Equation(
                    provenance=provenance,
                    left=left,
                    right=right,
                    target=output[-1 - column],
                    carry_in=(
                        None if column == 0 else f"c:p{phase}:n0:col{column - 1}"
                    ),
                    carry_out=(
                        None
                        if column + 1 == len(output)
                        else f"c:p{phase}:n0:col{column}"
                    ),
                )
            )
    rows = [equation.row() for equation in equations]
    if tuple(row["provenance"] for row in rows) != _candidate_provenances():
        raise ValueError("built equations do not match the frozen candidate order")
    return rows


def build_manifest(topology: Topology) -> dict[str, object]:
    equations = build_equations(topology)
    content: dict[str, object] = {
        "schema": "base19-radial-equations-v1",
        "base": topology.base,
        "topology_sha256": topology.canonical_sha256,
        "equation_count": len(equations),
        "equations": equations,
    }
    content["content_sha256"] = hashlib.sha256(canonical_bytes(content)).hexdigest()
    return content


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("topology", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    topology = load_topology(args.topology)
    args.output.write_bytes(canonical_bytes(build_manifest(topology)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
