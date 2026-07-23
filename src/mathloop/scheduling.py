"""Deterministic portfolio allocation and exact in-memory budget policy."""

import math
import random
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar, cast

from mathloop.billing import validate_database_usd

MAX_DATABASE_USD = Decimal("99999999.999999")


def _validate_weight(value: object, name: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be an integer or float")
    weight = float(cast(int | float, value))
    if not math.isfinite(weight) or weight <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return weight


def _require_rng(rng: object) -> random.Random:
    if not isinstance(rng, random.Random):
        raise TypeError("rng must be a random.Random instance")
    return rng


@dataclass(frozen=True)
class PortfolioPolicy:
    exploitation: float
    novelty: float
    completeness: float
    verification: float

    lanes: ClassVar[tuple[str, ...]] = (
        "exploitation",
        "novelty",
        "completeness",
        "verification",
    )

    def __post_init__(self) -> None:
        weights = tuple(_validate_weight(getattr(self, lane), lane) for lane in self.lanes)
        if not math.isclose(math.fsum(weights), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("portfolio weights must sum to one")
        for lane, weight in zip(self.lanes, weights, strict=True):
            object.__setattr__(self, lane, weight)

    def choose_lane(self, rng: random.Random) -> str:
        generator = _require_rng(rng)
        draw = generator.random()
        cumulative = 0.0
        for lane in self.lanes:
            cumulative += getattr(self, lane)
            if draw < cumulative:
                return lane
        return self.lanes[-1]

    def allocate_batch(self, capacity: int, rng: random.Random) -> tuple[str, ...]:
        if type(capacity) is not int:
            raise TypeError("capacity must be an integer")
        if capacity < len(self.lanes):
            raise ValueError(f"capacity must be at least {len(self.lanes)}")
        generator = _require_rng(rng)
        allocation = list(self.lanes)
        allocation.extend(self.choose_lane(generator) for _ in range(capacity - len(self.lanes)))
        generator.shuffle(allocation)
        return tuple(allocation)


def _validate_usd(value: object, field_name: str) -> Decimal:
    validate_database_usd(value, field_name=field_name, positive=False)  # type: ignore[arg-type]
    amount = value
    assert isinstance(amount, Decimal)
    if amount > MAX_DATABASE_USD:
        raise ValueError(f"{field_name} exceeds NUMERIC(14, 6) capacity")
    return amount


@dataclass(frozen=True)
class BudgetLedger:
    limit_usd: Decimal
    spent_usd: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        limit = _validate_usd(self.limit_usd, "limit_usd")
        spent = _validate_usd(self.spent_usd, "spent_usd")
        if spent > limit:
            raise ValueError("spent_usd cannot exceed limit_usd")

    def authorize(self, estimated_cost_usd: Decimal) -> bool:
        estimate = _validate_usd(estimated_cost_usd, "estimated_cost_usd")
        return self.spent_usd + estimate <= self.limit_usd
