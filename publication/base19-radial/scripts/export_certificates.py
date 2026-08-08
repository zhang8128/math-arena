#!/usr/bin/env python3
"""Generate stable publication certificates from the exact T26 radial engine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".timeloop" / "lib"))
sys.path.insert(0, str(ROOT / ".timeloop" / "runs"))

from lychrel_interface_perturbations import InterfaceMove, move_interface  # noqa: E402
from t22_lychrel_affine_lift import base17_reference_cycle  # noqa: E402
from t26_radial_frontier import (  # noqa: E402
    base19_candidate_provenances,
    replay_radial_witness,
    solve_radial_frontier,
)

EQUATIONS = ROOT / "publication" / "base19-radial" / "instance" / "equations.json"
DELETIONS = (
    ROOT / "publication" / "base19-radial" / "certificates" / "deletions.jsonl"
)
KNOWN_DELETION = "phase=0,n=0,column=0"
MINIMAL_CORE_REMOVED = "phase=0,n=0,column=82"


def canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _content_digested(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result["content_sha256"] = hashlib.sha256(canonical_bytes(result)).hexdigest()
    return result


def _validate_content_digest(payload: dict[str, Any]) -> None:
    unsigned = dict(payload)
    expected = unsigned.pop("content_sha256", None)
    actual = hashlib.sha256(canonical_bytes(unsigned)).hexdigest()
    if expected != actual:
        raise ValueError("certificate content digest mismatch")


def _equations_sha256() -> str:
    return hashlib.sha256(EQUATIONS.read_bytes()).hexdigest()


def _moved_words():
    return move_interface(
        base17_reference_cycle(),
        InterfaceMove(0, 0, -2),
    )


def _validate_frontier(
    payload: dict[str, Any],
    *,
    expected_schema: str = "base19-radial-frontier-v1",
    expected_equation_count: int = 409,
) -> None:
    if payload.get("schema") != expected_schema:
        raise ValueError("frontier schema is invalid")
    if (
        payload.get("status") != "UNSAT"
        or payload.get("equation_count") != expected_equation_count
    ):
        raise ValueError("frontier does not certify the expected UNSAT result")
    layers = payload.get("layers")
    if not isinstance(layers, list) or len(layers) != 35:
        raise ValueError("frontier must contain exactly 35 radial layers")
    if layers[0].get("layer") != -1 or layers[-1].get("layer") != 33:
        raise ValueError("frontier layer interval changed")
    if layers[-1].get("output_states") != []:
        raise ValueError("frontier terminal state set is not empty")
    expected_inputs: list[list[int]] = [[]]
    expected_input_variables: list[str] = []
    for expected_layer, layer in zip(range(-1, 34), layers, strict=True):
        provenances = layer.get("equation_provenances")
        input_variables = layer.get("input_variables")
        variables = layer.get("output_variables")
        states = layer.get("output_states")
        transitions = layer.get("transitions")
        if layer.get("layer") != expected_layer:
            raise ValueError("frontier layer order changed")
        if not isinstance(provenances, list) or len(provenances) != layer.get(
            "equation_count"
        ):
            raise ValueError("frontier layer equation coverage is incomplete")
        if (
            not isinstance(input_variables, list)
            or not isinstance(variables, list)
            or not isinstance(states, list)
        ):
            raise ValueError("frontier layer variables or states are malformed")
        if not isinstance(transitions, list) or len(transitions) != layer.get(
            "input_state_count"
        ):
            raise ValueError("frontier transition coverage is incomplete")
        if input_variables != expected_input_variables:
            raise ValueError("frontier layer interfaces are disconnected")
        if layer.get("input_state_count") != len(expected_inputs):
            raise ValueError("frontier input-state count is invalid")
        if layer.get("output_state_count") != len(states):
            raise ValueError("frontier output-state count is invalid")
        if states != sorted(states):
            raise ValueError("frontier states are not in canonical order")
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
            input_state = transition.get("input_state")
            local_outputs = transition.get("output_states")
            if (
                not isinstance(input_state, list)
                or len(input_state) != len(input_variables)
                or not isinstance(local_outputs, list)
                or local_outputs != sorted(local_outputs)
            ):
                raise ValueError("frontier transition is malformed")
            transition_inputs.append(input_state)
            if len({tuple(output) for output in local_outputs}) != len(local_outputs):
                raise ValueError("frontier transition output is duplicated")
            for output in local_outputs:
                if not isinstance(output, list) or len(output) != len(variables):
                    raise ValueError("frontier transition output width is invalid")
                transition_outputs.add(tuple(output))
        if transition_inputs != expected_inputs:
            raise ValueError("frontier transitions do not match the input frontier")
        if transition_outputs != {tuple(state) for state in states}:
            raise ValueError("frontier transitions do not cover the output frontier")
        if layer.get("local_model_count") != sum(
            len(transition["output_states"]) for transition in transitions
        ):
            raise ValueError("frontier local-model count is invalid")
        expected_inputs = states
        expected_input_variables = variables
    if sum(layer["equation_count"] for layer in layers) != expected_equation_count:
        raise ValueError("frontier layer equation counts do not cover the system")


def _validate_minimal_core_frontier(payload: dict[str, Any]) -> None:
    if payload.get("removed") != MINIMAL_CORE_REMOVED:
        raise ValueError("minimal-core frontier removes the wrong equation")
    if payload.get("deletions_sha256") != hashlib.sha256(
        DELETIONS.read_bytes()
    ).hexdigest():
        raise ValueError("minimal-core frontier is not bound to the deletion audit")
    _validate_frontier(
        payload,
        expected_schema="base19-radial-minimal-core-frontier-v1",
        expected_equation_count=408,
    )


def build_frontier_certificate() -> dict[str, Any]:
    evidence = solve_radial_frontier(
        _moved_words(),
        19,
        base19_candidate_provenances(),
        include_certificate=True,
    )
    payload = {
        "schema": "base19-radial-frontier-v1",
        "equations_sha256": _equations_sha256(),
        **evidence,
    }
    _validate_frontier(payload)
    return _content_digested(payload)


def build_minimal_core_frontier_certificate() -> dict[str, Any]:
    provenances = tuple(
        provenance
        for provenance in base19_candidate_provenances()
        if provenance != MINIMAL_CORE_REMOVED
    )
    if len(provenances) != 408:
        raise ValueError("minimal-core provenance set is not 408 equations")
    evidence = solve_radial_frontier(
        _moved_words(),
        19,
        provenances,
        include_certificate=True,
    )
    payload = {
        "schema": "base19-radial-minimal-core-frontier-v1",
        "equations_sha256": _equations_sha256(),
        "deletions_sha256": hashlib.sha256(DELETIONS.read_bytes()).hexdigest(),
        "removed": MINIMAL_CORE_REMOVED,
        **evidence,
    }
    _validate_minimal_core_frontier(payload)
    return _content_digested(payload)


def _validate_witness(payload: dict[str, Any]) -> None:
    if payload.get("schema") != "base19-radial-witness-v1":
        raise ValueError("witness schema is invalid")
    if payload.get("status") != "SAT" or payload.get("equation_count") != 408:
        raise ValueError("witness does not certify the 408-equation neighbor")
    if payload.get("removed") != KNOWN_DELETION:
        raise ValueError("witness records the wrong removed equation")
    expected_replay = {
        "status": "valid",
        "equation_count": 408,
        "digit_count": 409,
        "carry_count": 410,
    }
    if payload.get("witness_replay") != expected_replay:
        raise ValueError("witness exact replay is missing or invalid")
    provenances = tuple(
        provenance
        for provenance in base19_candidate_provenances()
        if provenance != KNOWN_DELETION
    )
    actual_replay = replay_radial_witness(
        _moved_words(),
        19,
        provenances,
        payload.get("witness"),
    )
    if actual_replay != expected_replay:
        raise ValueError("witness exact replay result changed")


def build_witness_certificate() -> dict[str, Any]:
    provenances = tuple(
        provenance
        for provenance in base19_candidate_provenances()
        if provenance != KNOWN_DELETION
    )
    evidence = solve_radial_frontier(
        _moved_words(),
        19,
        provenances,
        include_witness=True,
    )
    payload = {
        "schema": "base19-radial-witness-v1",
        "equations_sha256": _equations_sha256(),
        "removed": KNOWN_DELETION,
        **evidence,
    }
    _validate_witness(payload)
    return _content_digested(payload)


def write_atomic(
    path: Path,
    payload: dict[str, Any],
    validator: Callable[[dict[str, Any]], None],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as stream:
        stream.write(canonical_bytes(payload))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    reopened = json.loads(path.read_text(encoding="utf-8"))
    if reopened != payload:
        raise ValueError("atomic certificate readback differs from validated payload")
    validator(reopened)
    _validate_content_digest(reopened)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frontier", required=True, type=Path)
    parser.add_argument("--witness", required=True, type=Path)
    parser.add_argument("--minimal-core-frontier", type=Path)
    args = parser.parse_args(argv)
    write_atomic(args.frontier, build_frontier_certificate(), _validate_frontier)
    write_atomic(args.witness, build_witness_certificate(), _validate_witness)
    if args.minimal_core_frontier is not None:
        write_atomic(
            args.minimal_core_frontier,
            build_minimal_core_frontier_certificate(),
            _validate_minimal_core_frontier,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
