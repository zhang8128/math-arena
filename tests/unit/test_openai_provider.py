from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIConnectionError, APITimeoutError, RateLimitError
from pydantic import BaseModel

from mathloop.methods.proof_sketch import ProofSketch
from mathloop.providers.base import (
    MAX_MODEL_OUTPUT_TOKENS,
    MAX_MODEL_PROMPT_BYTES,
    ModelCostAuthorization,
    ModelCostAuthorizationError,
    ModelRequest,
    RetryableModelProviderError,
)
from mathloop.providers.openai import (
    IncompleteModelResponseError,
    InvalidModelResponseError,
    ModelRefusalError,
    OpenAIProvider,
)


class AlternateOutput(BaseModel):
    answer: str


class FakeResponses:
    def __init__(self, response: object, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def fake_provider(
    response: object, error: Exception | None = None
) -> tuple[OpenAIProvider, FakeResponses]:
    responses = FakeResponses(response, error=error)
    client = SimpleNamespace(responses=responses)
    return OpenAIProvider(client=client), responses


def valid_response(parsed: BaseModel) -> SimpleNamespace:
    return SimpleNamespace(
        output_parsed=parsed,
        id="resp_test",
        status="completed",
        output=[],
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=25,
            input_tokens_details=SimpleNamespace(cached_tokens=20, cache_write_tokens=30),
        ),
    )


def request(**overrides: object) -> ModelRequest:
    values: dict[str, object] = {
        "model": "gpt-5.6-luna",
        "system": "Propose only.",
        "prompt": "Problem",
        "effort": "low",
        "max_output_tokens": 4096,
        "timeout_seconds": 31,
        "cost_authorization": ModelCostAuthorization(max_cost_usd=Decimal("1.00")),
    }
    values.update(overrides)
    return ModelRequest(**values)  # type: ignore[arg-type]


def test_openai_provider_returns_generic_typed_output_usage_and_billing() -> None:
    parsed = AlternateOutput(answer="induction")
    provider, _ = fake_provider(valid_response(parsed))

    result = provider.generate(request(), AlternateOutput)

    assert result.value is parsed
    assert result.provider_response_id == "resp_test"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 25
    assert result.usage.cached_input_tokens == 20
    assert result.usage.cache_write_input_tokens == 30
    assert result.billing_receipt.actual_cost_usd == Decimal("0.000240")


def test_openai_provider_sends_exact_nonpersistent_parse_request_with_timeout() -> None:
    parsed = ProofSketch(strategy="induction", lemmas=["base case"], risks=["gap"])
    provider, responses = fake_provider(valid_response(parsed))
    model_request = request(
        model="gpt-5.6-terra",
        system="Propose only.",
        prompt="  exact normalized problem  ",
        effort="xhigh",
        max_output_tokens=1234,
        timeout_seconds=17,
    )

    provider.generate(model_request, ProofSketch)

    assert responses.calls == [
        {
            "model": "gpt-5.6-terra",
            "input": [
                {"role": "system", "content": "Propose only."},
                {"role": "user", "content": "  exact normalized problem  "},
            ],
            "text_format": ProofSketch,
            "reasoning": {"effort": "xhigh", "context": "current_turn"},
            "max_output_tokens": 1234,
            "store": False,
            "timeout": 17,
        }
    ]


def test_openai_provider_rejects_unauthorized_worst_case_cost_before_parse() -> None:
    provider, responses = fake_provider(valid_response(AlternateOutput(answer="unused")))

    with pytest.raises(ModelCostAuthorizationError, match="worst-case"):
        provider.generate(
            request(
                model="gpt-5.6-sol",
                max_output_tokens=128_000,
                cost_authorization=ModelCostAuthorization(
                    max_cost_usd=Decimal("0.000001")
                ),
            ),
            AlternateOutput,
        )

    assert responses.calls == []


def test_openai_provider_fails_closed_for_unpriced_model_before_parse() -> None:
    provider, responses = fake_provider(valid_response(AlternateOutput(answer="unused")))

    with pytest.raises(ModelCostAuthorizationError, match="unpriced"):
        provider.generate(request(model="gpt-unknown"), AlternateOutput)

    assert responses.calls == []


def test_openai_provider_prices_cache_details_and_rounds_cost_upward() -> None:
    parsed = AlternateOutput(answer="induction")
    provider, _ = fake_provider(valid_response(parsed))

    result = provider.generate(request(model="gpt-5.6-sol"), AlternateOutput)

    receipt = result.billing_receipt
    assert receipt.provider == "openai"
    assert receipt.model == "gpt-5.6-sol"
    assert receipt.response_id == "resp_test"
    assert receipt.input_tokens == 100
    assert receipt.output_tokens == 25
    assert receipt.cached_input_tokens == 20
    assert receipt.cache_write_input_tokens == 30
    assert receipt.actual_cost_usd == Decimal("0.001198")
    assert receipt.pricing_version == "2026-07-22"
    assert receipt.pricing_source == (
        "https://developers.openai.com/api/docs/models/gpt-5.6-sol"
    )


def test_openai_provider_prices_family_alias_as_sol_with_alias_on_receipt() -> None:
    provider, _ = fake_provider(valid_response(AlternateOutput(answer="induction")))

    result = provider.generate(request(model="gpt-5.6"), AlternateOutput)

    assert result.billing_receipt.model == "gpt-5.6"
    assert result.billing_receipt.actual_cost_usd == Decimal("0.001198")
    assert result.billing_receipt.pricing_source.endswith("/gpt-5.6-sol")


@pytest.mark.parametrize(
    "sdk_error",
    [
        APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses")),
        APIConnectionError(
            request=httpx.Request("POST", "https://api.openai.com/v1/responses")
        ),
        RateLimitError(
            "rate limited",
            response=httpx.Response(
                429,
                request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
            ),
            body=None,
        ),
    ],
)
def test_openai_provider_maps_sdk_transients_to_retryable_timeout_classification(
    sdk_error: Exception,
) -> None:
    provider, _ = fake_provider(response=object(), error=sdk_error)

    with pytest.raises(RetryableModelProviderError) as raised:
        provider.generate(request(), AlternateOutput)

    assert isinstance(raised.value, TimeoutError)
    assert raised.value.__cause__ is sdk_error


@pytest.mark.parametrize("field", ["model", "system", "prompt"])
@pytest.mark.parametrize("value", ["", " \t\n", 123, True, None])
def test_model_request_rejects_non_exact_or_empty_strings(field: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        request(**{field: value})


@pytest.mark.parametrize("effort", ["minimal", "LOW", "", 1, True, None])
def test_model_request_rejects_unknown_or_non_string_effort(effort: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        request(effort=effort)


@pytest.mark.parametrize("effort", ["none", "low", "medium", "high", "xhigh", "max"])
def test_model_request_accepts_each_supported_effort(effort: str) -> None:
    model_request = request(effort=effort)

    assert model_request.effort == effort


@pytest.mark.parametrize(
    "token_limit", [0, -1, MAX_MODEL_OUTPUT_TOKENS + 1, True, False, 1.0, "4096", None]
)
def test_model_request_rejects_invalid_token_limits(token_limit: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        request(effort="medium", max_output_tokens=token_limit)


@pytest.mark.parametrize("timeout", [0, -1, True, "31", None, float("inf")])
def test_model_request_rejects_invalid_timeouts(timeout: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        request(timeout_seconds=timeout)


@pytest.mark.parametrize(
    "cost", [Decimal("0"), Decimal("-1"), Decimal("NaN"), 0.1, True, "1.00", None]
)
def test_model_cost_authorization_rejects_non_decimal_or_non_positive_cost(
    cost: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        ModelCostAuthorization(max_cost_usd=cost)  # type: ignore[arg-type]


def test_model_request_enforces_strict_combined_prompt_byte_ceiling() -> None:
    with pytest.raises(ValueError, match="prompt content"):
        request(system="s", prompt="p" * MAX_MODEL_PROMPT_BYTES)


@pytest.mark.parametrize(
    "mutation",
    [
        {"output_parsed": None},
        {"output_parsed": AlternateOutput(answer="wrong schema")},
        {"id": None},
        {"id": ""},
        {"usage": None},
        {"usage": SimpleNamespace(output_tokens=25)},
        {
            "usage": SimpleNamespace(
                input_tokens=-1,
                output_tokens=25,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            )
        },
        {
            "usage": SimpleNamespace(
                input_tokens=True,
                output_tokens=25,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            )
        },
        {
            "usage": SimpleNamespace(
                input_tokens=100,
                output_tokens=-1,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            )
        },
        {
            "usage": SimpleNamespace(
                input_tokens=100,
                output_tokens=False,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
            )
        },
        {"usage": SimpleNamespace(input_tokens=100, output_tokens=25)},
        {
            "usage": SimpleNamespace(
                input_tokens=100,
                output_tokens=25,
                input_tokens_details=SimpleNamespace(cached_tokens=-1, cache_write_tokens=0),
            )
        },
        {
            "usage": SimpleNamespace(
                input_tokens=100,
                output_tokens=25,
                input_tokens_details=SimpleNamespace(cached_tokens=60, cache_write_tokens=41),
            )
        },
    ],
)
def test_openai_provider_rejects_malformed_responses_as_typed_failure(
    mutation: dict[str, object],
) -> None:
    response = valid_response(
        ProofSketch(strategy="induction", lemmas=["base case"], risks=["gap"])
    )
    for name, value in mutation.items():
        setattr(response, name, value)
    provider, _ = fake_provider(response)

    with pytest.raises(InvalidModelResponseError):
        provider.generate(request(), ProofSketch)


def test_openai_provider_rejects_missing_response_attributes_as_typed_failure() -> None:
    provider, _ = fake_provider(SimpleNamespace(status="completed", output=[]))

    with pytest.raises(InvalidModelResponseError):
        provider.generate(request(), ProofSketch)


def test_openai_provider_reports_incomplete_result_as_typed_failure() -> None:
    response = valid_response(
        ProofSketch(strategy="induction", lemmas=["base case"], risks=["gap"])
    )
    response.status = "incomplete"
    response.incomplete_details = SimpleNamespace(reason="max_output_tokens")
    provider, _ = fake_provider(response)

    with pytest.raises(IncompleteModelResponseError, match="max_output_tokens"):
        provider.generate(request(), ProofSketch)


def test_openai_provider_reports_refusal_as_typed_failure() -> None:
    response = valid_response(
        ProofSketch(strategy="induction", lemmas=["base case"], risks=["gap"])
    )
    response.output_parsed = None
    response.output = [
        SimpleNamespace(content=[SimpleNamespace(type="refusal", refusal="cannot assist")])
    ]
    provider, _ = fake_provider(response)

    with pytest.raises(ModelRefusalError, match="cannot assist"):
        provider.generate(request(), ProofSketch)
