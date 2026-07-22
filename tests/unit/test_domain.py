from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from mathloop.domain import (
    CandidateClaim,
    ClaimStatus,
    ClaimType,
    EvidenceLevel,
    MethodVersion,
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


def test_nested_method_spec_is_immutable_and_json_serializable() -> None:
    method = MethodVersion(
        id=uuid4(),
        family="search",
        version=1,
        spec={"limits": {"depth": 4}, "strategies": ["bounded"]},
        status="active",
        created_at=datetime.now(UTC),
    )

    with pytest.raises(TypeError):
        method.spec["limits"]["depth"] = 5
    with pytest.raises(AttributeError):
        method.spec["strategies"].append("exhaustive")

    assert method.model_dump(mode="json")["spec"] == {
        "limits": {"depth": 4},
        "strategies": ["bounded"],
    }


def test_nested_claim_witness_is_immutable() -> None:
    claim = CandidateClaim(
        id=uuid4(),
        problem_id=uuid4(),
        experiment_id=uuid4(),
        claim_type=ClaimType.DISPROOF,
        statement="n=40 is a counterexample",
        witness={"counterexample": {"n": 40}},
        status=ClaimStatus.CANDIDATE,
        evidence_level=EvidenceLevel.LEAD,
        created_at=datetime.now(UTC),
    )

    assert claim.witness is not None
    with pytest.raises(TypeError):
        claim.witness["counterexample"]["n"] = 41


def test_non_independent_verification_does_not_promote_claim() -> None:
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
    verification = Verification(
        verifier="integer-predicate",
        verifier_version="1",
        accepted=True,
        independent=False,
        details={"value": False},
    )

    with pytest.raises(ValueError, match="independent verifier"):
        advance_claim(claim, verification)

    assert claim.status is ClaimStatus.CANDIDATE
