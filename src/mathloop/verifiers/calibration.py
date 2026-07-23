"""Independent exact checkers for the local calibration corpus."""

from math import isqrt

from mathloop.predicates.base import PredicateEvaluation, PredicateRegistry


def _prime_by_trial_division(value: int) -> bool:
    if value < 2:
        return False
    for divisor in range(2, isqrt(value) + 1):
        if value % divisor == 0:
            return False
    return True


def _euler(n: int) -> PredicateEvaluation:
    value = n * n + n + 41
    return PredicateEvaluation(_prime_by_trial_division(value), value)


def _fermat(n: int) -> PredicateEvaluation:
    value = 2 ** (2**n) + 1
    return PredicateEvaluation(_prime_by_trial_division(value), value)


def _odd_sum(n: int) -> PredicateEvaluation:
    left = n * (1 + (2 * n - 1)) // 2 if n else 0
    right = n * n
    return PredicateEvaluation(left == right, right)


def _quadratic_two(n: int) -> PredicateEvaluation:
    value = n * (n + 1) + 2
    return PredicateEvaluation(_prime_by_trial_division(value), value)


def _quadratic_three(n: int) -> PredicateEvaluation:
    value = n * (n + 1) + 3
    return PredicateEvaluation(_prime_by_trial_division(value), value)


def _integer_sum(n: int) -> PredicateEvaluation:
    iterative = 0
    for value in range(1, n + 1):
        iterative += value
    closed_form = n * (n + 1) // 2
    return PredicateEvaluation(iterative == closed_form, closed_form)


def build_verifier_registry() -> PredicateRegistry:
    registry = PredicateRegistry()

    registry.register("euler_prime", _euler)
    registry.register("fermat_prime", _fermat)
    registry.register("sum_odds", _odd_sum)
    registry.register("quadratic_two_prime", _quadratic_two)
    registry.register("quadratic_three_prime", _quadratic_three)
    registry.register("sum_integers", _integer_sum)
    return registry
