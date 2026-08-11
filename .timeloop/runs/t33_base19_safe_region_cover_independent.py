#!/usr/bin/env python3
"""Independently check bounded base-19 safe-region cover claims."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
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
T32_DIGESTS = {
    "library": "cf6ad87c8edf3ffa2c86449b9762f8c9d4254645eb71b7f88963a688a1bded11",
    "runner": "d9c90e0dc4ce910a6ddef66233b03bff31449a46662fba75628a44dca3ed9e57",
    "independent": "fb520b513dd5673e145b583ee8a5025c8113890fdb89139a48b528655ed506b5",
    "test": "a6ee921a8ba6304d3a48b0db0b893b6bd8077576acc27146b91d626ac00858bd",
}
T32_COMMITS = ["df191a5", "515bbdd", "b5ff122", "e4bc16d", "9d17f77"]
T32_DESIGN_SHA256 = "93cecb3d3ce2c6a2610454f63302e26e2bbe57c7eba1825474bc808ad9ff76bd"
T33_DESIGN_SHA256 = "dadd1fe42f32d6f61b72609394f2172ca4fac3a6979660d03453058a221322a0"
T33_RESTART_DESIGN_SHA256 = (
    "10feaf957e889ca33b9f06441f88258179e2674e13248f72355adcd629b9c854"
)

P30_VARIABLES = (
    "L0",
    "R0",
    "L1",
    "R1",
    "L2",
    "R2",
    "L3",
    "R3",
    "L4",
    "R4",
    "L5",
    "R5",
    "D0",
)
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


def q0_atom_holds(atom: dict[str, object], state: dict[str, int]) -> bool:
    require_keys(atom, {"relation", "terms", "constant"}, "Q0 atom")
    if atom["relation"] != "eq" or not is_int(atom["constant"]):
        raise Reject("Q0 atom must be an equality")
    terms = atom["terms"]
    if not isinstance(terms, list) or not terms:
        raise Reject("Q0 terms are invalid")
    total = 0
    seen: set[str] = set()
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


def require_q0(q0: dict[str, object]) -> None:
    variables = (
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
    require_keys(q0, {"layer", "variables", "clauses"}, "Q0")
    if q0["layer"] != 31 or q0["variables"] != list(variables):
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
        q0_atom_holds(atom, {name: 0 for name in variables})


def layer_relation(
    equations: dict[str, object], frontier: dict[str, object]
) -> tuple[
    dict[str, set[int]],
    tuple[Constraint, ...],
    tuple[dict[str, object], ...],
    dict[str, str],
    dict[str, str],
    tuple[tuple[int, ...], ...],
]:
    layers_value = frontier.get("layers")
    equations_value = equations.get("equations")
    if not isinstance(layers_value, list) or not isinstance(equations_value, list):
        raise Reject("equation/frontier collections changed")
    layers = {
        layer["layer"]: layer
        for layer in layers_value
        if isinstance(layer, dict) and is_int(layer.get("layer"))
    }
    layer = layers.get(31)
    if not isinstance(layer, dict) or layer.get("equation_count") != 12:
        raise Reject("layer-31 relation changed")
    by_provenance = {
        equation["provenance"]: equation
        for equation in equations_value
        if isinstance(equation, dict) and isinstance(equation.get("provenance"), str)
    }
    provenances = layer.get("equation_provenances")
    if not isinstance(provenances, list) or any(
        not isinstance(name, str) or name not in by_provenance for name in provenances
    ):
        raise Reject("layer-31 equation provenances changed")
    selected = tuple(by_provenance[name] for name in provenances)
    input_value = layer.get("input_variables")
    output_value = layer.get("output_variables")
    if not isinstance(input_value, list) or not all(
        isinstance(name, str) for name in input_value
    ):
        raise Reject("layer-31 input variables changed")
    if not isinstance(output_value, list) or not all(
        isinstance(name, str) for name in output_value
    ):
        raise Reject("layer-31 output variables changed")
    input_variables = tuple(input_value)
    output_variables = tuple(output_value)
    input_original_to_canonical = canonical_map(input_variables)
    output_original_to_canonical = canonical_map(output_variables)
    input_map = {value: key for key, value in input_original_to_canonical.items()}
    output_map = {value: key for key, value in output_original_to_canonical.items()}
    if tuple(input_map) != P30_VARIABLES:
        raise Reject("layer-30 canonical input scope changed")
    names = set(input_variables) | set(output_variables)
    names.update(name for equation in selected for name in equation_variables(equation))
    if equations.get("base") != 19:
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
    transitions = layer.get("transitions")
    if not isinstance(transitions, list) or len(transitions) != 18:
        raise Reject("layer-31 promoted transition count changed")
    promoted = []
    for transition in transitions:
        if not isinstance(transition, dict):
            raise Reject("layer-31 transition is invalid")
        row = transition.get("input_state")
        if not isinstance(row, list) or len(row) != len(P30_VARIABLES) or any(
            not is_int(value) for value in row
        ):
            raise Reject("layer-31 promoted input changed")
        promoted.append(tuple(row))
    if len(set(promoted)) != 18:
        raise Reject("layer-31 promoted inputs are not distinct")
    return domains, constraints, selected, input_map, output_map, tuple(promoted)


def affine_atom_holds(atom: dict[str, object], assignment: dict[str, int]) -> bool:
    """Evaluate one strict affine atom without repository code."""
    expected = {"relation", "terms", "constant"}
    if atom.get("relation") == "congruent":
        expected.add("modulus")
    require_keys(atom, expected, "safe-region atom")
    relation = atom["relation"]
    terms = atom["terms"]
    constant = atom["constant"]
    if relation not in {"eq", "le", "congruent"}:
        raise Reject("safe-region atom relation differs")
    if not isinstance(terms, list) or not 1 <= len(terms) <= 2:
        raise Reject("safe-region atom support differs")
    if not is_int(constant):
        raise Reject("safe-region atom constant differs")
    total = 0
    seen: set[str] = set()
    for term in terms:
        if (
            not isinstance(term, list)
            or len(term) != 2
            or not isinstance(term[0], str)
            or term[0] not in P30_VARIABLES
            or term[0] in seen
            or not is_int(term[1])
            or term[1] == 0
            or abs(term[1]) > 3
        ):
            raise Reject("safe-region atom term differs")
        seen.add(term[0])
        total += term[1] * assignment[term[0]]
    if relation == "eq":
        return total == constant
    if relation == "le":
        return total <= constant
    modulus = atom["modulus"]
    if not is_int(modulus) or not 2 <= modulus <= 19:
        raise Reject("safe-region atom modulus differs")
    return (total - constant) % modulus == 0


def parse_affine_atom(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise Reject("safe-region atom must be an object")
    probe = {name: 0 for name in P30_VARIABLES}
    affine_atom_holds(value, probe)
    terms = value["terms"]
    assert isinstance(terms, list)
    if terms != sorted(terms, key=lambda term: term[0]):
        raise Reject("safe-region atom terms are not canonical")
    relation = value["relation"]
    constant = value["constant"]
    assert isinstance(relation, str) and is_int(constant)
    coefficients = tuple(term[1] for term in terms)
    if relation != "congruent":
        divisor = math.gcd(abs(constant), *(abs(value) for value in coefficients))
        if divisor != 1:
            raise Reject("safe-region atom is not primitive")
        if relation == "eq" and coefficients[0] < 0:
            raise Reject("safe-region equality sign is not canonical")
    else:
        modulus = value["modulus"]
        assert is_int(modulus)
        centered = []
        for coefficient in coefficients:
            residue = coefficient % modulus
            centered.append(residue - modulus if residue > modulus // 2 else residue)
        residue = constant % modulus
        centered_constant = residue - modulus if residue > modulus // 2 else residue
        if tuple(centered) != coefficients or centered_constant != constant:
            raise Reject("safe-region congruence is not centered")
    return value


def parse_clause(value: object, *, allow_empty: bool = False) -> list[dict[str, object]]:
    if not isinstance(value, dict):
        raise Reject("safe-region clause must be an object")
    require_keys(value, {"atoms"}, "safe-region clause")
    atoms_value = value["atoms"]
    if not isinstance(atoms_value, list) or (
        not allow_empty and not 1 <= len(atoms_value) <= 6
    ):
        raise Reject("safe-region clause must have one to six atoms")
    if allow_empty and len(atoms_value) > 6:
        raise Reject("safe-region reduction has more than six atoms")
    atoms = [parse_affine_atom(atom) for atom in atoms_value]
    atom_bytes = [canonical_bytes(atom) for atom in atoms]
    if atom_bytes != sorted(set(atom_bytes)):
        raise Reject("safe-region atoms are not canonical and distinct")
    return atoms


def allowed_affine_tuples(
    atom: dict[str, object],
    input_map: dict[str, str],
    domains: dict[str, set[int]],
) -> Constraint:
    names = tuple(input_map[term[0]] for term in atom["terms"])
    allowed = []
    for values in itertools.product(*(sorted(domains[name]) for name in names)):
        state = {
            canonical: value
            for canonical, original in input_map.items()
            for name, value in zip(names, values, strict=True)
            if original == name
        }
        if affine_atom_holds(atom, state):
            allowed.append(values)
    if not allowed:
        raise Reject("safe-region atom has no bounded tuple")
    return names, tuple(allowed)


def allowed_q0_failure_tuples(
    atom: dict[str, object],
    output_map: dict[str, str],
    domains: dict[str, set[int]],
) -> Constraint:
    terms = atom["terms"]
    names = tuple(output_map[term[0]] for term in terms)
    allowed = []
    for values in itertools.product(*(sorted(domains[name]) for name in names)):
        state = {
            canonical: value
            for canonical, original in output_map.items()
            for name, value in zip(names, values, strict=True)
            if original == name
        }
        if not q0_atom_holds(atom, state):
            allowed.append(values)
    if not allowed:
        raise Reject("Q0 failure atom has no bounded tuple")
    return names, tuple(allowed)


def first_bad_solution(
    domains: dict[str, set[int]],
    transfer_constraints: tuple[Constraint, ...],
    input_map: dict[str, str],
    output_map: dict[str, str],
    q0: dict[str, object],
    atoms: list[dict[str, object]],
) -> tuple[tuple[str, int], ...] | None:
    clause_constraints = tuple(
        allowed_affine_tuples(atom, input_map, domains) for atom in atoms
    )
    q0_atoms = q0["clauses"][0]["atoms"]
    for atom in q0_atoms:
        failure = allowed_q0_failure_tuples(atom, output_map, domains)
        found = first_solution(
            domains, (*transfer_constraints, *clause_constraints, failure)
        )
        if found is not None:
            return found
    return None


def bounded_rows() -> tuple[tuple[int, ...], ...]:
    return tuple(
        (*carries, digit)
        for carries in itertools.product((0, 1), repeat=12)
        for digit in range(19)
    )


def row_holds(atoms: list[dict[str, object]], row: tuple[int, ...]) -> bool:
    assignment = dict(zip(P30_VARIABLES, row, strict=True))
    return all(affine_atom_holds(atom, assignment) for atom in atoms)


def centered_residue(value: int, modulus: int) -> int:
    residue = value % modulus
    return residue - modulus if residue > modulus // 2 else residue


def normalize_atom(
    relation: str,
    terms: tuple[tuple[str, int], ...],
    constant: int,
    modulus: int | None = None,
) -> dict[str, object] | None:
    ordered = sorted(terms)
    if relation == "congruent":
        assert modulus is not None
        ordered = [
            (name, centered)
            for name, coefficient in ordered
            if (centered := centered_residue(coefficient, modulus)) != 0
        ]
        if not ordered:
            return None
        constant = centered_residue(constant, modulus)
    else:
        divisor = math.gcd(
            abs(constant), *(abs(coefficient) for _, coefficient in ordered)
        )
        divisor = max(divisor, 1)
        ordered = [(name, coefficient // divisor) for name, coefficient in ordered]
        constant //= divisor
        if relation == "eq" and ordered[0][1] < 0:
            ordered = [(name, -coefficient) for name, coefficient in ordered]
            constant = -constant
    if len(ordered) > 2 or any(abs(coefficient) > 3 for _, coefficient in ordered):
        return None
    payload: dict[str, object] = {
        "relation": relation,
        "terms": [[name, coefficient] for name, coefficient in ordered],
        "constant": constant,
    }
    if relation == "congruent":
        payload["modulus"] = modulus
    return payload


def atom_is_domain_tautology(atom: dict[str, object]) -> bool:
    names = tuple(term[0] for term in atom["terms"])
    domains = tuple(range(19) if name == "D0" else (0, 1) for name in names)
    for values in itertools.product(*domains):
        assignment = dict(zip(names, values, strict=True))
        if not affine_atom_holds(atom, assignment):
            return False
    return True


def generate_seed_pair_pool(
    first: tuple[int, ...], second: tuple[int, ...]
) -> list[dict[str, object]]:
    if len(first) != 13 or len(second) != 13 or first == second:
        raise Reject("seed-pair rows differ")
    first_assignment = dict(zip(P30_VARIABLES, first, strict=True))
    second_assignment = dict(zip(P30_VARIABLES, second, strict=True))
    coefficients = (-3, -2, -1, 1, 2, 3)
    atoms: dict[bytes, dict[str, object]] = {}
    for support in (1, 2):
        for names in itertools.combinations(P30_VARIABLES, support):
            for selected in itertools.product(coefficients, repeat=support):
                if math.gcd(*(abs(value) for value in selected)) != 1:
                    continue
                terms = tuple(zip(names, selected, strict=True))
                first_value = sum(
                    coefficient * first_assignment[name]
                    for name, coefficient in terms
                )
                second_value = sum(
                    coefficient * second_assignment[name]
                    for name, coefficient in terms
                )
                proposals: list[dict[str, object] | None] = []
                if first_value == second_value:
                    proposals.append(normalize_atom("eq", terms, first_value))
                proposals.extend(
                    (
                        normalize_atom(
                            "le", terms, max(first_value, second_value)
                        ),
                        normalize_atom(
                            "le",
                            tuple((name, -coefficient) for name, coefficient in terms),
                            -min(first_value, second_value),
                        ),
                    )
                )
                for modulus in range(2, 20):
                    if (first_value - second_value) % modulus == 0:
                        proposals.append(
                            normalize_atom(
                                "congruent",
                                terms,
                                first_value % modulus,
                                modulus,
                            )
                        )
                for atom in proposals:
                    if atom is not None:
                        atoms[canonical_bytes(atom)] = atom
    return [
        atoms[key]
        for key in sorted(atoms)
        if not atom_is_domain_tautology(atoms[key])
    ]


def parse_seed_pair(value: object, promoted: tuple[tuple[int, ...], ...]) -> tuple[
    tuple[int, int], tuple[tuple[int, ...], tuple[int, ...]]
]:
    if not isinstance(value, dict):
        raise Reject("seed pair must be an object")
    require_keys(value, {"indices", "rows"}, "seed pair")
    indices = value["indices"]
    rows = value["rows"]
    if (
        not isinstance(indices, list)
        or len(indices) != 2
        or any(not is_int(index) for index in indices)
        or not 0 <= indices[0] < indices[1] < 18
    ):
        raise Reject("seed-pair indices differ")
    if not isinstance(rows, list) or len(rows) != 2 or any(
        not isinstance(row, list)
        or len(row) != 13
        or any(not is_int(item) for item in row)
        for row in rows
    ):
        raise Reject("seed-pair rows differ")
    row_tuple = (tuple(rows[0]), tuple(rows[1]))
    index_tuple = (indices[0], indices[1])
    if row_tuple != (promoted[index_tuple[0]], promoted[index_tuple[1]]):
        raise Reject("seed-pair rows do not match promoted indices")
    return index_tuple, row_tuple


def atom_sha256(atom: dict[str, object]) -> str:
    return hashlib.sha256(canonical_bytes(atom)).hexdigest()


def conjunction_sha256(atoms: list[dict[str, object]]) -> str:
    return hashlib.sha256(canonical_bytes(atoms)).hexdigest()


def singleton_extent(atom: dict[str, object]) -> int:
    names = tuple(
        name for name in P30_VARIABLES if any(term[0] == name for term in atom["terms"])
    )
    domains = tuple(range(19) if name == "D0" else (0, 1) for name in names)
    satisfying = 0
    for values in itertools.product(*domains):
        assignment = dict(zip(names, values, strict=True))
        if affine_atom_holds(atom, assignment):
            satisfying += 1
    free_multiplier = math.prod(
        19 if name == "D0" else 2 for name in P30_VARIABLES if name not in names
    )
    return satisfying * free_multiplier


def q0_holds(q0: dict[str, object], output: dict[str, int]) -> bool:
    clauses = q0.get("clauses")
    if not isinstance(clauses, list):
        raise Reject("Q0 clauses changed")
    return any(
        isinstance(clause, dict)
        and isinstance(clause.get("atoms"), list)
        and all(q0_atom_holds(atom, output) for atom in clause["atoms"])
        for clause in clauses
    )


def replay_witness(
    witness: object,
    selected: tuple[dict[str, object], ...],
    domains: dict[str, set[int]],
    input_map: dict[str, str],
    output_map: dict[str, str],
    q0: dict[str, object],
) -> tuple[dict[str, int], dict[str, int], tuple[int, ...], bool]:
    if not isinstance(witness, dict):
        raise Reject("SAT query witness must be an object")
    require_keys(
        witness, {"input_state", "output_state", "local_state"}, "SAT query witness"
    )
    sections = tuple(witness[name] for name in ("input_state", "output_state", "local_state"))
    if any(not isinstance(section, dict) for section in sections):
        raise Reject("SAT query witness sections differ")
    input_value, output_value, local_value = sections
    expected_input = {f"input:{name}" for name in input_map}
    expected_output = {f"output:{name}" for name in output_map}
    if set(input_value) != expected_input or set(output_value) != expected_output:
        raise Reject("SAT query witness boundary variables differ")
    assignment: dict[str, int] = {}
    input_assignment: dict[str, int] = {}
    output_assignment: dict[str, int] = {}
    for scoped, value in input_value.items():
        canonical = scoped.removeprefix("input:")
        if not is_int(value):
            raise Reject("SAT query witness input value differs")
        assignment[input_map[canonical]] = value
        input_assignment[canonical] = value
    for scoped, value in output_value.items():
        canonical = scoped.removeprefix("output:")
        if not is_int(value):
            raise Reject("SAT query witness output value differs")
        assignment[output_map[canonical]] = value
        output_assignment[canonical] = value
    for scoped, value in local_value.items():
        if not isinstance(scoped, str) or not scoped.startswith("local:") or not is_int(value):
            raise Reject("SAT query witness local value differs")
        original = scoped.removeprefix("local:")
        if original in assignment:
            raise Reject("SAT query witness sections overlap")
        assignment[original] = value
    if set(assignment) != set(domains) or any(
        value not in domains[name] for name, value in assignment.items()
    ):
        raise Reject("SAT query witness full assignment differs")
    residuals = tuple(equation_residual(equation, assignment, 19) for equation in selected)
    return input_assignment, output_assignment, residuals, q0_holds(q0, output_assignment)


def parse_incremental_transcript(
    value: object,
    promoted: tuple[tuple[int, ...], ...],
    domains: dict[str, set[int]],
    constraints: tuple[Constraint, ...],
    selected: tuple[dict[str, object], ...],
    input_map: dict[str, str],
    output_map: dict[str, str],
    q0: dict[str, object],
) -> tuple[
    dict[str, tuple[list[dict[str, object]], str]],
    list[dict[str, object]],
]:
    if not isinstance(value, dict):
        raise Reject("incremental transcript must be an object")
    require_keys(value, {"queries", "pairs"}, "incremental transcript")
    queries_value = value["queries"]
    pairs_value = value["pairs"]
    if not isinstance(queries_value, list) or not isinstance(pairs_value, list):
        raise Reject("incremental transcript lists differ")
    pairs: list[dict[str, object]] = []
    atom_by_digest: dict[str, dict[str, object]] = {}
    expected_pairs = list(itertools.combinations(range(18), 2))
    for pair_index, pair_value in enumerate(pairs_value):
        if not isinstance(pair_value, dict):
            raise Reject("pair trace must be an object")
        require_keys(
            pair_value,
            {"seed_pair", "pool_size", "pool_sha256", "visits"},
            "pair trace",
        )
        indices, rows = parse_seed_pair(pair_value["seed_pair"], promoted)
        if pair_index >= len(expected_pairs) or indices != expected_pairs[pair_index]:
            raise Reject("pair trace order differs")
        pool = generate_seed_pair_pool(*rows)
        if pair_value["pool_size"] != len(pool) or pair_value["pool_sha256"] != hashlib.sha256(
            canonical_bytes(pool)
        ).hexdigest():
            raise Reject("pair trace pool boundary differs")
        visits = pair_value["visits"]
        if not isinstance(visits, list) or not visits:
            raise Reject("pair trace visits differ")
        pool_by_digest = {atom_sha256(atom): atom for atom in pool}
        for digest, atom in pool_by_digest.items():
            previous = atom_by_digest.setdefault(digest, atom)
            if previous != atom:
                raise Reject("seed-pool atom digest collision")
        pairs.append(
            {
                "indices": indices,
                "pool": pool,
                "pool_by_digest": pool_by_digest,
                "visits": visits,
            }
        )

    query_by_digest: dict[str, tuple[list[dict[str, object]], str]] = {}
    query_order: list[str] = []
    query_payload_by_digest: dict[str, dict[str, object]] = {}
    for query in queries_value:
        if not isinstance(query, dict):
            raise Reject("query record must be an object")
        require_keys(
            query,
            {
                "conjunction",
                "conjunction_sha256",
                "status",
                "witness",
                "equation_residuals",
                "q0_holds",
            },
            "query record",
        )
        digests = query["conjunction"]
        if not isinstance(digests, list) or len(digests) > 6 or any(
            not isinstance(digest, str) or digest not in atom_by_digest for digest in digests
        ):
            raise Reject("query conjunction atom digests differ")
        atoms = [atom_by_digest[digest] for digest in digests]
        if [canonical_bytes(atom) for atom in atoms] != sorted(
            {canonical_bytes(atom) for atom in atoms}
        ):
            raise Reject("query conjunction is not canonical and distinct")
        digest = conjunction_sha256(atoms)
        if query["conjunction_sha256"] != digest:
            raise Reject("query digest differs")
        if digest in query_by_digest:
            raise Reject("query record digest repeats")
        status = query["status"]
        if status == "SAT":
            if query["witness"] is None or query["equation_residuals"] != [0] * 12 or query[
                "q0_holds"
            ] is not False:
                raise Reject("SAT query replay fields differ")
        elif status == "UNSAT":
            if query["witness"] is not None or query["equation_residuals"] != [] or query[
                "q0_holds"
            ] is not None:
                raise Reject("UNSAT query replay fields differ")
        else:
            raise Reject("query status differs")
        query_by_digest[digest] = (atoms, status)
        query_payload_by_digest[digest] = query
        query_order.append(digest)

    fresh_order: list[str] = []
    for pair in pairs:
        pool = pair["pool"]
        pool_by_digest = pair["pool_by_digest"]
        visits = pair["visits"]
        seen: dict[str, dict[str, object]] = {}
        prior_inputs: list[tuple[tuple[str, int], ...]] = []
        for visit_index, visit in enumerate(visits):
            if not isinstance(visit, dict):
                raise Reject("search visit must be an object")
            require_keys(
                visit,
                {
                    "purpose",
                    "parent_sha256",
                    "query_sha256",
                    "fresh_query",
                    "violated_atom_sha256s",
                    "branch_atom_sha256s",
                },
                "search visit",
            )
            purpose = visit["purpose"]
            digest = visit["query_sha256"]
            parent = visit["parent_sha256"]
            if purpose not in {"ROOT", "SEARCH", "REDUCTION", "ACCEPTANCE_REPLAY"}:
                raise Reject("search visit purpose differs")
            if digest not in query_by_digest or not isinstance(visit["fresh_query"], bool):
                raise Reject("search visit query link differs")
            atoms, status = query_by_digest[digest]
            if not {canonical_bytes(atom) for atom in atoms} <= {
                canonical_bytes(atom) for atom in pool
            }:
                raise Reject("search query leaves its pair pool")
            if visit_index == 0:
                if purpose != "ROOT" or parent is not None or atoms:
                    raise Reject("pair root visit differs")
            elif purpose == "ROOT":
                raise Reject("pair repeats its root visit")
            if parent is not None and parent not in seen:
                raise Reject("search visit parent link differs")
            if purpose == "SEARCH":
                if parent is None:
                    raise Reject("search child omits its parent")
                parent_atoms = query_by_digest[parent][0]
                if len(atoms) != len(parent_atoms) + 1 or not {
                    canonical_bytes(atom) for atom in parent_atoms
                } < {canonical_bytes(atom) for atom in atoms}:
                    raise Reject("search child conjunction differs")
            violated = visit["violated_atom_sha256s"]
            branches = visit["branch_atom_sha256s"]
            if (
                not isinstance(violated, list)
                or not isinstance(branches, list)
                or len(set(violated)) != len(violated)
                or set(violated) != set(branches)
                or any(digest not in pool_by_digest for digest in violated)
            ):
                raise Reject("search visit branch set differs")
            query_payload = query_payload_by_digest[digest]
            if status == "UNSAT":
                if violated or branches:
                    raise Reject("UNSAT search visit has branch atoms")
            else:
                input_assignment, _, residuals, witness_q0 = replay_witness(
                    query_payload["witness"],
                    selected,
                    domains,
                    input_map,
                    output_map,
                    q0,
                )
                if residuals != tuple(query_payload["equation_residuals"]) or any(residuals):
                    raise Reject("SAT query equation replay differs")
                if witness_q0 is not query_payload["q0_holds"] or witness_q0:
                    raise Reject("SAT query Q0 replay differs")
                if not all(affine_atom_holds(atom, input_assignment) for atom in atoms):
                    raise Reject("SAT query witness violates its conjunction")
                canonical_input = tuple((name, input_assignment[name]) for name in P30_VARIABLES)
                if canonical_input not in prior_inputs:
                    prior_inputs.append(canonical_input)
                actual_violated = [
                    atom_sha256(atom)
                    for atom in pool
                    if not affine_atom_holds(atom, input_assignment)
                ]

                def branch_key(
                    atom_digest: str,
                    _pool_by_digest: dict[str, dict[str, object]] = pool_by_digest,
                    _prior_inputs: list[tuple[tuple[str, int], ...]] = prior_inputs,
                ) -> tuple[object, ...]:
                    atom = _pool_by_digest[atom_digest]
                    excluded = sum(
                        not affine_atom_holds(atom, dict(prior))
                        for prior in _prior_inputs
                    )
                    coverage = sum(
                        row_holds([atom], promoted_row) for promoted_row in promoted
                    )
                    return (
                        -excluded,
                        -coverage,
                        -singleton_extent(atom),
                        canonical_bytes(atom),
                    )

                actual_branches = sorted(actual_violated, key=branch_key)
                if violated != actual_violated:
                    raise Reject("search visit violated atoms differ")
                if branches != actual_branches:
                    raise Reject("search visit branch order differs")
            if visit["fresh_query"]:
                fresh_order.append(digest)
            seen[digest] = visit
    if fresh_order != query_order or len(set(fresh_order)) != len(fresh_order):
        raise Reject("fresh-query order differs")

    for digest, (atoms, status) in query_by_digest.items():
        bad = first_bad_solution(domains, constraints, input_map, output_map, q0, atoms)
        actual_status = "SAT" if bad is not None else "UNSAT"
        if status != actual_status:
            raise Reject(f"claimed {status} query is {actual_status}: {digest}")
    return query_by_digest, pairs


def verify_provenance(
    provenance: object,
    clause_atoms: list[dict[str, object]],
    promoted: tuple[tuple[int, ...], ...],
    domains: dict[str, set[int]],
    constraints: tuple[Constraint, ...],
    input_map: dict[str, str],
    output_map: dict[str, str],
    q0: dict[str, object],
    query_by_digest: dict[str, tuple[list[dict[str, object]], str]],
    pairs: list[dict[str, object]],
) -> tuple[tuple[int, int], tuple[int, ...], int]:
    if not isinstance(provenance, dict):
        raise Reject("safe-region provenance must be an object")
    require_keys(
        provenance,
        {
            "clause",
            "seed_pair",
            "pool_size",
            "pool_sha256",
            "solver_version",
            "solver_parameters",
            "core_candidate",
            "core_candidate_sha256",
            "acquisition_query_sha256",
            "minimization_trace",
            "promoted_indices",
            "bounded_extent",
        },
        "safe-region provenance",
    )
    if provenance["clause"] != {"atoms": clause_atoms}:
        raise Reject("provenance clause differs")
    seed_indices, seed_rows = parse_seed_pair(provenance["seed_pair"], promoted)
    pool = generate_seed_pair_pool(*seed_rows)
    if provenance["pool_size"] != len(pool):
        raise Reject("seed-pair pool size differs")
    pool_digest = hashlib.sha256(canonical_bytes(pool)).hexdigest()
    if provenance["pool_sha256"] != pool_digest:
        raise Reject("seed-pair pool digest differs")
    if provenance["solver_parameters"] != [
        ["phase_selection", 0],
        ["random_seed", 0],
    ]:
        raise Reject("solver parameters differ")
    if not isinstance(provenance["solver_version"], str) or not provenance[
        "solver_version"
    ]:
        raise Reject("solver version differs")
    core_value = provenance["core_candidate"]
    if not isinstance(core_value, list):
        raise Reject("core candidate must be a list")
    core_candidate = [parse_affine_atom(atom) for atom in core_value]
    core_bytes = [canonical_bytes(atom) for atom in core_candidate]
    if not 1 <= len(core_candidate) <= 6 or core_bytes != sorted(set(core_bytes)):
        raise Reject("core candidate is not canonical and distinct")
    if not set(core_bytes) <= {canonical_bytes(atom) for atom in pool}:
        raise Reject("core candidate contains an atom outside the seed pool")
    core_digest = hashlib.sha256(canonical_bytes(core_candidate)).hexdigest()
    if (
        provenance["core_candidate_sha256"] != core_digest
        or provenance["acquisition_query_sha256"] != core_digest
    ):
        raise Reject("acquisition core digest differs")
    if query_by_digest.get(core_digest) != (core_candidate, "UNSAT"):
        raise Reject("acquisition query record differs")
    pair = next((item for item in pairs if item["indices"] == seed_indices), None)
    if pair is None:
        raise Reject("acquisition seed pair has no trace")
    visits = pair["visits"]
    if not any(
        visit["query_sha256"] == core_digest
        and visit["purpose"] in {"ROOT", "SEARCH"}
        for visit in visits
    ):
        raise Reject("acquisition search visit is missing")
    trace = provenance["minimization_trace"]
    if not isinstance(trace, list) or not trace:
        raise Reject("minimization trace is empty")
    current = list(core_candidate)
    for step in trace:
        if not isinstance(step, dict):
            raise Reject("core-reduction step must be an object")
        require_keys(
            step,
            {"removed_atom_sha256", "candidate_sha256", "status", "retained"},
            "core-reduction step",
        )
        removed_index = None
        for index, atom in enumerate(current):
            if hashlib.sha256(canonical_bytes(atom)).hexdigest() == step[
                "removed_atom_sha256"
            ]:
                removed_index = index
                break
        if removed_index is None:
            raise Reject("core-reduction atom is unavailable")
        candidate = current[:removed_index] + current[removed_index + 1 :]
        if step["candidate_sha256"] != hashlib.sha256(
            canonical_bytes(candidate)
        ).hexdigest():
            raise Reject("core-reduction candidate digest differs")
        found = first_bad_solution(
            domains, constraints, input_map, output_map, q0, candidate
        )
        status = "SAT" if found is not None else "UNSAT"
        if step["status"] != status or step["retained"] != (status == "SAT"):
            raise Reject("core-reduction status differs")
        candidate_digest = hashlib.sha256(canonical_bytes(candidate)).hexdigest()
        if not any(
            visit["purpose"] == "REDUCTION"
            and visit["parent_sha256"] == core_digest
            and visit["query_sha256"] == candidate_digest
            for visit in visits
        ):
            raise Reject("core-reduction visit is missing")
        if status == "UNSAT":
            current = candidate
    if [canonical_bytes(atom) for atom in current] != [
        canonical_bytes(atom) for atom in clause_atoms
    ]:
        raise Reject("minimization trace does not produce the clause")
    clause_digest = hashlib.sha256(canonical_bytes(clause_atoms)).hexdigest()
    if not any(
        visit["purpose"] == "ACCEPTANCE_REPLAY"
        and visit["parent_sha256"] == core_digest
        and visit["query_sha256"] == clause_digest
        for visit in visits
    ):
        raise Reject("fresh acceptance replay is missing")
    indices = provenance["promoted_indices"]
    if not isinstance(indices, list) or indices != sorted(set(indices)) or any(
        not is_int(index) or not 0 <= index < 18 for index in indices
    ):
        raise Reject("promoted indices differ")
    actual_indices = tuple(
        index for index, row in enumerate(promoted) if row_holds(clause_atoms, row)
    )
    if tuple(indices) != actual_indices or not set(seed_indices) <= set(actual_indices):
        raise Reject("promoted coverage differs")
    extent = sum(row_holds(clause_atoms, row) for row in bounded_rows())
    if provenance["bounded_extent"] != extent:
        raise Reject("bounded extent differs")
    return seed_indices, actual_indices, extent


def load_frozen_sources(
    args: argparse.Namespace,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    paths = (
        args.equations,
        args.frontier,
        args.t27_evidence,
        args.t28_evidence,
        args.t28_independent,
        args.t29_trace,
        args.t29_dataset,
        args.t29_evidence,
        args.t29_certificate,
        args.t29_independent,
        args.t30_evidence,
        args.t30_certificate,
        args.t30_independent,
    )
    sources = tuple(
        load_object(path, f"frozen source {index}")
        for index, path in enumerate(paths)
    )
    equations = sources[0][1]
    frontier = sources[1][1]
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
    t30_certificate = sources[11][1]
    q0 = t30_certificate.get("q0")
    if not isinstance(q0, dict):
        raise Reject("T30 certificate Q0 is missing")
    require_q0(q0)
    return equations, frontier, q0


def parse_milestone(payload: dict[str, object]) -> tuple[
    list[dict[str, object]], object, object, int, int
]:
    require_keys(
        payload,
        {
            "schema",
            "status",
            "source_digests",
            "t29_artifact_digests",
            "t30_artifact_digests",
            "t32_source_digests",
            "t32_commits",
            "t32_design_sha256",
            "t33_design_sha256",
            "t33_restart_design_sha256",
            "clause",
            "provenance",
            "seed_pair_count",
            "region_test_count",
            "search_transcript",
            "primary_safety_status",
        },
        "milestone",
    )
    if payload["schema"] != "t33-base19-safe-region-milestone-v2":
        raise Reject("milestone schema changed")
    if payload["status"] != "PASS":
        raise Reject("milestone status changed")
    if payload["source_digests"] != {
        name: SOURCE_DIGESTS[name] for name in ("equations", "frontier", "provenances")
    }:
        raise Reject("milestone source digests changed")
    if payload["t29_artifact_digests"] != T29_DIGESTS:
        raise Reject("milestone T29 artifact digests changed")
    if payload["t30_artifact_digests"] != T30_DIGESTS:
        raise Reject("milestone T30 artifact digests changed")
    if payload["t32_source_digests"] != T32_DIGESTS:
        raise Reject("milestone T32 source digests changed")
    if payload["t32_commits"] != T32_COMMITS:
        raise Reject("milestone T32 commits changed")
    if (
        payload["t32_design_sha256"] != T32_DESIGN_SHA256
        or payload["t33_design_sha256"] != T33_DESIGN_SHA256
        or payload["t33_restart_design_sha256"] != T33_RESTART_DESIGN_SHA256
    ):
        raise Reject("milestone design boundary changed")
    if payload["primary_safety_status"] != "UNSAT":
        raise Reject("milestone primary safety status changed")
    pair_count = payload["seed_pair_count"]
    region_count = payload["region_test_count"]
    if (
        not is_int(pair_count)
        or not 1 <= pair_count <= 153
        or not is_int(region_count)
        or not 1 <= region_count <= 2_000
    ):
        raise Reject("milestone counters differ")
    return (
        parse_clause(payload["clause"]),
        payload["provenance"],
        payload["search_transcript"],
        pair_count,
        region_count,
    )


def _add_raw_arguments(parser: argparse.ArgumentParser) -> None:
    for name in (
        "equations",
        "frontier",
        "t27_evidence",
        "t28_evidence",
        "t28_independent",
        "t29_trace",
        "t29_dataset",
        "t29_evidence",
        "t29_certificate",
        "t29_independent",
        "t30_evidence",
        "t30_certificate",
        "t30_independent",
        "candidate",
    ):
        parser.add_argument(name, type=Path)


def audit_milestone(args: argparse.Namespace) -> dict[str, object]:
    equations, frontier, q0 = load_frozen_sources(args)
    _, candidate = load_object(args.candidate, "safe-region milestone")
    atoms, provenance, transcript, pair_count, region_count = parse_milestone(candidate)
    domains, constraints, selected, input_map, output_map, promoted = layer_relation(
        equations, frontier
    )
    query_by_digest, pairs = parse_incremental_transcript(
        transcript,
        promoted,
        domains,
        constraints,
        selected,
        input_map,
        output_map,
        q0,
    )
    if len(pairs) != pair_count or len(query_by_digest) != region_count:
        raise Reject("milestone transcript counter differs")
    bad = first_bad_solution(
        domains, constraints, input_map, output_map, q0, atoms
    )
    if bad is not None:
        values = dict(bad)
        bad_input = {
            canonical: values[original] for canonical, original in input_map.items()
        }
        raise Reject(
            "safe-region counterexample: "
            + canonical_bytes(bad_input).decode("utf-8")
        )
    seed_indices, promoted_indices, extent = verify_provenance(
        provenance,
        atoms,
        promoted,
        domains,
        constraints,
        input_map,
        output_map,
        q0,
        query_by_digest,
        pairs,
    )
    if len(promoted_indices) < 2 or extent < 4:
        raise Reject("safe-region diversity gate failed")
    predicate = {
        "layer": 30,
        "variables": list(P30_VARIABLES),
        "clauses": [{"atoms": atoms}],
    }
    table = {
        "layer": 30,
        "variables": list(P30_VARIABLES),
        "states": [list(promoted[index]) for index in promoted_indices],
    }
    predicate_bytes = len(canonical_bytes(predicate))
    table_bytes = len(canonical_bytes(table))
    if predicate_bytes >= table_bytes:
        raise Reject("safe-region milestone is not compact")
    return {
        "schema": "t33-base19-safe-region-milestone-independent-v2",
        "status": "PASS",
        "repository_imports": [],
        "seed_indices": list(seed_indices),
        "promoted_indices": list(promoted_indices),
        "bounded_extent": extent,
        "predicate_bytes": predicate_bytes,
        "covered_table_bytes": table_bytes,
        "safety_status": "UNSAT",
        "enumerated_input_count": 77_824,
        "seed_pair_count": pair_count,
        "region_test_count": region_count,
        "query_record_count": len(query_by_digest),
        "transcript_status": "PASS",
        "t33_restart_design_sha256": T33_RESTART_DESIGN_SHA256,
    }


def audit_full(args: argparse.Namespace) -> dict[str, object]:
    raise Reject(f"full audit requires a complete T33 certificate: {args.candidate}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    milestone = subparsers.add_parser("milestone", help="audit one safe region")
    _add_raw_arguments(milestone)
    milestone.set_defaults(handler=audit_milestone)
    full = subparsers.add_parser("full", help="audit a complete safe-region cover")
    _add_raw_arguments(full)
    full.set_defaults(handler=audit_full)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except Reject as error:
        print(f"REJECT: {error}", file=sys.stderr)
        return 1
    print(canonical_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
