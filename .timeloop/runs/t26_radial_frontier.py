#!/usr/bin/env python3
"""Exact radial-frontier audit for bounded reverse-add column systems."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from lychrel_arbitrary_topology import (
    ColumnConstraint,
    DigitAtom,
    build_column_constraints,
    render_arbitrary,
)
from lychrel_wordproof import ParametricWord

_PROVENANCE_RE = re.compile(
    r"phase=(?P<phase>\d+),n=0,column=(?P<column>\d+)\Z"
)


@dataclass(frozen=True)
class _RadialProblem:
    base: int
    constraints: dict[str, ColumnConstraint]
    provenances: tuple[str, ...]
    layer_by_provenance: dict[str, int]
    constraints_by_layer: dict[int, tuple[str, ...]]
    occurrence_layers: dict[str, frozenset[int]]
    variable_kinds: dict[str, str]
    leading_digits: frozenset[str]
    first_layer: int
    last_layer: int


def _parse_provenance(provenance: str) -> tuple[int, int]:
    match = _PROVENANCE_RE.fullmatch(provenance)
    if match is None:
        raise ValueError(f"malformed n=0 provenance: {provenance}")
    return int(match["phase"]), int(match["column"])


def _digit_key(atom: DigitAtom) -> str | None:
    return None if atom.variable is None else f"digit:{atom.variable}"


def _constraint_variables(constraint: ColumnConstraint) -> tuple[str, ...]:
    result = []
    for atom in (constraint.left, constraint.right, constraint.target):
        key = _digit_key(atom)
        if key is not None:
            result.append(key)
    for carry in (constraint.carry_in, constraint.carry_out):
        if carry is not None:
            result.append(carry)
    return tuple(dict.fromkeys(result))


def _build_problem(
    words: tuple[ParametricWord, ...],
    base: int,
    provenances: Iterable[str],
) -> _RadialProblem:
    selected = tuple(provenances)
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("provenances must be nonempty and unique")
    constraints = {
        constraint.provenance: constraint
        for constraint in build_column_constraints(
            words,
            base,
            parameters=(0,),
        )
    }
    source_lengths = {
        phase: len(render_arbitrary(words, phase, 0, base))
        for phase in range(len(words))
    }
    layer_by_provenance = {}
    constraints_by_layer: dict[int, list[str]] = defaultdict(list)
    occurrence_layers: dict[str, set[int]] = defaultdict(set)
    variable_kinds: dict[str, str] = {}
    for provenance in selected:
        if provenance not in constraints:
            raise ValueError(f"unknown column provenance: {provenance}")
        phase, column = _parse_provenance(provenance)
        source_length = source_lengths[phase]
        layer = (
            -1
            if column >= source_length
            else min(column, source_length - 1 - column)
        )
        layer_by_provenance[provenance] = layer
        constraints_by_layer[layer].append(provenance)
        for variable in _constraint_variables(constraints[provenance]):
            occurrence_layers[variable].add(layer)
            kind = "digit" if variable.startswith("digit:") else "carry"
            previous = variable_kinds.setdefault(variable, kind)
            if previous != kind:
                raise AssertionError("one semantic variable has conflicting kinds")

    first_layer = min(layer_by_provenance.values())
    last_layer = max(layer_by_provenance.values())
    return _RadialProblem(
        base=base,
        constraints=constraints,
        provenances=selected,
        layer_by_provenance=layer_by_provenance,
        constraints_by_layer={
            layer: tuple(items)
            for layer, items in constraints_by_layer.items()
        },
        occurrence_layers={
            variable: frozenset(layers)
            for variable, layers in occurrence_layers.items()
        },
        variable_kinds=variable_kinds,
        leading_digits=frozenset(
            f"digit:p{phase}:f0:d0" for phase in range(len(words))
        ),
        first_layer=first_layer,
        last_layer=last_layer,
    )


def _frontier(problem: _RadialProblem, layer: int) -> tuple[str, ...]:
    return tuple(
        sorted(
            variable
            for variable, occurrences in problem.occurrence_layers.items()
            if any(item <= layer for item in occurrences)
            and any(item > layer for item in occurrences)
        )
    )


def _state_digest(states: set[tuple[int, ...]]) -> str:
    payload = json.dumps(
        sorted(states),
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _provenance_digest(provenances: tuple[str, ...]) -> str:
    return hashlib.sha256(
        "".join(f"{item}\n" for item in provenances).encode("utf-8")
    ).hexdigest()


def base19_candidate_provenances() -> tuple[str, ...]:
    """Return the frozen 409-column base-19 radial candidate."""
    bands = {
        0: ((0, 33), (48, 82)),
        1: ((0, 33), (49, 82)),
        2: ((0, 33), (49, 82)),
        3: ((0, 33), (49, 82)),
        4: ((0, 33), (49, 82)),
        5: ((0, 33), (49, 83)),
    }
    result = tuple(
        f"phase={phase},n=0,column={column}"
        for phase, ranges in bands.items()
        for start, stop in ranges
        for column in range(start, stop + 1)
        if (phase, column) != (5, 82)
    )
    if len(result) != 409 or len(result) != len(set(result)):
        raise AssertionError("base-19 radial candidate is not 409 unique columns")
    return result


def _load_z3():
    try:
        import z3  # type: ignore
    except ImportError as error:
        raise RuntimeError(
            "radial frontier solving requires the optional z3-solver dependency"
        ) from error
    return z3


class ExactSolverError(RuntimeError):
    """The solver failed to return an exact SAT/UNSAT result."""


def _checked_model(z3_module, solver):
    status = solver.check()
    if status == z3_module.sat:
        return solver.model()
    if status == z3_module.unsat:
        return None
    raise ExactSolverError(f"solver returned unknown: {solver.reason_unknown()}")


def _z3_name(variable: str) -> str:
    return "t26_" + re.sub(r"[^A-Za-z0-9_]", "_", variable)


def _model_value(z3, model, expression, kind: str) -> int:
    value = model.eval(expression, model_completion=True)
    if kind == "carry":
        return int(z3.is_true(value))
    return value.as_long()


def solve_radial_frontier(
    words: tuple[ParametricWord, ...],
    base: int,
    provenances: Iterable[str],
    *,
    include_witness: bool = False,
    include_certificate: bool = False,
) -> dict[str, object]:
    """Project exact local solutions across folded radial frontiers."""
    problem = _build_problem(words, base, provenances)
    z3 = _load_z3()
    variables: dict[str, object] = {}

    def z3_variable(variable: str):
        if variable not in variables:
            variables[variable] = (
                z3.Int(_z3_name(variable))
                if problem.variable_kinds[variable] == "digit"
                else z3.Bool(_z3_name(variable))
            )
        return variables[variable]

    def integer_value(variable: str):
        expression = z3_variable(variable)
        return (
            expression
            if problem.variable_kinds[variable] == "digit"
            else z3.If(expression, 1, 0)
        )

    def atom_value(atom: DigitAtom):
        if atom.variable is None:
            return atom.value
        return z3_variable(f"digit:{atom.variable}")

    states: set[tuple[int, ...]] = {()}
    previous_frontier: tuple[str, ...] = ()
    layer_records = []
    parent_records: dict[
        int,
        dict[tuple[int, ...], tuple[tuple[int, ...], dict[str, int]]],
    ] = {}
    max_digit_frontier = 0
    max_carry_frontier = 0
    max_reachable_states = 1
    processed_layers = []

    for layer in range(problem.first_layer, problem.last_layer + 1):
        output_frontier = _frontier(problem, layer)
        local_variables = set(previous_frontier) | set(output_frontier)
        solver = z3.SolverFor("QF_LIA")
        solver.set(random_seed=0)
        layer_provenances = problem.constraints_by_layer.get(layer, ())
        for provenance in layer_provenances:
            constraint = problem.constraints[provenance]
            local_variables.update(_constraint_variables(constraint))
            solver.add(
                atom_value(constraint.left)
                + atom_value(constraint.right)
                + (
                    integer_value(constraint.carry_in)
                    if constraint.carry_in is not None
                    else 0
                )
                == atom_value(constraint.target)
                + base
                * (
                    integer_value(constraint.carry_out)
                    if constraint.carry_out is not None
                    else 0
                )
            )
        for variable in sorted(local_variables):
            if problem.variable_kinds[variable] != "digit":
                continue
            expression = z3_variable(variable)
            solver.add(expression >= 0, expression < base)
            if variable in problem.leading_digits:
                solver.add(expression > 0)

        input_states = states
        output_states: set[tuple[int, ...]] = set()
        parents = {}
        model_count = 0
        for input_state in sorted(input_states):
            solver.push()
            if len(previous_frontier) != len(input_state):
                raise AssertionError("radial input state has the wrong width")
            for index, variable in enumerate(previous_frontier):
                value = input_state[index]
                solver.add(
                    z3_variable(variable)
                    == (
                        bool(value)
                        if problem.variable_kinds[variable] == "carry"
                        else value
                    )
                )
            while True:
                model = _checked_model(z3, solver)
                if model is None:
                    break
                model_count += 1
                output_state = tuple(
                    _model_value(
                        z3,
                        model,
                        z3_variable(variable),
                        problem.variable_kinds[variable],
                    )
                    for variable in output_frontier
                )
                if output_state not in output_states and include_witness:
                    parents[output_state] = (
                        input_state,
                        {
                            variable: _model_value(
                                z3,
                                model,
                                z3_variable(variable),
                                problem.variable_kinds[variable],
                            )
                            for variable in sorted(local_variables)
                        },
                    )
                output_states.add(output_state)
                if not output_frontier:
                    break
                solver.add(
                    z3.Or(
                        *(
                            z3_variable(variable)
                            != (
                                bool(output_state[index])
                                if problem.variable_kinds[variable] == "carry"
                                else output_state[index]
                            )
                            for index, variable in enumerate(output_frontier)
                        )
                    )
                )
            solver.pop()

        digit_frontier = sum(
            problem.variable_kinds[variable] == "digit"
            for variable in output_frontier
        )
        carry_frontier = len(output_frontier) - digit_frontier
        max_digit_frontier = max(max_digit_frontier, digit_frontier)
        max_carry_frontier = max(max_carry_frontier, carry_frontier)
        max_reachable_states = max(max_reachable_states, len(output_states))
        layer_record: dict[str, object] = {
            "layer": layer,
            "equation_count": len(layer_provenances),
            "input_frontier_size": len(previous_frontier),
            "output_frontier_size": len(output_frontier),
            "output_frontier_digit_count": digit_frontier,
            "output_frontier_carry_count": carry_frontier,
            "input_state_count": len(input_states),
            "output_state_count": len(output_states),
            "local_model_count": model_count,
            "output_states_sha256": _state_digest(output_states),
        }
        if include_certificate:
            layer_record.update(
                {
                    "equation_provenances": list(layer_provenances),
                    "input_variables": list(previous_frontier),
                    "output_variables": list(output_frontier),
                    "output_states": [list(state) for state in sorted(output_states)],
                }
            )
        layer_records.append(layer_record)
        if include_witness:
            parent_records[layer] = parents
        processed_layers.append(layer)
        states = output_states
        previous_frontier = output_frontier
        if not states:
            break

    digit_count = sum(
        kind == "digit" for kind in problem.variable_kinds.values()
    )
    carry_count = len(problem.variable_kinds) - digit_count
    evidence: dict[str, object] = {
        "status": "SAT" if states else "UNSAT",
        "base": base,
        "equation_count": len(problem.provenances),
        "active_digit_count": digit_count,
        "active_carry_count": carry_count,
        "provenances_sha256": _provenance_digest(problem.provenances),
        "z3_version": z3.get_version_string(),
        "max_frontier_digit_count": max_digit_frontier,
        "max_frontier_carry_count": max_carry_frontier,
        "max_reachable_state_count": max_reachable_states,
        "layers": layer_records,
    }
    if not states or not include_witness:
        return evidence

    final_state = min(states)
    assignments: dict[str, int] = {}
    for layer in reversed(processed_layers):
        input_state, local_assignment = parent_records[layer][final_state]
        for variable, value in local_assignment.items():
            if variable in assignments and assignments[variable] != value:
                raise AssertionError("radial witness has an inconsistent overlap")
            assignments[variable] = value
        final_state = input_state
    if final_state:
        raise AssertionError("radial witness did not return to the empty boundary")
    witness = {
        "digits": {
            variable.removeprefix("digit:"): value
            for variable, value in sorted(assignments.items())
            if problem.variable_kinds[variable] == "digit"
        },
        "carries": {
            variable: value
            for variable, value in sorted(assignments.items())
            if problem.variable_kinds[variable] == "carry"
        },
    }
    replay = replay_radial_witness(
        words,
        base,
        problem.provenances,
        witness,
    )
    if replay["status"] != "valid":
        raise AssertionError("radial witness failed exact arithmetic replay")
    evidence["witness"] = witness
    evidence["witness_replay"] = replay
    return evidence


def replay_radial_witness(
    words: tuple[ParametricWord, ...],
    base: int,
    provenances: Iterable[str],
    witness: object,
) -> dict[str, object]:
    """Replay one projected witness with plain exact integer arithmetic."""
    problem = _build_problem(words, base, provenances)
    if not isinstance(witness, dict):
        raise ValueError("witness must be an object")
    digits = witness.get("digits")
    carries = witness.get("carries")
    if not isinstance(digits, dict) or not isinstance(carries, dict):
        raise ValueError("witness digits and carries must be objects")
    expected_digits = {
        variable.removeprefix("digit:")
        for variable, kind in problem.variable_kinds.items()
        if kind == "digit"
    }
    expected_carries = {
        variable
        for variable, kind in problem.variable_kinds.items()
        if kind == "carry"
    }
    if set(digits) != expected_digits or set(carries) != expected_carries:
        raise ValueError("witness variable coverage is incomplete")
    if any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value >= base
        for value in digits.values()
    ):
        raise ValueError("witness digit is outside the target base")
    if any(value not in (0, 1) for value in carries.values()):
        raise ValueError("witness carry is not binary")
    for leading in problem.leading_digits:
        key = leading.removeprefix("digit:")
        if key in digits and digits[key] == 0:
            raise ValueError("witness has a zero leading digit")

    def atom_value(atom: DigitAtom) -> int:
        if atom.variable is None:
            assert atom.value is not None
            return atom.value
        return digits[atom.variable]

    for provenance in problem.provenances:
        constraint = problem.constraints[provenance]
        left = (
            atom_value(constraint.left)
            + atom_value(constraint.right)
            + (
                carries[constraint.carry_in]
                if constraint.carry_in is not None
                else 0
            )
        )
        right = atom_value(constraint.target) + base * (
            carries[constraint.carry_out]
            if constraint.carry_out is not None
            else 0
        )
        if left != right:
            raise ValueError(f"witness violates {provenance}")
    return {
        "status": "valid",
        "equation_count": len(problem.provenances),
        "digit_count": len(digits),
        "carry_count": len(carries),
    }
