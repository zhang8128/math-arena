"""Disposable, lease-bound experiment workers with hard process cancellation."""

from __future__ import annotations

import base64
import hashlib
import json
import multiprocessing
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from mathloop.artifacts import ArtifactStore
from mathloop.billing import BillingAuthorization, BillingReceipt, validate_database_usd
from mathloop.config import Settings
from mathloop.domain import (
    CandidateClaim,
    ClaimStatus,
    ClaimType,
    EvidenceLevel,
    Experiment,
    Problem,
    Verification,
)
from mathloop.methods.base import MethodContext, MethodRegistry, MethodResult, SolverMethod
from mathloop.processes import terminate_process_tree
from mathloop.provenance import require_current_method_provenance
from mathloop.spawn_guard import SupervisedSpawnRegistry
from mathloop.storage.repository import (
    ArtifactRecord,
    MethodNotFoundError,
    ProblemNotFoundError,
    Repository,
)
from mathloop.tools.docker import SandboxFailure


class ClaimVerifier(Protocol):
    def verify(self, problem: Problem, claim: CandidateClaim) -> Verification: ...


@dataclass(frozen=True)
class ExecutionOutcome:
    result: MethodResult
    external_execution_started: bool


class ExecutionTimedOut(TimeoutError):
    def __init__(self, timeout_seconds: float, *, external_execution_started: bool) -> None:
        super().__init__(f"experiment exceeded {timeout_seconds} seconds")
        self.external_execution_started = external_execution_started


class ExecutionFailed(RuntimeError):
    def __init__(self, cause: BaseException, *, external_execution_started: bool) -> None:
        super().__init__(f"isolated execution failed: {cause!r}")
        self.cause = cause
        self.external_execution_started = external_execution_started


def _execute_in_child(
    method: SolverMethod,
    context: MethodContext,
    channel: Connection,
    supervisor_channel: Connection | None,
) -> None:
    if hasattr(os, "setsid"):
        os.setsid()
        process_group_id = os.getpgrp()
        channel.send(("process_group_ready", process_group_id))
        if supervisor_channel is not None:
            supervisor_channel.send(("execution_group_started", process_group_id))

    def mark_external_execution_started() -> None:
        channel.send(("external_start_requested", None))
        acknowledgement, _payload = channel.recv()
        if acknowledgement != "external_start_acknowledged":
            raise RuntimeError("external execution gate returned an invalid acknowledgement")

    child_context = replace(
        context,
        external_execution_callback=mark_external_execution_started,
    )
    spawn_registry = SupervisedSpawnRegistry(channel, supervisor_channel)
    try:
        with spawn_registry.installed():
            result = method.run(child_context)
    except BaseException as error:
        try:
            channel.send(("error", error))
        except (OSError, TypeError):
            channel.send(("error_repr", (type(error).__name__, repr(error))))
    else:
        channel.send(("result", result))
    finally:
        channel.close()


class ProcessExecutionBoundary:
    """Run one method in a process that is always joined or killed."""

    def __init__(self, *, supervisor_channel: Connection | None = None) -> None:
        self._child: BaseProcess | None = None
        self._supervisor_channel = supervisor_channel
        self._reported_stopped_groups: set[int] = set()
        self._reported_stopped_descendants: set[int] = set()

    @property
    def has_live_child(self) -> bool:
        return self._child is not None and self._child.is_alive()

    def run(
        self,
        method: SolverMethod,
        context: MethodContext,
        *,
        timeout_seconds: float,
        external_started_callback: Callable[[], None] | None = None,
    ) -> ExecutionOutcome:
        if type(timeout_seconds) not in (int, float) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        process_context = multiprocessing.get_context("forkserver")
        parent_channel, child_channel = process_context.Pipe(duplex=True)
        process = process_context.Process(
            target=_execute_in_child,
            args=(method, context, child_channel, self._supervisor_channel),
            daemon=True,
        )
        self._child = process
        self._reported_stopped_groups.clear()
        self._reported_stopped_descendants.clear()
        external_started = False
        process_group_id: int | None = None
        descendant_groups: dict[int, int] = {}
        deadline = time.monotonic() + float(timeout_seconds)
        try:
            try:
                process.start()
            except Exception as error:
                raise ExecutionFailed(
                    error,
                    external_execution_started=False,
                ) from error
            child_channel.close()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._stop_child(process, process_group_id, descendant_groups)
                    raise ExecutionTimedOut(
                        float(timeout_seconds),
                        external_execution_started=external_started,
                    )
                if parent_channel.poll(min(remaining, 0.02)):
                    try:
                        kind, payload = parent_channel.recv()
                    except EOFError:
                        self._stop_child(process, process_group_id, descendant_groups)
                        raise ExecutionFailed(
                            RuntimeError("isolated execution exited without a result"),
                            external_execution_started=external_started,
                        ) from None
                    if kind == "external_start_requested":
                        if not external_started and external_started_callback is not None:
                            try:
                                external_started_callback()
                            except Exception as error:
                                self._stop_child(
                                    process,
                                    process_group_id,
                                    descendant_groups,
                                )
                                raise ExecutionFailed(
                                    error,
                                    external_execution_started=False,
                                ) from error
                        external_started = True
                        parent_channel.send(("external_start_acknowledged", None))
                        continue
                    if kind == "process_group_ready":
                        process_group_id = int(payload)
                        continue
                    if kind in {"descendant_started", "descendant_stopped"}:
                        pid, group = self._descendant_identity(payload)
                        if kind == "descendant_started":
                            descendant_groups[pid] = group
                        else:
                            descendant_groups.pop(pid, None)
                        continue
                    self._stop_child(process, process_group_id, descendant_groups)
                    if kind == "result" and isinstance(payload, MethodResult):
                        return ExecutionOutcome(payload, external_started)
                    if kind == "error" and isinstance(payload, BaseException):
                        if isinstance(payload, (KeyboardInterrupt, SystemExit)):
                            raise payload
                        raise ExecutionFailed(
                            payload,
                            external_execution_started=external_started,
                        )
                    raise ExecutionFailed(
                        RuntimeError(f"isolated execution error: {payload!r}"),
                        external_execution_started=external_started,
                    )
                if not process.is_alive():
                    # Give the pipe one final chance to deliver a buffered message.
                    if parent_channel.poll(0.02):
                        continue
                    self._stop_child(process, process_group_id, descendant_groups)
                    raise ExecutionFailed(
                        RuntimeError("isolated execution exited without a result"),
                        external_execution_started=external_started,
                    )
        finally:
            child_channel.close()
            parent_channel.close()
            if process.is_alive():
                self._stop_child(process, process_group_id, descendant_groups)

    def _stop_child(
        self,
        process: BaseProcess,
        process_group_id: int | None,
        descendant_groups: dict[int, int],
    ) -> None:
        groups = set(descendant_groups.values())
        if process_group_id is not None:
            groups.add(process_group_id)
        try:
            terminate_process_tree(process, known_process_groups=groups)
        finally:
            self._report_descendants_stopped(descendant_groups)
            if (
                process_group_id is not None
                and process_group_id not in self._reported_stopped_groups
                and self._supervisor_channel is not None
            ):
                self._supervisor_channel.send(("execution_group_stopped", process_group_id))
                self._reported_stopped_groups.add(process_group_id)

    @staticmethod
    def _descendant_identity(payload: object) -> tuple[int, int]:
        if not isinstance(payload, dict):
            raise RuntimeError("execution descendant event has an invalid payload")
        pid = payload.get("pid")
        process_group_id = payload.get("process_group_id")
        if type(pid) is not int or pid <= 1:
            raise RuntimeError("execution descendant event has an invalid PID")
        if type(process_group_id) is not int or process_group_id <= 1:
            raise RuntimeError("execution descendant event has an invalid process group")
        return pid, process_group_id

    def _report_descendants_stopped(
        self,
        descendant_groups: dict[int, int],
    ) -> None:
        if self._supervisor_channel is None:
            return
        for pid, process_group_id in descendant_groups.items():
            if pid in self._reported_stopped_descendants:
                continue
            try:
                self._supervisor_channel.send(
                    (
                        "execution_descendant_stopped",
                        {"pid": pid, "process_group_id": process_group_id},
                    )
                )
            except OSError:
                return
            self._reported_stopped_descendants.add(pid)


class Worker:
    def __init__(
        self,
        repository: Repository,
        artifacts: ArtifactStore,
        methods: MethodRegistry,
        settings: Settings,
        *,
        execution_boundary: ProcessExecutionBoundary | None = None,
    ) -> None:
        self.repository = repository
        self.artifacts = artifacts
        self.methods = methods
        self.settings = settings
        self.execution_boundary = execution_boundary or ProcessExecutionBoundary()

    def run_once(self, worker_id: str) -> bool:
        claimed = self.repository.claim_next(
            worker_id,
            now=datetime.now(UTC),
            lease_seconds=self.settings.lease_seconds,
        )
        if claimed is None:
            return False
        canonical = self.repository.get_experiment(claimed.id)
        if canonical != claimed:
            self.repository.fail(
                claimed.id,
                worker_id,
                "projection",
                "claimed experiment differs from its canonical projection",
                retryable=False,
            )
            return True
        try:
            problem = self.repository.get_problem(claimed.problem_id)
            method_version = self.repository.get_method(claimed.method_id)
        except (ProblemNotFoundError, MethodNotFoundError) as error:
            self.repository.fail(
                claimed.id,
                worker_id,
                "projection",
                str(error),
                retryable=False,
            )
            return True
        try:
            method = self.methods.get(method_version.family)
        except KeyError:
            self.repository.fail(
                claimed.id,
                worker_id,
                "capability",
                f"method implementation unavailable: {method_version.family}",
                retryable=False,
            )
            return True
        try:
            method_identity = require_current_method_provenance(
                method_version.family,
                self.methods.provenance(method_version.family),
                method_version.spec.get("provenance"),
                claimed.config.get("provenance"),
            )
        except ValueError as error:
            self.repository.fail(
                claimed.id,
                worker_id,
                "provenance",
                str(error),
                retryable=False,
            )
            return True

        try:
            reserve = self._external_reserve(claimed, method_version.spec)
        except (TypeError, ValueError) as error:
            self.repository.fail(
                claimed.id,
                worker_id,
                "method",
                f"invalid external budget configuration: {error}",
                retryable=False,
            )
            return True
        if reserve is not None and not self.repository.reserve_daily_budget(
            claimed.id,
            reserve,
            self.settings.daily_api_budget_usd,
        ):
            self.repository.fail(
                claimed.id,
                worker_id,
                "budget",
                "daily API budget denied before execution",
                retryable=False,
            )
            return True
        if reserve is not None:
            reservation = self.repository.get_budget_reservation(claimed.id)
            if reservation.settled_usd is not None:
                self.repository.record_metric(
                    "experiment.retry_blocked_budget",
                    {
                        "experiment_id": str(claimed.id),
                        "settled_usd": format(reservation.settled_usd, "f"),
                        "policy": "no-automatic-reexecution-after-settlement",
                    },
                    f"experiment:retry-blocked-budget:{claimed.id}",
                )
                self.repository.fail(
                    claimed.id,
                    worker_id,
                    "billing",
                    "automatic external reexecution blocked after budget settlement",
                    retryable=False,
                )
                return True
            if reservation.execution_dispatched:
                self.repository.settle_budget(claimed.id, reservation.reserved_usd)
                self.repository.record_metric(
                    "experiment.retry_blocked_budget",
                    {
                        "experiment_id": str(claimed.id),
                        "settled_usd": format(reservation.reserved_usd, "f"),
                        "policy": "dispatched-attempt-reclaimed-conservatively",
                    },
                    f"experiment:retry-blocked-budget:{claimed.id}",
                )
                self.repository.fail(
                    claimed.id,
                    worker_id,
                    "billing",
                    "reclaimed external dispatch full-settled before reexecution",
                    retryable=False,
                )
                return True
        context = MethodContext(
            problem=problem,
            seed=claimed.seed,
            config=dict(claimed.config),
        )
        try:
            outcome = self.execution_boundary.run(
                method,
                context,
                timeout_seconds=self.settings.max_experiment_seconds,
                external_started_callback=(
                    None
                    if reserve is None
                    else lambda: self.repository.mark_budget_execution_dispatched(
                        claimed.id
                    )
                ),
            )
        except ExecutionTimedOut as error:
            if reserve is not None and error.external_execution_started:
                self.repository.mark_budget_execution_dispatched(claimed.id)
            retryable = self._settle_failed_external(
                claimed.id,
                reserve,
                error.external_execution_started,
                retryable=True,
            )
            self.repository.fail(
                claimed.id,
                worker_id,
                "infrastructure",
                str(error),
                retryable=retryable,
            )
            return True
        except ExecutionFailed as error:
            if reserve is not None and error.external_execution_started:
                self.repository.mark_budget_execution_dispatched(claimed.id)
            retryable = isinstance(error.cause, (TimeoutError, SandboxFailure, OSError))
            retryable = self._settle_failed_external(
                claimed.id,
                reserve,
                error.external_execution_started,
                retryable=retryable,
            )
            self.repository.fail(
                claimed.id,
                worker_id,
                "infrastructure" if retryable else "method",
                repr(error.cause),
                retryable=retryable,
            )
            return True

        result = outcome.result
        if reserve is not None and outcome.external_execution_started:
            self.repository.mark_budget_execution_dispatched(claimed.id)
        try:
            cost = self._settle_successful_external(
                claimed.id,
                reserve,
                result.billing_authorization,
                result.billing_receipt,
                outcome.external_execution_started,
            )
        except (TypeError, ValueError) as error:
            self.repository.fail(
                claimed.id,
                worker_id,
                "method",
                f"invalid external billing result: {error}",
                retryable=False,
            )
            return True
        artifact_bytes = self._artifact_envelope(
            claimed,
            result,
            method_identity,
        )
        stored = self.artifacts.put_bytes(artifact_bytes, "application/json")
        artifact = ArtifactRecord(
            digest=stored.digest,
            media_type=stored.media_type,
            size_bytes=stored.size_bytes,
            relative_path=stored.path.relative_to(self.artifacts.root.resolve()).as_posix(),
            experiment_id=claimed.id,
        )
        candidate = self._candidate_for_result(claimed, result)
        result_payload = self._result_payload(result, stored.digest)
        self.repository.commit_worker_result(
            claimed.id,
            worker_id,
            result=result_payload,
            cost_usd=cost,
            artifact=artifact,
            claim=candidate,
        )
        if candidate is not None:
            self._verify_persisted_candidate(candidate.id)
        return True

    def _verify_persisted_candidate(self, claim_id: UUID) -> CandidateClaim:
        claim = self.repository.get_claim(claim_id)
        artifact = self.repository.get_claim_artifact(claim_id)
        artifact_bytes = self.artifacts.open(artifact.digest)
        if hashlib.sha256(artifact_bytes).hexdigest() != artifact.digest:
            raise ValueError("canonical artifact content does not match its digest")
        envelope = json.loads(artifact_bytes)
        if not isinstance(envelope, dict) or envelope.get("experiment_id") != str(
            claim.experiment_id
        ):
            raise ValueError("canonical artifact does not match the claim experiment")
        experiment = self.repository.get_experiment(claim.experiment_id)
        method = self.repository.get_method(experiment.method_id)
        method_identity = require_current_method_provenance(
            method.family,
            self.methods.provenance(method.family),
            method.spec.get("provenance"),
            experiment.config.get("provenance"),
        )
        if (
            envelope.get("config") != experiment.config
            or envelope.get("seed") != experiment.seed
            or envelope.get("method_provenance") != method_identity
        ):
            raise ValueError(
                "canonical artifact execution provenance differs from the experiment"
            )
        result = envelope.get("result")
        if (
            not isinstance(result, dict)
            or result.get("witness") != claim.model_dump(mode="json")["witness"]
        ):
            raise ValueError("canonical artifact witness does not match the claim")
        return self.repository.evaluate_and_record_claim(
            claim,
            record_method_outcome=True,
        )

    def verify_pending(self) -> int:
        verified = 0
        for claim_id in self.repository.list_candidate_claim_ids():
            self._verify_persisted_candidate(claim_id)
            verified += 1
        return verified

    def _external_reserve(
        self, experiment: Experiment, method_spec: dict[str, object]
    ) -> Decimal | None:
        if "external_provider" not in method_spec:
            return None
        value = experiment.config.get(
            "max_api_cost_usd_per_experiment",
            method_spec.get(
                "max_api_cost_usd_per_experiment",
                format(self.settings.max_api_cost_usd_per_experiment, "f"),
            ),
        )
        return _parse_database_decimal(value, "max_api_cost_usd_per_experiment", positive=True)

    def _settle_failed_external(
        self,
        experiment_id: UUID,
        reserve: Decimal | None,
        external_started: bool,
        *,
        retryable: bool,
    ) -> bool:
        if reserve is None:
            return retryable
        if external_started:
            self.repository.settle_budget(experiment_id, reserve)
            return retryable
        self.repository.settle_budget(experiment_id, Decimal("0"))
        return retryable

    def _settle_successful_external(
        self,
        experiment_id: UUID,
        reserve: Decimal | None,
        authorization: BillingAuthorization | None,
        receipt: BillingReceipt | None,
        external_started: bool,
    ) -> Decimal:
        if reserve is None:
            if authorization is not None or receipt is not None or external_started:
                raise ValueError("local method returned unauthorized external billing")
            return Decimal("0")
        if (
            authorization is not None
            and receipt is not None
            and receipt.authorization == authorization
            and authorization.reserved_cost_usd <= reserve
            and receipt.actual_cost_usd <= reserve
        ):
            self.repository.settle_budget(experiment_id, receipt.actual_cost_usd)
            return receipt.actual_cost_usd
        conservative = reserve if external_started else Decimal("0")
        self.repository.settle_budget(experiment_id, conservative)
        if external_started:
            raise ValueError("external execution returned no trustworthy billing receipt")
        return Decimal("0")

    @staticmethod
    def _candidate_for_result(
        experiment: Experiment, result: MethodResult
    ) -> CandidateClaim | None:
        if result.status != "candidate" or result.witness is None or result.claim is None:
            return None
        witness = result.witness
        if (
            set(witness) == {"n", "value"}
            and type(witness["n"]) is int
            and type(witness["value"]) is int
        ):
            claim_type = ClaimType.DISPROOF
        elif (
            set(witness) == {"certificate", "base", "step"}
            and witness["certificate"]
            in {"sum_odds_induction", "sum_integers_induction"}
            and type(witness["base"]) is int
            and type(witness["step"]) is int
        ):
            claim_type = ClaimType.PROOF
        else:
            return None
        return CandidateClaim(
            id=uuid5(NAMESPACE_URL, f"claim:{experiment.id}"),
            problem_id=experiment.problem_id,
            experiment_id=experiment.id,
            claim_type=claim_type,
            statement=result.claim,
            witness=witness,
            status=ClaimStatus.CANDIDATE,
            evidence_level=EvidenceLevel.LEAD,
            created_at=experiment.created_at,
        )

    @staticmethod
    def _artifact_envelope(
        experiment: Experiment,
        result: MethodResult,
        method_provenance: dict[str, object],
    ) -> bytes:
        envelope = {
            "experiment_id": str(experiment.id),
            "problem_id": str(experiment.problem_id),
            "method_id": str(experiment.method_id),
            "config": experiment.config,
            "seed": experiment.seed,
            "method_provenance": method_provenance,
            "result": {
                "status": result.status,
                "summary": result.summary,
                "witness": result.witness,
                "claim": result.claim,
                "method_artifact_base64": (
                    base64.b64encode(result.artifact).decode("ascii")
                    if result.artifact is not None
                    else None
                ),
            },
        }
        return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()

    @staticmethod
    def _result_payload(result: MethodResult, artifact_digest: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "status": result.status,
            "summary": result.summary,
            "artifact_digest": artifact_digest,
        }
        if result.billing_authorization is not None:
            payload["billing_authorization"] = result.billing_authorization.to_audit_dict()
        if result.billing_receipt is not None:
            payload["billing_receipt"] = result.billing_receipt.to_audit_dict()
        return payload


def _parse_database_decimal(value: object, field_name: str, *, positive: bool) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(f"{field_name} must be a Decimal-compatible integer or string")
    if not isinstance(value, (Decimal, int, str)):
        raise TypeError(f"{field_name} must be a Decimal-compatible integer or string")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{field_name} is not an exact decimal") from error
    validate_database_usd(parsed, field_name=field_name, positive=positive)
    return parsed
