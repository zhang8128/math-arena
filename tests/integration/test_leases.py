from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest

from mathloop.domain import Experiment, ExperimentStatus
from mathloop.storage.repository import EventConflictError, Repository


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


def test_concurrent_claims_lease_an_experiment_once(repository: Repository) -> None:
    experiment_id = repository.enqueue_raw(
        problem_id=uuid4(), method_id=uuid4(), lane="completeness", config={}, seed=1
    )
    now = datetime.now(UTC)
    barrier = Barrier(2)

    def claim(worker: str) -> object:
        barrier.wait()
        return repository.claim_next(worker, now=now, lease_seconds=30)

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(claim, ("worker-a", "worker-b")))

    claimed = [claim for claim in claims if claim is not None]
    assert len(claimed) == 1
    assert claimed[0].id == experiment_id


def test_enqueued_experiment_exact_replay_preserves_current_lease(
    repository: Repository,
) -> None:
    experiment = Experiment(
        id=uuid4(),
        problem_id=uuid4(),
        method_id=uuid4(),
        lane="completeness",
        config={},
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(experiment, idempotency_key="experiment:first")
    assert repository.claim_next("worker-a", now=datetime.now(UTC), lease_seconds=30)

    assert repository.enqueue(experiment, idempotency_key="experiment:second") == experiment.id
    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT status, lease_owner FROM experiments WHERE id = %(id)s",
            {"id": experiment.id},
        ).fetchone()
    assert row == ("leased", "worker-a")


def test_claim_event_conflict_rolls_back_projection_update(repository: Repository) -> None:
    experiment_id = repository.enqueue_raw(
        problem_id=uuid4(), method_id=uuid4(), lane="completeness", config={}, seed=1
    )
    now = datetime.now(UTC)
    with repository.database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, event_type, payload, idempotency_key
            ) VALUES ('experiment', %(id)s, 'experiment.leased', '{}'::jsonb, %(key)s)
            """,
            {"id": experiment_id, "key": f"experiment:lease:{experiment_id}:1"},
        )

    with pytest.raises(EventConflictError, match="experiment:lease"):
        repository.claim_next("worker-a", now=now, lease_seconds=30)

    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT status, attempt, lease_owner FROM experiments WHERE id = %(id)s",
            {"id": experiment_id},
        ).fetchone()
    assert row == ("queued", 0, None)


def test_heartbeat_event_conflict_rolls_back_projection_update(repository: Repository) -> None:
    experiment_id = repository.enqueue_raw(
        problem_id=uuid4(), method_id=uuid4(), lane="completeness", config={}, seed=1
    )
    claimed_at = datetime.now(UTC)
    assert repository.claim_next("worker-a", now=claimed_at, lease_seconds=120) is not None
    heartbeat_at = claimed_at + timedelta(seconds=1)
    assert repository.heartbeat(experiment_id, "worker-a", heartbeat_at, lease_seconds=30)

    with pytest.raises(EventConflictError, match="experiment:heartbeat"):
        repository.heartbeat(experiment_id, "worker-a", heartbeat_at, lease_seconds=60)

    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT lease_expires_at FROM experiments WHERE id = %(id)s",
            {"id": experiment_id},
        ).fetchone()
    assert row is not None
    assert row[0] == heartbeat_at + timedelta(seconds=30)


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


@pytest.mark.parametrize("lease_seconds", [0, -1])
def test_lease_duration_must_be_positive(
    repository: Repository, lease_seconds: int
) -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="positive"):
        repository.claim_next("worker-a", now=now, lease_seconds=lease_seconds)
    with pytest.raises(ValueError, match="positive"):
        repository.heartbeat(uuid4(), "worker-a", now=now, lease_seconds=lease_seconds)


def test_lease_timestamp_must_be_timezone_aware(repository: Repository) -> None:
    now = datetime.now()
    with pytest.raises(ValueError, match="timezone-aware"):
        repository.claim_next("worker-a", now=now, lease_seconds=30)
    with pytest.raises(ValueError, match="timezone-aware"):
        repository.heartbeat(uuid4(), "worker-a", now=now, lease_seconds=30)


def test_complete_rejects_negative_cost(repository: Repository) -> None:
    experiment_id = repository.enqueue_raw(
        problem_id=uuid4(), method_id=uuid4(), lane="completeness", config={}, seed=1
    )
    now = datetime.now(UTC)
    assert repository.claim_next("worker-a", now=now, lease_seconds=30) is not None

    with pytest.raises(ValueError, match="non-negative"):
        repository.complete(experiment_id, "worker-a", result={}, cost_usd=-0.01)

    assert repository.count_events("experiment.completed") == 0
