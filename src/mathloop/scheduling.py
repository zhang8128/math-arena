"""Deterministic portfolio allocation and exact in-memory budget policy."""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, cast
from uuid import UUID

from mathloop.billing import MAX_DATABASE_USD, validate_database_usd
from mathloop.domain import Experiment, ExperimentStatus, MethodVersion, Problem

if TYPE_CHECKING:
    from mathloop.storage.repository import Repository

EVOLUTION_HOLDOUT_LANE = "evolution_holdout"
ROUTING_HOLDOUT_LANE = "routing_holdout"
EVOLUTION_HOLDOUT_EVALUATION_BUDGET = 1


def _validate_weight(value: object, name: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{name} must be an integer or float")
    weight = float(cast(int | float, value))
    if not math.isfinite(weight) or weight <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return weight


def _require_rng(rng: object) -> random.Random:
    if not isinstance(rng, random.Random):
        raise TypeError("rng must be a random.Random instance")
    return rng


@dataclass(frozen=True)
class PortfolioPolicy:
    exploitation: float
    novelty: float
    completeness: float
    verification: float

    lanes: ClassVar[tuple[str, ...]] = (
        "exploitation",
        "novelty",
        "completeness",
        "verification",
    )

    def __post_init__(self) -> None:
        weights = tuple(_validate_weight(getattr(self, lane), lane) for lane in self.lanes)
        if not math.isclose(math.fsum(weights), 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("portfolio weights must sum to one")
        for lane, weight in zip(self.lanes, weights, strict=True):
            object.__setattr__(self, lane, weight)

    def choose_lane(self, rng: random.Random) -> str:
        generator = _require_rng(rng)
        draw = generator.random()
        cumulative = 0.0
        for lane in self.lanes:
            cumulative += getattr(self, lane)
            if draw < cumulative:
                return lane
        return self.lanes[-1]

    def allocate_batch(self, capacity: int, rng: random.Random) -> tuple[str, ...]:
        if type(capacity) is not int:
            raise TypeError("capacity must be an integer")
        if capacity < len(self.lanes):
            raise ValueError(f"capacity must be at least {len(self.lanes)}")
        generator = _require_rng(rng)
        allocation = list(self.lanes)
        allocation.extend(self.choose_lane(generator) for _ in range(capacity - len(self.lanes)))
        generator.shuffle(allocation)
        return tuple(allocation)


def _validate_usd(value: object, field_name: str) -> Decimal:
    validate_database_usd(value, field_name=field_name, positive=False)  # type: ignore[arg-type]
    amount = value
    assert isinstance(amount, Decimal)
    if amount > MAX_DATABASE_USD:
        raise ValueError(f"{field_name} exceeds NUMERIC(14, 6) capacity")
    return amount


@dataclass(frozen=True)
class BudgetLedger:
    limit_usd: Decimal
    spent_usd: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        limit = _validate_usd(self.limit_usd, "limit_usd")
        spent = _validate_usd(self.spent_usd, "spent_usd")
        if spent > limit:
            raise ValueError("spent_usd cannot exceed limit_usd")

    def authorize(self, estimated_cost_usd: Decimal) -> bool:
        estimate = _validate_usd(estimated_cost_usd, "estimated_cost_usd")
        return self.spent_usd + estimate <= self.limit_usd


class RuntimeScheduler:
    """Deterministic repository-backed portfolio scheduling."""

    def __init__(self, repository: Repository, policy: PortfolioPolicy) -> None:
        self.repository = repository
        self.policy = policy

    def schedule(self, limit: int, seed: int) -> tuple[UUID, ...]:
        if type(limit) is not int or limit < 0:
            raise ValueError("limit must be a non-negative integer")
        if type(seed) is not int:
            raise TypeError("seed must be an integer")
        if limit == 0:
            return ()
        problems = self.repository.list_eligible_problems()
        methods = self.repository.list_methods()
        evaluation = self._schedule_evolution_holdout_pair(
            limit,
            seed,
            problems,
            methods,
        )
        routing = self._schedule_routing_holdout_pair(
            limit - len(evaluation),
            seed,
            problems,
            methods,
        )
        reserved = evaluation + routing
        remaining_limit = limit - len(reserved)
        if remaining_limit == 0:
            return reserved
        rng = random.Random(seed)
        if remaining_limit >= len(self.policy.lanes):
            lanes = self.policy.allocate_batch(remaining_limit, rng)
        else:
            lanes = tuple(self.policy.choose_lane(rng) for _ in range(remaining_limit))
        methods_by_id = {method.id: method for method in methods}
        scheduled = list(reserved)
        used_work: list[tuple[UUID, str, dict[str, object]]] = []
        for experiment_id in reserved:
            experiment = self.repository.get_experiment(experiment_id)
            used_work.append(
                _semantic_work_key(experiment, methods_by_id[experiment.method_id])
            )
        allocations = sorted(
            enumerate(lanes),
            key=lambda allocation: (allocation[1] != "completeness", allocation[0]),
        )
        for index, lane in allocations:
            experiment_seed = _experiment_seed(seed, index, lane)
            replay = self.repository.find_scheduled_experiment(experiment_seed, lane)
            if replay is not None:
                scheduled.append(replay.id)
                if lane != "verification":
                    replay_method = methods_by_id.get(replay.method_id)
                    if replay_method is None:
                        replay_method = self.repository.get_method(replay.method_id)
                    used_work.append(_semantic_work_key(replay, replay_method))
                continue
            options = self._options(
                lane,
                problems,
                methods,
                used_work,
                seed,
                index,
            )
            if not options:
                self.repository.record_metric(
                    "scheduler.lane_unfilled",
                    {"lane": lane, "seed": seed, "index": index},
                    f"scheduler:unfilled:{seed}:{index}:{lane}",
                )
                continue
            if lane == "exploitation":
                problem, method = options[0]
            else:
                problem, method = options[(seed + index) % len(options)]
            config = self._config(problem, method, lane)
            existing = self.repository.find_experiment(
                problem.id,
                method.id,
                experiment_seed,
            )
            if existing is not None:
                scheduled.append(existing.id)
                if lane != "verification":
                    used_work.append(_semantic_work_key(existing, method))
                continue
            experiment = Experiment(
                id=UUID(
                    bytes=hashlib.sha256(
                        (
                            f"{problem.id}:{method.id}:{lane}:{experiment_seed}:"
                            f"{json.dumps(config, sort_keys=True, separators=(',', ':'))}"
                        ).encode()
                    ).digest()[:16]
                ),
                problem_id=problem.id,
                method_id=method.id,
                lane=lane,
                config=config,
                seed=experiment_seed,
                status=ExperimentStatus.QUEUED,
                created_at=datetime.now(UTC),
            )
            enqueued = self.repository.enqueue_if_semantic_work_available(
                experiment,
                idempotency_key=f"experiment:scheduled:{experiment.id}",
            )
            if not enqueued:
                self._record_suppression(
                    problem,
                    method,
                    lane,
                    seed,
                    index,
                    "concurrent_semantic_work",
                    config,
                )
                continue
            scheduled.append(experiment.id)
            used_work.append(_semantic_work_key(experiment, method))
        return tuple(scheduled)

    def _schedule_routing_holdout_pair(
        self,
        limit: int,
        seed: int,
        problems: tuple[Problem, ...],
        methods: tuple[MethodVersion, ...],
    ) -> tuple[UUID, ...]:
        from mathloop.evolution import MetricsCohort, ucb_score

        if limit < 2:
            return ()
        active = [method for method in methods if method.status == "active"]
        for problem in problems:
            if problem.cohort != "holdout" or problem.features.get(
                "finite_witness"
            ) is not False:
                continue
            applicable = [
                method for method in active if _is_applicable(problem, method)
            ]
            if len(applicable) < 2:
                continue
            applicable.sort(key=lambda method: (method.family, method.version))
            development = {
                method.id: self.repository.get_method_execution_metrics(
                    method.id,
                    MetricsCohort.DEVELOPMENT,
                )
                for method in applicable
            }
            observed = [
                method
                for method in applicable
                if development[method.id].trials > 0
            ]
            if not observed:
                continue
            total_trials = sum(
                development[method.id].trials for method in observed
            )
            static_method = applicable[0]
            adaptive_method = max(
                observed,
                key=lambda method: (
                    ucb_score(
                        development[method.id].verified,
                        development[method.id].trials,
                        total_trials,
                    ),
                    -method.version,
                    method.family,
                ),
            )
            if adaptive_method.id == static_method.id:
                continue
            pair_id = UUID(
                bytes=hashlib.sha256(
                    f"routing:{problem.id}:{seed}".encode()
                ).digest()[:16]
            )
            pair: list[UUID] = []
            pending: list[Experiment] = []
            for index, (method, policy) in enumerate(
                (
                    (static_method, "static_routing"),
                    (adaptive_method, "adaptive_routing"),
                )
            ):
                experiment_seed = _experiment_seed(
                    seed,
                    index,
                    ROUTING_HOLDOUT_LANE,
                )
                existing = self.repository.find_experiment(
                    problem.id,
                    method.id,
                    experiment_seed,
                )
                if existing is not None:
                    pair.append(existing.id)
                    continue
                if self.repository.has_terminal_experiment(problem.id, method.id):
                    pair.clear()
                    break
                config = self._config(problem, method, "exploitation")
                config.update(
                    {
                        "routing_policy": policy,
                        "routing_pair": str(pair_id),
                        "allocation_units": 1,
                    }
                )
                if method.family in {"integer_counterexample", "sage_polynomial"}:
                    config["max_evaluations"] = 1
                experiment = Experiment(
                    id=UUID(
                        bytes=hashlib.sha256(
                            (
                                f"{problem.id}:{method.id}:{ROUTING_HOLDOUT_LANE}:"
                                f"{experiment_seed}:"
                                f"{json.dumps(config, sort_keys=True, separators=(',', ':'))}"
                            ).encode()
                        ).digest()[:16]
                    ),
                    problem_id=problem.id,
                    method_id=method.id,
                    lane=ROUTING_HOLDOUT_LANE,
                    config=config,
                    seed=experiment_seed,
                    status=ExperimentStatus.QUEUED,
                    created_at=datetime.now(UTC),
                )
                pair.append(experiment.id)
                pending.append(experiment)
            if len(pair) == 2:
                self.repository.enqueue_evaluation_batch(
                    tuple(pending),
                    idempotency_prefix="experiment:routing-holdout",
                )
                return tuple(pair)
        return ()

    def _schedule_evolution_holdout_pair(
        self,
        limit: int,
        seed: int,
        problems: tuple[Problem, ...],
        methods: tuple[MethodVersion, ...],
    ) -> tuple[UUID, ...]:
        if limit < 2:
            return ()
        candidates = [
            method
            for method in methods
            if method.family == "integer_counterexample"
            and method.status == "candidate"
            and method.parent_id is not None
        ]
        if not candidates:
            return ()
        child = max(candidates, key=lambda method: method.version)
        parent = next(
            (
                method
                for method in methods
                if method.id == child.parent_id and method.status == "active"
            ),
            None,
        )
        if parent is None:
            return ()
        for problem in problems:
            if problem.cohort != "holdout" or not _is_applicable(problem, parent):
                continue
            if self.repository.problem_has_verified_claim(problem.id):
                continue
            declared_start = problem.checker["start"]
            assert type(declared_start) is int
            common_stop = min(int(parent.spec["stop"]), int(child.spec["stop"]))
            pair: list[UUID] = []
            pending: list[Experiment] = []
            for index, (method, policy) in enumerate(
                (
                    (parent, "fixed_parent"),
                    (child, "candidate_method"),
                )
            ):
                experiment_seed = _experiment_seed(
                    seed,
                    index,
                    EVOLUTION_HOLDOUT_LANE,
                )
                existing = self.repository.find_experiment(
                    problem.id,
                    method.id,
                    experiment_seed,
                )
                if existing is not None:
                    pair.append(existing.id)
                    continue
                if self.repository.has_terminal_experiment(problem.id, method.id):
                    pair.clear()
                    break
                config: dict[str, object] = {
                    "start": declared_start,
                    "stop": common_stop,
                    "order": method.spec["order"],
                    "evaluation_policy": policy,
                    "evaluation_pair": str(child.id),
                    "max_evaluations": EVOLUTION_HOLDOUT_EVALUATION_BUDGET,
                }
                if "provenance" in method.spec:
                    provenance = method.spec["provenance"]
                    assert isinstance(provenance, dict)
                    config["provenance"] = provenance["identity_sha256"]
                experiment = Experiment(
                    id=UUID(
                        bytes=hashlib.sha256(
                            (
                                f"{problem.id}:{method.id}:{EVOLUTION_HOLDOUT_LANE}:"
                                f"{experiment_seed}:"
                                f"{json.dumps(config, sort_keys=True, separators=(',', ':'))}"
                            ).encode()
                        ).digest()[:16]
                    ),
                    problem_id=problem.id,
                    method_id=method.id,
                    lane=EVOLUTION_HOLDOUT_LANE,
                    config=config,
                    seed=experiment_seed,
                    status=ExperimentStatus.QUEUED,
                    created_at=datetime.now(UTC),
                )
                pair.append(experiment.id)
                pending.append(experiment)
            if len(pair) == 2:
                self.repository.enqueue_evaluation_batch(
                    tuple(pending),
                    idempotency_prefix="experiment:evolution-holdout",
                )
                return tuple(pair)
        return ()

    def _options(
        self,
        lane: str,
        problems: tuple[Problem, ...],
        methods: tuple[MethodVersion, ...],
        used_work: list[tuple[UUID, str, dict[str, object]]],
        schedule_seed: int,
        allocation_index: int,
    ) -> list[tuple[Problem, MethodVersion]]:
        from mathloop.evolution import MetricsCohort, ucb_score

        if lane == "verification":
            # Candidate verification is canonical work performed immediately after
            # completion. With no independently queued candidate, this allocation is
            # deliberately audited as unfilled rather than relabeled solver work.
            return []
        options: list[tuple[Problem, MethodVersion]] = []
        for problem in problems:
            if problem.cohort == "holdout":
                continue
            for method in methods:
                if not _is_applicable(problem, method):
                    continue
                if method.status == "candidate":
                    continue
                if lane == "completeness" and not (
                    method.family == "integer_counterexample"
                    and method.status == "active"
                    and method.spec.get("order") == "ascending"
                ):
                    continue
                if self.repository.problem_has_verified_claim(problem.id):
                    self._record_suppression(
                        problem,
                        method,
                        lane,
                        schedule_seed,
                        allocation_index,
                        "resolved_problem",
                        self._config(problem, method, lane),
                    )
                    continue
                config = self._config(problem, method, lane)
                work_key = _semantic_work_key_parts(problem.id, method, config)
                if any(
                    _semantic_work_overlaps(work_key, used) for used in used_work
                ) or self.repository.semantic_work_exists(problem.id, method.id, config):
                    self._record_suppression(
                        problem,
                        method,
                        lane,
                        schedule_seed,
                        allocation_index,
                        "semantic_work_exists",
                        config,
                    )
                    continue
                if lane != "completeness" and self.repository.has_terminal_experiment(
                    problem.id,
                    method.id,
                ):
                    self._record_suppression(
                        problem,
                        method,
                        lane,
                        schedule_seed,
                        allocation_index,
                        "terminal_method_problem_pair",
                        config,
                    )
                    continue
                options.append((problem, method))
        if lane == "exploitation":
            total_trials = sum(
                self.repository.get_method_metrics(
                    problem.domain,
                    method.id,
                    MetricsCohort.DEVELOPMENT,
                ).trials
                for problem, method in options
            )
            options.sort(
                key=lambda option: (
                    -ucb_score(
                        self.repository.get_method_metrics(
                            option[0].domain,
                            option[1].id,
                            MetricsCohort.DEVELOPMENT,
                        ).verified,
                        self.repository.get_method_metrics(
                            option[0].domain,
                            option[1].id,
                            MetricsCohort.DEVELOPMENT,
                        ).trials,
                        total_trials,
                    ),
                    option[0].source_id,
                    option[1].family,
                    option[1].version,
                )
            )
        elif lane == "novelty":
            options.sort(
                key=lambda option: (
                    -option[0].version,
                    -option[1].version,
                    option[0].source_id,
                    option[1].family,
                )
            )
        else:
            options.sort(key=lambda option: (option[0].source_id, option[1].family))
        return options

    def _record_suppression(
        self,
        problem: Problem,
        method: MethodVersion,
        lane: str,
        schedule_seed: int,
        allocation_index: int,
        reason: str,
        config: dict[str, object],
    ) -> None:
        config_json = json.dumps(config, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(f"{problem.id}:{method.id}:{config_json}".encode()).hexdigest()
        self.repository.record_metric(
            "scheduler.duplicate_work_suppressed",
            {
                "problem_id": str(problem.id),
                "method_id": str(method.id),
                "lane": lane,
                "reason": reason,
                "semantic_work_digest": digest,
            },
            (f"scheduler:duplicate:{schedule_seed}:{allocation_index}:{lane}:{reason}:{digest}"),
        )

    def _config(self, problem: Problem, method: MethodVersion, lane: str) -> dict[str, object]:
        config: dict[str, object]
        if method.family == "integer_counterexample":
            if lane == "completeness":
                config = dict(
                    self.repository.get_next_completeness_spec(
                        problem.id,
                        method.family,
                        method.spec,
                    )
                )
            else:
                declared_start = problem.checker["start"]
                config = {
                    "start": declared_start,
                    "stop": method.spec["stop"],
                    "order": method.spec["order"],
                }
        elif method.family == "sage_polynomial":
            config = {
                "start": problem.checker["start"],
                "stop": method.spec["stop"],
                "order": method.spec["order"],
            }
        else:
            config = {
                key: value
                for key, value in method.spec.items()
                if key != "provenance"
            }
        if "provenance" in method.spec:
            provenance = method.spec["provenance"]
            assert isinstance(provenance, dict)
            config["provenance"] = provenance["identity_sha256"]
        return config


def _is_applicable(problem: Problem, method: MethodVersion) -> bool:
    checker = problem.checker
    if method.family == "integer_counterexample":
        return (
            checker.get("kind") == "integer_predicate"
            and type(checker.get("predicate_id")) is str
            and type(checker.get("start")) is int
        )
    if method.family == "symbolic_induction":
        return (
            checker.get("kind") == "integer_predicate"
            and checker.get("predicate_id") in {"sum_odds", "sum_integers"}
            and checker.get("start") == 0
        )
    if method.family == "sage_polynomial":
        return (
            checker.get("kind") == "integer_predicate"
            and type(checker.get("predicate_id")) is str
            and type(checker.get("start")) is int
        )
    if method.family == "proof_sketch":
        return True
    return False


def _semantic_work_key(
    experiment: Experiment,
    method: MethodVersion,
) -> tuple[UUID, str, dict[str, object]]:
    return _semantic_work_key_parts(
        experiment.problem_id,
        method,
        experiment.config,
    )


def _semantic_work_key_parts(
    problem_id: UUID,
    method: MethodVersion,
    config: dict[str, object],
) -> tuple[UUID, str, dict[str, object]]:
    if (
        method.family == "integer_counterexample"
        and type(config.get("start")) is int
        and type(config.get("stop")) is int
        and config.get("order") == "ascending"
    ):
        scope = f"family:{method.family}"
    else:
        scope = f"method:{method.id}"
    return (problem_id, scope, dict(config))


def _semantic_work_overlaps(
    left: tuple[UUID, str, dict[str, object]],
    right: tuple[UUID, str, dict[str, object]],
) -> bool:
    if left[:2] != right[:2]:
        return False
    left_config = left[2]
    right_config = right[2]
    if left_config == right_config:
        return True
    left_start = left_config.get("start")
    left_stop = left_config.get("stop")
    right_start = right_config.get("start")
    right_stop = right_config.get("stop")
    return (
        type(left_start) is int
        and type(left_stop) is int
        and type(right_start) is int
        and type(right_stop) is int
        and left_config.get("order") == right_config.get("order")
        and max(left_start, right_start) < min(left_stop, right_stop)
    )


def _experiment_seed(seed: int, index: int, lane: str) -> int:
    value = int.from_bytes(
        hashlib.sha256(f"{seed}:{index}:{lane}".encode()).digest()[:8],
        "big",
    )
    return value % (2**63 - 1)
