"""Narrow SageMath-backed exact operations."""

import json
from typing import Protocol

from mathloop.config import Settings
from mathloop.methods.base import MethodContext, MethodResult
from mathloop.provenance import SAGE_IMAGE_DIGEST
from mathloop.tools.docker import DockerLimits, DockerRunner


class JsonRunner(Protocol):
    def run_json(self, payload: dict[str, object]) -> dict[str, object]: ...


class SagePolynomialMethod:
    family = "sage_polynomial"

    def __init__(self, settings: Settings, runner: JsonRunner | None = None) -> None:
        self.runner: JsonRunner = runner or DockerRunner(
            image=SAGE_IMAGE_DIGEST,
            limits=DockerLimits(
                seconds=settings.max_experiment_seconds,
                memory_mb=settings.max_container_memory_mb,
                cpus=settings.max_container_cpus,
            ),
        )

    def run(self, context: MethodContext) -> MethodResult:
        if "value" in context.config:
            value = context.config.get("value")
            if isinstance(value, bool) or not isinstance(value, int):
                return MethodResult(
                    status="invalid_config",
                    summary="factor requires an integer value",
                )
            response = self.runner.run_json({"operation": "factor", "value": value})
            return MethodResult(
                status="completed",
                summary=f"factored {value} with SageMath",
                artifact=json.dumps(response, sort_keys=True).encode(),
            )
        checker = context.problem.checker
        predicate_id = checker.get("predicate_id")
        declared_start = checker.get("start")
        start = context.config.get("start", declared_start)
        stop = context.config.get("stop")
        order = context.config.get("order", "ascending")
        if (
            checker.get("kind") != "integer_predicate"
            or type(predicate_id) is not str
            or type(declared_start) is not int
            or type(start) is not int
            or type(stop) is not int
            or start < declared_start
            or start > stop
            or order not in {"ascending", "boundary_first"}
        ):
            return MethodResult(
                status="invalid_config",
                summary="Sage integer search requires valid predicate interval metadata",
            )
        response = self.runner.run_json(
            {
                "operation": "find_integer_counterexample",
                "predicate_id": predicate_id,
                "start": start,
                "stop": stop,
                "order": order,
            }
        )
        if set(response) == {"ok", "found"} and response == {
            "ok": True,
            "found": False,
        }:
            return MethodResult(
                status="bounded_no_counterexample",
                summary=f"Sage found no counterexample in [{start}, {stop})",
                artifact=json.dumps(response, sort_keys=True).encode(),
            )
        if (
            set(response) != {"ok", "found", "n", "value"}
            or response.get("ok") is not True
            or response.get("found") is not True
            or type(response.get("n")) is not int
            or type(response.get("value")) is not int
        ):
            return MethodResult(
                status="invalid_result",
                summary="Sage returned a malformed counterexample result",
            )
        n = response["n"]
        value = response["value"]
        assert type(n) is int and type(value) is int
        if n < start or n >= stop:
            return MethodResult(
                status="invalid_result",
                summary="Sage returned a witness outside the requested interval",
            )
        witness: dict[str, object] = {"n": n, "value": value}
        return MethodResult(
            status="candidate",
            summary=f"Sage found a counterexample at n={n}",
            witness=witness,
            claim=f"n={n} falsifies the universal statement",
            artifact=json.dumps(response, sort_keys=True).encode(),
        )
