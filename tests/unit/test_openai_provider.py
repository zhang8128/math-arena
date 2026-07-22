from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel

from mathloop.methods.proof_sketch import ProofSketch
from mathloop.providers.base import MAX_MODEL_OUTPUT_TOKENS, ModelRequest
from mathloop.providers.openai import (
    IncompleteModelResponseError,
    InvalidModelResponseError,
    ModelRefusalError,
    OpenAIProvider,
)


class AlternateOutput(BaseModel):
    answer: str


class FakeResponses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        return self.response


def fake_provider(response: object) -> tuple[OpenAIProvider, FakeResponses]:
    responses = FakeResponses(response)
    client = SimpleNamespace(responses=responses)
    return OpenAIProvider(client=client), responses


def valid_response(parsed: BaseModel) -> SimpleNamespace:
    return SimpleNamespace(
        output_parsed=parsed,
        id="resp_test",
        status="completed",
        output=[],
        usage=SimpleNamespace(input_tokens=100, output_tokens=25),
    )


def test_openai_provider_returns_generic_typed_output_and_usage() -> None:
    parsed = AlternateOutput(answer="induction")
    provider, _ = fake_provider(valid_response(parsed))

    result = provider.generate(
        ModelRequest(model="gpt-5.6-luna", system="Propose only.", prompt="Problem", effort="low"),
        AlternateOutput,
    )

    assert result.value is parsed
    assert result.provider_response_id == "resp_test"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 25


def test_openai_provider_sends_exact_nonpersistent_parse_request() -> None:
    parsed = ProofSketch(strategy="induction", lemmas=["base case"], risks=["gap"])
    provider, responses = fake_provider(valid_response(parsed))
    request = ModelRequest(
        model="gpt-5.6-terra",
        system="Propose only.",
        prompt="  exact normalized problem  ",
        effort="xhigh",
        max_output_tokens=1234,
    )

    provider.generate(request, ProofSketch)

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
        }
    ]


@pytest.mark.parametrize("field", ["model", "system", "prompt"])
@pytest.mark.parametrize("value", ["", " \t\n", 123, True, None])
def test_model_request_rejects_non_exact_or_empty_strings(field: str, value: object) -> None:
    kwargs: dict[str, object] = {
        "model": "gpt-5.6-luna",
        "system": "Propose only.",
        "prompt": "Problem",
        "effort": "low",
    }
    kwargs[field] = value

    with pytest.raises((TypeError, ValueError)):
        ModelRequest(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("effort", ["minimal", "LOW", "", 1, True, None])
def test_model_request_rejects_unknown_or_non_string_effort(effort: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ModelRequest(  # type: ignore[arg-type]
            model="gpt-5.6-luna", system="Propose only.", prompt="Problem", effort=effort
        )


@pytest.mark.parametrize("effort", ["none", "low", "medium", "high", "xhigh", "max"])
def test_model_request_accepts_each_supported_effort(effort: str) -> None:
    request = ModelRequest(
        model="gpt-5.6-luna", system="Propose only.", prompt="Problem", effort=effort
    )

    assert request.effort == effort


@pytest.mark.parametrize(
    "token_limit", [0, -1, MAX_MODEL_OUTPUT_TOKENS + 1, True, False, 1.0, "4096", None]
)
def test_model_request_rejects_invalid_token_limits(token_limit: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ModelRequest(  # type: ignore[arg-type]
            model="gpt-5.6-luna",
            system="Propose only.",
            prompt="Problem",
            effort="medium",
            max_output_tokens=token_limit,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        {"output_parsed": None},
        {"output_parsed": AlternateOutput(answer="wrong schema")},
        {"id": None},
        {"id": ""},
        {"usage": None},
        {"usage": SimpleNamespace(output_tokens=25)},
        {"usage": SimpleNamespace(input_tokens=-1, output_tokens=25)},
        {"usage": SimpleNamespace(input_tokens=True, output_tokens=25)},
        {"usage": SimpleNamespace(input_tokens=100, output_tokens=-1)},
        {"usage": SimpleNamespace(input_tokens=100, output_tokens=False)},
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
        provider.generate(
            ModelRequest(
                model="gpt-5.6-luna", system="Propose only.", prompt="Problem", effort="low"
            ),
            ProofSketch,
        )


def test_openai_provider_rejects_missing_response_attributes_as_typed_failure() -> None:
    provider, _ = fake_provider(SimpleNamespace(status="completed", output=[]))

    with pytest.raises(InvalidModelResponseError):
        provider.generate(
            ModelRequest(
                model="gpt-5.6-luna", system="Propose only.", prompt="Problem", effort="low"
            ),
            ProofSketch,
        )


def test_openai_provider_reports_incomplete_result_as_typed_failure() -> None:
    response = valid_response(
        ProofSketch(strategy="induction", lemmas=["base case"], risks=["gap"])
    )
    response.status = "incomplete"
    response.incomplete_details = SimpleNamespace(reason="max_output_tokens")
    provider, _ = fake_provider(response)

    with pytest.raises(IncompleteModelResponseError, match="max_output_tokens"):
        provider.generate(
            ModelRequest(
                model="gpt-5.6-luna", system="Propose only.", prompt="Problem", effort="low"
            ),
            ProofSketch,
        )


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
        provider.generate(
            ModelRequest(
                model="gpt-5.6-luna", system="Propose only.", prompt="Problem", effort="low"
            ),
            ProofSketch,
        )
