"""Typed certificates for the base-19 exact-image refinement gate."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from lychrel_invariant_certificate import Conjunction, LayerPredicate, LinearAtom
from lychrel_reachability_separator import SemanticWitness

_SCHEMA = "t30-base19-exact-image-refinement-certificate-v1"
_PASS = "EXACT_IMAGE_REFINEMENT_PASS"
_STOP = "EXACT_IMAGE_REFINEMENT_STOP"
_REMOVED = "phase=0,n=0,column=82"
_SOURCE_DIGEST_NAMES = {
    "equations",
    "frontier",
    "provenances",
    "t27_evidence",
    "t28_evidence",
    "t28_independent",
}
_T29_DIGEST_NAMES = {
    "certificate",
    "dataset",
    "evidence",
    "independent",
    "trace",
}


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
    expected_names: set[str],
    context: str,
) -> None:
    if (
        len(entries) != len(expected_names)
        or tuple(sorted(entries)) != entries
        or set(dict(entries)) != expected_names
    ):
        raise ValueError(f"{context} digest names differ")
    for name, digest in entries:
        _validate_digest(digest, f"{context} digest {name}")


@dataclass(frozen=True)
class PredecessorImageObligation:
    predecessor_index: int
    predecessor_sha256: str
    exact_model_count: int
    output_count: int
    output_sha256: str
    q0_violation_status: str

    def __post_init__(self) -> None:
        if not _is_int(self.predecessor_index) or self.predecessor_index < 0:
            raise ValueError("predecessor index must be a nonnegative integer")
        _validate_digest(self.predecessor_sha256, "predecessor digest")
        _validate_digest(self.output_sha256, "output digest")
        if not _is_int(self.exact_model_count) or self.exact_model_count < 0:
            raise ValueError("exact model count must be a nonnegative integer")
        if (
            not _is_int(self.output_count)
            or self.output_count < 0
            or self.output_count > self.exact_model_count
        ):
            raise ValueError("output count must be between zero and the model count")
        if self.q0_violation_status not in {"SAT", "UNSAT"}:
            raise ValueError("q0 violation status must be SAT or UNSAT")
        if self.q0_violation_status == "SAT" and self.output_count == 0:
            raise ValueError("a q0 violation requires an output")

    def to_payload(self) -> dict[str, object]:
        return {
            "predecessor_index": self.predecessor_index,
            "predecessor_sha256": self.predecessor_sha256,
            "exact_model_count": self.exact_model_count,
            "output_count": self.output_count,
            "output_sha256": self.output_sha256,
            "q0_violation_status": self.q0_violation_status,
        }


def _validate_q0(q0: LayerPredicate) -> None:
    if q0.layer != 31:
        raise ValueError("q0 must be at layer 31")
    if len(q0.clauses) != 1:
        raise ValueError("q0 must contain one conjunction")
    atoms = q0.clauses[0].atoms
    if len(atoms) != 5:
        raise ValueError("q0 must contain exactly five atoms")
    if any(atom.relation != "eq" for atom in atoms):
        raise ValueError("q0 atoms must be equalities")
    if max(abs(coefficient) for atom in atoms for _, coefficient in atom.terms) > 3:
        raise ValueError("q0 coefficient magnitude exceeds three")
    if max(len(atom.terms) for atom in atoms) > 11:
        raise ValueError("q0 atom support exceeds 11")
    if sum(len(atom.terms) for atom in atoms) != 34:
        raise ValueError("q0 total coefficient support must equal 34")


@dataclass(frozen=True)
class ExactImageRefinementCertificate:
    schema: str
    status: str
    base: int
    removed: str
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    q0: LayerPredicate
    predecessor_obligations: tuple[PredecessorImageObligation, ...]
    implication_status: str
    finite_status: str
    semantic_status: str
    implication_witness: SemanticWitness | None
    semantic_witness: SemanticWitness | None

    def __post_init__(self) -> None:
        if self.schema != _SCHEMA:
            raise ValueError(f"unsupported exact-image certificate schema: {self.schema}")
        if self.status not in {_PASS, _STOP}:
            raise ValueError("unsupported exact-image certificate status")
        if self.base != 19:
            raise ValueError("exact-image certificate is frozen to base 19")
        if self.removed != _REMOVED:
            raise ValueError("exact-image certificate removed coordinate differs")
        _validate_digest_map(
            self.source_digests, _SOURCE_DIGEST_NAMES, "source"
        )
        _validate_digest_map(
            self.t29_artifact_digests, _T29_DIGEST_NAMES, "T29 artifact"
        )
        _validate_q0(self.q0)
        indices = tuple(item.predecessor_index for item in self.predecessor_obligations)
        if indices != tuple(range(len(indices))):
            raise ValueError("predecessor indices must be consecutive from zero")
        if len({item.predecessor_sha256 for item in self.predecessor_obligations}) != len(
            self.predecessor_obligations
        ):
            raise ValueError("predecessor digests must be unique")

        if self.implication_status not in {"SAT", "UNSAT", "NOT_RUN"}:
            raise ValueError("unsupported implication status")
        if self.finite_status not in {"PASS", "STOP", "NOT_RUN"}:
            raise ValueError("unsupported finite status")
        if self.semantic_status not in {"SAT", "UNSAT", "NOT_RUN"}:
            raise ValueError("unsupported semantic status")
        if self.implication_status == "SAT" and self.implication_witness is None:
            raise ValueError("implication SAT requires a witness")
        if self.implication_status != "SAT" and self.implication_witness is not None:
            raise ValueError("only implication SAT carries a witness")
        if self.semantic_status == "SAT" and self.semantic_witness is None:
            raise ValueError("semantic SAT requires a witness")
        if self.semantic_status != "SAT" and self.semantic_witness is not None:
            raise ValueError("only semantic SAT carries a witness")

        obligation_count = len(self.predecessor_obligations)
        statuses = tuple(
            item.q0_violation_status for item in self.predecessor_obligations
        )
        pass_state = (
            self.status == _PASS
            and self.implication_status == "UNSAT"
            and self.finite_status == "PASS"
            and self.semantic_status == "UNSAT"
            and obligation_count == 18
            and set(statuses) <= {"UNSAT"}
        )
        implication_stop = (
            self.status == _STOP
            and self.implication_status == "SAT"
            and self.finite_status == "NOT_RUN"
            and self.semantic_status == "NOT_RUN"
            and 1 <= obligation_count <= 18
            and statuses[-1:] == ("SAT",)
            and set(statuses[:-1]) <= {"UNSAT"}
        )
        finite_stop = (
            self.status == _STOP
            and self.implication_status == "UNSAT"
            and self.finite_status == "STOP"
            and self.semantic_status == "NOT_RUN"
            and obligation_count == 18
            and set(statuses) <= {"UNSAT"}
        )
        semantic_stop = (
            self.status == _STOP
            and self.implication_status == "UNSAT"
            and self.finite_status == "PASS"
            and self.semantic_status == "SAT"
            and obligation_count == 18
            and set(statuses) <= {"UNSAT"}
        )
        if not any((pass_state, implication_stop, finite_stop, semantic_stop)):
            if self.status == _PASS and obligation_count != 18:
                raise ValueError("PASS requires 18 predecessor obligations")
            raise ValueError("certificate statuses violate the first-failure state machine")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "status": self.status,
            "base": self.base,
            "removed": self.removed,
            "source_digests": dict(self.source_digests),
            "t29_artifact_digests": dict(self.t29_artifact_digests),
            "q0": self.q0.to_payload(),
            "predecessor_obligations": [
                obligation.to_payload() for obligation in self.predecessor_obligations
            ],
            "implication_status": self.implication_status,
            "finite_status": self.finite_status,
            "semantic_status": self.semantic_status,
            "implication_witness": (
                None
                if self.implication_witness is None
                else self.implication_witness.to_payload()
            ),
            "semantic_witness": (
                None if self.semantic_witness is None else self.semantic_witness.to_payload()
            ),
        }


def _require_keys(value: Mapping[str, object], expected: set[str], context: str) -> None:
    if set(value) != expected:
        raise ValueError(f"{context} keys differ")


def _parse_digest_map(
    value: object, expected_names: set[str], context: str
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} digests must be an object")
    entries = tuple(sorted(value.items()))
    if any(not isinstance(name, str) or not isinstance(digest, str) for name, digest in entries):
        raise ValueError(f"{context} digest entries must be strings")
    parsed = tuple((name, digest) for name, digest in entries)  # type: ignore[misc]
    _validate_digest_map(parsed, expected_names, context)
    return parsed


def _parse_atom(payload: object) -> LinearAtom:
    if not isinstance(payload, Mapping):
        raise ValueError("q0 atom must be an object")
    expected = {"relation", "terms", "constant"}
    if payload.get("relation") == "congruent":
        expected.add("modulus")
    _require_keys(payload, expected, "q0 atom")
    terms = payload["terms"]
    if not isinstance(terms, list):
        raise ValueError("q0 atom terms must be a list")
    parsed_terms = []
    for term in terms:
        if not isinstance(term, list) or len(term) != 2:
            raise ValueError("q0 term must be a two-item list")
        name, coefficient = term
        if not isinstance(name, str) or not _is_int(coefficient):
            raise ValueError("q0 term must contain a string and integer")
        parsed_terms.append((name, coefficient))
    return LinearAtom(
        relation=payload["relation"],  # type: ignore[arg-type]
        terms=tuple(parsed_terms),
        constant=payload["constant"],  # type: ignore[arg-type]
        modulus=payload.get("modulus"),  # type: ignore[arg-type]
    )


def _parse_q0(payload: object) -> LayerPredicate:
    if not isinstance(payload, Mapping):
        raise ValueError("q0 must be an object")
    _require_keys(payload, {"layer", "variables", "clauses"}, "q0")
    variables = payload["variables"]
    clauses = payload["clauses"]
    if not isinstance(variables, list) or not all(
        isinstance(variable, str) for variable in variables
    ):
        raise ValueError("q0 variables must be a string list")
    if not isinstance(clauses, list):
        raise ValueError("q0 clauses must be a list")
    parsed_clauses = []
    for clause in clauses:
        if not isinstance(clause, Mapping):
            raise ValueError("q0 clause must be an object")
        _require_keys(clause, {"atoms"}, "q0 clause")
        atoms = clause["atoms"]
        if not isinstance(atoms, list):
            raise ValueError("q0 atoms must be a list")
        parsed_clauses.append(Conjunction(tuple(_parse_atom(atom) for atom in atoms)))
    return LayerPredicate(
        layer=payload["layer"],  # type: ignore[arg-type]
        variables=tuple(variables),
        clauses=tuple(parsed_clauses),
    )


def _parse_assignment(
    payload: object, context: str, *, allow_empty: bool = False
) -> tuple[tuple[str, int], ...]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{context} must be an object")
    assignment = tuple(sorted(payload.items()))
    if not allow_empty and not assignment:
        raise ValueError(f"{context} must be nonempty")
    if len({name for name, _ in assignment}) != len(assignment) or any(
        not isinstance(name, str) or not name or not _is_int(value)
        for name, value in assignment
    ):
        raise ValueError(f"{context} is invalid")
    return assignment  # type: ignore[return-value]


def _parse_witness(payload: object) -> SemanticWitness:
    if not isinstance(payload, Mapping):
        raise ValueError("semantic witness must be an object")
    _require_keys(
        payload,
        {"input_state", "output_state", "local_state"},
        "semantic witness",
    )
    return SemanticWitness(
        input_state=_parse_assignment(payload["input_state"], "witness input"),
        output_state=_parse_assignment(payload["output_state"], "witness output"),
        local_state=_parse_assignment(
            payload["local_state"], "witness local", allow_empty=True
        ),
    )


def _parse_obligation(payload: object) -> PredecessorImageObligation:
    if not isinstance(payload, Mapping):
        raise ValueError("predecessor obligation must be an object")
    _require_keys(
        payload,
        {
            "predecessor_index",
            "predecessor_sha256",
            "exact_model_count",
            "output_count",
            "output_sha256",
            "q0_violation_status",
        },
        "predecessor obligation",
    )
    return PredecessorImageObligation(
        predecessor_index=payload["predecessor_index"],  # type: ignore[arg-type]
        predecessor_sha256=payload["predecessor_sha256"],  # type: ignore[arg-type]
        exact_model_count=payload["exact_model_count"],  # type: ignore[arg-type]
        output_count=payload["output_count"],  # type: ignore[arg-type]
        output_sha256=payload["output_sha256"],  # type: ignore[arg-type]
        q0_violation_status=payload["q0_violation_status"],  # type: ignore[arg-type]
    )


def parse_exact_image_refinement_certificate(
    payload: object,
) -> ExactImageRefinementCertificate:
    """Parse T30 evidence while rejecting extra or malformed syntax."""
    if not isinstance(payload, Mapping):
        raise ValueError("exact-image certificate must be an object")
    _require_keys(
        payload,
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
        "certificate",
    )
    obligations = payload["predecessor_obligations"]
    if not isinstance(obligations, list):
        raise ValueError("predecessor obligations must be a list")
    implication_witness = payload["implication_witness"]
    semantic_witness = payload["semantic_witness"]
    return ExactImageRefinementCertificate(
        schema=payload["schema"],  # type: ignore[arg-type]
        status=payload["status"],  # type: ignore[arg-type]
        base=payload["base"],  # type: ignore[arg-type]
        removed=payload["removed"],  # type: ignore[arg-type]
        source_digests=_parse_digest_map(
            payload["source_digests"], _SOURCE_DIGEST_NAMES, "source"
        ),
        t29_artifact_digests=_parse_digest_map(
            payload["t29_artifact_digests"], _T29_DIGEST_NAMES, "T29 artifact"
        ),
        q0=_parse_q0(payload["q0"]),
        predecessor_obligations=tuple(
            _parse_obligation(obligation) for obligation in obligations
        ),
        implication_status=payload["implication_status"],  # type: ignore[arg-type]
        finite_status=payload["finite_status"],  # type: ignore[arg-type]
        semantic_status=payload["semantic_status"],  # type: ignore[arg-type]
        implication_witness=(
            None if implication_witness is None else _parse_witness(implication_witness)
        ),
        semantic_witness=(
            None if semantic_witness is None else _parse_witness(semantic_witness)
        ),
    )
