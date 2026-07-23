"""Human-review and operational reports derived only from canonical state."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from mathloop.artifacts import ArtifactStore
from mathloop.domain import ClaimStatus
from mathloop.provenance import method_provenance, require_current_method_provenance
from mathloop.storage.repository import Repository
from mathloop.verification import CalibrationVerificationKernel


class Reporting:
    def __init__(
        self,
        repository: Repository,
        artifacts: ArtifactStore,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts

    def review_queue(self) -> list[dict[str, object]]:
        review: list[dict[str, object]] = []
        for record in self.repository.list_review_records():
            experiment = self.repository.get_experiment(record.claim.experiment_id)
            method = self.repository.get_method(experiment.method_id)
            method_identity = require_current_method_provenance(
                method.family,
                method_provenance(method.family),
                method.spec.get("provenance"),
                experiment.config.get("provenance"),
            )
            review.append(
                {
                    "claim_id": str(record.claim.id),
                    "source_id": record.problem.source_id,
                    "source_uri": record.problem.source_uri,
                    "source_hash": record.problem.source_hash,
                    "source_version": record.problem.version,
                    "statement": record.problem.statement,
                    "normalized_statement": record.problem.normalized_statement,
                    "claim_type": record.claim.claim_type.value,
                    "claim_statement": record.claim.statement,
                    "status": record.claim.status.value,
                    "witness": record.claim.model_dump(mode="json")["witness"],
                    "artifact_digest": record.artifact.digest,
                    "verifier": record.verifier,
                    "verifier_version": record.verifier_version,
                    "verification_details": record.verification_details,
                    "experiment_config": experiment.config,
                    "experiment_seed": experiment.seed,
                    "method_provenance": method_identity,
                    "verifier_provenance": record.verification_details.get(
                        "provenance"
                    ),
                    "reproduction_command": f"mathloop reproduce {record.claim.id}",
                    "novelty_status": "unchecked",
                }
            )
        return review

    def metrics(self) -> dict[str, object]:
        return self.repository.metrics_snapshot()

    def reproduce(self, claim_id: UUID) -> dict[str, object]:
        claim = self.repository.get_claim(claim_id)
        if claim.status not in {
            ClaimStatus.MACHINE_VERIFIED,
            ClaimStatus.NOVELTY_CHECKED,
            ClaimStatus.HUMAN_REVIEWED,
        }:
            raise ValueError("claim is not machine verified")
        artifact = self.repository.get_claim_artifact(claim_id)
        content = self.artifacts.open(artifact.digest)
        if hashlib.sha256(content).hexdigest() != artifact.digest:
            raise ValueError("artifact digest verification failed")
        envelope = json.loads(content)
        if not isinstance(envelope, dict) or envelope.get("experiment_id") != str(
            claim.experiment_id
        ):
            raise ValueError("artifact does not belong to the canonical claim")
        experiment = self.repository.get_experiment(claim.experiment_id)
        method = self.repository.get_method(experiment.method_id)
        method_identity = require_current_method_provenance(
            method.family,
            method_provenance(method.family),
            method.spec.get("provenance"),
            experiment.config.get("provenance"),
        )
        if (
            envelope.get("config") != experiment.config
            or envelope.get("seed") != experiment.seed
            or envelope.get("method_provenance") != method_identity
        ):
            raise ValueError(
                "artifact execution provenance differs from the canonical experiment"
            )
        result = envelope.get("result")
        expected_witness = claim.model_dump(mode="json")["witness"]
        if not isinstance(result, dict) or result.get("witness") != expected_witness:
            raise ValueError("artifact witness differs from the canonical claim")
        candidate_snapshot = claim.model_copy(update={"status": ClaimStatus.CANDIDATE})
        verification = CalibrationVerificationKernel().verify(
            self.repository.get_problem(claim.problem_id),
            candidate_snapshot,
        )
        return {
            "claim_id": str(claim.id),
            "artifact_digest": artifact.digest,
            "accepted": verification.accepted,
            "verifier": verification.verifier,
            "verifier_version": verification.verifier_version,
            "details": verification.model_dump(mode="json")["details"],
        }
