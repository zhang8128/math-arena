from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import BaseModel, ValidationError

from mathloop.domain import Problem, ProblemStatus
from mathloop.methods.base import MethodContext
from mathloop.methods.proof_sketch import ProofSketch, ProofSketchMethod
from mathloop.providers.base import ModelRequest, ModelResponse, ModelUsage, T


class RecordingProvider:
    def __init__(self, response: ModelResponse[ProofSketch]) -> None:
        self.response = response
        self.calls: list[tuple[ModelRequest, type[BaseModel]]] = []

    def generate(self, request: ModelRequest, schema: type[T]) -> ModelResponse[T]:
        self.calls.append((request, schema))
        return self.response  # type: ignore[return-value]


def problem() -> Problem:
    return Problem(
        id=uuid4(),
        source_id="test",
        source_uri="local://test",
        source_hash="hash",
        statement="RAW statement must not be sent",
        normalized_statement="For every n, establish P(n).",
        domain="number_theory",
        features={},
        checker={},
        status=ProblemStatus.ELIGIBLE,
        cohort="development",
        version=1,
        created_at=datetime.now(UTC),
    )


def recording_provider() -> RecordingProvider:
    sketch = ProofSketch(
        strategy="Use strong induction.",
        lemmas=["Establish the base case."],
        risks=["The inductive hypothesis may be too weak."],
    )
    return RecordingProvider(
        ModelResponse(
            value=sketch,
            provider_response_id="resp_sketch",
            usage=ModelUsage(input_tokens=81, output_tokens=34),
        )
    )


def test_proof_sketch_method_uses_only_normalized_statement_and_returns_lead_artifact() -> None:
    provider = recording_provider()
    method = ProofSketchMethod(provider=provider, model="gpt-5.6-terra")
    context = MethodContext(
        problem=problem(), seed=99, config={"effort": "high", "max_output_tokens": 2048}
    )

    result = method.run(context)

    assert len(provider.calls) == 1
    request, schema = provider.calls[0]
    assert request.prompt == "For every n, establish P(n)."
    assert "RAW statement" not in request.system
    assert request.model == "gpt-5.6-terra"
    assert request.effort == "high"
    assert request.max_output_tokens == 2048
    assert "never claim" in request.system.lower()
    assert schema is ProofSketch
    assert result.status == "lead"
    assert result.summary == "Use strong induction."
    assert result.claim is None
    assert result.witness is None
    assert json.loads(result.artifact or b"{}") == {
        "proof_sketch": {
            "lemmas": ["Establish the base case."],
            "risks": ["The inductive hypothesis may be too weak."],
            "strategy": "Use strong induction.",
        },
        "provider_response_id": "resp_sketch",
        "usage": {"input_tokens": 81, "output_tokens": 34},
    }


def test_proof_sketch_method_uses_safe_defaults() -> None:
    provider = recording_provider()
    method = ProofSketchMethod(provider=provider, model="gpt-5.6-luna")

    method.run(MethodContext(problem=problem(), seed=0, config={}))

    request, _ = provider.calls[0]
    assert request.effort == "medium"
    assert request.max_output_tokens == 4096


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"effort": "LOW"}, "effort"),
        ({"effort": 1}, "effort"),
        ({"effort": True}, "effort"),
        ({"max_output_tokens": "4096"}, "max_output_tokens"),
        ({"max_output_tokens": 1.0}, "max_output_tokens"),
        ({"max_output_tokens": True}, "max_output_tokens"),
        ({"max_output_tokens": 0}, "max_output_tokens"),
        ({"max_output_tokens": 128_001}, "max_output_tokens"),
    ],
)
def test_proof_sketch_method_rejects_invalid_config_without_calling_provider(
    config: dict[str, object], message: str
) -> None:
    provider = recording_provider()
    method = ProofSketchMethod(provider=provider, model="gpt-5.6-terra")

    result = method.run(MethodContext(problem=problem(), seed=0, config=config))

    assert result.status == "invalid_config"
    assert message in result.summary
    assert result.claim is None
    assert result.witness is None
    assert result.artifact is None
    assert provider.calls == []


@pytest.mark.parametrize("model", ["", "  ", 123, True, None])
def test_proof_sketch_method_rejects_invalid_model_at_construction(model: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ProofSketchMethod(provider=recording_provider(), model=model)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "payload",
    [
        {"strategy": "", "lemmas": ["lemma"], "risks": ["risk"]},
        {"strategy": "strategy", "lemmas": [], "risks": ["risk"]},
        {"strategy": "strategy", "lemmas": [""], "risks": ["risk"]},
        {"strategy": "strategy", "lemmas": ["lemma"], "risks": []},
        {"strategy": "strategy", "lemmas": ["lemma"], "risks": ["  "]},
        {"strategy": "x" * 4001, "lemmas": ["lemma"], "risks": ["risk"]},
        {"strategy": "strategy", "lemmas": ["x" * 2001], "risks": ["risk"]},
        {"strategy": "strategy", "lemmas": ["lemma"] * 33, "risks": ["risk"]},
        {"strategy": "strategy", "lemmas": ["lemma"], "risks": ["risk"], "proof": True},
    ],
)
def test_proof_sketch_schema_rejects_empty_oversized_or_extra_content(
    payload: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        ProofSketch.model_validate(payload)
