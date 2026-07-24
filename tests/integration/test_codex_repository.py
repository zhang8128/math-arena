from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest

from mathloop.codex.domain import (
    CodexModelRole,
    CodexPolicy,
    CodexTurnReceipt,
    CodexTurnReservation,
    CodexTurnStatus,
    CodexUsage,
)
from mathloop.codex.events import CodexEvent
from mathloop.domain import Experiment, ExperimentStatus
from mathloop.storage.repository import (
    CodexTurnConflictError,
    CodexTurnNotFoundError,
    EventConflictError,
    Repository,
)

# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------


def _enqueue_experiment(repository: Repository, *, lane: str = "codex") -> UUID:
    experiment = Experiment(
        id=uuid4(),
        problem_id=uuid4(),
        method_id=uuid4(),
        lane=lane,
        config={},
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(experiment, f"experiment:{experiment.id}")
    return experiment.id


def reserve_one(
    repository: Repository,
    *,
    experiment_id: UUID | None = None,
    worker_id: str = "worker-1",
    role: CodexModelRole = CodexModelRole.TERRA,
    model: str = "gpt-5.6-terra",
    policy: CodexPolicy | None = None,
    now: datetime | None = None,
) -> CodexTurnReservation:
    reservation = repository.reserve_codex_turn(
        experiment_id=experiment_id if experiment_id is not None else _enqueue_experiment(
            repository
        ),
        worker_id=worker_id,
        role=role,
        model=model,
        policy=policy if policy is not None else CodexPolicy(),
        now=now if now is not None else datetime.now(UTC),
    )
    assert reservation is not None
    return reservation


def _seed_codex_turns(
    repository: Repository,
    *,
    budget_day: date,
    role: CodexModelRole,
    count: int,
    status: CodexTurnStatus = CodexTurnStatus.COMPLETED,
) -> None:
    """Bulk-insert already-terminal codex_turns rows (and their owning experiments).

    Used to reach large role/day boundaries (e.g. the approved 40/40/20 envelope)
    without paying for hundreds of individual reserve/dispatch/fail round trips.
    """
    if count <= 0:
        return
    with repository.database.transaction() as connection:
        connection.execute(
            """
            WITH new_experiments AS (
                INSERT INTO experiments (
                    id, problem_id, method_id, lane, config, seed, status,
                    created_at, updated_at
                )
                SELECT gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), 'codex-seed',
                       '{}'::jsonb, 1, 'succeeded', now(), now()
                FROM generate_series(1, %(count)s)
                RETURNING id
            )
            INSERT INTO codex_turns (
                id, experiment_id, budget_day, role, model, status,
                lease_owner, lease_expires_at, created_at, updated_at
            )
            SELECT gen_random_uuid(), id, %(budget_day)s, %(role)s, 'seed-model', %(status)s,
                   'seed-worker', now() + interval '30 minutes', now(), now()
            FROM new_experiments
            """,
            {
                "count": count,
                "budget_day": budget_day,
                "role": role.value,
                "status": status.value,
            },
        )


def _turn_started_event(sequence: int = 0) -> CodexEvent:
    return CodexEvent(
        sequence=sequence,
        event_type="turn.started",
        payload={"type": "turn.started"},
        raw_sha256="a" * 64,
    )


def _turn_completed_event(usage: dict[str, int], sequence: int = 1) -> CodexEvent:
    return CodexEvent(
        sequence=sequence,
        event_type="turn.completed",
        payload={"type": "turn.completed", "usage": usage},
        raw_sha256="b" * 64,
    )


_USAGE_PAYLOAD = {
    "input_tokens": 10,
    "cached_input_tokens": 2,
    "output_tokens": 4,
    "reasoning_output_tokens": 1,
}


def _receipt_for(reservation: CodexTurnReservation, *, usage: dict[str, int]) -> CodexTurnReceipt:
    return CodexTurnReceipt(
        reservation_id=reservation.id,
        experiment_id=reservation.experiment_id,
        thread_id="thread-1",
        model=reservation.model,
        cli_version="0.145.0",
        usage=CodexUsage(**usage),
        final_status="completed",
    )


# ---------------------------------------------------------------------------
# Brief-verbatim cases
# ---------------------------------------------------------------------------


def test_codex_turn_limit_and_concurrency_are_atomic(repository: Repository) -> None:
    policy = CodexPolicy(
        daily_turn_limit=2,
        concurrent_turn_limit=1,
        model_turn_limits={"luna": 0, "terra": 2, "sol": 0},
        reserved_sol_turns=0,
    )
    fixed_now = datetime.now(UTC)
    experiment_id_1 = _enqueue_experiment(repository)
    experiment_id_2 = _enqueue_experiment(repository)

    first = repository.reserve_codex_turn(
        experiment_id=experiment_id_1,
        worker_id="worker-1",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=fixed_now,
    )
    assert first is not None
    assert (
        repository.reserve_codex_turn(
            experiment_id=experiment_id_2,
            worker_id="worker-2",
            role=CodexModelRole.TERRA,
            model="gpt-5.6-terra",
            policy=policy,
            now=fixed_now,
        )
        is None
    )


def test_dispatched_turn_cannot_be_reserved_or_replayed(repository: Repository) -> None:
    reservation = reserve_one(repository)
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.fail_codex_turn(
        reservation.id,
        status=CodexTurnStatus.AMBIGUOUS,
        failure_kind="worker_lost",
        failure_message="dispatch outcome is ambiguous",
    )

    assert repository.reserve_codex_turn_for_existing_experiment(reservation.experiment_id) is None


# ---------------------------------------------------------------------------
# Role quota and reserved-Sol floor arithmetic
# ---------------------------------------------------------------------------


def test_role_quota_blocks_at_the_approved_40_40_20_envelope(repository: Repository) -> None:
    policy = CodexPolicy()  # 100 daily / 4 concurrent / 40 luna / 40 terra / 20 sol / 10 reserved
    now = datetime.now(UTC)
    budget_day = now.date()

    _seed_codex_turns(repository, budget_day=budget_day, role=CodexModelRole.LUNA, count=40)
    assert (
        repository.reserve_codex_turn(
            experiment_id=_enqueue_experiment(repository),
            worker_id="worker-luna",
            role=CodexModelRole.LUNA,
            model="gpt-5.6-luna",
            policy=policy,
            now=now,
        )
        is None
    )

    _seed_codex_turns(repository, budget_day=budget_day, role=CodexModelRole.TERRA, count=40)
    assert (
        repository.reserve_codex_turn(
            experiment_id=_enqueue_experiment(repository),
            worker_id="worker-terra",
            role=CodexModelRole.TERRA,
            model="gpt-5.6-terra",
            policy=policy,
            now=now,
        )
        is None
    )

    _seed_codex_turns(repository, budget_day=budget_day, role=CodexModelRole.SOL, count=20)
    assert (
        repository.reserve_codex_turn(
            experiment_id=_enqueue_experiment(repository),
            worker_id="worker-sol",
            role=CodexModelRole.SOL,
            model="gpt-5.6-sol",
            policy=policy,
            now=now,
        )
        is None
    )


def test_reserved_sol_floor_blocks_non_sol_but_sol_competes_normally(
    repository: Repository,
) -> None:
    policy = CodexPolicy(
        daily_turn_limit=11,
        concurrent_turn_limit=5,
        model_turn_limits={"luna": 5, "terra": 5, "sol": 5},
        reserved_sol_turns=10,
    )
    now = datetime.now(UTC)
    budget_day = now.date()

    # Fills the entire non-reserved pool (daily_turn_limit - reserved_sol_turns = 1).
    _seed_codex_turns(repository, budget_day=budget_day, role=CodexModelRole.TERRA, count=1)

    assert (
        repository.reserve_codex_turn(
            experiment_id=_enqueue_experiment(repository),
            worker_id="worker-luna",
            role=CodexModelRole.LUNA,
            model="gpt-5.6-luna",
            policy=policy,
            now=now,
        )
        is None
    ), "non-Sol roles must never eat into the reserved Sol floor"

    reservation = repository.reserve_codex_turn(
        experiment_id=_enqueue_experiment(repository),
        worker_id="worker-sol",
        role=CodexModelRole.SOL,
        model="gpt-5.6-sol",
        policy=policy,
        now=now,
    )
    assert reservation is not None, "Sol reservations must still compete for the general pool"


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_concurrent_reservations_serialize_and_exactly_one_wins(repository: Repository) -> None:
    policy = CodexPolicy(
        daily_turn_limit=1,
        concurrent_turn_limit=4,
        model_turn_limits={"luna": 0, "terra": 1, "sol": 0},
        reserved_sol_turns=0,
    )
    now = datetime.now(UTC)
    experiment_a = _enqueue_experiment(repository)
    experiment_b = _enqueue_experiment(repository)
    barrier = Barrier(2)

    def attempt(experiment_id: UUID, worker: str) -> CodexTurnReservation | None:
        barrier.wait()
        return repository.reserve_codex_turn(
            experiment_id=experiment_id,
            worker_id=worker,
            role=CodexModelRole.TERRA,
            model="gpt-5.6-terra",
            policy=policy,
            now=now,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda pair: attempt(*pair),
                [(experiment_a, "worker-a"), (experiment_b, "worker-b")],
            )
        )

    successes = [result for result in results if result is not None]
    assert len(successes) == 1


# ---------------------------------------------------------------------------
# Reservation replay
# ---------------------------------------------------------------------------


def test_reservation_exact_replay_is_idempotent(repository: Repository) -> None:
    policy = CodexPolicy()
    now = datetime.now(UTC)
    experiment_id = _enqueue_experiment(repository)

    first = repository.reserve_codex_turn(
        experiment_id=experiment_id,
        worker_id="worker-1",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=now,
    )
    second = repository.reserve_codex_turn(
        experiment_id=experiment_id,
        worker_id="worker-1",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=now,
    )
    assert first is not None
    assert second == first


def test_reservation_replay_with_different_worker_is_still_idempotent(
    repository: Repository,
) -> None:
    """worker_id is lease bookkeeping, not part of the reservation's immutable identity."""
    policy = CodexPolicy()
    now = datetime.now(UTC)
    experiment_id = _enqueue_experiment(repository)

    first = repository.reserve_codex_turn(
        experiment_id=experiment_id,
        worker_id="worker-1",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=now,
    )
    second = repository.reserve_codex_turn(
        experiment_id=experiment_id,
        worker_id="worker-2",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=now,
    )
    assert first is not None
    assert second == first


def test_reservation_replay_with_mismatched_role_conflicts(repository: Repository) -> None:
    policy = CodexPolicy()
    now = datetime.now(UTC)
    experiment_id = _enqueue_experiment(repository)

    first = repository.reserve_codex_turn(
        experiment_id=experiment_id,
        worker_id="worker-1",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=now,
    )
    assert first is not None

    with pytest.raises(EventConflictError):
        repository.reserve_codex_turn(
            experiment_id=experiment_id,
            worker_id="worker-1",
            role=CodexModelRole.LUNA,
            model="gpt-5.6-luna",
            policy=policy,
            now=now,
        )


def test_reservation_replay_with_mismatched_model_conflicts(repository: Repository) -> None:
    policy = CodexPolicy()
    now = datetime.now(UTC)
    experiment_id = _enqueue_experiment(repository)

    first = repository.reserve_codex_turn(
        experiment_id=experiment_id,
        worker_id="worker-1",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=now,
    )
    assert first is not None

    with pytest.raises(EventConflictError):
        repository.reserve_codex_turn(
            experiment_id=experiment_id,
            worker_id="worker-1",
            role=CodexModelRole.TERRA,
            model="gpt-5.6-terra-different",
            policy=policy,
            now=now,
        )


def test_reservation_replay_with_mismatched_deadline_conflicts(repository: Repository) -> None:
    """turn_timeout_seconds feeds the reservation's immutable deadline_seconds."""
    now = datetime.now(UTC)
    experiment_id = _enqueue_experiment(repository)

    first = repository.reserve_codex_turn(
        experiment_id=experiment_id,
        worker_id="worker-1",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=CodexPolicy(turn_timeout_seconds=1800),
        now=now,
    )
    assert first is not None

    with pytest.raises(EventConflictError):
        repository.reserve_codex_turn(
            experiment_id=experiment_id,
            worker_id="worker-1",
            role=CodexModelRole.TERRA,
            model="gpt-5.6-terra",
            policy=CodexPolicy(turn_timeout_seconds=900),
            now=now,
        )


def test_reserve_codex_turn_returns_none_for_an_already_dispatched_experiment(
    repository: Repository,
) -> None:
    """Calling reserve_codex_turn again (not just the `_for_existing_experiment` helper)

    for an experiment whose turn has moved past `reserved` must report unreservable
    -- not raise, and not mint a second reservation -- even when every field the
    caller passes matches the original reservation exactly.
    """
    policy = CodexPolicy()
    now = datetime.now(UTC)
    experiment_id = _enqueue_experiment(repository)

    reservation = repository.reserve_codex_turn(
        experiment_id=experiment_id,
        worker_id="worker-1",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=now,
    )
    assert reservation is not None
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")

    again = repository.reserve_codex_turn(
        experiment_id=experiment_id,
        worker_id="worker-1",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=now,
    )
    assert again is None

    with repository.database.transaction() as connection:
        count = connection.execute(
            "SELECT count(*) FROM codex_turns WHERE experiment_id = %(id)s",
            {"id": experiment_id},
        ).fetchone()
    assert count == (1,), "a second call must never mint a second row for the same experiment"


def test_stale_reserved_row_cannot_be_replayed_and_dispatched_past_its_own_lease(
    repository: Repository,
) -> None:
    """A crash/restart retry must not resurrect an expired, un-reconciled reservation.

    Concrete failure this guards against, with concurrent_turn_limit=1 and no
    reconcile_codex_turns ever running:

    1. worker A reserves turn X for experiment E1; its lease will expire.
    2. Past that expiry, with X still sitting un-reconciled as 'reserved', worker
       B reserves turn Y for a different experiment E2 -- legitimate, since an
       un-dispatched reservation's lease lapsing is safe to free by elapsed
       time alone (nothing ever ran for it).
    3. worker A retries reserve_codex_turn for E1 (a realistic crash/restart
       retry). It must NOT get X handed back as though it were still a live
       reservation.
    4. worker A must also not be able to dispatch X directly (e.g. from an id it
       cached before crashing) once its lease has lapsed.

    Without both guards, X could reach 'dispatched' -- a status this ledger
    counts as active concurrency unconditionally -- while Y is also active,
    silently exceeding the concurrency limit with no error raised anywhere and
    no dependency on reconcile_codex_turns ever being invoked.
    """
    policy = CodexPolicy(
        daily_turn_limit=5,
        concurrent_turn_limit=1,
        model_turn_limits={"luna": 0, "terra": 5, "sol": 0},
        reserved_sol_turns=0,
        turn_timeout_seconds=1800,
    )
    t0 = datetime.now(UTC)
    experiment_e1 = _enqueue_experiment(repository)
    experiment_e2 = _enqueue_experiment(repository)

    turn_x = repository.reserve_codex_turn(
        experiment_id=experiment_e1,
        worker_id="worker-a",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=t0,
    )
    assert turn_x is not None

    past_lease = t0 + timedelta(seconds=1801)

    turn_y = repository.reserve_codex_turn(
        experiment_id=experiment_e2,
        worker_id="worker-b",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=past_lease,
    )
    assert turn_y is not None, (
        "an un-dispatched reservation's own lapsed lease is safe to free by elapsed "
        "time alone, since nothing was ever dispatched from it"
    )

    replayed = repository.reserve_codex_turn(
        experiment_id=experiment_e1,
        worker_id="worker-a",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=past_lease,
    )
    assert replayed is None, (
        "an expired, un-reconciled reservation must not be replayed back to the caller "
        "as though it were still a live reservation"
    )

    with pytest.raises(CodexTurnConflictError):
        repository.mark_codex_turn_dispatched(turn_x.id, "worker-a", now=past_lease)

    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT status FROM codex_turns WHERE id = %(id)s", {"id": turn_x.id}
        ).fetchone()
    assert row == ("reserved",), (
        "a lapsed reservation must never be promoted to 'dispatched' -- that status is "
        "counted as active concurrency unconditionally"
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def test_mark_dispatched_rejects_wrong_worker(repository: Repository) -> None:
    reservation = reserve_one(repository, worker_id="worker-1")
    with pytest.raises(CodexTurnConflictError):
        repository.mark_codex_turn_dispatched(reservation.id, "worker-intruder")


def test_mark_dispatched_replay_by_same_worker_is_idempotent(repository: Repository) -> None:
    reservation = reserve_one(repository, worker_id="worker-1")
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")  # no error

    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT status FROM codex_turns WHERE id = %(id)s", {"id": reservation.id}
        ).fetchone()
    assert row == ("dispatched",)


# ---------------------------------------------------------------------------
# Raw wire event replay
# ---------------------------------------------------------------------------


def test_append_codex_turn_event_replay_is_idempotent_on_exact_match(
    repository: Repository,
) -> None:
    reservation = reserve_one(repository)
    event = _turn_started_event()

    repository.append_codex_turn_event(reservation.id, event)
    repository.append_codex_turn_event(reservation.id, event)

    with repository.database.transaction() as connection:
        count = connection.execute(
            "SELECT count(*) FROM codex_turn_events WHERE turn_id = %(id)s",
            {"id": reservation.id},
        ).fetchone()
    assert count == (1,)


def test_append_codex_turn_event_replay_conflicts_on_mismatch(repository: Repository) -> None:
    reservation = reserve_one(repository)
    repository.append_codex_turn_event(reservation.id, _turn_started_event())

    conflicting = CodexEvent(
        sequence=0,
        event_type="turn.started",
        payload={"type": "turn.started", "extra": "different"},
        raw_sha256="c" * 64,
    )
    with pytest.raises(EventConflictError):
        repository.append_codex_turn_event(reservation.id, conflicting)


def test_append_codex_turn_event_rejects_unknown_turn(repository: Repository) -> None:
    with pytest.raises(CodexTurnNotFoundError):
        repository.append_codex_turn_event(uuid4(), _turn_started_event())


# ---------------------------------------------------------------------------
# Completion
# ---------------------------------------------------------------------------


def test_complete_codex_turn_requires_prior_dispatch(repository: Repository) -> None:
    reservation = reserve_one(repository)
    receipt = _receipt_for(reservation, usage=_USAGE_PAYLOAD)
    with pytest.raises(CodexTurnConflictError):
        repository.complete_codex_turn(reservation.id, receipt)


def test_complete_codex_turn_persists_usage_and_is_terminal_immutable(
    repository: Repository,
) -> None:
    reservation = reserve_one(repository)
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.append_codex_turn_event(reservation.id, _turn_started_event())
    repository.append_codex_turn_event(
        reservation.id, _turn_completed_event(_USAGE_PAYLOAD, sequence=1)
    )
    receipt = _receipt_for(reservation, usage=_USAGE_PAYLOAD)

    repository.complete_codex_turn(reservation.id, receipt)

    with repository.database.transaction() as connection:
        row = connection.execute(
            """
            SELECT status, input_tokens, cached_input_tokens, output_tokens,
                   reasoning_output_tokens, thread_id, cli_version
            FROM codex_turns WHERE id = %(id)s
            """,
            {"id": reservation.id},
        ).fetchone()
    assert row == ("completed", 10, 2, 4, 1, "thread-1", "0.145.0")

    with pytest.raises(CodexTurnConflictError):
        repository.complete_codex_turn(reservation.id, receipt)


def test_complete_codex_turn_requires_exactly_one_turn_started_event(
    repository: Repository,
) -> None:
    reservation = reserve_one(repository)
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.append_codex_turn_event(
        reservation.id, _turn_completed_event(_USAGE_PAYLOAD, sequence=0)
    )
    receipt = _receipt_for(reservation, usage=_USAGE_PAYLOAD)

    with pytest.raises(CodexTurnConflictError):
        repository.complete_codex_turn(reservation.id, receipt)


def test_complete_codex_turn_rejects_receipt_usage_mismatch(repository: Repository) -> None:
    reservation = reserve_one(repository)
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.append_codex_turn_event(reservation.id, _turn_started_event())
    repository.append_codex_turn_event(
        reservation.id, _turn_completed_event(_USAGE_PAYLOAD, sequence=1)
    )
    mismatched = _receipt_for(
        reservation,
        usage={**_USAGE_PAYLOAD, "input_tokens": 999},
    )

    with pytest.raises(CodexTurnConflictError):
        repository.complete_codex_turn(reservation.id, mismatched)


def test_complete_codex_turn_rejects_receipt_for_another_reservation(
    repository: Repository,
) -> None:
    reservation = reserve_one(repository)
    other = reserve_one(repository, worker_id="worker-2")
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.append_codex_turn_event(reservation.id, _turn_started_event())
    repository.append_codex_turn_event(
        reservation.id, _turn_completed_event(_USAGE_PAYLOAD, sequence=1)
    )
    foreign_receipt = _receipt_for(other, usage=_USAGE_PAYLOAD)

    with pytest.raises(CodexTurnConflictError):
        repository.complete_codex_turn(reservation.id, foreign_receipt)


def test_complete_codex_turn_rejects_experiment_id_mismatch_with_correct_reservation_id(
    repository: Repository,
) -> None:
    """A correct reservation_id must not mask a forged/mismatched experiment_id.

    `test_complete_codex_turn_rejects_receipt_for_another_reservation` builds its
    receipt from a *different* reservation, so it is rejected at the earlier,
    shallower `receipt.reservation_id != canonical_id` check and never exercises
    the `experiment_id != receipt.experiment_id` identity check that follows it.
    This test keeps `reservation_id` correct so only the identity check can catch
    the mismatch.
    """
    reservation = reserve_one(repository)
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.append_codex_turn_event(reservation.id, _turn_started_event())
    repository.append_codex_turn_event(
        reservation.id, _turn_completed_event(_USAGE_PAYLOAD, sequence=1)
    )
    receipt = CodexTurnReceipt(
        reservation_id=reservation.id,
        experiment_id=uuid4(),
        thread_id="thread-1",
        model=reservation.model,
        cli_version="0.145.0",
        usage=CodexUsage(**_USAGE_PAYLOAD),
        final_status="completed",
    )

    with pytest.raises(CodexTurnConflictError):
        repository.complete_codex_turn(reservation.id, receipt)


def test_complete_codex_turn_rejects_model_mismatch_with_correct_reservation_id(
    repository: Repository,
) -> None:
    """Same as above, isolating the `model != receipt.model` half of the identity check."""
    reservation = reserve_one(repository)
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.append_codex_turn_event(reservation.id, _turn_started_event())
    repository.append_codex_turn_event(
        reservation.id, _turn_completed_event(_USAGE_PAYLOAD, sequence=1)
    )
    receipt = CodexTurnReceipt(
        reservation_id=reservation.id,
        experiment_id=reservation.experiment_id,
        thread_id="thread-1",
        model="a-different-model",
        cli_version="0.145.0",
        usage=CodexUsage(**_USAGE_PAYLOAD),
        final_status="completed",
    )

    with pytest.raises(CodexTurnConflictError):
        repository.complete_codex_turn(reservation.id, receipt)


# ---------------------------------------------------------------------------
# Failure
# ---------------------------------------------------------------------------


def test_fail_codex_turn_rejects_updates_to_a_terminal_row(repository: Repository) -> None:
    reservation = reserve_one(repository)
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.fail_codex_turn(
        reservation.id,
        status=CodexTurnStatus.FAILED,
        failure_kind="worker_lost",
        failure_message="first failure",
    )

    with pytest.raises(CodexTurnConflictError):
        repository.fail_codex_turn(
            reservation.id,
            status=CodexTurnStatus.FAILED,
            failure_kind="worker_lost",
            failure_message="first failure",
        )


# ---------------------------------------------------------------------------
# Lease expiry and reconciliation
# ---------------------------------------------------------------------------


def test_reconcile_frees_concurrency_for_lease_expired_before_dispatch(
    repository: Repository,
) -> None:
    policy = CodexPolicy(
        daily_turn_limit=5,
        concurrent_turn_limit=1,
        model_turn_limits={"luna": 0, "terra": 5, "sol": 0},
        reserved_sol_turns=0,
        turn_timeout_seconds=60,
    )
    now = datetime.now(UTC)
    reservation = reserve_one(repository, worker_id="worker-1", policy=policy, now=now)

    blocked = repository.reserve_codex_turn(
        experiment_id=_enqueue_experiment(repository),
        worker_id="worker-2",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=now,
    )
    assert blocked is None, "the un-dispatched reservation still holds the concurrency slot"

    past_lease = now + timedelta(seconds=61)
    assert repository.reconcile_codex_turns(past_lease) == 1

    with repository.database.transaction() as connection:
        reconciled_row = connection.execute(
            "SELECT status, failure_kind FROM codex_turns WHERE id = %(id)s",
            {"id": reservation.id},
        ).fetchone()
    assert reconciled_row == ("failed", "reservation_lease_expired"), (
        "an un-dispatched reservation whose lease lapses is settled as a clean failure, "
        "never left dangling as 'reserved'"
    )

    freed = repository.reserve_codex_turn(
        experiment_id=_enqueue_experiment(repository),
        worker_id="worker-3",
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        policy=policy,
        now=past_lease,
    )
    assert freed is not None, "reconciliation must free the concurrency slot conservatively"


def test_reconcile_never_un_consumes_a_dispatched_turn(repository: Repository) -> None:
    """Concurrency for a dispatched turn must stay consumed forever, not just its experiment.

    A dispatched turn's true outcome is unknown once its lease lapses without a
    terminal event -- the underlying Codex CLI process might still be running.
    Reconciliation settles the ledger row to `ambiguous` for bookkeeping, but it
    must never treat that settlement as freeing a concurrency slot: doing so
    would let a second turn dispatch while the first might still be in flight,
    exactly the double-dispatch risk this ledger exists to prevent.
    """
    policy = CodexPolicy(
        daily_turn_limit=5,
        concurrent_turn_limit=1,
        model_turn_limits={"luna": 0, "terra": 5, "sol": 0},
        reserved_sol_turns=0,
        turn_timeout_seconds=60,
    )
    now = datetime.now(UTC)
    reservation = reserve_one(repository, worker_id="worker-1", policy=policy, now=now)
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")

    past_lease = now + timedelta(seconds=61)

    assert (
        repository.reserve_codex_turn(
            experiment_id=_enqueue_experiment(repository),
            worker_id="worker-2",
            role=CodexModelRole.TERRA,
            model="gpt-5.6-terra",
            policy=policy,
            now=past_lease,
        )
        is None
    ), "a dispatched turn's expired lease must not free its concurrency slot before reconciliation"

    assert repository.reconcile_codex_turns(past_lease) == 1

    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT status FROM codex_turns WHERE id = %(id)s", {"id": reservation.id}
        ).fetchone()
    assert row == ("ambiguous",)

    assert (
        repository.reserve_codex_turn_for_existing_experiment(reservation.experiment_id) is None
    ), "a dispatched turn that lapses without a terminal event is never re-reservable"

    assert (
        repository.reserve_codex_turn(
            experiment_id=_enqueue_experiment(repository),
            worker_id="worker-3",
            role=CodexModelRole.TERRA,
            model="gpt-5.6-terra",
            policy=policy,
            now=past_lease,
        )
        is None
    ), "settling a dispatched turn to ambiguous must not free its concurrency slot either"


def test_reconcile_is_a_noop_when_nothing_has_expired(repository: Repository) -> None:
    now = datetime.now(UTC)
    reserve_one(repository, now=now)
    assert repository.reconcile_codex_turns(now) == 0


# ---------------------------------------------------------------------------
# Usage status
# ---------------------------------------------------------------------------


def test_codex_usage_status_reports_daily_role_and_token_totals(repository: Repository) -> None:
    now = datetime.now(UTC)
    reservation = reserve_one(repository, role=CodexModelRole.SOL, model="gpt-5.6-sol", now=now)
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.append_codex_turn_event(reservation.id, _turn_started_event())
    repository.append_codex_turn_event(
        reservation.id, _turn_completed_event(_USAGE_PAYLOAD, sequence=1)
    )
    repository.complete_codex_turn(reservation.id, _receipt_for(reservation, usage=_USAGE_PAYLOAD))

    status = repository.codex_usage_status(now)

    assert status.budget_day == now.date()
    assert status.daily_reserved == 1
    assert status.role_reserved["sol"] == 1
    assert status.role_reserved["luna"] == 0
    assert status.role_reserved["terra"] == 0
    assert status.active_leases == 0  # the turn is completed, no longer active
    assert status.usage.input_tokens == 10
    assert status.usage.output_tokens == 4


def test_codex_usage_status_counts_active_leases(repository: Repository) -> None:
    now = datetime.now(UTC)
    reserve_one(repository, now=now)
    status = repository.codex_usage_status(now)
    assert status.active_leases == 1
    assert status.daily_reserved == 1


