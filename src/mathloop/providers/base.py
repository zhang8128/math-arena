"""Typed, provider-neutral structured model contracts."""

from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

from mathloop.billing import BillingAuthorization, BillingReceipt, validate_database_usd

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]
SUPPORTED_REASONING_EFFORTS = frozenset({"none", "low", "medium", "high", "xhigh", "max"})
MAX_MODEL_OUTPUT_TOKENS = 128_000
MAX_MODEL_PROMPT_BYTES = 65_536

T = TypeVar("T", bound=BaseModel)


class ModelProviderError(RuntimeError):
    """A provider returned a result that cannot satisfy the model contract."""


class ModelCostAuthorizationError(ModelProviderError):
    """A request has no known price or exceeds its authorized cost."""


class RetryableModelProviderError(ModelProviderError, TimeoutError):
    """A transient provider failure that the worker may classify like a timeout."""


class InvalidModelResponseError(ModelProviderError):
    """A provider result is missing or contains invalid structured data."""


class IncompleteModelResponseError(ModelProviderError):
    """A provider stopped before producing a complete structured result."""


class ModelRefusalError(ModelProviderError):
    """A provider declined to fulfill the structured model request."""


@dataclass(frozen=True)
class ModelCostAuthorization:
    max_cost_usd: Decimal

    def __post_init__(self) -> None:
        validate_database_usd(self.max_cost_usd, field_name="max_cost_usd", positive=True)


@dataclass(frozen=True)
class ModelRequest:
    model: str
    system: str
    prompt: str
    effort: ReasoningEffort
    max_output_tokens: int
    timeout_seconds: float
    cost_authorization: ModelCostAuthorization

    def __post_init__(self) -> None:
        for name in ("model", "system", "prompt"):
            value = getattr(self, name)
            if type(value) is not str:
                raise TypeError(f"{name} must be a string")
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        prompt_bytes = len(self.system.encode("utf-8")) + len(self.prompt.encode("utf-8"))
        if prompt_bytes > MAX_MODEL_PROMPT_BYTES:
            raise ValueError(
                f"combined prompt content exceeds {MAX_MODEL_PROMPT_BYTES} UTF-8 bytes"
            )
        if type(self.effort) is not str:
            raise TypeError("effort must be a string")
        if self.effort not in SUPPORTED_REASONING_EFFORTS:
            raise ValueError(f"unsupported reasoning effort: {self.effort}")
        if type(self.max_output_tokens) is not int:
            raise TypeError("max_output_tokens must be an integer")
        if not 1 <= self.max_output_tokens <= MAX_MODEL_OUTPUT_TOKENS:
            raise ValueError(
                f"max_output_tokens must be between 1 and {MAX_MODEL_OUTPUT_TOKENS}"
            )
        if type(self.timeout_seconds) not in (int, float):
            raise TypeError("timeout_seconds must be a number")
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if not isinstance(self.cost_authorization, ModelCostAuthorization):
            raise TypeError("cost_authorization must be a ModelCostAuthorization")


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    cache_write_input_tokens: int

    def __post_init__(self) -> None:
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


@dataclass(frozen=True)
class ModelResponse[ResponseT: BaseModel]:
    value: ResponseT
    provider_response_id: str
    usage: ModelUsage
    billing_authorization: BillingAuthorization
    billing_receipt: BillingReceipt

    def __post_init__(self) -> None:
        if type(self.provider_response_id) is not str:
            raise TypeError("provider_response_id must be a string")
        if not self.provider_response_id.strip():
            raise ValueError("provider_response_id must not be empty")
        if self.billing_receipt.response_id != self.provider_response_id:
            raise ValueError("billing receipt response id does not match model response")
        if self.billing_receipt.authorization != self.billing_authorization:
            raise ValueError("billing receipt does not retain model response authorization")
        if (
            self.billing_receipt.input_tokens != self.usage.input_tokens
            or self.billing_receipt.output_tokens != self.usage.output_tokens
            or self.billing_receipt.cached_input_tokens != self.usage.cached_input_tokens
            or self.billing_receipt.cache_write_input_tokens
            != self.usage.cache_write_input_tokens
        ):
            raise ValueError("billing receipt token counts do not match model usage")


class ModelProvider(Protocol):
    def generate(self, request: ModelRequest, schema: type[T]) -> ModelResponse[T]: ...
