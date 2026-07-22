"""OpenAI Responses API adapter for provider-neutral structured output."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from time import monotonic
from types import MappingProxyType
from typing import Any, TypeIs

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from openai.types.responses.input_token_count_params import Text as InputTokenCountText
from openai.types.responses.response_format_text_config_param import (
    ResponseFormatTextConfigParam,
)
from openai.types.responses.response_input_param import ResponseInputParam
from openai.types.shared_params.reasoning import Reasoning

from mathloop.billing import DATABASE_USD_QUANTUM, BillingAuthorization, BillingReceipt
from mathloop.providers.base import (
    IncompleteModelResponseError,
    InvalidModelResponseError,
    ModelCostAuthorizationError,
    ModelProviderError,
    ModelRefusalError,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    RetryableModelProviderError,
    T,
)
from mathloop.providers.openai_sdk_2_47 import strict_text_format_for_schema

OPENAI_PRICING_VERSION = "2026-07-22"
OPENAI_LONG_CONTEXT_THRESHOLD_TOKENS = 272_000
TOKENS_PER_PRICING_UNIT = Decimal(1_000_000)


@dataclass(frozen=True)
class OpenAITextPricing:
    input_per_million_usd: Decimal
    cached_input_per_million_usd: Decimal
    output_per_million_usd: Decimal
    source: str

    @property
    def cache_write_per_million_usd(self) -> Decimal:
        return self.input_per_million_usd * Decimal("1.25")


# Official model catalog prices retrieved 2026-07-22. Each model page also
# specifies cache writes at 1.25x uncached input and the >272K token multiplier.
# https://developers.openai.com/api/docs/models/gpt-5.6-sol
# https://developers.openai.com/api/docs/models/gpt-5.6-terra
# https://developers.openai.com/api/docs/models/gpt-5.6-luna
_SOL_PRICING = OpenAITextPricing(
    input_per_million_usd=Decimal("5.00"),
    cached_input_per_million_usd=Decimal("0.50"),
    output_per_million_usd=Decimal("30.00"),
    source="https://developers.openai.com/api/docs/models/gpt-5.6-sol",
)
OPENAI_PRICING_CATALOG: Mapping[str, OpenAITextPricing] = MappingProxyType(
    {
        "gpt-5.6": _SOL_PRICING,
        "gpt-5.6-sol": _SOL_PRICING,
        "gpt-5.6-terra": OpenAITextPricing(
            input_per_million_usd=Decimal("2.50"),
            cached_input_per_million_usd=Decimal("0.25"),
            output_per_million_usd=Decimal("15.00"),
            source="https://developers.openai.com/api/docs/models/gpt-5.6-terra",
        ),
        "gpt-5.6-luna": OpenAITextPricing(
            input_per_million_usd=Decimal("1.00"),
            cached_input_per_million_usd=Decimal("0.10"),
            output_per_million_usd=Decimal("6.00"),
            source="https://developers.openai.com/api/docs/models/gpt-5.6-luna",
        ),
    }
)


class OpenAIProvider:
    """Issue exact-counted, synchronous structured Responses API requests."""

    def __init__(
        self,
        client: OpenAI | Any | None = None,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if client is None:
            self.client = OpenAI(max_retries=0)
        elif isinstance(client, OpenAI):
            self.client = client.with_options(max_retries=0)
        else:
            self.client = client
        self.clock = clock

    def generate(self, request: ModelRequest, schema: type[T]) -> ModelResponse[T]:
        deadline = self.clock() + request.timeout_seconds
        pricing = OPENAI_PRICING_CATALOG.get(request.model)
        if pricing is None:
            raise ModelCostAuthorizationError(
                f"OpenAI model is unpriced and cannot be authorized: {request.model}"
            )

        model_input: ResponseInputParam = [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.prompt},
        ]
        reasoning: Reasoning = {"effort": request.effort, "context": "current_turn"}
        text_format = strict_text_format_for_schema(schema)
        authorization = self._authorize_request_cost(
            request=request,
            pricing=pricing,
            model_input=model_input,
            reasoning=reasoning,
            text_format=text_format,
            deadline=deadline,
        )

        try:
            timeout = self._remaining_timeout(deadline)
            response = self.client.responses.parse(
                model=request.model,
                input=model_input,
                text_format=schema,
                reasoning=reasoning,
                max_output_tokens=request.max_output_tokens,
                store=False,
                timeout=timeout,
            )
        except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
            raise _retryable_provider_error(exc) from exc
        self._remaining_timeout(deadline)

        status = getattr(response, "status", None)
        if status == "incomplete":
            details = getattr(response, "incomplete_details", None)
            reason = getattr(details, "reason", "unknown")
            raise IncompleteModelResponseError(f"model response was incomplete: {reason}")
        if status in {"failed", "cancelled", "in_progress", "queued"}:
            raise ModelProviderError(f"model response has unusable status: {status}")

        refusal = _find_refusal(getattr(response, "output", ()))
        if refusal is not None:
            raise ModelRefusalError(f"model refused the request: {refusal}")

        parsed = getattr(response, "output_parsed", None)
        if not isinstance(parsed, schema):
            raise InvalidModelResponseError("model returned no valid structured output")

        response_id = getattr(response, "id", None)
        if type(response_id) is not str or not response_id.strip():
            raise InvalidModelResponseError("model response id is missing or invalid")

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        input_details = getattr(usage, "input_tokens_details", None)
        cached_input_tokens = getattr(input_details, "cached_tokens", None)
        cache_write_input_tokens = getattr(input_details, "cache_write_tokens", None)
        if not _valid_token_count(input_tokens):
            raise InvalidModelResponseError("model response usage is missing or invalid")
        if not _valid_token_count(output_tokens):
            raise InvalidModelResponseError("model response usage is missing or invalid")
        if not _valid_token_count(cached_input_tokens):
            raise InvalidModelResponseError("model response usage is missing or invalid")
        if not _valid_token_count(cache_write_input_tokens):
            raise InvalidModelResponseError("model response usage is missing or invalid")
        if input_tokens != authorization.authorized_input_tokens:
            raise InvalidModelResponseError(
                "model response input tokens differ from exact authorized input tokens"
            )
        if output_tokens > authorization.max_output_tokens:
            raise InvalidModelResponseError(
                "model response output tokens exceed authorized maximum"
            )
        if cached_input_tokens + cache_write_input_tokens > input_tokens:
            raise InvalidModelResponseError("model response usage token details are inconsistent")

        model_usage = ModelUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_input_tokens=cache_write_input_tokens,
        )
        actual_cost = _actual_cost_usd(model_usage, pricing)
        if (
            actual_cost > authorization.reserved_cost_usd
            or actual_cost > request.cost_authorization.max_cost_usd
        ):
            raise InvalidModelResponseError("actual cost exceeds authorized reserved cost")

        receipt = BillingReceipt(
            provider="openai",
            model=request.model,
            response_id=response_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_input_tokens=cache_write_input_tokens,
            actual_cost_usd=actual_cost,
            pricing_version=OPENAI_PRICING_VERSION,
            pricing_source=pricing.source,
            authorization=authorization,
        )
        model_response = ModelResponse(
            value=parsed,
            provider_response_id=response_id,
            usage=model_usage,
            billing_authorization=authorization,
            billing_receipt=receipt,
        )
        self._remaining_timeout(deadline)
        return model_response

    def _authorize_request_cost(
        self,
        *,
        request: ModelRequest,
        pricing: OpenAITextPricing,
        model_input: ResponseInputParam,
        reasoning: Reasoning,
        text_format: ResponseFormatTextConfigParam,
        deadline: float,
    ) -> BillingAuthorization:
        try:
            count_text: InputTokenCountText = {"format": text_format}
            # Official exact-count endpoint: POST /responses/input_tokens.
            timeout = self._remaining_timeout(deadline)
            count_response = self.client.responses.input_tokens.count(
                model=request.model,
                input=model_input,
                reasoning=reasoning,
                text=count_text,
                timeout=timeout,
            )
        except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
            raise _retryable_provider_error(exc) from exc

        exact_input_tokens = getattr(count_response, "input_tokens", None)
        if not _valid_token_count(exact_input_tokens):
            raise InvalidModelResponseError("exact input token count is missing or invalid")

        reserved_cost = _reserved_cost_usd(
            input_tokens=exact_input_tokens,
            max_output_tokens=request.max_output_tokens,
            pricing=pricing,
        )
        authorization = BillingAuthorization(
            provider="openai",
            model=request.model,
            authorized_input_tokens=exact_input_tokens,
            max_output_tokens=request.max_output_tokens,
            reserved_cost_usd=reserved_cost,
            pricing_version=OPENAI_PRICING_VERSION,
            pricing_source=pricing.source,
        )
        if reserved_cost > request.cost_authorization.max_cost_usd:
            raise ModelCostAuthorizationError(
                "reserved request cost exceeds authorized cap "
                f"({reserved_cost} > {request.cost_authorization.max_cost_usd})"
            )
        return authorization

    def _remaining_timeout(self, deadline: float) -> float:
        remaining = deadline - self.clock()
        if remaining <= 0:
            raise RetryableModelProviderError("model request deadline exhausted")
        return remaining


def _reserved_cost_usd(
    *, input_tokens: int, max_output_tokens: int, pricing: OpenAITextPricing
) -> Decimal:
    input_multiplier, output_multiplier = _long_context_multipliers(input_tokens)
    cost = (
        Decimal(input_tokens) * pricing.cache_write_per_million_usd * input_multiplier
        + Decimal(max_output_tokens) * pricing.output_per_million_usd * output_multiplier
    ) / TOKENS_PER_PRICING_UNIT
    return cost.quantize(DATABASE_USD_QUANTUM, rounding=ROUND_CEILING)


def _actual_cost_usd(usage: ModelUsage, pricing: OpenAITextPricing) -> Decimal:
    ordinary_input_tokens = (
        usage.input_tokens - usage.cached_input_tokens - usage.cache_write_input_tokens
    )
    input_multiplier, output_multiplier = _long_context_multipliers(usage.input_tokens)
    cost = (
        Decimal(ordinary_input_tokens) * pricing.input_per_million_usd * input_multiplier
        + Decimal(usage.cached_input_tokens)
        * pricing.cached_input_per_million_usd
        * input_multiplier
        + Decimal(usage.cache_write_input_tokens)
        * pricing.cache_write_per_million_usd
        * input_multiplier
        + Decimal(usage.output_tokens) * pricing.output_per_million_usd * output_multiplier
    ) / TOKENS_PER_PRICING_UNIT
    return cost.quantize(DATABASE_USD_QUANTUM, rounding=ROUND_CEILING)


def _long_context_multipliers(input_tokens: int) -> tuple[Decimal, Decimal]:
    if input_tokens > OPENAI_LONG_CONTEXT_THRESHOLD_TOKENS:
        return Decimal("2"), Decimal("1.5")
    return Decimal("1"), Decimal("1")


def _retryable_provider_error(exc: Exception) -> RetryableModelProviderError:
    return RetryableModelProviderError(
        f"transient OpenAI Responses API failure: {type(exc).__name__}"
    )


def _valid_token_count(value: object) -> TypeIs[int]:
    return type(value) is int and value >= 0


def _field(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _find_refusal(output: object) -> str | None:
    if isinstance(output, (str, bytes)) or not isinstance(output, (list, tuple)):
        return None
    for item in output:
        content = _field(item, "content", ())
        if isinstance(content, (str, bytes)) or not isinstance(content, (list, tuple)):
            continue
        for part in content:
            if _field(part, "type") != "refusal":
                continue
            refusal = _field(part, "refusal")
            return refusal if type(refusal) is str and refusal else "unspecified refusal"
    return None
