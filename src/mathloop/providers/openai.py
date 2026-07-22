"""OpenAI Responses API adapter for provider-neutral structured output."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from types import MappingProxyType
from typing import Any, TypeIs

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from mathloop.billing import DATABASE_USD_QUANTUM, BillingReceipt
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

OPENAI_PRICING_VERSION = "2026-07-22"
OPENAI_CONSERVATIVE_MESSAGE_OVERHEAD_TOKENS = 4096
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
    """Issue synchronous, non-persistent structured Responses API requests.

    Optional method registration and API-key capability reporting belong to the
    runtime wiring layer, not this adapter.
    """

    def __init__(self, client: OpenAI | Any | None = None) -> None:
        self.client = client if client is not None else OpenAI()

    def generate(self, request: ModelRequest, schema: type[T]) -> ModelResponse[T]:
        pricing = _authorize_request_cost(request, schema)

        try:
            response = self.client.responses.parse(
                model=request.model,
                input=[
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.prompt},
                ],
                text_format=schema,
                reasoning={"effort": request.effort, "context": "current_turn"},
                max_output_tokens=request.max_output_tokens,
                store=False,
                timeout=request.timeout_seconds,
            )
        except (APITimeoutError, APIConnectionError, RateLimitError) as exc:
            raise RetryableModelProviderError(
                f"transient OpenAI Responses API failure: {type(exc).__name__}"
            ) from exc

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
        if cached_input_tokens + cache_write_input_tokens > input_tokens:
            raise InvalidModelResponseError("model response usage token details are inconsistent")

        model_usage = ModelUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            cache_write_input_tokens=cache_write_input_tokens,
        )
        actual_cost = _actual_cost_usd(model_usage, pricing)
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
        )
        return ModelResponse(
            value=parsed,
            provider_response_id=response_id,
            usage=model_usage,
            billing_receipt=receipt,
        )


def _authorize_request_cost(request: ModelRequest, schema: type[T]) -> OpenAITextPricing:
    pricing = OPENAI_PRICING_CATALOG.get(request.model)
    if pricing is None:
        raise ModelCostAuthorizationError(
            f"OpenAI model is unpriced and cannot be authorized: {request.model}"
        )

    schema_json = json.dumps(
        schema.model_json_schema(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    content_bytes = (
        len(request.system.encode("utf-8"))
        + len(request.prompt.encode("utf-8"))
        + len(schema_json.encode("utf-8"))
    )
    worst_case_input_tokens = content_bytes + OPENAI_CONSERVATIVE_MESSAGE_OVERHEAD_TOKENS
    input_multiplier, output_multiplier = _long_context_multipliers(worst_case_input_tokens)
    worst_case_cost = (
        Decimal(worst_case_input_tokens)
        * pricing.cache_write_per_million_usd
        * input_multiplier
        + Decimal(request.max_output_tokens)
        * pricing.output_per_million_usd
        * output_multiplier
    ) / TOKENS_PER_PRICING_UNIT
    if worst_case_cost > request.cost_authorization.max_cost_usd:
        raise ModelCostAuthorizationError(
            "authorized cost cap cannot cover worst-case request cost "
            f"({worst_case_cost} > {request.cost_authorization.max_cost_usd})"
        )
    return pricing


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
