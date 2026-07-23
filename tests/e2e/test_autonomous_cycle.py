from decimal import Decimal
from pathlib import Path
from uuid import UUID

from mathloop.artifacts import ArtifactStore
from mathloop.runtime import build_runtime


def test_cycle_discovers_verifies_and_reports_calibration_results(
    repository, tmp_path: Path
) -> None:
    runtime = build_runtime(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        api_enabled=False,
    )
    first_ingest = runtime.ingest(Path("data/calibration/problems.jsonl"))
    runtime.register_baseline_methods()
    first_schedule = runtime.schedule(limit=12, seed=11)

    while runtime.worker.run_once("e2e-worker"):
        pass

    review = runtime.reporting.review_queue()
    euler = next(item for item in review if item["source_id"] == "calibration/euler-prime")
    fermat = next(item for item in review if item["source_id"] == "calibration/fermat-prime")
    odd_sum = next(item for item in review if item["source_id"] == "calibration/sum-odds")
    sage_generated = next(
        item
        for item in review
        if item["source_id"] == "calibration/euler-prime"
        and item["method_provenance"]["component"] == "method:sage_polynomial"
    )

    assert euler["status"] == "machine_verified"
    assert euler["witness"] == {"n": 40, "value": 1681}
    assert fermat["status"] == "machine_verified"
    assert fermat["witness"] == {"n": 5, "value": 4294967297}
    assert odd_sum["claim_type"] == "proof"
    assert odd_sum["verifier"] == "sage-symbolic-induction"
    assert odd_sum["verifier_version"] == "1"
    assert sage_generated["witness"] == {"n": 40, "value": 1681}
    assert all(item["verifier_provenance"] for item in review)
    assert all(item["novelty_status"] == "unchecked" for item in review)
    assert all(item["artifact_digest"] for item in review)
    assert all(item["reproduction_command"].startswith("mathloop reproduce ") for item in review)
    for item in review:
        reproduction = runtime.reporting.reproduce(UUID(item["claim_id"]))
        assert reproduction["accepted"] is True
        assert reproduction["artifact_digest"] == item["artifact_digest"]

    metrics = runtime.reporting.metrics()
    assert metrics["false_positive_rate"] == "0"
    assert Decimal(metrics["duplicate_work_rate"]) >= 0
    assert all(
        isinstance(method["cost_usd"], str)
        for method in metrics["attempts_cost_by_method"].values()
    )

    before_problem_events = repository.count_events("problem.discovered")
    assert runtime.ingest(Path("data/calibration/problems.jsonl")) == first_ingest
    state_dependent_schedule = runtime.schedule(limit=12, seed=11)
    after_state_dependent_events = repository.count_events("experiment.enqueued")
    assert runtime.schedule(limit=12, seed=11) == state_dependent_schedule
    assert repository.count_events("problem.discovered") == before_problem_events
    assert repository.count_events("experiment.enqueued") == after_state_dependent_events

    fresh_cycle = runtime.schedule(limit=12, seed=12)
    assert len(fresh_cycle) < len(first_schedule)
    resolved_sources = {item["source_id"] for item in review}
    resolved_problem_ids = {
        problem.id
        for problem in repository.list_eligible_problems()
        if problem.source_id in resolved_sources
    }
    assert all(
        repository.get_experiment(experiment_id).problem_id not in resolved_problem_ids
        for experiment_id in fresh_cycle
    )
