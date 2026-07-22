"""Contracts for exact, integer-valued predicates."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PredicateEvaluation:
    holds: bool
    value: int


Predicate = Callable[[int], PredicateEvaluation]


class PredicateRegistry:
    def __init__(self) -> None:
        self._predicates: dict[str, Predicate] = {}

    def register(self, name: str, predicate: Predicate) -> None:
        if name in self._predicates:
            raise ValueError(f"predicate already registered: {name}")
        self._predicates[name] = predicate

    def evaluate(self, name: str, n: int) -> PredicateEvaluation:
        return self._predicates[name](n)

    def contains(self, name: str) -> bool:
        return name in self._predicates
