"""Exact predicates for the local calibration corpus."""

from math import isqrt

from mathloop.predicates.base import PredicateEvaluation, PredicateRegistry


def _is_prime(value: int) -> bool:
    if value < 2:
        return False
    return all(value % divisor for divisor in range(2, isqrt(value) + 1))


def _euler(n: int) -> PredicateEvaluation:
    value = n * n + n + 41
    return PredicateEvaluation(_is_prime(value), value)


def _fermat(n: int) -> PredicateEvaluation:
    value = 2 ** (2**n) + 1
    return PredicateEvaluation(_is_prime(value), value)


def _odd_sum(n: int) -> PredicateEvaluation:
    return PredicateEvaluation(
        sum(2 * k + 1 for k in range(n)) == n * n,
        n * n,
    )


def _quadratic_two(n: int) -> PredicateEvaluation:
    value = n * n + n + 2
    return PredicateEvaluation(_is_prime(value), value)


def _quadratic_three(n: int) -> PredicateEvaluation:
    value = n * n + n + 3
    return PredicateEvaluation(_is_prime(value), value)


def _integer_sum(n: int) -> PredicateEvaluation:
    closed_form = n * (n + 1) // 2
    return PredicateEvaluation(sum(range(1, n + 1)) == closed_form, closed_form)


def build_calibration_registry() -> PredicateRegistry:
    registry = PredicateRegistry()
    registry.register("euler_prime", _euler)
    registry.register("fermat_prime", _fermat)
    registry.register("sum_odds", _odd_sum)
    registry.register("quadratic_two_prime", _quadratic_two)
    registry.register("quadratic_three_prime", _quadratic_three)
    registry.register("sum_integers", _integer_sum)
    return registry
