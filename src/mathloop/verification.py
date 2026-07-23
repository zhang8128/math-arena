"""Independent verification and verified-claim persistence."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol
from uuid import UUID

from mathloop.domain import (
    CandidateClaim,
    ClaimStatus,
    ClaimType,
    Problem,
    Verification,
)
from mathloop.predicates.base import PredicateRegistry
from mathloop.provenance import SAGE_IMAGE_DIGEST, verifier_provenance
from mathloop.storage.repository import (
    ClaimStateConflictError,
    InvalidIdentifierError,
    Repository,
)
from mathloop.tools.docker import DockerLimits, DockerRunner
from mathloop.verifiers.calibration import build_verifier_registry


class JsonRunner(Protocol):
    def run_json(self, payload: dict[str, object]) -> dict[str, object]: ...


class ClaimVerifier(Protocol):
    def verify(self, problem: Problem, claim: CandidateClaim) -> Verification: ...


@dataclass(frozen=True)
class IntegerVerificationBounds:
    minimum: int
    maximum: int


INTEGER_VERIFICATION_BOUNDS: Mapping[str, IntegerVerificationBounds] = MappingProxyType(
    {
        "euler_prime": IntegerVerificationBounds(minimum=0, maximum=100_000),
        "fermat_prime": IntegerVerificationBounds(minimum=0, maximum=5),
        "sum_odds": IntegerVerificationBounds(minimum=0, maximum=1_000_000_000),
        "quadratic_two_prime": IntegerVerificationBounds(
            minimum=0,
            maximum=100_000,
        ),
        "quadratic_three_prime": IntegerVerificationBounds(
            minimum=0,
            maximum=100_000,
        ),
        "sum_integers": IntegerVerificationBounds(
            minimum=0,
            maximum=1_000_000_000,
        ),
    }
)


def _problem_identity_error(problem: Problem, claim: CandidateClaim) -> str | None:
    if type(problem.id) is not UUID or type(claim.problem_id) is not UUID:
        return "invalid problem identity"
    if claim.problem_id != problem.id:
        return "claim does not belong to problem"
    return None


def _integer_checker(problem: Problem) -> tuple[str, int] | None:
    checker = problem.checker
    if not isinstance(checker, dict) or set(checker) != {
        "kind",
        "predicate_id",
        "start",
    }:
        return None
    kind = checker["kind"]
    predicate_id = checker["predicate_id"]
    start = checker["start"]
    if (
        type(kind) is not str
        or kind != "integer_predicate"
        or type(predicate_id) is not str
        or type(start) is not int
    ):
        return None
    return predicate_id, start


class IntegerWitnessVerifier:
    name = "integer-predicate"
    version = "1"

    def __init__(self, predicates: PredicateRegistry) -> None:
        self.predicates = predicates

    def verify(self, problem: Problem, claim: CandidateClaim) -> Verification:
        identity_error = _problem_identity_error(problem, claim)
        if identity_error is not None:
            return self._rejected(identity_error)
        if claim.status is not ClaimStatus.CANDIDATE:
            return self._rejected("only candidate claims can be verified")
        checker = _integer_checker(problem)
        if checker is None:
            return self._rejected("unsupported checker contract")
        predicate_id, declared_start = checker
        if claim.claim_type is not ClaimType.DISPROOF:
            return self._rejected("integer witness requires a disproof claim")
        bounds = INTEGER_VERIFICATION_BOUNDS.get(predicate_id)
        if bounds is None:
            return self._rejected("unsupported predicate")
        if not self.predicates.contains(predicate_id):
            return self._rejected("unsupported predicate")
        witness = claim.witness
        if witness is None or "n" not in witness or "value" not in witness:
            return self._rejected("missing integer witness")
        n = witness["n"]
        if type(n) is not int:
            return self._rejected("integer witness n must be an exact integer")
        supplied_value = witness["value"]
        if type(supplied_value) is not int:
            return self._rejected("integer witness value must be an exact integer")
        if n < declared_start or n < bounds.minimum or n > bounds.maximum:
            return self._rejected("integer witness is outside verifier bounds")
        evaluation = self.predicates.evaluate(predicate_id, n)
        accepted = not evaluation.holds and supplied_value == evaluation.value
        return Verification(
            verifier=self.name,
            verifier_version=self.version,
            accepted=accepted,
            independent=True,
            details={
                "n": n,
                "computed_value": evaluation.value,
                "predicate_holds": evaluation.holds,
            },
        )

    def _rejected(self, reason: str) -> Verification:
        return Verification(
            verifier=self.name,
            verifier_version=self.version,
            accepted=False,
            independent=True,
            details={"reason": reason},
        )


class SymbolicCertificateVerifier:
    name = "sage-symbolic-induction"
    version = "1"

    def __init__(self, runner: JsonRunner) -> None:
        self.runner = runner

    def verify(self, problem: Problem, claim: CandidateClaim) -> Verification:
        identity_error = _problem_identity_error(problem, claim)
        if identity_error is not None:
            return self._rejected(identity_error)
        if claim.status is not ClaimStatus.CANDIDATE:
            return self._rejected("only candidate claims can be verified")
        checker = _integer_checker(problem)
        if checker not in {("sum_odds", 0), ("sum_integers", 0)}:
            return self._rejected("unsupported checker contract")
        if claim.claim_type is not ClaimType.PROOF:
            return self._rejected("symbolic certificate requires a proof claim")
        witness = claim.witness
        predicate_id = checker[0]
        expected_certificate = (
            "sum_odds_induction"
            if predicate_id == "sum_odds"
            else "sum_integers_induction"
        )
        if not self._is_exact_certificate(witness, expected_certificate):
            return self._rejected("unsupported certificate")
        result = self.runner.run_json(
            {"operation": f"verify_{expected_certificate}"}
        )
        expected_keys = {"ok", "base", "step"}
        accepted = set(result) == expected_keys and all(
            result[key] is True for key in expected_keys
        )
        return Verification(
            verifier=self.name,
            verifier_version=self.version,
            accepted=accepted,
            independent=True,
            details=result,
        )

    @staticmethod
    def _is_exact_certificate(
        witness: dict[str, object] | None,
        expected_certificate: str,
    ) -> bool:
        return (
            witness is not None
            and set(witness) == {"certificate", "base", "step"}
            and witness["certificate"] == expected_certificate
            and type(witness["base"]) is int
            and witness["base"] == 0
            and type(witness["step"]) is int
            and witness["step"] == 0
        )

    def _rejected(self, reason: str) -> Verification:
        return Verification(
            verifier=self.name,
            verifier_version=self.version,
            accepted=False,
            independent=True,
            details={"reason": reason},
        )


class CalibrationVerificationKernel:
    """Own the fixed verifier implementations used by repository persistence."""

    __slots__ = ()

    def verify(self, problem: Problem, claim: CandidateClaim) -> Verification:
        if claim.claim_type is ClaimType.PROOF:
            verification = SymbolicCertificateVerifier(
                DockerRunner(
                    image=SAGE_IMAGE_DIGEST,
                    limits=DockerLimits(seconds=60, memory_mb=512, cpus=1.0),
                )
            ).verify(
                problem,
                claim,
            )
        else:
            verification = IntegerWitnessVerifier(build_verifier_registry()).verify(
                problem,
                claim,
            )
        return verification.model_copy(
            update={
                "details": {
                    **verification.details,
                    "provenance": verifier_provenance(verification.verifier),
                }
            }
        )

class VerificationService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def evaluate(self, claim_id: UUID) -> CandidateClaim:
        if type(claim_id) is not UUID:
            raise InvalidIdentifierError("claim_id must be an exact UUID")
        claim = self.repository.get_claim(claim_id)
        if claim.status is not ClaimStatus.CANDIDATE:
            raise ClaimStateConflictError(
                f"claim {claim.id} is not in candidate state"
            )
        return self.repository.evaluate_and_record_claim(
            claim,
            record_method_outcome=False,
        )
