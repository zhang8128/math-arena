#!/usr/bin/env python3
"""Independently check bounded base-19 semantic-leak mechanism claims."""

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
T30_DIGESTS = {
    "certificate": "3ac0b6ae254ad8bb7c7b19754335ea6a81bea77a0dc808e7eda1cd8994839892",
    "evidence": "4b327e826a8b2462eedffa2cf572b77155fc95d8e7b94a4430d7f0331f75bd2a",
    "independent": "56037d658f628ffa526f9adb710746231806450717f7bde5c0655f4ed6388639",
    "report": "3ea55f8410887d3a522436be38bf3d9b5c010ac3c412d48405cd69f19828b95c",
}
T31_DIGESTS = {
    "library": "62e46be94c8ce27f538257fd8d1a61fb5e582fa23b80ccfbf9b8bdd6ac3375e1",
    "runner": "da4ceebd20cf11e164a1e3228d96c53136fcbce8071055867a72d3869b60a732",
    "test": "3b88dadc423f41ec1ca81a2aea4df60071ad0d1a1165fc229c902012babc6b3e",
}
T31_COMMITS = ["69022cb", "adc6986", "619b737", "6835036"]
DESIGN_SHA256 = "93cecb3d3ce2c6a2610454f63302e26e2bbe57c7eba1825474bc808ad9ff76bd"

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
RELATIONS = {
    "digit_order": ("eq", "lt", "gt"),
    "digit_sum": ("lt19", "eq18", "ge19"),
    "input_carry_pair": ("eq", "ne"),
    "output_carry_pair": ("eq", "ne"),
    "left_carry_flow": ("eq", "ne"),
    "right_carry_flow": ("eq", "ne"),
}
CARRY_RE = re.compile(r"c:p(?P<phase>\d+):n\d+:col(?P<column>\d+)\Z")
DIGIT_RE = re.compile(
    r"(?:digit:)?p(?P<phase>\d+):f(?P<fragment>\d+):d(?P<offset>\d+)\Z"
)


class Reject(RuntimeError):
    """The isolated checker rejected an input claim."""


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def require_keys(payload: dict[str, object], expected: set[str], context: str) -> None:
    if set(payload) != expected:
        raise Reject(f"{context} keys differ")


def load_object(path: Path, context: str) -> tuple[bytes, dict[str, object]]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise Reject(f"cannot read {context}: {error}") from error
    if not isinstance(payload, dict):
        raise Reject(f"{context} must be an object")
    return raw, payload


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
        ordered = sorted(carries[phase])
        if len(ordered) != 2:
            raise Reject("frontier does not have two carries per phase")
        for label, (_, variable) in zip(
            (f"L{phase}", f"R{phase}"), ordered, strict=True
        ):
            result[variable] = label
    for index, (*_, variable) in enumerate(sorted(digits)):
        if index >= 2:
            raise Reject("frontier has more than two live digits")
        result[variable] = f"D{index}"
    if tuple(result) != variables or len(set(result.values())) != len(result):
        raise Reject("frontier canonicalization is not bijective")
    return result


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
    literal = atom.get("literal")
    if not is_int(literal):
        raise Reject("equation literal is invalid")
    return base - 1 if literal == 18 else literal


def equation_residual(
    equation: dict[str, object], assignment: dict[str, int], base: int
) -> int:
    carry_in = equation.get("carry_in")
    carry_out = equation.get("carry_out")
    return (
        atom_value(equation["left"], assignment, base)
        + atom_value(equation["right"], assignment, base)
        + (0 if carry_in is None else assignment[carry_in])
        - atom_value(equation["target"], assignment, base)
        - base * (0 if carry_out is None else assignment[carry_out])
    )


Constraint = tuple[tuple[str, ...], tuple[tuple[int, ...], ...]]


def allowed_equation_tuples(
    equation: dict[str, object], domains: dict[str, set[int]], base: int
) -> Constraint:
    names = equation_variables(equation)
    allowed = []
    for values in itertools.product(*(sorted(domains[name]) for name in names)):
        assignment = dict(zip(names, values, strict=True))
        if equation_residual(equation, assignment, base) == 0:
            allowed.append(values)
    if not allowed:
        raise Reject("equation has no bounded tuple")
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
                reduced = domains[name] & {values[index] for values in viable}
                if not reduced:
                    return False
                if reduced != domains[name]:
                    domains[name] = reduced
                    changed = True
    return True


def first_solution(
    domains: dict[str, set[int]], constraints: tuple[Constraint, ...]
) -> tuple[tuple[str, int], ...] | None:
    def search(current: dict[str, set[int]]) -> tuple[tuple[str, int], ...] | None:
        current = {name: set(values) for name, values in current.items()}
        if not propagate(current, constraints):
            return None
        unresolved = [name for name, values in current.items() if len(values) > 1]
        if not unresolved:
            return tuple(
                (name, next(iter(current[name]))) for name in sorted(current)
            )
        branch = min(unresolved, key=lambda name: (len(current[name]), name))
        for value in sorted(current[branch]):
            child = {name: set(values) for name, values in current.items()}
            child[branch] = {value}
            found = search(child)
            if found is not None:
                return found
        return None

    return search(domains)


def parse_literal(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise Reject("structural literal must be an object")
    require_keys(payload, {"phase", "kind", "relation"}, "structural literal")
    phase = payload["phase"]
    kind = payload["kind"]
    relation = payload["relation"]
    if not is_int(phase) or not 0 <= phase < 6:
        raise Reject("structural literal phase is invalid")
    if not isinstance(kind, str) or kind not in RELATIONS:
        raise Reject("structural literal kind is invalid")
    if not isinstance(relation, str) or relation not in RELATIONS[kind]:
        raise Reject("structural literal relation is invalid")
    return {"phase": phase, "kind": kind, "relation": relation}


def structural_literal_holds(
    literal: dict[str, object], assignment: dict[str, int]
) -> bool:
    literal = parse_literal(literal)
    phase = literal["phase"]
    kind = literal["kind"]
    relation = literal["relation"]
    if kind == "digit_order":
        left, right = assignment[f"a{phase}"], assignment[f"b{phase}"]
        return {"eq": left == right, "lt": left < right, "gt": left > right}[
            relation
        ]
    if kind == "digit_sum":
        total = assignment[f"a{phase}"] + assignment[f"b{phase}"]
        return {
            "lt19": total < 19,
            "eq18": total == 18,
            "ge19": total >= 19,
        }[relation]
    pair_names = {
        "input_carry_pair": (f"Lin{phase}", f"Rin{phase}"),
        "output_carry_pair": (f"Lout{phase}", f"Rout{phase}"),
        "left_carry_flow": (f"Lin{phase}", f"Lout{phase}"),
        "right_carry_flow": (f"Rin{phase}", f"Rout{phase}"),
    }
    left_name, right_name = pair_names[kind]
    equal = assignment[left_name] == assignment[right_name]
    return equal if relation == "eq" else not equal


def allowed_structural_tuples(
    literal: dict[str, object], structural_names: dict[str, str], domains: dict[str, set[int]]
) -> Constraint:
    literal = parse_literal(literal)
    phase = literal["phase"]
    kind = literal["kind"]
    keys = {
        "digit_order": (f"a{phase}", f"b{phase}"),
        "digit_sum": (f"a{phase}", f"b{phase}"),
        "input_carry_pair": (f"Lin{phase}", f"Rin{phase}"),
        "output_carry_pair": (f"Lout{phase}", f"Rout{phase}"),
        "left_carry_flow": (f"Lin{phase}", f"Lout{phase}"),
        "right_carry_flow": (f"Rin{phase}", f"Rout{phase}"),
    }[kind]
    names = tuple(structural_names[key] for key in keys)
    allowed = []
    for values in itertools.product(*(sorted(domains[name]) for name in names)):
        view = {key: value for key, value in zip(keys, values, strict=True)}
        expanded = {
            f"a{phase}": view.get(f"a{phase}", 0),
            f"b{phase}": view.get(f"b{phase}", 0),
            f"Lin{phase}": view.get(f"Lin{phase}", 0),
            f"Rin{phase}": view.get(f"Rin{phase}", 0),
            f"Lout{phase}": view.get(f"Lout{phase}", 0),
            f"Rout{phase}": view.get(f"Rout{phase}", 0),
        }
        if structural_literal_holds(literal, expanded):
            allowed.append(values)
    if not allowed:
        raise Reject("structural literal has no bounded tuple")
    return names, tuple(allowed)


def atom_holds(atom: dict[str, object], state: dict[str, int]) -> bool:
    require_keys(atom, {"relation", "terms", "constant"}, "Q0 atom")
    if atom["relation"] != "eq" or not is_int(atom["constant"]):
        raise Reject("Q0 atom must be an equality")
    terms = atom["terms"]
    if not isinstance(terms, list) or not terms:
        raise Reject("Q0 terms are invalid")
    total = 0
    seen = set()
    for term in terms:
        if (
            not isinstance(term, list)
            or len(term) != 2
            or not isinstance(term[0], str)
            or term[0] in seen
            or term[0] not in state
            or not is_int(term[1])
        ):
            raise Reject("Q0 term is invalid")
        seen.add(term[0])
        total += term[1] * state[term[0]]
    return total == atom["constant"]


def q0_residuals(q0: dict[str, object], state: dict[str, int]) -> tuple[int, ...]:
    atoms = q0["clauses"][0]["atoms"]
    return tuple(
        sum(coefficient * state[name] for name, coefficient in atom["terms"])
        - atom["constant"]
        for atom in atoms
    )


def require_q0(q0: dict[str, object]) -> None:
    require_keys(q0, {"layer", "variables", "clauses"}, "Q0")
    if q0["layer"] != 31 or q0["variables"] != list(VARIABLES):
        raise Reject("Q0 scope changed")
    clauses = q0["clauses"]
    if not isinstance(clauses, list) or len(clauses) != 1:
        raise Reject("Q0 must have one clause")
    clause = clauses[0]
    if not isinstance(clause, dict):
        raise Reject("Q0 clause is invalid")
    require_keys(clause, {"atoms"}, "Q0 clause")
    atoms = clause["atoms"]
    if not isinstance(atoms, list) or len(atoms) != 5:
        raise Reject("Q0 must have five atoms")
    for atom in atoms:
        if not isinstance(atom, dict):
            raise Reject("Q0 atom is invalid")
        atom_holds(atom, {name: 0 for name in VARIABLES})


def allowed_atom_tuples(
    atom: dict[str, object], canonical_to_original: dict[str, str], domains: dict[str, set[int]]
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
    if not allowed:
        raise Reject("Q0 atom has no bounded tuple")
    return names, tuple(allowed)


def layer_relation(
    equations: dict[str, object], frontier: dict[str, object]
) -> tuple[
    dict[str, set[int]],
    tuple[Constraint, ...],
    tuple[dict[str, object], ...],
    dict[str, str],
    dict[str, str],
    dict[str, str],
]:
    layers = {layer["layer"]: layer for layer in frontier["layers"]}
    layer = layers.get(31)
    if not isinstance(layer, dict) or layer.get("equation_count") != 12:
        raise Reject("layer-31 relation changed")
    by_provenance = {
        equation["provenance"]: equation for equation in equations["equations"]
    }
    selected = tuple(by_provenance[name] for name in layer["equation_provenances"])
    input_variables = tuple(layer["input_variables"])
    output_variables = tuple(layer["output_variables"])
    input_original_to_canonical = canonical_map(input_variables)
    output_original_to_canonical = canonical_map(output_variables)
    input_map = {value: key for key, value in input_original_to_canonical.items()}
    output_map = {value: key for key, value in output_original_to_canonical.items()}
    names = set(input_variables) | set(output_variables)
    names.update(name for equation in selected for name in equation_variables(equation))
    base = equations.get("base")
    if base != 19:
        raise Reject("equation base changed")
    domains = {
        name: (
            {0, 1}
            if name.startswith("c:")
            else set(range(1 if re.fullmatch(r"digit:p\d+:f0:d0", name) else 0, 19))
        )
        for name in names
    }
    constraints = tuple(
        allowed_equation_tuples(equation, domains, 19) for equation in selected
    )
    structural_names: dict[str, str] = {}
    for phase in range(6):
        left = selected[2 * phase]
        right = selected[2 * phase + 1]
        left_pair = {
            "digit:" + left["left"]["variable"],
            "digit:" + left["right"]["variable"],
        }
        right_pair = {
            "digit:" + right["left"]["variable"],
            "digit:" + right["right"]["variable"],
        }
        if left_pair != right_pair:
            raise Reject("paired phase summands changed")
        structural_names.update(
            {
                f"a{phase}": "digit:" + left["left"]["variable"],
                f"b{phase}": "digit:" + left["right"]["variable"],
                f"Lin{phase}": input_map[f"L{phase}"],
                f"Rin{phase}": input_map[f"R{phase}"],
                f"Lout{phase}": output_map[f"L{phase}"],
                f"Rout{phase}": output_map[f"R{phase}"],
            }
        )
    return domains, constraints, selected, input_map, output_map, structural_names


def require_frozen_inputs(
    sources: tuple[tuple[bytes, dict[str, object]], ...]
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    equations_raw, equations = sources[0]
    frontier_raw, frontier = sources[1]
    del equations_raw, frontier_raw
    if content_digest(equations) != SOURCE_DIGESTS["equations"]:
        raise Reject("equation content digest changed")
    if content_digest(frontier) != SOURCE_DIGESTS["frontier"]:
        raise Reject("frontier content digest changed")
    if frontier.get("provenances_sha256") != SOURCE_DIGESTS["provenances"]:
        raise Reject("frontier provenance digest changed")
    raw_expectations = (
        SOURCE_DIGESTS["t27_evidence"],
        SOURCE_DIGESTS["t28_evidence"],
        SOURCE_DIGESTS["t28_independent"],
        T29_DIGESTS["trace"],
        T29_DIGESTS["dataset"],
        T29_DIGESTS["evidence"],
        T29_DIGESTS["certificate"],
        T29_DIGESTS["independent"],
        T30_DIGESTS["evidence"],
        T30_DIGESTS["certificate"],
        T30_DIGESTS["independent"],
    )
    for (raw, _), expected in zip(sources[2:], raw_expectations, strict=True):
        if raw_digest(raw) != expected:
            raise Reject("frozen raw artifact digest changed")
    t30_certificate = sources[-2][1]
    q0 = t30_certificate.get("q0")
    if not isinstance(q0, dict):
        raise Reject("T30 certificate Q0 is missing")
    require_q0(q0)
    return equations, frontier, q0


def parse_milestone(
    payload: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[list[bool]]]:
    require_keys(
        payload,
        {
            "schema",
            "leak_type",
            "witnesses",
            "failure_masks",
            "source_digests",
            "t29_artifact_digests",
            "t30_artifact_digests",
            "t31_source_digests",
            "t31_commits",
            "design_sha256",
        },
        "milestone",
    )
    if payload["schema"] != "t32-base19-semantic-leak-type-milestone-v1":
        raise Reject("milestone schema changed")
    expected_fields = (
        ("source_digests", SOURCE_DIGESTS),
        ("t29_artifact_digests", T29_DIGESTS),
        ("t30_artifact_digests", T30_DIGESTS),
        ("t31_source_digests", T31_DIGESTS),
    )
    for field, expected in expected_fields:
        if payload[field] != expected:
            raise Reject(f"milestone {field} changed")
    if payload["t31_commits"] != T31_COMMITS or payload["design_sha256"] != DESIGN_SHA256:
        raise Reject("milestone T31/design boundary changed")
    leak_type = payload["leak_type"]
    if not isinstance(leak_type, dict):
        raise Reject("leak type must be an object")
    require_keys(leak_type, {"literals"}, "leak type")
    literal_payloads = leak_type["literals"]
    if not isinstance(literal_payloads, list) or not 1 <= len(literal_payloads) <= 6:
        raise Reject("leak type must have one to six literals")
    literals = [parse_literal(literal) for literal in literal_payloads]
    literal_bytes = [canonical_bytes(literal) for literal in literals]
    if literal_bytes != sorted(set(literal_bytes)):
        raise Reject("leak type literals are not canonical and distinct")
    witnesses = payload["witnesses"]
    masks = payload["failure_masks"]
    if not isinstance(witnesses, list) or len(witnesses) != 2 or not all(
        isinstance(witness, dict) for witness in witnesses
    ):
        raise Reject("milestone requires two witnesses")
    if not isinstance(masks, list) or len(masks) != 2 or any(
        not isinstance(mask, list)
        or len(mask) != 5
        or any(not isinstance(bit, bool) for bit in mask)
        for mask in masks
    ):
        raise Reject("milestone failure masks are invalid")
    return literals, witnesses, masks


def parse_assignment(payload: object, context: str) -> dict[str, int]:
    if not isinstance(payload, dict) or any(
        not isinstance(name, str) or not is_int(value) for name, value in payload.items()
    ):
        raise Reject(f"{context} assignment is invalid")
    return payload


def replay_witness(
    witness: dict[str, object],
    selected: tuple[dict[str, object], ...],
    input_map: dict[str, str],
    output_map: dict[str, str],
    structural_names: dict[str, str],
    literals: list[dict[str, object]],
    q0: dict[str, object],
) -> tuple[list[int], tuple[int, ...], tuple[bool, ...]]:
    require_keys(witness, {"input_state", "output_state", "local_state"}, "witness")
    input_state = parse_assignment(witness["input_state"], "witness input")
    output_state = parse_assignment(witness["output_state"], "witness output")
    local_state = parse_assignment(witness["local_state"], "witness local")
    expected_input = {f"input:{name}" for name in input_map}
    expected_output = {f"output:{name}" for name in output_map}
    if set(input_state) != expected_input or set(output_state) != expected_output:
        raise Reject("witness frontier scope changed")
    assignment = {
        original: input_state[f"input:{canonical}"]
        for canonical, original in input_map.items()
    }
    assignment.update(
        {
            original: output_state[f"output:{canonical}"]
            for canonical, original in output_map.items()
        }
    )
    for name, value in local_state.items():
        if not name.startswith("local:") or name.removeprefix("local:") in assignment:
            raise Reject("witness local scope is invalid")
        assignment[name.removeprefix("local:")] = value
    expected_names = {name for equation in selected for name in equation_variables(equation)}
    if set(assignment) != expected_names:
        raise Reject("witness relation assignment is incomplete")
    residuals = [equation_residual(equation, assignment, 19) for equation in selected]
    view = {key: assignment[original] for key, original in structural_names.items()}
    if not all(structural_literal_holds(literal, view) for literal in literals):
        raise Reject("diversity witness does not satisfy leak type")
    output_canonical = {
        canonical: assignment[original] for canonical, original in output_map.items()
    }
    residual_mask = tuple(value != 0 for value in q0_residuals(q0, output_canonical))
    input_tuple = tuple(input_state[f"input:{name}"] for name in sorted(input_map))
    return residuals, input_tuple, residual_mask


def audit_milestone(args: argparse.Namespace) -> dict[str, object]:
    source_paths = (
        args.EQUATIONS,
        args.FRONTIER,
        args.T27_EVIDENCE,
        args.T28_EVIDENCE,
        args.T28_INDEPENDENT,
        args.T29_TRACE,
        args.T29_DATASET,
        args.T29_EVIDENCE,
        args.T29_CERTIFICATE,
        args.T29_INDEPENDENT,
        args.T30_EVIDENCE,
        args.T30_CERTIFICATE,
        args.T30_INDEPENDENT,
    )
    sources = tuple(load_object(path, path.name) for path in source_paths)
    equations, frontier, q0 = require_frozen_inputs(sources)
    _, milestone = load_object(args.MILESTONE, "milestone")
    literals, witnesses, claimed_masks = parse_milestone(milestone)
    relation = layer_relation(equations, frontier)
    (
        domains,
        equation_constraints,
        selected,
        input_map,
        output_map,
        structural_names,
    ) = relation
    output_original = {canonical: original for canonical, original in output_map.items()}
    q0_constraints = tuple(
        allowed_atom_tuples(atom, output_original, domains)
        for atom in q0["clauses"][0]["atoms"]
    )
    type_constraints = tuple(
        allowed_structural_tuples(literal, structural_names, domains)
        for literal in literals
    )
    countermodel = first_solution(
        domains, (*equation_constraints, *type_constraints, *q0_constraints)
    )
    if countermodel is not None:
        raise Reject(f"type soundness counterexample: {dict(countermodel)}")
    residual_rows = []
    input_tuples = []
    masks = []
    for witness in witnesses:
        residuals, input_tuple, mask = replay_witness(
            witness,
            selected,
            input_map,
            output_map,
            structural_names,
            literals,
            q0,
        )
        if residuals != [0] * 12:
            raise Reject("diversity witness has nonzero equation residual")
        residual_rows.append(residuals)
        input_tuples.append(input_tuple)
        masks.append(mask)
    if input_tuples[0] == input_tuples[1]:
        raise Reject("diversity witnesses have the same input")
    if masks[0] == masks[1] or [list(mask) for mask in masks] != claimed_masks:
        raise Reject("diversity failure masks differ")
    return {
        "schema": "t32-base19-semantic-leak-types-independent-milestone-v1",
        "status": "PASS",
        "repository_imports": [],
        "soundness_status": "UNSAT",
        "witness_residuals": residual_rows,
        "failure_masks": [list(mask) for mask in masks],
        "source_digests": SOURCE_DIGESTS,
        "t29_artifact_digests": T29_DIGESTS,
        "t30_artifact_digests": T30_DIGESTS,
        "t31_source_digests": T31_DIGESTS,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    milestone = subparsers.add_parser("milestone", help="audit one sound leak type")
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
        "T30_INDEPENDENT",
        "MILESTONE",
    ):
        milestone.add_argument(name, type=Path)
    subparsers.add_parser("full", help="audit a complete leak-type family")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode != "milestone":
            raise Reject("full audit is not implemented before the family gate")
        result = audit_milestone(args)
    except (Reject, KeyError, TypeError, ValueError) as error:
        print(f"REJECT: {error}", file=sys.stderr)
        return 2
    print(canonical_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
