"""Exact predicates for the local calibration corpus."""

from math import isqrt

from mathloop.predicates.base import PredicateEvaluation, PredicateRegistry


def _is_prime(value: int) -> bool:
    if value < 2:
        return False
    return all(value % divisor for divisor in range(2, isqrt(value) + 1))


def build_calibration_registry() -> PredicateRegistry:
    registry = PredicateRegistry()
    registry.register(
        "euler_prime",
        lambda n: PredicateEvaluation(_is_prime(n * n + n + 41), n * n + n + 41),
    )
    registry.register(
        "fermat_prime",
        lambda n: PredicateEvaluation(_is_prime(2 ** (2**n) + 1), 2 ** (2**n) + 1),
    )
    registry.register(
        "sum_odds",
        lambda n: PredicateEvaluation(sum(2 * k + 1 for k in range(n)) == n * n, n * n),
    )
    return registry
