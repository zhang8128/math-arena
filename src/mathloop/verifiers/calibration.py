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


def build_verifier_registry() -> PredicateRegistry:
    registry = PredicateRegistry()

    def euler(n: int) -> PredicateEvaluation:
        value = n * n + n + 41
        return PredicateEvaluation(_prime_by_trial_division(value), value)

    def fermat(n: int) -> PredicateEvaluation:
        value = 2 ** (2**n) + 1
        return PredicateEvaluation(_prime_by_trial_division(value), value)

    def odd_sum(n: int) -> PredicateEvaluation:
        left = n * (1 + (2 * n - 1)) // 2 if n else 0
        right = n * n
        return PredicateEvaluation(left == right, right)

    registry.register("euler_prime", euler)
    registry.register("fermat_prime", fermat)
    registry.register("sum_odds", odd_sum)
    return registry
