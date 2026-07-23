from decimal import Decimal

from mathloop.evolution import ucb_score
from mathloop.runtime import _comparable_budgets


def test_synthetic_equal_budget_adaptive_routing_beats_fixed_calibration() -> None:
    """Calibration demonstration only; it is not evidence of research improvement."""
    domains = ["algebra", "number_theory"] * 12
    outcomes = {
        ("algebra", "method-a"): 1,
        ("algebra", "method-b"): 0,
        ("number_theory", "method-a"): 0,
        ("number_theory", "method-b"): 1,
    }
    methods = ("method-a", "method-b")
    scores = {
        (domain, method): {"trials": 0, "verified": 0}
        for domain in {"algebra", "number_theory"}
        for method in methods
    }
    adaptive_verified = 0
    fixed_verified = 0
    for domain in domains:
        fixed_verified += outcomes[(domain, "method-a")]
        total_trials = sum(scores[(domain, method)]["trials"] for method in methods)
        selected = max(
            methods,
            key=lambda method: ucb_score(
                scores[(domain, method)]["verified"],
                scores[(domain, method)]["trials"],
                total_trials,
            ),
        )
        outcome = outcomes[(domain, selected)]
        scores[(domain, selected)]["trials"] += 1
        scores[(domain, selected)]["verified"] += outcome
        adaptive_verified += outcome

    assert len(domains) == 24  # equal experiment budgets
    assert adaptive_verified > fixed_verified


def test_holdout_budget_comparison_includes_search_work_not_only_dollars() -> None:
    assert not _comparable_budgets(Decimal("0"), Decimal("0"), parent_work=100, child_work=200)
    assert _comparable_budgets(Decimal("0"), Decimal("0"), parent_work=100, child_work=105)
