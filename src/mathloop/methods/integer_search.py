"""Complete finite searches for counterexamples to integer predicates."""

import json

from mathloop.methods.base import MethodContext, MethodResult
from mathloop.predicates.base import PredicateRegistry


class IntegerCounterexampleSearch:
    family = "integer_counterexample"

    def __init__(self, predicates: PredicateRegistry) -> None:
        self.predicates = predicates

    def search(
        self,
        predicate_id: str,
        start: int,
        stop: int,
        order: str = "ascending",
        declared_start: int | None = None,
    ) -> MethodResult:
        if order not in {"ascending", "boundary_first"}:
            return self._invalid_config(f"unsupported order: {order}")
        if start > stop:
            return self._invalid_config("start must not exceed stop")
        if declared_start is not None and start < declared_start:
            return self._invalid_config("requested interval starts below the declared domain")
        if not self.predicates.contains(predicate_id):
            return self._invalid_config(f"unknown predicate: {predicate_id}")

        values = range(start, stop)
        if order == "boundary_first":
            values = range(stop - 1, start - 1, -1)
        for n in values:
            evaluation = self.predicates.evaluate(predicate_id, n)
            if not evaluation.holds:
                witness: dict[str, object] = {"n": n, "value": evaluation.value}
                artifact = {
                    "predicate_id": predicate_id,
                    "declared_start": start if declared_start is None else declared_start,
                    "requested_interval": {"start": start, "stop": stop},
                    "order": order,
                    "witness": witness,
                }
                return MethodResult(
                    status="candidate",
                    summary=f"counterexample at n={n}",
                    witness=witness,
                    claim=f"n={n} falsifies the universal statement",
                    artifact=json.dumps(artifact, sort_keys=True).encode(),
                )
        return MethodResult(
            status="bounded_no_counterexample",
            summary=f"no counterexample in [{start}, {stop})",
        )

    def run(self, context: MethodContext) -> MethodResult:
        checker = context.problem.checker
        if checker.get("kind") != "integer_predicate":
            return MethodResult(status="inapplicable", summary="requires integer_predicate")

        predicate_id = checker.get("predicate_id")
        if not isinstance(predicate_id, str):
            return self._invalid_config("integer_predicate requires a string predicate_id")
        declared_start = checker.get("start")
        if isinstance(declared_start, bool) or not isinstance(declared_start, int):
            return self._invalid_config("integer_predicate requires an integer start")
        start = self._integer_config(context.config, "start", declared_start)
        stop = self._integer_config(context.config, "stop", 100)
        order = context.config.get("order", "ascending")
        if start is None or stop is None:
            return self._invalid_config("start and stop must be integers")
        if not isinstance(order, str):
            return self._invalid_config("order must be a string")
        return self.search(predicate_id, start, stop, order, declared_start)

    @staticmethod
    def _integer_config(config: dict[str, object], name: str, default: object) -> int | None:
        value = config.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value

    @staticmethod
    def _invalid_config(summary: str) -> MethodResult:
        return MethodResult(status="invalid_config", summary=summary)
