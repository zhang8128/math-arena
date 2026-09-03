"""Tests for the certified prime-run bound (T29).

The point of these is that the lemma is a counting argument, so it must be
checkable independently of the search that motivated it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from primerun_bounds import (  # noqa: E402
    audit_all_primes,
    cauchy_bound,
    certified_max_run,
    least_root_prime,
    poly_eval,
    roots_mod_p,
    run_bound,
    value_equals_prime_points,
)


def test_poly_eval_is_highest_degree_first():
    assert poly_eval((1, 1, 41), 0) == 41
    assert poly_eval((1, 1, 41), 40) == 1681
    assert poly_eval((1, 0, 0, -2), 3) == 25  # n^3 - 2


def test_euler_polynomial_least_root_prime_is_41():
    # Rabinowitsch: n^2+n+41 is prime for n=0..39, so no prime below 41 divides
    # any value; 41 | f(40) = 41^2.
    assert least_root_prime((1, 1, 41)) == 41
    assert roots_mod_p((1, 1, 41), 41) == [0, 40]


def test_euler_polynomial_certified_global_max_run_is_80():
    res = certified_max_run((1, 1, 41))
    assert res["p"] == 41 and res["r"] == 2
    assert res["max_run"] == 80 and res["start"] == -40
    assert res["certified"] and res["certified_claim"] == "global max over Z"


def test_t10_counterexample_form_reproduces():
    # notebook/rabinowitsch-families.md T10: 7n^2+3n+7 has run 13 = 2p-1, p=7,
    # because f(0) = 7 = p is the prime itself and does not break the run.
    res = certified_max_run((7, 3, 7))
    assert res["p"] == 7
    assert res["max_run"] == 13
    assert res["certified"]


def test_value_equals_prime_points_is_complete():
    # f(n) = n^2 + n + 41 takes the value 41 exactly at n = 0 and n = -1.
    assert value_equals_prime_points((1, 1, 41), 41) == [-1, 0]
    # f(n) = n^2 - 5 takes value +-11 at n = +-4 and value -11 nowhere else.
    assert value_equals_prime_points((1, 0, -5), 11) == [-4, 4]


def test_cauchy_bound_contains_every_integer_root():
    coeffs = (1, 0, -7, 6)  # roots 1, 2, -3
    b = cauchy_bound(coeffs)
    for root in (1, 2, -3):
        assert abs(root) <= b


def test_run_bound_formula():
    # degree 2, one root class: floor(4/1)+1 = 5, so L <= 5p-1.
    assert run_bound(2, 1, 7) == 34
    # degree 2, two root classes: floor(4/2)+1 = 3.
    assert run_bound(2, 2, 41) == 122
    # degree 3, one root class: floor(6/1)+1 = 7.
    assert run_bound(3, 1, 5) == 34


def test_lemma_holds_on_a_batch_of_quadratics():
    violations = []
    for a in range(1, 6):
        for b in range(-6, 7):
            for c in range(-40, 41):
                if a == 0:
                    continue
                violations += audit_all_primes((a, b, c), -60, 60, prime_cap=60)
    assert violations == []


def test_no_anchor_forces_short_runs():
    # 2n^2+2n+1 is odd for all n but 3 | f(1) = 5? check a case where |f| = p is
    # unattainable: f(n) = n^2 + n + 43.  3 | f(1) = 45, and |f(n)| = 3 never.
    res = certified_max_run((1, 1, 43))
    assert res["p"] == 3
    assert res["anchors"] == []
    assert res["certified_claim"] == "max_run <= p-1"
