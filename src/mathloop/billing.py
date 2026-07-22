"""Provider-neutral billing records for experiment settlement and audit."""

from dataclasses import dataclass
from decimal import Decimal

DATABASE_USD_QUANTUM = Decimal("0.000001")


@dataclass(frozen=True)
class BillingReceipt:
    provider: str
    model: str
    response_id: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int
    actual_cost_usd: Decimal
    pricing_version: str
    pricing_source: str

    def __post_init__(self) -> None:
        for name in (
            "provider",
            "model",
            "response_id",
            "pricing_version",
            "pricing_source",
        ):
            value = getattr(self, name)
            if type(value) is not str:
                raise TypeError(f"{name} must be a string")
            if not value.strip():
                raise ValueError(f"{name} must not be empty")

        for name in (
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "cache_write_input_tokens",
        ):
            value = getattr(self, name)
            if type(value) is not int:
                raise TypeError(f"{name} must be an integer")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")

        if self.cached_input_tokens + self.cache_write_input_tokens > self.input_tokens:
            raise ValueError("cached and cache-write tokens cannot exceed input tokens")

        if type(self.actual_cost_usd) is not Decimal:
            raise TypeError("actual_cost_usd must be a Decimal")
        if not self.actual_cost_usd.is_finite() or self.actual_cost_usd < 0:
            raise ValueError("actual_cost_usd must be finite and non-negative")
        exponent = self.actual_cost_usd.as_tuple().exponent
        if not isinstance(exponent, int) or exponent < -6:
            raise ValueError("actual_cost_usd must use at most six decimal places")

    def to_audit_dict(self) -> dict[str, str | int]:
        return {
            "provider": self.provider,
            "model": self.model,
            "response_id": self.response_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "actual_cost_usd": format(self.actual_cost_usd, "f"),
            "pricing_version": self.pricing_version,
            "pricing_source": self.pricing_source,
        }
