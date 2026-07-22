from datetime import UTC, datetime
from uuid import uuid4

from mathloop.domain import Problem, ProblemStatus
from mathloop.storage.repository import Repository


def test_add_problem_is_idempotent(repository: Repository) -> None:
    problem = Problem(
        id=uuid4(),
        source_id="calibration/euler-prime",
        source_uri="local://calibration",
        source_hash="a" * 64,
        statement="n^2+n+41 is always prime",
        normalized_statement="forall n>=0, prime(n^2+n+41)",
        domain="number_theory",
        features={"finite_witness": True},
        checker={"kind": "integer_predicate", "predicate_id": "euler_prime"},
        status=ProblemStatus.ELIGIBLE,
        cohort="development",
        version=1,
        created_at=datetime.now(UTC),
    )
    first = repository.add_problem(problem, idempotency_key="problem:a")
    second = repository.add_problem(problem, idempotency_key="problem:a")
    assert first == second
    assert repository.count_events("problem.discovered") == 1


def test_daily_budget_is_reserved_before_work(repository: Repository) -> None:
    assert repository.reserve_daily_budget(uuid4(), 0.8, daily_limit_usd=1.0) is True
    assert repository.reserve_daily_budget(uuid4(), 0.3, daily_limit_usd=1.0) is False
