"""Validated method scoring, mutation, and holdout promotion policies."""

import math
import random
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import cast
from uuid import UUID, uuid4

from mathloop.billing import MAX_DATABASE_USD, validate_database_usd
from mathloop.domain import MethodVersion

MIN_INTEGER_STOP = 10
MAX_INTEGER_STOP = 1_000_000
MAX_INT64 = 2**63 - 1
VALID_INTEGER_ORDERS = frozenset({"ascending", "boundary_first"})


class MetricsCohort(StrEnum):
    DEVELOPMENT = "development"
    HOLDOUT = "holdout"


def _require_exact_int(value: object, field_name: str, *, minimum: int = 0) -> int:
    if type(value) is not int:
        raise TypeError(f"{field_name} must be an integer")
    if value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}")
    return value


def _require_database_usd(value: object, field_name: str) -> Decimal:
    validate_database_usd(value, field_name=field_name, positive=False)  # type: ignore[arg-type]
    amount = value
    assert isinstance(amount, Decimal)
    if amount > MAX_DATABASE_USD:
        raise ValueError(f"{field_name} exceeds NUMERIC(14, 6) capacity")
    return amount


@dataclass(frozen=True)
class MethodMetrics:
    cohort: MetricsCohort
    trials: int
    verified: int
    false_positives: int
    cost_usd: Decimal

    def __post_init__(self) -> None:
        if type(self.cohort) is not MetricsCohort:
            raise TypeError("cohort must be a MetricsCohort")
        trials = _require_exact_int(self.trials, "trials")
        verified = _require_exact_int(self.verified, "verified")
        false_positives = _require_exact_int(self.false_positives, "false_positives")
        _require_database_usd(self.cost_usd, "cost_usd")
        if verified + false_positives > trials:
            raise ValueError("verified and false positives cannot exceed trials")


def _require_number(value: object, field_name: str) -> float:
    if type(value) not in (int, float, Decimal):
        raise TypeError(f"{field_name} must be an integer, float, or Decimal")
    number = float(cast(int | float | Decimal, value))
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def ucb_score(
    reward: int | float | Decimal,
    trials: int,
    total_trials: int,
    exploration: int | float | Decimal = 1.4,
) -> float:
    reward_value = _require_number(reward, "reward")
    exploration_value = _require_number(exploration, "exploration")
    trial_count = _require_exact_int(trials, "trials")
    total_count = _require_exact_int(total_trials, "total_trials")
    if reward_value < 0:
        raise ValueError("reward must be non-negative")
    if exploration_value < 0:
        raise ValueError("exploration must be non-negative")
    if trial_count > total_count:
        raise ValueError("trials cannot exceed total_trials")
    if reward_value > trial_count:
        raise ValueError("reward cannot exceed trials")
    if trial_count == 0:
        return math.inf
    mean = reward_value / trial_count
    return mean + exploration_value * math.sqrt(math.log(total_count + 1) / trial_count)


def _validate_integer_search_spec(
    spec: Mapping[str, object],
) -> tuple[int, str, object | None]:
    if not isinstance(spec, Mapping):
        raise TypeError("spec must be a mapping")
    if set(spec) not in ({"stop", "order"}, {"stop", "order", "provenance"}):
        raise ValueError(
            "integer search spec must contain stop, order, and optional provenance"
        )
    stop = _require_exact_int(spec["stop"], "stop", minimum=MIN_INTEGER_STOP)
    if stop > MAX_INTEGER_STOP:
        raise ValueError(f"stop cannot exceed {MAX_INTEGER_STOP}")
    order = spec["order"]
    if type(order) is not str:
        raise TypeError("order must be a string")
    if order not in VALID_INTEGER_ORDERS:
        raise ValueError("order must be ascending or boundary_first")
    return stop, order, spec.get("provenance")


def mutate_integer_search(spec: Mapping[str, object], rng: random.Random) -> dict[str, object]:
    stop, order, provenance = _validate_integer_search_spec(spec)
    if not isinstance(rng, random.Random):
        raise TypeError("rng must be a random.Random instance")
    toggled = "boundary_first" if order == "ascending" else "ascending"
    candidates: list[dict[str, int | str]] = [
        {"stop": stop, "order": toggled}
    ]
    doubled = min(stop * 2, MAX_INTEGER_STOP)
    if doubled != stop:
        candidates.append({"stop": doubled, "order": order})
    halved = max(stop // 2, MIN_INTEGER_STOP)
    if halved != stop:
        candidates.append({"stop": halved, "order": order})
    mutated: dict[str, object] = dict(rng.choice(candidates))
    if provenance is not None:
        mutated["provenance"] = provenance
    return mutated


def mutate_integer_search_method(parent: MethodVersion, rng: random.Random) -> MethodVersion:
    if not isinstance(parent, MethodVersion):
        raise TypeError("parent must be a MethodVersion")
    child_spec = mutate_integer_search(parent.spec, rng)
    child_id = uuid4()
    if child_id == parent.id:
        child_id = UUID(int=(parent.id.int + 1) % (2**128))
    return MethodVersion(
        id=child_id,
        family=parent.family,
        version=parent.version + 1,
        spec=child_spec,
        parent_id=parent.id,
        status="candidate",
        created_at=datetime.now(UTC),
    )


def next_completeness_spec(spec: Mapping[str, object]) -> dict[str, int | str]:
    if not isinstance(spec, Mapping):
        raise TypeError("spec must be a mapping")
    if set(spec) not in ({"stop", "order"}, {"stop", "order", "provenance"}):
        raise ValueError(
            "completeness spec must contain stop, order, and optional provenance"
        )
    stop = _require_exact_int(spec["stop"], "stop", minimum=1)
    if stop > MAX_INT64:
        raise ValueError("stop cannot exceed the signed int64 limit")
    if type(spec["order"]) is not str:
        raise TypeError("order must be a string")
    if spec["order"] != "ascending":
        raise ValueError("completeness search order must be ascending")
    return {"stop": min(stop * 2, MAX_INT64), "order": "ascending"}


def should_promote(parent: MethodMetrics, child: MethodMetrics, minimum_trials: int) -> bool:
    if not isinstance(parent, MethodMetrics) or not isinstance(child, MethodMetrics):
        raise TypeError("parent and child must be MethodMetrics")
    required_trials = _require_exact_int(minimum_trials, "minimum_trials", minimum=1)
    if parent.cohort is not MetricsCohort.HOLDOUT or child.cohort is not MetricsCohort.HOLDOUT:
        raise ValueError("promotion requires holdout metrics")
    if parent.trials < required_trials or child.trials < required_trials:
        return False
    if child.false_positives != 0:
        return False
    minimum_cost = Decimal("0.01")
    parent_rate = Decimal(parent.verified) / max(parent.cost_usd, minimum_cost)
    child_rate = Decimal(child.verified) / max(child.cost_usd, minimum_cost)
    return child_rate > parent_rate and child_rate >= parent_rate * Decimal("1.05")
