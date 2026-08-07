#!/usr/bin/env python3
"""Validate publication certificates and render transparent Lean literals."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _validate_content_digest(payload: dict[str, Any]) -> None:
    unsigned = dict(payload)
    expected = unsigned.pop("content_sha256", None)
    actual = hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
    if expected != actual:
        raise ValueError("certificate content digest mismatch")


def _validate_frontier(payload: dict[str, Any]) -> None:
    if payload.get("schema") != "base19-radial-frontier-v1":
        raise ValueError("frontier schema is invalid")
    if payload.get("status") != "UNSAT" or payload.get("equation_count") != 409:
        raise ValueError("frontier status or equation count is invalid")
    layers = payload.get("layers")
    if not isinstance(layers, list) or len(layers) != 35:
        raise ValueError("frontier must contain 35 layers")
    for layer in layers:
        if not isinstance(layer, dict):
            raise ValueError("frontier layer is malformed")
        variables = layer.get("output_variables")
        states = layer.get("output_states")
        provenances = layer.get("equation_provenances")
        if not isinstance(variables, list) or not isinstance(states, list):
            raise ValueError("frontier variables or states are malformed")
        if not isinstance(provenances, list) or len(provenances) != layer.get(
            "equation_count"
        ):
            raise ValueError("frontier equation provenance coverage is invalid")
        for state in states:
            if not isinstance(state, list) or len(state) != len(variables):
                raise ValueError("frontier state width is invalid")
            for variable, value in zip(variables, state, strict=True):
                if type(value) is not int:
                    raise ValueError("frontier state contains a non-integer")
                valid = value in (0, 1) if variable.startswith("c:") else 0 <= value < 19
                if not valid:
                    raise ValueError("frontier state is outside its declared domain")
        digest = hashlib.sha256(
            json.dumps(states, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        if digest != layer.get("output_states_sha256"):
            raise ValueError("frontier state digest mismatch")
    if layers[0].get("layer") != -1 or layers[-1].get("layer") != 33:
        raise ValueError("frontier layer interval is invalid")
    if layers[-1].get("output_states") != []:
        raise ValueError("frontier terminal state set is not empty")
    _validate_content_digest(payload)


def _validate_witness(payload: dict[str, Any]) -> None:
    if payload.get("schema") != "base19-radial-witness-v1":
        raise ValueError("witness schema is invalid")
    if payload.get("status") != "SAT" or payload.get("equation_count") != 408:
        raise ValueError("witness status or equation count is invalid")
    if payload.get("removed") != "phase=0,n=0,column=0":
        raise ValueError("witness removed equation is invalid")
    witness = payload.get("witness")
    if not isinstance(witness, dict):
        raise ValueError("witness assignment is missing")
    digits = witness.get("digits")
    carries = witness.get("carries")
    if not isinstance(digits, dict) or len(digits) != 409:
        raise ValueError("witness digit assignment is incomplete")
    if not isinstance(carries, dict) or len(carries) != 410:
        raise ValueError("witness carry assignment is incomplete")
    if any(type(value) is not int or not 0 <= value < 19 for value in digits.values()):
        raise ValueError("witness digit is outside its declared domain")
    if any(value not in (0, 1) for value in carries.values()):
        raise ValueError("witness carry is outside its declared domain")
    _validate_content_digest(payload)


def _lean_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _lean_string_list(values: list[str]) -> str:
    return "[" + ", ".join(_lean_string(value) for value in values) + "]"


def _lean_int_list(values: list[int]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"


def _render_frontier(payload: dict[str, Any], source_sha256: str) -> str:
    lines = [
        "namespace Base19Radial",
        "",
        "structure GeneratedLayerData where",
        "  layer : Int",
        "  equationProvenances : List String",
        "  inputVariables : List String",
        "  outputVariables : List String",
        "  outputStates : List (List Int)",
        "deriving Repr, DecidableEq",
        "",
        f"def frontierSourceSha256 : String := {_lean_string(source_sha256)}",
        "",
    ]
    layers = payload["layers"]
    for index, layer in enumerate(layers):
        lines.append(f"def generatedLayerStates{index} : List (List Int) := [")
        states = layer["output_states"]
        for state_index, state in enumerate(states):
            state_suffix = "," if state_index + 1 < len(states) else ""
            lines.append(f"  {_lean_int_list(state)}{state_suffix}")
        lines.extend(["]", ""])

    lines.append("def generatedLayerData : List GeneratedLayerData := [")
    for index, layer in enumerate(layers):
        suffix = "," if index + 1 < len(layers) else ""
        lines.extend(
            [
                "  {",
                f"    layer := {layer['layer']}",
                "    equationProvenances := "
                + _lean_string_list(layer["equation_provenances"]),
                "    inputVariables := " + _lean_string_list(layer["input_variables"]),
                "    outputVariables := " + _lean_string_list(layer["output_variables"]),
                f"    outputStates := generatedLayerStates{index}",
                f"  }}{suffix}",
            ]
        )
    lines.extend(["]", "", "end Base19Radial", ""])
    return "\n".join(lines)


def _render_witness(payload: dict[str, Any], source_sha256: str) -> str:
    witness = payload["witness"]
    digits = sorted(witness["digits"].items())
    carries = sorted(witness["carries"].items())

    lines = [
        "namespace Base19Radial",
        "",
        f"def witnessSourceSha256 : String := {_lean_string(source_sha256)}",
        "",
        "def generatedWitnessDigits : List (String × Int) := [",  # noqa: RUF001
    ]
    for index, (name, value) in enumerate(digits):
        suffix = "," if index + 1 < len(digits) else ""
        lines.append(f"  ({_lean_string(name)}, {value}){suffix}")
    lines.extend(
        [
            "]",
            "",
            "def generatedWitnessCarries : List (String × Int) := [",  # noqa: RUF001
        ]
    )
    for index, (name, value) in enumerate(carries):
        suffix = "," if index + 1 < len(carries) else ""
        lines.append(f"  ({_lean_string(name)}, {value}){suffix}")
    lines.extend(["]", "", "end Base19Radial", ""])
    return "\n".join(lines)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("certificate root must be an object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontier", required=True, type=Path)
    parser.add_argument("--witness", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    frontier = _load(args.frontier)
    witness = _load(args.witness)
    _validate_frontier(frontier)
    _validate_witness(witness)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frontier_sha = hashlib.sha256(args.frontier.read_bytes()).hexdigest()
    witness_sha = hashlib.sha256(args.witness.read_bytes()).hexdigest()
    (args.output_dir / "FrontierData.lean").write_text(
        _render_frontier(frontier, frontier_sha),
        encoding="utf-8",
    )
    (args.output_dir / "WitnessData.lean").write_text(
        _render_witness(witness, witness_sha),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as error:
        print(f"render_lean_data: {error}", file=sys.stderr)
        sys.exit(1)
