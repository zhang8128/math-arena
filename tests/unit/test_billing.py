from decimal import Decimal

import pytest

from mathloop.billing import BillingReceipt


def valid_receipt(**overrides: object) -> BillingReceipt:
    values: dict[str, object] = {
        "provider": "openai",
        "model": "gpt-5.6-sol",
        "response_id": "resp_test",
        "input_tokens": 100,
        "output_tokens": 25,
        "cached_input_tokens": 20,
        "cache_write_input_tokens": 30,
        "actual_cost_usd": Decimal("0.001198"),
        "pricing_version": "2026-07-22",
        "pricing_source": "https://developers.openai.com/api/docs/models/gpt-5.6-sol",
    }
    values.update(overrides)
    return BillingReceipt(**values)  # type: ignore[arg-type]


def test_billing_receipt_exposes_validated_provider_neutral_audit_data() -> None:
    receipt = valid_receipt()

    assert receipt.to_audit_dict() == {
        "provider": "openai",
        "model": "gpt-5.6-sol",
        "response_id": "resp_test",
        "input_tokens": 100,
        "output_tokens": 25,
        "cached_input_tokens": 20,
        "cache_write_input_tokens": 30,
        "actual_cost_usd": "0.001198",
        "pricing_version": "2026-07-22",
        "pricing_source": "https://developers.openai.com/api/docs/models/gpt-5.6-sol",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", ""),
        ("provider", 1),
        ("model", "  "),
        ("response_id", None),
        ("pricing_version", ""),
        ("pricing_source", "\n"),
        ("input_tokens", -1),
        ("input_tokens", True),
        ("output_tokens", -1),
        ("cached_input_tokens", -1),
        ("cache_write_input_tokens", False),
        ("actual_cost_usd", Decimal("-0.000001")),
        ("actual_cost_usd", Decimal("NaN")),
        ("actual_cost_usd", 0.1),
    ],
)
def test_billing_receipt_rejects_invalid_fields(field: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        valid_receipt(**{field: value})


@pytest.mark.parametrize(
    "overrides",
    [
        {"cached_input_tokens": 101},
        {"cache_write_input_tokens": 101},
        {"cached_input_tokens": 60, "cache_write_input_tokens": 41},
        {"actual_cost_usd": Decimal("0.0000001")},
        {"actual_cost_usd": Decimal("0.0011980")},
    ],
)
def test_billing_receipt_rejects_impossible_counts_or_sub_database_precision(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        valid_receipt(**overrides)
