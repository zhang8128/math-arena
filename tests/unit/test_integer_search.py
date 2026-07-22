from datetime import UTC, datetime
from uuid import uuid4

from mathloop.domain import Problem, ProblemStatus
from mathloop.methods.base import MethodContext
from mathloop.methods.integer_search import IntegerCounterexampleSearch
from mathloop.predicates.calibration import build_calibration_registry


def _problem(checker: dict[str, object]) -> Problem:
    return Problem(
        id=uuid4(),
        source_id="test",
        source_uri="local://test",
        source_hash="hash",
        statement="test",
        normalized_statement="test",
        domain="number_theory",
        features={},
        checker=checker,
        status=ProblemStatus.ELIGIBLE,
        cohort="development",
        version=1,
        created_at=datetime.now(UTC),
    )


def test_euler_prime_counterexample_is_exact() -> None:
    method = IntegerCounterexampleSearch(build_calibration_registry())

    result = method.search("euler_prime", start=0, stop=100)

    assert result.status == "candidate"
    assert result.witness == {"n": 40, "value": 1681}


def test_bounded_success_does_not_become_a_proof() -> None:
    method = IntegerCounterexampleSearch(build_calibration_registry())

    result = method.search("sum_odds", start=0, stop=100)

    assert result.status == "bounded_no_counterexample"
    assert result.claim is None
    assert result.witness is None
    assert result.artifact is None


def test_boundary_first_checks_the_upper_boundary_first() -> None:
    method = IntegerCounterexampleSearch(build_calibration_registry())

    result = method.search("euler_prime", start=40, stop=42, order="boundary_first")

    assert result.status == "candidate"
    assert result.witness == {"n": 41, "value": 1763}


def test_invalid_order_returns_structured_non_evidence_result() -> None:
    method = IntegerCounterexampleSearch(build_calibration_registry())
    context = MethodContext(
        problem=_problem({"kind": "integer_predicate", "predicate_id": "euler_prime"}),
        seed=0,
        config={"order": "random"},
    )

    result = method.run(context)

    assert result.status == "invalid_config"
    assert result.claim is None
    assert result.witness is None


def test_invalid_bounds_return_structured_non_evidence_result() -> None:
    method = IntegerCounterexampleSearch(build_calibration_registry())
    context = MethodContext(
        problem=_problem({"kind": "integer_predicate", "predicate_id": "euler_prime"}),
        seed=0,
        config={"start": 10, "stop": 0},
    )

    result = method.run(context)

    assert result.status == "invalid_config"
    assert result.claim is None
    assert result.witness is None
