from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mathloop.domain import (
    CandidateClaim,
    ClaimStatus,
    ClaimType,
    EvidenceLevel,
    Verification,
    advance_claim,
)


def test_claim_is_immutable() -> None:
    claim = CandidateClaim(
        id=uuid4(),
        problem_id=uuid4(),
        experiment_id=uuid4(),
        claim_type=ClaimType.DISPROOF,
        statement="n=40 is a counterexample",
        witness={"n": 40},
        status=ClaimStatus.CANDIDATE,
        evidence_level=EvidenceLevel.LEAD,
        created_at=datetime.now(UTC),
    )
    with pytest.raises(ValidationError):
        claim.status = ClaimStatus.MACHINE_VERIFIED


def test_only_accepted_independent_verification_promotes_claim() -> None:
    claim = CandidateClaim.model_validate(
        {
            "id": uuid4(),
            "problem_id": uuid4(),
            "experiment_id": uuid4(),
            "claim_type": "disproof",
            "statement": "counterexample",
            "witness": {"n": 40},
            "status": "candidate",
            "evidence_level": "lead",
            "created_at": datetime.now(UTC),
        }
    )
    rejected = Verification(
        verifier="integer-predicate",
        verifier_version="1",
        accepted=False,
        independent=True,
        details={"reason": "predicate held"},
    )
    assert advance_claim(claim, rejected).status is ClaimStatus.REJECTED

    accepted = rejected.model_copy(update={"accepted": True, "details": {"value": False}})
    assert advance_claim(claim, accepted).status is ClaimStatus.MACHINE_VERIFIED
