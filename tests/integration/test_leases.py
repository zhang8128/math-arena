from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from mathloop.storage.repository import Repository


def test_expired_experiment_can_be_reclaimed(repository: Repository) -> None:
    experiment_id = repository.enqueue_raw(
        problem_id=uuid4(), method_id=uuid4(), lane="completeness", config={}, seed=1
    )
    now = datetime.now(UTC)
    first = repository.claim_next("worker-a", now=now, lease_seconds=1)
    assert first is not None and first.id == experiment_id
    assert repository.claim_next("worker-b", now=now, lease_seconds=1) is None
    reclaimed = repository.claim_next("worker-b", now=now + timedelta(seconds=2), lease_seconds=30)
    assert reclaimed is not None and reclaimed.id == experiment_id


def test_expired_owner_cannot_heartbeat_or_complete(repository: Repository) -> None:
    experiment_id = repository.enqueue_raw(
        problem_id=uuid4(), method_id=uuid4(), lane="completeness", config={}, seed=1
    )
    now = datetime.now(UTC)
    assert repository.claim_next("worker-a", now=now, lease_seconds=1) is not None
    expired_at = now + timedelta(seconds=2)
    assert (
        repository.heartbeat(experiment_id, "worker-a", now=expired_at, lease_seconds=30) is False
    )

    expired_experiment_id = repository.enqueue_raw(
        problem_id=uuid4(), method_id=uuid4(), lane="completeness", config={}, seed=2
    )
    assert repository.claim_next(
        "worker-a", now=now - timedelta(seconds=2), lease_seconds=1
    ) is not None
    with pytest.raises(ValueError, match="not leased by this worker"):
        repository.complete(expired_experiment_id, "worker-a", result={}, cost_usd=0.0)
