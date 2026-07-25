"""Composition root for the local-first autonomous mathematics vertical slice."""

from __future__ import annotations

import multiprocessing
import os
import random
import signal
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from threading import Event
from uuid import NAMESPACE_URL, UUID, uuid5

from mathloop.artifacts import ArtifactStore
from mathloop.codex.client import CodexClient
from mathloop.codex.domain import CodexModelRole
from mathloop.codex.launch import CodexLaunchPolicy
from mathloop.codex.worktrees import CodexWorktreeManager
from mathloop.config import Settings
from mathloop.domain import MethodVersion
from mathloop.evolution import (
    MethodMetrics,
    MetricsCohort,
    mutate_integer_search,
    should_promote,
)
from mathloop.methods.base import (
    MethodContext,
    MethodRegistry,
    MethodResult,
    SolverMethod,
)
from mathloop.methods.codex_agent import register_codex_proof_strategy
from mathloop.methods.integer_search import IntegerCounterexampleSearch
from mathloop.methods.proof_sketch import ProofSketchMethod
from mathloop.methods.sage import SagePolynomialMethod
from mathloop.methods.symbolic import SymbolicInductionMethod
from mathloop.predicates.calibration import build_calibration_registry
from mathloop.processes import terminate_process_tree
from mathloop.provenance import SAGE_IMAGE_DIGEST, codex_method_provenance, method_provenance
from mathloop.providers.openai import OpenAIProvider
from mathloop.reporting import Reporting
from mathloop.scheduling import EVOLUTION_HOLDOUT_LANE, PortfolioPolicy, RuntimeScheduler
from mathloop.sources.jsonl import (
    IngestResult,
    JsonlProblemSource,
    ingest_source,
    ingest_source_with_result,
)
from mathloop.storage.db import Database
from mathloop.storage.repository import Repository
from mathloop.tools.docker import DockerLimits, DockerRunner
from mathloop.verification import JsonRunner
from mathloop.worker import (
    _CODEX_OUTER_TIMEOUT_GRACE_SECONDS,
    ProcessExecutionBoundary,
    Worker,
)

BASELINE_CREATED_AT = datetime(2026, 7, 22, tzinfo=UTC)
MINIMUM_HOLDOUT_TRIALS = 2
MAX_CANDIDATE_EVALUATION_CYCLES = 2


@dataclass
class DeferredOpenAIProofSketchMethod:
    """Create the network client only inside the disposable execution process."""

    settings: Settings
    model: str
    family: str = "proof_sketch"

    def run(self, context: MethodContext) -> MethodResult:
        return ProofSketchMethod(
            self.settings,
            OpenAIProvider(),
            self.model,
        ).run(context)


@dataclass
class Runtime:
    repository: Repository
    artifacts: ArtifactStore
    settings: Settings
    methods: MethodRegistry
    scheduler: RuntimeScheduler
    worker: Worker
    reporting: Reporting
    sage_runner: JsonRunner
    api_enabled: bool
    codex_enabled: bool = False

    def __post_init__(self) -> None:
        self.loop = AutonomousLoop(self)

    def ingest(self, path: Path) -> tuple[UUID, ...]:
        return tuple(ingest_source(JsonlProblemSource(path), self.repository))

    def ingest_with_result(self, path: Path) -> IngestResult:
        return ingest_source_with_result(JsonlProblemSource(path), self.repository)

    def register_baseline_methods(self) -> tuple[UUID, ...]:
        # `api_enabled` and `codex_enabled` settle through disjoint budgets
        # (dollars vs. turns) and must never both be live in one runtime.
        # `build_runtime` already refuses to construct a `Runtime` with both
        # set, but this check does not depend on that: `Runtime` is a plain,
        # unfrozen dataclass, so nothing stops a caller from constructing one
        # directly (bypassing `build_runtime` entirely) with both flags set.
        # Refusing here, at the one shared entry point every registration
        # path actually goes through, is what makes the guarantee hold
        # regardless of how the `Runtime` came to exist.
        if self.api_enabled and self.codex_enabled:
            raise ValueError(
                "api_enabled and codex_enabled are mutually exclusive: the OpenAI "
                "API and Codex external methods settle through disjoint budgets "
                "and must never both be live in one runtime"
            )
        self.repository.quarantine_legacy_provenance()
        predicate_registry = build_calibration_registry()
        implementations: list[SolverMethod] = [
            IntegerCounterexampleSearch(predicate_registry),
            SymbolicInductionMethod(),
            SagePolynomialMethod(self.settings, self.sage_runner),
        ]
        baseline_specs: list[tuple[str, dict[str, object]]] = [
            (
                "integer_counterexample",
                {
                    "stop": 100,
                    "order": "ascending",
                    "provenance": method_provenance("integer_counterexample"),
                },
            ),
            (
                "symbolic_induction",
                {"provenance": method_provenance("symbolic_induction")},
            ),
            (
                "sage_polynomial",
                {
                    "stop": 100,
                    "order": "ascending",
                    "provenance": method_provenance("sage_polynomial"),
                },
            ),
        ]
        if self.api_enabled and os.environ.get("OPENAI_API_KEY"):
            # Symmetric half of the mutual-exclusion guarantee: Codex's own
            # registration (`register_codex_proof_strategy`, below) already
            # refuses to register alongside an existing "proof_sketch", but
            # that only protects the "codex registers after the API" order.
            # This check protects the reverse: if a "codex_proof_strategy"
            # method is already registered in `self.methods` (e.g. because
            # this registry is shared across more than one `register_
            # baseline_methods` call), the API method must refuse too --
            # otherwise reordering these two blocks in a future edit would
            # silently reopen the one-directional gap.
            if self.methods.contains("codex_proof_strategy"):
                raise ValueError(
                    "the OpenAI API and Codex external methods cannot both be registered"
                )
            implementations.append(
                DeferredOpenAIProofSketchMethod(
                    self.settings,
                    self.settings.openai_model_scout,
                )
            )
            baseline_specs.append(
                (
                    "proof_sketch",
                    {
                        "effort": "medium",
                        "max_output_tokens": self.settings.max_model_output_tokens,
                        "max_api_cost_usd_per_experiment": format(
                            self.settings.max_api_cost_usd_per_experiment,
                            "f",
                        ),
                        "external_provider": "openai",
                        "provenance": method_provenance("proof_sketch"),
                    },
                )
            )
        elif self.api_enabled:
            self.repository.record_metric(
                "capability.unavailable",
                {"capability": "openai", "reason": "OPENAI_API_KEY is absent"},
                "capability:openai:credentials-unavailable",
            )
        for implementation in implementations:
            if not self.methods.contains(implementation.family):
                self.methods.register(
                    implementation,
                    provenance=method_provenance(implementation.family),
                )

        if self.codex_enabled:
            role = CodexModelRole.LUNA
            model = self.settings.codex_model_luna
            client = _build_codex_client(self.settings)
            registered = register_codex_proof_strategy(
                self.methods,
                self.settings,
                client,
                model=model,
                role=role,
            )
            if registered:
                baseline_specs.append(
                    (
                        "codex_proof_strategy",
                        {
                            "external_provider": "codex",
                            "codex_role": role.value,
                            "codex_model": model,
                            "provenance": codex_method_provenance(
                                model=model,
                                role=role,
                                min_cli_version=self.settings.codex_min_cli_version,
                            ),
                        },
                    )
                )

        return tuple(
            self.repository.register_provenance_baseline(
                family,
                spec,
                created_at=BASELINE_CREATED_AT,
            ).id
            for family, spec in baseline_specs
        )

    def schedule(self, limit: int, seed: int) -> tuple[UUID, ...]:
        return self.scheduler.schedule(limit, seed)


@dataclass
class _SupervisedWorkerProcess:
    process: BaseProcess
    result_channel: Connection
    execution_group_channel: Connection
    active_execution_groups: set[int]
    active_execution_descendants: dict[int, int]
    quota: int
    deadline: float


class AutonomousLoop:
    def __init__(
        self,
        runtime: Runtime,
        *,
        queue_capacity: int = 12,
        worker_iterations: int = 12,
        worker_processes: int = 1,
    ) -> None:
        self.runtime = runtime
        self.queue_capacity = queue_capacity
        self.worker_iterations = worker_iterations
        self.worker_processes = worker_processes
        self.stop_requested = Event()

    def request_stop(self) -> None:
        self.stop_requested.set()

    def cycle(self) -> dict[str, object]:
        cycle_number = self.runtime.repository.count_events("runtime.cycle_metrics") + 1
        ingested = 0
        for path in sorted(self.runtime.settings.incoming_root.glob("*.jsonl")):
            ingested += self.runtime.ingest_with_result(path).inserted
        reconciled_completeness = self.runtime.repository.reconcile_completeness_progress()
        reconciled_method_outcomes = self.runtime.repository.reconcile_method_outcomes()
        reconciled_method_promotions = self.runtime.repository.reconcile_method_promotions()
        requeued = self.runtime.repository.requeue_retryable_failures()
        capacity = max(self.queue_capacity - self.runtime.repository.queue_depth(), 0)
        scheduled = self.runtime.schedule(capacity, seed=cycle_number)
        worker_runs = self._run_workers(cycle_number)
        verified_pending = self.runtime.worker.verify_pending()
        evolution = self._evolve(cycle_number)
        metrics = {
            "cycle": cycle_number,
            "ingested_snapshots": ingested,
            "reconciled_completeness": reconciled_completeness,
            "reconciled_method_outcomes": reconciled_method_outcomes,
            "reconciled_method_promotions": reconciled_method_promotions,
            "requeued_failures": requeued,
            "scheduled": len(scheduled),
            "worker_runs": worker_runs,
            "verified_pending": verified_pending,
            "evolution": evolution,
            "queue_depth": self.runtime.repository.queue_depth(),
        }
        self.runtime.repository.record_metric(
            "runtime.cycle_metrics",
            metrics,
            f"runtime:cycle:{cycle_number}",
        )
        return metrics

    def _run_workers(self, cycle_number: int) -> int:
        if self.worker_iterations <= 0:
            return 0
        if self.worker_processes <= 1:
            completed = 0
            for index in range(self.worker_iterations):
                if self.stop_requested.is_set():
                    break
                if not self.runtime.worker.run_once(f"cycle-{cycle_number}-worker-{index}"):
                    break
                completed += 1
            return completed
        process_count = min(self.worker_processes, self.worker_iterations)
        base_quota, remainder = divmod(self.worker_iterations, process_count)
        context = multiprocessing.get_context("forkserver")
        processes: list[_SupervisedWorkerProcess] = []
        settings_payload = self.runtime.settings
        started_at = time.monotonic()
        # A codex turn can legitimately run for up to codex_turn_timeout_seconds
        # (1800s by default) plus its own outer grace -- far longer than
        # max_experiment_seconds (300s by default), which this per-worker-process
        # deadline was originally sized against for the non-Codex autonomous
        # loop only. Without this, a worker process still correctly running a
        # single in-budget Codex turn would look "stuck" to this supervisor
        # long before the turn's own deadline ever fires, and would be killed
        # -- discarding a turn that already consumed real, non-refundable
        # Codex quota. `codex_enabled` is fixed for the lifetime of this
        # `Runtime`, so every worker process spawned from it may attempt a
        # Codex turn in any of its `quota` iterations.
        per_iteration_seconds: float = self.runtime.settings.max_experiment_seconds
        if self.runtime.codex_enabled:
            per_iteration_seconds = max(
                per_iteration_seconds,
                self.runtime.settings.codex_turn_timeout_seconds
                + _CODEX_OUTER_TIMEOUT_GRACE_SECONDS,
            )
        for index in range(process_count):
            quota = base_quota + int(index < remainder)
            parent_channel, child_channel = context.Pipe(duplex=False)
            group_channel, child_group_channel = context.Pipe(duplex=False)
            process = context.Process(
                target=_worker_process_main,
                args=(
                    settings_payload,
                    str(self.runtime.artifacts.root),
                    self.runtime.api_enabled,
                    self.runtime.codex_enabled,
                    cycle_number,
                    index,
                    quota,
                    child_channel,
                    child_group_channel,
                ),
                daemon=False,
            )
            process.start()
            child_channel.close()
            child_group_channel.close()
            deadline = started_at + quota * per_iteration_seconds + 30
            processes.append(
                _SupervisedWorkerProcess(
                    process=process,
                    result_channel=parent_channel,
                    execution_group_channel=group_channel,
                    active_execution_groups=set(),
                    active_execution_descendants={},
                    quota=quota,
                    deadline=deadline,
                )
            )
        completed = 0
        errors: list[str] = []
        stop_forwarded = False
        for worker in processes:
            while worker.process.is_alive() and time.monotonic() < worker.deadline:
                worker.process.join(timeout=0.05)
                _drain_execution_group_events(worker)
                if self.stop_requested.is_set() and not stop_forwarded:
                    for active in processes:
                        _drain_execution_group_events(active)
                        if active.process.is_alive():
                            _terminate_supervised_worker(
                                active,
                                terminate_timeout=per_iteration_seconds + 2,
                            )
                    stop_forwarded = True
                    worker.deadline = min(
                        worker.deadline,
                        time.monotonic() + per_iteration_seconds + 2,
                    )
            _drain_execution_group_events(worker, wait_seconds=0.05)
            if (
                worker.process.is_alive()
                or worker.active_execution_groups
                or worker.active_execution_descendants
            ):
                _terminate_supervised_worker(
                    worker,
                    terminate_timeout=per_iteration_seconds + 2,
                )
            if worker.process.is_alive():
                errors.append(f"worker process {worker.process.pid} could not be terminated")
            elif worker.result_channel.poll():
                try:
                    kind, payload = worker.result_channel.recv()
                except EOFError:
                    errors.append(f"worker process {worker.process.pid} exited without a result")
                else:
                    if kind == "completed":
                        completed += int(payload)
                    else:
                        errors.append(str(payload))
            elif worker.process.exitcode != 0:
                errors.append(
                    f"worker process {worker.process.pid} exited with code "
                    f"{worker.process.exitcode}"
                )
            worker.result_channel.close()
            worker.execution_group_channel.close()
        if errors:
            raise RuntimeError("; ".join(errors))
        return completed

    def _evolve(self, cycle_number: int) -> dict[str, object]:
        methods = self.runtime.repository.list_methods(("active", "candidate", "archived"))
        active = [
            method
            for method in methods
            if method.family == "integer_counterexample" and method.status == "active"
        ]
        candidates = [
            method
            for method in methods
            if method.family == "integer_counterexample" and method.status == "candidate"
        ]
        if not active:
            return {"decision": "no_active_parent"}
        parent = max(active, key=lambda method: method.version)
        if not candidates:
            child_spec = mutate_integer_search(
                parent.spec,
                random.Random(cycle_number),
            )
            next_version = (
                max(
                    method.version
                    for method in methods
                    if method.family == parent.family
                )
                + 1
            )
            child = MethodVersion(
                id=uuid5(
                    NAMESPACE_URL,
                    f"mathloop:mutation:{parent.id}:cycle:{cycle_number}",
                ),
                family=parent.family,
                version=next_version,
                spec=child_spec,
                parent_id=parent.id,
                status="candidate",
                created_at=BASELINE_CREATED_AT + timedelta(seconds=cycle_number),
            )
            self.runtime.repository.register_method(
                child,
                idempotency_key=f"method:mutation:{parent.id}:{cycle_number}",
            )
            self.runtime.repository.record_metric(
                "evolution.candidate_created",
                {
                    "parent_id": str(parent.id),
                    "child_id": str(child.id),
                    "cycle": cycle_number,
                },
                f"evolution:candidate:{child.id}",
            )
            return {"decision": "candidate_created", "child_id": str(child.id)}

        child = max(candidates, key=lambda method: method.version)
        parent_metrics = self._holdout_metrics(parent.id)
        child_metrics = self._holdout_metrics(child.id)
        parent_work = self.runtime.repository.get_method_work_units(
            parent.id,
            MetricsCohort.HOLDOUT,
            lane=EVOLUTION_HOLDOUT_LANE,
        )
        child_work = self.runtime.repository.get_method_work_units(
            child.id,
            MetricsCohort.HOLDOUT,
            lane=EVOLUTION_HOLDOUT_LANE,
        )
        comparable = _comparable_budgets(
            parent_metrics.cost_usd,
            child_metrics.cost_usd,
            parent_work=parent_work,
            child_work=child_work,
        )
        created_cycle = max(
            int((child.created_at - BASELINE_CREATED_AT).total_seconds()),
            0,
        )
        evaluation_cycles = max(cycle_number - created_cycle, 0)
        enough_trials = (
            parent_metrics.trials >= MINIMUM_HOLDOUT_TRIALS
            and child_metrics.trials >= MINIMUM_HOLDOUT_TRIALS
        )
        if not enough_trials or not comparable:
            if evaluation_cycles < MAX_CANDIDATE_EVALUATION_CYCLES:
                decision = "insufficient_data"
            else:
                self.runtime.repository.set_method_status(
                    child.id,
                    "archived",
                    "candidate evaluation window ended without comparable holdout evidence",
                )
                decision = "candidate_retired"
        elif should_promote(
            parent_metrics,
            child_metrics,
            MINIMUM_HOLDOUT_TRIALS,
        ):
            self.runtime.repository.promote_method(
                child.id,
                parent.id,
                "holdout verified progress per cost exceeded parent under comparable budgets",
            )
            decision = "promoted"
        else:
            self.runtime.repository.set_method_status(
                child.id,
                "archived",
                "paired holdout evaluation did not exceed the active baseline",
            )
            decision = "no_promotion"
        payload: dict[str, object] = {
            "decision": decision,
            "parent_id": str(parent.id),
            "child_id": str(child.id),
            "parent_trials": parent_metrics.trials,
            "child_trials": child_metrics.trials,
            "parent_cost_usd": format(parent_metrics.cost_usd, "f"),
            "child_cost_usd": format(child_metrics.cost_usd, "f"),
            "parent_work_units": parent_work,
            "child_work_units": child_work,
            "comparable_budgets": comparable,
            "evaluation_cycles": evaluation_cycles,
            "cohort": MetricsCohort.HOLDOUT.value,
        }
        self.runtime.repository.record_metric(
            f"evolution.{decision}",
            payload,
            (
                f"evolution:decision:{child.id}:{parent_metrics.trials}:"
                f"{child_metrics.trials}:{decision}"
            ),
        )
        return payload

    def _holdout_metrics(self, method_id: UUID) -> MethodMetrics:
        return self.runtime.repository.get_method_execution_metrics(
            method_id,
            MetricsCohort.HOLDOUT,
            lane=EVOLUTION_HOLDOUT_LANE,
        )


def _comparable_budgets(
    parent: Decimal,
    child: Decimal,
    *,
    parent_work: int,
    child_work: int,
) -> bool:
    def comparable(left: Decimal, right: Decimal) -> bool:
        if left == right == 0:
            return True
        maximum = max(left, right)
        minimum = min(left, right)
        return minimum > 0 and maximum <= minimum * Decimal("1.10")

    return comparable(parent, child) and comparable(Decimal(parent_work), Decimal(child_work))


def _drain_execution_group_events(
    worker: _SupervisedWorkerProcess,
    *,
    wait_seconds: float = 0,
) -> None:
    wait = wait_seconds
    while worker.execution_group_channel.poll(wait):
        wait = 0
        try:
            kind, payload = worker.execution_group_channel.recv()
        except EOFError:
            return
        if kind in {"execution_group_started", "execution_group_stopped"}:
            if type(payload) is not int or payload <= 1:
                raise RuntimeError("worker reported an invalid execution process group")
            if kind == "execution_group_started":
                worker.active_execution_groups.add(payload)
            else:
                worker.active_execution_groups.discard(payload)
        elif kind in {
            "execution_descendant_started",
            "execution_descendant_stopped",
        }:
            pid, process_group_id = _execution_descendant_identity(payload)
            if kind == "execution_descendant_started":
                worker.active_execution_descendants[pid] = process_group_id
            else:
                worker.active_execution_descendants.pop(pid, None)
        else:
            raise RuntimeError(f"worker reported an unknown process-group event: {kind}")


def _terminate_supervised_worker(
    worker: _SupervisedWorkerProcess,
    *,
    terminate_timeout: float,
) -> None:
    known_groups = set(worker.active_execution_groups)
    known_groups.update(worker.active_execution_descendants.values())
    if worker.process.pid is not None:
        known_groups.add(worker.process.pid)
    terminate_process_tree(
        worker.process,
        known_process_groups=known_groups,
        terminate_timeout=terminate_timeout,
        kill_timeout=1,
    )
    worker.active_execution_groups.clear()
    worker.active_execution_descendants.clear()


def _execution_descendant_identity(payload: object) -> tuple[int, int]:
    if not isinstance(payload, dict):
        raise RuntimeError("worker reported an invalid execution descendant")
    pid = payload.get("pid")
    process_group_id = payload.get("process_group_id")
    if type(pid) is not int or pid <= 1:
        raise RuntimeError("worker reported an invalid execution descendant PID")
    if type(process_group_id) is not int or process_group_id <= 1:
        raise RuntimeError("worker reported an invalid descendant process group")
    return pid, process_group_id


def _worker_process_main(
    settings_payload: Settings,
    artifact_root: str,
    api_enabled: bool,
    codex_enabled: bool,
    cycle_number: int,
    process_index: int,
    quota: int,
    channel: Connection,
    execution_group_channel: Connection,
) -> None:
    if hasattr(os, "setsid"):
        os.setsid()
    stop_requested = False

    def request_stop(signum: int, frame: object) -> None:
        nonlocal stop_requested
        del signum, frame
        stop_requested = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    sender = channel
    database: Database | None = None
    try:
        settings = settings_payload
        database = Database(settings.database_url)
        repository = Repository(database)
        runtime = build_runtime(
            repository,
            ArtifactStore(Path(artifact_root)),
            api_enabled=api_enabled,
            codex_enabled=codex_enabled,
            settings=settings,
        )
        runtime.worker.execution_boundary = ProcessExecutionBoundary(
            supervisor_channel=execution_group_channel
        )
        runtime.register_baseline_methods()
        completed = 0
        worker_id = f"cycle-{cycle_number}-process-{process_index}-pid-{os.getpid()}"
        for _ in range(quota):
            if stop_requested:
                break
            if not runtime.worker.run_once(worker_id):
                break
            completed += 1
        sender.send(("completed", completed))
    except Exception as error:
        sender.send(("error", repr(error)))
    finally:
        if database is not None:
            database.close()
        sender.close()
        execution_group_channel.close()


def build_runtime(
    repository: Repository,
    artifacts: ArtifactStore,
    *,
    api_enabled: bool,
    codex_enabled: bool = False,
    settings: Settings | None = None,
    verifier_runner: JsonRunner | None = None,
) -> Runtime:
    if type(api_enabled) is not bool:
        raise TypeError("api_enabled must be a boolean")
    if type(codex_enabled) is not bool:
        raise TypeError("codex_enabled must be a boolean")
    if api_enabled and codex_enabled:
        # Fails fast, before a Database/Worker/etc. is even constructed. This
        # is necessary but not sufficient on its own: `Runtime` is a plain,
        # unfrozen dataclass, so nothing stops a caller from constructing one
        # directly with both flags set, bypassing this check entirely. The
        # authoritative guarantee -- the one that holds regardless of how a
        # `Runtime` came to exist -- lives in `register_baseline_methods`
        # itself; this is a fast, clear failure for the common path only.
        raise ValueError(
            "api_enabled and codex_enabled are mutually exclusive: the OpenAI "
            "API and Codex external methods settle through disjoint budgets "
            "and must never both be live in one runtime"
        )
    runtime_settings = settings or Settings(
        database_url=repository.database.database_url,
        artifact_root=artifacts.root,
    )
    if runtime_settings.codex_enabled != codex_enabled:
        # `codex_enabled` here is always authoritative for this Runtime,
        # exactly like `api_enabled` (which has no persisted Settings
        # counterpart at all). Without this, `register_codex_proof_strategy`
        # -- which gates on `settings.codex_enabled`, not this parameter --
        # could silently do nothing for a caller that asked for Codex here
        # but never separately set MATHLOOP_CODEX_ENABLED, or could silently
        # stay live for a caller that did not ask for it here but happened
        # to inherit that environment variable from an earlier session.
        # `model_copy` (not in-place mutation) so a caller-supplied Settings
        # object already in use elsewhere is never mutated out from under it.
        runtime_settings = runtime_settings.model_copy(update={"codex_enabled": codex_enabled})
    runner: JsonRunner
    if verifier_runner is None:
        runner = DockerRunner(
            image=SAGE_IMAGE_DIGEST,
            limits=DockerLimits(
                seconds=runtime_settings.max_experiment_seconds,
                memory_mb=runtime_settings.max_container_memory_mb,
                cpus=runtime_settings.max_container_cpus,
            ),
        )
    else:
        runner = verifier_runner
    methods = MethodRegistry()
    scheduler = RuntimeScheduler(
        repository,
        PortfolioPolicy(
            exploitation=0.55,
            novelty=0.15,
            completeness=0.15,
            verification=0.15,
        ),
    )
    worker = Worker(
        repository,
        artifacts,
        methods,
        runtime_settings,
    )
    reporting = Reporting(repository, artifacts)
    return Runtime(
        repository=repository,
        artifacts=artifacts,
        settings=runtime_settings,
        methods=methods,
        scheduler=scheduler,
        worker=worker,
        reporting=reporting,
        sage_runner=runner,
        api_enabled=api_enabled,
        codex_enabled=codex_enabled,
    )


def _build_codex_client(settings: Settings) -> CodexClient:
    """Build the one real `CodexClient` every Codex-enabled registration uses.

    Nothing here holds a live OS resource across a fork boundary: the launch
    policy and worktree manager are plain configuration values (paths and
    ints), and `CodexClient` itself only spawns the real `codex exec`
    subprocess inside `execute()`, never at construction. Constructing this
    fresh in whichever process calls `register_baseline_methods` -- the
    parent CLI process or a forked worker child -- is therefore always safe.
    """
    launch_policy = CodexLaunchPolicy(
        codex_binary=settings.codex_cli_path,
        codex_home=settings.codex_worktree_root / "codex-home",
    )
    worktree_manager = CodexWorktreeManager(
        repo_root=settings.codex_repo_root,
        worktree_root=settings.codex_worktree_root,
    )
    return CodexClient(launch_policy, worktree_manager)
