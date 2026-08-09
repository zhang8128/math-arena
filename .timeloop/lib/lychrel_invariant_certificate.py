"""Typed, deterministic certificates for radial reverse-add invariants."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass

_RELATIONS = frozenset({"eq", "le", "congruent"})
_UNORDERED_SEQUENCE_KEYS = frozenset(
    {"atoms", "clauses", "obligations", "predicates", "terms"}
)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _canonical_value(value: object, *, parent_key: str | None = None) -> object:
    if hasattr(value, "to_payload"):
        return _canonical_value(value.to_payload())  # type: ignore[union-attr]
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical_value(
            {field.name: getattr(value, field.name) for field in fields(value)}
        )
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(item, parent_key=str(key))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        items = [_canonical_value(item) for item in value]
        if parent_key in _UNORDERED_SEQUENCE_KEYS:
            items.sort(
                key=lambda item: json.dumps(
                    item,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            )
        return items
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"value is not canonically JSON serializable: {type(value).__name__}")


def canonical_bytes(value: object) -> bytes:
    """Return canonical, whitespace-free, UTF-8 JSON bytes."""
    return json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True)
class LinearAtom:
    relation: str
    terms: tuple[tuple[str, int], ...]
    constant: int
    modulus: int | None = None

    def __post_init__(self) -> None:
        if self.relation not in _RELATIONS:
            raise ValueError(f"unsupported relation: {self.relation}")
        if not _is_int(self.constant):
            raise ValueError("atom constant must be an integer")
        if not self.terms:
            raise ValueError("an atom must contain at least one term")

        names: set[str] = set()
        normalized: list[tuple[str, int]] = []
        for term in self.terms:
            if not isinstance(term, tuple) or len(term) != 2:
                raise ValueError("each term must be a (variable, coefficient) pair")
            name, coefficient = term
            if not isinstance(name, str) or not name:
                raise ValueError("term variable names must be nonempty strings")
            if name in names:
                raise ValueError(f"duplicate variable in atom: {name}")
            names.add(name)
            if not _is_int(coefficient):
                raise ValueError("term coefficient must be an integer")
            if coefficient == 0:
                raise ValueError("zero coefficients are not canonical")
            if abs(coefficient) > 3:
                raise ValueError("coefficient magnitude exceeds three")
            normalized.append((name, coefficient))

        normalized.sort()
        constant = self.constant
        if self.relation == "congruent":
            if not _is_int(self.modulus) or not 2 <= self.modulus <= 20:
                raise ValueError("congruence modulus must be in 2..20")
            constant %= self.modulus
        elif self.modulus is not None:
            raise ValueError("only congruence atoms have a modulus")

        if self.relation in {"eq", "le"}:
            divisor = math.gcd(
                abs(constant),
                *(abs(coefficient) for _, coefficient in normalized),
            )
            if divisor > 1:
                normalized = [
                    (name, coefficient // divisor)
                    for name, coefficient in normalized
                ]
                constant //= divisor
        if self.relation == "eq" and normalized[0][1] < 0:
            normalized = [(name, -coefficient) for name, coefficient in normalized]
            constant = -constant

        object.__setattr__(self, "terms", tuple(normalized))
        object.__setattr__(self, "constant", constant)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "relation": self.relation,
            "terms": [list(term) for term in self.terms],
            "constant": self.constant,
        }
        if self.modulus is not None:
            payload["modulus"] = self.modulus
        return payload


@dataclass(frozen=True)
class Conjunction:
    atoms: tuple[LinearAtom, ...]

    def __post_init__(self) -> None:
        if not self.atoms:
            raise ValueError("a conjunction must contain at least one atom")
        if len(self.atoms) > 12:
            raise ValueError("a conjunction may contain at most 12 atoms")
        if len(set(self.atoms)) != len(self.atoms):
            raise ValueError("a conjunction may not repeat an atom")
        object.__setattr__(
            self,
            "atoms",
            tuple(sorted(self.atoms, key=canonical_bytes)),
        )

    def to_payload(self) -> dict[str, object]:
        return {"atoms": [atom.to_payload() for atom in self.atoms]}


@dataclass(frozen=True)
class LayerPredicate:
    layer: int
    variables: tuple[str, ...]
    clauses: tuple[Conjunction, ...]

    def __post_init__(self) -> None:
        if not _is_int(self.layer):
            raise ValueError("predicate layer must be an integer")
        if not self.variables or any(
            not isinstance(variable, str) or not variable
            for variable in self.variables
        ):
            raise ValueError("predicate variables must be nonempty strings")
        if len(set(self.variables)) != len(self.variables):
            raise ValueError("predicate variables must be unique")
        if not self.clauses:
            raise ValueError("a predicate must contain at least one clause")
        if len(self.clauses) > 3:
            raise ValueError("a predicate may contain at most three clauses")
        scope = set(self.variables)
        used = {
            variable
            for clause in self.clauses
            for atom in clause.atoms
            for variable, _ in atom.terms
        }
        outside = sorted(used - scope)
        if outside:
            raise ValueError(f"atom variables outside predicate scope: {outside}")
        object.__setattr__(
            self,
            "clauses",
            tuple(sorted(self.clauses, key=canonical_bytes)),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "layer": self.layer,
            "variables": list(self.variables),
            "clauses": [clause.to_payload() for clause in self.clauses],
        }


@dataclass(frozen=True)
class InvariantCertificate:
    schema: str
    base: int
    removed: str
    source_digests: tuple[tuple[str, str], ...]
    predicates: tuple[LayerPredicate, ...]
    obligations: tuple[Mapping[str, object], ...]

    def __post_init__(self) -> None:
        if self.schema != "t27-invariant-certificate-v1":
            raise ValueError(f"unsupported certificate schema: {self.schema}")
        if not _is_int(self.base) or self.base < 2:
            raise ValueError("certificate base must be an integer at least two")
        if not isinstance(self.removed, str) or not self.removed:
            raise ValueError("certificate removed provenance must be nonempty")
        layers = [predicate.layer for predicate in self.predicates]
        if len(layers) != len(set(layers)):
            raise ValueError("certificate predicate layers must be unique")
        object.__setattr__(
            self,
            "predicates",
            tuple(sorted(self.predicates, key=lambda predicate: predicate.layer)),
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "base": self.base,
            "removed": self.removed,
            "source_digests": dict(self.source_digests),
            "predicates": [predicate.to_payload() for predicate in self.predicates],
            "obligations": [dict(obligation) for obligation in self.obligations],
        }


def _evaluate_atom(atom: LinearAtom, assignment: Mapping[str, int]) -> bool:
    missing = [name for name, _ in atom.terms if name not in assignment]
    if missing:
        raise ValueError(f"missing assignment for variables: {missing}")
    values = [assignment[name] for name, _ in atom.terms]
    if any(not _is_int(value) for value in values):
        raise ValueError("assignment values must be integers")
    total = sum(
        coefficient * assignment[name]
        for name, coefficient in atom.terms
    )
    if atom.relation == "eq":
        return total == atom.constant
    if atom.relation == "le":
        return total <= atom.constant
    if atom.relation == "congruent":
        assert atom.modulus is not None
        return (total - atom.constant) % atom.modulus == 0
    raise ValueError(f"unsupported relation: {atom.relation}")


def evaluate_predicate(
    predicate: LayerPredicate,
    assignment: Mapping[str, int],
) -> bool:
    """Evaluate one bounded disjunctive predicate exactly."""
    missing = [variable for variable in predicate.variables if variable not in assignment]
    if missing:
        raise ValueError(f"missing assignment for variables: {missing}")
    return any(
        all(_evaluate_atom(atom, assignment) for atom in clause.atoms)
        for clause in predicate.clauses
    )


def _require_exact_keys(
    value: Mapping[str, object],
    expected: set[str],
    context: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{context} keys differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _parse_atom(payload: object) -> LinearAtom:
    if not isinstance(payload, Mapping):
        raise ValueError("atom must be an object")
    relation = payload.get("relation")
    expected = {"relation", "terms", "constant"}
    if relation == "congruent":
        expected.add("modulus")
    _require_exact_keys(payload, expected, "atom")
    terms_payload = payload["terms"]
    if not isinstance(terms_payload, list):
        raise ValueError("atom terms must be a list")
    terms: list[tuple[str, int]] = []
    names: set[str] = set()
    for term in terms_payload:
        if not isinstance(term, list) or len(term) != 2:
            raise ValueError("each serialized term must be a two-item list")
        name, coefficient = term
        if not isinstance(name, str) or not name:
            raise ValueError("serialized variable must be a nonempty string")
        if name in names:
            raise ValueError(f"duplicate variable in serialized atom: {name}")
        names.add(name)
        if not _is_int(coefficient):
            raise ValueError("serialized coefficient must be an integer")
        terms.append((name, coefficient))
    constant = payload["constant"]
    if not _is_int(constant):
        raise ValueError("serialized constant must be an integer")
    modulus = payload.get("modulus")
    if relation == "congruent" and _is_int(modulus) and not 0 <= constant < modulus:
        raise ValueError("congruence constant must be a canonical residue")
    return LinearAtom(
        relation=relation,  # type: ignore[arg-type]
        terms=tuple(terms),
        constant=constant,
        modulus=modulus,  # type: ignore[arg-type]
    )


def _parse_predicate(payload: object) -> LayerPredicate:
    if not isinstance(payload, Mapping):
        raise ValueError("predicate must be an object")
    _require_exact_keys(payload, {"layer", "variables", "clauses"}, "predicate")
    layer = payload["layer"]
    variables = payload["variables"]
    clauses = payload["clauses"]
    if not _is_int(layer):
        raise ValueError("serialized predicate layer must be an integer")
    if not isinstance(variables, list):
        raise ValueError("serialized predicate variables must be a list")
    if not isinstance(clauses, list):
        raise ValueError("serialized predicate clauses must be a list")
    parsed_clauses = []
    for clause in clauses:
        if not isinstance(clause, Mapping):
            raise ValueError("clause must be an object")
        _require_exact_keys(clause, {"atoms"}, "clause")
        atoms = clause["atoms"]
        if not isinstance(atoms, list):
            raise ValueError("serialized atoms must be a list")
        parsed_clauses.append(Conjunction(tuple(_parse_atom(atom) for atom in atoms)))
    return LayerPredicate(
        layer,
        tuple(variables),  # type: ignore[arg-type]
        tuple(parsed_clauses),
    )


def parse_certificate(payload: object) -> InvariantCertificate:
    """Parse a certificate while rejecting noncanonical serialized syntax."""
    if not isinstance(payload, Mapping):
        raise ValueError("certificate must be an object")
    _require_exact_keys(
        payload,
        {
            "schema",
            "base",
            "removed",
            "source_digests",
            "predicates",
            "obligations",
        },
        "certificate",
    )
    digests = payload["source_digests"]
    predicates = payload["predicates"]
    obligations = payload["obligations"]
    if not isinstance(digests, Mapping):
        raise ValueError("source_digests must be an object")
    normalized_digests = []
    for name, digest in digests.items():
        if not isinstance(name, str) or not isinstance(digest, str):
            raise ValueError("source digest entries must be strings")
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"source digest is not lowercase SHA-256: {name}")
        normalized_digests.append((name, digest))
    if not isinstance(predicates, list):
        raise ValueError("predicates must be a list")
    if not isinstance(obligations, list) or any(
        not isinstance(item, Mapping) for item in obligations
    ):
        raise ValueError("obligations must be a list of objects")
    return InvariantCertificate(
        schema=payload["schema"],  # type: ignore[arg-type]
        base=payload["base"],  # type: ignore[arg-type]
        removed=payload["removed"],  # type: ignore[arg-type]
        source_digests=tuple(sorted(normalized_digests)),
        predicates=tuple(_parse_predicate(item) for item in predicates),
        obligations=tuple(dict(item) for item in obligations),
    )


def compression_record(
    certificate_payload: object,
    state_payload: object,
) -> dict[str, int | bool]:
    """Compare canonical byte sizes without a lossy floating-point ratio."""
    certificate_size = len(canonical_bytes(certificate_payload))
    state_size = len(canonical_bytes(state_payload))
    return {
        "certificate_bytes": certificate_size,
        "state_table_bytes": state_size,
        "compression_numerator": state_size,
        "compression_denominator": certificate_size,
        "at_least_tenfold": state_size >= 10 * certificate_size,
    }
