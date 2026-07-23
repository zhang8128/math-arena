from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from mathloop.artifacts import ArtifactStore
from mathloop.billing import BillingAuthorization, BillingReceipt
from mathloop.config import Settings
from mathloop.domain import Experiment, ExperimentStatus, MethodVersion, Problem, ProblemStatus
from mathloop.methods.base import MethodContext, MethodRegistry, MethodResult
from mathloop.provenance import component_provenance
from mathloop.storage.repository import Repository
from mathloop.worker import ExecutionFailed, ExecutionOutcome, Worker


def _authorization() -> BillingAuthorization:
    return BillingAuthorization(
        provider="test",
        model="test-model",
        authorized_input_tokens=10,
        max_output_tokens=10,
        reserved_cost_usd=Decimal("0.400000"),
        pricing_version="test-v1",
        pricing_source="local://pricing",
    )


class ExternalSuccessMethod:
    family = "fake_external"

    def run(self, context: MethodContext) -> MethodResult:
        context.mark_external_execution_started()
        authorization = _authorization()
        receipt = BillingReceipt(
            provider="test",
            model="test-model",
            response_id="response-1",
            input_tokens=10,
            output_tokens=2,
            cached_input_tokens=0,
            cache_write_input_tokens=0,
            actual_cost_usd=Decimal("0.125000"),
            pricing_version="test-v1",
            pricing_source="local://pricing",
            authorization=authorization,
        )
        return MethodResult(
            status="lead",
            summary="external proposal",
            artifact=b"proposal",
            billing_authorization=authorization,
            billing_receipt=receipt,
        )


class ExternalFailureMethod:
    family = "fake_external"

    def run(self, context: MethodContext) -> MethodResult:
        context.mark_external_execution_started()
        raise TimeoutError("provider timed out after response parsing")


class PreStartFailureMethod:
    family = "fake_external"

    def run(self, context: MethodContext) -> MethodResult:
        raise ValueError("invalid method configuration")


class MissingReceiptMethod:
    family = "fake_external"

    def run(self, context: MethodContext) -> MethodResult:
        context.mark_external_execution_started()
        return MethodResult(status="lead", summary="receipt missing")


class OverReserveReceiptMethod:
    family = "fake_external"

    def run(self, context: MethodContext) -> MethodResult:
        context.mark_external_execution_started()
        authorization = BillingAuthorization(
            provider="test",
            model="test-model",
            authorized_input_tokens=10,
            max_output_tokens=10,
            reserved_cost_usd=Decimal("0.600000"),
            pricing_version="test-v1",
            pricing_source="local://pricing",
        )
        receipt = BillingReceipt(
            provider="test",
            model="test-model",
            response_id="response-over-reserve",
            input_tokens=10,
            output_tokens=1,
            cached_input_tokens=0,
            cache_write_input_tokens=0,
            actual_cost_usd=Decimal("0.100000"),
            pricing_version="test-v1",
            pricing_source="local://pricing",
            authorization=authorization,
        )
        return MethodResult(
            status="lead",
            summary="authorization exceeds worker reserve",
            billing_authorization=authorization,
            billing_receipt=receipt,
        )


class MustNotRunMethod:
    family = "fake_external"

    def run(self, context: MethodContext) -> MethodResult:
        marker = Path(str(context.config["marker_path"]))
        marker.write_text("executed")
        raise AssertionError("budget denial must prevent execution")


class StartFailureThenSuccessBoundary:
    def __init__(self) -> None:
        self.calls = 0

    def run(
        self,
        method: object,
        context: MethodContext,
        *,
        timeout_seconds: float,
        external_started_callback: Callable[[], None] | None = None,
    ) -> ExecutionOutcome:
        del timeout_seconds, external_started_callback
        self.calls += 1
        if self.calls == 1:
            raise ExecutionFailed(
                OSError("forkserver process start failed"),
                external_execution_started=False,
            )
        result = method.run(context)  # type: ignore[attr-defined]
        return ExecutionOutcome(result, external_execution_started=True)


def _settings(tmp_path: Path, *, daily_budget: Decimal = Decimal("1.000000")) -> Settings:
    return Settings(
        artifact_root=tmp_path / "artifacts",
        incoming_root=tmp_path / "incoming",
        daily_api_budget_usd=daily_budget,
        max_experiment_seconds=2,
        lease_seconds=3,
        max_api_cost_usd_per_experiment=Decimal("0.500000"),
    )


def _enqueue_external(repository: Repository, config: dict[str, object]) -> Experiment:
    provenance = _test_provenance()
    problem = Problem(
        id=uuid4(),
        source_id=f"test/{uuid4()}",
        source_uri="local://worker-billing",
        source_hash=uuid4().hex * 2,
        statement="test",
        normalized_statement="test",
        domain="testing",
        features={},
        checker={"kind": "unsupported"},
        status=ProblemStatus.ELIGIBLE,
        cohort="development",
        version=1,
        created_at=datetime.now(UTC),
    )
    method = MethodVersion(
        id=uuid4(),
        family="fake_external",
        version=1,
        spec={
            "external_provider": "test",
            "max_api_cost_usd_per_experiment": "0.500000",
            "provenance": provenance,
        },
        status="active",
        created_at=datetime.now(UTC),
    )
    experiment = Experiment(
        id=uuid4(),
        problem_id=problem.id,
        method_id=method.id,
        lane="novelty",
        config={**config, "provenance": provenance["identity_sha256"]},
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.add_problem(problem, f"problem:{problem.id}")
    repository.register_method(method, f"method:{method.id}")
    repository.enqueue(experiment, f"experiment:{experiment.id}")
    return experiment


def _worker(
    repository: Repository,
    tmp_path: Path,
    method: object,
    *,
    daily_budget: Decimal = Decimal("1.000000"),
) -> Worker:
    provenance = _test_provenance()
    methods = MethodRegistry()
    methods.register(method, provenance=provenance)  # type: ignore[arg-type]
    return Worker(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        methods,
        _settings(tmp_path, daily_budget=daily_budget),
    )


def _test_provenance() -> dict[str, object]:
    return component_provenance(
        "method:fake_external",
        "tests/integration/test_worker_billing.py",
    )


def test_successful_external_receipt_settles_actual_exact_cost(
    repository: Repository, tmp_path: Path
) -> None:
    experiment = _enqueue_external(repository, {})

    assert _worker(repository, tmp_path, ExternalSuccessMethod()).run_once("worker")

    assert repository.get_experiment(experiment.id).status is ExperimentStatus.SUCCEEDED
    reservation = repository.get_budget_reservation(experiment.id)
    assert reservation.reserved_usd == Decimal("0.500000")
    assert reservation.settled_usd == Decimal("0.125000")


def test_started_external_failure_conservatively_settles_full_reserve(
    repository: Repository, tmp_path: Path
) -> None:
    experiment = _enqueue_external(repository, {})

    assert _worker(repository, tmp_path, ExternalFailureMethod()).run_once("worker")

    failure = repository.list_failures()[0]
    assert failure.experiment_id == experiment.id
    assert failure.kind == "infrastructure"
    assert failure.retryable is True
    reservation = repository.get_budget_reservation(experiment.id)
    assert reservation.settled_usd == Decimal("0.500000")
    assert repository.requeue_retryable_failures() == 0
    assert not _worker(repository, tmp_path, ExternalFailureMethod()).run_once("retry-worker")
    assert repository.count_events("experiment.retry_blocked_budget") == 1
    report = repository.metrics_snapshot()["attempts_cost_by_method"]
    assert report["fake_external:v1"] == {
        "attempts": 1,
        "cost_usd": "0.500000",
    }


def test_pre_dispatch_zero_settlement_retries_with_fresh_reservation(
    repository: Repository,
    tmp_path: Path,
) -> None:
    experiment = _enqueue_external(repository, {})
    worker = _worker(repository, tmp_path, ExternalSuccessMethod())
    boundary = StartFailureThenSuccessBoundary()
    worker.execution_boundary = boundary  # type: ignore[assignment]

    assert worker.run_once("first-worker")
    first_reservation = repository.get_budget_reservation(experiment.id)
    assert first_reservation.settled_usd == Decimal("0.000000")

    assert repository.requeue_retryable_failures() == 1
    assert worker.run_once("retry-worker")

    canonical = repository.get_experiment(experiment.id)
    assert canonical.status is ExperimentStatus.SUCCEEDED
    reservation = repository.get_budget_reservation(experiment.id)
    assert reservation.settled_usd == Decimal("0.125000")
    assert repository.count_events("budget.reserved") == 2
    assert repository.count_events("budget.reservation_reopened") == 1
    report = repository.metrics_snapshot()["attempts_cost_by_method"]
    assert report["fake_external:v1"] == {
        "attempts": 2,
        "cost_usd": "0.125000",
    }


def test_dispatch_marker_failure_keeps_provider_attempt_zero_safe(
    repository: Repository,
    tmp_path: Path,
    monkeypatch,
) -> None:
    experiment = _enqueue_external(repository, {})
    worker = _worker(repository, tmp_path, ExternalSuccessMethod())

    def fail_dispatch_marker(_experiment_id) -> None:
        raise OSError("database unavailable before dispatch commit")

    monkeypatch.setattr(
        repository,
        "mark_budget_execution_dispatched",
        fail_dispatch_marker,
    )

    assert worker.run_once("worker")

    reservation = repository.get_budget_reservation(experiment.id)
    assert reservation.execution_dispatched is False
    assert reservation.settled_usd == Decimal("0")
    with repository.database.transaction() as connection:
        failure = connection.execute(
            "SELECT retryable FROM experiments WHERE id = %(id)s",
            {"id": experiment.id},
        ).fetchone()
    assert failure == (True,)
    assert repository.requeue_retryable_failures() == 1
    assert repository.find_budget_reservation(experiment.id) is None


def test_dispatched_zero_settlement_cannot_be_reexecuted(
    repository: Repository,
) -> None:
    experiment = _enqueue_external(repository, {})
    now = datetime.now(UTC)
    claimed = repository.claim_next("worker", now, 30)
    assert claimed is not None
    assert repository.reserve_daily_budget(
        experiment.id,
        Decimal("0.500000"),
        Decimal("1.000000"),
    )
    repository.mark_budget_execution_dispatched(experiment.id)
    repository.settle_budget(experiment.id, Decimal("0"))
    repository.fail(
        experiment.id,
        "worker",
        "infrastructure",
        "dispatched transport failed at zero billed cost",
        retryable=True,
        now=now + timedelta(seconds=1),
    )

    assert repository.requeue_retryable_failures() == 0
    assert repository.get_budget_reservation(experiment.id).execution_dispatched is True
    assert repository.count_events("experiment.retry_blocked_budget") == 1


def test_metrics_count_canonical_attempts_instead_of_experiment_rows(
    repository: Repository,
) -> None:
    experiment = _enqueue_external(repository, {})
    started = datetime.now(UTC)
    first = repository.claim_next("attempt-one", started, 30)
    assert first is not None
    repository.fail(
        experiment.id,
        "attempt-one",
        "infrastructure",
        "retryable before dispatch",
        retryable=True,
        now=started + timedelta(seconds=1),
    )
    assert repository.requeue_retryable_failures() == 1
    second = repository.claim_next("attempt-two", started + timedelta(seconds=2), 30)
    assert second is not None
    repository.fail(
        experiment.id,
        "attempt-two",
        "method",
        "permanent",
        retryable=False,
        now=started + timedelta(seconds=3),
    )

    report = repository.metrics_snapshot()["attempts_cost_by_method"]
    assert report["fake_external:v1"]["attempts"] == 2


def test_missing_canonical_references_fail_permanently_instead_of_lease_looping(
    repository: Repository,
    tmp_path: Path,
) -> None:
    experiment = Experiment(
        id=uuid4(),
        problem_id=uuid4(),
        method_id=uuid4(),
        lane="novelty",
        config={},
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(experiment, f"experiment:{experiment.id}")

    assert _worker(repository, tmp_path, ExternalSuccessMethod()).run_once("worker")

    canonical = repository.get_experiment(experiment.id)
    assert canonical.status is ExperimentStatus.FAILED
    failure = repository.list_failures()[0]
    assert failure.kind == "projection"
    assert failure.retryable is False


def test_budget_denial_happens_before_external_execution(
    repository: Repository, tmp_path: Path
) -> None:
    assert repository.reserve_daily_budget(
        uuid4(),
        Decimal("0.800000"),
        Decimal("1.000000"),
    )
    marker = tmp_path / "must-not-exist"
    experiment = _enqueue_external(repository, {"marker_path": str(marker)})

    assert _worker(repository, tmp_path, MustNotRunMethod()).run_once("worker")

    assert not marker.exists()
    failure = repository.list_failures()[0]
    assert failure.experiment_id == experiment.id
    assert failure.kind == "budget"
    assert repository.find_budget_reservation(experiment.id) is None


def test_dispatched_unsettled_external_attempt_is_full_settled_on_reclaim(
    repository: Repository, tmp_path: Path
) -> None:
    marker = tmp_path / "reclaimed-must-not-run"
    experiment = _enqueue_external(repository, {"marker_path": str(marker)})
    claimed_at = datetime.now(UTC) - timedelta(seconds=10)
    claimed = repository.claim_next("crashed-parent", claimed_at, lease_seconds=1)
    assert claimed is not None
    assert repository.reserve_daily_budget(
        experiment.id,
        Decimal("0.500000"),
        Decimal("1.000000"),
    )
    repository.mark_budget_execution_dispatched(experiment.id)

    assert _worker(repository, tmp_path, MustNotRunMethod()).run_once("reclaimer")

    assert not marker.exists()
    reservation = repository.get_budget_reservation(experiment.id)
    assert reservation.execution_dispatched is True
    assert reservation.settled_usd == Decimal("0.500000")
    failure = repository.list_failures()[0]
    assert failure.kind == "billing"
    assert failure.retryable is False
    assert repository.count_events("experiment.retry_blocked_budget") == 1


def test_pre_start_failure_settles_zero_without_inventing_spend(
    repository: Repository, tmp_path: Path
) -> None:
    experiment = _enqueue_external(repository, {})

    assert _worker(repository, tmp_path, PreStartFailureMethod()).run_once("worker")

    failure = repository.list_failures()[0]
    assert failure.kind == "method"
    assert failure.retryable is False
    assert repository.get_budget_reservation(experiment.id).settled_usd == Decimal("0.000000")


def test_started_execution_missing_receipt_is_full_settled_and_failed(
    repository: Repository, tmp_path: Path
) -> None:
    experiment = _enqueue_external(repository, {})

    assert _worker(repository, tmp_path, MissingReceiptMethod()).run_once("worker")

    failure = repository.list_failures()[0]
    assert failure.kind == "method"
    assert failure.retryable is False
    assert repository.get_budget_reservation(experiment.id).settled_usd == Decimal("0.500000")


def test_receipt_authorization_must_fit_worker_reserve(
    repository: Repository, tmp_path: Path
) -> None:
    experiment = _enqueue_external(repository, {})

    assert _worker(repository, tmp_path, OverReserveReceiptMethod()).run_once("worker")

    failure = repository.list_failures()[0]
    assert failure.kind == "method"
    assert failure.retryable is False
    assert repository.get_budget_reservation(experiment.id).settled_usd == Decimal("0.500000")
