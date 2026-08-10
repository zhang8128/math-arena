"""Typed certificates for the base-19 semantic-leak mechanism cover."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from lychrel_invariant_certificate import canonical_bytes
from lychrel_reachability_separator import SemanticWitness

_SCHEMA = "t32-base19-semantic-leak-types-certificate-v1"
_PASS = "SEMANTIC_LEAK_TYPES_PASS"
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
_T31_NAMES = {"library", "runner", "test"}
_T31_COMMITS = ("69022cb", "adc6986", "619b737", "6835036")

RELATIONS = {
    "digit_order": ("eq", "lt", "gt"),
    "digit_sum": ("lt19", "eq18", "ge19"),
    "input_carry_pair": ("eq", "ne"),
    "output_carry_pair": ("eq", "ne"),
    "left_carry_flow": ("eq", "ne"),
    "right_carry_flow": ("eq", "ne"),
}

STRUCTURAL_KEYS = tuple(
    name
    for phase in range(6)
    for name in (
        f"a{phase}",
        f"b{phase}",
        f"Lin{phase}",
        f"Rin{phase}",
        f"Lout{phase}",
        f"Rout{phase}",
    )
)


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
    entries: tuple[tuple[str, str], ...], names: set[str], context: str
) -> None:
    if tuple(sorted(entries)) != entries or len(entries) != len(names):
        raise ValueError(f"{context} digest names differ")
    if set(dict(entries)) != names:
        raise ValueError(f"{context} digest names differ")
    for name, digest in entries:
        _validate_digest(digest, f"{context} digest {name}")


def _require_keys(value: Mapping[str, object], expected: set[str], context: str) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{context} keys differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


@dataclass(frozen=True)
class StructuralLiteral:
    phase: int
    kind: str
    relation: str

    def __post_init__(self) -> None:
        if not _is_int(self.phase) or not 0 <= self.phase < 6:
            raise ValueError("literal phase must be in 0..5")
        if self.kind not in RELATIONS:
            raise ValueError(f"unsupported structural literal kind: {self.kind}")
        if self.relation not in RELATIONS[self.kind]:
            raise ValueError(
                f"unsupported relation for {self.kind}: {self.relation}"
            )

    def to_payload(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "kind": self.kind,
            "relation": self.relation,
        }


def generate_literal_pool() -> tuple[StructuralLiteral, ...]:
    """Return the complete frozen T32 structural literal pool."""
    return tuple(
        sorted(
            (
                StructuralLiteral(phase, kind, relation)
                for phase in range(6)
                for kind, relations in RELATIONS.items()
                for relation in relations
            ),
            key=canonical_bytes,
        )
    )


def _literal_variables(literal: StructuralLiteral) -> frozenset[str]:
    phase = literal.phase
    if literal.kind in {"digit_order", "digit_sum"}:
        return frozenset({f"a{phase}", f"b{phase}"})
    if literal.kind == "input_carry_pair":
        return frozenset({f"Lin{phase}", f"Rin{phase}"})
    if literal.kind == "output_carry_pair":
        return frozenset({f"Lout{phase}", f"Rout{phase}"})
    if literal.kind == "left_carry_flow":
        return frozenset({f"Lin{phase}", f"Lout{phase}"})
    return frozenset({f"Rin{phase}", f"Rout{phase}"})


@dataclass(frozen=True)
class LeakType:
    literals: tuple[StructuralLiteral, ...]

    def __post_init__(self) -> None:
        if not self.literals:
            raise ValueError("a leak type must contain at least one literal")
        if len(self.literals) > 6:
            raise ValueError("a leak type may contain at most six literals")
        if len(set(self.literals)) != len(self.literals):
            raise ValueError("a leak type may not repeat a literal")
        object.__setattr__(
            self, "literals", tuple(sorted(self.literals, key=canonical_bytes))
        )

    def to_payload(self) -> dict[str, object]:
        return {"literals": [literal.to_payload() for literal in self.literals]}


def type_objective(leak_type: LeakType) -> tuple[object, ...]:
    variables = frozenset().union(
        *(_literal_variables(literal) for literal in leak_type.literals)
    )
    return (
        len(leak_type.literals),
        len({literal.phase for literal in leak_type.literals}),
        len(variables),
        canonical_bytes(leak_type),
    )


@dataclass(frozen=True)
class LeakTypeFamily:
    types: tuple[LeakType, ...]

    def __post_init__(self) -> None:
        if not self.types:
            raise ValueError("a leak family must contain at least one type")
        if len(self.types) > 8:
            raise ValueError("a leak family may contain at most eight types")
        if len(set(self.types)) != len(self.types):
            raise ValueError("a leak family may not repeat a type")
        object.__setattr__(self, "types", tuple(sorted(self.types, key=type_objective)))

    def to_payload(self) -> dict[str, object]:
        return {"types": [leak_type.to_payload() for leak_type in self.types]}


def _validate_assignment(assignment: Mapping[str, int]) -> None:
    actual = set(assignment)
    expected = set(STRUCTURAL_KEYS)
    if actual != expected:
        raise ValueError(
            "structural assignment keys differ: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    for name, value in assignment.items():
        if not _is_int(value):
            raise ValueError(f"structural assignment value is not an integer: {name}")
        if name.startswith(("Lin", "Rin", "Lout", "Rout")):
            if value not in {0, 1}:
                raise ValueError(f"structural carry is outside 0..1: {name}")
        elif not 0 <= value <= 18:
            raise ValueError(f"structural digit is outside 0..18: {name}")


def evaluate_literal(
    literal: StructuralLiteral, assignment: Mapping[str, int]
) -> bool:
    """Evaluate one structural literal on one exact transfer assignment."""
    _validate_assignment(assignment)
    phase = literal.phase
    if literal.kind == "digit_order":
        left, right = assignment[f"a{phase}"], assignment[f"b{phase}"]
        return {
            "eq": left == right,
            "lt": left < right,
            "gt": left > right,
        }[literal.relation]
    if literal.kind == "digit_sum":
        total = assignment[f"a{phase}"] + assignment[f"b{phase}"]
        return {
            "lt19": total < 19,
            "eq18": total == 18,
            "ge19": total >= 19,
        }[literal.relation]
    names = {
        "input_carry_pair": (f"Lin{phase}", f"Rin{phase}"),
        "output_carry_pair": (f"Lout{phase}", f"Rout{phase}"),
        "left_carry_flow": (f"Lin{phase}", f"Lout{phase}"),
        "right_carry_flow": (f"Rin{phase}", f"Rout{phase}"),
    }[literal.kind]
    equal = assignment[names[0]] == assignment[names[1]]
    return equal if literal.relation == "eq" else not equal


def evaluate_leak_type(leak_type: LeakType, assignment: Mapping[str, int]) -> bool:
    _validate_assignment(assignment)
    return all(evaluate_literal(literal, assignment) for literal in leak_type.literals)


def evaluate_leak_family(
    family: LeakTypeFamily, assignment: Mapping[str, int]
) -> int | None:
    """Return the canonical first matching type index, or None."""
    _validate_assignment(assignment)
    for index, leak_type in enumerate(family.types):
        if evaluate_leak_type(leak_type, assignment):
            return index
    return None


def _validate_mask(mask: tuple[bool, ...], context: str) -> None:
    if len(mask) != 5 or any(not isinstance(value, bool) for value in mask):
        raise ValueError(f"{context} must contain five Booleans")
    if not any(mask):
        raise ValueError(f"{context} must record at least one failure")


@dataclass(frozen=True)
class TypeDiversityRecord:
    type_index: int
    witnesses: tuple[SemanticWitness, SemanticWitness]
    failure_masks: tuple[tuple[bool, bool, bool, bool, bool], ...]

    def __post_init__(self) -> None:
        if not _is_int(self.type_index) or self.type_index < 0:
            raise ValueError("diversity type index must be nonnegative")
        if len(self.witnesses) != 2:
            raise ValueError("diversity requires exactly two witnesses")
        if self.witnesses[0].input_state == self.witnesses[1].input_state:
            raise ValueError("diversity witnesses must have distinct inputs")
        if len(self.failure_masks) != 2:
            raise ValueError("diversity requires exactly two failure masks")
        for index, mask in enumerate(self.failure_masks):
            _validate_mask(mask, f"diversity failure mask {index}")
        if self.failure_masks[0] == self.failure_masks[1]:
            raise ValueError("diversity witnesses must have distinct failure masks")

    def to_payload(self) -> dict[str, object]:
        return {
            "type_index": self.type_index,
            "witnesses": [witness.to_payload() for witness in self.witnesses],
            "failure_masks": [list(mask) for mask in self.failure_masks],
        }


@dataclass(frozen=True)
class SemanticLeakTypesCertificate:
    schema: str
    status: str
    base: int
    removed: str
    source_digests: tuple[tuple[str, str], ...]
    t29_artifact_digests: tuple[tuple[str, str], ...]
    t30_artifact_digests: tuple[tuple[str, str], ...]
    t31_source_digests: tuple[tuple[str, str], ...]
    t31_commits: tuple[str, ...]
    design_sha256: str
    family: LeakTypeFamily
    milestone_witnesses: tuple[SemanticWitness, SemanticWitness]
    type_soundness: tuple[str, ...]
    exhaustiveness_status: str
    diversity: tuple[TypeDiversityRecord, ...]
    discovery_witness_count: int
    tested_candidate_count: int
    enumerated_input_count: int
    bad_input_count: int
    family_bytes: int
    bad_input_table_bytes: int

    def __post_init__(self) -> None:
        if self.schema != _SCHEMA:
            raise ValueError("semantic-leak certificate schema differs")
        if self.status != _PASS:
            raise ValueError("semantic-leak certificate status differs")
        if self.base != 19 or isinstance(self.base, bool):
            raise ValueError("semantic-leak certificate base differs")
        if self.removed != _REMOVED:
            raise ValueError("semantic-leak certificate removed coordinate differs")
        _validate_digest_map(self.source_digests, _SOURCE_NAMES, "source")
        _validate_digest_map(self.t29_artifact_digests, _T29_NAMES, "T29 artifact")
        _validate_digest_map(self.t30_artifact_digests, _T30_NAMES, "T30 artifact")
        _validate_digest_map(self.t31_source_digests, _T31_NAMES, "T31 source")
        if self.t31_commits != _T31_COMMITS:
            raise ValueError("T31 commit boundary differs")
        _validate_digest(self.design_sha256, "design digest")
        if len(self.milestone_witnesses) != 2:
            raise ValueError("milestone requires exactly two witnesses")
        if self.type_soundness != ("UNSAT",) * len(self.family.types):
            raise ValueError("type soundness statuses differ")
        if self.exhaustiveness_status != "UNSAT":
            raise ValueError("family exhaustiveness status differs")
        if len(self.diversity) != len(self.family.types):
            raise ValueError("family diversity count differs")
        if tuple(item.type_index for item in self.diversity) != tuple(
            range(len(self.family.types))
        ):
            raise ValueError("family diversity indices differ")
        if self.diversity[0].witnesses != self.milestone_witnesses:
            raise ValueError("milestone witnesses differ from type zero diversity")
        if (
            not _is_int(self.discovery_witness_count)
            or not 1 <= self.discovery_witness_count <= 256
        ):
            raise ValueError("discovery witness count must be in 1..256")
        if (
            not _is_int(self.tested_candidate_count)
            or not 1 <= self.tested_candidate_count <= 10_000
        ):
            raise ValueError("tested candidate count must be in 1..10000")
        if self.enumerated_input_count != 77_824 or isinstance(
            self.enumerated_input_count, bool
        ):
            raise ValueError("certificate must enumerate exactly 77,824 inputs")
        if (
            not _is_int(self.bad_input_count)
            or not 1 <= self.bad_input_count <= self.enumerated_input_count
        ):
            raise ValueError("bad-input count is invalid")
        if not _is_int(self.family_bytes) or self.family_bytes < 1:
            raise ValueError("family byte count is invalid")
        if not _is_int(self.bad_input_table_bytes) or self.bad_input_table_bytes < 1:
            raise ValueError("bad-input table byte count is invalid")
        if self.family_bytes >= self.bad_input_table_bytes:
            raise ValueError("family must be smaller than the bad-input table")

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "status": self.status,
            "base": self.base,
            "removed": self.removed,
            "source_digests": dict(self.source_digests),
            "t29_artifact_digests": dict(self.t29_artifact_digests),
            "t30_artifact_digests": dict(self.t30_artifact_digests),
            "t31_source_digests": dict(self.t31_source_digests),
            "t31_commits": list(self.t31_commits),
            "design_sha256": self.design_sha256,
            "family": self.family.to_payload(),
            "milestone_witnesses": [
                witness.to_payload() for witness in self.milestone_witnesses
            ],
            "type_soundness": list(self.type_soundness),
            "exhaustiveness_status": self.exhaustiveness_status,
            "diversity": [item.to_payload() for item in self.diversity],
            "discovery_witness_count": self.discovery_witness_count,
            "tested_candidate_count": self.tested_candidate_count,
            "enumerated_input_count": self.enumerated_input_count,
            "bad_input_count": self.bad_input_count,
            "family_bytes": self.family_bytes,
            "bad_input_table_bytes": self.bad_input_table_bytes,
        }


def _parse_digest_map(
    value: object, names: set[str], context: str
) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} digests must be an object")
    entries = tuple(sorted(value.items()))
    if any(not isinstance(name, str) or not isinstance(digest, str) for name, digest in entries):
        raise ValueError(f"{context} digests are invalid")
    result = entries  # type: ignore[assignment]
    _validate_digest_map(result, names, context)
    return result


def _parse_literal(value: object) -> StructuralLiteral:
    if not isinstance(value, Mapping):
        raise ValueError("structural literal must be an object")
    _require_keys(value, {"phase", "kind", "relation"}, "structural literal")
    return StructuralLiteral(
        value["phase"], value["kind"], value["relation"]  # type: ignore[arg-type]
    )


def _parse_type(value: object) -> LeakType:
    if not isinstance(value, Mapping):
        raise ValueError("leak type must be an object")
    _require_keys(value, {"literals"}, "leak type")
    literals = value["literals"]
    if not isinstance(literals, list):
        raise ValueError("leak type literals must be a list")
    return LeakType(tuple(_parse_literal(item) for item in literals))


def _parse_family(value: object) -> LeakTypeFamily:
    if not isinstance(value, Mapping):
        raise ValueError("leak family must be an object")
    _require_keys(value, {"types"}, "leak family")
    types = value["types"]
    if not isinstance(types, list):
        raise ValueError("leak family types must be a list")
    return LeakTypeFamily(tuple(_parse_type(item) for item in types))


def _parse_assignment(
    value: object, context: str, *, allow_empty: bool = False
) -> tuple[tuple[str, int], ...]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be an object")
    result = tuple(sorted(value.items()))
    if not allow_empty and not result:
        raise ValueError(f"{context} must be nonempty")
    if any(
        not isinstance(name, str) or not name or not _is_int(item)
        for name, item in result
    ):
        raise ValueError(f"{context} is invalid")
    return result  # type: ignore[return-value]


def _parse_witness(value: object) -> SemanticWitness:
    if not isinstance(value, Mapping):
        raise ValueError("semantic witness must be an object")
    _require_keys(
        value, {"input_state", "output_state", "local_state"}, "semantic witness"
    )
    return SemanticWitness(
        _parse_assignment(value["input_state"], "witness input"),
        _parse_assignment(value["output_state"], "witness output"),
        _parse_assignment(value["local_state"], "witness local", allow_empty=True),
    )


def _parse_mask(value: object, context: str) -> tuple[bool, bool, bool, bool, bool]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    result = tuple(value)
    _validate_mask(result, context)  # type: ignore[arg-type]
    return result  # type: ignore[return-value]


def _parse_diversity(value: object) -> TypeDiversityRecord:
    if not isinstance(value, Mapping):
        raise ValueError("diversity record must be an object")
    _require_keys(
        value, {"type_index", "witnesses", "failure_masks"}, "diversity record"
    )
    witnesses = value["witnesses"]
    masks = value["failure_masks"]
    if not isinstance(witnesses, list) or not isinstance(masks, list):
        raise ValueError("diversity witnesses and masks must be lists")
    return TypeDiversityRecord(
        value["type_index"],  # type: ignore[arg-type]
        tuple(_parse_witness(item) for item in witnesses),  # type: ignore[arg-type]
        tuple(_parse_mask(item, "diversity failure mask") for item in masks),
    )


def parse_semantic_leak_types_certificate(
    payload: object,
) -> SemanticLeakTypesCertificate:
    """Parse one exact-key T32 PASS certificate."""
    if not isinstance(payload, Mapping):
        raise ValueError("semantic-leak certificate must be an object")
    expected = {
        "schema",
        "status",
        "base",
        "removed",
        "source_digests",
        "t29_artifact_digests",
        "t30_artifact_digests",
        "t31_source_digests",
        "t31_commits",
        "design_sha256",
        "family",
        "milestone_witnesses",
        "type_soundness",
        "exhaustiveness_status",
        "diversity",
        "discovery_witness_count",
        "tested_candidate_count",
        "enumerated_input_count",
        "bad_input_count",
        "family_bytes",
        "bad_input_table_bytes",
    }
    _require_keys(payload, expected, "certificate")
    commits = payload["t31_commits"]
    milestone = payload["milestone_witnesses"]
    soundness = payload["type_soundness"]
    diversity = payload["diversity"]
    if not isinstance(commits, list):
        raise ValueError("T31 commits must be a list")
    if not isinstance(milestone, list):
        raise ValueError("milestone witnesses must be a list")
    if not isinstance(soundness, list):
        raise ValueError("type soundness must be a list")
    if not isinstance(diversity, list):
        raise ValueError("diversity must be a list")
    return SemanticLeakTypesCertificate(
        schema=payload["schema"],  # type: ignore[arg-type]
        status=payload["status"],  # type: ignore[arg-type]
        base=payload["base"],  # type: ignore[arg-type]
        removed=payload["removed"],  # type: ignore[arg-type]
        source_digests=_parse_digest_map(payload["source_digests"], _SOURCE_NAMES, "source"),
        t29_artifact_digests=_parse_digest_map(
            payload["t29_artifact_digests"], _T29_NAMES, "T29 artifact"
        ),
        t30_artifact_digests=_parse_digest_map(
            payload["t30_artifact_digests"], _T30_NAMES, "T30 artifact"
        ),
        t31_source_digests=_parse_digest_map(
            payload["t31_source_digests"], _T31_NAMES, "T31 source"
        ),
        t31_commits=tuple(commits),  # type: ignore[arg-type]
        design_sha256=payload["design_sha256"],  # type: ignore[arg-type]
        family=_parse_family(payload["family"]),
        milestone_witnesses=tuple(_parse_witness(item) for item in milestone),  # type: ignore[arg-type]
        type_soundness=tuple(soundness),  # type: ignore[arg-type]
        exhaustiveness_status=payload["exhaustiveness_status"],  # type: ignore[arg-type]
        diversity=tuple(_parse_diversity(item) for item in diversity),
        discovery_witness_count=payload["discovery_witness_count"],  # type: ignore[arg-type]
        tested_candidate_count=payload["tested_candidate_count"],  # type: ignore[arg-type]
        enumerated_input_count=payload["enumerated_input_count"],  # type: ignore[arg-type]
        bad_input_count=payload["bad_input_count"],  # type: ignore[arg-type]
        family_bytes=payload["family_bytes"],  # type: ignore[arg-type]
        bad_input_table_bytes=payload["bad_input_table_bytes"],  # type: ignore[arg-type]
    )
