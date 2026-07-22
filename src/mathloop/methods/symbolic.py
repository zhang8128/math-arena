"""Small symbolic certificates for supported identities."""

import json

from sympy import Symbol, expand  # type: ignore[import-untyped]

from mathloop.methods.base import MethodContext, MethodResult


class SymbolicInductionMethod:
    family = "symbolic_induction"

    def prove_sum_odds(self) -> MethodResult:
        n = Symbol("n", integer=True, nonnegative=True)
        base = 0**2
        step = expand((n + 1) ** 2 - n**2 - (2 * n + 1))
        witness: dict[str, object] = {
            "certificate": "sum_odds_induction",
            "base": int(base),
            "step": int(step),
        }
        return MethodResult(
            status="candidate",
            summary="base and induction-step polynomials normalize to zero",
            witness=witness,
            claim="the sum of the first n positive odd integers equals n^2",
            artifact=json.dumps(witness, sort_keys=True).encode(),
        )

    def run(self, context: MethodContext) -> MethodResult:
        checker = context.problem.checker
        declared_start = checker.get("start")
        if (
            checker.get("kind") != "integer_predicate"
            or checker.get("predicate_id") != "sum_odds"
            or type(declared_start) is not int
            or declared_start != 0
        ):
            return MethodResult(status="inapplicable", summary="unsupported identity")
        return self.prove_sum_odds()
