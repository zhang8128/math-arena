"""Shared solver method contracts."""

from dataclasses import dataclass
from typing import Protocol

from mathloop.billing import BillingAuthorization, BillingReceipt
from mathloop.domain import Problem


@dataclass(frozen=True)
class MethodResult:
    status: str
    summary: str
    witness: dict[str, object] | None = None
    claim: str | None = None
    artifact: bytes | None = None
    billing_authorization: BillingAuthorization | None = None
    billing_receipt: BillingReceipt | None = None


@dataclass(frozen=True)
class MethodContext:
    problem: Problem
    seed: int
    config: dict[str, object]


class SolverMethod(Protocol):
    family: str

    def run(self, context: MethodContext) -> MethodResult: ...


class MethodRegistry:
    def __init__(self) -> None:
        self._methods: dict[str, SolverMethod] = {}

    def register(self, method: SolverMethod) -> None:
        if method.family in self._methods:
            raise ValueError(f"method already registered: {method.family}")
        self._methods[method.family] = method

    def get(self, family: str) -> SolverMethod:
        return self._methods[family]
