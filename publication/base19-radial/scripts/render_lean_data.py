#!/usr/bin/env python3
"""Validate publication certificates and render transparent Lean literals."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ARTIFACT = Path(__file__).resolve().parents[1]
EQUATIONS = ARTIFACT / "instance" / "equations.json"
FEASIBILITY_LAYERS = (-1, 22, 33)
FEASIBILITY_GROUP_SIZE = 8


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
    expected_inputs: list[list[int]] = [[]]
    expected_input_variables: list[str] = []
    for expected_layer, layer in zip(range(-1, 34), layers, strict=True):
        if not isinstance(layer, dict):
            raise ValueError("frontier layer is malformed")
        variables = layer.get("output_variables")
        states = layer.get("output_states")
        provenances = layer.get("equation_provenances")
        transitions = layer.get("transitions")
        input_variables = layer.get("input_variables")
        if layer.get("layer") != expected_layer:
            raise ValueError("frontier layer order is invalid")
        if not isinstance(variables, list) or not isinstance(states, list):
            raise ValueError("frontier variables or states are malformed")
        if not isinstance(provenances, list) or len(provenances) != layer.get(
            "equation_count"
        ):
            raise ValueError("frontier equation provenance coverage is invalid")
        if not isinstance(transitions, list) or len(transitions) != layer.get(
            "input_state_count"
        ):
            raise ValueError("frontier transition coverage is invalid")
        if not isinstance(input_variables, list):
            raise ValueError("frontier input variables are malformed")
        if input_variables != expected_input_variables:
            raise ValueError("frontier layer interfaces are disconnected")
        if layer.get("input_state_count") != len(expected_inputs):
            raise ValueError("frontier input-state count is invalid")
        if layer.get("output_state_count") != len(states):
            raise ValueError("frontier output-state count is invalid")
        if states != sorted(states) or len({tuple(state) for state in states}) != len(
            states
        ):
            raise ValueError("frontier states are not canonical and unique")
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
        transition_outputs: set[tuple[int, ...]] = set()
        transition_inputs: list[list[int]] = []
        for transition in transitions:
            if not isinstance(transition, dict):
                raise ValueError("frontier transition is malformed")
            input_state = transition.get("input_state")
            outputs = transition.get("output_states")
            if not isinstance(input_state, list) or not isinstance(outputs, list):
                raise ValueError("frontier transition states are malformed")
            if len(input_state) != len(input_variables):
                raise ValueError("frontier transition input width is invalid")
            transition_inputs.append(input_state)
            if outputs != sorted(outputs) or len(
                {tuple(output) for output in outputs}
            ) != len(outputs):
                raise ValueError("frontier transition outputs are not canonical")
            for output in outputs:
                if not isinstance(output, list) or len(output) != len(variables):
                    raise ValueError("frontier transition output width is invalid")
                transition_outputs.add(tuple(output))
        if transition_inputs != expected_inputs:
            raise ValueError("frontier transitions do not match the input frontier")
        if transition_outputs != {tuple(state) for state in states}:
            raise ValueError("frontier transition outputs do not match frontier")
        if layer.get("local_model_count") != sum(
            len(transition["output_states"]) for transition in transitions
        ):
            raise ValueError("frontier local-model count is invalid")
        expected_inputs = states
        expected_input_variables = variables
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


def _atom_variable(atom: dict[str, Any]) -> str | None:
    if set(atom) == {"variable"} and isinstance(atom["variable"], str):
        return f"digit:{atom['variable']}"
    if set(atom) == {"literal"} and type(atom["literal"]) is int:
        return None
    raise ValueError("equation manifest atom is malformed")


def _variable_ids(equations: list[dict[str, Any]]) -> dict[str, int]:
    digits: list[str] = []
    carries: list[str] = []
    seen_digits: set[str] = set()
    seen_carries: set[str] = set()
    for equation in equations:
        for key in ("left", "right", "target"):
            name = _atom_variable(equation[key])
            if name is not None and name not in seen_digits:
                seen_digits.add(name)
                digits.append(name)
        for key in ("carry_in", "carry_out"):
            name = equation[key]
            if name is not None and name not in seen_carries:
                seen_carries.add(name)
                carries.append(name)
    names = digits + carries
    if len(digits) != 409 or len(carries) != 410:
        raise ValueError("equation manifest variable counts changed")
    return {name: index for index, name in enumerate(names)}


def _equation_variables(equation: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("left", "right", "target"):
        name = _atom_variable(equation[key])
        if name is not None:
            names.append(name)
    for key in ("carry_in", "carry_out"):
        name = equation[key]
        if name is not None:
            names.append(name)
    return names


def _kind(name: str) -> str:
    if name.startswith("c:"):
        return ".carry"
    if name in {f"digit:p{phase}:f0:d0" for phase in range(6)}:
        return ".leading"
    return ".digit"


def _lean_kinds(names: list[str]) -> str:
    return "[" + ", ".join(_kind(name) for name in names) + "]"


def _lean_ids(names: list[str], variable_ids: dict[str, int]) -> str:
    return _lean_int_list([variable_ids[name] for name in names])


def _layer_suffix(layer: int) -> str:
    return "Neg1" if layer == -1 else str(layer)


def _local_atom(
    value: dict[str, Any] | str | None,
    locations: dict[str, tuple[str, int]],
) -> str:
    if isinstance(value, dict):
        name = _atom_variable(value)
        if name is None:
            return f".lit {value['literal']}"
    elif value is None:
        return ".lit 0"
    elif isinstance(value, str):
        name = value
    else:
        raise ValueError("equation manifest local atom is malformed")
    location, index = locations[name]
    return f".{location} {index}"


def _render_layer(
    layer: dict[str, Any],
    equations_by_provenance: dict[str, dict[str, Any]],
    variable_ids: dict[str, int],
) -> tuple[list[str], int]:
    input_names = layer["input_variables"]
    output_names = layer["output_variables"]
    local_equations = [
        equations_by_provenance[provenance]
        for provenance in layer["equation_provenances"]
    ]
    interface = set(input_names) | set(output_names)
    hidden_names: list[str] = []
    seen_hidden: set[str] = set()
    for equation in local_equations:
        for name in _equation_variables(equation):
            if name not in interface and name not in seen_hidden:
                seen_hidden.add(name)
                hidden_names.append(name)
    locations = {
        **{name: ("input", index) for index, name in enumerate(input_names)},
        **{name: ("output", index) for index, name in enumerate(output_names)},
        **{name: ("hidden", index) for index, name in enumerate(hidden_names)},
    }
    layer_name = f"generatedLayer{_layer_suffix(layer['layer'])}"
    lines = [
        f"def {layer_name} : Layer := {{",
        f"  inputVariables := {_lean_ids(input_names, variable_ids)}",
        f"  outputVariables := {_lean_ids(output_names, variable_ids)}",
        f"  hiddenVariables := {_lean_ids(hidden_names, variable_ids)}",
        f"  inputKinds := {_lean_kinds(input_names)}",
        f"  outputKinds := {_lean_kinds(output_names)}",
        f"  hiddenKinds := {_lean_kinds(hidden_names)}",
        "  equations := [",
    ]
    for index, equation in enumerate(local_equations):
        suffix = "," if index + 1 < len(local_equations) else ""
        lines.extend(
            [
                "    {",
                f"      left := {_local_atom(equation['left'], locations)}",
                f"      right := {_local_atom(equation['right'], locations)}",
                f"      target := {_local_atom(equation['target'], locations)}",
                f"      carryIn := {_local_atom(equation['carry_in'], locations)}",
                f"      carryOut := {_local_atom(equation['carry_out'], locations)}",
                f"      provenance := {_lean_string(equation['provenance'])}",
                f"    }}{suffix}",
            ]
        )
    lines.extend(["  ]", "}", ""])
    return lines, len(hidden_names)


def _destructure_state(
    variable: str,
    valid_hypothesis: str,
    width: int,
    layer_name: str,
) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    coordinate_names: list[str] = []
    for index in range(width):
        coordinate = f"{variable}{index}"
        coordinate_names.append(coordinate)
        lines.append(f"  rcases {variable} with _ | ⟨{coordinate}, {variable}⟩")
        lines.append(
            f"  · simp [State.validFor, candidate, {layer_name}] at {valid_hypothesis}"
        )
    lines.append(f"  have {variable}Nil : {variable} = [] := by")
    lines.append(f"    cases {variable} with")
    lines.append("    | nil => rfl")
    lines.append("    | cons value values =>")
    lines.append(
        f"        simp [State.validFor, candidate, {layer_name}] at {valid_hypothesis}"
    )
    lines.append(f"  subst {variable}")
    return lines, coordinate_names


def _render_state_lemma(
    layer: dict[str, Any],
    input_state: list[int],
    state_index: int,
    group_index: int,
    output_frontier_name: str,
) -> list[str]:
    suffix = _layer_suffix(layer["layer"])
    layer_name = f"generatedLayer{suffix}"
    theorem_name = f"generatedLayer{suffix}State{state_index}"
    lines = [
        f"theorem {theorem_name} (output : State)",
        f"    (step : Layer.Step candidate {layer_name} {_lean_int_list(input_state)} output) :",
        f"    {output_frontier_name} output := by",
        f"  apply generatedLayer{suffix}Group{group_index}OutputsSubset output",
        f"  apply generatedLayer{suffix}Group{group_index}Transition "
        f"{_lean_int_list(input_state)} output",
        f"  · simp [generatedLayer{suffix}Group{group_index}Inputs]",
        "  · exact step",
        "",
    ]
    return lines


def _render_closed_lemma(
    layer: dict[str, Any],
    input_states: list[list[int]],
    input_frontier_name: str,
    output_frontier_name: str,
) -> list[str]:
    suffix = _layer_suffix(layer["layer"])
    layer_name = f"generatedLayer{suffix}"
    lines = [
        f"theorem generatedLayer{suffix}Closed :",
        f"    Frontier.Closed candidate {layer_name} "
        f"{input_frontier_name} {output_frontier_name} := by",
        "  intro input inputMem output step",
    ]
    coordinates = [f"input{index}" for index in range(len(layer["input_variables"]))]
    for coordinate in coordinates:
        lines.extend(
            [
                f"  rcases input with _ | ⟨{coordinate}, input⟩",
                f"  · simp [{input_frontier_name}] at inputMem",
            ]
        )
    lines.extend(
        [
            "  have inputNil : input = [] := by",
            "    cases input with",
            "    | nil => rfl",
            "    | cons value values =>",
            f"        simp [{input_frontier_name}] at inputMem",
            "  subst input",
        ]
    )
    trie = _trie_expression(input_states, coordinates, 0, 2)
    lines.append(f"  change {trie} at inputMem")
    state_indices = {tuple(state): index for index, state in enumerate(input_states)}
    lines.extend(
        _render_trie_dispatch(
            input_states, coordinates, 0, state_indices, suffix, 2
        )
    )
    lines.append("")
    return lines


def _render_group_lemmas(
    layer: dict[str, Any],
    group_index: int,
    input_states: list[list[int]],
    output_states: list[list[int]],
    global_output_frontier: str,
    hidden_width: int,
) -> list[str]:
    suffix = _layer_suffix(layer["layer"])
    layer_name = f"generatedLayer{suffix}"
    input_name = f"generatedLayer{suffix}Group{group_index}Inputs"
    output_name = f"generatedLayer{suffix}Group{group_index}Outputs"
    lines = _render_frontier_predicate(
        input_name, input_states, len(layer["input_variables"])
    )
    lines.extend(
        _render_frontier_predicate(
            output_name, output_states, len(layer["output_variables"])
        )
    )
    lines.extend(
        [
            f"theorem generatedLayer{suffix}Group{group_index}Transition "
            "(input output : State)",
            f"    (inputMem : {input_name} input)",
            f"    (step : Layer.Step candidate {layer_name} input output) :",
            f"    {output_name} output := by",
            "  rcases step with ⟨hidden, inputValid, outputValid, hiddenValid, equations⟩",
        ]
    )
    input_lines, _ = _destructure_state(
        "input", "inputValid", len(layer["input_variables"]), layer_name
    )
    output_lines, _ = _destructure_state(
        "output", "outputValid", len(layer["output_variables"]), layer_name
    )
    hidden_lines, _ = _destructure_state(
        "hidden", "hiddenValid", hidden_width, layer_name
    )
    lines.extend(input_lines)
    lines.extend(output_lines)
    lines.extend(hidden_lines)
    lines.extend(
        [
            "  rw [generatedCandidateBase] at inputValid outputValid hiddenValid equations",
            f"  simp [State.validFor, {layer_name}] "
            "at inputValid outputValid hiddenValid",
            f"  simp [{input_name}] at inputMem",
            f"  simp [{layer_name}, LocalColumn.check, LocalAtom.eval] at equations",
            f"  simp [{output_name}]",
            "  omega",
            "",
            f"theorem generatedLayer{suffix}Group{group_index}OutputsSubset "
            "(output : State)",
            f"    (outputMem : {output_name} output) :",
            f"    {global_output_frontier} output := by",
        ]
    )
    output_coordinates = [
        f"output{index}" for index in range(len(layer["output_variables"]))
    ]
    for coordinate in output_coordinates:
        lines.extend(
            [
                f"  rcases output with _ | ⟨{coordinate}, output⟩",
                f"  · simp [{output_name}] at outputMem",
            ]
        )
    lines.extend(
        [
            "  have outputNil : output = [] := by",
            "    cases output with",
            "    | nil => rfl",
            "    | cons value values =>",
            f"        simp [{output_name}] at outputMem",
            "  subst output",
        ]
    )
    output_trie = _trie_expression(output_states, output_coordinates, 0, 2)
    lines.append(f"  change {output_trie} at outputMem")
    lines.extend(
        _render_inclusion_dispatch(
            output_states,
            output_coordinates,
            0,
            global_output_frontier,
            2,
        )
    )
    lines.append("")
    return lines


def _render_inclusion_dispatch(
    states: list[list[int]],
    coordinates: list[str],
    index: int,
    global_frontier: str,
    indent: int,
) -> list[str]:
    padding = " " * indent
    if not states:
        return [f"{padding}contradiction"]
    if index == len(coordinates):
        return [f"{padding}simp [{global_frontier}]"]
    groups: dict[int, list[list[int]]] = {}
    for state in states:
        groups.setdefault(state[index], []).append(state)
    lines: list[str] = []
    ordered_groups = sorted(groups.items())
    for _value, group in ordered_groups[:-1]:
        lines.extend(
            [
                f"{padding}rcases outputMem with branch | outputMem",
                f"{padding}· rcases branch with ⟨coordinateEq, outputMem⟩",
                f"{padding}  subst {coordinates[index]}",
            ]
        )
        lines.extend(
            _render_inclusion_dispatch(
                group,
                coordinates,
                index + 1,
                global_frontier,
                indent + 2,
            )
        )
    _last_value, last_group = ordered_groups[-1]
    lines.extend(
        [
            f"{padding}rcases outputMem with ⟨coordinateEq, outputMem⟩",
            f"{padding}subst {coordinates[index]}",
        ]
    )
    lines.extend(
        _render_inclusion_dispatch(
            last_group,
            coordinates,
            index + 1,
            global_frontier,
            indent,
        )
    )
    return lines


def _render_trie_dispatch(
    states: list[list[int]],
    coordinates: list[str],
    index: int,
    state_indices: dict[tuple[int, ...], int],
    layer_suffix: str,
    indent: int,
) -> list[str]:
    padding = " " * indent
    if not states:
        return [f"{padding}contradiction"]
    if index == len(coordinates):
        if len(states) != 1:
            raise ValueError("frontier trie leaf is not unique")
        state_index = state_indices[tuple(states[0])]
        return [
            f"{padding}exact generatedLayer{layer_suffix}State{state_index} output step"
        ]
    groups: dict[int, list[list[int]]] = {}
    for state in states:
        groups.setdefault(state[index], []).append(state)
    lines: list[str] = []
    ordered_groups = sorted(groups.items())
    for _value, group in ordered_groups[:-1]:
        lines.extend(
            [
                f"{padding}rcases inputMem with branch | inputMem",
                f"{padding}· rcases branch with ⟨coordinateEq, inputMem⟩",
                f"{padding}  subst {coordinates[index]}",
            ]
        )
        lines.extend(
            _render_trie_dispatch(
                group,
                coordinates,
                index + 1,
                state_indices,
                layer_suffix,
                indent + 2,
            )
        )
    _last_value, last_group = ordered_groups[-1]
    lines.extend(
        [
            f"{padding}rcases inputMem with ⟨coordinateEq, inputMem⟩",
            f"{padding}subst {coordinates[index]}",
        ]
    )
    lines.extend(
        _render_trie_dispatch(
            last_group,
            coordinates,
            index + 1,
            state_indices,
            layer_suffix,
            indent,
        )
    )
    return lines


def _trie_expression(
    states: list[list[int]], coordinates: list[str], index: int, indent: int
) -> str:
    if not states:
        return "False"
    if index == len(coordinates):
        return "True"
    groups: dict[int, list[list[int]]] = {}
    for state in states:
        groups.setdefault(state[index], []).append(state)
    padding = " " * indent
    child_padding = " " * (indent + 2)
    branches = []
    for value, group in sorted(groups.items()):
        child = _trie_expression(group, coordinates, index + 1, indent + 2)
        branches.append(f"{coordinates[index]} = {value} ∧ ({child})")
    separator = f" ∨\n{child_padding}"  # noqa: RUF001
    return f"(\n{child_padding}" + separator.join(branches) + f"\n{padding})"


def _render_frontier_predicate(
    name: str, states: list[list[int]], width: int
) -> list[str]:
    if any(len(state) != width for state in states):
        raise ValueError("frontier predicate state width is inconsistent")
    coordinates = [f"x{index}" for index in range(width)]
    pattern = "[" + ", ".join(coordinates) + "]"
    expression = _trie_expression(states, coordinates, 0, 4)
    return [
        f"def {name} : Frontier.Set := fun state =>",
        "  match state with",
        f"  | {pattern} => {expression}",
        "  | _ => False",
        "",
    ]


def _render_frontier_proofs(
    frontier: dict[str, Any], equations_manifest: dict[str, Any]
) -> str:
    equations = equations_manifest.get("equations")
    if not isinstance(equations, list) or len(equations) != 409:
        raise ValueError("equation manifest must contain 409 equations")
    variable_ids = _variable_ids(equations)
    by_provenance = {equation["provenance"]: equation for equation in equations}
    layers = frontier["layers"]
    lines = [
        "import Base19Radial.Radial",
        "import Base19Radial.Instance",
        "import Base19Radial.Generated.FrontierData",
        "",
        "set_option maxRecDepth 100000",
        "set_option maxHeartbeats 2000000",
        "",
        "namespace Base19Radial",
        "",
        "theorem generatedCandidateBase : candidate.base = 19 := rfl",
        "",
    ]
    frontier_specs: dict[str, tuple[list[list[int]], int]] = {}
    for certificate_index, layer in enumerate(layers):
        if layer["layer"] not in FEASIBILITY_LAYERS:
            continue
        if certificate_index == 0:
            frontier_specs["generatedInitialFrontier"] = ([[]], 0)
        else:
            previous = layers[certificate_index - 1]
            frontier_specs[f"generatedFrontier{certificate_index - 1}"] = (
                previous["output_states"],
                len(previous["output_variables"]),
            )
        frontier_specs[f"generatedFrontier{certificate_index}"] = (
            layer["output_states"],
            len(layer["output_variables"]),
        )
    for name, (states, width) in frontier_specs.items():
        lines.extend(_render_frontier_predicate(name, states, width))

    for certificate_index, layer in enumerate(layers):
        if layer["layer"] not in FEASIBILITY_LAYERS:
            continue
        layer_lines, hidden_width = _render_layer(
            layer, by_provenance, variable_ids
        )
        lines.extend(layer_lines)
        if certificate_index == 0:
            input_states = [[]]
            input_frontier_name = "generatedInitialFrontier"
        else:
            input_states = layers[certificate_index - 1]["output_states"]
            input_frontier_name = f"generatedFrontier{certificate_index - 1}"
        output_frontier_name = f"generatedFrontier{certificate_index}"
        transitions = layer["transitions"]
        if len(transitions) != len(input_states):
            raise ValueError("frontier transition count does not match inputs")
        groups: list[tuple[list[list[int]], list[list[int]]]] = []
        for group_start in range(0, len(input_states), FEASIBILITY_GROUP_SIZE):
            group_inputs = input_states[
                group_start : group_start + FEASIBILITY_GROUP_SIZE
            ]
            group_transitions = transitions[
                group_start : group_start + FEASIBILITY_GROUP_SIZE
            ]
            group_outputs = sorted(
                {
                    tuple(output)
                    for transition in group_transitions
                    for output in transition["output_states"]
                }
            )
            groups.append((group_inputs, [list(output) for output in group_outputs]))
        for group_index, (group_inputs, group_outputs) in enumerate(groups):
            lines.extend(
                _render_group_lemmas(
                    layer,
                    group_index,
                    group_inputs,
                    group_outputs,
                    output_frontier_name,
                    hidden_width,
                )
            )
        for state_index, input_state in enumerate(input_states):
            transition = transitions[state_index]
            if transition["input_state"] != input_state:
                raise ValueError("frontier transition input order changed")
            lines.extend(
                _render_state_lemma(
                    layer,
                    input_state,
                    state_index,
                    state_index // FEASIBILITY_GROUP_SIZE,
                    output_frontier_name,
                )
            )
        lines.extend(
            _render_closed_lemma(
                layer,
                input_states,
                input_frontier_name,
                output_frontier_name,
            )
        )
    lines.extend(["end Base19Radial", ""])
    return "\n".join(lines)


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
    parser.add_argument(
        "--experimental-frontier-proofs",
        action="store_true",
        help="render the concrete Lean closure experiment that failed the resource gate",
    )
    args = parser.parse_args(argv)
    frontier = _load(args.frontier)
    witness = _load(args.witness)
    equations_manifest = _load(EQUATIONS)
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
    if args.experimental_frontier_proofs:
        (args.output_dir / "FrontiersExperimental.lean").write_text(
            _render_frontier_proofs(frontier, equations_manifest),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ValueError as error:
        print(f"render_lean_data: {error}", file=sys.stderr)
        sys.exit(1)
