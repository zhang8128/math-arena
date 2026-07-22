from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


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
