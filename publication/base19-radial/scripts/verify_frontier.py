#!/usr/bin/env python3
"""Independently replay a base-19 frontier certificate from its equation JSON.

This verifier deliberately imports no exploratory T26 module.  It rebuilds
each layer as a finite QF_LIA problem, enumerates the exact output projection
for every certified input state, and compares the result byte-for-byte with
the serialized transition relation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import z3

BASE = 19
LEADING_DIGIT = re.compile(r"digit:p\d+:f0:d0\Z")


def canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def validate_content_digest(payload: dict[str, Any], label: str) -> None:
    unsigned = dict(payload)
    expected = unsigned.pop("content_sha256", None)
    actual = hashlib.sha256(canonical_bytes(unsigned)).hexdigest()
    if expected != actual:
        raise ValueError(f"{label} content digest mismatch")


def equation_variables(equation: dict[str, Any]) -> tuple[str, ...]:
    variables: list[str] = []
    for name in ("left", "right", "target"):
        atom = equation.get(name)
        if not isinstance(atom, dict):
            raise ValueError(f"equation {name} atom is malformed")
        if set(atom) == {"variable"} and isinstance(atom["variable"], str):
            variables.append(f"digit:{atom['variable']}")
        elif set(atom) != {"literal"} or type(atom["literal"]) is not int:
            raise ValueError(f"equation {name} atom is malformed")
    for name in ("carry_in", "carry_out"):
        carry = equation.get(name)
        if carry is not None:
            if not isinstance(carry, str) or not carry.startswith("c:"):
                raise ValueError(f"equation {name} is malformed")
            variables.append(carry)
    return tuple(dict.fromkeys(variables))


def atom_value(atom: dict[str, Any], variables: dict[str, Any]) -> Any:
    if "literal" in atom:
        return atom["literal"]
    return variables[f"digit:{atom['variable']}"]


def integer_value(variable: str, variables: dict[str, Any]) -> Any:
    expression = variables[variable]
    return z3.If(expression, 1, 0) if variable.startswith("c:") else expression


def state_value(model: z3.ModelRef, variable: str, expression: Any) -> int:
    value = model.eval(expression, model_completion=True)
    return int(z3.is_true(value)) if variable.startswith("c:") else value.as_long()


def check_exact_status(solver: z3.Solver) -> z3.CheckSatResult:
    status = solver.check()
    if status == z3.unknown:
        raise ValueError(f"independent solver returned unknown: {solver.reason_unknown()}")
    return status


def enumerate_outputs(
    equations: list[dict[str, Any]],
    input_variables: list[str],
    input_state: list[int],
    output_variables: list[str],
) -> tuple[list[list[int]], int]:
    local_names = set(input_variables) | set(output_variables)
    for equation in equations:
        local_names.update(equation_variables(equation))
    variables = {
        name: (
            z3.Bool(f"replay_{index}")
            if name.startswith("c:")
            else z3.Int(f"replay_{index}")
        )
        for index, name in enumerate(sorted(local_names))
    }
    solver = z3.SolverFor("QF_LIA")
    solver.set(random_seed=0)
    for name, expression in variables.items():
        if name.startswith("digit:"):
            solver.add(expression >= 0, expression < BASE)
            if LEADING_DIGIT.fullmatch(name):
                solver.add(expression > 0)
    for equation in equations:
        carry_in = equation["carry_in"]
        carry_out = equation["carry_out"]
        solver.add(
            atom_value(equation["left"], variables)
            + atom_value(equation["right"], variables)
            + (integer_value(carry_in, variables) if carry_in is not None else 0)
            == atom_value(equation["target"], variables)
            + BASE
            * (integer_value(carry_out, variables) if carry_out is not None else 0)
        )
    for name, value in zip(input_variables, input_state, strict=True):
        solver.add(variables[name] == (bool(value) if name.startswith("c:") else value))

    outputs: set[tuple[int, ...]] = set()
    model_count = 0
    while check_exact_status(solver) == z3.sat:
        model = solver.model()
        model_count += 1
        output = tuple(
            state_value(model, name, variables[name]) for name in output_variables
        )
        outputs.add(output)
        if not output_variables:
            break
        solver.add(
            z3.Or(
                *(
                    variables[name]
                    != (bool(value) if name.startswith("c:") else value)
                    for name, value in zip(output_variables, output, strict=True)
                )
            )
        )
    return [list(output) for output in sorted(outputs)], model_count


def verify(manifest_path: Path, certificate_path: Path) -> tuple[int, int]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(certificate, dict):
        raise ValueError("manifest and certificate must be JSON objects")
    validate_content_digest(manifest, "manifest")
    validate_content_digest(certificate, "certificate")
    if manifest.get("schema") != "base19-radial-equations-v1":
        raise ValueError("manifest schema is invalid")
    if manifest.get("base") != BASE or certificate.get("base") != BASE:
        raise ValueError("base is not 19")
    if certificate.get("equations_sha256") != hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest():
        raise ValueError("certificate is not bound to the equation manifest")
    removed = certificate.get("removed")
    if not isinstance(removed, str):
        raise ValueError("certificate does not name one removed equation")
    raw_equations = manifest.get("equations")
    if not isinstance(raw_equations, list):
        raise ValueError("manifest equations are malformed")
    equation_map: dict[str, dict[str, Any]] = {}
    for equation in raw_equations:
        if not isinstance(equation, dict) or not isinstance(
            equation.get("provenance"), str
        ):
            raise ValueError("manifest equation is malformed")
        provenance = equation["provenance"]
        if provenance in equation_map:
            raise ValueError("manifest has duplicate equation provenance")
        equation_variables(equation)
        equation_map[provenance] = equation
    if removed not in equation_map:
        raise ValueError("removed equation is absent from the manifest")
    expected_provenances = set(equation_map) - {removed}
    if certificate.get("equation_count") != len(expected_provenances):
        raise ValueError("certificate equation count is invalid")

    layers = certificate.get("layers")
    if not isinstance(layers, list) or not layers:
        raise ValueError("certificate layers are malformed")
    seen: list[str] = []
    equation_layers: dict[str, int] = {}
    occurrences: dict[str, set[int]] = defaultdict(set)
    for layer in layers:
        if not isinstance(layer, dict) or type(layer.get("layer")) is not int:
            raise ValueError("certificate layer is malformed")
        layer_index = layer["layer"]
        provenances = layer.get("equation_provenances")
        if not isinstance(provenances, list) or any(
            not isinstance(item, str) for item in provenances
        ):
            raise ValueError("certificate layer provenance list is malformed")
        for provenance in provenances:
            if provenance not in expected_provenances or provenance in equation_layers:
                raise ValueError("certificate equation coverage is not exact")
            equation_layers[provenance] = layer_index
            seen.append(provenance)
            for variable in equation_variables(equation_map[provenance]):
                occurrences[variable].add(layer_index)
    if set(seen) != expected_provenances or len(seen) != len(expected_provenances):
        raise ValueError("certificate equation coverage is not exact")

    previous_variables: list[str] = []
    previous_states: list[list[int]] = [[]]
    for layer in layers:
        layer_index = layer["layer"]
        input_variables = layer.get("input_variables")
        output_variables = layer.get("output_variables")
        transitions = layer.get("transitions")
        if input_variables != previous_variables:
            raise ValueError("certificate input frontier is disconnected")
        expected_output_variables = sorted(
            variable
            for variable, variable_layers in occurrences.items()
            if any(item <= layer_index for item in variable_layers)
            and any(item > layer_index for item in variable_layers)
        )
        if output_variables != expected_output_variables:
            raise ValueError("certificate output frontier is not the exact live cut")
        if not isinstance(transitions, list) or len(transitions) != len(previous_states):
            raise ValueError("certificate transition coverage is incomplete")
        if [item.get("input_state") for item in transitions] != previous_states:
            raise ValueError("certificate transition inputs are not canonical")
        equations = [equation_map[item] for item in layer["equation_provenances"]]
        layer_outputs: set[tuple[int, ...]] = set()
        layer_model_count = 0
        for transition in transitions:
            certified_outputs = transition.get("output_states")
            if not isinstance(certified_outputs, list):
                raise ValueError("certificate transition outputs are malformed")
            replayed_outputs, model_count = enumerate_outputs(
                equations,
                input_variables,
                transition["input_state"],
                output_variables,
            )
            if replayed_outputs != certified_outputs:
                raise ValueError(
                    f"frontier transition mismatch at layer {layer_index} "
                    f"and input {transition['input_state']}"
                )
            layer_outputs.update(tuple(item) for item in replayed_outputs)
            layer_model_count += model_count
        replayed_layer_outputs = [list(item) for item in sorted(layer_outputs)]
        if replayed_layer_outputs != layer.get("output_states"):
            raise ValueError(f"frontier state mismatch at layer {layer_index}")
        if layer_model_count != layer.get("local_model_count"):
            raise ValueError(f"frontier model count mismatch at layer {layer_index}")
        previous_variables = output_variables
        previous_states = replayed_layer_outputs

    if previous_states:
        raise ValueError("frontier terminal state set is not empty")
    if certificate.get("status") != "UNSAT":
        raise ValueError("empty frontier is not reported as UNSAT")
    return len(expected_provenances), len(layers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("certificate", type=Path)
    args = parser.parse_args(argv)
    equation_count, layer_count = verify(args.manifest, args.certificate)
    print(f"verified {equation_count} equations across {layer_count} layers")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"verification failed: {error}", file=sys.stderr)
        sys.exit(1)
