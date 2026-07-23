import hashlib
import json
import os
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from multiprocessing.connection import Connection
from pathlib import Path
from threading import Barrier
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from mathloop.artifacts import ArtifactStore
from mathloop.config import Settings
from mathloop.domain import (
    CandidateClaim,
    ClaimStatus,
    ClaimType,
    EvidenceLevel,
    Experiment,
    ExperimentStatus,
    MethodVersion,
    Problem,
    ProblemStatus,
)
from mathloop.evolution import MethodMetrics, MetricsCohort
from mathloop.predicates.base import PredicateEvaluation, PredicateRegistry
from mathloop.provenance import method_provenance, provenance_digest
from mathloop.runtime import build_runtime
from mathloop.storage.repository import Repository


class ExactSymbolicRunner:
    def run_json(self, payload: dict[str, object]) -> dict[str, object]:
        if payload in (
            {"operation": "verify_sum_odds_induction"},
            {"operation": "verify_sum_integers_induction"},
        ):
            return {"ok": True, "base": True, "step": True}
        assert payload.get("operation") == "find_integer_counterexample"
        start = int(payload["start"])
        stop = int(payload["stop"])
        values = range(start, stop)
        if payload["order"] == "boundary_first":
            values = range(stop - 1, start - 1, -1)
        for n in values:
            predicate_id = payload["predicate_id"]
            if predicate_id == "euler_prime":
                value = n * n + n + 41
                holds = n != 40
            elif predicate_id == "fermat_prime":
                value = 2 ** (2**n) + 1
                holds = n != 5
            elif predicate_id == "quadratic_two_prime":
                value = n * n + n + 2
                holds = value % 2 != 0
            elif predicate_id == "quadratic_three_prime":
                value = n * n + n + 3
                holds = value % 3 != 0
            else:
                value = n * n
                holds = True
            if not holds:
                return {"ok": True, "found": True, "n": n, "value": value}
        return {"ok": True, "found": False}


def _defective_euler_evaluation(n: int) -> PredicateEvaluation:
    value = n * n + n + 41
    return PredicateEvaluation(holds=n != 0, value=value)


def _build_defective_euler_registry() -> PredicateRegistry:
    registry = PredicateRegistry()
    registry.register("euler_prime", _defective_euler_evaluation)
    return registry


def _crash_after_starting_detached_execution_group(
    settings_payload: Settings,
    artifact_root: str,
    api_enabled: bool,
    cycle_number: int,
    process_index: int,
    quota: int,
    channel: Connection,
    execution_group_channel: Connection,
) -> None:
    del settings_payload, api_enabled, cycle_number, process_index, quota, channel
    descendant = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    Path(artifact_root).parent.joinpath("detached-worker.pid").write_text(str(descendant.pid))
    execution_group_channel.send(
        (
            "execution_descendant_started",
            {"pid": descendant.pid, "process_group_id": descendant.pid},
        )
    )
    os._exit(17)


def _runtime(repository: Repository, tmp_path: Path):
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )
    runtime.ingest(Path("data/calibration/problems.jsonl"))
    runtime.register_baseline_methods()
    return runtime


def _holdout_problem(
    repository: Repository,
    source_id: str = "test/holdout-euler",
    *,
    cohort: str = "holdout",
) -> Problem:
    problem = Problem(
        id=uuid4(),
        source_id=source_id,
        source_uri=f"local://{source_id}",
        source_hash=uuid4().hex * 2,
        statement="Euler polynomial is always prime",
        normalized_statement="forall n >= 0, prime(n^2+n+41)",
        domain="number_theory",
        features={"finite_witness": True},
        checker={"kind": "integer_predicate", "predicate_id": "euler_prime", "start": 0},
        status=ProblemStatus.ELIGIBLE,
        cohort=cohort,
        version=1,
        created_at=datetime.now(UTC),
    )
    repository.add_problem(problem, f"problem:{problem.id}")
    return problem


def test_runtime_schedules_paired_holdout_comparison_without_duplicate_suppression(
    repository: Repository,
    tmp_path: Path,
) -> None:
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )
    first_holdout = _holdout_problem(repository, "test/holdout-euler/first")
    _holdout_problem(repository, "test/holdout-euler/second")
    runtime.register_baseline_methods()
    parent = next(
        method
        for method in repository.list_methods(("active",))
        if method.family == "integer_counterexample"
    )
    child = MethodVersion(
        id=uuid4(),
        family=parent.family,
        version=2,
        spec={
            "stop": 200,
            "order": "ascending",
            "provenance": parent.spec["provenance"],
        },
        parent_id=parent.id,
        status="candidate",
        created_at=datetime.now(UTC),
    )
    repository.register_method(child, f"method:{child.id}")

    scheduled = runtime.schedule(limit=2, seed=41)

    experiments = [repository.get_experiment(experiment_id) for experiment_id in scheduled]
    paired = [
        experiment
        for experiment in experiments
        if experiment.lane == "evolution_holdout"
    ]
    assert len(paired) == 2
    assert {experiment.problem_id for experiment in paired} == {first_holdout.id}
    assert {experiment.method_id for experiment in paired} == {parent.id, child.id}
    assert {
        (experiment.config["start"], experiment.config["stop"])
        for experiment in paired
    } == {(0, 100)}
    assert {
        experiment.config["evaluation_policy"] for experiment in paired
    } == {"fixed_parent", "candidate_method"}
    assert repository.count_events("scheduler.duplicate_work_suppressed") == 0
    metrics = runtime.reporting.metrics()
    assert metrics["duplicate_work_rate"] == "0"
    comparison = metrics["method_evolution_holdout"]
    assert comparison["status"] == "evaluation_scheduled"  # type: ignore[index]
    assert {
        result["policy"] for result in comparison["results"]  # type: ignore[index]
    } == {"fixed_parent", "candidate_method"}


def test_default_offline_cycles_measure_static_vs_adaptive_routing_lift(
    repository: Repository,
    tmp_path: Path,
) -> None:
    runtime = _runtime(repository, tmp_path)

    first = runtime.loop.cycle()
    holdout_ids = {
        problem.id
        for problem in repository.list_eligible_problems()
        if problem.cohort == "holdout"
    }
    with repository.database.transaction() as connection:
        generic_first_cycle = connection.execute(
            """
            SELECT problem_id
            FROM experiments
            WHERE lane NOT IN (
                'evolution_holdout', 'routing_holdout', 'verification'
            )
            """
        ).fetchall()
    assert all(
        row[0] not in holdout_ids for row in generic_first_cycle
    )
    assert first["evolution"]["decision"] == "candidate_created"  # type: ignore[index]

    runtime.loop.cycle()
    third = runtime.loop.cycle()

    metrics = runtime.reporting.metrics()
    assert third["evolution"]["decision"] == "promoted"  # type: ignore[index]
    method_comparison = metrics["method_evolution_holdout"]
    assert method_comparison["status"] == "measured"  # type: ignore[index]
    method_results = {
        result["policy"]: result  # type: ignore[index]
        for result in method_comparison["results"]  # type: ignore[index]
    }
    assert method_results["fixed_parent"]["attempts"] == 2
    assert method_results["candidate_method"]["attempts"] == 2
    assert method_results["fixed_parent"]["work_units"] == 200
    assert method_results["candidate_method"]["work_units"] == 200
    assert method_results["fixed_parent"]["verified"] == 0
    assert method_results["candidate_method"]["verified"] == 2
    comparison = metrics["static_vs_adaptive_routing_holdout"]
    assert comparison["status"] == "measured"  # type: ignore[index]
    results = {
        result["policy"]: result  # type: ignore[index]
        for result in comparison["results"]  # type: ignore[index]
    }
    assert results["static_routing"]["attempts"] == 1
    assert results["adaptive_routing"]["attempts"] == 1
    assert results["static_routing"]["allocation_units"] == 1
    assert results["adaptive_routing"]["allocation_units"] == 1
    assert results["static_routing"]["cost_usd"] == "0.000000"
    assert results["adaptive_routing"]["cost_usd"] == "0.000000"
    assert results["static_routing"]["verified"] == 0
    assert results["adaptive_routing"]["verified"] == 1
    assert comparison["observed_lift"] == {  # type: ignore[index]
        "metric": "verified_per_attempt",
        "fixed": "0",
        "adaptive": "1",
        "absolute": "1",
    }


@pytest.mark.parametrize(
    ("faulty_registry", "expected_witness"),
    [
        pytest.param("generator", {"n": 0, "value": 41}, id="generator-defect"),
        pytest.param("verifier", {"n": 40, "value": 1681}, id="verifier-defect"),
    ],
)
def test_runtime_keeps_generation_and_verification_implementations_independent(
    repository: Repository,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    faulty_registry: str,
    expected_witness: dict[str, int],
) -> None:
    import mathloop.runtime as runtime_module
    import mathloop.verification as verification_module

    monkeypatch.setattr(
        runtime_module if faulty_registry == "generator" else verification_module,
        (
            "build_calibration_registry"
            if faulty_registry == "generator"
            else "build_verifier_registry"
        ),
        _build_defective_euler_registry,
        raising=False,
    )
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )
    runtime.ingest(Path("data/calibration/problems.jsonl"))
    runtime.register_baseline_methods()
    experiment_ids = runtime.schedule(limit=12, seed=11)

    while runtime.worker.run_once("independence-worker"):
        pass

    euler_problem = next(
        problem
        for problem in repository.list_eligible_problems()
        if problem.source_id == "calibration/euler-prime"
    )
    integer_method = next(
        method
        for method in repository.list_methods()
        if method.family == "integer_counterexample"
    )
    euler_experiment = next(
        experiment
        for experiment in map(repository.get_experiment, experiment_ids)
        if experiment.problem_id == euler_problem.id
        and experiment.method_id == integer_method.id
    )
    claim = repository.get_claim(
        uuid5(NAMESPACE_URL, f"claim:{euler_experiment.id}")
    )

    assert claim.witness == expected_witness
    assert claim.status is ClaimStatus.REJECTED
    assert repository.get_evaluation_id(claim.id, "integer-predicate", "1")
    assert all(
        item["source_id"] != "calibration/euler-prime"
        or item["method_provenance"]["component"]
        != "method:integer_counterexample"
        for item in runtime.reporting.review_queue()
    )


def test_cycle_counts_only_new_incoming_snapshots(
    repository: Repository,
    tmp_path: Path,
) -> None:
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "problems.jsonl").write_text(Path("data/calibration/problems.jsonl").read_text())
    settings = Settings(
        database_url=repository.database.database_url,
        artifact_root=tmp_path / "artifacts",
        incoming_root=incoming,
    )
    runtime = build_runtime(
        repository,
        ArtifactStore(settings.artifact_root),
        api_enabled=False,
        settings=settings,
        verifier_runner=ExactSymbolicRunner(),
    )
    runtime.loop.queue_capacity = 0
    runtime.loop.worker_iterations = 0

    assert runtime.loop.cycle()["ingested_snapshots"] == 6
    assert runtime.loop.cycle()["ingested_snapshots"] == 0


def test_outer_supervisor_cleans_registered_group_after_worker_root_exits(
    repository: Repository,
    tmp_path: Path,
    monkeypatch,
) -> None:
    import mathloop.runtime as runtime_module

    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )
    runtime.loop.worker_iterations = 1
    runtime.loop.worker_processes = 2
    monkeypatch.setattr(
        runtime_module,
        "_worker_process_main",
        _crash_after_starting_detached_execution_group,
    )

    with pytest.raises(RuntimeError):
        runtime.loop._run_workers(cycle_number=1)

    descendant_pid = int((tmp_path / "detached-worker.pid").read_text())
    try:
        with pytest.raises(ProcessLookupError):
            os.kill(descendant_pid, 0)
    finally:
        try:
            os.kill(descendant_pid, 9)
        except ProcessLookupError:
            pass


def test_verification_allocations_are_audited_not_relabelled_solver_work(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = _runtime(repository, tmp_path)

    scheduled = runtime.schedule(limit=8, seed=17)

    experiments = [repository.get_experiment(experiment_id) for experiment_id in scheduled]
    assert all(experiment.lane != "verification" for experiment in experiments)
    metrics = runtime.reporting.metrics()
    assert metrics["unfilled_lanes"]["verification"] >= 1  # type: ignore[index]


def test_exploitation_always_selects_highest_development_ucb(
    repository: Repository, tmp_path: Path, monkeypatch
) -> None:
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )
    _holdout_problem(repository, cohort="development")
    strong = MethodVersion(
        id=uuid4(),
        family="integer_counterexample",
        version=1,
        spec={"stop": 100, "order": "boundary_first"},
        status="active",
        created_at=datetime.now(UTC),
    )
    weak = strong.model_copy(update={"id": uuid4(), "version": 2})
    repository.register_method(strong, f"method:{strong.id}")
    repository.register_method(weak, f"method:{weak.id}")

    def metrics(_domain, method_id, cohort):
        assert cohort is MetricsCohort.DEVELOPMENT
        return MethodMetrics(
            cohort=cohort,
            trials=10,
            verified=9 if method_id == strong.id else 1,
            false_positives=0,
            cost_usd=Decimal("0"),
        )

    monkeypatch.setattr(repository, "get_method_metrics", metrics)

    scheduled = runtime.schedule(limit=1, seed=1)

    assert len(scheduled) == 1
    assert repository.get_experiment(scheduled[0]).method_id == strong.id


def test_candidate_methods_are_holdout_only_and_never_take_completeness_lane(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = _runtime(repository, tmp_path)
    _holdout_problem(repository)
    parent = next(
        method
        for method in repository.list_methods(("active",))
        if method.family == "integer_counterexample"
    )
    candidate = MethodVersion(
        id=uuid4(),
        family=parent.family,
        version=2,
        spec={
            "stop": 200,
            "order": "boundary_first",
            "provenance": parent.spec["provenance"],
        },
        parent_id=parent.id,
        status="candidate",
        created_at=datetime.now(UTC),
    )
    repository.register_method(candidate, f"method:{candidate.id}")

    scheduled = runtime.schedule(limit=40, seed=29)
    experiments = [repository.get_experiment(experiment_id) for experiment_id in scheduled]
    candidate_experiments = [
        experiment for experiment in experiments if experiment.method_id == candidate.id
    ]

    assert candidate_experiments
    assert all(
        repository.get_problem(experiment.problem_id).cohort == "holdout"
        for experiment in candidate_experiments
    )
    assert all(experiment.lane != "completeness" for experiment in candidate_experiments)
    completeness = [experiment for experiment in experiments if experiment.lane == "completeness"]
    assert completeness
    assert all(experiment.method_id == parent.id for experiment in completeness)
    assert all(experiment.config["order"] == "ascending" for experiment in completeness)


def test_scheduler_does_not_duplicate_an_inflight_completeness_interval(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = _runtime(repository, tmp_path)

    first = runtime.schedule(limit=12, seed=11)
    second = runtime.schedule(limit=2, seed=1)

    completeness = [
        repository.get_experiment(experiment_id)
        for experiment_id in first + second
        if repository.get_experiment(experiment_id).lane == "completeness"
    ]
    intervals = {
        (
            experiment.problem_id,
            experiment.method_id,
            experiment.config["start"],
            experiment.config["stop"],
        )
        for experiment in completeness
    }
    assert len(intervals) == len(completeness)


def test_scheduler_suppresses_same_semantic_work_across_new_seeds(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = _runtime(repository, tmp_path)

    first = runtime.schedule(limit=12, seed=11)
    second = runtime.schedule(limit=40, seed=31)

    first_keys = {
        (
            experiment.problem_id,
            experiment.method_id,
            json.dumps(experiment.config, sort_keys=True),
        )
        for experiment_id in first
        if (experiment := repository.get_experiment(experiment_id)).lane != "verification"
    }
    second_keys = {
        (
            experiment.problem_id,
            experiment.method_id,
            json.dumps(experiment.config, sort_keys=True),
        )
        for experiment_id in second
        if (experiment := repository.get_experiment(experiment_id)).lane != "verification"
    }

    assert first_keys.isdisjoint(second_keys)
    metrics = runtime.reporting.metrics()
    assert metrics["semantic_duplicates_suppressed"] > 0
    assert metrics["duplicate_work_rate"] == "0"
    assert metrics["duplicate_suppression_rate"] != "0"


def test_scheduler_suppresses_every_solving_lane_for_verified_problems(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = _runtime(repository, tmp_path)
    runtime.schedule(limit=12, seed=11)
    while runtime.worker.run_once("resolved-filter-worker"):
        pass
    resolved_sources = {item["source_id"] for item in runtime.reporting.review_queue()}
    resolved_problem_ids = {
        problem.id
        for problem in repository.list_eligible_problems()
        if problem.source_id in resolved_sources
    }

    fresh = runtime.schedule(limit=24, seed=37)

    assert resolved_problem_ids
    assert all(
        repository.get_experiment(experiment_id).problem_id not in resolved_problem_ids
        for experiment_id in fresh
    )


def test_completeness_does_not_relabel_an_existing_exact_interval(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )
    problem = _holdout_problem(repository, cohort="development")
    method = MethodVersion(
        id=uuid4(),
        family="integer_counterexample",
        version=1,
        spec={
            "stop": 100,
            "order": "ascending",
            "provenance": method_provenance("integer_counterexample"),
        },
        status="active",
        created_at=datetime.now(UTC),
    )
    repository.register_method(method, f"method:{method.id}")
    config = repository.get_next_completeness_spec(
        problem.id,
        method.family,
        method.spec,
    )
    config["provenance"] = method.spec["provenance"]["identity_sha256"]  # type: ignore[index]
    covered = Experiment(
        id=uuid4(),
        problem_id=problem.id,
        method_id=method.id,
        lane="exploitation",
        config=config,
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(covered, f"experiment:{covered.id}")
    completeness_seed = next(
        seed
        for seed in range(100)
        if runtime.scheduler.policy.choose_lane(random.Random(seed)) == "completeness"
    )

    assert runtime.schedule(limit=1, seed=completeness_seed) == ()
    assert runtime.reporting.metrics()["semantic_duplicates_suppressed"] >= 1


def test_concurrent_schedulers_atomically_suppress_overlapping_work(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )
    _holdout_problem(repository, cohort="development")
    method = MethodVersion(
        id=uuid4(),
        family="integer_counterexample",
        version=1,
        spec={
            "stop": 100,
            "order": "ascending",
            "provenance": method_provenance("integer_counterexample"),
        },
        status="active",
        created_at=datetime.now(UTC),
    )
    repository.register_method(method, f"method:{method.id}")
    completeness_seeds = [
        seed
        for seed in range(100)
        if runtime.scheduler.policy.choose_lane(random.Random(seed)) == "completeness"
    ][:2]
    barrier = Barrier(2)

    def schedule(seed: int) -> tuple[object, ...]:
        barrier.wait()
        return runtime.schedule(limit=1, seed=seed)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(schedule, completeness_seeds))

    assert sum(len(result) for result in results) == 1
    assert repository.count_events("experiment.enqueued") == 1
    assert repository.count_events("scheduler.duplicate_work_suppressed") >= 1


def test_completeness_overlap_is_suppressed_across_method_versions_in_family(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )
    _holdout_problem(repository, cohort="development")
    parent = MethodVersion(
        id=uuid4(),
        family="integer_counterexample",
        version=1,
        spec={"stop": 100, "order": "ascending"},
        status="active",
        created_at=datetime.now(UTC),
    )
    child = parent.model_copy(
        update={
            "id": uuid4(),
            "version": 2,
            "spec": {"stop": 200, "order": "ascending"},
            "parent_id": parent.id,
        }
    )
    repository.register_method(parent, f"method:{parent.id}")
    repository.register_method(child, f"method:{child.id}")

    scheduled = runtime.schedule(limit=40, seed=29)
    completeness = [
        repository.get_experiment(experiment_id)
        for experiment_id in scheduled
        if repository.get_experiment(experiment_id).lane == "completeness"
    ]

    assert len(completeness) == 1
    assert repository.count_events("scheduler.duplicate_work_suppressed") >= 1


def test_duplicate_work_metric_uses_family_scope_for_ascending_intervals(
    repository: Repository,
) -> None:
    problem = _holdout_problem(repository, cohort="development")
    parent = MethodVersion(
        id=uuid4(),
        family="integer_counterexample",
        version=1,
        spec={"stop": 100, "order": "ascending"},
        status="active",
        created_at=datetime.now(UTC),
    )
    child = parent.model_copy(update={"id": uuid4(), "version": 2, "parent_id": parent.id})
    repository.register_method(parent, f"method:{parent.id}")
    repository.register_method(child, f"method:{child.id}")
    first = Experiment(
        id=uuid4(),
        problem_id=problem.id,
        method_id=parent.id,
        lane="completeness",
        config={"start": 0, "stop": 100, "order": "ascending"},
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    overlapping = first.model_copy(
        update={
            "id": uuid4(),
            "method_id": child.id,
            "config": {"start": 50, "stop": 150, "order": "ascending"},
            "seed": 2,
        }
    )
    repository.enqueue(first, f"experiment:{first.id}")
    repository.enqueue(overlapping, f"experiment:{overlapping.id}")

    assert repository.metrics_snapshot()["duplicate_work_rate"] == "0.5"


def test_cycle_reconciles_succeeded_bounded_work_after_progress_crash(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )
    problem = _holdout_problem(repository, cohort="development")
    method = MethodVersion(
        id=uuid4(),
        family="integer_counterexample",
        version=1,
        spec={
            "stop": 10,
            "order": "ascending",
            "provenance": method_provenance("integer_counterexample"),
        },
        status="active",
        created_at=datetime.now(UTC),
    )
    repository.register_method(method, f"method:{method.id}")
    experiment = Experiment(
        id=uuid4(),
        problem_id=problem.id,
        method_id=method.id,
        lane="exploitation",
        config={
            "start": 0,
            "stop": 10,
            "order": "ascending",
            "provenance": method.spec["provenance"]["identity_sha256"],  # type: ignore[index]
        },
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(experiment, f"experiment:{experiment.id}")
    claimed = repository.claim_next("crashed-worker", datetime.now(UTC), 30)
    assert claimed is not None
    repository.complete(
        claimed.id,
        "crashed-worker",
        {"status": "bounded_no_counterexample"},
        Decimal("0"),
    )
    assert repository.get_completeness_progress(problem.id, method.family) == 0
    runtime.loop.queue_capacity = 0
    runtime.loop.worker_iterations = 0

    first = runtime.loop.cycle()
    second = runtime.loop.cycle()

    assert first["reconciled_completeness"] == 1
    assert second["reconciled_completeness"] == 0
    assert repository.get_completeness_progress(problem.id, method.family) == 10


def test_cycle_keeps_candidate_during_bounded_holdout_evaluation(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = _runtime(repository, tmp_path)
    runtime.loop.worker_iterations = 0

    first = runtime.loop.cycle()
    second = runtime.loop.cycle()

    candidates = [
        method
        for method in repository.list_methods(("candidate",))
        if method.family == "integer_counterexample"
    ]
    assert len(candidates) == 1
    assert first["evolution"]["decision"] == "candidate_created"  # type: ignore[index]
    assert second["evolution"]["decision"] == "insufficient_data"  # type: ignore[index]
    assert second["evolution"]["cohort"] == "holdout"  # type: ignore[index]
    assert repository.count_events("evolution.insufficient_data") == 1
    assert repository.count_events("method.status_changed") == 0


def test_cycle_retires_candidate_after_bounded_insufficient_evaluation(
    repository: Repository,
    tmp_path: Path,
) -> None:
    runtime = _runtime(repository, tmp_path)
    runtime.loop.worker_iterations = 0
    runtime.loop.queue_capacity = 0

    decisions = [runtime.loop.cycle()["evolution"]["decision"] for _ in range(4)]  # type: ignore[index]

    methods = [
        method
        for method in repository.list_methods(("active", "candidate", "archived"))
        if method.family == "integer_counterexample"
    ]
    assert decisions == [
        "candidate_created",
        "insufficient_data",
        "candidate_retired",
        "candidate_created",
    ]
    assert [method.version for method in methods] == [1, 2, 3]
    assert [method.status for method in methods] == ["active", "archived", "candidate"]
    assert repository.count_events("method.status_changed") == 1


def test_cycle_uses_distinct_supervised_worker_processes(
    repository: Repository, tmp_path: Path
) -> None:
    runtime = _runtime(repository, tmp_path)
    runtime.loop.queue_capacity = 4
    runtime.loop.worker_iterations = 2
    runtime.loop.worker_processes = 2

    metrics = runtime.loop.cycle()

    process_workers = [
        worker for worker in repository.list_lease_workers() if "-process-" in worker
    ]
    assert metrics["worker_runs"] == 2
    assert len(process_workers) == 2
    assert len({worker.rsplit("-pid-", 1)[1] for worker in process_workers}) == 2


def test_requested_unavailable_api_is_audited_and_local_methods_continue(
    repository: Repository, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=True,
        verifier_runner=ExactSymbolicRunner(),
    )

    runtime.register_baseline_methods()
    runtime.register_baseline_methods()

    assert repository.count_events("capability.unavailable") == 1
    assert {method.family for method in repository.list_methods()} == {
        "integer_counterexample",
        "sage_polynomial",
        "symbolic_induction",
    }


def test_existing_legacy_volume_is_quarantined_before_provenance_v2_registration(
    repository: Repository,
    tmp_path: Path,
) -> None:
    problem = _holdout_problem(repository, "test/legacy-provenance-volume")
    legacy = MethodVersion(
        id=uuid5(NAMESPACE_URL, "mathloop:integer_counterexample:v1"),
        family="integer_counterexample",
        version=1,
        spec={"stop": 100, "order": "ascending"},
        status="active",
        created_at=datetime(2026, 7, 21, tzinfo=UTC),
    )
    repository.register_method(legacy, "method:integer_counterexample:v1")
    legacy_candidate = MethodVersion(
        id=uuid4(),
        family="integer_counterexample",
        version=2,
        spec={"stop": 200, "order": "boundary_first"},
        parent_id=legacy.id,
        status="candidate",
        created_at=datetime(2026, 7, 21, 0, 0, 1, tzinfo=UTC),
    )
    repository.register_method(
        legacy_candidate,
        "method:integer_counterexample:v2",
    )
    queued = Experiment(
        id=uuid4(),
        problem_id=problem.id,
        method_id=legacy.id,
        lane="exploitation",
        config={"start": 0, "stop": 100, "order": "ascending"},
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(queued, f"experiment:{queued.id}")
    with repository.database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO completeness_progress (
                problem_id, method_family, completed_upper_bound
            ) VALUES (%(problem_id)s, 'integer_counterexample', 100)
            """,
            {"problem_id": problem.id},
        )
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )

    runtime.register_baseline_methods()
    runtime.register_baseline_methods()

    assert repository.get_method(legacy.id).status == "archived"
    assert repository.get_method(legacy_candidate.id).status == "archived"
    quarantined = repository.get_experiment(queued.id)
    assert quarantined.status is ExperimentStatus.FAILED
    with repository.database.transaction() as connection:
        failure = connection.execute(
            """
            SELECT failure_kind, failure_message, retryable
            FROM experiments
            WHERE id = %(id)s
            """,
            {"id": queued.id},
        ).fetchone()
    assert failure == ("provenance", "legacy_unreproducible", False)
    active_integer = [
        method
        for method in repository.list_methods(("active",))
        if method.family == "integer_counterexample"
    ]
    assert len(active_integer) == 1
    assert active_integer[0].version == 3
    assert "provenance" in active_integer[0].spec
    assert repository.get_completeness_progress(
        problem.id,
        "integer_counterexample",
    ) == 0
    assert repository.count_events("method.legacy_provenance_quarantined") == 2
    assert repository.count_events("experiment.legacy_provenance_quarantined") == 1
    assert repository.count_events("completeness.legacy_provenance_reset") == 1
    assert runtime.reporting.metrics()["legacy_unreproducible"] == {
        "methods": 2,
        "experiments": 1,
        "claims": 0,
    }


def test_superseded_valid_provenance_epoch_is_retired_atomically_on_restart(
    repository: Repository,
    tmp_path: Path,
) -> None:
    problem = _holdout_problem(
        repository,
        "test/superseded-valid-provenance",
        cohort="holdout",
    )
    stale_provenance = method_provenance("integer_counterexample")
    stale_provenance["component"] = "method:integer_counterexample:previous-epoch"
    stale_payload = {
        key: value
        for key, value in stale_provenance.items()
        if key != "identity_sha256"
    }
    stale_provenance["identity_sha256"] = provenance_digest(stale_payload)
    active = MethodVersion(
        id=uuid4(),
        family="integer_counterexample",
        version=1,
        spec={
            "stop": 100,
            "order": "ascending",
            "provenance": stale_provenance,
        },
        status="active",
        created_at=datetime(2026, 7, 21, tzinfo=UTC),
    )
    candidate = active.model_copy(
        update={
            "id": uuid4(),
            "version": 2,
            "parent_id": active.id,
            "status": "candidate",
        }
    )
    repository.register_method(active, f"method:{active.id}")
    repository.register_method(candidate, f"method:{candidate.id}")
    stale_identity = stale_provenance["identity_sha256"]
    queued = Experiment(
        id=uuid4(),
        problem_id=problem.id,
        method_id=active.id,
        lane="exploitation",
        config={
            "start": 0,
            "stop": 100,
            "order": "ascending",
            "provenance": stale_identity,
        },
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    leased = queued.model_copy(
        update={"id": uuid4(), "method_id": candidate.id, "seed": 2}
    )
    succeeded = queued.model_copy(
        update={
            "id": uuid4(),
            "config": {
                "start": 0,
                "stop": 50,
                "order": "ascending",
                "provenance": stale_identity,
            },
            "seed": 3,
        }
    )
    pending_verification = queued.model_copy(
        update={
            "id": uuid4(),
            "config": {
                "start": 0,
                "stop": 75,
                "order": "boundary_first",
                "provenance": stale_identity,
            },
            "seed": 4,
        }
    )
    repository.enqueue(queued, f"experiment:{queued.id}")
    repository.enqueue(leased, f"experiment:{leased.id}")
    repository.enqueue(succeeded, f"experiment:{succeeded.id}")
    repository.enqueue(
        pending_verification,
        f"experiment:{pending_verification.id}",
    )
    with repository.database.transaction() as connection:
        connection.execute(
            """
            UPDATE experiments
            SET status = 'leased', lease_owner = 'stale-worker',
                lease_expires_at = now() + interval '1 hour'
            WHERE id = %(id)s
            """,
            {"id": leased.id},
        )
        connection.execute(
            """
            UPDATE experiments
            SET status = 'succeeded',
                result = '{"status":"bounded_no_counterexample"}'::jsonb
            WHERE id = %(id)s
            """,
            {"id": succeeded.id},
        )
        connection.execute(
            """
            UPDATE experiments
            SET status = 'succeeded', result = '{"status":"candidate"}'::jsonb
            WHERE id = %(id)s
            """,
            {"id": pending_verification.id},
        )
        connection.execute(
            """
            INSERT INTO completeness_progress (
                problem_id, method_family, completed_upper_bound
            ) VALUES (%(problem_id)s, 'integer_counterexample', 100)
            """,
            {"problem_id": problem.id},
        )
        stale_digest = hashlib.sha256(b"stale-epoch-artifact").hexdigest()
        connection.execute(
            """
            INSERT INTO artifacts (
                digest, media_type, size_bytes, relative_path, experiment_id
            ) VALUES (
                %(digest)s, 'application/json', 2, %(relative_path)s,
                %(experiment_id)s
            )
            """,
            {
                "digest": stale_digest,
                "relative_path": (
                    f"{stale_digest[:2]}/{stale_digest[2:4]}/{stale_digest}"
                ),
                "experiment_id": succeeded.id,
            },
        )
        repository._append_event(
            connection,
            aggregate_type="experiment",
            aggregate_id=succeeded.id,
            event_type="artifact.stored",
            payload={
                "digest": stale_digest,
                "media_type": "application/json",
                "size_bytes": 2,
                "relative_path": (
                    f"{stale_digest[:2]}/{stale_digest[2:4]}/{stale_digest}"
                ),
                "experiment_id": str(succeeded.id),
                "method_provenance": stale_identity,
            },
            idempotency_key=f"artifact:experiment:{succeeded.id}",
        )
        pending_digest = hashlib.sha256(
            b"stale-pending-verification-artifact"
        ).hexdigest()
        connection.execute(
            """
            INSERT INTO artifacts (
                digest, media_type, size_bytes, relative_path, experiment_id
            ) VALUES (
                %(digest)s, 'application/json', 2, %(relative_path)s,
                %(experiment_id)s
            )
            """,
            {
                "digest": pending_digest,
                "relative_path": (
                    f"{pending_digest[:2]}/{pending_digest[2:4]}/{pending_digest}"
                ),
                "experiment_id": pending_verification.id,
            },
        )
        repository._append_event(
            connection,
            aggregate_type="experiment",
            aggregate_id=pending_verification.id,
            event_type="artifact.stored",
            payload={
                "digest": pending_digest,
                "media_type": "application/json",
                "size_bytes": 2,
                "relative_path": (
                    f"{pending_digest[:2]}/{pending_digest[2:4]}/{pending_digest}"
                ),
                "experiment_id": str(pending_verification.id),
                "method_provenance": stale_identity,
            },
            idempotency_key=f"artifact:experiment:{pending_verification.id}",
        )
    stale_claim = CandidateClaim(
        id=uuid4(),
        problem_id=problem.id,
        experiment_id=succeeded.id,
        claim_type=ClaimType.DISPROOF,
        statement="n=40 is a counterexample",
        witness={"n": 40, "value": 1681},
        status=ClaimStatus.CANDIDATE,
        evidence_level=EvidenceLevel.LEAD,
        created_at=datetime.now(UTC),
    )
    repository.save_candidate(stale_claim)
    repository.evaluate_and_record_claim(
        stale_claim,
        record_method_outcome=False,
    )
    stale_pending_claim = stale_claim.model_copy(
        update={
            "id": uuid4(),
            "experiment_id": pending_verification.id,
            "created_at": datetime.now(UTC),
        }
    )
    repository.save_candidate(stale_pending_claim)
    assert repository.problem_has_verified_claim(problem.id) is True
    assert stale_pending_claim.id in repository.list_candidate_claim_ids()
    assert stale_claim.id in {
        record.claim.id for record in repository.list_review_records()
    }
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )

    runtime.register_baseline_methods()
    first_active = next(
        method
        for method in repository.list_methods(("active",))
        if method.family == "integer_counterexample"
    )
    first_counts = (
        repository.count_events("method.superseded_provenance_archived"),
        repository.count_events("experiment.superseded_provenance_quarantined"),
        repository.count_events("completeness.superseded_provenance_reset"),
    )
    restarted = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
        verifier_runner=ExactSymbolicRunner(),
    )
    restarted.register_baseline_methods()

    assert repository.get_method(active.id).status == "archived"
    assert repository.get_method(candidate.id).status == "archived"
    assert first_active.version == 3
    assert first_active.spec["provenance"] == method_provenance(
        "integer_counterexample"
    )
    assert [
        method.id
        for method in repository.list_methods(("active",))
        if method.family == "integer_counterexample"
    ] == [first_active.id]
    for experiment_id in (queued.id, leased.id):
        experiment = repository.get_experiment(experiment_id)
        assert experiment.status is ExperimentStatus.FAILED
        with repository.database.transaction() as connection:
            failure = connection.execute(
                """
                SELECT failure_kind, failure_message, retryable, lease_owner,
                       lease_expires_at
                FROM experiments
                WHERE id = %(id)s
                """,
                {"id": experiment_id},
            ).fetchone()
        assert failure == (
            "provenance",
            "superseded_provenance",
            False,
            None,
            None,
        )
    assert repository.reconcile_completeness_progress() == 0
    assert repository.get_completeness_progress(
        problem.id,
        "integer_counterexample",
    ) == 0
    current_provenance = first_active.spec["provenance"]
    assert isinstance(current_provenance, dict)
    assert repository.semantic_work_exists(
        problem.id,
        first_active.id,
        {
            "start": 0,
            "stop": 50,
            "order": "ascending",
            "provenance": current_provenance["identity_sha256"],
        },
    ) is False
    current_candidate = first_active.model_copy(
        update={
            "id": uuid4(),
            "version": first_active.version + 1,
            "spec": {
                **first_active.spec,
                "order": "boundary_first",
            },
            "parent_id": first_active.id,
            "status": "candidate",
            "created_at": datetime.now(UTC),
        }
    )
    repository.register_method(
        current_candidate,
        f"method:{current_candidate.id}",
    )
    assert repository.problem_has_verified_claim(problem.id) is False
    assert stale_pending_claim.id not in repository.list_candidate_claim_ids()
    assert stale_claim.id not in {
        record.claim.id for record in repository.list_review_records()
    }
    assert runtime.worker.verify_pending() == 0
    assert runtime.reporting.review_queue() == []
    scheduled = runtime.schedule(limit=2, seed=97)
    assert len(scheduled) == 2
    assert {
        repository.get_experiment(experiment_id).problem_id
        for experiment_id in scheduled
    } == {problem.id}

    current_experiment = repository.get_experiment(scheduled[0])
    current_identity = current_experiment.config["provenance"]
    current_digest = hashlib.sha256(b"current-epoch-artifact").hexdigest()
    with repository.database.transaction() as connection:
        connection.execute(
            """
            UPDATE experiments
            SET status = 'succeeded', result = '{"status":"candidate"}'::jsonb
            WHERE id = %(id)s
            """,
            {"id": current_experiment.id},
        )
        connection.execute(
            """
            INSERT INTO artifacts (
                digest, media_type, size_bytes, relative_path, experiment_id
            ) VALUES (
                %(digest)s, 'application/json', 2, %(relative_path)s,
                %(experiment_id)s
            )
            """,
            {
                "digest": current_digest,
                "relative_path": (
                    f"{current_digest[:2]}/{current_digest[2:4]}/{current_digest}"
                ),
                "experiment_id": current_experiment.id,
            },
        )
        repository._append_event(
            connection,
            aggregate_type="experiment",
            aggregate_id=current_experiment.id,
            event_type="artifact.stored",
            payload={
                "digest": current_digest,
                "media_type": "application/json",
                "size_bytes": 2,
                "relative_path": (
                    f"{current_digest[:2]}/{current_digest[2:4]}/{current_digest}"
                ),
                "experiment_id": str(current_experiment.id),
                "method_provenance": current_identity,
            },
            idempotency_key=f"artifact:experiment:{current_experiment.id}",
        )
    current_claim = stale_claim.model_copy(
        update={
            "id": uuid4(),
            "experiment_id": current_experiment.id,
            "created_at": datetime.now(UTC),
        }
    )
    repository.save_candidate(current_claim)
    repository.evaluate_and_record_claim(
        current_claim,
        record_method_outcome=False,
    )
    assert repository.problem_has_verified_claim(problem.id) is True
    assert current_claim.id in {
        record.claim.id for record in repository.list_review_records()
    }
    assert first_counts == (2, 2, 1)
    assert (
        repository.count_events("method.superseded_provenance_archived"),
        repository.count_events("experiment.superseded_provenance_quarantined"),
        repository.count_events("completeness.superseded_provenance_reset"),
    ) == first_counts


def test_worker_rejects_tampered_provenance_before_solver_execution(
    repository: Repository,
    tmp_path: Path,
) -> None:
    runtime = _runtime(repository, tmp_path)
    problem = next(
        problem
        for problem in repository.list_eligible_problems()
        if problem.source_id == "calibration/euler-prime"
    )
    method = next(
        method
        for method in repository.list_methods(("active",))
        if method.family == "integer_counterexample"
    )
    experiment = Experiment(
        id=uuid4(),
        problem_id=problem.id,
        method_id=method.id,
        lane="exploitation",
        config={
            "start": 0,
            "stop": 100,
            "order": "ascending",
            "provenance": "0" * 64,
        },
        seed=99,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(experiment, f"experiment:{experiment.id}")

    assert runtime.worker.run_once("provenance-worker")

    assert repository.get_experiment(experiment.id).status is ExperimentStatus.FAILED
    with repository.database.transaction() as connection:
        failure = connection.execute(
            """
            SELECT failure_kind, retryable
            FROM experiments
            WHERE id = %(id)s
            """,
            {"id": experiment.id},
        ).fetchone()
        claims = connection.execute(
            "SELECT count(*) FROM claims WHERE experiment_id = %(id)s",
            {"id": experiment.id},
        ).fetchone()
        artifacts = connection.execute(
            "SELECT count(*) FROM artifacts WHERE experiment_id = %(id)s",
            {"id": experiment.id},
        ).fetchone()
    assert failure == ("provenance", False)
    assert claims == (0,)
    assert artifacts == (0,)
