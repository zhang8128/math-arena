"""Typed, provider-neutral structured model contracts."""

from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh", "max"]
SUPPORTED_REASONING_EFFORTS = frozenset({"none", "low", "medium", "high", "xhigh", "max"})
MAX_MODEL_OUTPUT_TOKENS = 128_000

T = TypeVar("T", bound=BaseModel)


class ModelProviderError(RuntimeError):
    """A provider returned a result that cannot satisfy the model contract."""


class InvalidModelResponseError(ModelProviderError):
    """A provider result is missing or contains invalid structured data."""


class IncompleteModelResponseError(ModelProviderError):
    """A provider stopped before producing a complete structured result."""


class ModelRefusalError(ModelProviderError):
    """A provider declined to fulfill the structured model request."""


@dataclass(frozen=True)
class ModelRequest:
    model: str
    system: str
    prompt: str
    effort: ReasoningEffort
    max_output_tokens: int = 4096

    def __post_init__(self) -> None:
        for name in ("model", "system", "prompt"):
            value = getattr(self, name)
            if type(value) is not str:
                raise TypeError(f"{name} must be a string")
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
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


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ModelResponse[ResponseT: BaseModel]:
    value: ResponseT
    provider_response_id: str
    usage: ModelUsage


class ModelProvider(Protocol):
    def generate(self, request: ModelRequest, schema: type[T]) -> ModelResponse[T]: ...
