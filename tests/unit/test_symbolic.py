from datetime import UTC, datetime
from uuid import uuid4

import pytest

from mathloop.domain import Problem, ProblemStatus
from mathloop.methods.base import MethodContext
from mathloop.methods.symbolic import SymbolicInductionMethod


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


def test_sum_of_odds_produces_an_induction_certificate() -> None:
    result = SymbolicInductionMethod().prove_sum_odds()

    assert result.status == "candidate"
    assert result.witness == {"certificate": "sum_odds_induction", "base": 0, "step": 0}
    assert result.claim == "the sum of the first n positive odd integers equals n^2"


@pytest.mark.parametrize(
    "checker",
    [
        {"kind": "unrelated", "predicate_id": "sum_odds", "start": 0},
        {"kind": "integer_predicate", "predicate_id": "sum_odds"},
        {"kind": "integer_predicate", "predicate_id": "sum_odds", "start": 1},
        {"kind": "integer_predicate", "predicate_id": "sum_odds", "start": 0.0},
        {"kind": "integer_predicate", "predicate_id": "sum_odds", "start": False},
    ],
)
def test_run_requires_the_complete_sum_odds_checker_contract(
    checker: dict[str, object],
) -> None:
    context = MethodContext(problem=_problem(checker), seed=0, config={})

    result = SymbolicInductionMethod().run(context)

    assert result.status == "inapplicable"
    assert result.claim is None
    assert result.witness is None
    assert result.artifact is None


def test_run_issues_a_certificate_for_the_supported_checker_contract() -> None:
    context = MethodContext(
        problem=_problem({"kind": "integer_predicate", "predicate_id": "sum_odds", "start": 0}),
        seed=0,
        config={},
    )

    result = SymbolicInductionMethod().run(context)

    assert result.status == "candidate"
    assert result.witness == {"certificate": "sum_odds_induction", "base": 0, "step": 0}
