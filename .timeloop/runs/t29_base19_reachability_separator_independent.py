#!/usr/bin/env python3
"""Independently audit the frozen T29 base-19 separator artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SOURCE_DIGESTS = {
    "equations": "ff79f31cbc55d7c463e6a14faedaad58d880509d5769e56b9a4bd06ebacd9040",
    "frontier": "0d25cf4645b3c187c74511b0677ea1481c4ba6c923a726ffea9747ee1b4a64c0",
    "provenances": "cac34c9317e8209bfea6a4e4fb37ef204346ccde54424f8c93dd8a8e40619302",
    "t27_evidence": "32324c40903b78aec4d787b7e64a6d73d0999e3846d91ca1340c99f8ac2d8686",
    "t28_evidence": "b0904f68fda4ad7990ac1d474ec157cf671567cdf02869d9ae2cceebe1814e47",
    "t28_independent": "7f095af25afc02ff48fe4d2ee53b4827ba99fa1548a5d970e475780fdaa1639e",
}
REMOVED = "phase=0,n=0,column=82"
TRACE_KEYS = {
    "counts",
    "schema",
    "source_digests",
    "steps",
    "stop_reason",
    "terminal_iteration",
    "variables",
}
DATASET_KEYS = {
    "counts",
    "live_controls",
    "positives",
    "schema",
    "source_digests",
    "trace_negatives",
    "variables",
}
EVIDENCE_KEYS = {
    "base",
    "certificate_sha256",
    "claim_boundary",
    "counts",
    "dataset_sha256",
    "finite_objective",
    "finite_predicate",
    "finite_status",
    "limitations",
    "limits",
    "pool_size",
    "primary_sources",
    "prism",
    "removed",
    "schema",
    "semantic_counterexample",
    "semantic_equation_count",
    "semantic_status",
    "source_digests",
    "status",
    "stop_reason",
    "trace",
    "trace_sha256",
}
CERTIFICATE_KEYS = {
    "base",
    "dataset_sha256",
    "finite_status",
    "predicate",
    "removed",
    "schema",
    "semantic_status",
    "semantic_witness",
    "source_digests",
    "trace_sha256",
}
CARRY_RE = re.compile(r"c:p(?P<phase>\d+):n\d+:col(?P<column>\d+)")
DIGIT_RE = re.compile(r"digit:p(?P<phase>\d+):f(?P<fragment>\d+):d(?P<offset>\d+)")


class Reject(RuntimeError):
    """The isolated audit rejected an input artifact."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def load_object(path: Path, context: str) -> tuple[bytes, dict[str, object]]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError) as error:
        raise Reject(f"cannot read {context}: {error}") from error
    if not isinstance(payload, dict):
        raise Reject(f"{context} must be an object")
    return raw, payload


def require_keys(payload: dict[str, object], expected: set[str], context: str) -> None:
    if set(payload) != expected:
        raise Reject(f"{context} keys differ")


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def source_content_digest(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_bytes(unsigned) + b"\n").hexdigest()


def require_sources(
    equations_raw: bytes,
    equations: dict[str, object],
    frontier_raw: bytes,
    frontier: dict[str, object],
    t28_raw: bytes,
    t28: dict[str, object],
) -> None:
    del equations_raw, frontier_raw
    if source_content_digest(equations) != SOURCE_DIGESTS["equations"]:
        raise Reject("equation content digest changed")
    if source_content_digest(frontier) != SOURCE_DIGESTS["frontier"]:
        raise Reject("frontier content digest changed")
    if frontier.get("provenances_sha256") != SOURCE_DIGESTS["provenances"]:
        raise Reject("frontier provenance digest changed")
    if hashlib.sha256(t28_raw).hexdigest() != SOURCE_DIGESTS["t28_evidence"]:
        raise Reject("T28 evidence raw digest changed")
    if (
        t28.get("schema") != "t28-base19-tail-quotient-evidence-v1"
        or t28.get("status") != "STOP"
        or t28.get("stop_reason") != "decision_depth_exceeded"
        or t28.get("frozen_hashes")
        != {name: SOURCE_DIGESTS[name] for name in SOURCE_DIGESTS if name in {
            "equations", "frontier", "provenances", "t27_evidence"
        }}
    ):
        raise Reject("T28 evidence boundary changed")


def require_source_map(payload: dict[str, object], context: str) -> None:
    if payload.get("source_digests") != SOURCE_DIGESTS:
        raise Reject(f"{context} source identities changed")


def parse_state_rows(
    value: object,
    width: int,
    context: str,
) -> tuple[tuple[int, ...], ...]:
    if not isinstance(value, list):
        raise Reject(f"{context} must be a list")
    rows = []
    for row in value:
        if (
            not isinstance(row, list)
            or len(row) != width
            or any(not is_int(item) for item in row)
        ):
            raise Reject(f"{context} contains a malformed state")
        rows.append(tuple(row))
    result = tuple(rows)
    if result != tuple(sorted(set(result))):
        raise Reject(f"{context} must be sorted and unique")
    return result


def check_trace(
    trace: dict[str, object],
    t28: dict[str, object],
) -> tuple[tuple[str, ...], tuple[tuple[int, ...], ...]]:
    require_keys(trace, TRACE_KEYS, "trace")
    require_source_map(trace, "trace")
    variables = trace.get("variables")
    steps = trace.get("steps")
    if (
        trace.get("schema") != "t29-base19-counterexample-trace-v1"
        or not isinstance(variables, list)
        or variables != sorted(set(variables))
        or len(variables) != 14
        or not all(isinstance(name, str) for name in variables)
        or not isinstance(steps, list)
        or len(steps) != 221
        or trace.get("counts") != {"counterexamples": 221}
        or trace.get("terminal_iteration") != 222
        or trace.get("stop_reason") != "decision_depth_exceeded"
    ):
        raise Reject("trace boundary changed")
    scope = tuple(variables)
    states = []
    step_keys = {
        "candidate_atom_count",
        "input_state",
        "iteration",
        "node_count",
        "obligation",
        "path_depth",
        "rejected_class",
    }
    for expected_iteration, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            raise Reject("trace step must be an object")
        require_keys(step, step_keys, "trace step")
        state = step.get("input_state")
        if (
            step.get("iteration") != expected_iteration
            or step.get("rejected_class") != "DEAD"
            or step.get("obligation") != "dead_has_no_successor"
            or not isinstance(state, dict)
            or set(state) != set(scope)
            or any(not is_int(value) for value in state.values())
            or any(
                not is_int(step.get(name)) or int(step[name]) < 0
                for name in ("candidate_atom_count", "node_count", "path_depth")
            )
        ):
            raise Reject("trace step changed")
        states.append(tuple(state[name] for name in scope))
    if len(set(states)) != 221:
        raise Reject("trace states are not unique")
    counterexample = t28.get("counterexample")
    if not isinstance(counterexample, dict) or not isinstance(
        counterexample.get("state"), dict
    ):
        raise Reject("T28 counterexample is missing")
    if states[-1] != tuple(counterexample["state"][name] for name in scope):
        raise Reject("trace final state disagrees with T28")
    return scope, tuple(states)


def check_dataset(
    dataset: dict[str, object],
    variables: tuple[str, ...],
    trace_states: tuple[tuple[int, ...], ...],
) -> tuple[
    tuple[tuple[int, ...], ...],
    tuple[tuple[int, ...], ...],
    tuple[tuple[int, ...], ...],
]:
    require_keys(dataset, DATASET_KEYS, "dataset")
    require_source_map(dataset, "dataset")
    if (
        dataset.get("schema")
        != "t29-base19-reachability-separator-dataset-v1"
        or dataset.get("variables") != list(variables)
        or dataset.get("counts")
        != {"positives": 12, "trace_negatives": 221, "live_controls": 6}
    ):
        raise Reject("dataset boundary changed")
    positives = parse_state_rows(dataset.get("positives"), 14, "positives")
    negatives = parse_state_rows(
        dataset.get("trace_negatives"), 14, "trace negatives"
    )
    live = parse_state_rows(dataset.get("live_controls"), 14, "live controls")
    if (len(positives), len(negatives), len(live)) != (12, 221, 6):
        raise Reject("dataset counts changed")
    if negatives != tuple(sorted(trace_states)):
        raise Reject("dataset trace negatives disagree with trace")
    if set(positives) & set(negatives) or set(positives) & set(live) or set(negatives) & set(live):
        raise Reject("dataset parts overlap")
    return positives, negatives, live


def validate_atom(atom: object, variables: tuple[str, ...]) -> dict[str, object]:
    if not isinstance(atom, dict):
        raise Reject("predicate atom must be an object")
    relation = atom.get("relation")
    expected = {"relation", "terms", "constant"}
    if relation == "congruent":
        expected.add("modulus")
    require_keys(atom, expected, "predicate atom")
    terms = atom.get("terms")
    if (
        relation not in {"eq", "le", "congruent"}
        or not is_int(atom.get("constant"))
        or not isinstance(terms, list)
        or not 1 <= len(terms) <= 14
    ):
        raise Reject("predicate atom is malformed")
    names = []
    for term in terms:
        if (
            not isinstance(term, list)
            or len(term) != 2
            or term[0] not in variables
            or not is_int(term[1])
            or term[1] == 0
            or abs(term[1]) > 3
        ):
            raise Reject("predicate term is malformed")
        names.append(term[0])
    if names != sorted(set(names)):
        raise Reject("predicate terms are not canonical")
    modulus = atom.get("modulus")
    if relation == "congruent":
        if not is_int(modulus) or not 2 <= int(modulus) <= 20:
            raise Reject("predicate modulus is outside 2..20")
    elif modulus is not None:
        raise Reject("noncongruence atom has a modulus")
    return atom


def validate_predicate(
    predicate: object,
    variables: tuple[str, ...],
) -> dict[str, object]:
    if not isinstance(predicate, dict):
        raise Reject("predicate must be an object")
    require_keys(predicate, {"layer", "variables", "clauses"}, "predicate")
    clauses = predicate.get("clauses")
    if (
        predicate.get("layer") != 31
        or predicate.get("variables") != list(variables)
        or not isinstance(clauses, list)
        or not 1 <= len(clauses) <= 3
    ):
        raise Reject("predicate boundary changed")
    for clause in clauses:
        if not isinstance(clause, dict):
            raise Reject("predicate clause must be an object")
        require_keys(clause, {"atoms"}, "predicate clause")
        atoms = clause.get("atoms")
        if not isinstance(atoms, list) or not 1 <= len(atoms) <= 12:
            raise Reject("predicate clause width changed")
        for atom in atoms:
            validate_atom(atom, variables)
        if atoms != sorted(atoms, key=canonical_bytes):
            raise Reject("predicate atoms are not canonical")
    if clauses != sorted(clauses, key=canonical_bytes):
        raise Reject("predicate clauses are not canonical")
    return predicate


def atom_holds(atom: dict[str, object], assignment: dict[str, int]) -> bool:
    terms = atom["terms"]
    assert isinstance(terms, list)
    total = sum(int(term[1]) * assignment[str(term[0])] for term in terms)
    constant = int(atom["constant"])
    if atom["relation"] == "eq":
        return total == constant
    if atom["relation"] == "le":
        return total <= constant
    return (total - constant) % int(atom["modulus"]) == 0


def predicate_holds(
    predicate: dict[str, object],
    variables: tuple[str, ...],
    state: tuple[int, ...],
) -> bool:
    assignment = dict(zip(variables, state, strict=True))
    clauses = predicate["clauses"]
    assert isinstance(clauses, list)
    return any(
        all(atom_holds(atom, assignment) for atom in clause["atoms"])
        for clause in clauses
    )


def canonical_map(layer: dict[str, object], side: str) -> dict[str, str]:
    variables = layer.get(f"{side}_variables")
    if not isinstance(variables, list) or not all(isinstance(name, str) for name in variables):
        raise Reject("frontier variable list is malformed")
    carries: dict[int, list[tuple[int, str]]] = {}
    digits = []
    for variable in variables:
        carry = CARRY_RE.fullmatch(variable)
        if carry:
            carries.setdefault(int(carry["phase"]), []).append(
                (int(carry["column"]), variable)
            )
            continue
        digit = DIGIT_RE.fullmatch(variable)
        if not digit:
            raise Reject("frontier variable cannot be canonicalized")
        digits.append(
            (
                int(digit["phase"]),
                int(digit["fragment"]),
                int(digit["offset"]),
                variable,
            )
        )
    mapping = {}
    for phase in sorted(carries):
        for label, (_, variable) in zip(
            (f"L{phase}", f"R{phase}"), sorted(carries[phase]), strict=False
        ):
            mapping[variable] = label
    for index, (*_, variable) in enumerate(sorted(digits)):
        mapping[variable] = f"D{index}"
    if set(mapping) != set(variables) or len(set(mapping.values())) != len(mapping):
        raise Reject("frontier canonical scope changed")
    return mapping


def atom_value(atom: object, assignment: dict[str, int], base: int) -> int:
    if not isinstance(atom, dict) or set(atom) not in ({"variable"}, {"literal"}):
        raise Reject("equation atom is malformed")
    if "variable" in atom:
        name = atom["variable"]
        if not isinstance(name, str):
            raise Reject("equation variable is malformed")
        return assignment[f"digit:{name}"]
    literal = atom["literal"]
    if not is_int(literal):
        raise Reject("equation literal is malformed")
    return base - 1 if literal == 18 else int(literal)


def replay_semantic_witness(
    equations_payload: dict[str, object],
    frontier: dict[str, object],
    predicate: dict[str, object],
    witness: object,
    variables: tuple[str, ...],
) -> None:
    if not isinstance(witness, dict) or set(witness) != {
        "input_state", "output_state", "local_state"
    }:
        raise Reject("semantic witness is malformed")
    layers = frontier.get("layers")
    if not isinstance(layers, list):
        raise Reject("frontier layers are missing")
    layer = next(
        (item for item in layers if isinstance(item, dict) and item.get("layer") == 32),
        None,
    )
    if layer is None:
        raise Reject("frontier layer 32 is missing")
    input_map = canonical_map(layer, "input")
    output_map = canonical_map(layer, "output")
    input_state = witness["input_state"]
    output_state = witness["output_state"]
    local_state = witness["local_state"]
    if not all(isinstance(section, dict) for section in (input_state, output_state, local_state)):
        raise Reject("semantic witness sections must be objects")
    expected_input = {f"input:{name}" for name in input_map.values()}
    expected_output = {f"output:{name}" for name in output_map.values()}
    if set(input_state) != expected_input or set(output_state) != expected_output:
        raise Reject("semantic witness frontier scope changed")
    assignment = {
        original: input_state[f"input:{canonical}"]
        for original, canonical in input_map.items()
    }
    assignment.update(
        {
            original: output_state[f"output:{canonical}"]
            for original, canonical in output_map.items()
        }
    )
    for name, value in local_state.items():
        if not isinstance(name, str) or not name.startswith("local:"):
            raise Reject("semantic local name is malformed")
        assignment[name.removeprefix("local:")] = value
    if any(not is_int(value) for value in assignment.values()):
        raise Reject("semantic witness contains a noninteger")
    equations = equations_payload.get("equations")
    provenances = layer.get("equation_provenances")
    if not isinstance(equations, list) or not isinstance(provenances, list):
        raise Reject("semantic equations are missing")
    by_provenance = {
        item.get("provenance"): item for item in equations if isinstance(item, dict)
    }
    selected = []
    for provenance in provenances:
        if provenance not in by_provenance:
            raise Reject("semantic provenance is missing")
        selected.append(by_provenance[provenance])
    if len(selected) != 12:
        raise Reject("semantic equation count changed")
    required_names = set(layer["input_variables"]) | set(layer["output_variables"])
    for equation in selected:
        for side in ("left", "right", "target"):
            atom = equation.get(side)
            if isinstance(atom, dict) and "variable" in atom:
                required_names.add(f"digit:{atom['variable']}")
        for carry in (equation.get("carry_in"), equation.get("carry_out")):
            if carry is not None:
                required_names.add(carry)
    if set(assignment) != required_names:
        raise Reject("semantic witness is not complete")
    for name, value in assignment.items():
        lower = 1 if name.startswith("digit:p") and ":f0:d0" in name else 0
        upper = 1 if name.startswith("c:") else 18
        if not lower <= value <= upper:
            raise Reject("semantic witness violates a variable domain")
    for equation in selected:
        carry_in = equation.get("carry_in")
        carry_out = equation.get("carry_out")
        residual = (
            atom_value(equation.get("left"), assignment, 19)
            + atom_value(equation.get("right"), assignment, 19)
            + (0 if carry_in is None else assignment[carry_in])
            - atom_value(equation.get("target"), assignment, 19)
            - 19 * (0 if carry_out is None else assignment[carry_out])
        )
        if residual != 0:
            raise Reject("semantic witness fails an integer equation")
    canonical_input = tuple(
        input_state[f"input:{name}"] for name in variables
    )
    if not predicate_holds(predicate, variables, canonical_input):
        raise Reject("semantic witness input fails the finite predicate")


def audit(arguments: argparse.Namespace) -> dict[str, object]:
    equations_raw, equations = load_object(arguments.equations, "equations")
    frontier_raw, frontier = load_object(arguments.frontier, "frontier")
    t28_raw, t28 = load_object(arguments.t28_evidence, "T28 evidence")
    _, trace = load_object(arguments.trace, "trace")
    _, dataset = load_object(arguments.dataset, "dataset")
    t29_raw, evidence = load_object(arguments.t29_evidence, "T29 evidence")
    if arguments.certificate is None:
        raise Reject("finite PASS requires a certificate")
    certificate_raw, certificate = load_object(arguments.certificate, "certificate")
    require_sources(equations_raw, equations, frontier_raw, frontier, t28_raw, t28)
    require_keys(evidence, EVIDENCE_KEYS, "T29 evidence")
    require_keys(certificate, CERTIFICATE_KEYS, "certificate")
    require_source_map(evidence, "T29 evidence")
    require_source_map(certificate, "certificate")
    variables, trace_states = check_trace(trace, t28)
    positives, negatives, live = check_dataset(dataset, variables, trace_states)
    trace_digest = hashlib.sha256(canonical_bytes(trace)).hexdigest()
    dataset_digest = hashlib.sha256(canonical_bytes(dataset)).hexdigest()
    if (
        evidence.get("trace_sha256") != trace_digest
        or certificate.get("trace_sha256") != trace_digest
        or evidence.get("dataset_sha256") != dataset_digest
        or certificate.get("dataset_sha256") != dataset_digest
    ):
        raise Reject("trace or dataset digest disagreement")
    if (
        evidence.get("schema")
        != "t29-base19-reachability-separator-evidence-v1"
        or evidence.get("status") != "FINITE_SEPARATOR_PASS_SEMANTIC_STOP"
        or evidence.get("finite_status") != "PASS"
        or evidence.get("semantic_status") != "SAT"
        or evidence.get("stop_reason") != "semantic_successor_found"
        or evidence.get("counts")
        != {"positives": 12, "trace_negatives": 221, "live_controls": 6}
        or evidence.get("pool_size") != 83
        or evidence.get("semantic_equation_count") != 12
    ):
        raise Reject("T29 achieved boundary changed")
    if (
        certificate.get("schema")
        != "t29-base19-reachability-separator-certificate-v1"
        or certificate.get("base") != 19
        or certificate.get("removed") != REMOVED
        or certificate.get("finite_status") != "PASS"
        or certificate.get("semantic_status") != "SAT"
        or evidence.get("certificate_sha256")
        != hashlib.sha256(canonical_bytes(certificate)).hexdigest()
    ):
        raise Reject("certificate identity changed")
    predicate = validate_predicate(certificate.get("predicate"), variables)
    if evidence.get("finite_predicate") != predicate:
        raise Reject("evidence and certificate predicates disagree")
    if any(not predicate_holds(predicate, variables, state) for state in positives):
        raise Reject("finite predicate misses a positive")
    if any(predicate_holds(predicate, variables, state) for state in negatives):
        raise Reject("finite predicate absorbs a trace negative")
    if any(predicate_holds(predicate, variables, state) for state in live):
        raise Reject("finite predicate absorbs a live control")
    witness = certificate.get("semantic_witness")
    if evidence.get("semantic_counterexample") != witness:
        raise Reject("semantic witnesses disagree")
    replay_semantic_witness(equations, frontier, predicate, witness, variables)
    return {
        "schema": "t29-base19-reachability-separator-independent-v1",
        "status": "FINITE_SEPARATOR_PASS_SEMANTIC_STOP",
        "repository_imports": [],
        "source_digests": SOURCE_DIGESTS,
        "primary_evidence_sha256": hashlib.sha256(t29_raw).hexdigest(),
        "certificate_file_sha256": hashlib.sha256(certificate_raw).hexdigest(),
        "trace_sha256": trace_digest,
        "dataset_sha256": dataset_digest,
        "finite_replay_counts": {
            "positives": len(positives),
            "trace_negatives": len(negatives),
            "live_controls": len(live),
        },
        "semantic_equation_count": 12,
        "semantic_successor_replayed": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("equations", type=Path, metavar="EQUATIONS")
    parser.add_argument("frontier", type=Path, metavar="FRONTIER")
    parser.add_argument("t28_evidence", type=Path, metavar="T28_EVIDENCE")
    parser.add_argument("trace", type=Path, metavar="TRACE")
    parser.add_argument("dataset", type=Path, metavar="DATASET")
    parser.add_argument("t29_evidence", type=Path, metavar="T29_EVIDENCE")
    parser.add_argument("certificate", type=Path, nargs="?", metavar="CERTIFICATE")
    return parser


def main() -> None:
    parser = build_parser()
    arguments = parser.parse_args()
    try:
        result = audit(arguments)
    except (Reject, KeyError, TypeError, ValueError) as error:
        print(f"REJECT: {error}", file=sys.stderr)
        raise SystemExit(2) from error
    sys.stdout.buffer.write(canonical_bytes(result) + b"\n")


if __name__ == "__main__":
    main()
