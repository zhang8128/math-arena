from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from psycopg.errors import CheckViolation
from psycopg.types.json import Jsonb

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
    Verification,
)
from mathloop.evolution import MethodMetrics, MetricsCohort
from mathloop.storage.repository import (
    CompletenessProgressError,
    EvaluationContextError,
    EvaluationNotFoundError,
    Repository,
)

pytestmark = pytest.mark.integration


def _problem(*, cohort: MetricsCohort, start: int = 0) -> Problem:
    problem_id = uuid4()
    return Problem(
        id=problem_id,
        source_id=f"test/{problem_id}",
        source_uri=f"local://{problem_id}",
        source_hash=str(problem_id),
        statement="all values satisfy the predicate",
        normalized_statement="forall n, P(n)",
        domain="number_theory",
        features={},
        checker={"kind": "integer_predicate", "predicate_id": "sum_odds", "start": start},
        status=ProblemStatus.ELIGIBLE,
        cohort=cohort.value,
        version=1,
        created_at=datetime.now(UTC),
    )


def _method(*, family: str = "integer_counterexample") -> MethodVersion:
    return MethodVersion(
        id=uuid4(),
        family=family,
        version=1,
        spec={"stop": 100, "order": "ascending"},
        status="active",
        created_at=datetime.now(UTC),
    )


def _persist_completed_experiment(
    repository: Repository,
    *,
    problem: Problem,
    method: MethodVersion,
    lane: str,
    config: dict[str, object],
    cost_usd: Decimal,
    result_status: str,
    register_entities: bool = True,
) -> Experiment:
    repository.add_problem(problem, idempotency_key=f"problem:{problem.id}")
    repository.register_method(method, idempotency_key=f"method:{method.id}")
    experiment_id = uuid4()
    experiment = Experiment(
        id=experiment_id,
        problem_id=problem.id,
        method_id=method.id,
        lane=lane,
        config=config,
        seed=experiment_id.int % (2**63 - 1),
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(experiment, idempotency_key=f"experiment:{experiment.id}")
    with repository.database.transaction() as connection:
        connection.execute(
            """
            UPDATE experiments
            SET status = 'succeeded', cost_usd = %(cost)s,
                result = %(result)s, updated_at = now()
            WHERE id = %(id)s
            """,
            {
                "id": experiment.id,
                "cost": cost_usd,
                "result": Jsonb({"status": result_status}),
            },
        )
    return experiment.model_copy(update={"status": ExperimentStatus.SUCCEEDED})
def _persist_evaluation(
    repository: Repository,
    *,
    problem: Problem,
    method: MethodVersion,
    accepted: bool,
    cost_usd: Decimal,
    register_entities: bool = True,
) -> UUID:
    experiment = _persist_completed_experiment(
        repository,
        problem=problem,
        method=method,
        lane="exploitation",
        config={},
        cost_usd=cost_usd,
        result_status="candidate",
        register_entities=register_entities,
    )
    claim = CandidateClaim(
        id=uuid4(),
        problem_id=problem.id,
        experiment_id=experiment.id,
        claim_type=ClaimType.DISPROOF,
        statement="candidate",
        witness={"n": 1},
        status=ClaimStatus.CANDIDATE,
        evidence_level=EvidenceLevel.LEAD,
        created_at=datetime.now(UTC),
    )
    repository.save_candidate(claim)
    repository.record_verification(
        claim,
        Verification(
            verifier="exact-checker",
            verifier_version="v1",
            accepted=accepted,
            independent=True,
            details={"checked": True},
        ),
    )
    return repository.get_evaluation_id(claim.id, "exact-checker", "v1")


def test_scores_derive_domain_method_cohort_and_cost_from_canonical_evaluations(
    repository: Repository,
) -> None:
    method = _method()
    development_problem = _problem(cohort=MetricsCohort.DEVELOPMENT)
    holdout_problem = _problem(cohort=MetricsCohort.HOLDOUT)
    development_evaluation = _persist_evaluation(
        repository,
        problem=development_problem,
        method=method,
        accepted=True,
        cost_usd=Decimal("0.200000"),
    )
    holdout_evaluation = _persist_evaluation(
        repository,
        problem=holdout_problem,
        method=method,
        accepted=False,
        cost_usd=Decimal("0.300000"),
        register_entities=False,
    )

    development = repository.record_method_outcome(development_evaluation)
    holdout = repository.record_method_outcome(holdout_evaluation)

    assert development == MethodMetrics(
        cohort=MetricsCohort.DEVELOPMENT,
        trials=1,
        verified=1,
        false_positives=0,
        cost_usd=Decimal("0.200000"),
    )
    assert holdout == MethodMetrics(
        cohort=MetricsCohort.HOLDOUT,
        trials=1,
        verified=0,
        false_positives=1,
        cost_usd=Decimal("0.300000"),
    )
    with repository.database.transaction() as connection:
        rows = connection.execute(
            """
            SELECT cohort, trials, reward, false_positives, cost_usd
            FROM method_scores
            WHERE domain = 'number_theory' AND method_id = %(method_id)s
            ORDER BY cohort
            """,
            {"method_id": method.id},
        ).fetchall()
    assert rows == [
        ("development", 1, 1, 0, Decimal("0.200000")),
        ("holdout", 1, 0, 1, Decimal("0.300000")),
    ]


def test_missing_or_non_independent_evaluation_cannot_update_scores(
    repository: Repository,
) -> None:
    with pytest.raises(EvaluationNotFoundError):
        repository.record_method_outcome(uuid4())

    problem = _problem(cohort=MetricsCohort.DEVELOPMENT)
    method = _method()
    evaluation_id = _persist_evaluation(
        repository,
        problem=problem,
        method=method,
        accepted=True,
        cost_usd=Decimal("0.100000"),
    )
    with repository.database.transaction() as connection:
        connection.execute(
            "UPDATE evaluations SET independent = false WHERE id = %(id)s",
            {"id": evaluation_id},
        )

    with pytest.raises(EvaluationContextError, match="independent"):
        repository.record_method_outcome(evaluation_id)
    assert repository.get_method_metrics(
        "number_theory", method.id, MetricsCohort.DEVELOPMENT
    ).trials == 0


def test_false_positive_records_trial_without_reward(repository: Repository) -> None:
    problem = _problem(cohort=MetricsCohort.DEVELOPMENT)
    method = _method()
    evaluation_id = _persist_evaluation(
        repository,
        problem=problem,
        method=method,
        accepted=False,
        cost_usd=Decimal("0.100000"),
    )

    metrics = repository.record_method_outcome(evaluation_id)

    assert metrics.trials == 1
    assert metrics.verified == 0
    assert metrics.false_positives == 1


def test_one_evaluation_can_improve_score_only_once_even_concurrently(
    repository: Repository,
) -> None:
    workers = 6
    barrier = Barrier(workers)
    problem = _problem(cohort=MetricsCohort.DEVELOPMENT)
    method = _method()
    evaluation_id = _persist_evaluation(
        repository,
        problem=problem,
        method=method,
        accepted=True,
        cost_usd=Decimal("0.100000"),
    )

    def replay(_: int) -> MethodMetrics:
        barrier.wait()
        return repository.record_method_outcome(evaluation_id)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(replay, range(workers)))

    metrics = repository.get_method_metrics(
        "number_theory", method.id, MetricsCohort.DEVELOPMENT
    )
    assert metrics.trials == 1
    assert metrics.verified == 1
    assert metrics.cost_usd == Decimal("0.100000")
    assert repository.count_events("method.outcome_recorded") == 1


def test_caller_cannot_fabricate_score_domain_method_cohort_or_cost(
    repository: Repository,
) -> None:
    problem = _problem(cohort=MetricsCohort.HOLDOUT)
    method = _method()
    evaluation_id = _persist_evaluation(
        repository,
        problem=problem,
        method=method,
        accepted=True,
        cost_usd=Decimal("0.100000"),
    )

    with pytest.raises(TypeError):
        repository.record_method_outcome(  # type: ignore[call-arg]
            evaluation_id,
            cohort=MetricsCohort.DEVELOPMENT,
            domain="fabricated",
            method_id=uuid4(),
            cost_usd=Decimal("0"),
        )

    assert repository.count_events("method.outcome_recorded") == 0


def test_concurrent_distinct_canonical_evaluations_update_atomically(
    repository: Repository,
) -> None:
    workers = 6
    barrier = Barrier(workers)
    method = _method()
    evaluation_ids: list[UUID] = []
    for index in range(workers):
        evaluation_ids.append(
            _persist_evaluation(
                repository,
                problem=_problem(cohort=MetricsCohort.DEVELOPMENT),
                method=method,
                accepted=True,
                cost_usd=Decimal("0.100000"),
                register_entities=index == 0,
            )
        )

    def record(evaluation_id: UUID) -> MethodMetrics:
        barrier.wait()
        return repository.record_method_outcome(evaluation_id)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(record, evaluation_ids))

    assert repository.get_method_metrics(
        "number_theory", method.id, MetricsCohort.DEVELOPMENT
    ) == MethodMetrics(
        cohort=MetricsCohort.DEVELOPMENT,
        trials=workers,
        verified=workers,
        false_positives=0,
        cost_usd=Decimal("0.600000"),
    )


def test_missing_method_metrics_read_as_exact_zeroes(repository: Repository) -> None:
    assert repository.get_method_metrics(
        "number_theory", uuid4(), MetricsCohort.DEVELOPMENT
    ) == MethodMetrics(
        cohort=MetricsCohort.DEVELOPMENT,
        trials=0,
        verified=0,
        false_positives=0,
        cost_usd=Decimal("0"),
    )


def _completeness_experiment(
    repository: Repository,
    *,
    problem: Problem,
    method: MethodVersion,
    start: int,
    stop: int,
    register_entities: bool,
    lane: str = "completeness",
    result_status: str = "bounded_no_counterexample",
) -> Experiment:
    return _persist_completed_experiment(
        repository,
        problem=problem,
        method=method,
        lane=lane,
        config={"start": start, "stop": stop, "order": "ascending"},
        cost_usd=Decimal("0.010000"),
        result_status=result_status,
        register_entities=register_entities,
    )


def test_completeness_advances_only_from_contiguous_successful_experiments(
    repository: Repository,
) -> None:
    problem = _problem(cohort=MetricsCohort.DEVELOPMENT)
    method = _method()
    first = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=0,
        stop=100,
        register_entities=True,
    )

    assert repository.get_completeness_progress(problem.id, method.family) == 0
    assert repository.record_completeness_progress(first.id) == 100
    assert repository.get_next_completeness_spec(
        problem.id,
        method.family,
        {"stop": 100, "order": "ascending"},
    ) == {"start": 100, "stop": 200, "order": "ascending"}
    second = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=100,
        stop=200,
        register_entities=False,
    )
    assert repository.record_completeness_progress(second.id) == 200


def test_completeness_cursor_supports_integer_domains_starting_below_zero(
    repository: Repository,
) -> None:
    problem = _problem(cohort=MetricsCohort.DEVELOPMENT, start=-10)
    method = _method()
    experiment = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=-10,
        stop=0,
        register_entities=True,
    )

    assert repository.record_completeness_progress(experiment.id) == 0
    assert repository.get_completeness_progress(problem.id, method.family) == 0


def test_completeness_rejects_gaps_repeats_wrong_lane_and_partial_searches(
    repository: Repository,
) -> None:
    problem = _problem(cohort=MetricsCohort.DEVELOPMENT)
    method = _method()
    first = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=0,
        stop=100,
        register_entities=True,
    )
    gap = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=200,
        stop=300,
        register_entities=False,
    )
    wrong_lane = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=0,
        stop=100,
        register_entities=False,
        lane="exploitation",
    )
    partial = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=0,
        stop=100,
        register_entities=False,
        result_status="candidate",
    )

    with pytest.raises(CompletenessProgressError, match="lane"):
        repository.record_completeness_progress(wrong_lane.id)
    with pytest.raises(CompletenessProgressError, match="full interval"):
        repository.record_completeness_progress(partial.id)
    with pytest.raises(CompletenessProgressError, match="contiguous"):
        repository.record_completeness_progress(gap.id)
    assert repository.record_completeness_progress(first.id) == 100
    with pytest.raises(CompletenessProgressError, match="contiguous"):
        repository.record_completeness_progress(gap.id)
    duplicate = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=0,
        stop=100,
        register_entities=False,
    )
    with pytest.raises(CompletenessProgressError, match="contiguous"):
        repository.record_completeness_progress(duplicate.id)


def test_completeness_experiment_replay_is_concurrently_idempotent(
    repository: Repository,
) -> None:
    workers = 6
    barrier = Barrier(workers)
    problem = _problem(cohort=MetricsCohort.DEVELOPMENT)
    method = _method()
    experiment = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=0,
        stop=100,
        register_entities=True,
    )

    def replay(_: int) -> int:
        barrier.wait()
        return repository.record_completeness_progress(experiment.id)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        assert list(executor.map(replay, range(workers))) == [100] * workers
    assert repository.count_events("completeness.progress_recorded") == 1


def test_out_of_order_concurrent_completeness_never_skips_gap(
    repository: Repository,
) -> None:
    barrier = Barrier(2)
    problem = _problem(cohort=MetricsCohort.DEVELOPMENT)
    method = _method()
    first = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=0,
        stop=100,
        register_entities=True,
    )
    gap = _completeness_experiment(
        repository,
        problem=problem,
        method=method,
        start=200,
        stop=300,
        register_entities=False,
    )

    def record(experiment: Experiment) -> int | None:
        barrier.wait()
        try:
            return repository.record_completeness_progress(experiment.id)
        except CompletenessProgressError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(record, [first, gap]))
    assert repository.get_completeness_progress(problem.id, method.family) == 100


def test_database_initialize_validates_and_fully_migrates_legacy_method_scores(
    repository: Repository,
) -> None:
    method_id = uuid4()
    fractional_id = uuid4()
    invalid_id = uuid4()
    with repository.database.transaction() as connection:
        connection.execute("DROP TABLE method_scores")
        connection.execute(
            """
            CREATE TABLE method_scores (
                domain TEXT NOT NULL,
                method_id UUID NOT NULL,
                cohort TEXT NOT NULL,
                trials INTEGER NOT NULL DEFAULT 0,
                reward DOUBLE PRECISION NOT NULL DEFAULT 0,
                PRIMARY KEY (domain, method_id, cohort)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO method_scores (domain, method_id, cohort, trials, reward)
            VALUES
                ('number_theory', %(method_id)s, 'development', 3, 2),
                ('number_theory', %(fractional_id)s, 'development', 3, 1.5),
                ('number_theory', %(invalid_id)s, 'invalid', 1, -1)
            """,
            {
                "method_id": method_id,
                "fractional_id": fractional_id,
                "invalid_id": invalid_id,
            },
        )

    with pytest.raises(CheckViolation, match="invalid legacy method_scores"):
        repository.database.initialize()
    with repository.database.transaction() as connection:
        connection.execute(
            "DELETE FROM method_scores WHERE method_id IN (%(first)s, %(second)s)",
            {"first": fractional_id, "second": invalid_id},
        )
    repository.database.initialize()

    assert repository.get_method_metrics(
        "number_theory", method_id, MetricsCohort.DEVELOPMENT
    ) == MethodMetrics(
        cohort=MetricsCohort.DEVELOPMENT,
        trials=3,
        verified=2,
        false_positives=0,
        cost_usd=Decimal("0.000000"),
    )
    with repository.database.transaction() as connection:
        column_rows = connection.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'method_scores'
              AND column_name IN ('trials', 'reward')
            """
        ).fetchall()
        constraint_rows = connection.execute(
            """
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'method_scores'::regclass AND contype = 'c'
            """
        ).fetchall()
    assert dict(column_rows) == {"trials": "bigint", "reward": "bigint"}
    assert {row[0] for row in constraint_rows} >= {
        "method_scores_cohort_valid",
        "method_scores_trials_nonnegative",
        "method_scores_reward_nonnegative",
        "method_scores_false_positives_nonnegative",
        "method_scores_cost_nonnegative",
        "method_scores_counts_valid",
    }
