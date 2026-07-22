"""OpenAI Responses API adapter for provider-neutral structured output."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeIs

from openai import OpenAI

from mathloop.providers.base import (
    IncompleteModelResponseError,
    InvalidModelResponseError,
    ModelProviderError,
    ModelRefusalError,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    T,
)


class OpenAIProvider:
    """Issue synchronous, non-persistent structured Responses API requests.

    Optional method registration and API-key capability reporting belong to the
    runtime wiring layer, not this adapter.
    """

    def __init__(self, client: OpenAI | Any | None = None) -> None:
        self.client = client if client is not None else OpenAI()

    def generate(self, request: ModelRequest, schema: type[T]) -> ModelResponse[T]:
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
        )

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
        if not _valid_token_count(input_tokens) or not _valid_token_count(output_tokens):
            raise InvalidModelResponseError("model response usage is missing or invalid")

        return ModelResponse(
            value=parsed,
            provider_response_id=response_id,
            usage=ModelUsage(input_tokens=input_tokens, output_tokens=output_tokens),
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
