import random
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import pytest

from mathloop.domain import Experiment, ExperimentStatus, MethodVersion, Problem, ProblemStatus
from mathloop.scheduling import BudgetLedger, PortfolioPolicy, RuntimeScheduler, _is_applicable


def _policy() -> PortfolioPolicy:
    return PortfolioPolicy(
        exploitation=0.55,
        novelty=0.15,
        completeness=0.15,
        verification=0.15,
    )


def test_choose_lane_uses_only_supplied_rng_replayably() -> None:
    policy = _policy()

    first_rng = random.Random(7)
    replay_rng = random.Random(7)

    first = [policy.choose_lane(first_rng) for _ in range(30)]
    replay = [policy.choose_lane(replay_rng) for _ in range(30)]

    assert first == replay


def test_every_required_lane_can_receive_work() -> None:
    policy = _policy()
    rng = random.Random(7)

    observed = {policy.choose_lane(rng) for _ in range(500)}

    assert observed == {"exploitation", "novelty", "completeness", "verification"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"exploitation": 0.0},
        {"novelty": -0.1, "exploitation": 0.8},
        {"completeness": float("nan")},
        {"verification": float("inf")},
        {"novelty": True},
        {"novelty": "0.15"},
        {"exploitation": 0.54},
    ],
)
def test_portfolio_rejects_invalid_or_non_unit_weights(overrides: dict[str, object]) -> None:
    values: dict[str, object] = {
        "exploitation": 0.55,
        "novelty": 0.15,
        "completeness": 0.15,
        "verification": 0.15,
    }
    values.update(overrides)

    with pytest.raises((TypeError, ValueError)):
        PortfolioPolicy(**values)  # type: ignore[arg-type]


def test_batch_allocation_guarantees_every_lane_and_is_replayable() -> None:
    policy = _policy()

    first = policy.allocate_batch(40, random.Random(11))
    replay = policy.allocate_batch(40, random.Random(11))

    assert first == replay
    assert len(first) == 40
    assert all(first.count(lane) >= 1 for lane in policy.lanes)


def test_minimum_batch_contains_each_required_lane_once() -> None:
    allocation = _policy().allocate_batch(4, random.Random(19))

    assert sorted(allocation) == ["completeness", "exploitation", "novelty", "verification"]


@pytest.mark.parametrize("capacity", [3, 1, 0, -1])
def test_batch_rejects_capacity_too_small_for_cycle_invariant(capacity: int) -> None:
    with pytest.raises(ValueError, match="at least 4"):
        _policy().allocate_batch(capacity, random.Random(1))


@pytest.mark.parametrize("capacity", [True, 4.0, "4"])
def test_batch_rejects_non_integer_capacity(capacity: object) -> None:
    with pytest.raises(TypeError, match="integer"):
        _policy().allocate_batch(capacity, random.Random(1))  # type: ignore[arg-type]


def test_budget_authorization_is_exact_and_does_not_mutate_ledger() -> None:
    ledger = BudgetLedger(limit_usd=Decimal("1.000000"), spent_usd=Decimal("0.800000"))

    assert ledger.authorize(estimated_cost_usd=Decimal("0.200000")) is True
    assert ledger.authorize(estimated_cost_usd=Decimal("0.200001")) is False
    assert ledger.spent_usd == Decimal("0.800000")
    with pytest.raises(FrozenInstanceError):
        ledger.spent_usd = Decimal("1.000000")  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("limit_usd", -1),
        ("limit_usd", True),
        ("limit_usd", 1.0),
        ("limit_usd", Decimal("NaN")),
        ("limit_usd", Decimal("1.0000001")),
        ("limit_usd", Decimal("100000000.000000")),
        ("spent_usd", Decimal("-0.000001")),
        ("spent_usd", False),
        ("spent_usd", 0.5),
        ("spent_usd", Decimal("Infinity")),
    ],
)
def test_budget_ledger_rejects_non_decimal_or_database_unsafe_values(
    field: str, value: object
) -> None:
    values: dict[str, object] = {
        "limit_usd": Decimal("1.000000"),
        "spent_usd": Decimal("0.500000"),
    }
    values[field] = value

    with pytest.raises((TypeError, ValueError)):
        BudgetLedger(**values)  # type: ignore[arg-type]


def test_budget_ledger_rejects_already_overspent_state() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        BudgetLedger(limit_usd=Decimal("1.00"), spent_usd=Decimal("1.01"))


@pytest.mark.parametrize(
    "estimate",
    [
        -1,
        True,
        0.1,
        Decimal("-0.000001"),
        Decimal("NaN"),
        Decimal("0.0000001"),
    ],
)
def test_budget_authorization_rejects_invalid_estimates(estimate: object) -> None:
    ledger = BudgetLedger(limit_usd=Decimal("1.00"), spent_usd=Decimal("0.00"))

    with pytest.raises((TypeError, ValueError)):
        ledger.authorize(estimated_cost_usd=estimate)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Codex scheduling: never allocate to holdout rows; copy model/role verbatim
# ---------------------------------------------------------------------------


def _method_version(family: str, spec: dict[str, object]) -> MethodVersion:
    return MethodVersion(
        id=uuid4(),
        family=family,
        version=1,
        spec=spec,
        status="active",
        created_at=datetime.now(UTC),
    )


def _problem(cohort: str) -> Problem:
    return Problem(
        id=uuid4(),
        source_id=f"test/{uuid4()}",
        source_uri="local://scheduler-test",
        source_hash="a" * 64,
        statement="statement",
        normalized_statement="statement",
        domain="testing",
        features={},
        checker={"kind": "unsupported"},
        status=ProblemStatus.ELIGIBLE,
        cohort=cohort,
        version=1,
        created_at=datetime.now(UTC),
    )


def _codex_method_spec() -> dict[str, object]:
    return {
        "external_provider": "codex",
        "codex_role": "terra",
        "codex_model": "gpt-5.6-terra",
        "max_output_tokens": 4096,
        "provenance": {"identity_sha256": "f" * 64},
    }


def test_codex_method_is_applicable_to_development_problems() -> None:
    method = _method_version("codex_proof_strategy", _codex_method_spec())

    assert _is_applicable(_problem("development"), method) is True


def test_codex_method_is_never_applicable_to_holdout_problems() -> None:
    """The single choke point closing the routing-holdout loophole.

    `_options` (the ordinary exploitation/novelty/completeness/verification
    lanes) already skips every holdout problem regardless of `_is_applicable`.
    `_schedule_routing_holdout_pair`, which always operates on holdout
    problems, does not -- it consults only `_is_applicable`. So this is the
    one place that must return `False` for Codex against a holdout problem
    to keep Codex out of every scheduling path, not just the ordinary ones.
    """
    method = _method_version("codex_proof_strategy", _codex_method_spec())

    assert _is_applicable(_problem("holdout"), method) is False


def test_codex_scheduler_config_copies_model_and_role_into_immutable_experiment_config() -> None:
    method = _method_version("codex_proof_strategy", _codex_method_spec())
    scheduler = RuntimeScheduler(cast(Any, None), _policy())

    config = scheduler._config(_problem("development"), method, "exploitation")

    assert config["external_provider"] == "codex"
    assert config["codex_role"] == "terra"
    assert config["codex_model"] == "gpt-5.6-terra"
    assert config["max_output_tokens"] == 4096
    assert config["provenance"] == "f" * 64

    # `Experiment` is a `FrozenModel`: wrapping the scheduler's config in one
    # freezes it recursively (`FrozenDict`), so the copied model/role are not
    # merely equal at scheduling time -- they cannot be mutated afterward.
    experiment = Experiment(
        id=uuid4(),
        problem_id=uuid4(),
        method_id=method.id,
        lane="exploitation",
        config=config,
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    assert experiment.config["codex_role"] == "terra"
    assert experiment.config["codex_model"] == "gpt-5.6-terra"
    with pytest.raises(TypeError):
        experiment.config["codex_role"] = "sol"  # type: ignore[index]
