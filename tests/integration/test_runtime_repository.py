from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from mathloop.domain import ExperimentStatus
from mathloop.storage.repository import ArtifactRecord, LeaseConflictError, Repository

pytestmark = pytest.mark.integration


def _claim_one(repository: Repository, *, lease_seconds: int = 30):
    repository.enqueue_raw(
        problem_id=uuid4(),
        method_id=uuid4(),
        lane="novelty",
        config={},
        seed=1,
    )
    claimed_at = datetime.now(UTC)
    claimed = repository.claim_next("worker-a", claimed_at, lease_seconds)
    assert claimed is not None
    return claimed, claimed_at


def _artifact(experiment_id) -> ArtifactRecord:
    return ArtifactRecord(
        digest="a" * 64,
        media_type="application/json",
        size_bytes=2,
        relative_path="aa/aa/" + "a" * 64,
        experiment_id=experiment_id,
    )


def test_artifact_record_rejects_noncanonical_metadata() -> None:
    with pytest.raises(ValueError, match="digest"):
        ArtifactRecord(
            digest="not-a-digest",
            media_type="application/json",
            size_bytes=2,
            relative_path="unsafe",
            experiment_id=uuid4(),
        )


def test_worker_result_commit_is_atomic(repository: Repository) -> None:
    claimed, claimed_at = _claim_one(repository)

    repository.commit_worker_result(
        claimed.id,
        "worker-a",
        result={"status": "completed", "artifact_digest": "a" * 64},
        cost_usd=Decimal("0.000000"),
        artifact=_artifact(claimed.id),
        claim=None,
        now=claimed_at + timedelta(seconds=1),
    )

    assert repository.get_experiment(claimed.id).status is ExperimentStatus.SUCCEEDED
    assert repository.count_events("artifact.stored") == 1
    assert repository.count_events("experiment.completed") == 1


def test_invalid_partial_commit_rolls_back_evidence_and_completion(
    repository: Repository,
) -> None:
    claimed, claimed_at = _claim_one(repository)
    artifact = _artifact(claimed.id)
    invalid_artifact = ArtifactRecord(
        digest=artifact.digest,
        media_type=artifact.media_type,
        size_bytes=artifact.size_bytes,
        relative_path=artifact.relative_path,
        experiment_id=uuid4(),
    )

    with pytest.raises(ValueError, match="artifact experiment"):
        repository.commit_worker_result(
            claimed.id,
            "worker-a",
            result={"status": "completed"},
            cost_usd=Decimal("0"),
            artifact=invalid_artifact,
            claim=None,
            now=claimed_at + timedelta(seconds=1),
        )

    assert repository.get_experiment(claimed.id).status is ExperimentStatus.LEASED
    assert repository.count_events("artifact.stored") == 0
    assert repository.count_events("experiment.completed") == 0


def test_stale_owner_cannot_publish_after_lease_reclamation(repository: Repository) -> None:
    claimed, claimed_at = _claim_one(repository, lease_seconds=1)
    reclaimed_at = claimed_at + timedelta(seconds=2)
    reclaimed = repository.claim_next("worker-b", reclaimed_at, lease_seconds=30)
    assert reclaimed is not None and reclaimed.id == claimed.id

    with pytest.raises(LeaseConflictError, match="not leased"):
        repository.commit_worker_result(
            claimed.id,
            "worker-a",
            result={"status": "candidate"},
            cost_usd=Decimal("0"),
            artifact=_artifact(claimed.id),
            claim=None,
            now=reclaimed_at + timedelta(seconds=1),
        )

    assert repository.count_events("artifact.stored") == 0
    assert repository.count_events("experiment.completed") == 0
    canonical = repository.get_experiment(claimed.id)
    assert canonical.status is ExperimentStatus.LEASED


def test_retryable_failure_requeues_same_experiment_identity(
    repository: Repository,
) -> None:
    claimed, claimed_at = _claim_one(repository)

    repository.fail(
        claimed.id,
        "worker-a",
        "infrastructure",
        "temporary sandbox outage",
        retryable=True,
        now=claimed_at + timedelta(seconds=1),
    )

    failures = repository.list_failures()
    assert len(failures) == 1
    assert failures[0].experiment_id == claimed.id
    assert failures[0].retryable is True
    assert repository.requeue_retryable_failures() == 1
    retried = repository.claim_next(
        "worker-b", claimed_at + timedelta(seconds=2), lease_seconds=30
    )
    assert retried is not None and retried.id == claimed.id
