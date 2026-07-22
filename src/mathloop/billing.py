"""Provider-neutral billing authorizations and receipts."""

from dataclasses import dataclass
from decimal import Decimal

DATABASE_USD_QUANTUM = Decimal("0.000001")


def validate_database_usd(value: Decimal, *, field_name: str, positive: bool) -> None:
    if type(value) is not Decimal:
        raise TypeError(f"{field_name} must be a Decimal")
    if not value.is_finite() or value < 0 or (positive and value == 0):
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{field_name} must be finite and {qualifier}")
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -6:
        raise ValueError(f"{field_name} must use at most six decimal places")


def _validate_nonempty_strings(value: object, names: tuple[str, ...]) -> None:
    for name in names:
        field_value = getattr(value, name)
        if type(field_value) is not str:
            raise TypeError(f"{name} must be a string")
        if not field_value.strip():
            raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class BillingAuthorization:
    provider: str
    model: str
    authorized_input_tokens: int
    max_output_tokens: int
    reserved_cost_usd: Decimal
    pricing_version: str
    pricing_source: str

    def __post_init__(self) -> None:
        _validate_nonempty_strings(
            self, ("provider", "model", "pricing_version", "pricing_source")
        )
        if type(self.authorized_input_tokens) is not int:
            raise TypeError("authorized_input_tokens must be an integer")
        if self.authorized_input_tokens < 0:
            raise ValueError("authorized_input_tokens must be non-negative")
        if type(self.max_output_tokens) is not int:
            raise TypeError("max_output_tokens must be an integer")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        validate_database_usd(
            self.reserved_cost_usd, field_name="reserved_cost_usd", positive=False
        )

    def to_audit_dict(self) -> dict[str, str | int]:
        return {
            "provider": self.provider,
            "model": self.model,
            "authorized_input_tokens": self.authorized_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "reserved_cost_usd": format(self.reserved_cost_usd, "f"),
            "pricing_version": self.pricing_version,
            "pricing_source": self.pricing_source,
        }


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
    authorization: BillingAuthorization

    def __post_init__(self) -> None:
        _validate_nonempty_strings(
            self,
            (
                "provider",
                "model",
                "response_id",
                "pricing_version",
                "pricing_source",
            ),
        )

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
        validate_database_usd(
            self.actual_cost_usd, field_name="actual_cost_usd", positive=False
        )
        if not isinstance(self.authorization, BillingAuthorization):
            raise TypeError("authorization must be a BillingAuthorization")
        if self.provider != self.authorization.provider:
            raise ValueError("receipt provider does not match authorization")
        if self.model != self.authorization.model:
            raise ValueError("receipt model does not match authorization")
        if self.pricing_version != self.authorization.pricing_version:
            raise ValueError("receipt pricing version does not match authorization")
        if self.pricing_source != self.authorization.pricing_source:
            raise ValueError("receipt pricing source does not match authorization")
        if self.input_tokens != self.authorization.authorized_input_tokens:
            raise ValueError("receipt input tokens do not match authorization")
        if self.output_tokens > self.authorization.max_output_tokens:
            raise ValueError("receipt output tokens exceed authorization")
        if self.actual_cost_usd > self.authorization.reserved_cost_usd:
            raise ValueError("receipt actual cost exceeds authorization")

    def to_audit_dict(self) -> dict[str, str | int | dict[str, str | int]]:
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
            "authorization": self.authorization.to_audit_dict(),
        }
