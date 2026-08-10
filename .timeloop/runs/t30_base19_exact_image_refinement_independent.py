#!/usr/bin/env python3
"""Independently audit the frozen T30 exact-image refinement artifacts."""

from __future__ import annotations

import argparse
import hashlib
import itertools
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
T29_DIGESTS = {
    "certificate": "1c234891f001cb3a59e5670560ab26e3cb248a943e249aee049aac7d32c7db5a",
    "dataset": "6603e381805db845ef9388d234e36f31eba510d838ac98c143c238c2ff144995",
    "evidence": "c1e3dc4bc4ab07207a6ab49d6a9c9fd86486013abeaf016b6ecd59c9755e1d32",
    "independent": "9f926208cc7416e24d811f6cd54485d19741b6f8ffe44f3b365b2f816e579644",
    "trace": "c56877975293c10575009a691b1d1bbde376838f805d232a2c18a4d00b2c4715",
}
REMOVED = "phase=0,n=0,column=82"
VARIABLES = (
    "D0",
    "D1",
    "L0",
    "L1",
    "L2",
    "L3",
    "L4",
    "L5",
    "R0",
    "R1",
    "R2",
    "R3",
    "R4",
    "R5",
)
CARRY_RE = re.compile(r"c:p(?P<phase>\d+):n\d+:col(?P<column>\d+)\Z")
DIGIT_RE = re.compile(
    r"(?:digit:)?p(?P<phase>\d+):f(?P<fragment>\d+):d(?P<offset>\d+)\Z"
)


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
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Reject(f"cannot read {context}: {error}") from error
    if not isinstance(payload, dict):
        raise Reject(f"{context} must be an object")
    return raw, payload


def require_keys(payload: dict[str, object], expected: set[str], context: str) -> None:
    if set(payload) != expected:
        raise Reject(f"{context} keys differ")


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def raw_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def content_digest(payload: dict[str, object]) -> str:
    unsigned = dict(payload)
    unsigned.pop("content_sha256", None)
    return hashlib.sha256(canonical_bytes(unsigned) + b"\n").hexdigest()


def canonical_map(variables: tuple[str, ...]) -> dict[str, str]:
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
            raise Reject(f"malformed frontier variable: {variable}")
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
        for label, (_, variable) in zip(
            (f"L{phase}", f"R{phase}"), sorted(carries[phase]), strict=False
        ):
            result[variable] = label
    for index, (*_, variable) in enumerate(sorted(digits)):
        if index >= 2:
            raise Reject("frontier has more than two live digits")
        result[variable] = f"D{index}"
    if tuple(result) != variables or len(set(result.values())) != len(result):
        raise Reject("frontier canonicalization is not bijective")
    return result


def atom_holds(atom: dict[str, object], state: dict[str, int]) -> bool:
    expected = {"relation", "terms", "constant"}
    if atom.get("relation") == "congruent":
        expected.add("modulus")
    require_keys(atom, expected, "predicate atom")
    relation = atom["relation"]
    terms = atom["terms"]
    constant = atom["constant"]
    if (
        relation not in {"eq", "le", "congruent"}
        or not isinstance(terms, list)
        or not terms
        or not is_int(constant)
    ):
        raise Reject("predicate atom values are invalid")
    total = 0
    seen = set()
    for term in terms:
        if not isinstance(term, list) or len(term) != 2:
            raise Reject("predicate term is invalid")
        name, coefficient = term
        if (
            not isinstance(name, str)
            or name in seen
            or name not in state
            or not is_int(coefficient)
            or coefficient == 0
            or abs(coefficient) > 3
        ):
            raise Reject("predicate term is outside the closed grammar")
        seen.add(name)
        total += coefficient * state[name]
    if relation == "eq":
        return total == constant
    if relation == "le":
        return total <= constant
    modulus = atom.get("modulus")
    if not is_int(modulus) or not 2 <= modulus <= 20:
        raise Reject("predicate modulus is outside the closed grammar")
    return (total - constant) % modulus == 0


def predicate_holds(predicate: dict[str, object], state: dict[str, int]) -> bool:
    require_keys(predicate, {"layer", "variables", "clauses"}, "predicate")
    clauses = predicate["clauses"]
    if predicate["layer"] != 31 or predicate["variables"] != list(VARIABLES):
        raise Reject("predicate scope changed")
    if not isinstance(clauses, list) or not clauses:
        raise Reject("predicate clauses are invalid")
    for clause in clauses:
        if not isinstance(clause, dict):
            raise Reject("predicate clause is invalid")
        require_keys(clause, {"atoms"}, "predicate clause")
        atoms = clause["atoms"]
        if not isinstance(atoms, list) or not 1 <= len(atoms) <= 12:
            raise Reject("predicate clause exceeds the atom budget")
    return any(all(atom_holds(atom, state) for atom in clause["atoms"]) for clause in clauses)


def require_q0(predicate: dict[str, object]) -> None:
    predicate_holds(predicate, {name: 0 for name in VARIABLES})
    clauses = predicate["clauses"]
    if len(clauses) != 1 or len(clauses[0]["atoms"]) != 5:
        raise Reject("Q0 must be one five-atom conjunction")
    atoms = clauses[0]["atoms"]
    if any(atom.get("relation") != "eq" for atom in atoms):
        raise Reject("Q0 must contain only equalities")
    supports = [len(atom["terms"]) for atom in atoms]
    if max(supports) != 11 or sum(supports) != 34:
        raise Reject("Q0 support changed")
    expected = {
        (("L1", 1), ("L4", -1), ("L5", 1), ("R4", -1), 0),
        (
            ("L1", 1),
            ("L2", -2),
            ("L4", -2),
            ("L5", -2),
            ("R1", -3),
            ("R2", 3),
            ("R3", 2),
            ("R4", 1),
            0,
        ),
        (("L0", 3), ("L1", 1), ("L2", 2), ("L5", -2), ("R1", -3), ("R3", 1), 3),
        (
            ("D1", 1),
            ("L0", 3),
            ("L1", -2),
            ("L2", -3),
            ("L3", 1),
            ("L4", 1),
            ("R0", -1),
            ("R1", -3),
            ("R2", -3),
            ("R3", 3),
            ("R4", -1),
            9,
        ),
        (("D0", 1), ("D1", -1), ("L0", -1), ("R0", 1), ("R5", 1), 1),
    }
    actual = {
        (*tuple((term[0], term[1]) for term in atom["terms"]), atom["constant"])
        for atom in atoms
    }
    if actual != expected:
        raise Reject("Q0 equations changed")


def equation_variables(equation: dict[str, object]) -> tuple[str, ...]:
    names = []
    for side in ("left", "right", "target"):
        atom = equation.get(side)
        if not isinstance(atom, dict):
            raise Reject("equation atom is invalid")
        if set(atom) == {"variable"} and isinstance(atom["variable"], str):
            names.append("digit:" + atom["variable"])
        elif set(atom) != {"literal"} or not is_int(atom.get("literal")):
            raise Reject("equation atom union is invalid")
    for side in ("carry_in", "carry_out"):
        carry = equation.get(side)
        if carry is not None:
            if not isinstance(carry, str) or not CARRY_RE.fullmatch(carry):
                raise Reject("equation carry is invalid")
            names.append(carry)
    return tuple(dict.fromkeys(names))


def atom_value(atom: dict[str, object], assignment: dict[str, int], base: int) -> int:
    if "variable" in atom:
        return assignment["digit:" + str(atom["variable"])]
    literal = atom["literal"]
    if not is_int(literal):
        raise Reject("equation literal is invalid")
    return base - 1 if literal == 18 else literal


def equation_holds(
    equation: dict[str, object], assignment: dict[str, int], base: int
) -> bool:
    carry_in = equation["carry_in"]
    carry_out = equation["carry_out"]
    return (
        atom_value(equation["left"], assignment, base)
        + atom_value(equation["right"], assignment, base)
        + (0 if carry_in is None else assignment[carry_in])
        - atom_value(equation["target"], assignment, base)
        - base * (0 if carry_out is None else assignment[carry_out])
        == 0
    )


Constraint = tuple[tuple[str, ...], tuple[tuple[int, ...], ...]]


def allowed_equation_tuples(
    equation: dict[str, object], domains: dict[str, set[int]], base: int
) -> Constraint:
    names = equation_variables(equation)
    allowed = []
    for values in itertools.product(*(sorted(domains[name]) for name in names)):
        assignment = dict(zip(names, values, strict=True))
        if equation_holds(equation, assignment, base):
            allowed.append(values)
    if not allowed:
        raise Reject("equation has no bounded tuple")
    return names, tuple(allowed)


def allowed_atom_tuples(
    atom: dict[str, object],
    canonical_to_original: dict[str, str],
    domains: dict[str, set[int]],
) -> Constraint:
    names = tuple(canonical_to_original[term[0]] for term in atom["terms"])
    allowed = []
    for values in itertools.product(*(sorted(domains[name]) for name in names)):
        state = {
            canonical: value
            for canonical, original in canonical_to_original.items()
            for name, value in zip(names, values, strict=True)
            if original == name
        }
        if atom_holds(atom, state):
            allowed.append(values)
    return names, tuple(allowed)


def propagate(domains: dict[str, set[int]], constraints: tuple[Constraint, ...]) -> bool:
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
                supported = {values[index] for values in viable}
                reduced = domains[name] & supported
                if not reduced:
                    return False
                if reduced != domains[name]:
                    domains[name] = reduced
                    changed = True
    return True


def enumerate_solutions(
    domains: dict[str, set[int]], constraints: tuple[Constraint, ...]
) -> tuple[tuple[tuple[str, int], ...], ...]:
    solutions = []

    def search(current: dict[str, set[int]]) -> None:
        current = {name: set(values) for name, values in current.items()}
        if not propagate(current, constraints):
            return
        unresolved = [name for name, values in current.items() if len(values) > 1]
        if not unresolved:
            solutions.append(tuple((name, next(iter(current[name]))) for name in sorted(current)))
            return
        degree = {
            name: sum(name in constraint_names for constraint_names, _ in constraints)
            for name in unresolved
        }
        branch = min(
            unresolved,
            key=lambda name: (len(current[name]), -degree[name], name),
        )
        for value in sorted(current[branch]):
            child = {name: set(values) for name, values in current.items()}
            child[branch] = {value}
            search(child)

    search(domains)
    result = tuple(sorted(solutions))
    if len(result) != len(set(result)):
        raise Reject("CSP enumeration produced duplicate models")
    return result


def csp_satisfiable(domains: dict[str, set[int]], constraints: tuple[Constraint, ...]) -> bool:
    return bool(enumerate_solutions(domains, constraints))


def layer_relation(
    equations: dict[str, object], layer: dict[str, object]
) -> tuple[dict[str, set[int]], tuple[Constraint, ...], tuple[dict[str, object], ...]]:
    by_provenance = {
        equation["provenance"]: equation for equation in equations["equations"]
    }
    selected = tuple(by_provenance[name] for name in layer["equation_provenances"])
    names = set(layer["input_variables"]) | set(layer["output_variables"])
    names.update(name for equation in selected for name in equation_variables(equation))
    base = equations["base"]
    domains = {
        name: (
            set(range(2))
            if name.startswith("c:")
            else set(range(1 if re.fullmatch(r"digit:p\d+:f0:d0", name) else 0, base))
        )
        for name in names
    }
    constraints = tuple(
        allowed_equation_tuples(equation, domains, base) for equation in selected
    )
    return domains, constraints, selected


def require_sources(
    raw_payloads: tuple[tuple[bytes, dict[str, object]], ...]
) -> None:
    equations_raw, equations = raw_payloads[0]
    frontier_raw, frontier = raw_payloads[1]
    t27_raw, t27 = raw_payloads[2]
    t28_raw, t28 = raw_payloads[3]
    t28_ind_raw, t28_ind = raw_payloads[4]
    del equations_raw, frontier_raw
    if content_digest(equations) != SOURCE_DIGESTS["equations"]:
        raise Reject("equation content digest changed")
    if content_digest(frontier) != SOURCE_DIGESTS["frontier"]:
        raise Reject("frontier content digest changed")
    if frontier.get("provenances_sha256") != SOURCE_DIGESTS["provenances"]:
        raise Reject("frontier provenance digest changed")
    if raw_digest(t27_raw) != SOURCE_DIGESTS["t27_evidence"]:
        raise Reject("T27 evidence raw digest changed")
    if raw_digest(t28_raw) != SOURCE_DIGESTS["t28_evidence"]:
        raise Reject("T28 evidence raw digest changed")
    if raw_digest(t28_ind_raw) != SOURCE_DIGESTS["t28_independent"]:
        raise Reject("T28 independent raw digest changed")
    tail_lemma = t27.get("tail_lemma")
    if (
        t27.get("status") != "STOP"
        or not isinstance(tail_lemma, dict)
        or tail_lemma.get("obligation_status") != "PASS"
        or t28.get("status") != "STOP"
    ):
        raise Reject("T27/T28 achieved boundary changed")
    if (
        t28_ind.get("status") != "STOP"
        or t28_ind.get("primary_evidence_sha256") != SOURCE_DIGESTS["t28_evidence"]
        or t28_ind.get("counterexample_successor_exists") is not True
    ):
        raise Reject("T28 independent boundary changed")


def require_t29(
    raw_payloads: tuple[tuple[bytes, dict[str, object]], ...]
) -> None:
    names = ("trace", "dataset", "evidence", "certificate", "independent")
    for name, (raw, _) in zip(names, raw_payloads, strict=True):
        if raw_digest(raw) != T29_DIGESTS[name]:
            raise Reject(f"T29 {name} raw digest changed")
    trace, dataset, evidence, certificate, independent = (
        payload for _, payload in raw_payloads
    )
    for context, payload in zip(
        names, (trace, dataset, evidence, certificate, independent), strict=True
    ):
        if payload.get("source_digests") != SOURCE_DIGESTS:
            raise Reject(f"T29 {context} source identities changed")
    if (
        evidence.get("status") != "FINITE_SEPARATOR_PASS_SEMANTIC_STOP"
        or evidence.get("finite_status") != "PASS"
        or evidence.get("semantic_status") != "SAT"
        or certificate.get("semantic_status") != "SAT"
        or independent.get("status") != "FINITE_SEPARATOR_PASS_SEMANTIC_STOP"
        or independent.get("repository_imports") != []
    ):
        raise Reject("T29 achieved boundary changed")


def parse_rows(value: object, width: int, context: str) -> tuple[tuple[int, ...], ...]:
    if not isinstance(value, list):
        raise Reject(f"{context} must be a list")
    rows = []
    for row in value:
        if not isinstance(row, list) or len(row) != width or any(not is_int(x) for x in row):
            raise Reject(f"{context} row is malformed")
        rows.append(tuple(row))
    result = tuple(rows)
    if result != tuple(sorted(set(result))):
        raise Reject(f"{context} rows are not sorted and unique")
    return result


def check_t30_shapes(
    evidence_raw: bytes,
    evidence: dict[str, object],
    certificate_raw: bytes,
    certificate: dict[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    require_keys(
        certificate,
        {
            "schema",
            "status",
            "base",
            "removed",
            "source_digests",
            "t29_artifact_digests",
            "q0",
            "predecessor_obligations",
            "implication_status",
            "finite_status",
            "semantic_status",
            "implication_witness",
            "semantic_witness",
        },
        "T30 certificate",
    )
    if (
        certificate.get("schema")
        != "t30-base19-exact-image-refinement-certificate-v1"
        or certificate.get("status") != "EXACT_IMAGE_REFINEMENT_PASS"
        or certificate.get("base") != 19
        or certificate.get("removed") != REMOVED
        or certificate.get("source_digests") != SOURCE_DIGESTS
        or certificate.get("t29_artifact_digests") != T29_DIGESTS
        or certificate.get("implication_status") != "UNSAT"
        or certificate.get("finite_status") != "PASS"
        or certificate.get("semantic_status") != "UNSAT"
        or certificate.get("implication_witness") is not None
        or certificate.get("semantic_witness") is not None
    ):
        raise Reject("T30 certificate PASS boundary changed")
    q0 = certificate["q0"]
    if not isinstance(q0, dict):
        raise Reject("T30 Q0 is malformed")
    require_q0(q0)
    obligations = certificate["predecessor_obligations"]
    if not isinstance(obligations, list) or len(obligations) != 18:
        raise Reject("T30 certificate obligation count changed")
    if [item.get("predecessor_index") for item in obligations] != list(range(18)):
        raise Reject("T30 predecessor obligation order changed")

    if (
        evidence.get("schema") != "t30-base19-exact-image-refinement-evidence-v1"
        or evidence.get("status") != "EXACT_IMAGE_REFINEMENT_PASS"
        or evidence.get("stop_reason") is not None
        or evidence.get("base") != 19
        or evidence.get("removed") != REMOVED
        or evidence.get("source_digests") != SOURCE_DIGESTS
        or evidence.get("t29_artifact_digests") != T29_DIGESTS
        or evidence.get("t29_certificate_sha256") != T29_DIGESTS["certificate"]
        or evidence.get("q0") != q0
        or evidence.get("certificate_sha256")
        != hashlib.sha256(canonical_bytes(certificate)).hexdigest()
    ):
        raise Reject("T30 primary evidence boundary changed")
    implication = evidence.get("implication")
    finite = evidence.get("finite")
    semantic = evidence.get("semantic")
    if (
        not isinstance(implication, dict)
        or not isinstance(finite, dict)
        or not isinstance(semantic, dict)
    ):
        raise Reject("T30 gate sections are malformed")
    if implication.get("predecessor_obligations") != obligations:
        raise Reject("T30 evidence/certificate obligations disagree")
    if (
        implication.get("status") != "UNSAT"
        or implication.get("predecessor_count") != 18
        or implication.get("successor_bearing_predecessor_count") != 5
        or implication.get("exact_model_count") != 18
        or implication.get("distinct_output_count") != 18
        or implication.get("witness") is not None
        or finite
        != {
            "status": "PASS",
            "q0_positive_count": 12,
            "q0_trace_accepted": 0,
            "q0_live_count": 6,
            "q0_leak_holds": False,
            "combined_failures": [],
        }
        or semantic
        != {"status": "UNSAT", "equation_count": 12, "witness": None}
    ):
        raise Reject("T30 gate summaries changed")
    del evidence_raw, certificate_raw
    return q0, obligations


def replay_predecessors(
    equations: dict[str, object],
    layer: dict[str, object],
    q0: dict[str, object],
    obligations: list[dict[str, object]],
) -> tuple[int, int, int]:
    domains, constraints, selected = layer_relation(equations, layer)
    del selected
    input_variables = tuple(layer["input_variables"])
    output_variables = tuple(layer["output_variables"])
    output_mapping = canonical_map(output_variables)
    transitions = layer["transitions"]
    if not isinstance(transitions, list) or len(transitions) != 18:
        raise Reject("layer-31 transitions changed")
    total_models = 0
    successor_bearing = 0
    all_outputs = set()
    for index, (transition, obligation) in enumerate(
        zip(transitions, obligations, strict=True)
    ):
        if not isinstance(transition, dict) or not isinstance(obligation, dict):
            raise Reject("predecessor record is malformed")
        input_state = transition.get("input_state")
        expected_outputs = transition.get("output_states")
        if not isinstance(input_state, list) or not isinstance(expected_outputs, list):
            raise Reject("frontier transition is malformed")
        fixed = {name: set(values) for name, values in domains.items()}
        for name, value in zip(input_variables, input_state, strict=True):
            fixed[name] = {value}
        models = enumerate_solutions(fixed, constraints)
        output_rows = tuple(
            sorted(
                {
                    tuple(dict(model)[name] for name in output_variables)
                    for model in models
                }
            )
        )
        if output_rows != tuple(tuple(row) for row in expected_outputs):
            raise Reject(f"predecessor {index} exact outputs disagree with frontier")
        if len(models) != len(output_rows):
            raise Reject(f"predecessor {index} local model count changed")
        canonical_to_index = {
            canonical: output_variables.index(original)
            for original, canonical in output_mapping.items()
        }
        canonical_rows = tuple(
            sorted(
                tuple(row[canonical_to_index[name]] for name in VARIABLES)
                for row in output_rows
            )
        )
        for row in canonical_rows:
            if not predicate_holds(q0, dict(zip(VARIABLES, row, strict=True))):
                raise Reject(f"predecessor {index} has a Q0 violation")
        expected_obligation = {
            "predecessor_index": index,
            "predecessor_sha256": hashlib.sha256(canonical_bytes(input_state)).hexdigest(),
            "exact_model_count": len(models),
            "output_count": len(canonical_rows),
            "output_sha256": hashlib.sha256(
                canonical_bytes([list(row) for row in canonical_rows])
            ).hexdigest(),
            "q0_violation_status": "UNSAT",
        }
        if obligation != expected_obligation:
            differing = {
                key: (obligation.get(key), expected_obligation[key])
                for key in expected_obligation
                if obligation.get(key) != expected_obligation[key]
            }
            raise Reject(f"predecessor {index} obligation changed: {differing}")
        total_models += len(models)
        successor_bearing += bool(models)
        all_outputs.update(canonical_rows)
    return total_models, successor_bearing, len(all_outputs)


def replay_finite(
    dataset: dict[str, object],
    t29_evidence: dict[str, object],
    t29_certificate: dict[str, object],
    q0: dict[str, object],
) -> tuple[int, int, int]:
    if dataset.get("variables") != list(VARIABLES):
        raise Reject("T29 dataset scope changed")
    positives = parse_rows(dataset.get("positives"), 14, "positives")
    traces = parse_rows(dataset.get("trace_negatives"), 14, "trace negatives")
    live = parse_rows(dataset.get("live_controls"), 14, "live controls")
    s29 = t29_certificate.get("predicate")
    if not isinstance(s29, dict):
        raise Reject("T29 predicate is malformed")
    positive_count = 0
    trace_count = 0
    live_count = 0
    for row in positives:
        state = dict(zip(VARIABLES, row, strict=True))
        positive_count += predicate_holds(q0, state)
        if not predicate_holds(s29, state) or not predicate_holds(q0, state):
            raise Reject("combined predicate rejects a promoted DEAD state")
    for row in traces:
        state = dict(zip(VARIABLES, row, strict=True))
        trace_count += predicate_holds(q0, state)
    for row in live:
        state = dict(zip(VARIABLES, row, strict=True))
        live_count += predicate_holds(q0, state)
        if predicate_holds(s29, state) and predicate_holds(q0, state):
            raise Reject("combined predicate accepts a live control")
    witness = t29_evidence.get("semantic_counterexample")
    if not isinstance(witness, dict) or not isinstance(witness.get("input_state"), dict):
        raise Reject("T29 semantic leak is malformed")
    leak = {
        name.removeprefix("input:"): value
        for name, value in witness["input_state"].items()
    }
    if predicate_holds(q0, leak):
        raise Reject("Q0 accepts the T29 semantic leak")
    if (positive_count, trace_count, live_count) != (12, 0, 6):
        raise Reject("finite Q0 counts changed")
    return positive_count, trace_count, live_count


def replay_semantics(
    equations: dict[str, object],
    layer: dict[str, object],
    s29: dict[str, object],
    q0: dict[str, object],
) -> int:
    domains, equation_constraints, selected = layer_relation(equations, layer)
    input_variables = tuple(layer["input_variables"])
    input_mapping = canonical_map(input_variables)
    canonical_to_original = {canonical: original for original, canonical in input_mapping.items()}
    atom_constraints = []
    for predicate in (s29, q0):
        predicate_holds(predicate, {name: 0 for name in VARIABLES})
        clauses = predicate["clauses"]
        if len(clauses) != 1:
            raise Reject("semantic replay requires conjunctive predicates")
        atom_constraints.extend(
            allowed_atom_tuples(atom, canonical_to_original, domains)
            for atom in clauses[0]["atoms"]
        )
    if csp_satisfiable(domains, (*equation_constraints, *atom_constraints)):
        raise Reject("refined layer-32 query is SAT")
    return len(selected)


def audit(args: argparse.Namespace) -> dict[str, object]:
    source_payloads = tuple(
        load_object(path, label)
        for path, label in (
            (args.EQUATIONS, "equations"),
            (args.FRONTIER, "frontier"),
            (args.T27_EVIDENCE, "T27 evidence"),
            (args.T28_EVIDENCE, "T28 evidence"),
            (args.T28_INDEPENDENT, "T28 independent"),
        )
    )
    require_sources(source_payloads)
    t29_payloads = tuple(
        load_object(path, label)
        for path, label in (
            (args.T29_TRACE, "T29 trace"),
            (args.T29_DATASET, "T29 dataset"),
            (args.T29_EVIDENCE, "T29 evidence"),
            (args.T29_CERTIFICATE, "T29 certificate"),
            (args.T29_INDEPENDENT, "T29 independent"),
        )
    )
    require_t29(t29_payloads)
    evidence_raw, evidence = load_object(args.T30_EVIDENCE, "T30 evidence")
    certificate_raw, certificate = load_object(
        args.T30_CERTIFICATE, "T30 certificate"
    )
    q0, obligations = check_t30_shapes(
        evidence_raw, evidence, certificate_raw, certificate
    )
    equations = source_payloads[0][1]
    frontier = source_payloads[1][1]
    layers = {layer["layer"]: layer for layer in frontier["layers"]}
    model_count, predecessor_count, output_count = replay_predecessors(
        equations, layers[31], q0, obligations
    )
    finite_counts = replay_finite(
        t29_payloads[1][1], t29_payloads[2][1], t29_payloads[3][1], q0
    )
    equation_count = replay_semantics(
        equations,
        layers[32],
        t29_payloads[3][1]["predicate"],
        q0,
    )
    return {
        "schema": "t30-base19-exact-image-refinement-independent-v1",
        "status": "EXACT_IMAGE_REFINEMENT_PASS",
        "repository_imports": [],
        "source_digests": SOURCE_DIGESTS,
        "t29_artifact_digests": T29_DIGESTS,
        "primary_evidence_sha256": raw_digest(evidence_raw),
        "certificate_file_sha256": raw_digest(certificate_raw),
        "predecessor_obligation_count": len(obligations),
        "successor_bearing_predecessor_count": predecessor_count,
        "exact_model_count": model_count,
        "distinct_output_count": output_count,
        "finite_replay_counts": {
            "q0_positive_count": finite_counts[0],
            "q0_trace_accepted": finite_counts[1],
            "q0_live_count": finite_counts[2],
        },
        "semantic_equation_count": equation_count,
        "semantic_status": "UNSAT",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "EQUATIONS",
        "FRONTIER",
        "T27_EVIDENCE",
        "T28_EVIDENCE",
        "T28_INDEPENDENT",
        "T29_TRACE",
        "T29_DATASET",
        "T29_EVIDENCE",
        "T29_CERTIFICATE",
        "T29_INDEPENDENT",
        "T30_EVIDENCE",
        "T30_CERTIFICATE",
    ):
        parser.add_argument(name, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = audit(args)
    except (Reject, KeyError, TypeError, ValueError) as error:
        print(f"REJECT: {error}", file=sys.stderr)
        return 2
    print(canonical_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
