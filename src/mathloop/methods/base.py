"""Shared solver method contracts."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from mathloop.billing import BillingAuthorization, BillingReceipt
from mathloop.codex.domain import CodexTurnReceipt
from mathloop.codex.events import CodexEvent
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
    codex_turn_receipt: CodexTurnReceipt | None = None


@dataclass(frozen=True)
class MethodContext:
    problem: Problem
    seed: int
    config: dict[str, object]
    external_execution_callback: Callable[[], None] | None = None
    # Correlates this execution with an external system's own record of it
    # (e.g. a Codex turn reservation id). Set by the worker, read by whatever
    # concrete method needs to rebuild a request bound to that same turn.
    external_execution_id: UUID | None = None
    # Streams one durably-persisted event at a time back to the worker. A
    # method (or a client it calls, such as CodexClient) invokes this
    # synchronously per event; the worker persists the event and only then
    # returns, so the method never observes the next event before the
    # previous one is safely on the ledger.
    emit_external_event: Callable[[CodexEvent], None] | None = None

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
