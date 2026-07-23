from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from mathloop.billing import validate_database_usd
from mathloop.domain import (
    CandidateClaim,
    ClaimStatus,
    EvidenceLevel,
    Experiment,
    ExperimentStatus,
    MethodVersion,
    Problem,
    ProblemCandidate,
    ProblemStatus,
    Verification,
    advance_claim,
)
from mathloop.evolution import (
    MAX_INT64,
    MethodMetrics,
    MetricsCohort,
    next_completeness_spec,
)
from mathloop.scheduling import MAX_DATABASE_USD
from mathloop.storage.db import Database


class EventConflictError(ValueError):
    """An idempotency key was reused for a different event."""


class ProjectionConflictError(ValueError):
    """An aggregate ID was reused with different immutable projection data."""


class ClaimStateConflictError(ValueError):
    """A verification targeted a claim that is no longer a candidate."""


class InvalidIdentifierError(ValueError):
    """A repository identifier was not an exact UUID."""


class ProblemNotFoundError(LookupError):
    """A canonical problem projection does not exist."""


class ClaimNotFoundError(LookupError):
    """A canonical claim projection does not exist."""


class ClaimSnapshotConflictError(ValueError):
    """A caller claim disagrees with its canonical immutable projection."""


class EvaluationNotFoundError(LookupError):
    """A canonical persisted verification evaluation does not exist."""


class EvaluationContextError(ValueError):
    """An evaluation is not backed by consistent canonical repository state."""


class CompletenessProgressError(ValueError):
    """An experiment cannot advance the durable completeness cursor."""


def _require_uuid(value: object, field_name: str) -> UUID:
    if type(value) is not UUID:
        raise InvalidIdentifierError(f"{field_name} must be an exact UUID")
    return value


def _require_nonempty_string(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def _require_database_usd(value: object, field_name: str) -> Decimal:
    validate_database_usd(value, field_name=field_name, positive=False)  # type: ignore[arg-type]
    amount = value
    assert isinstance(amount, Decimal)
    if amount > MAX_DATABASE_USD:
        raise ValueError(f"{field_name} exceeds NUMERIC(14, 6) capacity")
    return amount


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
            """
            SELECT aggregate_id,
                   aggregate_type = %(aggregate_type)s
                   AND aggregate_id = %(aggregate_id)s
                   AND event_type = %(event_type)s
                   AND payload = %(payload)s AS exact_replay
            FROM events
            WHERE idempotency_key = %(idempotency_key)s
            """,
            {
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "payload": Jsonb(payload),
                "idempotency_key": idempotency_key,
            },
        ).fetchone()
        if existing is None:
            raise RuntimeError("event idempotency conflict did not return an event")
        if not existing[1]:
            raise EventConflictError(
                f"idempotency key {idempotency_key!r} conflicts with an existing event"
            )
        return existing[0], False

    def add_problem(self, problem: Problem, idempotency_key: str) -> UUID:
        with self.database.transaction() as connection:
            return self._store_problem(connection, problem, idempotency_key)

    def get_problem(self, problem_id: UUID) -> Problem:
        canonical_id = _require_uuid(problem_id, "problem_id")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id, source_id, source_uri, source_hash, statement,
                       normalized_statement, domain, features, checker, status,
                       cohort, version, created_at
                FROM problems
                WHERE id = %(id)s
                """,
                {"id": canonical_id},
            ).fetchone()
        if row is None:
            raise ProblemNotFoundError(f"problem {canonical_id} was not found")
        return self._problem_from_row(row)

    def get_claim(self, claim_id: UUID) -> CandidateClaim:
        canonical_id = _require_uuid(claim_id, "claim_id")
        with self.database.transaction() as connection:
            row = self._read_claim(connection, canonical_id)
        if row is None:
            raise ClaimNotFoundError(f"claim {canonical_id} was not found")
        return self._claim_from_row(row)

    def get_evaluation_id(
        self, claim_id: UUID, verifier: str, verifier_version: str
    ) -> UUID:
        canonical_claim_id = _require_uuid(claim_id, "claim_id")
        canonical_verifier = _require_nonempty_string(verifier, "verifier")
        canonical_version = _require_nonempty_string(verifier_version, "verifier_version")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id
                FROM evaluations
                WHERE claim_id = %(claim_id)s AND verifier = %(verifier)s
                  AND verifier_version = %(verifier_version)s
                """,
                {
                    "claim_id": canonical_claim_id,
                    "verifier": canonical_verifier,
                    "verifier_version": canonical_version,
                },
            ).fetchone()
        if row is None:
            raise EvaluationNotFoundError(
                "canonical evaluation was not found for the claim and verifier version"
            )
        return cast(UUID, row[0])

    @staticmethod
    def _problem_from_row(row: tuple[Any, ...]) -> Problem:
        return Problem(
            id=row[0],
            source_id=row[1],
            source_uri=row[2],
            source_hash=row[3],
            statement=row[4],
            normalized_statement=row[5],
            domain=row[6],
            features=row[7],
            checker=row[8],
            status=row[9],
            cohort=row[10],
            version=row[11],
            created_at=row[12],
        )

    @staticmethod
    def _claim_from_row(row: tuple[Any, ...]) -> CandidateClaim:
        return CandidateClaim(
            id=row[0],
            problem_id=row[1],
            experiment_id=row[2],
            claim_type=row[3],
            statement=row[4],
            witness=row[5],
            status=row[6],
            evidence_level=row[7],
            created_at=row[8],
        )

    @staticmethod
    def _read_claim(
        connection: Connection[tuple[Any, ...]],
        claim_id: UUID,
        *,
        for_update: bool = False,
    ) -> tuple[Any, ...] | None:
        lock_clause = " FOR UPDATE" if for_update else ""
        return connection.execute(
            """
            SELECT id, problem_id, experiment_id, claim_type, statement, witness,
                   status, evidence_level, created_at
            FROM claims
            WHERE id = %(id)s
            """
            + lock_clause,
            {"id": claim_id},
        ).fetchone()

    def ingest_problem_snapshot(
        self,
        candidate: ProblemCandidate,
        *,
        problem_id: UUID,
        cohort: str,
        created_at: datetime,
    ) -> UUID:
        """Idempotently persist one source snapshot and its next source version."""
        with self.database.transaction() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%(source_id)s, 0))",
                {"source_id": candidate.source_id},
            )
            existing = connection.execute(
                "SELECT id FROM problems WHERE source_hash = %(source_hash)s",
                {"source_hash": candidate.source_hash},
            ).fetchone()
            if existing is not None:
                return cast(UUID, existing[0])
            allocation = connection.execute(
                """
                INSERT INTO problem_source_versions (source_id, next_version)
                VALUES (%(source_id)s, 2)
                ON CONFLICT (source_id) DO UPDATE
                SET next_version = problem_source_versions.next_version + 1
                RETURNING next_version - 1
                """,
                {"source_id": candidate.source_id},
            ).fetchone()
            if allocation is None:
                raise RuntimeError("source version allocation did not return a version")
            problem = Problem(
                id=problem_id,
                **candidate.model_dump(exclude={"expected"}),
                status=ProblemStatus.ELIGIBLE,
                cohort=cohort,
                version=int(allocation[0]),
                created_at=created_at,
            )
            return self._store_problem(
                connection,
                problem,
                idempotency_key=f"problem:{candidate.source_hash}",
            )

    def _store_problem(
        self,
        connection: Connection[tuple[Any, ...]],
        problem: Problem,
        idempotency_key: str,
    ) -> UUID:
        payload = problem.model_dump(mode="json")
        stored_id, appended = self._append_event(
            connection,
            aggregate_type="problem",
            aggregate_id=problem.id,
            event_type="problem.discovered",
            payload=payload,
            idempotency_key=idempotency_key,
        )
        if appended:
            projection = connection.execute(
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
                ON CONFLICT (id) DO UPDATE SET id = EXCLUDED.id
                WHERE (
                    problems.source_id, problems.source_uri, problems.source_hash,
                    problems.statement, problems.normalized_statement, problems.domain,
                    problems.features, problems.checker, problems.status, problems.cohort,
                    problems.version, problems.created_at
                ) IS NOT DISTINCT FROM (
                    EXCLUDED.source_id, EXCLUDED.source_uri, EXCLUDED.source_hash,
                    EXCLUDED.statement, EXCLUDED.normalized_statement, EXCLUDED.domain,
                    EXCLUDED.features, EXCLUDED.checker, EXCLUDED.status, EXCLUDED.cohort,
                    EXCLUDED.version, EXCLUDED.created_at
                )
                RETURNING id
                """,
                {
                    **payload,
                    "features": Jsonb(payload["features"]),
                    "checker": Jsonb(payload["checker"]),
                },
            ).fetchone()
            if projection is None:
                raise ProjectionConflictError(
                    f"problem {problem.id} has conflicting immutable projection data"
                )
            connection.execute(
                """
                INSERT INTO problem_source_versions (source_id, next_version)
                VALUES (%(source_id)s, %(next_version)s)
                ON CONFLICT (source_id) DO UPDATE
                SET next_version = GREATEST(
                    problem_source_versions.next_version, EXCLUDED.next_version
                )
                """,
                {"source_id": problem.source_id, "next_version": problem.version + 1},
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
                projection = connection.execute(
                    """
                    INSERT INTO methods (
                        id, family, version, spec, parent_id, status, created_at
                    ) VALUES (
                        %(id)s, %(family)s, %(version)s, %(spec)s, %(parent_id)s,
                        %(status)s, %(created_at)s
                    )
                    ON CONFLICT (id) DO UPDATE SET id = EXCLUDED.id
                    WHERE (
                        methods.family, methods.version, methods.spec, methods.parent_id,
                        methods.status, methods.created_at
                    ) IS NOT DISTINCT FROM (
                        EXCLUDED.family, EXCLUDED.version, EXCLUDED.spec, EXCLUDED.parent_id,
                        EXCLUDED.status, EXCLUDED.created_at
                    )
                    RETURNING id
                    """,
                    {**payload, "spec": Jsonb(payload["spec"])},
                ).fetchone()
                if projection is None:
                    raise ProjectionConflictError(
                        f"method {method.id} has conflicting immutable projection data"
                    )
        return stored_id

    def record_method_outcome(self, evaluation_id: UUID) -> MethodMetrics:
        canonical_evaluation_id = _require_uuid(evaluation_id, "evaluation_id")
        with self.database.transaction() as connection:
            context = connection.execute(
                """
                SELECT v.accepted, v.independent, v.claim_id,
                       c.status, c.problem_id, c.experiment_id,
                       e.problem_id, e.method_id, e.status, e.cost_usd,
                       p.domain, p.cohort, m.id
                FROM evaluations AS v
                LEFT JOIN claims AS c ON c.id = v.claim_id
                LEFT JOIN experiments AS e ON e.id = c.experiment_id
                LEFT JOIN problems AS p ON p.id = c.problem_id
                LEFT JOIN methods AS m ON m.id = e.method_id
                WHERE v.id = %(evaluation_id)s
                """,
                {"evaluation_id": canonical_evaluation_id},
            ).fetchone()
            if context is None:
                raise EvaluationNotFoundError(
                    f"evaluation {canonical_evaluation_id} was not found"
                )
            if context[1] is not True:
                raise EvaluationContextError("routing scores require independent verification")
            if any(value is None for value in context[2:13]):
                raise EvaluationContextError(
                    "evaluation is missing its canonical claim, experiment, problem, or method"
                )
            accepted = bool(context[0])
            claim_status = str(context[3])
            claim_problem_id = cast(UUID, context[4])
            experiment_id = cast(UUID, context[5])
            experiment_problem_id = cast(UUID, context[6])
            method_id = cast(UUID, context[7])
            experiment_status = str(context[8])
            cost = _require_database_usd(context[9], "cost_usd")
            domain = _require_nonempty_string(context[10], "domain")
            try:
                cohort = MetricsCohort(context[11])
            except (TypeError, ValueError) as error:
                raise EvaluationContextError("evaluation problem has an invalid cohort") from error
            if claim_problem_id != experiment_problem_id:
                raise EvaluationContextError("claim and experiment problem IDs do not match")
            if experiment_status != ExperimentStatus.SUCCEEDED.value:
                raise EvaluationContextError("evaluation experiment is not succeeded")
            accepted_statuses = {
                ClaimStatus.MACHINE_VERIFIED.value,
                ClaimStatus.NOVELTY_CHECKED.value,
                ClaimStatus.HUMAN_REVIEWED.value,
            }
            if accepted and claim_status not in accepted_statuses:
                raise EvaluationContextError("accepted evaluation has no verified claim projection")
            if not accepted and claim_status != ClaimStatus.REJECTED.value:
                raise EvaluationContextError("rejected evaluation has no rejected claim projection")
            verified_increment = int(accepted)
            false_positive_increment = int(not accepted)
            payload: dict[str, object] = {
                "evaluation_id": str(canonical_evaluation_id),
                "claim_id": str(context[2]),
                "experiment_id": str(experiment_id),
                "domain": domain,
                "method_id": str(method_id),
                "cohort": cohort.value,
                "accepted": accepted,
                "cost_usd": format(cost, "f"),
            }
            _, appended = self._append_event(
                connection,
                aggregate_type="method",
                aggregate_id=method_id,
                event_type="method.outcome_recorded",
                payload=payload,
                idempotency_key=f"method:outcome:evaluation:{canonical_evaluation_id}",
            )
            if appended:
                row = connection.execute(
                    """
                    INSERT INTO method_scores (
                        domain, method_id, cohort, trials, reward,
                        false_positives, cost_usd
                    ) VALUES (
                        %(domain)s, %(method_id)s, %(cohort)s, 1,
                        %(reward)s, %(false_positives)s, %(cost_usd)s
                    )
                    ON CONFLICT (domain, method_id, cohort) DO UPDATE
                    SET trials = method_scores.trials + 1,
                        reward = method_scores.reward + EXCLUDED.reward,
                        false_positives = (
                            method_scores.false_positives + EXCLUDED.false_positives
                        ),
                        cost_usd = method_scores.cost_usd + EXCLUDED.cost_usd
                    RETURNING trials, reward, false_positives, cost_usd
                    """,
                    {
                        "domain": domain,
                        "method_id": method_id,
                        "cohort": cohort.value,
                        "reward": verified_increment,
                        "false_positives": false_positive_increment,
                        "cost_usd": cost,
                    },
                ).fetchone()
            else:
                row = self._read_method_metrics(connection, domain, method_id, cohort)
        if row is None:
            raise RuntimeError("persisted method outcome has no score projection")
        return self._method_metrics_from_row(cohort, row)

    def get_method_metrics(
        self, domain: str, method_id: UUID, cohort: MetricsCohort
    ) -> MethodMetrics:
        canonical_domain = _require_nonempty_string(domain, "domain")
        canonical_method_id = _require_uuid(method_id, "method_id")
        if type(cohort) is not MetricsCohort:
            raise TypeError("cohort must be a MetricsCohort")
        with self.database.transaction() as connection:
            row = self._read_method_metrics(
                connection, canonical_domain, canonical_method_id, cohort
            )
        if row is None:
            return MethodMetrics(
                cohort=cohort,
                trials=0,
                verified=0,
                false_positives=0,
                cost_usd=Decimal("0"),
            )
        return self._method_metrics_from_row(cohort, row)

    @staticmethod
    def _read_method_metrics(
        connection: Connection[tuple[Any, ...]],
        domain: str,
        method_id: UUID,
        cohort: MetricsCohort,
    ) -> tuple[Any, ...] | None:
        return connection.execute(
            """
            SELECT trials, reward, false_positives, cost_usd
            FROM method_scores
            WHERE domain = %(domain)s AND method_id = %(method_id)s
              AND cohort = %(cohort)s
            """,
            {"domain": domain, "method_id": method_id, "cohort": cohort.value},
        ).fetchone()

    @staticmethod
    def _method_metrics_from_row(cohort: MetricsCohort, row: tuple[Any, ...]) -> MethodMetrics:
        return MethodMetrics(
            cohort=cohort,
            trials=int(row[0]),
            verified=int(row[1]),
            false_positives=int(row[2]),
            cost_usd=Decimal(row[3]),
        )

    def record_completeness_progress(self, experiment_id: UUID) -> int:
        canonical_experiment_id = _require_uuid(experiment_id, "experiment_id")
        with self.database.transaction() as connection:
            context = connection.execute(
                """
                SELECT e.problem_id, e.method_id, e.lane, e.config, e.status, e.result,
                       p.checker, m.family
                FROM experiments AS e
                LEFT JOIN problems AS p ON p.id = e.problem_id
                LEFT JOIN methods AS m ON m.id = e.method_id
                WHERE e.id = %(experiment_id)s
                """,
                {"experiment_id": canonical_experiment_id},
            ).fetchone()
            if context is None:
                raise CompletenessProgressError(
                    f"experiment {canonical_experiment_id} was not found"
                )
            if context[6] is None or context[7] is None:
                raise CompletenessProgressError(
                    "completeness experiment lacks a canonical problem or method"
                )
            problem_id = cast(UUID, context[0])
            method_family = _require_nonempty_string(context[7], "method_family")
            if context[2] != "completeness":
                raise CompletenessProgressError("experiment is not in the completeness lane")
            if context[4] != ExperimentStatus.SUCCEEDED.value:
                raise CompletenessProgressError("completeness experiment is not succeeded")
            result = context[5]
            if not isinstance(result, dict) or result.get("status") != "bounded_no_counterexample":
                raise CompletenessProgressError(
                    "completeness experiment did not finish the full interval"
                )
            config = context[3]
            if not isinstance(config, dict) or set(config) != {"start", "stop", "order"}:
                raise CompletenessProgressError("completeness experiment has an invalid config")
            start = config["start"]
            stop = config["stop"]
            if type(start) is not int or type(stop) is not int:
                raise CompletenessProgressError("completeness interval bounds must be integers")
            if config["order"] != "ascending":
                raise CompletenessProgressError("completeness search order must be ascending")
            if start >= stop or stop > MAX_INT64:
                raise CompletenessProgressError("completeness interval bounds are invalid")
            checker = context[6]
            declared_start = checker.get("start") if isinstance(checker, dict) else None
            if type(declared_start) is not int:
                raise CompletenessProgressError("problem has no exact declared integer start")
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%(key)s, 0))",
                {"key": f"{problem_id}:{method_family}"},
            )
            progress = connection.execute(
                """
                SELECT completed_upper_bound
                FROM completeness_progress
                WHERE problem_id = %(problem_id)s AND method_family = %(method_family)s
                FOR UPDATE
                """,
                {"problem_id": problem_id, "method_family": method_family},
            ).fetchone()
            current = int(progress[0]) if progress is not None else declared_start
            payload: dict[str, object] = {
                "experiment_id": str(canonical_experiment_id),
                "problem_id": str(problem_id),
                "method_id": str(context[1]),
                "method_family": method_family,
                "start": start,
                "stop": stop,
            }
            _, appended = self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=canonical_experiment_id,
                event_type="completeness.progress_recorded",
                payload=payload,
                idempotency_key=f"completeness:experiment:{canonical_experiment_id}",
            )
            if not appended:
                if progress is None:
                    raise RuntimeError("persisted completeness event has no progress projection")
                return current
            if start != current:
                raise CompletenessProgressError(
                    f"completeness interval is not contiguous: expected start {current}"
                )
            row = connection.execute(
                """
                INSERT INTO completeness_progress (
                    problem_id, method_family, completed_upper_bound
                ) VALUES (
                    %(problem_id)s, %(method_family)s, %(stop)s
                )
                ON CONFLICT (problem_id, method_family) DO UPDATE
                SET completed_upper_bound = EXCLUDED.completed_upper_bound,
                    updated_at = now()
                WHERE completeness_progress.completed_upper_bound = %(start)s
                RETURNING completed_upper_bound
                """,
                {
                    "problem_id": problem_id,
                    "method_family": method_family,
                    "start": start,
                    "stop": stop,
                },
            ).fetchone()
            if row is None:
                raise CompletenessProgressError("completeness cursor changed concurrently")
            return int(row[0])

    def get_completeness_progress(self, problem_id: UUID, method_family: str) -> int:
        canonical_problem_id = _require_uuid(problem_id, "problem_id")
        canonical_family = _require_nonempty_string(method_family, "method_family")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT cp.completed_upper_bound, p.checker
                FROM problems AS p
                LEFT JOIN completeness_progress AS cp
                  ON cp.problem_id = p.id AND cp.method_family = %(method_family)s
                WHERE p.id = %(problem_id)s
                """,
                {"problem_id": canonical_problem_id, "method_family": canonical_family},
            ).fetchone()
        if row is None:
            raise ProblemNotFoundError(f"problem {canonical_problem_id} was not found")
        if row[0] is not None:
            return int(row[0])
        checker = row[1]
        declared_start = checker.get("start") if isinstance(checker, dict) else None
        if type(declared_start) is not int:
            raise CompletenessProgressError("problem has no exact declared integer start")
        return declared_start

    def get_next_completeness_spec(
        self,
        problem_id: UUID,
        method_family: str,
        parent_spec: Mapping[str, object],
    ) -> dict[str, int | str]:
        current = self.get_completeness_progress(problem_id, method_family)
        next_completeness_spec(parent_spec)
        base_stop = max(current, cast(int, parent_spec["stop"]))
        grown = next_completeness_spec({"stop": base_stop, "order": "ascending"})
        return {"start": current, "stop": grown["stop"], "order": "ascending"}

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
                projection = connection.execute(
                    """
                    INSERT INTO experiments (
                        id, problem_id, method_id, lane, config, seed, status, created_at,
                        updated_at
                    ) VALUES (
                        %(id)s, %(problem_id)s, %(method_id)s, %(lane)s, %(config)s,
                        %(seed)s, %(status)s, %(created_at)s, %(created_at)s
                    )
                    ON CONFLICT (id) DO UPDATE SET id = EXCLUDED.id
                    WHERE (
                        experiments.problem_id, experiments.method_id, experiments.lane,
                        experiments.config, experiments.seed, experiments.created_at
                    ) IS NOT DISTINCT FROM (
                        EXCLUDED.problem_id, EXCLUDED.method_id, EXCLUDED.lane,
                        EXCLUDED.config, EXCLUDED.seed, EXCLUDED.created_at
                    )
                    RETURNING id
                    """,
                    {**payload, "config": Jsonb(payload["config"])},
                ).fetchone()
                if projection is None:
                    raise ProjectionConflictError(
                        f"experiment {experiment.id} has conflicting immutable projection data"
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
        self._validate_lease(now, lease_seconds)
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
        self._validate_lease(now, lease_seconds)
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
        self,
        experiment_id: UUID,
        worker: str,
        result: dict[str, object],
        cost_usd: float,
        *,
        now: datetime | None = None,
    ) -> None:
        cost = Decimal(str(cost_usd))
        if not cost.is_finite() or cost < 0:
            raise ValueError("experiment cost must be a finite non-negative amount")
        completed_at = datetime.now(UTC) if now is None else now
        self._validate_lease_timestamp(completed_at)
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
                    lease_owner = NULL, lease_expires_at = NULL, updated_at = %(now)s
                WHERE id = %(id)s AND status = 'leased' AND lease_owner = %(worker)s
                  AND lease_expires_at > %(now)s
                RETURNING id
                """,
                {
                    "id": experiment_id,
                    "worker": worker,
                    "result": Jsonb(result),
                    "cost_usd": cost,
                    "now": completed_at,
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

    def record_verification(
        self, claim: CandidateClaim, verification: Verification
    ) -> CandidateClaim:
        claim_id = _require_uuid(claim.id, "claim_id")
        verification_payload = verification.model_dump(mode="json")
        with self.database.transaction() as connection:
            claim_row = self._read_claim(connection, claim_id, for_update=True)
            if claim_row is None:
                raise ClaimNotFoundError(f"claim {claim_id} was not found")
            canonical_claim = self._claim_from_row(claim_row)
            if not self._same_immutable_claim_snapshot(claim, canonical_claim):
                raise ClaimSnapshotConflictError(
                    f"claim {claim_id} conflicts with its canonical snapshot"
                )
            if claim.status is not ClaimStatus.CANDIDATE:
                raise ClaimStateConflictError(
                    f"claim {claim_id} caller snapshot is not in candidate state"
                )
            if not verification.independent:
                raise ValueError("claim promotion requires an independent verifier")
            _, appended = self._append_event(
                connection,
                aggregate_type="claim",
                aggregate_id=claim_id,
                event_type="claim.verified",
                payload=verification_payload,
                idempotency_key=(
                    f"verification:{claim_id}:{verification.verifier}:{verification.verifier_version}"
                ),
            )
            if not appended:
                if not self._is_expected_verified_projection(canonical_claim, verification):
                    raise ClaimStateConflictError(
                        f"claim {claim_id} does not match its replayed verification"
                    )
                return canonical_claim
            if canonical_claim.status is not ClaimStatus.CANDIDATE:
                raise ClaimStateConflictError(
                    f"claim {claim_id} is not in candidate state"
                )
            updated_claim = advance_claim(canonical_claim, verification)
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
                    "claim_id": claim_id,
                    "details": Jsonb(verification_payload["details"]),
                },
            )
            updated_row = connection.execute(
                """
                UPDATE claims
                SET status = %(status)s, evidence_level = %(evidence_level)s
                WHERE id = %(id)s AND status = 'candidate'
                RETURNING id, problem_id, experiment_id, claim_type, statement, witness,
                          status, evidence_level, created_at
                """,
                {
                    "id": claim_id,
                    "status": updated_claim.status.value,
                    "evidence_level": updated_claim.evidence_level.value,
                },
            ).fetchone()
            if updated_row is None:
                raise ClaimStateConflictError(
                    f"claim {claim_id} is not in candidate state"
                )
            return self._claim_from_row(updated_row)

    @staticmethod
    def _same_immutable_claim_snapshot(
        supplied: CandidateClaim, canonical: CandidateClaim
    ) -> bool:
        return (
            supplied.id,
            supplied.problem_id,
            supplied.experiment_id,
            supplied.claim_type,
            supplied.statement,
            supplied.witness,
            supplied.created_at,
        ) == (
            canonical.id,
            canonical.problem_id,
            canonical.experiment_id,
            canonical.claim_type,
            canonical.statement,
            canonical.witness,
            canonical.created_at,
        )

    @staticmethod
    def _is_expected_verified_projection(
        canonical: CandidateClaim, verification: Verification
    ) -> bool:
        if not verification.accepted:
            return canonical.status is ClaimStatus.REJECTED
        return canonical.status in {
            ClaimStatus.MACHINE_VERIFIED,
            ClaimStatus.NOVELTY_CHECKED,
            ClaimStatus.HUMAN_REVIEWED,
        } and canonical.evidence_level in {
            EvidenceLevel.REPRODUCIBLE_WITNESS,
            EvidenceLevel.FORMALLY_VERIFIED,
        }

    def count_events(self, event_type: str) -> int:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT count(*) FROM events WHERE event_type = %(event_type)s",
                {"event_type": event_type},
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def find_problem_by_source_hash(self, source_hash: str) -> UUID | None:
        """Return the immutable problem ID for an already ingested source snapshot."""
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT id FROM problems WHERE source_hash = %(source_hash)s",
                {"source_hash": source_hash},
            ).fetchone()
        return row[0] if row is not None else None

    def next_problem_version(self, source_id: str) -> int:
        """Atomically allocate a source version; abandoned allocations intentionally leave gaps."""
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                INSERT INTO problem_source_versions (source_id, next_version)
                VALUES (%(source_id)s, 2)
                ON CONFLICT (source_id) DO UPDATE
                SET next_version = problem_source_versions.next_version + 1
                RETURNING next_version - 1
                """,
                {"source_id": source_id},
            ).fetchone()
        return int(row[0]) if row is not None else 1

    def reserve_daily_budget(
        self, experiment_id: UUID, amount_usd: float, daily_limit_usd: float
    ) -> bool:
        amount = Decimal(str(amount_usd))
        limit = Decimal(str(daily_limit_usd))
        if not amount.is_finite() or not limit.is_finite() or amount < 0 or limit < 0:
            raise ValueError("budget amounts must be finite and non-negative")
        event_payload: dict[str, object] = {
            "amount_usd": amount_usd,
            "daily_limit_usd": daily_limit_usd,
        }
        with self.database.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(CURRENT_DATE::text))")
            existing = connection.execute(
                "SELECT experiment_id FROM budget_reservations WHERE experiment_id = %(id)s",
                {"id": experiment_id},
            ).fetchone()
            if existing is not None:
                self._append_event(
                    connection,
                    aggregate_type="experiment",
                    aggregate_id=experiment_id,
                    event_type="budget.reserved",
                    payload=event_payload,
                    idempotency_key=f"budget:reserve:{experiment_id}",
                )
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
                payload=event_payload,
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
        if not amount.is_finite() or amount < 0:
            raise ValueError("budget amounts must be finite and non-negative")
        with self.database.transaction() as connection:
            reservation = connection.execute(
                """
                SELECT reserved_usd, budget_day
                FROM budget_reservations
                WHERE experiment_id = %(id)s
                """,
                {"id": experiment_id},
            ).fetchone()
            if reservation is None:
                raise ValueError("experiment has no budget reservation")
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%(budget_day)s::text))",
                {"budget_day": reservation[1]},
            )
            reservation = connection.execute(
                """
                SELECT reserved_usd, budget_day
                FROM budget_reservations
                WHERE experiment_id = %(id)s
                FOR UPDATE
                """,
                {"id": experiment_id},
            ).fetchone()
            if reservation is None:
                raise ValueError("experiment has no budget reservation")
            if amount > reservation[0]:
                raise ValueError("actual cost exceeds the reserved maximum")
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

    @staticmethod
    def _validate_lease(now: datetime, lease_seconds: int) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease duration must be positive")
        Repository._validate_lease_timestamp(now)

    @staticmethod
    def _validate_lease_timestamp(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("lease timestamp must be timezone-aware")
