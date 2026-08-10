"""Typed certificates for the base-19 bad-image projection gate."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

from lychrel_invariant_certificate import canonical_bytes
from lychrel_reachability_separator import SemanticWitness

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

_RELATIONS = {"eq", "le", "congruent"}
_SCHEMA = "t31-base19-bad-image-projection-certificate-v1"
_PASS = "BAD_IMAGE_PROJECTION_PASS"
_STOP = "BAD_IMAGE_PROJECTION_STOP"
_REMOVED = "phase=0,n=0,column=82"
_SOURCE_NAMES = {
    "equations",
    "frontier",
    "provenances",
    "t27_evidence",
    "t28_evidence",
    "t28_independent",
}
_T29_NAMES = {"evidence", "trace", "dataset", "certificate", "independent"}
_T30_NAMES = {"evidence", "certificate", "independent", "report"}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_digest(value: object, context: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{context} must be a lowercase SHA-256")


def _validate_digest_map(
    entries: tuple[tuple[str, str], ...],
    names: set[str],
    context: str,
) -> None:
    if tuple(sorted(entries)) != entries or set(dict(entries)) != names:
        raise ValueError(f"{context} digest names differ")
    if len(entries) != len(names):
        raise ValueError(f"{context} digest names differ")
    for name, digest in entries:
        _validate_digest(digest, f"{context} digest {name}")


def _common_gcd(terms: tuple[tuple[str, int], ...], constant: int) -> int:
    result = abs(constant)
    for _, coefficient in terms:
        result = math.gcd(result, abs(coefficient))
    return max(result, 1)


def _centered_residue(value: int, modulus: int) -> int:
    residue = value % modulus
    if residue > modulus // 2:
        residue -= modulus
    return residue


@dataclass(frozen=True)
class ProjectionAtom:
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
        if len(self.terms) > 13:
            raise ValueError("atom support exceeds 13")

        seen: set[str] = set()
        normalized: list[tuple[str, int]] = []
        for term in self.terms:
            if not isinstance(term, tuple) or len(term) != 2:
                raise ValueError("each term must be a variable/coefficient pair")
            name, coefficient = term
            if not isinstance(name, str) or not name:
                raise ValueError("term variable names must be nonempty strings")
            if name in seen:
                raise ValueError(f"duplicate variable in atom: {name}")
            seen.add(name)
            if not _is_int(coefficient):
                raise ValueError("term coefficient must be an integer")
            if coefficient == 0:
                raise ValueError("zero coefficient is not canonical")
            if self.relation != "congruent" and abs(coefficient) > 9:
                raise ValueError("coefficient magnitude exceeds nine")
            normalized.append((name, coefficient))
        normalized.sort()

        constant = self.constant
        modulus = self.modulus
        if self.relation == "congruent":
            if not _is_int(modulus) or not 2 <= modulus <= 19:
                raise ValueError("congruence modulus must be in 2..19")
            normalized = [
                (name, centered)
                for name, coefficient in normalized
                if (centered := _centered_residue(coefficient, modulus)) != 0
            ]
            constant = _centered_residue(constant, modulus)
            if not normalized:
                raise ValueError("congruence normalization removed every term")
            if any(abs(coefficient) > 9 for _, coefficient in normalized):
                raise ValueError("coefficient magnitude exceeds nine")
        else:
            if modulus is not None:
                raise ValueError("only congruence atoms carry a modulus")
            divisor = _common_gcd(tuple(normalized), constant)
            normalized = [
                (name, coefficient // divisor) for name, coefficient in normalized
            ]
            constant //= divisor
            if self.relation == "eq" and normalized[0][1] < 0:
                normalized = [(name, -coefficient) for name, coefficient in normalized]
                constant = -constant

        object.__setattr__(self, "terms", tuple(normalized))
        object.__setattr__(self, "constant", constant)
        object.__setattr__(self, "modulus", modulus)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "relation": self.relation,
            "terms": [[name, coefficient] for name, coefficient in self.terms],
            "constant": self.constant,
        }
        if self.relation == "congruent":
            payload["modulus"] = self.modulus
        return payload


@dataclass(frozen=True)
class ProjectionClause:
    atoms: tuple[ProjectionAtom, ...]

    def __post_init__(self) -> None:
        if not self.atoms:
            raise ValueError("a clause must contain at least one atom")
        if len(self.atoms) > 6:
            raise ValueError("a clause may contain at most six atoms")
        if len(set(self.atoms)) != len(self.atoms):
            raise ValueError("a clause may not repeat an atom")
        object.__setattr__(self, "atoms", tuple(sorted(self.atoms, key=canonical_bytes)))

    def to_payload(self) -> dict[str, object]:
        return {"atoms": [atom.to_payload() for atom in self.atoms]}


@dataclass(frozen=True)
class Layer30Predicate:
    layer: int
    variables: tuple[str, ...]
    clauses: tuple[ProjectionClause, ...]

    def __post_init__(self) -> None:
        if self.layer != 30:
            raise ValueError("P30 must be at layer 30")
        if self.variables != P30_VARIABLES:
            raise ValueError("P30 variable scope differs")
        if not self.clauses:
            raise ValueError("P30 must contain at least one clause")
        if len(self.clauses) > 2:
            raise ValueError("P30 may contain at most two clauses")
        if len(set(self.clauses)) != len(self.clauses):
            raise ValueError("P30 may not repeat a clause")
        used = {
            name
            for clause in self.clauses
            for atom in clause.atoms
            for name, _ in atom.terms
        }
        outside = sorted(used - set(self.variables))
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


def _atom_holds(atom: ProjectionAtom, assignment: Mapping[str, int]) -> bool:
    total = sum(coefficient * assignment[name] for name, coefficient in atom.terms)
    if atom.relation == "eq":
        return total == atom.constant
    if atom.relation == "le":
        return total <= atom.constant
    assert atom.modulus is not None
    return (total - atom.constant) % atom.modulus == 0


def evaluate_p30(predicate: Layer30Predicate, assignment: Mapping[str, int]) -> bool:
    """Evaluate a T31 predicate on one exact layer-30 assignment."""
    if set(assignment) != set(predicate.variables) or any(
        not _is_int(value) for value in assignment.values()
    ):
        raise ValueError("assignment must exactly match the P30 scope")
    return any(
        all(_atom_holds(atom, assignment) for atom in clause.atoms)
        for clause in predicate.clauses
    )


def compactness_bytes(
    predicate: Layer30Predicate,
    promoted_rows: tuple[tuple[int, ...], ...],
) -> tuple[int, int]:
    """Measure canonical predicate and explicit promoted-table bytes."""
    if any(len(row) != len(predicate.variables) for row in promoted_rows):
        raise ValueError("promoted row width differs from P30 scope")
    table = {
        "layer": 30,
        "variables": list(predicate.variables),
        "states": [list(row) for row in promoted_rows],
    }
    return len(canonical_bytes(predicate.to_payload())), len(canonical_bytes(table))


@dataclass(frozen=True)
class ProjectionOrigin:
    atom_sha256: str
    failed_q0_equation: int
    qe_formula_sha256: str
    expression_path: tuple[int, ...]
    polarity: str

    def __post_init__(self) -> None:
        _validate_digest(self.atom_sha256, "origin atom digest")
        _validate_digest(self.qe_formula_sha256, "origin QE formula digest")
        if not _is_int(self.failed_q0_equation) or not 0 <= self.failed_q0_equation < 5:
            raise ValueError("failed Q0 equation must be in 0..4")
        if not self.expression_path or any(
            not _is_int(index) or index < 0 for index in self.expression_path
        ):
            raise ValueError("expression path must contain nonnegative integers")
        if self.polarity not in {"direct", "complement"}:
            raise ValueError("origin polarity must be direct or complement")

    def to_payload(self) -> dict[str, object]:
        return {
            "atom_sha256": self.atom_sha256,
            "failed_q0_equation": self.failed_q0_equation,
            "qe_formula_sha256": self.qe_formula_sha256,
            "expression_path": list(self.expression_path),
            "polarity": self.polarity,
        }


@dataclass(frozen=True)
class BadImageProjectionCertificate:
    schema: str
    status: str
    stop_reason: str | None
    base: int
    removed: str
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    t30_artifact_digests: tuple[tuple[str, str], ...]
    p30: Layer30Predicate
    projection_origins: tuple[ProjectionOrigin, ...]
    promoted_count: int
    promoted_sha256: str
    predicate_bytes: int
    state_table_bytes: int
    counterexample_count: int
    implication_status: str
    implication_equation_count: int
    composed_status: str
    composed_equation_count: int
    failure_witness: SemanticWitness | None

    def __post_init__(self) -> None:
        if self.schema != _SCHEMA:
            raise ValueError(f"unsupported bad-image certificate schema: {self.schema}")
        if self.status not in {_PASS, _STOP}:
            raise ValueError("unsupported bad-image certificate status")
        if self.base != 19:
            raise ValueError("bad-image certificate is frozen to base 19")
        if self.removed != _REMOVED:
            raise ValueError("bad-image certificate removed coordinate differs")
        _validate_digest_map(self.source_digests, _SOURCE_NAMES, "source")
        _validate_digest_map(self.t29_artifact_digests, _T29_NAMES, "T29 artifact")
        _validate_digest_map(self.t30_artifact_digests, _T30_NAMES, "T30 artifact")
        if not self.projection_origins or len(set(self.projection_origins)) != len(
            self.projection_origins
        ):
            raise ValueError("projection origins must be nonempty and unique")
        atom_digests = {
            hashlib_sha256(canonical_bytes(atom.to_payload()))
            for clause in self.p30.clauses
            for atom in clause.atoms
        }
        if {origin.atom_sha256 for origin in self.projection_origins} != atom_digests:
            raise ValueError("projection origins do not match P30 atoms")
        if self.promoted_count != 18:
            raise ValueError("certificate requires 18 promoted states")
        _validate_digest(self.promoted_sha256, "promoted-state digest")
        if not _is_int(self.predicate_bytes) or self.predicate_bytes < 1:
            raise ValueError("predicate byte count must be positive")
        if not _is_int(self.state_table_bytes) or self.state_table_bytes < 1:
            raise ValueError("state-table byte count must be positive")
        if self.predicate_bytes >= self.state_table_bytes:
            raise ValueError("certificate requires strict compression")
        if (
            not _is_int(self.counterexample_count)
            or not 0 <= self.counterexample_count <= 64
        ):
            raise ValueError("counterexample count must be in 0..64")
        statuses = {"SAT", "UNSAT", "NOT_RUN"}
        if self.implication_status not in statuses or self.composed_status not in statuses:
            raise ValueError("unsupported exact-query status")
        if self.implication_equation_count != 12:
            raise ValueError("certificate requires 12 implication equations")
        if self.composed_equation_count != 24:
            raise ValueError("certificate requires 24 composed equations")

        if self.status == _PASS:
            if (self.implication_status, self.composed_status) != ("UNSAT", "UNSAT"):
                raise ValueError("PASS statuses must both be UNSAT")
            if self.stop_reason is not None:
                raise ValueError("PASS cannot carry a stop reason")
            if self.failure_witness is not None:
                raise ValueError("PASS cannot carry a failure witness")
            return

        if not isinstance(self.stop_reason, str) or not self.stop_reason:
            raise ValueError("STOP requires a stop reason")
        has_sat = "SAT" in {self.implication_status, self.composed_status}
        if has_sat and self.failure_witness is None:
            raise ValueError("SAT requires a witness")
        if not has_sat and self.failure_witness is not None:
            raise ValueError("only SAT carries a witness")
        valid_order = (
            (self.implication_status == "SAT" and self.composed_status == "NOT_RUN")
            or (self.implication_status == "UNSAT" and self.composed_status == "SAT")
            or (self.implication_status == "UNSAT" and self.composed_status == "UNSAT")
            or (self.implication_status == "NOT_RUN" and self.composed_status == "NOT_RUN")
        )
        if not valid_order:
            raise ValueError("STOP statuses violate first-failure ordering")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "status": self.status,
            "stop_reason": self.stop_reason,
            "base": self.base,
            "removed": self.removed,
            "source_digests": dict(self.source_digests),
            "t29_artifact_digests": dict(self.t29_artifact_digests),
            "t30_artifact_digests": dict(self.t30_artifact_digests),
            "p30": self.p30.to_payload(),
            "projection_origins": [origin.to_payload() for origin in self.projection_origins],
            "promoted_count": self.promoted_count,
            "promoted_sha256": self.promoted_sha256,
            "predicate_bytes": self.predicate_bytes,
            "state_table_bytes": self.state_table_bytes,
            "counterexample_count": self.counterexample_count,
            "implication_status": self.implication_status,
            "implication_equation_count": self.implication_equation_count,
            "composed_status": self.composed_status,
            "composed_equation_count": self.composed_equation_count,
            "failure_witness": (
                None if self.failure_witness is None else self.failure_witness.to_payload()
            ),
        }


def hashlib_sha256(value: bytes) -> str:
    """Return a lowercase SHA-256 without exposing a mutable hash object."""
    import hashlib

    return hashlib.sha256(value).hexdigest()


def _require_keys(value: Mapping[str, object], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys differ")


def _parse_digest_map(
    value: object, names: set[str], context: str
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} digests must be an object")
    entries = tuple(sorted(value.items()))
    parsed = tuple((name, digest) for name, digest in entries)
    _validate_digest_map(parsed, names, context)  # type: ignore[arg-type]
    return parsed  # type: ignore[return-value]


def _parse_atom(value: object) -> ProjectionAtom:
    if not isinstance(value, Mapping):
        raise ValueError("P30 atom must be an object")
    expected = {"relation", "terms", "constant"}
    if value.get("relation") == "congruent":
        expected.add("modulus")
    _require_keys(value, expected, "P30 atom")
    terms = value["terms"]
    if not isinstance(terms, list):
        raise ValueError("P30 atom terms must be a list")
    parsed_terms = []
    for term in terms:
        if not isinstance(term, list) or len(term) != 2:
            raise ValueError("P30 term must be a two-item list")
        name, coefficient = term
        if not isinstance(name, str) or not _is_int(coefficient):
            raise ValueError("P30 term must contain a string and integer")
        parsed_terms.append((name, coefficient))
    atom = ProjectionAtom(
        relation=value["relation"],  # type: ignore[arg-type]
        terms=tuple(parsed_terms),
        constant=value["constant"],  # type: ignore[arg-type]
        modulus=value.get("modulus"),  # type: ignore[arg-type]
    )
    if atom.to_payload() != dict(value):
        raise ValueError("P30 atom is not canonically serialized")
    return atom


def _parse_predicate(value: object) -> Layer30Predicate:
    if not isinstance(value, Mapping):
        raise ValueError("P30 must be an object")
    _require_keys(value, {"layer", "variables", "clauses"}, "P30")
    variables = value["variables"]
    clauses = value["clauses"]
    if not isinstance(variables, list) or not all(
        isinstance(variable, str) for variable in variables
    ):
        raise ValueError("P30 variables must be a string list")
    if not isinstance(clauses, list):
        raise ValueError("P30 clauses must be a list")
    parsed_clauses = []
    for clause in clauses:
        if not isinstance(clause, Mapping):
            raise ValueError("P30 clause must be an object")
        _require_keys(clause, {"atoms"}, "P30 clause")
        atoms = clause["atoms"]
        if not isinstance(atoms, list):
            raise ValueError("P30 clause atoms must be a list")
        parsed_clauses.append(ProjectionClause(tuple(_parse_atom(atom) for atom in atoms)))
    predicate = Layer30Predicate(
        layer=value["layer"],  # type: ignore[arg-type]
        variables=tuple(variables),
        clauses=tuple(parsed_clauses),
    )
    if predicate.to_payload() != dict(value):
        raise ValueError("P30 is not canonically serialized")
    return predicate


def _parse_origin(value: object) -> ProjectionOrigin:
    if not isinstance(value, Mapping):
        raise ValueError("projection origin must be an object")
    _require_keys(
        value,
        {
            "atom_sha256",
            "failed_q0_equation",
            "qe_formula_sha256",
            "expression_path",
            "polarity",
        },
        "projection origin",
    )
    path = value["expression_path"]
    if not isinstance(path, list):
        raise ValueError("projection expression path must be a list")
    return ProjectionOrigin(
        atom_sha256=value["atom_sha256"],  # type: ignore[arg-type]
        failed_q0_equation=value["failed_q0_equation"],  # type: ignore[arg-type]
        qe_formula_sha256=value["qe_formula_sha256"],  # type: ignore[arg-type]
        expression_path=tuple(path),  # type: ignore[arg-type]
        polarity=value["polarity"],  # type: ignore[arg-type]
    )


def _parse_assignment(
    value: object, context: str, *, allow_empty: bool = False
) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be an object")
    assignment = tuple(sorted(value.items()))
    if not allow_empty and not assignment:
        raise ValueError(f"{context} must be nonempty")
    if any(
        not isinstance(name, str) or not name or not _is_int(item)
        for name, item in assignment
    ):
        raise ValueError(f"{context} is invalid")
    return assignment  # type: ignore[return-value]


def _parse_witness(value: object) -> SemanticWitness:
    if not isinstance(value, Mapping):
        raise ValueError("failure witness must be an object")
    _require_keys(
        value,
        {"input_state", "output_state", "local_state"},
        "failure witness",
    )
    return SemanticWitness(
        input_state=_parse_assignment(value["input_state"], "witness input"),
        output_state=_parse_assignment(value["output_state"], "witness output"),
        local_state=_parse_assignment(
            value["local_state"], "witness local", allow_empty=True
        ),
    )


def parse_bad_image_projection_certificate(
    payload: object,
) -> BadImageProjectionCertificate:
    """Parse one exact-key T31 certificate payload."""
    if not isinstance(payload, Mapping):
        raise ValueError("bad-image certificate must be an object")
    expected = {
        "schema",
        "status",
        "stop_reason",
        "base",
        "removed",
        "source_digests",
        "t29_artifact_digests",
        "t30_artifact_digests",
        "p30",
        "projection_origins",
        "promoted_count",
        "promoted_sha256",
        "predicate_bytes",
        "state_table_bytes",
        "counterexample_count",
        "implication_status",
        "implication_equation_count",
        "composed_status",
        "composed_equation_count",
        "failure_witness",
    }
    _require_keys(payload, expected, "certificate")
    origins = payload["projection_origins"]
    if not isinstance(origins, list):
        raise ValueError("projection origins must be a list")
    witness_payload = payload["failure_witness"]
    return BadImageProjectionCertificate(
        schema=payload["schema"],  # type: ignore[arg-type]
        status=payload["status"],  # type: ignore[arg-type]
        stop_reason=payload["stop_reason"],  # type: ignore[arg-type]
        base=payload["base"],  # type: ignore[arg-type]
        removed=payload["removed"],  # type: ignore[arg-type]
        source_digests=_parse_digest_map(payload["source_digests"], _SOURCE_NAMES, "source"),
        t29_artifact_digests=_parse_digest_map(
            payload["t29_artifact_digests"], _T29_NAMES, "T29 artifact"
        ),
        t30_artifact_digests=_parse_digest_map(
            payload["t30_artifact_digests"], _T30_NAMES, "T30 artifact"
        ),
        p30=_parse_predicate(payload["p30"]),
        projection_origins=tuple(_parse_origin(origin) for origin in origins),
        promoted_count=payload["promoted_count"],  # type: ignore[arg-type]
        promoted_sha256=payload["promoted_sha256"],  # type: ignore[arg-type]
        predicate_bytes=payload["predicate_bytes"],  # type: ignore[arg-type]
        state_table_bytes=payload["state_table_bytes"],  # type: ignore[arg-type]
        counterexample_count=payload["counterexample_count"],  # type: ignore[arg-type]
        implication_status=payload["implication_status"],  # type: ignore[arg-type]
        implication_equation_count=payload["implication_equation_count"],  # type: ignore[arg-type]
        composed_status=payload["composed_status"],  # type: ignore[arg-type]
        composed_equation_count=payload["composed_equation_count"],  # type: ignore[arg-type]
        failure_witness=(
            None if witness_payload is None else _parse_witness(witness_payload)
        ),
    )
