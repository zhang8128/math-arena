"""Model-generated proof sketches that remain non-authoritative leads."""

import json
from typing import Annotated, cast

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from mathloop.methods.base import MethodContext, MethodResult
from mathloop.providers.base import (
    MAX_MODEL_OUTPUT_TOKENS,
    SUPPORTED_REASONING_EFFORTS,
    ModelProvider,
    ModelRequest,
    ReasoningEffort,
)

SketchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ProofSketch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]
    lemmas: list[SketchText] = Field(min_length=1, max_length=32)
    risks: list[SketchText] = Field(min_length=1, max_length=32)


class ProofSketchMethod:
    family = "proof_sketch"

    def __init__(self, provider: ModelProvider, model: str) -> None:
        if type(model) is not str:
            raise TypeError("model must be a string")
        if not model.strip():
            raise ValueError("model must not be empty")
        self.provider = provider
        self.model = model

    def run(self, context: MethodContext) -> MethodResult:
        effort_value = context.config.get("effort", "medium")
        if type(effort_value) is not str or effort_value not in SUPPORTED_REASONING_EFFORTS:
            return self._invalid_config("effort must be a supported reasoning effort")
        effort = cast(ReasoningEffort, effort_value)

        token_value = context.config.get("max_output_tokens", 4096)
        if type(token_value) is not int:
            return self._invalid_config("max_output_tokens must be an integer")
        if not 1 <= token_value <= MAX_MODEL_OUTPUT_TOKENS:
            return self._invalid_config(
                f"max_output_tokens must be between 1 and {MAX_MODEL_OUTPUT_TOKENS}"
            )

        response = self.provider.generate(
            ModelRequest(
                model=self.model,
                system=(
                    "Propose a proof strategy and explicit lemmas. This is exploration only; "
                    "never claim the conjecture is proved and list material risks."
                ),
                prompt=context.problem.normalized_statement,
                effort=effort,
                max_output_tokens=token_value,
            ),
            ProofSketch,
        )
        artifact = {
            "proof_sketch": response.value.model_dump(mode="json"),
            "provider_response_id": response.provider_response_id,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
        return MethodResult(
            status="lead",
            summary=response.value.strategy,
            artifact=json.dumps(artifact, sort_keys=True).encode(),
        )

    @staticmethod
    def _invalid_config(summary: str) -> MethodResult:
        return MethodResult(status="invalid_config", summary=summary)
