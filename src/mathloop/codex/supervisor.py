"""Bounded operation of the Codex proof-strategy provider.

`CodexSupervisor` composes the existing autonomous cycle (`AutonomousLoop`,
already exercised by the plain `mathloop run` command) with Codex-specific
bookkeeping: how many *new* Codex turn reservations a bounded `start` call is
allowed to request, and an operator pause/drain state that survives a
process restart because it is derived entirely from durable events already
in the ledger -- never held only in this object's own memory.

Nothing here talks to the Codex CLI, a worktree, or the turn ledger's write
path directly. `AutonomousLoop.cycle()` -- via the ordinary scheduler and
`Worker.run_once` -- is the only thing that ever reserves, dispatches, or
settles a Codex turn (through `reserve_codex_turn`, `mark_codex_turn_
dispatched`, `append_codex_turn_event`, `complete_codex_turn`, and
`fail_codex_turn`, all built in earlier tasks). This module only decides
*how many cycles* to run and *whether it is currently allowed to run any*;
the durable daily/role/concurrency caps in `reserve_codex_turn` itself are
what actually make "never exceed the policy" true, unconditionally,
regardless of what a `--turns` argument asks for.

`reconcile_codex_turns` is deliberately never called from here (or anywhere
in `src/`): Task 4's concurrency fix was reviewed and accepted on the
explicit premise that reconciliation never runs in this plan, and scheduling
it would silently invalidate that review.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from threading import Event

from mathloop.codex.domain import CodexModelRole, CodexPolicy
from mathloop.runtime import Runtime

_PAUSED_EVENT = "codex_supervisor.paused"
_RESUMED_EVENT = "codex_supervisor.resumed"
_RESERVED_EVENT = "codex_turn.reserved"
_ACTIVE_TURN_STATUSES = ("dispatched", "running")
_FAILURE_TURN_STATUSES = ("failed", "timed_out", "ambiguous")
_DEFAULT_DRAIN_POLL_SECONDS = 0.2


class CodexSupervisor:
    """Runs bounded Codex cycles and reports/controls their durable state."""

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.repository = runtime.repository
        # Captured once, before `start()` ever mutates `runtime.loop`'s own
        # attributes: `start()` re-narrows `worker_iterations`/
        # `queue_capacity` toward each cycle's REMAINING allowance (see
        # below), and must always narrow from this pristine baseline, never
        # from whatever a PRIOR `start()` call on this same supervisor left
        # behind -- otherwise `start(1)` followed by `start(6)` would
        # silently and permanently cap the second call at 1.
        self._default_worker_iterations = runtime.loop.worker_iterations
        self._default_queue_capacity = runtime.loop.queue_capacity

    # -- operator commands ---------------------------------------------------

    def start(
        self,
        max_turns: int,
        *,
        workers: int = 1,
        stop_requested: Event | None = None,
    ) -> dict[str, object]:
        """Run bounded cycles until `max_turns` new Codex turns are reserved.

        Never itself decides who may hold a reservation, a concurrency slot,
        or a daily/role budget line -- `reserve_codex_turn` (Task 4) is the
        sole, already-durable authority for all three, so this bound holds
        even if a caller asks for far more turns than the ledger could ever
        grant today. `max_turns` only bounds how many cycles this call is
        willing to *request*; it is not a per-call reservation cap of its
        own, since a single cycle's own internal batch (its scheduler
        capacity and worker iterations) is the atomic unit of dispatch here.
        """
        if type(max_turns) is not int or max_turns <= 0:
            raise ValueError("max_turns must be a positive integer")
        if type(workers) is not int or workers <= 0:
            raise ValueError("workers must be a positive integer")
        # Clamped, not merely requested: `--workers` has no upper bound of its
        # own, and `reserve_codex_turn`'s concurrency cap denies (never
        # queues) any reservation attempt beyond it. That denial is currently
        # terminal for the experiment it was attempted against (Task 4/5's
        # accepted, out-of-scope-here failure classification), so asking for
        # more workers than the concurrency policy allows would permanently
        # fail real problem/method pairs for no reason -- clamping here means
        # this call never itself creates that over-subscription. It does NOT
        # eliminate the risk entirely: a lease already held by a different,
        # concurrently running process still counts against the same cap and
        # can still cause a denial regardless of how few workers this call
        # requests.
        effective_workers = min(workers, self.runtime.settings.codex_concurrent_turn_limit)
        if self.is_paused():
            return {
                "requested_turns": max_turns,
                "workers": effective_workers,
                "started_turns": 0,
                "cycles_run": 0,
                "paused": True,
                "interrupted": False,
                "usage": self._usage_payload(),
            }
        self.runtime.register_baseline_methods()
        self.runtime.loop.worker_processes = effective_workers
        started_before = self.repository.count_events(_RESERVED_EVENT)
        cycles_run = 0
        interrupted = False
        while cycles_run < max_turns:
            remaining = max_turns - (self.repository.count_events(_RESERVED_EVENT) - started_before)
            if remaining <= 0:
                break
            if self.is_paused():
                break
            if stop_requested is not None and stop_requested.is_set():
                interrupted = True
                break
            # Re-narrowed every iteration to the REMAINING allowance, always
            # from the pristine baseline captured at construction -- not just
            # once before the loop, and not from whatever a prior `start()`
            # call left `runtime.loop` holding. A single cycle that reserves
            # fewer than `max_turns` (e.g. because only some experiments were
            # eligible) must not let the NEXT cycle run a full-size batch
            # again -- that is how a caller asking for 6 could durably
            # over-reserve toward 2x. This is still only a soft narrowing of
            # one cycle's own batch size, not the hard limit: the durable
            # ledger caps above are what actually enforce that.
            self.runtime.loop.worker_iterations = min(self._default_worker_iterations, remaining)
            self.runtime.loop.queue_capacity = min(self._default_queue_capacity, remaining)
            report = self.runtime.loop.cycle()
            cycles_run += 1
            if stop_requested is not None and stop_requested.is_set():
                interrupted = True
                break
            if not report["scheduled"] and not report["worker_runs"]:
                # No new work was queued and nothing ran: further cycles
                # would just repeat the same no-op, so stop requesting them
                # rather than spinning until max_turns cycles are spent.
                break
        started_turns = self.repository.count_events(_RESERVED_EVENT) - started_before
        return {
            "requested_turns": max_turns,
            "workers": effective_workers,
            "started_turns": started_turns,
            "cycles_run": cycles_run,
            "paused": self.is_paused(),
            "interrupted": interrupted,
            "usage": self._usage_payload(),
        }

    def status(self) -> dict[str, object]:
        """Read-only snapshot: never appends an event or otherwise mutates the ledger."""
        return {
            "paused": self.is_paused(),
            "usage": self._usage_payload(),
            "active_worktree_ids": self._active_turn_ids(),
            "last_failure": self._last_failure(),
            "min_cli_version": self.runtime.settings.codex_min_cli_version,
            "observed_cli_version": self._observed_cli_version(),
        }

    def pause(self) -> dict[str, object]:
        """Durably record a pause. Idempotent: a no-op while already paused.

        Persisted purely as an event count comparison
        (`codex_supervisor.paused` vs. `codex_supervisor.resumed`), so a
        restarted process recomputes the same answer from the ledger alone
        -- there is no in-memory flag anywhere that a restart could lose.
        """
        if not self.is_paused():
            pause_count = self.repository.count_events(_PAUSED_EVENT)
            self.repository.record_metric(
                _PAUSED_EVENT,
                {"paused_at": datetime.now(UTC).isoformat()},
                idempotency_key=f"codex_supervisor:pause:{pause_count}",
            )
        return self.status()

    def resume(self) -> dict[str, object]:
        """Durably clear a pause. Idempotent: a no-op while not paused."""
        if self.is_paused():
            resumed_count = self.repository.count_events(_RESUMED_EVENT)
            self.repository.record_metric(
                _RESUMED_EVENT,
                {"resumed_at": datetime.now(UTC).isoformat()},
                idempotency_key=f"codex_supervisor:resume:{resumed_count}",
            )
        return self.status()

    def drain(
        self,
        *,
        grace_seconds: float = 60.0,
        poll_seconds: float = _DEFAULT_DRAIN_POLL_SECONDS,
        stop_requested: Event | None = None,
    ) -> dict[str, object]:
        """Pause (preventing new claims), then wait for active leases to clear.

        Never kills an in-flight turn itself: it only observes
        `codex_usage_status(...).active_leases` -- the same active-lease
        count `reserve_codex_turn` enforces the concurrency cap against --
        until it reaches zero, `grace_seconds` elapses, or `stop_requested`
        fires (an operator interrupt during the wait itself), whichever is
        first. The pause this begins with is never undone by an interrupt:
        an operator who asked to drain and then grew impatient still gets a
        durably paused supervisor back, not a resumed one.
        """
        if type(grace_seconds) not in (int, float) or grace_seconds < 0:
            raise ValueError("grace_seconds must be a non-negative number")
        if type(poll_seconds) not in (int, float) or poll_seconds <= 0:
            raise ValueError("poll_seconds must be a positive number")
        self.pause()
        deadline = time.monotonic() + grace_seconds
        drained = False
        interrupted = False
        while True:
            active_leases = self.repository.codex_usage_status(datetime.now(UTC)).active_leases
            if active_leases == 0:
                drained = True
                break
            if stop_requested is not None and stop_requested.is_set():
                interrupted = True
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(poll_seconds, remaining))
        payload = self.status()
        payload["drained"] = drained
        payload["interrupted"] = interrupted
        payload["grace_seconds"] = grace_seconds
        return payload

    def report(self) -> dict[str, object]:
        """Read-only accounting summary: current status plus turn outcome counts."""
        payload = self.status()
        payload["turns_by_status"] = self._turns_by_status()
        return payload

    # -- durable projections --------------------------------------------------

    def is_paused(self) -> bool:
        """Whether the durable pause projection is currently active.

        `paused > resumed` rather than a stored boolean: `pause`/`resume`
        each append at most one event per genuine transition (both are
        no-ops while already in the target state), so the two counts can
        never drift more than one apart, and recomputing this from `events`
        on every call is exactly what makes a restart safe -- there is
        nothing else to lose.
        """
        paused = self.repository.count_events(_PAUSED_EVENT)
        resumed = self.repository.count_events(_RESUMED_EVENT)
        return paused > resumed

    def _policy(self) -> CodexPolicy:
        settings = self.runtime.settings
        return CodexPolicy(
            daily_turn_limit=settings.codex_daily_turn_limit,
            concurrent_turn_limit=settings.codex_concurrent_turn_limit,
            turn_timeout_seconds=settings.codex_turn_timeout_seconds,
            model_turn_limits={
                CodexModelRole.LUNA.value: settings.codex_luna_turn_limit,
                CodexModelRole.TERRA.value: settings.codex_terra_turn_limit,
                CodexModelRole.SOL.value: settings.codex_sol_turn_limit,
            },
            reserved_sol_turns=settings.codex_reserved_sol_turns,
        )

    def _usage_payload(self) -> dict[str, object]:
        usage = self.repository.codex_usage_status(datetime.now(UTC))
        policy = self._policy()
        return {
            "budget_day": usage.budget_day.isoformat(),
            "daily_limit": policy.daily_turn_limit,
            "daily_reserved": usage.daily_reserved,
            "role_limits": dict(policy.model_turn_limits),
            "role_reserved": dict(usage.role_reserved),
            "reserved_sol_turns": policy.reserved_sol_turns,
            "concurrent_turn_limit": policy.concurrent_turn_limit,
            "active_leases": usage.active_leases,
            # Turns and tokens only -- never a dollar-equivalent figure.
            "tokens": usage.usage.model_dump(mode="json"),
        }

    def _active_turn_ids(self) -> list[str]:
        with self.repository.database.transaction() as connection:
            rows = connection.execute(
                "SELECT id FROM codex_turns WHERE status = ANY(%(statuses)s) ORDER BY created_at",
                {"statuses": list(_ACTIVE_TURN_STATUSES)},
            ).fetchall()
        return [str(row[0]) for row in rows]

    def _last_failure(self) -> dict[str, object] | None:
        with self.repository.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id, status, failure_kind, failure_message, updated_at
                FROM codex_turns WHERE status = ANY(%(statuses)s)
                ORDER BY updated_at DESC LIMIT 1
                """,
                {"statuses": list(_FAILURE_TURN_STATUSES)},
            ).fetchone()
        if row is None:
            return None
        turn_id, status, failure_kind, failure_message, updated_at = row
        return {
            "turn_id": str(turn_id),
            "status": status,
            "failure_kind": failure_kind,
            "failure_message": failure_message,
            "updated_at": updated_at.isoformat(),
        }

    def _observed_cli_version(self) -> str | None:
        with self.repository.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT cli_version FROM codex_turns
                WHERE cli_version IS NOT NULL ORDER BY updated_at DESC LIMIT 1
                """
            ).fetchone()
        return None if row is None else str(row[0])

    def _turns_by_status(self) -> dict[str, int]:
        with self.repository.database.transaction() as connection:
            rows = connection.execute(
                "SELECT status, count(*) FROM codex_turns GROUP BY status"
            ).fetchall()
        return {str(status): int(count) for status, count in rows}
