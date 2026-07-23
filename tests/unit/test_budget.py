from decimal import Decimal

from mathloop.scheduling import BudgetLedger


def test_budget_rejects_overspend_before_external_call() -> None:
    ledger = BudgetLedger(limit_usd=Decimal("1.0"), spent_usd=Decimal("0.8"))

    assert ledger.authorize(estimated_cost_usd=Decimal("0.19")) is True
    assert ledger.authorize(estimated_cost_usd=Decimal("0.21")) is False
