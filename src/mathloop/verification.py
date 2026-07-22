"""Independent verification and verified-claim persistence."""

from typing import Protocol

from mathloop.domain import CandidateClaim, ClaimType, Verification, advance_claim
from mathloop.predicates.base import PredicateRegistry
from mathloop.storage.repository import Repository


class JsonRunner(Protocol):
    def run_json(self, payload: dict[str, object]) -> dict[str, object]: ...


class IntegerWitnessVerifier:
    name = "integer-predicate"
    version = "1"

    def __init__(self, predicates: PredicateRegistry) -> None:
        self.predicates = predicates

    def verify(self, predicate_id: str, claim: CandidateClaim) -> Verification:
        if claim.claim_type is not ClaimType.DISPROOF:
            return self._rejected("integer witness requires a disproof claim")
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

    def verify(self, claim: CandidateClaim) -> Verification:
        if claim.claim_type is not ClaimType.PROOF:
            return self._rejected("symbolic certificate requires a proof claim")
        witness = claim.witness
        if not self._is_exact_sum_odds_certificate(witness):
            return self._rejected("unsupported certificate")
        result = self.runner.run_json({"operation": "verify_sum_odds_induction"})
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
    def _is_exact_sum_odds_certificate(witness: dict[str, object] | None) -> bool:
        return (
            witness is not None
            and set(witness) == {"certificate", "base", "step"}
            and witness["certificate"] == "sum_odds_induction"
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


class VerificationService:
    def __init__(self, repository: Repository, verifier: IntegerWitnessVerifier) -> None:
        self.repository = repository
        self.verifier = verifier

    def evaluate(self, predicate_id: str, claim: CandidateClaim) -> CandidateClaim:
        verification = self.verifier.verify(predicate_id, claim)
        self.repository.record_verification(claim, verification)
        return advance_claim(claim, verification)
