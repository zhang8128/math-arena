"""Narrow SageMath-backed exact operations."""

import json
from typing import Protocol

from mathloop.config import Settings
from mathloop.methods.base import MethodContext, MethodResult
from mathloop.tools.docker import DockerLimits, DockerRunner


class JsonRunner(Protocol):
    def run_json(self, payload: dict[str, object]) -> dict[str, object]: ...


class SagePolynomialMethod:
    family = "sage_polynomial"

    def __init__(self, settings: Settings, runner: JsonRunner | None = None) -> None:
        self.runner: JsonRunner = runner or DockerRunner(
            image="mathloop-sage:10.9",
            limits=DockerLimits(
                seconds=settings.max_experiment_seconds,
                memory_mb=settings.max_container_memory_mb,
                cpus=settings.max_container_cpus,
            ),
        )

    def run(self, context: MethodContext) -> MethodResult:
        value = context.config.get("value")
        if isinstance(value, bool) or not isinstance(value, int):
            return MethodResult(status="invalid_config", summary="factor requires an integer value")

        response = self.runner.run_json({"operation": "factor", "value": value})
        return MethodResult(
            status="completed",
            summary=f"factored {value} with SageMath",
            artifact=json.dumps(response, sort_keys=True).encode(),
        )
