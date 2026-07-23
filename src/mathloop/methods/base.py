"""Shared solver method contracts."""

from collections.abc import Callable
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
    external_execution_callback: Callable[[], None] | None = None

    def mark_external_execution_started(self) -> None:
        if self.external_execution_callback is not None:
            self.external_execution_callback()


class SolverMethod(Protocol):
    family: str

    def run(self, context: MethodContext) -> MethodResult: ...


class MethodRegistry:
    def __init__(self) -> None:
        self._methods: dict[str, SolverMethod] = {}
        self._provenance: dict[str, dict[str, object]] = {}

    def register(self, method: SolverMethod, *, provenance: dict[str, object]) -> None:
        if method.family in self._methods:
            raise ValueError(f"method already registered: {method.family}")
        self._methods[method.family] = method
        self._provenance[method.family] = dict(provenance)

    def get(self, family: str) -> SolverMethod:
        return self._methods[family]

    def contains(self, family: str) -> bool:
        return family in self._methods

    def provenance(self, family: str) -> dict[str, object]:
        return dict(self._provenance[family])
