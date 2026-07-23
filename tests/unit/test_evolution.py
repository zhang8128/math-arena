import math
import random
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from mathloop.domain import MethodVersion
from mathloop.evolution import (
    MethodMetrics,
    MetricsCohort,
    mutate_integer_search,
    mutate_integer_search_method,
    next_completeness_spec,
    should_promote,
    ucb_score,
)


def _metrics(**overrides: object) -> MethodMetrics:
    values: dict[str, object] = {
        "cohort": MetricsCohort.HOLDOUT,
        "trials": 20,
        "verified": 4,
        "false_positives": 0,
        "cost_usd": Decimal("2.000000"),
    }
    values.update(overrides)
    return MethodMetrics(**values)  # type: ignore[arg-type]


def test_mutation_changes_exactly_one_bounded_parameter() -> None:
    parent = {"stop": 100, "order": "ascending"}

    for seed in range(30):
        child = mutate_integer_search(parent, random.Random(seed))
        changed = [key for key in parent if parent[key] != child[key]]
        assert len(changed) == 1
        assert 10 <= child["stop"] <= 1_000_000
        assert child["order"] in {"ascending", "boundary_first"}


@pytest.mark.parametrize("stop", [10, 1_000_000])
def test_mutation_remains_effective_at_numeric_clamps(stop: int) -> None:
    parent = {"stop": stop, "order": "ascending"}

    for seed in range(30):
        assert mutate_integer_search(parent, random.Random(seed)) != parent


@pytest.mark.parametrize(
    "spec",
    [
        {"stop": True, "order": "ascending"},
        {"stop": 10.0, "order": "ascending"},
        {"stop": 9, "order": "ascending"},
        {"stop": 1_000_001, "order": "ascending"},
        {"stop": 100, "order": 1},
        {"stop": 100, "order": "descending"},
        {"stop": 100},
        {"stop": 100, "order": "ascending", "step": 2},
    ],
)
def test_mutation_rejects_malformed_or_out_of_range_specs(spec: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        mutate_integer_search(spec, random.Random(1))


def test_mutated_method_is_a_new_immutable_candidate_child() -> None:
    parent = MethodVersion(
        id=uuid4(),
        family="integer_search",
        version=3,
        spec={"stop": 100, "order": "ascending"},
        parent_id=uuid4(),
        status="active",
        created_at=datetime(2026, 7, 22, tzinfo=UTC),
    )

    child = mutate_integer_search_method(parent, random.Random(4))

    assert child.id != parent.id
    assert child.parent_id == parent.id
    assert child.version == 4
    assert child.family == parent.family
    assert child.status == "candidate"
    assert child.spec == mutate_integer_search(parent.spec, random.Random(4))
    with pytest.raises(TypeError, match="frozen"):
        child.spec["stop"] = 20


def test_mutated_method_resolves_uuid_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = MethodVersion(
        id=uuid4(),
        family="integer_search",
        version=1,
        spec={"stop": 100, "order": "ascending"},
        status="active",
        created_at=datetime(2026, 7, 22, tzinfo=UTC),
    )
    monkeypatch.setattr("mathloop.evolution.uuid4", lambda: parent.id)

    child = mutate_integer_search_method(parent, random.Random(4))

    assert child.id != parent.id


def test_completeness_bounds_grow_monotonically() -> None:
    assert next_completeness_spec({"stop": 100, "order": "ascending"}) == {
        "stop": 200,
        "order": "ascending",
    }


def test_completeness_growth_saturates_at_int64_cap() -> None:
    cap = 2**63 - 1

    assert next_completeness_spec({"stop": cap - 1, "order": "ascending"}) == {
        "stop": cap,
        "order": "ascending",
    }
    assert next_completeness_spec({"stop": cap, "order": "ascending"}) == {
        "stop": cap,
        "order": "ascending",
    }


@pytest.mark.parametrize(
    "spec",
    [
        {"stop": True, "order": "ascending"},
        {"stop": 0, "order": "ascending"},
        {"stop": 2**63, "order": "ascending"},
        {"stop": 10, "order": "boundary_first"},
        {"stop": 10, "order": "ascending", "start": 0},
    ],
)
def test_completeness_growth_rejects_noncanonical_specs(spec: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        next_completeness_spec(spec)


def test_contextual_score_prefers_verified_progress_after_equal_trials() -> None:
    weak = ucb_score(reward=2, trials=20, total_trials=40)
    strong = ucb_score(reward=8, trials=20, total_trials=40)

    assert strong > weak


def test_contextual_score_assigns_infinity_to_untried_method() -> None:
    assert ucb_score(reward=0, trials=0, total_trials=0) == math.inf


@pytest.mark.parametrize(
    "kwargs",
    [
        {"reward": True, "trials": 1, "total_trials": 1},
        {"reward": -1, "trials": 1, "total_trials": 1},
        {"reward": float("nan"), "trials": 1, "total_trials": 1},
        {"reward": float("inf"), "trials": 1, "total_trials": 1},
        {"reward": 2, "trials": 1, "total_trials": 1},
        {"reward": 1, "trials": True, "total_trials": 1},
        {"reward": 0, "trials": -1, "total_trials": 1},
        {"reward": 1, "trials": 2, "total_trials": 1},
        {"reward": 1, "trials": 1, "total_trials": 1.0},
        {"reward": 1, "trials": 1, "total_trials": 1, "exploration": -0.1},
        {"reward": 1, "trials": 1, "total_trials": 1, "exploration": True},
        {"reward": 1, "trials": 1, "total_trials": 1, "exploration": float("nan")},
    ],
)
def test_contextual_score_rejects_invalid_counts_and_nonfinite_values(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises((TypeError, ValueError)):
        ucb_score(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"cohort": "holdout"},
        {"trials": True},
        {"trials": -1},
        {"verified": -1},
        {"verified": 21},
        {"false_positives": -1},
        {"false_positives": 17},
        {"cost_usd": 2.0},
        {"cost_usd": Decimal("NaN")},
        {"cost_usd": Decimal("-0.000001")},
        {"cost_usd": Decimal("2.0000001")},
    ],
)
def test_holdout_metrics_reject_invalid_or_development_inputs(overrides: dict[str, object]) -> None:
    with pytest.raises((TypeError, ValueError)):
        _metrics(**overrides)


def test_promotion_requires_holdout_lift_and_no_false_positives() -> None:
    parent = _metrics(verified=4)
    child = _metrics(verified=6)
    unsafe = _metrics(verified=8, false_positives=1)

    assert should_promote(parent, child, minimum_trials=10) is True
    assert should_promote(parent, unsafe, minimum_trials=10) is False


def test_promotion_rejects_development_metrics() -> None:
    development = _metrics(cohort=MetricsCohort.DEVELOPMENT)

    with pytest.raises(ValueError, match="holdout"):
        should_promote(development, _metrics(verified=6), minimum_trials=10)


def test_promotion_requires_at_least_five_percent_verified_per_cost_lift() -> None:
    parent = _metrics(trials=100, verified=20, cost_usd=Decimal("10.000000"))
    below = _metrics(trials=100, verified=20, cost_usd=Decimal("9.523810"))
    exact = _metrics(trials=100, verified=21, cost_usd=Decimal("10.000000"))

    assert should_promote(parent, below, minimum_trials=100) is False
    assert should_promote(parent, exact, minimum_trials=100) is True


def test_promotion_requires_both_minimum_trial_counts() -> None:
    parent = _metrics(trials=9, verified=1)
    child = _metrics(trials=20, verified=6)

    assert should_promote(parent, child, minimum_trials=10) is False
    assert should_promote(_metrics(), _metrics(trials=9, verified=6), minimum_trials=10) is False


@pytest.mark.parametrize("minimum_trials", [True, 0, -1, 10.0])
def test_promotion_rejects_invalid_minimum_trials(minimum_trials: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        should_promote(_metrics(), _metrics(verified=6), minimum_trials)  # type: ignore[arg-type]
