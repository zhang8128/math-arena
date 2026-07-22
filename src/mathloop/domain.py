from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, NoReturn, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FrozenDict(dict[str, Any]):
    """A dict that keeps the familiar mapping API without allowing mutation."""

    @staticmethod
    def _immutable(*args: object, **kwargs: object) -> NoReturn:
        raise TypeError("frozen mappings cannot be modified")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return FrozenDict({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_json(item) for item in value)
    return value


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    def model_post_init(self, __context: Any) -> None:
        for field_name in type(self).model_fields:
            object.__setattr__(self, field_name, _freeze_json(getattr(self, field_name)))

    def model_copy(
        self, *, update: Mapping[str, Any] | None = None, deep: bool = False
    ) -> Self:
        copied = super().model_copy(update=update, deep=deep)
        for field_name in type(copied).model_fields:
            object.__setattr__(copied, field_name, _freeze_json(getattr(copied, field_name)))
        return copied


class ProblemStatus(StrEnum):
    DISCOVERED = "discovered"
    NORMALIZED = "normalized"
    ELIGIBLE = "eligible"
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    REVISIT_LATER = "revisit_later"


class ExperimentStatus(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"


class ClaimType(StrEnum):
    PROOF = "proof"
    DISPROOF = "disproof"
    CORRECTION = "correction"
    PARTIAL = "partial"


class ClaimStatus(StrEnum):
    CANDIDATE = "candidate"
    MACHINE_VERIFIED = "machine_verified"
    REJECTED = "rejected"
    NOVELTY_CHECKED = "novelty_checked"
    HUMAN_REVIEWED = "human_reviewed"


class EvidenceLevel(StrEnum):
    LEAD = "lead"
    COMPUTATIONALLY_SUPPORTED = "computationally_supported"
    REPRODUCIBLE_WITNESS = "reproducible_witness"
    FORMALLY_VERIFIED = "formally_verified"


class Problem(FrozenModel):
    id: UUID
    source_id: str
    source_uri: str
    source_hash: str
    statement: str
    normalized_statement: str
    domain: str
    features: dict[str, Any]
    checker: dict[str, Any]
    status: ProblemStatus
    cohort: str = Field(pattern="^(development|holdout)$")
    version: int = Field(ge=1)
    created_at: datetime


class ProblemCandidate(FrozenModel):
    source_id: str
    source_uri: str
    source_hash: str
    statement: str
    normalized_statement: str
    domain: str
    features: dict[str, Any]
    checker: dict[str, Any]
    expected: str | None = None


class MethodVersion(FrozenModel):
    id: UUID
    family: str
    version: int = Field(ge=1)
    spec: dict[str, Any]
    parent_id: UUID | None = None
    status: str = Field(pattern="^(candidate|active|retired|archived)$")
    created_at: datetime


class Experiment(FrozenModel):
    id: UUID
    problem_id: UUID
    method_id: UUID
    lane: str
    config: dict[str, Any]
    seed: int
    status: ExperimentStatus
    created_at: datetime


class CandidateClaim(FrozenModel):
    id: UUID
    problem_id: UUID
    experiment_id: UUID
    claim_type: ClaimType
    statement: str
    witness: dict[str, Any] | None
    status: ClaimStatus
    evidence_level: EvidenceLevel
    created_at: datetime


class Verification(FrozenModel):
    verifier: str
    verifier_version: str
    accepted: bool
    independent: bool
    details: dict[str, Any]


def advance_claim(claim: CandidateClaim, verification: Verification) -> CandidateClaim:
    if not verification.independent:
        raise ValueError("claim promotion requires an independent verifier")
    if verification.accepted:
        return claim.model_copy(
            update={
                "status": ClaimStatus.MACHINE_VERIFIED,
                "evidence_level": EvidenceLevel.REPRODUCIBLE_WITNESS,
            }
        )
    return claim.model_copy(update={"status": ClaimStatus.REJECTED})
