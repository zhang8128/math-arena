import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

from mathloop.billing import MAX_DATABASE_USD, validate_database_usd
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
from mathloop.provenance import validate_provenance, verifier_provenance
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


class MethodNotFoundError(LookupError):
    """A canonical method projection does not exist."""


class ExperimentNotFoundError(LookupError):
    """A canonical experiment projection does not exist."""


class LeaseConflictError(ValueError):
    """A worker no longer owns a live canonical experiment lease."""


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


@dataclass(frozen=True)
class ArtifactRecord:
    digest: str
    media_type: str
    size_bytes: int
    relative_path: str
    experiment_id: UUID

    def __post_init__(self) -> None:
        if type(self.digest) is not str or re.fullmatch(r"[0-9a-f]{64}", self.digest) is None:
            raise ValueError("artifact digest must be 64 lowercase hexadecimal characters")
        _require_nonempty_string(self.media_type, "media_type")
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ValueError("size_bytes must be a non-negative integer")
        expected_path = f"{self.digest[:2]}/{self.digest[2:4]}/{self.digest}"
        if self.relative_path != expected_path:
            raise ValueError("relative_path must be the canonical digest path")
        _require_uuid(self.experiment_id, "experiment_id")


@dataclass(frozen=True)
class FailureRecord:
    experiment_id: UUID
    problem_id: UUID
    method_id: UUID
    kind: str
    message: str
    retryable: bool
    attempt: int


@dataclass(frozen=True)
class BudgetReservationRecord:
    experiment_id: UUID
    reserved_usd: Decimal
    settled_usd: Decimal | None
    execution_dispatched: bool


@dataclass(frozen=True)
class ReviewRecord:
    claim: CandidateClaim
    problem: Problem
    artifact: ArtifactRecord
    verifier: str
    verifier_version: str
    verification_details: dict[str, object]


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

    def ping(self) -> bool:
        with self.database.transaction() as connection:
            row = connection.execute("SELECT 1").fetchone()
        return row == (1,)

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

    def get_method(self, method_id: UUID) -> MethodVersion:
        canonical_id = _require_uuid(method_id, "method_id")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id, family, version, spec, parent_id, status, created_at
                FROM methods
                WHERE id = %(id)s
                """,
                {"id": canonical_id},
            ).fetchone()
        if row is None:
            raise MethodNotFoundError(f"method {canonical_id} was not found")
        return self._method_from_row(row)

    def get_experiment(self, experiment_id: UUID) -> Experiment:
        canonical_id = _require_uuid(experiment_id, "experiment_id")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id, problem_id, method_id, lane, config, seed, status, created_at
                FROM experiments
                WHERE id = %(id)s
                """,
                {"id": canonical_id},
            ).fetchone()
        if row is None:
            raise ExperimentNotFoundError(f"experiment {canonical_id} was not found")
        return self._experiment_from_row(row)

    def get_claim(self, claim_id: UUID) -> CandidateClaim:
        canonical_id = _require_uuid(claim_id, "claim_id")
        with self.database.transaction() as connection:
            row = self._read_claim(connection, canonical_id)
        if row is None:
            raise ClaimNotFoundError(f"claim {canonical_id} was not found")
        return self._claim_from_row(row)

    def get_evaluation_id(self, claim_id: UUID, verifier: str, verifier_version: str) -> UUID:
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
    def _method_from_row(row: tuple[Any, ...]) -> MethodVersion:
        return MethodVersion(
            id=row[0],
            family=row[1],
            version=row[2],
            spec=row[3],
            parent_id=row[4],
            status=row[5],
            created_at=row[6],
        )

    @staticmethod
    def _experiment_from_row(row: tuple[Any, ...]) -> Experiment:
        return Experiment(
            id=row[0],
            problem_id=row[1],
            method_id=row[2],
            lane=row[3],
            config=row[4],
            seed=row[5],
            status=row[6],
            created_at=row[7],
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
        problem_id, _inserted = self.ingest_problem_snapshot_with_status(
            candidate,
            problem_id=problem_id,
            cohort=cohort,
            created_at=created_at,
        )
        return problem_id

    def ingest_problem_snapshot_with_status(
        self,
        candidate: ProblemCandidate,
        *,
        problem_id: UUID,
        cohort: str,
        created_at: datetime,
    ) -> tuple[UUID, bool]:
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
                return cast(UUID, existing[0]), False
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
            return (
                self._store_problem(
                    connection,
                    problem,
                    idempotency_key=f"problem:{candidate.source_hash}",
                ),
                True,
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

    def register_provenance_baseline(
        self,
        family: str,
        spec: Mapping[str, object],
        *,
        created_at: datetime,
    ) -> MethodVersion:
        """Reuse a current executable epoch or allocate the next family version."""
        canonical_family = _require_nonempty_string(family, "family")
        canonical_spec = dict(spec)
        provenance = validate_provenance(canonical_spec.get("provenance"))
        canonical_spec["provenance"] = provenance
        with self.database.transaction() as connection:
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%(family)s, 0))",
                {"family": f"method-provenance:{canonical_family}"},
            )
            superseded = connection.execute(
                """
                SELECT id, status, spec->'provenance'
                FROM methods
                WHERE family = %(family)s
                  AND status IN ('active', 'candidate')
                  AND spec ? 'provenance'
                  AND spec->'provenance' IS DISTINCT FROM %(provenance)s
                ORDER BY version, id
                FOR UPDATE
                """,
                {
                    "family": canonical_family,
                    "provenance": Jsonb(provenance),
                },
            ).fetchall()
            superseded_ids = [cast(UUID, row[0]) for row in superseded]
            current_identity = cast(str, provenance["identity_sha256"])
            for method_id, status, previous_provenance in superseded:
                previous_identity = (
                    previous_provenance.get("identity_sha256")
                    if isinstance(previous_provenance, dict)
                    else None
                )
                self._append_event(
                    connection,
                    aggregate_type="method",
                    aggregate_id=method_id,
                    event_type="method.superseded_provenance_archived",
                    payload={
                        "from": status,
                        "to": "archived",
                        "reason": "superseded_provenance",
                        "previous_identity": previous_identity,
                        "current_identity": current_identity,
                    },
                    idempotency_key=(
                        f"method:superseded-provenance:{method_id}:{current_identity}"
                    ),
                )
                connection.execute(
                    "UPDATE methods SET status = 'archived' WHERE id = %(id)s",
                    {"id": method_id},
                )
            if superseded_ids:
                pending = connection.execute(
                    """
                    SELECT id, status, method_id
                    FROM experiments
                    WHERE method_id = ANY(%(method_ids)s)
                      AND status IN ('queued', 'leased')
                    ORDER BY id
                    FOR UPDATE
                    """,
                    {"method_ids": superseded_ids},
                ).fetchall()
                for experiment_id, status, method_id in pending:
                    self._append_event(
                        connection,
                        aggregate_type="experiment",
                        aggregate_id=experiment_id,
                        event_type="experiment.superseded_provenance_quarantined",
                        payload={
                            "from": status,
                            "to": "failed",
                            "method_id": str(method_id),
                            "reason": "superseded_provenance",
                            "current_identity": current_identity,
                        },
                        idempotency_key=(
                            f"experiment:superseded-provenance:{experiment_id}:"
                            f"{current_identity}"
                        ),
                    )
                    connection.execute(
                        """
                        UPDATE experiments
                        SET status = 'failed',
                            failure_kind = 'provenance',
                            failure_message = 'superseded_provenance',
                            retryable = false,
                            lease_owner = NULL,
                            lease_expires_at = NULL,
                            updated_at = now()
                        WHERE id = %(id)s
                        """,
                        {"id": experiment_id},
                    )
                cursors = connection.execute(
                    """
                    SELECT problem_id, completed_upper_bound
                    FROM completeness_progress
                    WHERE method_family = %(family)s
                    ORDER BY problem_id
                    FOR UPDATE
                    """,
                    {"family": canonical_family},
                ).fetchall()
                for problem_id, completed_upper_bound in cursors:
                    self._append_event(
                        connection,
                        aggregate_type="problem",
                        aggregate_id=problem_id,
                        event_type="completeness.superseded_provenance_reset",
                        payload={
                            "method_family": canonical_family,
                            "previous_upper_bound": int(completed_upper_bound),
                            "reason": "superseded_provenance",
                            "current_identity": current_identity,
                        },
                        idempotency_key=(
                            f"completeness:superseded-provenance:{problem_id}:"
                            f"{canonical_family}:{current_identity}"
                        ),
                    )
                connection.execute(
                    """
                    DELETE FROM completeness_progress
                    WHERE method_family = %(family)s
                    """,
                    {"family": canonical_family},
                )
            current = connection.execute(
                """
                SELECT id, family, version, spec, parent_id, status, created_at
                FROM methods
                WHERE family = %(family)s
                  AND status = 'active'
                  AND spec->'provenance' = %(provenance)s
                ORDER BY version DESC, id
                LIMIT 1
                """,
                {
                    "family": canonical_family,
                    "provenance": Jsonb(provenance),
                },
            ).fetchone()
            if current is not None:
                return self._method_from_row(current)
            version_row = connection.execute(
                """
                SELECT COALESCE(max(version), 0) + 1
                FROM methods
                WHERE family = %(family)s
                """,
                {"family": canonical_family},
            ).fetchone()
            version = int(version_row[0]) if version_row is not None else 1
            identity = json.dumps(
                {
                    "family": canonical_family,
                    "version": version,
                    "spec": canonical_spec,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            method = MethodVersion(
                id=UUID(bytes=hashlib.sha256(identity.encode()).digest()[:16]),
                family=canonical_family,
                version=version,
                spec=canonical_spec,
                status="active",
                created_at=created_at,
            )
            payload = method.model_dump(mode="json")
            self._append_event(
                connection,
                aggregate_type="method",
                aggregate_id=method.id,
                event_type="method.registered",
                payload=payload,
                idempotency_key=(
                    f"method:provenance:{canonical_family}:"
                    f"{provenance['identity_sha256']}:{version}"
                ),
            )
            connection.execute(
                """
                INSERT INTO methods (
                    id, family, version, spec, parent_id, status, created_at
                ) VALUES (
                    %(id)s, %(family)s, %(version)s, %(spec)s, %(parent_id)s,
                    %(status)s, %(created_at)s
                )
                """,
                {**payload, "spec": Jsonb(payload["spec"])},
            )
            return method

    def quarantine_legacy_provenance(self) -> dict[str, int]:
        """Archive unstamped methods and permanently fail their pending work."""
        methods_quarantined = 0
        experiments_quarantined = 0
        completeness_cursors_reset = 0
        with self.database.transaction() as connection:
            methods = connection.execute(
                """
                SELECT id, status, family
                FROM methods
                WHERE NOT (spec ? 'provenance')
                  AND status IN ('active', 'candidate')
                ORDER BY id
                FOR UPDATE
                """
            ).fetchall()
            legacy_families = {str(row[2]) for row in methods}
            for method_id, status, _family in methods:
                _, appended = self._append_event(
                    connection,
                    aggregate_type="method",
                    aggregate_id=method_id,
                    event_type="method.legacy_provenance_quarantined",
                    payload={
                        "from": status,
                        "to": "archived",
                        "reason": "legacy_unreproducible",
                    },
                    idempotency_key=f"method:legacy-provenance:{method_id}",
                )
                if appended:
                    methods_quarantined += 1
                connection.execute(
                    "UPDATE methods SET status = 'archived' WHERE id = %(id)s",
                    {"id": method_id},
                )
            experiments = connection.execute(
                """
                SELECT e.id, e.status
                FROM experiments AS e
                JOIN methods AS m ON m.id = e.method_id
                WHERE (
                    NOT (m.spec ? 'provenance')
                    OR NOT (e.config ? 'provenance')
                )
                  AND e.status IN ('queued', 'leased')
                ORDER BY e.id
                FOR UPDATE OF e
                """
            ).fetchall()
            for experiment_id, status in experiments:
                _, appended = self._append_event(
                    connection,
                    aggregate_type="experiment",
                    aggregate_id=experiment_id,
                    event_type="experiment.legacy_provenance_quarantined",
                    payload={
                        "from": status,
                        "to": "failed",
                        "reason": "legacy_unreproducible",
                    },
                    idempotency_key=f"experiment:legacy-provenance:{experiment_id}",
                )
                if appended:
                    experiments_quarantined += 1
                connection.execute(
                    """
                    UPDATE experiments
                    SET status = 'failed',
                        failure_kind = 'provenance',
                        failure_message = 'legacy_unreproducible',
                        retryable = false,
                        lease_owner = NULL,
                        lease_expires_at = NULL,
                        updated_at = now()
                    WHERE id = %(id)s
                    """,
                    {"id": experiment_id},
                )
            if legacy_families:
                cursors = connection.execute(
                    """
                    SELECT problem_id, method_family, completed_upper_bound
                    FROM completeness_progress
                    WHERE method_family = ANY(%(families)s)
                    ORDER BY problem_id, method_family
                    FOR UPDATE
                    """,
                    {"families": list(legacy_families)},
                ).fetchall()
                for problem_id, family, completed_upper_bound in cursors:
                    _, appended = self._append_event(
                        connection,
                        aggregate_type="problem",
                        aggregate_id=problem_id,
                        event_type="completeness.legacy_provenance_reset",
                        payload={
                            "method_family": family,
                            "previous_upper_bound": int(completed_upper_bound),
                            "reason": "legacy_unreproducible",
                        },
                        idempotency_key=(
                            f"completeness:legacy-provenance:{problem_id}:{family}"
                        ),
                    )
                    if appended:
                        completeness_cursors_reset += 1
                connection.execute(
                    """
                    DELETE FROM completeness_progress
                    WHERE method_family = ANY(%(families)s)
                    """,
                    {"families": list(legacy_families)},
                )
        if completeness_cursors_reset:
            self.reconcile_completeness_progress()
        return {
            "methods": methods_quarantined,
            "experiments": experiments_quarantined,
            "completeness_cursors": completeness_cursors_reset,
        }

    def set_method_status(self, method_id: UUID, status: str, reason: str) -> MethodVersion:
        canonical_id = _require_uuid(method_id, "method_id")
        if status not in {"candidate", "active", "retired", "archived"}:
            raise ValueError("invalid method status")
        canonical_reason = _require_nonempty_string(reason, "reason")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id, family, version, spec, parent_id, status, created_at
                FROM methods
                WHERE id = %(id)s
                FOR UPDATE
                """,
                {"id": canonical_id},
            ).fetchone()
            if row is None:
                raise MethodNotFoundError(f"method {canonical_id} was not found")
            current = self._method_from_row(row)
            if current.status == status:
                return current
            self._append_event(
                connection,
                aggregate_type="method",
                aggregate_id=canonical_id,
                event_type="method.status_changed",
                payload={"from": current.status, "to": status, "reason": canonical_reason},
                idempotency_key=f"method:status:{canonical_id}:{status}",
            )
            updated = connection.execute(
                """
                UPDATE methods
                SET status = %(status)s
                WHERE id = %(id)s
                RETURNING id, family, version, spec, parent_id, status, created_at
                """,
                {"id": canonical_id, "status": status},
            ).fetchone()
        if updated is None:
            raise MethodNotFoundError(f"method {canonical_id} was not found")
        return self._method_from_row(updated)

    def promote_method(
        self,
        child_id: UUID,
        parent_id: UUID,
        reason: str,
    ) -> MethodVersion:
        canonical_child_id = _require_uuid(child_id, "child_id")
        canonical_parent_id = _require_uuid(parent_id, "parent_id")
        if canonical_child_id == canonical_parent_id:
            raise ValueError("a method cannot promote itself")
        canonical_reason = _require_nonempty_string(reason, "reason")
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id, family, version, spec, parent_id, status, created_at
                FROM methods
                WHERE id = ANY(%(ids)s)
                ORDER BY id
                FOR UPDATE
                """,
                {"ids": [canonical_child_id, canonical_parent_id]},
            ).fetchall()
            methods = {row[0]: self._method_from_row(row) for row in rows}
            child = methods.get(canonical_child_id)
            parent = methods.get(canonical_parent_id)
            if child is None:
                raise MethodNotFoundError(f"method {canonical_child_id} was not found")
            if parent is None:
                raise MethodNotFoundError(f"method {canonical_parent_id} was not found")
            if child.parent_id != parent.id or child.family != parent.family:
                raise ValueError("promotion child must belong to its declared parent family")
            if child.status not in {"candidate", "active"}:
                raise ValueError("promotion child must be candidate or active")
            if parent.status not in {"active", "archived"}:
                raise ValueError("promotion parent must be active or archived")

            if child.status != "active":
                self._append_event(
                    connection,
                    aggregate_type="method",
                    aggregate_id=child.id,
                    event_type="method.status_changed",
                    payload={
                        "from": child.status,
                        "to": "active",
                        "reason": canonical_reason,
                    },
                    idempotency_key=f"method:status:{child.id}:active",
                )
            if parent.status != "archived":
                self._append_event(
                    connection,
                    aggregate_type="method",
                    aggregate_id=parent.id,
                    event_type="method.status_changed",
                    payload={
                        "from": parent.status,
                        "to": "archived",
                        "reason": f"superseded by promoted child {child.id}",
                    },
                    idempotency_key=f"method:status:{parent.id}:archived",
                )
            self._append_event(
                connection,
                aggregate_type="method",
                aggregate_id=child.id,
                event_type="method.promotion_committed",
                payload={
                    "child_id": str(child.id),
                    "parent_id": str(parent.id),
                },
                idempotency_key=f"method:promotion:{child.id}:{parent.id}",
            )
            connection.execute(
                """
                UPDATE methods
                SET status = CASE
                    WHEN id = %(child_id)s THEN 'active'
                    WHEN id = %(parent_id)s THEN 'archived'
                    ELSE status
                END
                WHERE id IN (%(child_id)s, %(parent_id)s)
                """,
                {"child_id": child.id, "parent_id": parent.id},
            )
            updated = connection.execute(
                """
                SELECT id, family, version, spec, parent_id, status, created_at
                FROM methods
                WHERE id = %(id)s
                """,
                {"id": child.id},
            ).fetchone()
        assert updated is not None
        return self._method_from_row(updated)

    def reconcile_method_promotions(self) -> int:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT child.id, parent.id
                FROM methods AS child
                JOIN methods AS parent ON parent.id = child.parent_id
                JOIN events AS decision
                  ON decision.aggregate_type = 'method'
                 AND decision.aggregate_id = child.id
                 AND decision.event_type = 'method.promotion_committed'
                 AND decision.payload->>'child_id' = child.id::text
                 AND decision.payload->>'parent_id' = parent.id::text
                WHERE child.status = 'active' AND parent.status = 'active'
                ORDER BY child.id
                """
            ).fetchall()
        reconciled = 0
        for child_id, parent_id in rows:
            self.promote_method(
                child_id,
                parent_id,
                "reconciled active child from interrupted promotion",
            )
            reconciled += 1
        return reconciled

    def record_method_outcome(self, evaluation_id: UUID) -> MethodMetrics:
        canonical_evaluation_id = _require_uuid(evaluation_id, "evaluation_id")
        with self.database.transaction() as connection:
            return self._record_method_outcome(connection, canonical_evaluation_id)

    def _record_method_outcome(
        self,
        connection: Connection[tuple[Any, ...]],
        evaluation_id: UUID,
    ) -> MethodMetrics:
        context = connection.execute(
            """
            SELECT v.accepted, v.independent, v.claim_id,
                   c.status, c.problem_id, c.experiment_id,
                   e.problem_id, e.method_id, e.status, e.cost_usd,
                   p.domain, p.cohort, m.id,
                   v.details ? 'provenance',
                   e.config ? 'provenance',
                   m.spec ? 'provenance'
            FROM evaluations AS v
            LEFT JOIN claims AS c ON c.id = v.claim_id
            LEFT JOIN experiments AS e ON e.id = c.experiment_id
            LEFT JOIN problems AS p ON p.id = c.problem_id
            LEFT JOIN methods AS m ON m.id = e.method_id
            WHERE v.id = %(evaluation_id)s
            """,
            {"evaluation_id": evaluation_id},
        ).fetchone()
        if context is None:
            raise EvaluationNotFoundError(f"evaluation {evaluation_id} was not found")
        if context[1] is not True:
            raise EvaluationContextError("routing scores require independent verification")
        if any(value is None for value in context[2:13]):
            raise EvaluationContextError(
                "evaluation is missing its canonical claim, experiment, problem, or method"
            )
        if context[13:] != (True, True, True):
            raise EvaluationContextError(
                "legacy_unreproducible evaluations cannot affect routing scores"
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
        payload: dict[str, object] = {
            "evaluation_id": str(evaluation_id),
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
            idempotency_key=f"method:outcome:evaluation:{evaluation_id}",
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
                    false_positives = method_scores.false_positives + EXCLUDED.false_positives,
                    cost_usd = method_scores.cost_usd + EXCLUDED.cost_usd
                RETURNING trials, reward, false_positives, cost_usd
                """,
                {
                    "domain": domain,
                    "method_id": method_id,
                    "cohort": cohort.value,
                    "reward": int(accepted),
                    "false_positives": int(not accepted),
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

    def get_method_execution_metrics(
        self,
        method_id: UUID,
        cohort: MetricsCohort,
        *,
        lane: str | None = None,
    ) -> MethodMetrics:
        canonical_method_id = _require_uuid(method_id, "method_id")
        if type(cohort) is not MetricsCohort:
            raise TypeError("cohort must be a MetricsCohort")
        canonical_lane = None if lane is None else _require_nonempty_string(lane, "lane")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                WITH execution AS (
                    SELECT e.id,
                           GREATEST(
                               e.attempt,
                               CASE WHEN EXISTS (
                                   SELECT 1 FROM claims AS c
                                   JOIN evaluations AS v ON v.claim_id = c.id
                                   WHERE c.experiment_id = e.id AND v.independent = true
                               ) THEN 1 ELSE 0 END
                           ) AS attempts,
                           CASE WHEN EXISTS (
                               SELECT 1 FROM claims AS c
                               JOIN evaluations AS v ON v.claim_id = c.id
                               WHERE c.experiment_id = e.id
                                 AND v.independent = true AND v.accepted = true
                           ) THEN 1 ELSE 0 END AS verified,
                           CASE WHEN EXISTS (
                               SELECT 1 FROM claims AS c
                               JOIN evaluations AS v ON v.claim_id = c.id
                               WHERE c.experiment_id = e.id
                                 AND v.independent = true AND v.accepted = false
                           ) THEN 1 ELSE 0 END AS false_positive,
                           CASE WHEN b.settled_usd IS NOT NULL
                                THEN b.settled_usd ELSE e.cost_usd END AS effective_cost
                    FROM experiments AS e
                    JOIN problems AS p ON p.id = e.problem_id
                    LEFT JOIN budget_reservations AS b ON b.experiment_id = e.id
                    WHERE e.method_id = %(method_id)s AND p.cohort = %(cohort)s
                      AND (%(lane)s::text IS NULL OR e.lane = %(lane)s::text)
                )
                SELECT COALESCE(sum(attempts), 0), COALESCE(sum(verified), 0),
                       COALESCE(sum(false_positive), 0),
                       COALESCE(sum(effective_cost), 0)
                FROM execution
                """,
                {
                    "method_id": canonical_method_id,
                    "cohort": cohort.value,
                    "lane": canonical_lane,
                },
            ).fetchone()
        assert row is not None
        return MethodMetrics(
            cohort=cohort,
            trials=int(row[0]),
            verified=int(row[1]),
            false_positives=int(row[2]),
            cost_usd=Decimal(row[3]),
        )

    def get_method_work_units(
        self,
        method_id: UUID,
        cohort: MetricsCohort,
        *,
        lane: str | None = None,
    ) -> int:
        canonical_method_id = _require_uuid(method_id, "method_id")
        if type(cohort) is not MetricsCohort:
            raise TypeError("cohort must be a MetricsCohort")
        canonical_lane = None if lane is None else _require_nonempty_string(lane, "lane")
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT e.config, e.attempt
                FROM experiments AS e
                JOIN problems AS p ON p.id = e.problem_id
                WHERE e.method_id = %(method_id)s AND p.cohort = %(cohort)s
                  AND (%(lane)s::text IS NULL OR e.lane = %(lane)s::text)
                """,
                {
                    "method_id": canonical_method_id,
                    "cohort": cohort.value,
                    "lane": canonical_lane,
                },
            ).fetchall()
        total = 0
        for config, attempts in rows:
            attempt_count = int(attempts)
            if attempt_count <= 0:
                continue
            if (
                isinstance(config, dict)
                and type(config.get("start")) is int
                and type(config.get("stop")) is int
            ):
                total += max(int(config["stop"]) - int(config["start"]), 0) * attempt_count
            else:
                total += attempt_count
        return total

    def reconcile_method_outcomes(self) -> int:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT v.id
                FROM evaluations AS v
                JOIN claims AS c ON c.id = v.claim_id
                JOIN experiments AS x ON x.id = c.experiment_id
                JOIN methods AS m ON m.id = x.method_id
                WHERE v.independent = true
                  AND v.details ? 'provenance'
                  AND x.config ? 'provenance'
                  AND m.spec ? 'provenance'
                  AND NOT EXISTS (
                      SELECT 1 FROM events AS e
                      WHERE e.idempotency_key = (
                          'method:outcome:evaluation:' || v.id::text
                      )
                  )
                ORDER BY v.created_at, v.id
                """
            ).fetchall()
        reconciled = 0
        for row in rows:
            self.record_method_outcome(cast(UUID, row[0]))
            reconciled += 1
        return reconciled

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
                       p.checker, m.family, m.status, m.spec
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
            if context[7] != "integer_counterexample":
                raise CompletenessProgressError(
                    "completeness progress requires an integer counterexample method"
                )
            if context[8] != "active":
                raise CompletenessProgressError(
                    "completeness progress requires the active provenance epoch"
                )
            if context[4] != ExperimentStatus.SUCCEEDED.value:
                raise CompletenessProgressError("completeness experiment is not succeeded")
            result = context[5]
            if not isinstance(result, dict) or result.get("status") != "bounded_no_counterexample":
                raise CompletenessProgressError(
                    "completeness experiment did not finish the full interval"
                )
            config = context[3]
            if not isinstance(config, dict) or set(config) not in (
                {"start", "stop", "order"},
                {"start", "stop", "order", "provenance"},
            ):
                raise CompletenessProgressError("completeness experiment has an invalid config")
            start = config["start"]
            stop = config["stop"]
            method_spec = context[9]
            method_provenance = (
                method_spec.get("provenance")
                if isinstance(method_spec, dict)
                else None
            )
            expected_identity = (
                method_provenance.get("identity_sha256")
                if isinstance(method_provenance, dict)
                else None
            )
            if config.get("provenance") != expected_identity:
                raise CompletenessProgressError(
                    "completeness experiment provenance differs from the active method"
                )
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
            return self._advance_completeness_progress(
                connection,
                experiment_id=canonical_experiment_id,
                problem_id=problem_id,
                method_id=cast(UUID, context[1]),
                method_family=method_family,
                declared_start=declared_start,
                start=start,
                stop=stop,
            )

    def _advance_completeness_progress(
        self,
        connection: Connection[tuple[Any, ...]],
        *,
        experiment_id: UUID,
        problem_id: UUID,
        method_id: UUID,
        method_family: str,
        declared_start: int,
        start: int,
        stop: int,
    ) -> int:
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%(key)s, 0))",
            {"key": f"semantic-work:{problem_id}:{method_family}"},
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
            "experiment_id": str(experiment_id),
            "problem_id": str(problem_id),
            "method_id": str(method_id),
            "method_family": method_family,
            "start": start,
            "stop": stop,
        }
        _, appended = self._append_event(
            connection,
            aggregate_type="experiment",
            aggregate_id=experiment_id,
            event_type="completeness.progress_recorded",
            payload=payload,
            idempotency_key=f"completeness:experiment:{experiment_id}",
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

    def reconcile_completeness_progress(self) -> int:
        """Advance valid succeeded bounded intervals missing their progress event."""
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT e.id, e.problem_id, e.config, m.family
                FROM experiments AS e
                JOIN methods AS m ON m.id = e.method_id
                WHERE e.status = 'succeeded'
                  AND m.family = 'integer_counterexample'
                  AND m.status = 'active'
                  AND m.spec ? 'provenance'
                  AND e.config ? 'provenance'
                  AND e.config->>'provenance' =
                      m.spec->'provenance'->>'identity_sha256'
                  AND e.lane NOT IN ('evolution_holdout', 'routing_holdout')
                  AND e.result->>'status' = 'bounded_no_counterexample'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM events AS v
                      WHERE v.aggregate_id = e.id
                        AND v.event_type = 'completeness.progress_recorded'
                  )
                ORDER BY e.problem_id, e.created_at, e.id
                """
            ).fetchall()
        candidates: list[tuple[int, int, UUID]] = []
        for experiment_id, _problem_id, config, _family in rows:
            if (
                isinstance(config, dict)
                and set(config)
                in (
                    {"start", "stop", "order"},
                    {"start", "stop", "order", "provenance"},
                )
                and config.get("order") == "ascending"
                and type(config.get("start")) is int
                and type(config.get("stop")) is int
            ):
                candidates.append(
                    (cast(int, config["start"]), cast(int, config["stop"]), experiment_id)
                )
        reconciled = 0
        for _start, _stop, experiment_id in sorted(candidates):
            try:
                self.record_completeness_progress(experiment_id)
            except CompletenessProgressError:
                continue
            reconciled += 1
        return reconciled

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
            return self._enqueue_in_transaction(
                connection,
                experiment,
                payload,
                idempotency_key,
            )

    def enqueue_evaluation_batch(
        self,
        experiments: tuple[Experiment, ...],
        *,
        idempotency_prefix: str,
    ) -> tuple[UUID, ...]:
        """Atomically enqueue all members of an intentional evaluation batch."""
        if not experiments:
            return ()
        if len({experiment.id for experiment in experiments}) != len(experiments):
            raise ValueError("evaluation batch contains duplicate experiment IDs")
        prefix = _require_nonempty_string(idempotency_prefix, "idempotency_prefix")
        with self.database.transaction() as connection:
            return tuple(
                self._enqueue_in_transaction(
                    connection,
                    experiment,
                    experiment.model_dump(mode="json"),
                    f"{prefix}:{experiment.id}",
                )
                for experiment in experiments
            )

    def enqueue_if_semantic_work_available(
        self, experiment: Experiment, idempotency_key: str
    ) -> bool:
        """Atomically enqueue unless equivalent or overlapping work already exists."""
        payload = experiment.model_dump(mode="json")
        with self.database.transaction() as connection:
            canonical = connection.execute(
                """
                SELECT m.family
                FROM methods AS m
                WHERE m.id = %(method_id)s
                  AND EXISTS (
                      SELECT 1 FROM problems AS p WHERE p.id = %(problem_id)s
                  )
                """,
                {
                    "problem_id": experiment.problem_id,
                    "method_id": experiment.method_id,
                },
            ).fetchone()
            if canonical is None:
                raise ProjectionConflictError(
                    "experiment references a missing canonical problem or method"
                )
            family = str(canonical[0])
            family_interval = (
                family == "integer_counterexample"
                and self._is_ascending_interval_config(experiment.config)
            )
            lock_scope = family if family_interval else str(experiment.method_id)
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%(key)s, 0))",
                {"key": f"semantic-work:{experiment.problem_id}:{lock_scope}"},
            )
            if family_interval:
                rows = connection.execute(
                    """
                    SELECT e.id, e.config
                    FROM experiments AS e
                    JOIN methods AS m ON m.id = e.method_id
                    WHERE e.problem_id = %(problem_id)s AND m.family = %(family)s
                      AND m.status = 'active'
                      AND m.spec ? 'provenance'
                      AND e.config ? 'provenance'
                      AND e.config->>'provenance' =
                          m.spec->'provenance'->>'identity_sha256'
                      AND e.lane NOT IN (
                          'verification', 'evolution_holdout', 'routing_holdout'
                      )
                    """,
                    {"problem_id": experiment.problem_id, "family": family},
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT id, config
                    FROM experiments
                    WHERE problem_id = %(problem_id)s AND method_id = %(method_id)s
                      AND lane NOT IN (
                          'verification', 'evolution_holdout', 'routing_holdout'
                      )
                    """,
                    {
                        "problem_id": experiment.problem_id,
                        "method_id": experiment.method_id,
                    },
                ).fetchall()
            for existing_id, existing_config in rows:
                if existing_id == experiment.id:
                    return True
                if isinstance(existing_config, dict) and self._semantic_configs_overlap(
                    experiment.config,
                    existing_config,
                ):
                    return False
            self._enqueue_in_transaction(
                connection,
                experiment,
                payload,
                idempotency_key,
            )
            return True

    def _enqueue_in_transaction(
        self,
        connection: Connection[tuple[Any, ...]],
        experiment: Experiment,
        payload: dict[str, object],
        idempotency_key: str,
    ) -> UUID:
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
                RETURNING e.id, e.problem_id, e.method_id, e.lane, e.config,
                          e.seed, e.status, e.created_at, e.attempt;
                """,
                {"worker": worker, "now": now, "expires": expires},
            ).fetchone()
            if row is None:
                return None
            experiment = self._experiment_from_row(row[0:8])
            self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=experiment.id,
                event_type="experiment.leased",
                payload={
                    "worker": worker,
                    "lease_expires_at": expires.isoformat(),
                    "attempt": row[8],
                },
                idempotency_key=f"experiment:lease:{experiment.id}:{row[8]}",
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
        cost_usd: Decimal,
        *,
        now: datetime | None = None,
    ) -> None:
        canonical_experiment_id = _require_uuid(experiment_id, "experiment_id")
        canonical_worker = _require_nonempty_string(worker, "worker")
        cost = _require_database_usd(cost_usd, "cost_usd")
        completed_at = datetime.now(UTC) if now is None else now
        self._validate_lease_timestamp(completed_at)
        with self.database.transaction() as connection:
            _, appended = self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=canonical_experiment_id,
                event_type="experiment.completed",
                payload={
                    "worker": canonical_worker,
                    "result": result,
                    "cost_usd": format(cost, "f"),
                },
                idempotency_key=f"experiment:complete:{canonical_experiment_id}",
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
                    "id": canonical_experiment_id,
                    "worker": canonical_worker,
                    "result": Jsonb(result),
                    "cost_usd": cost,
                    "now": completed_at,
                },
            ).fetchone()
            if row is None:
                raise LeaseConflictError("experiment is not leased by this worker")

    def commit_worker_result(
        self,
        experiment_id: UUID,
        worker: str,
        *,
        result: dict[str, object],
        cost_usd: Decimal,
        artifact: ArtifactRecord,
        claim: CandidateClaim | None,
        now: datetime | None = None,
    ) -> None:
        """Atomically publish evidence, an optional candidate, and completion.

        The artifact bytes may already exist in the content store, but no canonical
        metadata or claim becomes visible unless the worker still owns a live lease.
        """
        canonical_experiment_id = _require_uuid(experiment_id, "experiment_id")
        canonical_worker = _require_nonempty_string(worker, "worker")
        cost = _require_database_usd(cost_usd, "cost_usd")
        completed_at = datetime.now(UTC) if now is None else now
        self._validate_lease_timestamp(completed_at)
        if artifact.experiment_id != canonical_experiment_id:
            raise ValueError("artifact experiment does not match the committed experiment")
        with self.database.transaction() as connection:
            lease = connection.execute(
                """
                SELECT e.problem_id, e.status, e.lease_owner, e.lease_expires_at,
                       e.config, p.checker, m.family, e.method_id, e.lane
                FROM experiments AS e
                LEFT JOIN problems AS p ON p.id = e.problem_id
                LEFT JOIN methods AS m ON m.id = e.method_id
                WHERE e.id = %(id)s
                FOR UPDATE OF e
                """,
                {"id": canonical_experiment_id},
            ).fetchone()
            if lease is None:
                raise ExperimentNotFoundError(f"experiment {canonical_experiment_id} was not found")
            if (
                lease[1] != ExperimentStatus.LEASED.value
                or lease[2] != canonical_worker
                or lease[3] is None
                or lease[3] <= completed_at
            ):
                raise LeaseConflictError("experiment is not leased by this worker")
            if claim is not None:
                if claim.experiment_id != canonical_experiment_id:
                    raise ValueError("claim experiment does not match the committed experiment")
                if claim.problem_id != lease[0]:
                    raise ValueError("claim problem does not match the canonical experiment")

            artifact_payload: dict[str, object] = {
                "digest": artifact.digest,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
                "relative_path": artifact.relative_path,
                "experiment_id": str(canonical_experiment_id),
                "method_provenance": (
                    lease[4].get("provenance")
                    if isinstance(lease[4], dict)
                    else None
                ),
            }
            _, artifact_appended = self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=canonical_experiment_id,
                event_type="artifact.stored",
                payload=artifact_payload,
                idempotency_key=f"artifact:experiment:{canonical_experiment_id}",
            )
            if artifact_appended:
                artifact_row = connection.execute(
                    """
                    INSERT INTO artifacts (
                        digest, media_type, size_bytes, relative_path, experiment_id
                    ) VALUES (
                        %(digest)s, %(media_type)s, %(size_bytes)s, %(relative_path)s,
                        %(experiment_id)s
                    )
                    ON CONFLICT (digest) DO UPDATE SET digest = EXCLUDED.digest
                    WHERE (
                        artifacts.media_type, artifacts.size_bytes,
                        artifacts.relative_path, artifacts.experiment_id
                    ) IS NOT DISTINCT FROM (
                        EXCLUDED.media_type, EXCLUDED.size_bytes,
                        EXCLUDED.relative_path, EXCLUDED.experiment_id
                    )
                    RETURNING digest
                    """,
                    {
                        "digest": artifact.digest,
                        "media_type": artifact.media_type,
                        "size_bytes": artifact.size_bytes,
                        "relative_path": artifact.relative_path,
                        "experiment_id": canonical_experiment_id,
                    },
                ).fetchone()
                if artifact_row is None:
                    raise ProjectionConflictError(
                        f"artifact {artifact.digest} has conflicting immutable metadata"
                    )

            if claim is not None:
                claim_payload = claim.model_dump(mode="json")
                _, claim_appended = self._append_event(
                    connection,
                    aggregate_type="claim",
                    aggregate_id=claim.id,
                    event_type="claim.candidate_saved",
                    payload=claim_payload,
                    idempotency_key=f"claim:{claim.id}",
                )
                if claim_appended:
                    claim_row = connection.execute(
                        """
                        INSERT INTO claims (
                            id, problem_id, experiment_id, claim_type, statement, witness,
                            status, evidence_level, created_at
                        ) VALUES (
                            %(id)s, %(problem_id)s, %(experiment_id)s, %(claim_type)s,
                            %(statement)s, %(witness)s, %(status)s, %(evidence_level)s,
                            %(created_at)s
                        )
                        ON CONFLICT (id) DO UPDATE SET id = EXCLUDED.id
                        WHERE (
                            claims.problem_id, claims.experiment_id, claims.claim_type,
                            claims.statement, claims.witness, claims.status,
                            claims.evidence_level, claims.created_at
                        ) IS NOT DISTINCT FROM (
                            EXCLUDED.problem_id, EXCLUDED.experiment_id,
                            EXCLUDED.claim_type, EXCLUDED.statement, EXCLUDED.witness,
                            EXCLUDED.status, EXCLUDED.evidence_level, EXCLUDED.created_at
                        )
                        RETURNING id
                        """,
                        {
                            **claim_payload,
                            "witness": (
                                Jsonb(claim_payload["witness"])
                                if claim_payload["witness"] is not None
                                else None
                            ),
                        },
                    ).fetchone()
                    if claim_row is None:
                        raise ProjectionConflictError(
                            f"claim {claim.id} has conflicting immutable projection data"
                        )

            _, completion_appended = self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=canonical_experiment_id,
                event_type="experiment.completed",
                payload={
                    "worker": canonical_worker,
                    "result": result,
                    "cost_usd": format(cost, "f"),
                },
                idempotency_key=f"experiment:complete:{canonical_experiment_id}",
            )
            if not completion_appended:
                raise ProjectionConflictError("leased experiment already has a completion event")
            completed = connection.execute(
                """
                UPDATE experiments
                SET status = 'succeeded', result = %(result)s, cost_usd = %(cost_usd)s,
                    lease_owner = NULL, lease_expires_at = NULL,
                    failure_kind = NULL, failure_message = NULL, retryable = NULL,
                    updated_at = %(now)s
                WHERE id = %(id)s AND status = 'leased' AND lease_owner = %(worker)s
                  AND lease_expires_at > %(now)s
                RETURNING id
                """,
                {
                    "id": canonical_experiment_id,
                    "worker": canonical_worker,
                    "result": Jsonb(result),
                    "cost_usd": cost,
                    "now": completed_at,
                },
            ).fetchone()
            if completed is None:
                raise LeaseConflictError("experiment is not leased by this worker")
            config = lease[4]
            checker = lease[5]
            if (
                lease[6] == "integer_counterexample"
                and lease[8] not in {"evolution_holdout", "routing_holdout"}
                and result.get("status") == "bounded_no_counterexample"
                and isinstance(config, dict)
                and config.get("order") == "ascending"
            ):
                if set(config) not in (
                    {"start", "stop", "order"},
                    {"start", "stop", "order", "provenance"},
                ):
                    raise CompletenessProgressError("completeness experiment has an invalid config")
                start = config["start"]
                stop = config["stop"]
                declared_start = checker.get("start") if isinstance(checker, dict) else None
                if (
                    type(start) is not int
                    or type(stop) is not int
                    or type(declared_start) is not int
                    or start >= stop
                    or stop > MAX_INT64
                ):
                    raise CompletenessProgressError(
                        "canonical bounded search has invalid interval metadata"
                    )
                self._advance_completeness_progress(
                    connection,
                    experiment_id=canonical_experiment_id,
                    problem_id=cast(UUID, lease[0]),
                    method_id=cast(UUID, lease[7]),
                    method_family="integer_counterexample",
                    declared_start=declared_start,
                    start=start,
                    stop=stop,
                )

    def fail(
        self,
        experiment_id: UUID,
        worker: str,
        kind: str,
        message: str,
        *,
        retryable: bool,
        now: datetime | None = None,
    ) -> None:
        canonical_id = _require_uuid(experiment_id, "experiment_id")
        canonical_worker = _require_nonempty_string(worker, "worker")
        canonical_kind = _require_nonempty_string(kind, "kind")
        canonical_message = _require_nonempty_string(message, "message")
        if type(retryable) is not bool:
            raise TypeError("retryable must be a boolean")
        failed_at = datetime.now(UTC) if now is None else now
        self._validate_lease_timestamp(failed_at)
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT attempt
                FROM experiments
                WHERE id = %(id)s AND status = 'leased' AND lease_owner = %(worker)s
                  AND lease_expires_at > %(now)s
                FOR UPDATE
                """,
                {"id": canonical_id, "worker": canonical_worker, "now": failed_at},
            ).fetchone()
            if row is None:
                raise LeaseConflictError("experiment is not leased by this worker")
            attempt = int(row[0])
            self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=canonical_id,
                event_type="experiment.failed",
                payload={
                    "worker": canonical_worker,
                    "kind": canonical_kind,
                    "message": canonical_message,
                    "retryable": retryable,
                    "attempt": attempt,
                },
                idempotency_key=f"experiment:failure:{canonical_id}:{attempt}",
            )
            updated = connection.execute(
                """
                UPDATE experiments
                SET status = 'failed', failure_kind = %(kind)s,
                    failure_message = %(message)s, retryable = %(retryable)s,
                    lease_owner = NULL, lease_expires_at = NULL, updated_at = %(now)s
                WHERE id = %(id)s AND status = 'leased' AND lease_owner = %(worker)s
                RETURNING id
                """,
                {
                    "id": canonical_id,
                    "worker": canonical_worker,
                    "kind": canonical_kind,
                    "message": canonical_message,
                    "retryable": retryable,
                    "now": failed_at,
                },
            ).fetchone()
            if updated is None:
                raise LeaseConflictError("experiment is not leased by this worker")

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
                            Jsonb(payload["witness"]) if payload["witness"] is not None else None
                        ),
                    },
                )

    def record_verification(
        self,
        claim: CandidateClaim,
        verification: Verification,
    ) -> CandidateClaim:
        del claim, verification
        raise PermissionError(
            "canonical claim promotion requires a kernel verifier attestation"
        )

    def record_verification_and_method_outcome(
        self,
        claim: CandidateClaim,
        verification: Verification,
    ) -> CandidateClaim:
        del claim, verification
        raise PermissionError(
            "canonical claim promotion requires a kernel verifier attestation"
        )

    def evaluate_and_record_claim(
        self,
        claim: CandidateClaim,
        *,
        record_method_outcome: bool,
    ) -> CandidateClaim:
        from mathloop.verification import CalibrationVerificationKernel

        if type(record_method_outcome) is not bool:
            raise TypeError("record_method_outcome must be a boolean")
        claim_id = _require_uuid(claim.id, "claim_id")
        canonical_claim = self.get_claim(claim_id)
        if not self._same_immutable_claim_snapshot(claim, canonical_claim):
            raise ClaimSnapshotConflictError(
                f"claim {claim_id} conflicts with its canonical snapshot"
            )
        if claim.status is not ClaimStatus.CANDIDATE:
            raise ClaimStateConflictError(
                f"claim {claim_id} caller snapshot is not in candidate state"
            )
        problem = self.get_problem(canonical_claim.problem_id)
        verification_claim = canonical_claim.model_copy(
            update={
                "status": ClaimStatus.CANDIDATE,
                "evidence_level": EvidenceLevel.LEAD,
            }
        )
        verification = CalibrationVerificationKernel.verify(
            CalibrationVerificationKernel(),
            problem,
            verification_claim,
        )
        allowed = {
            ("integer-predicate", "1"),
            ("sage-symbolic-induction", "1"),
        }
        if (
            verification.verifier,
            verification.verifier_version,
        ) not in allowed:
            raise PermissionError("verification result is outside the kernel allowlist")
        if not verification.independent:
            raise PermissionError("kernel verification must be independent")
        expected_provenance = verifier_provenance(verification.verifier)
        if verification.details.get("provenance") != expected_provenance:
            raise PermissionError("verification provenance is not the current kernel identity")
        verification_payload = verification.model_dump(mode="json")
        with self.database.transaction() as connection:
            claim_row = self._read_claim(connection, claim_id, for_update=True)
            if claim_row is None:
                raise ClaimNotFoundError(f"claim {claim_id} was not found")
            locked_claim = self._claim_from_row(claim_row)
            if not self._same_immutable_claim_snapshot(claim, locked_claim):
                raise ClaimSnapshotConflictError(
                    f"claim {claim_id} conflicts with its canonical snapshot"
                )
            _, appended = self._append_event(
                connection,
                aggregate_type="claim",
                aggregate_id=claim_id,
                event_type="claim.verified",
                payload=verification_payload,
                idempotency_key=(
                    f"verification:{claim_id}:{verification.verifier}:"
                    f"{verification.verifier_version}"
                ),
            )
            if not appended:
                if not self._is_expected_verified_projection(locked_claim, verification):
                    raise ClaimStateConflictError(
                        f"claim {claim_id} does not match its replayed verification"
                    )
                evaluation_id = self._get_evaluation_id_in_transaction(
                    connection,
                    claim_id,
                    verification.verifier,
                    verification.verifier_version,
                )
                if record_method_outcome:
                    self._record_method_outcome(connection, evaluation_id)
                return locked_claim
            if locked_claim.status is not ClaimStatus.CANDIDATE:
                raise ClaimStateConflictError(f"claim {claim_id} is not in candidate state")
            updated_claim = advance_claim(locked_claim, verification)
            evaluation_row = connection.execute(
                """
                INSERT INTO evaluations (
                    claim_id, verifier, verifier_version, accepted, independent, details
                ) VALUES (
                    %(claim_id)s, %(verifier)s, %(verifier_version)s, %(accepted)s,
                    %(independent)s, %(details)s
                )
                RETURNING id
                """,
                {
                    **verification_payload,
                    "claim_id": claim_id,
                    "details": Jsonb(verification_payload["details"]),
                },
            ).fetchone()
            if evaluation_row is None:
                raise RuntimeError("verification evaluation was not persisted")
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
                raise ClaimStateConflictError(f"claim {claim_id} is not in candidate state")
            evaluation_id = cast(UUID, evaluation_row[0])
            if record_method_outcome:
                self._record_method_outcome(connection, evaluation_id)
            return self._claim_from_row(updated_row)

    @staticmethod
    def _get_evaluation_id_in_transaction(
        connection: Connection[tuple[Any, ...]],
        claim_id: UUID,
        verifier: str,
        verifier_version: str,
    ) -> UUID:
        row = connection.execute(
            """
            SELECT id FROM evaluations
            WHERE claim_id = %(claim_id)s AND verifier = %(verifier)s
              AND verifier_version = %(verifier_version)s
            """,
            {
                "claim_id": claim_id,
                "verifier": verifier,
                "verifier_version": verifier_version,
            },
        ).fetchone()
        if row is None:
            raise EvaluationNotFoundError("canonical evaluation was not found")
        return cast(UUID, row[0])

    @staticmethod
    def _same_immutable_claim_snapshot(supplied: CandidateClaim, canonical: CandidateClaim) -> bool:
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

    def list_eligible_problems(self) -> tuple[Problem, ...]:
        """Return only the newest eligible immutable snapshot for each source."""
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT p.id, p.source_id, p.source_uri, p.source_hash, p.statement,
                       p.normalized_statement, p.domain, p.features, p.checker,
                       p.status, p.cohort, p.version, p.created_at
                FROM problems AS p
                WHERE p.status IN ('eligible', 'active', 'revisit_later')
                  AND NOT EXISTS (
                      SELECT 1 FROM problems AS newer
                      WHERE newer.source_id = p.source_id AND newer.version > p.version
                  )
                ORDER BY p.source_id, p.version, p.id
                """
            ).fetchall()
        return tuple(self._problem_from_row(row) for row in rows)

    def list_methods(
        self, statuses: tuple[str, ...] = ("active", "candidate")
    ) -> tuple[MethodVersion, ...]:
        allowed = {"candidate", "active", "retired", "archived"}
        if not statuses or any(
            type(status) is not str or status not in allowed for status in statuses
        ):
            raise ValueError("statuses must contain valid method states")
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id, family, version, spec, parent_id, status, created_at
                FROM methods
                WHERE status = ANY(%(statuses)s)
                ORDER BY family, version, id
                """,
                {"statuses": list(statuses)},
            ).fetchall()
        return tuple(self._method_from_row(row) for row in rows)

    def find_experiment(self, problem_id: UUID, method_id: UUID, seed: int) -> Experiment | None:
        canonical_problem_id = _require_uuid(problem_id, "problem_id")
        canonical_method_id = _require_uuid(method_id, "method_id")
        if type(seed) is not int:
            raise TypeError("seed must be an integer")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id, problem_id, method_id, lane, config, seed, status, created_at
                FROM experiments
                WHERE problem_id = %(problem_id)s AND method_id = %(method_id)s
                  AND seed = %(seed)s
                """,
                {
                    "problem_id": canonical_problem_id,
                    "method_id": canonical_method_id,
                    "seed": seed,
                },
            ).fetchone()
        return None if row is None else self._experiment_from_row(row)

    def find_scheduled_experiment(self, seed: int, lane: str) -> Experiment | None:
        if type(seed) is not int:
            raise TypeError("seed must be an integer")
        canonical_lane = _require_nonempty_string(lane, "lane")
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id, problem_id, method_id, lane, config, seed, status, created_at
                FROM experiments
                WHERE seed = %(seed)s AND lane = %(lane)s
                ORDER BY created_at, id
                LIMIT 2
                """,
                {"seed": seed, "lane": canonical_lane},
            ).fetchall()
        if len(rows) > 1:
            raise ProjectionConflictError("scheduled seed and lane identify multiple experiments")
        return None if not rows else self._experiment_from_row(rows[0])

    def semantic_work_exists(
        self,
        problem_id: UUID,
        method_id: UUID,
        config: Mapping[str, object],
    ) -> bool:
        canonical_problem_id = _require_uuid(problem_id, "problem_id")
        canonical_method_id = _require_uuid(method_id, "method_id")
        if not isinstance(config, Mapping):
            raise TypeError("config must be a mapping")
        with self.database.transaction() as connection:
            method_row = connection.execute(
                "SELECT family FROM methods WHERE id = %(method_id)s",
                {"method_id": canonical_method_id},
            ).fetchone()
            if method_row is None:
                raise MethodNotFoundError(f"method {canonical_method_id} was not found")
            family = str(method_row[0])
            requested = dict(config)
            if family == "integer_counterexample" and self._is_ascending_interval_config(requested):
                rows = connection.execute(
                    """
                    SELECT e.config
                    FROM experiments AS e
                    JOIN methods AS m ON m.id = e.method_id
                    WHERE e.problem_id = %(problem_id)s AND m.family = %(family)s
                      AND m.status = 'active'
                      AND m.spec ? 'provenance'
                      AND e.config ? 'provenance'
                      AND e.config->>'provenance' =
                          m.spec->'provenance'->>'identity_sha256'
                      AND e.lane NOT IN (
                          'verification', 'evolution_holdout', 'routing_holdout'
                      )
                    """,
                    {"problem_id": canonical_problem_id, "family": family},
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT config
                    FROM experiments
                    WHERE problem_id = %(problem_id)s AND method_id = %(method_id)s
                      AND lane NOT IN (
                          'verification', 'evolution_holdout', 'routing_holdout'
                      )
                    """,
                    {
                        "problem_id": canonical_problem_id,
                        "method_id": canonical_method_id,
                    },
                ).fetchall()
        return any(
            isinstance(row[0], dict) and self._semantic_configs_overlap(requested, row[0])
            for row in rows
        )

    @staticmethod
    def _is_ascending_interval_config(config: Mapping[str, object]) -> bool:
        return (
            type(config.get("start")) is int
            and type(config.get("stop")) is int
            and config.get("order") == "ascending"
        )

    @staticmethod
    def _semantic_configs_overlap(left: dict[str, object], right: dict[str, object]) -> bool:
        if left == right:
            return True
        left_start = left.get("start")
        left_stop = left.get("stop")
        right_start = right.get("start")
        right_stop = right.get("stop")
        return (
            type(left_start) is int
            and type(left_stop) is int
            and type(right_start) is int
            and type(right_stop) is int
            and left.get("order") == right.get("order")
            and max(left_start, right_start) < min(left_stop, right_stop)
        )

    def has_terminal_experiment(self, problem_id: UUID, method_id: UUID) -> bool:
        canonical_problem_id = _require_uuid(problem_id, "problem_id")
        canonical_method_id = _require_uuid(method_id, "method_id")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM experiments
                WHERE problem_id = %(problem_id)s AND method_id = %(method_id)s
                  AND (
                      status = 'succeeded'
                      OR (status = 'failed' AND retryable = false)
                  )
                LIMIT 1
                """,
                {
                    "problem_id": canonical_problem_id,
                    "method_id": canonical_method_id,
                },
            ).fetchone()
        return row is not None

    def problem_has_verified_claim(self, problem_id: UUID) -> bool:
        canonical_problem_id = _require_uuid(problem_id, "problem_id")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM claims AS c
                JOIN evaluations AS v ON v.claim_id = c.id
                JOIN experiments AS e ON e.id = c.experiment_id
                JOIN methods AS m ON m.id = e.method_id
                JOIN artifacts AS a ON a.experiment_id = e.id
                JOIN events AS artifact_event
                  ON artifact_event.aggregate_type = 'experiment'
                 AND artifact_event.aggregate_id = e.id
                 AND artifact_event.event_type = 'artifact.stored'
                 AND artifact_event.payload->>'digest' = a.digest
                WHERE c.problem_id = %(problem_id)s
                  AND e.problem_id = c.problem_id
                  AND e.status = 'succeeded'
                  AND e.lane <> 'verification'
                  AND m.status = 'active'
                  AND c.status IN (
                      'machine_verified', 'novelty_checked', 'human_reviewed'
                  )
                  AND v.accepted = true AND v.independent = true
                  AND v.details ? 'provenance'
                  AND e.config ? 'provenance'
                  AND m.spec ? 'provenance'
                  AND e.config->>'provenance' =
                      m.spec->'provenance'->>'identity_sha256'
                  AND artifact_event.payload->>'method_provenance' =
                      m.spec->'provenance'->>'identity_sha256'
                LIMIT 1
                """,
                {"problem_id": canonical_problem_id},
            ).fetchone()
        return row is not None

    def queue_depth(self) -> int:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT count(*) FROM experiments WHERE status IN ('queued', 'leased')"
            ).fetchone()
        return int(row[0]) if row is not None else 0

    def list_lease_workers(self) -> tuple[str, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT payload->>'worker'
                FROM events
                WHERE event_type = 'experiment.leased'
                  AND payload->>'worker' IS NOT NULL
                ORDER BY payload->>'worker'
                """
            ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def list_failures(self) -> tuple[FailureRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT id, problem_id, method_id, failure_kind, failure_message,
                       retryable, attempt
                FROM experiments
                WHERE status = 'failed'
                ORDER BY updated_at, id
                """
            ).fetchall()
        return tuple(
            FailureRecord(
                experiment_id=row[0],
                problem_id=row[1],
                method_id=row[2],
                kind=row[3],
                message=row[4],
                retryable=bool(row[5]),
                attempt=int(row[6]),
            )
            for row in rows
        )

    def requeue_retryable_failures(self) -> int:
        """Make transient failures claimable again without changing identity."""
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT e.id, e.attempt, b.settled_usd, b.execution_dispatched,
                       b.experiment_id
                FROM experiments AS e
                LEFT JOIN budget_reservations AS b ON b.experiment_id = e.id
                WHERE e.status = 'failed' AND e.retryable = true
                FOR UPDATE OF e
                """
            ).fetchall()
            requeued = 0
            for (
                experiment_id,
                attempt,
                settled_usd,
                execution_dispatched,
                reservation_id,
            ) in rows:
                zero_settled = (
                    settled_usd is not None and Decimal(settled_usd) == Decimal("0")
                )
                reopenable = zero_settled and not bool(execution_dispatched)
                if reservation_id is not None and not reopenable:
                    self._append_event(
                        connection,
                        aggregate_type="experiment",
                        aggregate_id=experiment_id,
                        event_type="experiment.retry_blocked_budget",
                        payload={
                            "attempt": int(attempt),
                            "settled_usd": (
                                "unsettled"
                                if settled_usd is None
                                else format(Decimal(settled_usd), "f")
                            ),
                            "policy": "no-automatic-reexecution-after-settlement",
                        },
                        idempotency_key=f"experiment:retry-blocked-budget:{experiment_id}",
                    )
                    continue
                if reopenable:
                    self._append_event(
                        connection,
                        aggregate_type="experiment",
                        aggregate_id=experiment_id,
                        event_type="budget.reservation_reopened",
                        payload={
                            "after_attempt": int(attempt),
                            "settled_usd": "0.000000",
                            "policy": "confirmed-pre-dispatch-zero-cost-retry",
                        },
                        idempotency_key=(
                            f"budget:reservation-reopened:{experiment_id}:{attempt}"
                        ),
                    )
                    connection.execute(
                        """
                        DELETE FROM budget_reservations
                        WHERE experiment_id = %(id)s AND settled_usd = 0
                        """,
                        {"id": experiment_id},
                    )
                _, appended = self._append_event(
                    connection,
                    aggregate_type="experiment",
                    aggregate_id=experiment_id,
                    event_type="experiment.requeued",
                    payload={"after_attempt": int(attempt)},
                    idempotency_key=f"experiment:requeue:{experiment_id}:{attempt}",
                )
                if appended:
                    connection.execute(
                        """
                        UPDATE experiments
                        SET status = 'queued', updated_at = now()
                        WHERE id = %(id)s AND status = 'failed' AND retryable = true
                        """,
                        {"id": experiment_id},
                    )
                    requeued += 1
        return requeued

    def list_candidate_claim_ids(self) -> tuple[UUID, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT c.id
                FROM claims AS c
                JOIN experiments AS e ON e.id = c.experiment_id
                JOIN methods AS m ON m.id = e.method_id
                JOIN artifacts AS a
                  ON a.experiment_id = e.id
                 AND a.experiment_unique_enforced = true
                JOIN events AS artifact_event
                  ON artifact_event.aggregate_type = 'experiment'
                 AND artifact_event.aggregate_id = e.id
                 AND artifact_event.event_type = 'artifact.stored'
                 AND artifact_event.payload->>'digest' = a.digest
                WHERE c.status = 'candidate'
                  AND e.status = 'succeeded'
                  AND e.lane <> 'verification'
                  AND m.status = 'active'
                  AND m.spec ? 'provenance'
                  AND e.config ? 'provenance'
                  AND e.config->>'provenance' =
                      m.spec->'provenance'->>'identity_sha256'
                  AND artifact_event.payload->>'method_provenance' =
                      m.spec->'provenance'->>'identity_sha256'
                ORDER BY c.created_at, c.id
                """
            ).fetchall()
        return tuple(cast(UUID, row[0]) for row in rows)

    def get_claim_artifact(self, claim_id: UUID) -> ArtifactRecord:
        canonical_id = _require_uuid(claim_id, "claim_id")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT a.digest, a.media_type, a.size_bytes, a.relative_path,
                       a.experiment_id
                FROM claims AS c
                JOIN artifacts AS a
                  ON a.experiment_id = c.experiment_id
                 AND a.experiment_unique_enforced = true
                WHERE c.id = %(claim_id)s
                """,
                {"claim_id": canonical_id},
            ).fetchone()
        if row is None:
            raise ClaimNotFoundError(f"claim {canonical_id} has no canonical artifact")
        return ArtifactRecord(
            digest=row[0],
            media_type=row[1],
            size_bytes=int(row[2]),
            relative_path=row[3],
            experiment_id=row[4],
        )

    def list_review_records(self) -> tuple[ReviewRecord, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT c.id, c.problem_id, c.experiment_id, c.claim_type,
                       c.statement, c.witness, c.status, c.evidence_level, c.created_at,
                       p.id, p.source_id, p.source_uri, p.source_hash, p.statement,
                       p.normalized_statement, p.domain, p.features, p.checker,
                       p.status, p.cohort, p.version, p.created_at,
                       a.digest, a.media_type, a.size_bytes, a.relative_path,
                       a.experiment_id,
                       v.verifier, v.verifier_version, v.details
                FROM claims AS c
                JOIN problems AS p ON p.id = c.problem_id
                JOIN artifacts AS a
                  ON a.experiment_id = c.experiment_id
                 AND a.experiment_unique_enforced = true
                JOIN experiments AS e ON e.id = c.experiment_id
                JOIN methods AS m ON m.id = e.method_id
                JOIN events AS artifact_event
                  ON artifact_event.aggregate_type = 'experiment'
                 AND artifact_event.aggregate_id = e.id
                 AND artifact_event.event_type = 'artifact.stored'
                 AND artifact_event.payload->>'digest' = a.digest
                JOIN LATERAL (
                    SELECT verifier, verifier_version, details
                    FROM evaluations
                    WHERE claim_id = c.id AND accepted = true AND independent = true
                      AND details ? 'provenance'
                    ORDER BY created_at, id
                    LIMIT 1
                ) AS v ON true
                WHERE c.status IN (
                    'machine_verified', 'novelty_checked', 'human_reviewed'
                )
                  AND e.status = 'succeeded'
                  AND e.lane <> 'verification'
                  AND m.status = 'active'
                  AND e.config ? 'provenance'
                  AND m.spec ? 'provenance'
                  AND e.config->>'provenance' =
                      m.spec->'provenance'->>'identity_sha256'
                  AND artifact_event.payload->>'method_provenance' =
                      m.spec->'provenance'->>'identity_sha256'
                ORDER BY p.source_id, p.version, c.created_at, c.id
                """
            ).fetchall()
        records: list[ReviewRecord] = []
        for row in rows:
            records.append(
                ReviewRecord(
                    claim=self._claim_from_row(row[0:9]),
                    problem=self._problem_from_row(row[9:22]),
                    artifact=ArtifactRecord(
                        digest=row[22],
                        media_type=row[23],
                        size_bytes=int(row[24]),
                        relative_path=row[25],
                        experiment_id=row[26],
                    ),
                    verifier=row[27],
                    verifier_version=row[28],
                    verification_details=row[29],
                )
            )
        return tuple(records)

    def record_metric(self, name: str, payload: dict[str, object], idempotency_key: str) -> None:
        canonical_name = _require_nonempty_string(name, "name")
        canonical_key = _require_nonempty_string(idempotency_key, "idempotency_key")
        aggregate_id = uuid4()
        with self.database.transaction() as connection:
            existing = connection.execute(
                "SELECT aggregate_id FROM events WHERE idempotency_key = %(key)s",
                {"key": canonical_key},
            ).fetchone()
            if existing is not None:
                aggregate_id = existing[0]
            self._append_event(
                connection,
                aggregate_type="runtime",
                aggregate_id=aggregate_id,
                event_type=canonical_name,
                payload=payload,
                idempotency_key=canonical_key,
            )

    def metrics_snapshot(self) -> dict[str, object]:
        """Return JSON-safe aggregate metrics from canonical projections and events."""
        with self.database.transaction() as connection:
            problem_rows = connection.execute(
                """
                SELECT cohort, domain, count(*)
                FROM problems
                GROUP BY cohort, domain
                ORDER BY cohort, domain
                """
            ).fetchall()
            method_rows = connection.execute(
                """
                SELECT m.family, m.version, COALESCE(sum(e.attempt), 0),
                       COALESCE(sum(
                           CASE WHEN b.settled_usd IS NOT NULL
                                THEN b.settled_usd ELSE e.cost_usd END
                       ), 0)
                FROM methods AS m
                LEFT JOIN experiments AS e
                  ON e.method_id = m.id AND e.config ? 'provenance'
                LEFT JOIN budget_reservations AS b ON b.experiment_id = e.id
                WHERE m.spec ? 'provenance'
                GROUP BY m.id, m.family, m.version
                ORDER BY m.family, m.version
                """
            ).fetchall()
            verification_row = connection.execute(
                """
                SELECT count(*), count(*) FILTER (WHERE accepted),
                       count(*) FILTER (WHERE NOT accepted)
                FROM evaluations
                WHERE independent = true AND details ? 'provenance'
                """
            ).fetchone()
            experiment_row = connection.execute(
                """
                SELECT count(*) FROM experiments
                WHERE lane NOT IN (
                    'verification', 'evolution_holdout', 'routing_holdout'
                )
                """
            ).fetchone()
            semantic_work_rows = connection.execute(
                """
                SELECT e.problem_id, e.method_id, m.family, e.config
                FROM experiments AS e
                JOIN methods AS m ON m.id = e.method_id
                WHERE lane NOT IN (
                    'verification', 'evolution_holdout', 'routing_holdout'
                )
                ORDER BY e.created_at, e.id
                """
            ).fetchall()
            suppressed_row = connection.execute(
                """
                SELECT count(*)
                FROM events
                WHERE event_type = 'scheduler.duplicate_work_suppressed'
                """
            ).fetchone()
            lane_rows = connection.execute(
                "SELECT lane, count(*) FROM experiments GROUP BY lane ORDER BY lane"
            ).fetchall()
            unfilled_rows = connection.execute(
                """
                SELECT payload->>'lane', count(*)
                FROM events
                WHERE event_type = 'scheduler.lane_unfilled'
                GROUP BY payload->>'lane'
                ORDER BY payload->>'lane'
                """
            ).fetchall()
            holdout_rows = connection.execute(
                """
                WITH holdout_execution AS (
                    SELECT m.family, m.version, e.id, e.attempt,
                           CASE WHEN b.settled_usd IS NOT NULL
                                THEN b.settled_usd ELSE e.cost_usd END AS effective_cost,
                           CASE WHEN EXISTS (
                               SELECT 1 FROM claims AS c
                               JOIN evaluations AS v ON v.claim_id = c.id
                               WHERE c.experiment_id = e.id
                                 AND v.independent = true AND v.accepted = true
                           ) THEN 1 ELSE 0 END AS verified
                    FROM experiments AS e
                    JOIN methods AS m ON m.id = e.method_id
                    JOIN problems AS p ON p.id = e.problem_id
                    LEFT JOIN budget_reservations AS b ON b.experiment_id = e.id
                    WHERE p.cohort = 'holdout'
                      AND m.spec ? 'provenance'
                      AND e.config ? 'provenance'
                )
                SELECT family, version, sum(attempt), sum(verified), sum(effective_cost)
                FROM holdout_execution
                GROUP BY family, version
                ORDER BY family, version
                """
            ).fetchall()
            paired_holdout_rows = connection.execute(
                """
                SELECT e.config->>'evaluation_pair',
                       e.config->>'evaluation_policy',
                       m.family, m.version,
                       count(*),
                       sum(e.attempt),
                       sum(
                           GREATEST(
                               (e.config->>'stop')::bigint
                               - (e.config->>'start')::bigint,
                               0
                           ) * e.attempt
                       ),
                       sum(
                           CASE WHEN EXISTS (
                               SELECT 1 FROM claims AS c
                               JOIN evaluations AS v ON v.claim_id = c.id
                               WHERE c.experiment_id = e.id
                                 AND v.independent = true AND v.accepted = true
                           ) THEN 1 ELSE 0 END
                       ),
                       sum(
                           CASE WHEN b.settled_usd IS NOT NULL
                                THEN b.settled_usd ELSE e.cost_usd END
                       )
                FROM experiments AS e
                JOIN methods AS m ON m.id = e.method_id
                LEFT JOIN budget_reservations AS b ON b.experiment_id = e.id
                WHERE e.lane = 'evolution_holdout'
                  AND m.spec ? 'provenance'
                  AND e.config ? 'provenance'
                GROUP BY e.config->>'evaluation_pair',
                         e.config->>'evaluation_policy',
                         m.family, m.version
                ORDER BY e.config->>'evaluation_pair',
                         e.config->>'evaluation_policy'
                """
            ).fetchall()
            routing_holdout_rows = connection.execute(
                """
                SELECT e.config->>'routing_pair',
                       e.config->>'routing_policy',
                       m.family, m.version,
                       count(*),
                       sum(e.attempt),
                       sum(
                           (e.config->>'allocation_units')::bigint * e.attempt
                       ),
                       sum(
                           CASE WHEN EXISTS (
                               SELECT 1 FROM claims AS c
                               JOIN evaluations AS v ON v.claim_id = c.id
                               WHERE c.experiment_id = e.id
                                 AND v.independent = true AND v.accepted = true
                           ) THEN 1 ELSE 0 END
                       ),
                       sum(
                           CASE WHEN b.settled_usd IS NOT NULL
                                THEN b.settled_usd ELSE e.cost_usd END
                       )
                FROM experiments AS e
                JOIN methods AS m ON m.id = e.method_id
                LEFT JOIN budget_reservations AS b ON b.experiment_id = e.id
                WHERE e.lane = 'routing_holdout'
                  AND m.spec ? 'provenance'
                  AND e.config ? 'provenance'
                GROUP BY e.config->>'routing_pair',
                         e.config->>'routing_policy',
                         m.family, m.version
                ORDER BY e.config->>'routing_pair',
                         e.config->>'routing_policy'
                """
            ).fetchall()
            legacy_unreproducible_row = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM methods WHERE NOT (spec ? 'provenance')),
                    (
                        SELECT count(*)
                        FROM experiments AS e
                        JOIN methods AS m ON m.id = e.method_id
                        WHERE NOT (m.spec ? 'provenance')
                           OR NOT (e.config ? 'provenance')
                    ),
                    (
                        SELECT count(DISTINCT c.id)
                        FROM claims AS c
                        JOIN experiments AS e ON e.id = c.experiment_id
                        JOIN methods AS m ON m.id = e.method_id
                        LEFT JOIN evaluations AS v ON v.claim_id = c.id
                        WHERE NOT (m.spec ? 'provenance')
                           OR NOT (e.config ? 'provenance')
                           OR (
                               v.id IS NOT NULL
                               AND NOT (v.details ? 'provenance')
                           )
                    )
                """
            ).fetchone()
        total_verifications = int(verification_row[0]) if verification_row else 0
        accepted = int(verification_row[1]) if verification_row else 0
        rejected = int(verification_row[2]) if verification_row else 0
        experiments = int(experiment_row[0]) if experiment_row else 0
        suppressed = int(suppressed_row[0]) if suppressed_row else 0
        work_opportunities = experiments + suppressed
        prior_work: dict[tuple[UUID, str], list[dict[str, object]]] = {}
        duplicate_experiments = 0
        for problem_id, method_id, method_family, config in semantic_work_rows:
            if not isinstance(config, dict):
                continue
            scope = (
                f"family:{method_family}"
                if method_family == "integer_counterexample"
                and self._is_ascending_interval_config(config)
                else f"method:{method_id}"
            )
            pair = (cast(UUID, problem_id), scope)
            prior_configs = prior_work.setdefault(pair, [])
            if any(self._semantic_configs_overlap(config, prior) for prior in prior_configs):
                duplicate_experiments += 1
            prior_configs.append(config)
        evolution_results = [
            {
                "pair_id": row[0],
                "policy": row[1],
                "method": f"{row[2]}:v{row[3]}",
                "experiments": int(row[4]),
                "attempts": int(row[5]),
                "work_units": int(row[6]),
                "verified": int(row[7]),
                "cost_usd": format(Decimal(row[8]), "f"),
            }
            for row in paired_holdout_rows
        ]
        routing_results = [
            {
                "pair_id": row[0],
                "policy": row[1],
                "selected_method": f"{row[2]}:v{row[3]}",
                "experiments": int(row[4]),
                "attempts": int(row[5]),
                "allocation_units": int(row[6]),
                "verified": int(row[7]),
                "cost_usd": format(Decimal(row[8]), "f"),
            }
            for row in routing_holdout_rows
        ]
        policy_totals: dict[str, tuple[int, int]] = {}
        for result in routing_results:
            policy = cast(str, result["policy"])
            attempts, verified = policy_totals.get(policy, (0, 0))
            policy_totals[policy] = (
                attempts + cast(int, result["attempts"]),
                verified + cast(int, result["verified"]),
            )
        observed_lift: dict[str, object] | None = None
        if {"static_routing", "adaptive_routing"} <= policy_totals.keys():
            fixed_attempts, fixed_verified = policy_totals["static_routing"]
            adaptive_attempts, adaptive_verified = policy_totals[
                "adaptive_routing"
            ]
            if fixed_attempts > 0 and adaptive_attempts > 0:
                fixed_rate = Decimal(fixed_verified) / Decimal(fixed_attempts)
                adaptive_rate = Decimal(adaptive_verified) / Decimal(
                    adaptive_attempts
                )
                observed_lift = {
                    "metric": "verified_per_attempt",
                    "fixed": format(fixed_rate, "f"),
                    "adaptive": format(adaptive_rate, "f"),
                    "absolute": format(adaptive_rate - fixed_rate, "f"),
                }
        return {
            "problem_counts": {f"{row[0]}:{row[1]}": int(row[2]) for row in problem_rows},
            "legacy_unreproducible": (
                {
                    "methods": int(legacy_unreproducible_row[0]),
                    "experiments": int(legacy_unreproducible_row[1]),
                    "claims": int(legacy_unreproducible_row[2]),
                }
                if legacy_unreproducible_row is not None
                else {"methods": 0, "experiments": 0, "claims": 0}
            ),
            "attempts_cost_by_method": {
                f"{row[0]}:v{row[1]}": {
                    "attempts": int(row[2]),
                    "cost_usd": format(Decimal(row[3]), "f"),
                }
                for row in method_rows
            },
            "verification_rate": (
                format(Decimal(accepted) / Decimal(total_verifications), "f")
                if total_verifications
                else "0"
            ),
            "false_positive_rate": (
                format(Decimal(rejected) / Decimal(total_verifications), "f")
                if total_verifications
                else "0"
            ),
            "duplicate_work_rate": (
                format(Decimal(duplicate_experiments) / Decimal(experiments), "f")
                if experiments
                else "0"
            ),
            "semantic_duplicates_suppressed": suppressed,
            "duplicate_suppression_rate": (
                format(Decimal(suppressed) / Decimal(work_opportunities), "f")
                if work_opportunities
                else "0"
            ),
            "lane_allocation": {row[0]: int(row[1]) for row in lane_rows},
            "unfilled_lanes": {row[0]: int(row[1]) for row in unfilled_rows},
            "holdout_by_method_version": {
                f"{row[0]}:v{row[1]}": {
                    "attempts": int(row[2]),
                    "verified": int(row[3]),
                    "cost_usd": format(Decimal(row[4]), "f"),
                }
                for row in holdout_rows
            },
            "method_evolution_holdout": {
                "status": (
                    "measured"
                    if paired_holdout_rows
                    and all(int(row[5]) > 0 for row in paired_holdout_rows)
                    else (
                        "evaluation_scheduled"
                        if paired_holdout_rows
                        else "insufficient_data"
                    )
                ),
                "results": evolution_results,
            },
            "static_vs_adaptive_routing_holdout": {
                "status": (
                    "measured"
                    if routing_holdout_rows
                    and all(int(row[5]) > 0 for row in routing_holdout_rows)
                    else (
                        "evaluation_scheduled"
                        if routing_holdout_rows
                        else "insufficient_data"
                    )
                ),
                "results": routing_results,
                "observed_lift": observed_lift,
            },
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
        self, experiment_id: UUID, amount_usd: Decimal, daily_limit_usd: Decimal
    ) -> bool:
        canonical_id = _require_uuid(experiment_id, "experiment_id")
        amount = _require_database_usd(amount_usd, "amount_usd")
        limit = _require_database_usd(daily_limit_usd, "daily_limit_usd")
        event_payload: dict[str, object] = {
            "amount_usd": format(amount, "f"),
            "daily_limit_usd": format(limit, "f"),
        }
        with self.database.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtext(CURRENT_DATE::text))")
            attempt_row = connection.execute(
                "SELECT attempt FROM experiments WHERE id = %(id)s",
                {"id": canonical_id},
            ).fetchone()
            attempt = int(attempt_row[0]) if attempt_row is not None else 0
            event_payload["attempt"] = attempt
            existing = connection.execute(
                "SELECT experiment_id FROM budget_reservations WHERE experiment_id = %(id)s",
                {"id": canonical_id},
            ).fetchone()
            if existing is not None:
                self._append_event(
                    connection,
                    aggregate_type="experiment",
                    aggregate_id=canonical_id,
                    event_type="budget.reserved",
                    payload=event_payload,
                    idempotency_key=f"budget:reserve:{canonical_id}:{attempt}",
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
                aggregate_id=canonical_id,
                event_type="budget.reserved",
                payload=event_payload,
                idempotency_key=f"budget:reserve:{canonical_id}:{attempt}",
            )
            connection.execute(
                """
                INSERT INTO budget_reservations (experiment_id, reserved_usd)
                VALUES (%(id)s, %(amount)s)
                """,
                {"id": canonical_id, "amount": amount},
            )
            return True

    def find_budget_reservation(self, experiment_id: UUID) -> BudgetReservationRecord | None:
        canonical_id = _require_uuid(experiment_id, "experiment_id")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT experiment_id, reserved_usd, settled_usd, execution_dispatched
                FROM budget_reservations
                WHERE experiment_id = %(id)s
                """,
                {"id": canonical_id},
            ).fetchone()
        if row is None:
            return None
        return BudgetReservationRecord(
            experiment_id=row[0],
            reserved_usd=Decimal(row[1]),
            settled_usd=None if row[2] is None else Decimal(row[2]),
            execution_dispatched=bool(row[3]),
        )

    def get_budget_reservation(self, experiment_id: UUID) -> BudgetReservationRecord:
        reservation = self.find_budget_reservation(experiment_id)
        if reservation is None:
            raise ValueError("experiment has no budget reservation")
        return reservation

    def mark_budget_execution_dispatched(self, experiment_id: UUID) -> None:
        canonical_id = _require_uuid(experiment_id, "experiment_id")
        with self.database.transaction() as connection:
            reservation = connection.execute(
                """
                SELECT b.settled_usd, b.execution_dispatched, COALESCE(e.attempt, 0)
                FROM budget_reservations AS b
                LEFT JOIN experiments AS e ON e.id = b.experiment_id
                WHERE b.experiment_id = %(id)s
                FOR UPDATE OF b
                """,
                {"id": canonical_id},
            ).fetchone()
            if reservation is None:
                raise ValueError("experiment has no budget reservation")
            if reservation[0] is not None:
                raise ValueError("settled external reservation cannot be dispatched")
            _, appended = self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=canonical_id,
                event_type="budget.execution_dispatched",
                payload={
                    "policy": "conservative-external-dispatch",
                    "attempt": int(reservation[2]),
                },
                idempotency_key=(
                    f"budget:execution-dispatched:{canonical_id}:{int(reservation[2])}"
                ),
            )
            if appended:
                connection.execute(
                    """
                    UPDATE budget_reservations
                    SET execution_dispatched = true
                    WHERE experiment_id = %(id)s
                    """,
                    {"id": canonical_id},
                )

    def settle_budget(self, experiment_id: UUID, actual_usd: Decimal) -> None:
        canonical_id = _require_uuid(experiment_id, "experiment_id")
        amount = _require_database_usd(actual_usd, "actual_usd")
        with self.database.transaction() as connection:
            reservation = connection.execute(
                """
                SELECT b.reserved_usd, b.budget_day, COALESCE(e.attempt, 0)
                FROM budget_reservations AS b
                LEFT JOIN experiments AS e ON e.id = b.experiment_id
                WHERE b.experiment_id = %(id)s
                """,
                {"id": canonical_id},
            ).fetchone()
            if reservation is None:
                raise ValueError("experiment has no budget reservation")
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%(budget_day)s::text))",
                {"budget_day": reservation[1]},
            )
            reservation = connection.execute(
                """
                SELECT b.reserved_usd, b.budget_day, COALESCE(e.attempt, 0)
                FROM budget_reservations AS b
                LEFT JOIN experiments AS e ON e.id = b.experiment_id
                WHERE b.experiment_id = %(id)s
                FOR UPDATE OF b
                """,
                {"id": canonical_id},
            ).fetchone()
            if reservation is None:
                raise ValueError("experiment has no budget reservation")
            if amount > reservation[0]:
                raise ValueError("actual cost exceeds the reserved maximum")
            _, appended = self._append_event(
                connection,
                aggregate_type="experiment",
                aggregate_id=canonical_id,
                event_type="budget.settled",
                payload={
                    "actual_usd": format(amount, "f"),
                    "attempt": int(reservation[2]),
                },
                idempotency_key=f"budget:settle:{canonical_id}:{int(reservation[2])}",
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
                {"id": canonical_id, "amount": amount},
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
