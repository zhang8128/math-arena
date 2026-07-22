from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from mathloop.domain import (
    CandidateClaim,
    Experiment,
    ExperimentStatus,
    MethodVersion,
    Problem,
    Verification,
    advance_claim,
)
from mathloop.storage.db import Database


class Repository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def _append_event(
        self,
        connection: Connection[tuple[Any, ...]],
        *,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> tuple[UUID, bool]:
        row = connection.execute(
            """
            INSERT INTO events (
                aggregate_type, aggregate_id, event_type, payload, idempotency_key
            ) VALUES (
                %(aggregate_type)s, %(aggregate_id)s, %(event_type)s, %(payload)s,
                %(idempotency_key)s
            )
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING aggregate_id
            """,
            {
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "payload": Jsonb(payload),
                "idempotency_key": idempotency_key,
            },
        ).fetchone()
        if row is not None:
            return row[0], True
        existing = connection.execute(
            "SELECT aggregate_id FROM events WHERE idempotency_key = %(idempotency_key)s",
            {"idempotency_key": idempotency_key},
        ).fetchone()
        if existing is None:
            raise RuntimeError("event idempotency conflict did not return an event")
        return existing[0], False

    def add_problem(self, problem: Problem, idempotency_key: str) -> UUID:
        payload = problem.model_dump(mode="json")
        with self.database.transaction() as connection:
            stored_id, appended = self._append_event(
                connection,
                aggregate_type="problem",
                aggregate_id=problem.id,
                event_type="problem.discovered",
                payload=payload,
                idempotency_key=idempotency_key,
            )
            if appended:
                connection.execute(
                    """
                    INSERT INTO problems (
                        id, source_id, source_uri, source_hash, statement,
                        normalized_statement, domain, features, checker, status,
                        cohort, version, created_at
                    ) VALUES (
                        %(id)s, %(source_id)s, %(source_uri)s, %(source_hash)s,
                        %(statement)s, %(normalized_statement)s, %(domain)s,
                        %(features)s, %(checker)s, %(status)s, %(cohort)s,
                        %(version)s, %(created_at)s
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    {
                        **payload,
                        "features": Jsonb(payload["features"]),
                        "checker": Jsonb(payload["checker"]),
                    },
                )
        return stored_id

    def register_method(self, method: MethodVersion, idempotency_key: str) -> UUID:
        payload = method.model_dump(mode="json")
        with self.database.transaction() as connection:
            stored_id, appended = self._append_event(
                connection,
                aggregate_type="method",
                aggregate_id=method.id,
                event_type="method.registered",
                payload=payload,
                idempotency_key=idempotency_key,
            )
            if appended:
                connection.execute(
                    """
                    INSERT INTO methods (
                        id, family, version, spec, parent_id, status, created_at
                    ) VALUES (
                        %(id)s, %(family)s, %(version)s, %(spec)s, %(parent_id)s,
                        %(status)s, %(created_at)s
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    {**payload, "spec": Jsonb(payload["spec"])},
                )
        return stored_id

    def enqueue(self, experiment: Experiment, idempotency_key: str) -> UUID:
        payload = experiment.model_dump(mode="json")
        with self.database.transaction() as connection:
            stored_id, appended = self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=experiment.id,
                event_type="experiment.enqueued",
                payload=payload,
                idempotency_key=idempotency_key,
            )
            if appended:
                connection.execute(
                    """
                    INSERT INTO experiments (
                        id, problem_id, method_id, lane, config, seed, status, created_at,
                        updated_at
                    ) VALUES (
                        %(id)s, %(problem_id)s, %(method_id)s, %(lane)s, %(config)s,
                        %(seed)s, %(status)s, %(created_at)s, %(created_at)s
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    {**payload, "config": Jsonb(payload["config"])},
                )
        return stored_id

    def enqueue_raw(
        self,
        problem_id: UUID,
        method_id: UUID,
        lane: str,
        config: dict[str, object],
        seed: int,
    ) -> UUID:
        experiment = Experiment(
            id=uuid4(),
            problem_id=problem_id,
            method_id=method_id,
            lane=lane,
            config=config,
            seed=seed,
            status=ExperimentStatus.QUEUED,
            created_at=datetime.now(UTC),
        )
        return self.enqueue(experiment, idempotency_key=f"experiment:{experiment.id}")

    def claim_next(self, worker: str, now: datetime, lease_seconds: int) -> Experiment | None:
        expires = now + timedelta(seconds=lease_seconds)
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                WITH candidate AS (
                    SELECT id
                    FROM experiments
                    WHERE status = 'queued'
                       OR (status = 'leased' AND lease_expires_at < %(now)s)
                    ORDER BY created_at, id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE experiments AS e
                SET status = 'leased', lease_owner = %(worker)s,
                    lease_expires_at = %(expires)s, attempt = attempt + 1, updated_at = %(now)s
                FROM candidate
                WHERE e.id = candidate.id
                RETURNING e.*;
                """,
                {"worker": worker, "now": now, "expires": expires},
            ).fetchone()
            if row is None:
                return None
            experiment = Experiment(
                id=row[0],
                problem_id=row[1],
                method_id=row[2],
                lane=row[3],
                config=row[4],
                seed=row[5],
                status=row[6],
                created_at=row[12],
            )
            self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=experiment.id,
                event_type="experiment.leased",
                payload={
                    "worker": worker,
                    "lease_expires_at": expires.isoformat(),
                    "attempt": row[9],
                },
                idempotency_key=f"experiment:lease:{experiment.id}:{row[9]}",
            )
            return experiment

    def heartbeat(
        self, experiment_id: UUID, worker: str, now: datetime, lease_seconds: int
    ) -> bool:
        expires = now + timedelta(seconds=lease_seconds)
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                UPDATE experiments
                SET lease_expires_at = %(expires)s, updated_at = %(now)s
                WHERE id = %(id)s AND status = 'leased' AND lease_owner = %(worker)s
                  AND lease_expires_at > %(now)s
                RETURNING attempt
                """,
                {"id": experiment_id, "worker": worker, "now": now, "expires": expires},
            ).fetchone()
            if row is None:
                return False
            self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=experiment_id,
                event_type="experiment.heartbeat",
                payload={"worker": worker, "lease_expires_at": expires.isoformat()},
                idempotency_key=f"experiment:heartbeat:{experiment_id}:{now.isoformat()}",
            )
            return True

    def complete(
        self, experiment_id: UUID, worker: str, result: dict[str, object], cost_usd: float
    ) -> None:
        with self.database.transaction() as connection:
            _, appended = self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=experiment_id,
                event_type="experiment.completed",
                payload={"worker": worker, "result": result, "cost_usd": cost_usd},
                idempotency_key=f"experiment:complete:{experiment_id}",
            )
            if not appended:
                return
            row = connection.execute(
                """
                UPDATE experiments
                SET status = 'succeeded', result = %(result)s, cost_usd = %(cost_usd)s,
                    lease_owner = NULL, lease_expires_at = NULL, updated_at = now()
                WHERE id = %(id)s AND status = 'leased' AND lease_owner = %(worker)s
                  AND lease_expires_at > now()
                RETURNING id
                """,
                {
                    "id": experiment_id,
                    "worker": worker,
                    "result": Jsonb(result),
                    "cost_usd": Decimal(str(cost_usd)),
                },
            ).fetchone()
            if row is None:
                raise ValueError("experiment is not leased by this worker")

    def save_candidate(self, claim: CandidateClaim) -> None:
        payload = claim.model_dump(mode="json")
        with self.database.transaction() as connection:
            _, appended = self._append_event(
                connection,
                aggregate_type="claim",
                aggregate_id=claim.id,
                event_type="claim.candidate_saved",
                payload=payload,
                idempotency_key=f"claim:{claim.id}",
            )
            if appended:
                connection.execute(
                    """
                    INSERT INTO claims (
                        id, problem_id, experiment_id, claim_type, statement, witness,
                        status, evidence_level, created_at
                    ) VALUES (
                        %(id)s, %(problem_id)s, %(experiment_id)s, %(claim_type)s,
                        %(statement)s, %(witness)s, %(status)s, %(evidence_level)s,
                        %(created_at)s
                    )
                    ON CONFLICT (id) DO NOTHING
                    """,
                    {
                        **payload,
                        "witness": (
                            Jsonb(payload["witness"])
                            if payload["witness"] is not None
                            else None
                        ),
                    },
                )

    def record_verification(self, claim: CandidateClaim, verification: Verification) -> None:
        updated_claim = advance_claim(claim, verification)
        verification_payload = verification.model_dump(mode="json")
        with self.database.transaction() as connection:
            _, appended = self._append_event(
                connection,
                aggregate_type="claim",
                aggregate_id=claim.id,
                event_type="claim.verified",
                payload=verification_payload,
                idempotency_key=(
                    f"verification:{claim.id}:{verification.verifier}:{verification.verifier_version}"
                ),
            )
            if appended:
                connection.execute(
                    """
                    INSERT INTO evaluations (
                        claim_id, verifier, verifier_version, accepted, independent, details
                    ) VALUES (
                        %(claim_id)s, %(verifier)s, %(verifier_version)s, %(accepted)s,
                        %(independent)s, %(details)s
                    )
                    """,
                    {
                        **verification_payload,
                        "claim_id": claim.id,
                        "details": Jsonb(verification_payload["details"]),
                    },
                )
                connection.execute(
                    """
                    UPDATE claims
                    SET status = %(status)s, evidence_level = %(evidence_level)s
                    WHERE id = %(id)s
                    """,
                    {
                        "id": claim.id,
                        "status": updated_claim.status.value,
                        "evidence_level": updated_claim.evidence_level.value,
                    },
                )

    def count_events(self, event_type: str) -> int:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT count(*) FROM events WHERE event_type = %(event_type)s",
                {"event_type": event_type},
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def next_problem_version(self, source_id: str) -> int:
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1
                FROM problems
                WHERE source_id = %(source_id)s
                """,
                {"source_id": source_id},
            ).fetchone()
        return int(row[0]) if row is not None else 1

    def reserve_daily_budget(
        self, experiment_id: UUID, amount_usd: float, daily_limit_usd: float
    ) -> bool:
        amount = Decimal(str(amount_usd))
        limit = Decimal(str(daily_limit_usd))
        if amount < 0 or limit < 0:
            raise ValueError("budget amounts must be non-negative")
        with self.database.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(CURRENT_DATE::text))")
            existing = connection.execute(
                "SELECT experiment_id FROM budget_reservations WHERE experiment_id = %(id)s",
                {"id": experiment_id},
            ).fetchone()
            if existing is not None:
                return True
            row = connection.execute(
                """
                SELECT COALESCE(
                    SUM(CASE WHEN settled_usd IS NULL THEN reserved_usd ELSE settled_usd END), 0
                )
                FROM budget_reservations
                WHERE budget_day = CURRENT_DATE
                """
            ).fetchone()
            total = Decimal(str(row[0])) if row is not None else Decimal("0")
            if total + amount > limit:
                return False
            self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=experiment_id,
                event_type="budget.reserved",
                payload={"amount_usd": amount_usd, "daily_limit_usd": daily_limit_usd},
                idempotency_key=f"budget:reserve:{experiment_id}",
            )
            connection.execute(
                """
                INSERT INTO budget_reservations (experiment_id, reserved_usd)
                VALUES (%(id)s, %(amount)s)
                """,
                {"id": experiment_id, "amount": amount},
            )
            return True

    def settle_budget(self, experiment_id: UUID, actual_usd: float) -> None:
        amount = Decimal(str(actual_usd))
        if amount < 0:
            raise ValueError("budget amounts must be non-negative")
        with self.database.transaction() as connection:
            _, appended = self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=experiment_id,
                event_type="budget.settled",
                payload={"actual_usd": actual_usd},
                idempotency_key=f"budget:settle:{experiment_id}",
            )
            if not appended:
                return
            row = connection.execute(
                """
                UPDATE budget_reservations
                SET settled_usd = %(amount)s
                WHERE experiment_id = %(id)s
                RETURNING experiment_id
                """,
                {"id": experiment_id, "amount": amount},
            ).fetchone()
            if row is None:
                raise ValueError("experiment has no budget reservation")
