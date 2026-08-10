#!/usr/bin/env python3
"""Independently audit the achieved T28 layer-31 STOP boundary."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path

_CARRY_RE = re.compile(r"c:p(?P<phase>\d+):n0:col(?P<column>\d+)\Z")
_DIGIT_RE = re.compile(
    r"(?:digit:)?p(?P<phase>\d+):f(?P<fragment>\d+):d(?P<offset>\d+)\Z"
)
_EXPECTED_COUNTS = {30: 18, 31: 18, 32: 22, 33: 0}


class AuditError(RuntimeError):
    pass


def _load(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AuditError(f"cannot load {label}: {error}") from error
    if not isinstance(value, dict):
        raise AuditError(f"{label} must be an object")
    return value


def _canonical_source_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def _content_digest(payload: dict[str, object], label: str) -> str:
    unsigned = dict(payload)
    claimed = unsigned.pop("content_sha256", None)
    actual = hashlib.sha256(_canonical_source_bytes(unsigned)).hexdigest()
    if claimed != actual:
        raise AuditError(f"{label} content digest mismatch")
    return actual


def _canonical_map(variables: tuple[str, ...]) -> dict[str, str]:
    carries: dict[int, list[tuple[int, str]]] = {}
    digits = []
    for variable in variables:
        carry = _CARRY_RE.fullmatch(variable)
        if carry:
            carries.setdefault(int(carry["phase"]), []).append(
                (int(carry["column"]), variable)
            )
            continue
        digit = _DIGIT_RE.fullmatch(variable)
        if not digit:
            raise AuditError(f"malformed frontier variable: {variable}")
        digits.append(
            (
                int(digit["phase"]),
                int(digit["fragment"]),
                int(digit["offset"]),
                variable,
            )
        )
    result: dict[str, str] = {}
    for phase in sorted(carries):
        rows = sorted(carries[phase])
        if len(rows) > 2:
            raise AuditError("more than two carries for one phase")
        for label, (_, variable) in zip(
            (f"L{phase}", f"R{phase}"), rows, strict=False
        ):
            result[variable] = label
    for index, (*_, variable) in enumerate(sorted(digits)):
        if index >= 2:
            raise AuditError("more than two live frontier digits")
        result[variable] = f"D{index}"
    if tuple(result) != variables or len(set(result.values())) != len(result):
        raise AuditError("frontier canonicalization is not bijective")
    return result


def _equation_variables(equation: dict[str, object]) -> tuple[str, ...]:
    names = []
    for side in ("left", "right", "target"):
        atom = equation.get(side)
        if not isinstance(atom, dict):
            raise AuditError("equation atom is invalid")
        if set(atom) == {"variable"} and isinstance(atom["variable"], str):
            names.append("digit:" + atom["variable"])
        elif (
            set(atom) != {"literal"}
            or not isinstance(atom["literal"], int)
            or isinstance(atom["literal"], bool)
        ):
            raise AuditError("equation atom union is invalid")
    for side in ("carry_in", "carry_out"):
        carry = equation.get(side)
        if carry is not None:
            if not isinstance(carry, str) or not _CARRY_RE.fullmatch(carry):
                raise AuditError("equation carry is invalid")
            names.append(carry)
    return tuple(dict.fromkeys(names))


def _atom_value(atom: dict[str, object], assignment: dict[str, int], base: int) -> int:
    if "variable" in atom:
        return assignment["digit:" + str(atom["variable"])]
    literal = atom["literal"]
    if not isinstance(literal, int) or isinstance(literal, bool):
        raise AuditError("equation literal is invalid")
    return base - 1 if literal == 18 else literal


def _equation_holds(
    equation: dict[str, object], assignment: dict[str, int], base: int
) -> bool:
    carry_in = equation["carry_in"]
    carry_out = equation["carry_out"]
    return (
        _atom_value(equation["left"], assignment, base)
        + _atom_value(equation["right"], assignment, base)
        + (0 if carry_in is None else assignment[carry_in])
        - _atom_value(equation["target"], assignment, base)
        - base * (0 if carry_out is None else assignment[carry_out])
        == 0
    )


def _allowed_equation_tuples(
    equation: dict[str, object], domains: dict[str, set[int]], base: int
) -> tuple[tuple[str, ...], tuple[tuple[int, ...], ...]]:
    names = _equation_variables(equation)
    allowed = []
    for values in itertools.product(*(sorted(domains[name]) for name in names)):
        if _equation_holds(equation, dict(zip(names, values, strict=True)), base):
            allowed.append(values)
    if not allowed:
        raise AuditError("local equation has no bounded tuple")
    return names, tuple(allowed)


def _propagate(
    domains: dict[str, set[int]],
    constraints: tuple[tuple[tuple[str, ...], tuple[tuple[int, ...], ...]], ...],
) -> bool:
    changed = True
    while changed:
        changed = False
        for names, allowed in constraints:
            viable = tuple(
                values
                for values in allowed
                if all(
                    value in domains[name]
                    for name, value in zip(names, values, strict=True)
                )
            )
            if not viable:
                return False
            for index, name in enumerate(names):
                reduced = domains[name] & {values[index] for values in viable}
                if not reduced:
                    return False
                if reduced != domains[name]:
                    domains[name] = reduced
                    changed = True
    return True


def _csp_satisfiable(
    domains: dict[str, set[int]],
    constraints: tuple[tuple[tuple[str, ...], tuple[tuple[int, ...], ...]], ...],
) -> bool:
    domains = {name: set(values) for name, values in domains.items()}
    if not _propagate(domains, constraints):
        return False
    unresolved = [name for name, values in domains.items() if len(values) > 1]
    if not unresolved:
        return True
    degree = {
        name: sum(name in constraint_names for constraint_names, _ in constraints)
        for name in unresolved
    }
    branch = min(unresolved, key=lambda name: (len(domains[name]), -degree[name], name))
    for value in sorted(domains[branch]):
        child = {name: set(values) for name, values in domains.items()}
        child[branch] = {value}
        if _csp_satisfiable(child, constraints):
            return True
    return False


def _validate_tail_layers(frontier: dict[str, object]) -> dict[int, dict[str, object]]:
    layers = frontier.get("layers")
    if not isinstance(layers, list):
        raise AuditError("frontier layers are invalid")
    by_number = {
        layer.get("layer"): layer for layer in layers if isinstance(layer, dict)
    }
    for number, expected_count in _EXPECTED_COUNTS.items():
        layer = by_number.get(number)
        if not isinstance(layer, dict):
            raise AuditError(f"frontier omits layer {number}")
        states = layer.get("output_states")
        if not isinstance(states, list) or len(states) != expected_count:
            raise AuditError(f"layer {number} output count changed")
        if layer.get("output_state_count") != expected_count:
            raise AuditError(f"layer {number} declared count changed")
        if states != sorted({tuple(state) for state in states}):
            normalized = [list(state) for state in sorted({tuple(state) for state in states})]
            if states != normalized:
                raise AuditError(f"layer {number} states are not sorted and unique")
        digest = hashlib.sha256(
            json.dumps(states, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        if layer.get("output_states_sha256") != digest:
            raise AuditError(f"layer {number} output digest changed")
    return by_number


def audit(
    equations_path: Path,
    frontier_path: Path,
    evidence_path: Path,
    certificate_path: Path | None = None,
) -> dict[str, object]:
    if certificate_path is not None:
        raise AuditError("STOP evidence must not be accompanied by a certificate")
    manifest = _load(equations_path, "equations")
    frontier = _load(frontier_path, "frontier")
    evidence = _load(evidence_path, "evidence")
    equations_digest = _content_digest(manifest, "equations")
    frontier_digest = _content_digest(frontier, "frontier")
    frozen = evidence.get("frozen_hashes")
    if not isinstance(frozen, dict):
        raise AuditError("evidence frozen hashes are missing")
    if frozen.get("equations") != equations_digest:
        raise AuditError("evidence equation digest mismatch")
    if frozen.get("frontier") != frontier_digest:
        raise AuditError("evidence frontier digest mismatch")
    if frozen.get("provenances") != frontier.get("provenances_sha256"):
        raise AuditError("evidence provenance digest mismatch")
    if evidence.get("schema") != "t28-base19-tail-quotient-evidence-v1":
        raise AuditError("evidence schema changed")
    if (
        evidence.get("status") != "STOP"
        or evidence.get("stop_layer") != 31
        or evidence.get("stop_reason") != "decision_depth_exceeded"
    ):
        raise AuditError("independent checker accepts only the achieved layer-31 STOP")
    expected_grammar = {
        "coefficients": list(range(-3, 4)),
        "moduli": list(range(2, 21)),
        "max_classes": 8,
        "max_nodes": 64,
        "max_depth": 10,
    }
    if evidence.get("grammar_limits") != expected_grammar:
        raise AuditError("grammar or readability limits changed")
    by_number = _validate_tail_layers(frontier)
    candidate_counts = evidence.get("candidate_counts")
    if not isinstance(candidate_counts, dict):
        raise AuditError("candidate counts are missing")
    for number in range(25, 33):
        item = candidate_counts.get(str(number))
        layer = by_number.get(number)
        if not isinstance(item, dict) or not isinstance(layer, dict):
            raise AuditError(f"candidate count for layer {number} is missing")
        if item.get("reachable_state_count") != len(layer["output_states"]):
            raise AuditError(f"candidate count for layer {number} changed")

    counterexample = evidence.get("counterexample")
    if not isinstance(counterexample, dict) or set(counterexample) < {
        "state",
        "rejected_class",
        "obligation",
    }:
        raise AuditError("counterexample is malformed")
    if (
        counterexample["rejected_class"] != "DEAD"
        or counterexample["obligation"] != "dead_has_no_successor"
    ):
        raise AuditError("counterexample obligation changed")
    state = counterexample["state"]
    transfer = by_number[32]
    inputs_raw = transfer.get("input_variables")
    provenances = transfer.get("equation_provenances")
    if not isinstance(state, dict) or not isinstance(inputs_raw, list) or not isinstance(
        provenances, list
    ):
        raise AuditError("layer-31 counterexample scope is malformed")
    original_to_canonical = _canonical_map(tuple(inputs_raw))
    if set(state) != set(original_to_canonical.values()):
        raise AuditError("counterexample variable scope changed")
    if any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 0
        or value >= (2 if name[0] in "LR" else 19)
        for name, value in state.items()
    ):
        raise AuditError("counterexample value is outside its exact domain")

    rows = manifest.get("equations")
    if not isinstance(rows, list) or manifest.get("base") != 19:
        raise AuditError("equation manifest changed")
    by_provenance = {
        row.get("provenance"): row for row in rows if isinstance(row, dict)
    }
    try:
        equations = tuple(by_provenance[name] for name in provenances)
    except KeyError as error:
        raise AuditError(f"local equation is missing: {error.args[0]}") from error
    names = sorted(
        {name for equation in equations for name in _equation_variables(equation)}
    )
    domains = {
        name: set(range(2)) if name.startswith("c:") else set(range(19))
        for name in names
    }
    for original, canonical in original_to_canonical.items():
        domains[original] = {state[canonical]}
    constraints = tuple(
        _allowed_equation_tuples(equation, domains, 19) for equation in equations
    )
    successor_exists = _csp_satisfiable(domains, constraints)
    if not successor_exists:
        raise AuditError("serialized dead-class counterexample has no exact successor")
    return {
        "schema": "t28-base19-tail-quotient-independent-v1",
        "status": "STOP",
        "repository_imports": [],
        "equations_content_sha256": equations_digest,
        "frontier_content_sha256": frontier_digest,
        "primary_evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "certificate_sha256": None,
        "rebuilt_tail_counts": [
            _EXPECTED_COUNTS[number] for number in sorted(_EXPECTED_COUNTS)
        ],
        "exact_obligation_counts": {
            "frontier_state_digests": 4,
            "local_equations": len(equations),
            "counterexample_successor": 1,
        },
        "counterexample_successor_exists": successor_exists,
        "mutation_scope": [
            "source digests",
            "frontier state digests",
            "grammar limits",
            "stop reason",
            "counterexample scope and values",
        ],
        "limitations": [
            "STOP is not an invariant-impossibility theorem.",
            "No certificate exists, so no guard or edge theorem was audited.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("equations", type=Path)
    parser.add_argument("frontier", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("certificate", type=Path, nargs="?")
    arguments = parser.parse_args(argv)
    try:
        result = audit(
            arguments.equations,
            arguments.frontier,
            arguments.evidence,
            arguments.certificate,
        )
    except AuditError as error:
        print(f"REJECT: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
