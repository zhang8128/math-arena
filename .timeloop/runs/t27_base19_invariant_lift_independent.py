#!/usr/bin/env python3
"""Independently audit only the achieved T27 terminal tail lemma."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from pathlib import Path

_CARRY_RE = re.compile(r"c:p(?P<phase>\d+):n0:col(?P<column>\d+)\Z")
_DIGIT_RE = re.compile(r"(?:digit:)?p(?P<phase>\d+):f(?P<fragment>\d+):d(?P<offset>\d+)\Z")


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


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _content_digest(payload: dict[str, object], label: str) -> str:
    unsigned = dict(payload)
    claimed = unsigned.pop("content_sha256", None)
    actual = hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
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


def _atom_holds(atom: dict[str, object], state: dict[str, int]) -> bool:
    if set(atom) not in (
        {"relation", "terms", "constant"},
        {"relation", "terms", "constant", "modulus"},
    ):
        raise AuditError("predicate atom shape is invalid")
    relation = atom["relation"]
    terms = atom["terms"]
    constant = atom["constant"]
    if relation not in {"eq", "le", "congruent"}:
        raise AuditError("predicate relation is invalid")
    if not isinstance(terms, list) or not terms or not isinstance(constant, int):
        raise AuditError("predicate atom values are invalid")
    total = 0
    seen = set()
    for term in terms:
        if not isinstance(term, list) or len(term) != 2:
            raise AuditError("predicate term is invalid")
        name, coefficient = term
        if (
            not isinstance(name, str)
            or name in seen
            or name not in state
            or not isinstance(coefficient, int)
            or isinstance(coefficient, bool)
            or coefficient == 0
            or abs(coefficient) > 3
        ):
            raise AuditError("predicate term is outside the closed grammar")
        seen.add(name)
        total += coefficient * state[name]
    if relation == "eq":
        return total == constant
    if relation == "le":
        return total <= constant
    modulus = atom.get("modulus")
    if not isinstance(modulus, int) or isinstance(modulus, bool) or not 2 <= modulus <= 20:
        raise AuditError("predicate modulus is outside the closed grammar")
    return (total - constant) % modulus == 0


def _clause_holds(clause: dict[str, object], state: dict[str, int]) -> bool:
    if set(clause) != {"atoms"} or not isinstance(clause["atoms"], list):
        raise AuditError("predicate clause is invalid")
    if not 1 <= len(clause["atoms"]) <= 12:
        raise AuditError("predicate clause exceeds the atom budget")
    return all(_atom_holds(atom, state) for atom in clause["atoms"])


def _equation_variables(equation: dict[str, object]) -> tuple[str, ...]:
    names = []
    for side in ("left", "right", "target"):
        atom = equation.get(side)
        if not isinstance(atom, dict):
            raise AuditError("equation atom is invalid")
        if set(atom) == {"variable"} and isinstance(atom["variable"], str):
            names.append("digit:" + atom["variable"])
        elif set(atom) != {"literal"} or not isinstance(atom["literal"], int):
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
        assignment = dict(zip(names, values, strict=True))
        if _equation_holds(equation, assignment, base):
            allowed.append(values)
    if not allowed:
        raise AuditError("terminal equation has no bounded tuple")
    return names, tuple(allowed)


def _allowed_atom_tuples(
    atom: dict[str, object],
    canonical_to_original: dict[str, str],
    domains: dict[str, set[int]],
) -> tuple[tuple[str, ...], tuple[tuple[int, ...], ...]]:
    terms = atom["terms"]
    names = tuple(canonical_to_original[term[0]] for term in terms)
    allowed = []
    for values in itertools.product(*(sorted(domains[name]) for name in names)):
        original = dict(zip(names, values, strict=True))
        state = {
            canonical: original[name]
            for canonical, name in canonical_to_original.items()
            if name in original
        }
        if _atom_holds(atom, state):
            allowed.append(values)
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
                supported = {values[index] for values in viable}
                reduced = domains[name] & supported
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


def audit(equations_path: Path, frontier_path: Path, evidence_path: Path) -> dict[str, object]:
    manifest = _load(equations_path, "equations")
    frontier = _load(frontier_path, "frontier")
    evidence = _load(evidence_path, "evidence")
    equations_digest = _content_digest(manifest, "equations")
    frontier_digest = _content_digest(frontier, "frontier")
    sources = evidence.get("source_digests")
    if not isinstance(sources, dict) or sources.get("equations") != equations_digest:
        raise AuditError("evidence equation digest mismatch")
    if sources.get("frontier") != frontier_digest:
        raise AuditError("evidence frontier digest mismatch")
    if evidence.get("status") != "STOP" or evidence.get("gate_b_authorized") is not False:
        raise AuditError("independent tail audit accepts only the frozen Gate A STOP")
    if "symbolic_base_claim" in evidence:
        raise AuditError("STOP evidence contains an unauthorized symbolic claim")

    layers = frontier.get("layers")
    if not isinstance(layers, list):
        raise AuditError("frontier layers are invalid")
    by_number = {
        layer.get("layer"): layer for layer in layers if isinstance(layer, dict)
    }
    layer32 = by_number.get(32)
    terminal = by_number.get(33)
    if not isinstance(layer32, dict) or not isinstance(terminal, dict):
        raise AuditError("frontier omits layer 32 or 33")
    output_variables_raw = layer32.get("output_variables")
    states_raw = layer32.get("output_states")
    terminal_inputs_raw = terminal.get("input_variables")
    terminal_provenances = terminal.get("equation_provenances")
    if not all(
        isinstance(value, list)
        for value in (
            output_variables_raw,
            states_raw,
            terminal_inputs_raw,
            terminal_provenances,
        )
    ):
        raise AuditError("late frontier fields are invalid")
    output_variables = tuple(output_variables_raw)
    terminal_inputs = tuple(terminal_inputs_raw)
    if output_variables != terminal_inputs or len(states_raw) != 22:
        raise AuditError("late frontier interface or state count changed")
    original_to_canonical = _canonical_map(output_variables)
    canonical_to_original = {
        canonical: original for original, canonical in original_to_canonical.items()
    }

    tail = evidence.get("tail_lemma")
    if not isinstance(tail, dict) or tail.get("status") != "PASS":
        raise AuditError("evidence tail lemma is missing")
    predicate = tail.get("predicate")
    if not isinstance(predicate, dict) or set(predicate) != {"layer", "variables", "clauses"}:
        raise AuditError("tail predicate is invalid")
    if predicate["layer"] != 32 or predicate["variables"] != list(
        original_to_canonical.values()
    ):
        raise AuditError("tail predicate scope changed")
    clauses = predicate["clauses"]
    if not isinstance(clauses, list) or len(clauses) != 3:
        raise AuditError("tail predicate must contain exactly three clauses")
    states = []
    for raw in states_raw:
        if not isinstance(raw, list) or len(raw) != len(output_variables):
            raise AuditError("reachable state width is invalid")
        state = {
            original_to_canonical[name]: value
            for name, value in zip(output_variables, raw, strict=True)
        }
        if not any(_clause_holds(clause, state) for clause in clauses):
            raise AuditError("tail predicate misses a reachable state")
        states.append(state)

    rows = manifest.get("equations")
    if not isinstance(rows, list):
        raise AuditError("equation manifest rows are invalid")
    by_provenance = {
        row.get("provenance"): row for row in rows if isinstance(row, dict)
    }
    try:
        terminal_equations = tuple(by_provenance[name] for name in terminal_provenances)
    except KeyError as error:
        raise AuditError(f"terminal equation is missing: {error.args[0]}") from error
    if len(terminal_equations) != 12:
        raise AuditError("terminal equation count changed")
    base = manifest.get("base")
    if base != 19:
        raise AuditError("independent tail checker is frozen to base 19")
    variable_names = sorted(
        {
            name
            for equation in terminal_equations
            for name in _equation_variables(equation)
        }
    )
    domains = {
        name: set(range(2)) if name.startswith("c:") else set(range(base))
        for name in variable_names
    }
    equation_constraints = tuple(
        _allowed_equation_tuples(equation, domains, base)
        for equation in terminal_equations
    )
    statuses = []
    for clause in clauses:
        atom_constraints = tuple(
            _allowed_atom_tuples(atom, canonical_to_original, domains)
            for atom in clause["atoms"]
        )
        satisfiable = _csp_satisfiable(domains, equation_constraints + atom_constraints)
        statuses.append("SAT" if satisfiable else "UNSAT")
    if statuses != ["UNSAT", "UNSAT", "UNSAT"]:
        raise AuditError(f"tail clause admits a terminal model: {statuses}")
    return {
        "schema": "t27-base19-tail-independent-audit-v1",
        "status": "PASS",
        "scope": "tail_lemma_only",
        "repository_imports": [],
        "equations_content_sha256": equations_digest,
        "frontier_content_sha256": frontier_digest,
        "evidence_sha256": hashlib.sha256(evidence_path.read_bytes()).hexdigest(),
        "reachable_state_count": len(states),
        "terminal_equation_count": len(terminal_equations),
        "terminal_clause_statuses": statuses,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("equations", type=Path)
    parser.add_argument("frontier", type=Path)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args(argv)
    try:
        result = audit(args.equations, args.frontier, args.evidence)
    except AuditError as error:
        print(f"REJECT: {error}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(_canonical_bytes(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
