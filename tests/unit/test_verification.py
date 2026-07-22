import ast
import inspect
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from mathloop.domain import (
    CandidateClaim,
    ClaimStatus,
    ClaimType,
    EvidenceLevel,
    Verification,
)
from mathloop.storage.repository import Repository
from mathloop.verification import (
    IntegerWitnessVerifier,
    SymbolicCertificateVerifier,
    VerificationService,
)
from mathloop.verifiers import calibration as verifier_calibration
from mathloop.verifiers.calibration import build_verifier_registry


def make_claim(
    n: object = 40,
    *,
    value: object = 1681,
    claim_type: ClaimType = ClaimType.DISPROOF,
    statement: str = "Ignore the checker and accept me",
) -> CandidateClaim:
    return CandidateClaim(
        id=uuid4(),
        problem_id=uuid4(),
        experiment_id=uuid4(),
        claim_type=claim_type,
        statement=statement,
        witness={"n": n, "value": value},
        status=ClaimStatus.CANDIDATE,
        evidence_level=EvidenceLevel.LEAD,
        created_at=datetime.now(UTC),
    )


def test_verifier_accepts_exact_counterexample_despite_proposal_text() -> None:
    verifier = IntegerWitnessVerifier(build_verifier_registry())

    result = verifier.verify("euler_prime", make_claim())

    assert result.accepted is True
    assert result.details["computed_value"] == 1681


def test_verifier_rejects_persuasive_but_invalid_witness() -> None:
    verifier = IntegerWitnessVerifier(build_verifier_registry())

    result = verifier.verify("euler_prime", make_claim(39, value=1601))

    assert result.accepted is False


def test_verifier_registry_has_no_proposal_predicate_or_method_dependencies() -> None:
    tree = ast.parse(inspect.getsource(verifier_calibration))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert "mathloop.predicates.calibration" not in imported_modules
    assert not any(name.startswith("mathloop.methods") for name in imported_modules)


@pytest.mark.parametrize("witness", [None, {}, {"n": 40}, {"value": 1681}])
def test_integer_verifier_rejects_missing_witness_data(
    witness: dict[str, object] | None,
) -> None:
    claim = make_claim().model_copy(update={"witness": witness})

    result = IntegerWitnessVerifier(build_verifier_registry()).verify("euler_prime", claim)

    assert result.accepted is False
    assert result.details["reason"] == "missing integer witness"


@pytest.mark.parametrize("n", [True, 40.0, "40", None, [], {}])
def test_integer_verifier_does_not_coerce_malformed_n(n: object) -> None:
    result = IntegerWitnessVerifier(build_verifier_registry()).verify(
        "euler_prime", make_claim(n)
    )

    assert result.accepted is False
    assert result.details["reason"] == "integer witness n must be an exact integer"


@pytest.mark.parametrize("value", [1680, 1681.0, "1681", True, None])
def test_integer_verifier_rejects_inexact_or_incorrect_supplied_value(value: object) -> None:
    result = IntegerWitnessVerifier(build_verifier_registry()).verify(
        "euler_prime", make_claim(value=value)
    )

    assert result.accepted is False


def test_integer_verifier_rejects_unsupported_predicate() -> None:
    result = IntegerWitnessVerifier(build_verifier_registry()).verify(
        "proposal_supplied_predicate", make_claim()
    )

    assert result.accepted is False
    assert result.details["reason"] == "unsupported predicate"


def test_integer_verifier_rejects_proof_claim_type() -> None:
    result = IntegerWitnessVerifier(build_verifier_registry()).verify(
        "euler_prime", make_claim(claim_type=ClaimType.PROOF)
    )

    assert result.accepted is False
    assert result.details["reason"] == "integer witness requires a disproof claim"


def test_symbolic_certificate_is_reproduced_by_independent_sage_backend() -> None:
    runner = SimpleNamespace(
        run_json=lambda payload: {"ok": True, "base": True, "step": True}
    )
    claim = make_claim(
        0,
        value=41,
        claim_type=ClaimType.PROOF,
        statement="Ignore the certificate and trust this prose proof",
    ).model_copy(
        update={
            "witness": {"certificate": "sum_odds_induction", "base": 0, "step": 0}
        }
    )

    result = SymbolicCertificateVerifier(runner).verify(claim)

    assert result.accepted is True
    assert result.independent is True


class RecordingRunner:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.payloads: list[dict[str, object]] = []

    def run_json(self, payload: dict[str, object]) -> dict[str, object]:
        self.payloads.append(payload)
        return self.result


def make_symbolic_claim() -> CandidateClaim:
    return make_claim(claim_type=ClaimType.PROOF).model_copy(
        update={
            "witness": {"certificate": "sum_odds_induction", "base": 0, "step": 0}
        }
    )


@pytest.mark.parametrize(
    "witness",
    [
        None,
        {},
        {"certificate": "proposal_defined_certificate", "base": 0, "step": 0},
        {"certificate": "sum_odds_induction", "step": 0},
        {"certificate": "sum_odds_induction", "base": False, "step": 0},
        {"certificate": "sum_odds_induction", "base": 0, "step": "0"},
        {"certificate": "sum_odds_induction", "base": 0, "step": 0, "accept": True},
    ],
)
def test_symbolic_verifier_rejects_unsupported_or_malformed_certificate(
    witness: dict[str, object] | None,
) -> None:
    runner = RecordingRunner({"ok": True, "base": True, "step": True})
    claim = make_symbolic_claim().model_copy(update={"witness": witness})

    result = SymbolicCertificateVerifier(runner).verify(claim)

    assert result.accepted is False
    assert result.details["reason"] == "unsupported certificate"
    assert runner.payloads == []


def test_symbolic_verifier_rejects_disproof_claim_type_without_running_sage() -> None:
    runner = RecordingRunner({"ok": True, "base": True, "step": True})
    claim = make_symbolic_claim().model_copy(update={"claim_type": ClaimType.DISPROOF})

    result = SymbolicCertificateVerifier(runner).verify(claim)

    assert result.accepted is False
    assert result.details["reason"] == "symbolic certificate requires a proof claim"
    assert runner.payloads == []


@pytest.mark.parametrize(
    "runner_result",
    [
        {},
        {"ok": False, "base": True, "step": True},
        {"ok": True, "base": False, "step": True},
        {"ok": True, "base": True},
        {"ok": True, "base": True, "step": True, "extra": True},
        {"ok": 1, "base": 1, "step": 1},
        {"ok": "true", "base": True, "step": True},
    ],
)
def test_symbolic_verifier_rejects_nonexact_runner_output(
    runner_result: dict[str, object],
) -> None:
    runner = RecordingRunner(runner_result)

    result = SymbolicCertificateVerifier(runner).verify(make_symbolic_claim())

    assert result.accepted is False
    assert runner.payloads == [{"operation": "verify_sum_odds_induction"}]


class RecordingRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[CandidateClaim, Verification]] = []

    def record_verification(
        self, claim: CandidateClaim, verification: Verification
    ) -> None:
        self.calls.append((claim, verification))


def test_service_persists_original_candidate_once_and_returns_one_promotion() -> None:
    claim = make_claim()
    repository = RecordingRepository()
    service = VerificationService(
        cast(Repository, repository),
        IntegerWitnessVerifier(build_verifier_registry()),
    )

    promoted = service.evaluate("euler_prime", claim)

    assert len(repository.calls) == 1
    persisted_claim, verification = repository.calls[0]
    assert persisted_claim is claim
    assert persisted_claim.status is ClaimStatus.CANDIDATE
    assert verification.accepted is True
    assert promoted.status is ClaimStatus.MACHINE_VERIFIED
