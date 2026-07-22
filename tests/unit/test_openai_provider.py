from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from openai.lib._parsing._responses import type_to_text_format_param
from pydantic import BaseModel

import mathloop.providers.openai as openai_provider_module
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
from mathloop.providers.openai_sdk_2_47 import (
    SUPPORTED_OPENAI_SDK_VERSION,
    strict_text_format_for_schema,
)


class AlternateOutput(BaseModel):
    answer: str


class ScriptedClock:
    def __init__(self, *values: float) -> None:
        self.values = iter(values)

    def __call__(self) -> float:
        return next(self.values)


class FakeInputTokens:
    def __init__(
        self,
        response: object,
        events: list[str],
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.events = events
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def count(self, **kwargs: Any) -> object:
        self.events.append("count")
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeResponses:
    def __init__(
        self,
        response: object,
        count_response: object,
        *,
        parse_error: Exception | None = None,
        count_error: Exception | None = None,
    ) -> None:
        self.response = response
        self.parse_error = parse_error
        self.events: list[str] = []
        self.calls: list[dict[str, Any]] = []
        self.input_tokens = FakeInputTokens(count_response, self.events, error=count_error)

    def parse(self, **kwargs: Any) -> object:
        self.events.append("parse")
        self.calls.append(kwargs)
        if self.parse_error is not None:
            raise self.parse_error
        return self.response


def fake_provider(
    response: object,
    *,
    counted_input_tokens: object = 100,
    parse_error: Exception | None = None,
    count_error: Exception | None = None,
    clock: Callable[[], float] | None = None,
) -> tuple[OpenAIProvider, FakeResponses]:
    responses = FakeResponses(
        response,
        SimpleNamespace(input_tokens=counted_input_tokens),
        parse_error=parse_error,
        count_error=count_error,
    )
    client = SimpleNamespace(responses=responses)
    effective_clock = clock if clock is not None else (lambda: 0.0)
    return OpenAIProvider(client=client, clock=effective_clock), responses


def valid_response(
    parsed: BaseModel,
    *,
    input_tokens: int = 100,
    output_tokens: int = 25,
    cached_tokens: int = 20,
    cache_write_tokens: int = 30,
) -> SimpleNamespace:
    return SimpleNamespace(
        output_parsed=parsed,
        id="resp_test",
        status="completed",
        output=[],
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_tokens_details=SimpleNamespace(
                cached_tokens=cached_tokens,
                cache_write_tokens=cache_write_tokens,
            ),
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


def sdk_error_samples() -> list[Exception]:
    return [
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
    ]


def test_openai_provider_returns_typed_output_usage_authorization_and_billing() -> None:
    parsed = AlternateOutput(answer="induction")
    provider, responses = fake_provider(valid_response(parsed))

    result = provider.generate(request(), AlternateOutput)

    assert responses.events == ["count", "parse"]
    assert result.value is parsed
    assert result.provider_response_id == "resp_test"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 25
    assert result.usage.cached_input_tokens == 20
    assert result.usage.cache_write_input_tokens == 30
    assert result.billing_authorization.authorized_input_tokens == 100
    assert result.billing_authorization.max_output_tokens == 4096
    assert result.billing_authorization.reserved_cost_usd == Decimal("0.024701")
    assert result.billing_receipt.authorization is result.billing_authorization
    assert result.billing_receipt.actual_cost_usd == Decimal("0.000240")


def test_openai_count_and_parse_share_exact_request_shape_and_bounded_timeout() -> None:
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
    model_input = [
        {"role": "system", "content": "Propose only."},
        {"role": "user", "content": "  exact normalized problem  "},
    ]
    reasoning = {"effort": "xhigh", "context": "current_turn"}

    provider.generate(model_request, ProofSketch)

    assert responses.input_tokens.calls == [
        {
            "model": "gpt-5.6-terra",
            "input": model_input,
            "reasoning": reasoning,
            "text": {"format": strict_text_format_for_schema(ProofSketch)},
            "timeout": 17,
        }
    ]
    assert responses.calls == [
        {
            "model": "gpt-5.6-terra",
            "input": model_input,
            "text_format": ProofSketch,
            "reasoning": reasoning,
            "max_output_tokens": 1234,
            "store": False,
            "timeout": 17,
        }
    ]


def test_single_deadline_reduces_parse_timeout_after_count_and_local_work() -> None:
    parsed = AlternateOutput(answer="induction")
    provider, responses = fake_provider(
        valid_response(parsed),
        clock=ScriptedClock(100.0, 101.0, 106.0, 106.0, 106.0),
    )

    provider.generate(request(timeout_seconds=10), AlternateOutput)

    assert responses.input_tokens.calls[0]["timeout"] == 9.0
    assert responses.calls[0]["timeout"] == 4.0


def test_deadline_exhausted_when_parse_returns_prevents_success() -> None:
    provider, responses = fake_provider(
        valid_response(AlternateOutput(answer="too late")),
        clock=ScriptedClock(100.0, 101.0, 102.0, 110.0),
    )

    with pytest.raises(RetryableModelProviderError, match="deadline") as raised:
        provider.generate(request(timeout_seconds=10), AlternateOutput)

    assert isinstance(raised.value, TimeoutError)
    assert responses.events == ["count", "parse"]


def test_deadline_exhausted_during_validation_and_billing_prevents_success() -> None:
    provider, responses = fake_provider(
        valid_response(AlternateOutput(answer="locally too late")),
        clock=ScriptedClock(100.0, 101.0, 102.0, 103.0, 110.0),
    )

    with pytest.raises(RetryableModelProviderError, match="deadline") as raised:
        provider.generate(request(timeout_seconds=10), AlternateOutput)

    assert isinstance(raised.value, TimeoutError)
    assert responses.events == ["count", "parse"]


def test_deadline_exhausted_after_count_prevents_parse() -> None:
    provider, responses = fake_provider(
        valid_response(AlternateOutput(answer="unused")),
        clock=ScriptedClock(10.0, 11.0, 20.0),
    )

    with pytest.raises(RetryableModelProviderError, match="deadline") as raised:
        provider.generate(request(timeout_seconds=10), AlternateOutput)

    assert isinstance(raised.value, TimeoutError)
    assert responses.events == ["count"]
    assert responses.calls == []


def test_deadline_exactly_exhausted_before_count_prevents_all_sdk_calls() -> None:
    provider, responses = fake_provider(
        valid_response(AlternateOutput(answer="unused")),
        clock=ScriptedClock(10.0, 20.0),
    )

    with pytest.raises(RetryableModelProviderError, match="deadline"):
        provider.generate(request(timeout_seconds=10), AlternateOutput)

    assert responses.events == []


def test_default_and_injected_real_openai_clients_disable_sdk_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    default_provider = OpenAIProvider(clock=lambda: 0.0)
    original = OpenAI(api_key="offline-test-key", max_retries=2)
    injected_provider = OpenAIProvider(client=original, clock=lambda: 0.0)
    try:
        assert default_provider.client.max_retries == 0
        assert original.max_retries == 2
        assert injected_provider.client is not original
        assert injected_provider.client.max_retries == 0
    finally:
        default_provider.client.close()
        injected_provider.client.close()
        original.close()


def test_injected_fake_client_is_not_cloned() -> None:
    provider, responses = fake_provider(valid_response(AlternateOutput(answer="induction")))

    assert provider.client.responses is responses


def test_private_sdk_text_format_adapter_is_versioned_and_parse_equivalent() -> None:
    assert openai.__version__ == SUPPORTED_OPENAI_SDK_VERSION == "2.47.0"
    assert strict_text_format_for_schema(ProofSketch) == type_to_text_format_param(ProofSketch)


def test_openai_provider_counts_before_rejecting_unauthorized_cost_without_parse() -> None:
    provider, responses = fake_provider(valid_response(AlternateOutput(answer="unused")))

    with pytest.raises(ModelCostAuthorizationError, match="reserved"):
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

    assert responses.events == ["count"]
    assert len(responses.input_tokens.calls) == 1
    assert responses.calls == []


def test_exact_count_closes_local_estimate_cost_bypass_before_parse() -> None:
    provider, responses = fake_provider(
        valid_response(AlternateOutput(answer="unused")), counted_input_tokens=300_000
    )

    with pytest.raises(ModelCostAuthorizationError, match=r"0\.750009"):
        provider.generate(
            request(
                max_output_tokens=1,
                cost_authorization=ModelCostAuthorization(max_cost_usd=Decimal("0.010000")),
            ),
            AlternateOutput,
        )

    assert responses.events == ["count"]
    assert responses.calls == []


def test_openai_provider_fails_closed_for_unpriced_model_before_count_or_parse() -> None:
    provider, responses = fake_provider(valid_response(AlternateOutput(answer="unused")))

    with pytest.raises(ModelCostAuthorizationError, match="unpriced"):
        provider.generate(request(model="gpt-unknown"), AlternateOutput)

    assert responses.events == []


@pytest.mark.parametrize(
    ("counted_input_tokens", "expected_reserved"),
    [
        (271_999, Decimal("0.340005")),
        (272_000, Decimal("0.340006")),
        (272_001, Decimal("0.680012")),
    ],
)
def test_reservation_uses_exact_count_for_long_context_threshold(
    counted_input_tokens: int, expected_reserved: Decimal
) -> None:
    parsed = AlternateOutput(answer="induction")
    provider, _ = fake_provider(
        valid_response(
            parsed,
            input_tokens=counted_input_tokens,
            output_tokens=1,
            cached_tokens=0,
            cache_write_tokens=0,
        ),
        counted_input_tokens=counted_input_tokens,
    )

    result = provider.generate(
        request(max_output_tokens=1, cost_authorization=ModelCostAuthorization(Decimal("1.0"))),
        AlternateOutput,
    )

    assert result.billing_authorization.reserved_cost_usd == expected_reserved


def test_reservation_rounds_up_before_exact_cap_comparison() -> None:
    parsed = AlternateOutput(answer="induction")
    response = valid_response(
        parsed, input_tokens=1, output_tokens=1, cached_tokens=0, cache_write_tokens=0
    )
    accepted_provider, _ = fake_provider(response, counted_input_tokens=1)

    result = accepted_provider.generate(
        request(
            max_output_tokens=1,
            cost_authorization=ModelCostAuthorization(Decimal("0.000008")),
        ),
        AlternateOutput,
    )

    assert result.billing_authorization.reserved_cost_usd == Decimal("0.000008")

    rejected_provider, responses = fake_provider(response, counted_input_tokens=1)
    with pytest.raises(ModelCostAuthorizationError, match=r"0\.000008"):
        rejected_provider.generate(
            request(
                max_output_tokens=1,
                cost_authorization=ModelCostAuthorization(Decimal("0.000007")),
            ),
            AlternateOutput,
        )
    assert responses.events == ["count"]


def test_openai_provider_prices_cache_details_and_rounds_actual_cost_upward() -> None:
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


@pytest.mark.parametrize("stage", ["count", "parse"])
@pytest.mark.parametrize("sdk_error", sdk_error_samples())
def test_openai_provider_maps_count_and_parse_transients_to_retryable_timeout(
    stage: str, sdk_error: Exception
) -> None:
    provider, responses = fake_provider(
        response=object(),
        count_error=sdk_error if stage == "count" else None,
        parse_error=sdk_error if stage == "parse" else None,
    )

    with pytest.raises(RetryableModelProviderError) as raised:
        provider.generate(request(), AlternateOutput)

    assert isinstance(raised.value, TimeoutError)
    assert raised.value.__cause__ is sdk_error
    assert responses.events == (["count"] if stage == "count" else ["count", "parse"])


@pytest.mark.parametrize("counted", [None, -1, True, 1.0, "100"])
def test_openai_provider_rejects_invalid_exact_count_response_without_parse(
    counted: object,
) -> None:
    provider, responses = fake_provider(
        valid_response(AlternateOutput(answer="unused")), counted_input_tokens=counted
    )

    with pytest.raises(InvalidModelResponseError, match="input token count"):
        provider.generate(request(), AlternateOutput)

    assert responses.events == ["count"]


@pytest.mark.parametrize("response_input_tokens", [99, 101])
def test_openai_provider_rejects_response_input_count_different_from_authorization(
    response_input_tokens: int,
) -> None:
    provider, _ = fake_provider(
        valid_response(
            AlternateOutput(answer="unused"),
            input_tokens=response_input_tokens,
            cached_tokens=0,
            cache_write_tokens=0,
        ),
        counted_input_tokens=100,
    )

    with pytest.raises(InvalidModelResponseError, match="authorized input"):
        provider.generate(request(), AlternateOutput)


def test_openai_provider_rejects_response_output_over_authorized_maximum() -> None:
    provider, _ = fake_provider(valid_response(AlternateOutput(answer="unused")))

    with pytest.raises(InvalidModelResponseError, match="output token"):
        provider.generate(request(max_output_tokens=24), AlternateOutput)


def test_openai_provider_rejects_actual_cost_above_reservation_before_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, _ = fake_provider(valid_response(AlternateOutput(answer="unused")))

    def excess_cost(*_: object) -> Decimal:
        return Decimal("0.024702")

    monkeypatch.setattr(openai_provider_module, "_actual_cost_usd", excess_cost)

    with pytest.raises(InvalidModelResponseError, match="reserved cost"):
        provider.generate(request(), AlternateOutput)


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
    "cost",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("NaN"),
        Decimal("0.0000001"),
        Decimal("1.0000000"),
        0.1,
        True,
        "1.00",
        None,
    ],
)
def test_model_cost_authorization_rejects_invalid_or_database_unsafe_cost(
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
