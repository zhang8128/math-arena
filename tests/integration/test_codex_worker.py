"""End-to-end coverage of the Codex turn ledger wiring inside `Worker`.

Every test here drives `Worker.run_once` through a real forked execution
boundary and a real (fake) Codex CLI subprocess against a real Postgres
`repository`. Nothing about the ledger calls -- reserve, dispatch, event
append, complete, fail -- is mocked: these tests exist specifically to prove
the *production* wiring in `worker.py` persists evidence in the right order
and never re-executes consumed work.
"""

import os
import subprocess
import tempfile
import threading
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from mathloop.artifacts import ArtifactStore
from mathloop.codex.client import CodexClient, CodexRequest, CodexTurnTimedOut
from mathloop.codex.domain import CodexModelRole, CodexTurnReservation
from mathloop.codex.events import CodexEvent
from mathloop.codex.launch import CodexLaunchPolicy
from mathloop.codex.worktrees import CodexWorktreeError, CodexWorktreeManager
from mathloop.config import Settings
from mathloop.domain import Experiment, ExperimentStatus, MethodVersion, Problem, ProblemStatus
from mathloop.methods.base import MethodContext, MethodRegistry, MethodResult
from mathloop.methods.proof_sketch import ProofSketch
from mathloop.provenance import component_provenance
from mathloop.storage.repository import Repository
from mathloop.worker import (
    ExecutionFailed,
    ExecutionLeaseLost,
    ExecutionOutcome,
    ProcessExecutionBoundary,
    Worker,
)

# ---------------------------------------------------------------------------
# Fake Codex CLI (shared with the low-level scenarios exercised here)
# ---------------------------------------------------------------------------

_FAKE_CODEX_SOURCE = '''\
#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\\n")
    sys.stdout.flush()


def main() -> int:
    argv = sys.argv[1:]
    mode = argv[-1] if argv else "success"
    worktree = None
    if "--cd" in argv:
        worktree = Path(argv[argv.index("--cd") + 1])
    # NOTE: the real, installed Codex CLI (0.145.0) has been confirmed by
    # direct binary inspection to NOT reliably include `cli_version` here --
    # `CodexClient` falls back to a separate `codex --version` query when
    # this event omits it (see `tests/unit/test_codex_client.py::
    # test_codex_client_falls_back_to_codex_version_when_thread_started_omits_it`
    # for the dedicated regression test). This fake keeps emitting the
    # convenient shape because this file's own scenarios are about the
    # ledger-dispatch/event-persistence path, not the CLI-version fallback
    # itself; do not treat this field's presence here as evidence it is
    # guaranteed present on the real CLI.
    _emit(
        {
            "type": "thread.started",
            "thread_id": "thread-worker-fake",
            "cli_version": "0.145.0-test",
        }
    )
    _emit({"type": "turn.started"})

    if mode == "hang":
        # Never completes on its own -- exists only to drive the client's
        # own timeout, which must survive being pickled across the real
        # multiprocessing pipe on its way back to the parent boundary.
        time.sleep(3600)
        return 0

    if mode == "slow_success":
        # Completes normally, but only after outliving lease_seconds in the
        # heartbeat tests below -- long enough to prove the experiment
        # lease was actively kept alive (or, in the lease-theft test,
        # long enough for a "thief" to steal it mid-run and for the next
        # heartbeat to notice).
        time.sleep(5.0)

    if worktree is not None:
        (worktree / "NOTES.md").write_text("codex was here\\n")
    _emit(
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": json.dumps(
                    {
                        "strategy": "induction",
                        "lemmas": ["base case holds"],
                        "risks": ["induction step may hide an off-by-one"],
                    }
                ),
            },
        }
    )
    _emit(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 10,
                "output_tokens": 12,
                "reasoning_output_tokens": 5,
            },
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "codex-worker-test@example.com", cwd=repo)
    _git("config", "user.name", "Codex Worker Test", cwd=repo)
    (repo / "README.md").write_text("seed content\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "seed", cwd=repo)
    return _git("rev-parse", "HEAD", cwd=repo).stdout.strip()


class CodexTurnMethod:
    """A fake `SolverMethod` that runs a real `CodexClient` turn.

    `context.config["codex_test_mode"]` selects the scenario: a normal turn,
    a failure before dispatch, a failure after dispatch, or a successful turn
    whose receipt is then tampered with to belong to a different reservation.
    """

    family = "fake_codex"

    def __init__(self, codex_binary: Path, repo_root: Path, worktree_root: Path) -> None:
        self._codex_binary = codex_binary
        self._repo_root = repo_root
        self._worktree_root = worktree_root

    def run(self, context: MethodContext) -> MethodResult:
        mode = str(context.config["codex_test_mode"])

        if mode == "pre_start_failure":
            raise ValueError("invalid codex prompt configuration")

        if mode == "dispatched_then_fail":
            context.mark_external_execution_started()
            raise OSError("codex worktree filesystem became unavailable")

        reservation = context.config["codex_reservation"]
        assert isinstance(reservation, CodexTurnReservation)
        base_sha = _git("rev-parse", "HEAD", cwd=self._repo_root).stdout.strip()
        launch_policy = CodexLaunchPolicy(
            codex_binary=self._codex_binary,
            codex_home=self._worktree_root / "codex-home",
        )
        inner_worktree_manager = CodexWorktreeManager(
            repo_root=self._repo_root, worktree_root=self._worktree_root
        )
        worktree_manager: object = inner_worktree_manager
        client_timeout = 30.0
        if mode == "hang_with_failing_cleanup":
            # A CodexTurnTimedOut whose cleanup also fails, driven through
            # the real forked boundary and the real ledger-write path
            # (mark_codex_turn_dispatched/fail_codex_turn), not just a bare
            # ProcessExecutionBoundary -- proving the note actually reaches
            # codex_turns.failure_message end to end, not merely that it
            # survives pickling in isolation.
            worktree_manager = _FailingRemoveWorktreeManager(inner_worktree_manager)
            client_timeout = 1.0
        client = CodexClient(
            launch_policy,
            worktree_manager,  # type: ignore[arg-type]
            environment={"PATH": os.environ.get("PATH", ""), "TMPDIR": tempfile.gettempdir()},
            timeout_seconds=client_timeout,
        )
        # The fake CLI only special-cases a handful of mode strings (e.g.
        # "hang", "slow_success"); anything else -- including "success" and
        # "mismatched_receipt" -- falls through to its normal completion
        # path unchanged, so forwarding the test mode directly as the
        # prompt lets one method double as the driver for those scenarios
        # too, without needing a mode-specific method class for each one.
        # "hang_with_failing_cleanup" is the one exception: the CLI itself
        # only knows "hang", so the prompt maps to that while the method's
        # own dispatch (above) still keys off the full test-mode string.
        prompt = "hang" if mode == "hang_with_failing_cleanup" else mode
        request: CodexRequest[ProofSketch] = CodexRequest(
            reservation=reservation,
            prompt=prompt,
            base_sha=base_sha,
            response_schema=ProofSketch,
        )
        emit_event = context.emit_external_event
        assert emit_event is not None
        response = client.execute(
            request, emit_event, on_dispatched=context.mark_external_execution_started
        )
        receipt = response.receipt
        if mode == "mismatched_receipt":
            receipt = receipt.model_copy(update={"reservation_id": uuid4()})
        return MethodResult(
            status="lead",
            summary="codex turn completed",
            artifact=response.patch,
            codex_turn_receipt=receipt,
        )


class _FailingRemoveWorktreeManager:
    """A worktree manager whose `remove` always fails, for note-survival tests.

    Duck-typed rather than a `CodexWorktreeManager` subclass so it can wrap
    the real `create`/`diff` behavior unchanged and only override `remove`.
    """

    def __init__(self, inner: CodexWorktreeManager) -> None:
        self._inner = inner

    def create(self, turn_id: object, base_sha: str, **kwargs: object) -> object:
        return self._inner.create(turn_id, base_sha, **kwargs)  # type: ignore[arg-type]

    def diff(self, worktree: object, **kwargs: object) -> object:
        return self._inner.diff(worktree, **kwargs)  # type: ignore[arg-type]

    def remove(self, worktree: object, **kwargs: object) -> None:
        del worktree, kwargs
        raise CodexWorktreeError("synthetic cleanup failure for note-survival test")


def _test_provenance() -> dict[str, object]:
    return component_provenance("method:fake_codex", "tests/integration/test_codex_worker.py")


def _enqueue_codex(repository: Repository, *, mode: str) -> Experiment:
    provenance = _test_provenance()
    problem = Problem(
        id=uuid4(),
        source_id=f"test/{uuid4()}",
        source_uri="local://codex-worker",
        source_hash=uuid4().hex * 2,
        statement="test",
        normalized_statement="test",
        domain="testing",
        features={},
        checker={"kind": "unsupported"},
        status=ProblemStatus.ELIGIBLE,
        cohort="development",
        version=1,
        created_at=datetime.now(UTC),
    )
    method = MethodVersion(
        id=uuid4(),
        family="fake_codex",
        version=1,
        spec={
            "external_provider": "codex",
            "codex_role": "terra",
            "codex_model": "gpt-5.6-terra",
            "provenance": provenance,
        },
        status="active",
        created_at=datetime.now(UTC),
    )
    experiment = Experiment(
        id=uuid4(),
        problem_id=problem.id,
        method_id=method.id,
        lane="codex",
        config={"codex_test_mode": mode, "provenance": provenance["identity_sha256"]},
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.add_problem(problem, f"problem:{problem.id}")
    repository.register_method(method, f"method:{method.id}")
    repository.enqueue(experiment, f"experiment:{experiment.id}")
    return experiment


def _settings(tmp_path: Path, *, lease_seconds: int = 30) -> Settings:
    return Settings(
        artifact_root=tmp_path / "artifacts",
        incoming_root=tmp_path / "incoming",
        max_experiment_seconds=2,
        lease_seconds=lease_seconds,
    )


def _worker(
    repository: Repository, tmp_path: Path, fake_codex: Path, *, lease_seconds: int = 30
) -> Worker:
    repo_root = tmp_path / "source-repo"
    _init_repo(repo_root)
    worktree_root = tmp_path / "codex-worktrees"
    methods = MethodRegistry()
    methods.register(
        CodexTurnMethod(fake_codex, repo_root, worktree_root),
        provenance=_test_provenance(),
    )
    return Worker(
        repository,
        ArtifactStore(tmp_path / "artifacts"),
        methods,
        _settings(tmp_path, lease_seconds=lease_seconds),
    )


@pytest.fixture
def fake_codex(tmp_path: Path) -> Path:
    script = tmp_path / "fake_codex.py"
    script.write_text(_FAKE_CODEX_SOURCE)
    script.chmod(0o700)
    return script


def _experiment_lease(repository: Repository, experiment_id: UUID) -> tuple[str, str | None]:
    """Return (status, lease_owner) straight from the row -- not the domain projection.

    `Experiment` (the projected domain object `repository.get_experiment`
    returns) does not expose `lease_owner`/`lease_expires_at` at all, so
    proving who currently holds an experiment's lease requires reading the
    row directly.
    """
    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT status, lease_owner FROM experiments WHERE id = %(id)s",
            {"id": experiment_id},
        ).fetchone()
    assert row is not None
    return row[0], row[1]


def _steal_lease(repository: Repository, experiment_id: UUID, thief: str) -> None:
    """Simulate a second worker legitimately re-claiming this experiment.

    Bypasses `claim_next`'s own gate (which only reclaims an *expired*
    lease) and writes the row directly -- this is a deterministic stand-in
    for the real race `claim_next` would eventually produce once the
    original worker's lease actually lapsed, not a test of `claim_next`
    itself. What this test needs is precise timing control over exactly
    when the "theft" lands relative to the running turn's own heartbeats.
    """
    with repository.database.transaction() as connection:
        connection.execute(
            """
            UPDATE experiments
            SET lease_owner = %(thief)s, lease_expires_at = %(expires)s
            WHERE id = %(id)s
            """,
            {
                "thief": thief,
                "expires": datetime.now(UTC) + timedelta(seconds=30),
                "id": experiment_id,
            },
        )


def _codex_turn_row(repository: Repository, experiment_id: UUID) -> tuple[str, str | None]:
    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT status, failure_kind FROM codex_turns WHERE experiment_id = %(id)s",
            {"id": experiment_id},
        ).fetchone()
    assert row is not None
    return row[0], row[1]


def _codex_turn_failure_message(repository: Repository, experiment_id: UUID) -> str | None:
    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT failure_message FROM codex_turns WHERE experiment_id = %(id)s",
            {"id": experiment_id},
        ).fetchone()
    assert row is not None
    return row[0]


def _codex_turn_event_types(repository: Repository, experiment_id: UUID) -> list[str]:
    with repository.database.transaction() as connection:
        turn_row = connection.execute(
            "SELECT id FROM codex_turns WHERE experiment_id = %(id)s",
            {"id": experiment_id},
        ).fetchone()
        assert turn_row is not None
        rows = connection.execute(
            "SELECT event_type FROM codex_turn_events WHERE turn_id = %(id)s ORDER BY sequence",
            {"id": turn_row[0]},
        ).fetchall()
    return [row[0] for row in rows]


def _codex_turn_count(repository: Repository) -> int:
    with repository.database.transaction() as connection:
        row = connection.execute("SELECT count(*) FROM codex_turns").fetchone()
    assert row is not None
    return int(row[0])


# ---------------------------------------------------------------------------
# The five behaviors the brief requires
# ---------------------------------------------------------------------------


def test_dispatch_marker_is_persisted_and_turn_completes(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    experiment = _enqueue_codex(repository, mode="success")

    assert _worker(repository, tmp_path, fake_codex).run_once("worker-1")

    assert repository.get_experiment(experiment.id).status is ExperimentStatus.SUCCEEDED
    assert repository.count_events("codex_turn.reserved") == 1
    assert repository.count_events("codex_turn.dispatched") == 1
    assert repository.count_events("codex_turn.completed") == 1
    status, _ = _codex_turn_row(repository, experiment.id)
    assert status == "completed"
    with repository.database.transaction() as connection:
        cost_row = connection.execute(
            "SELECT cost_usd FROM experiments WHERE id = %(id)s", {"id": experiment.id}
        ).fetchone()
    assert cost_row is not None
    assert cost_row[0] == Decimal("0")
    with repository.database.transaction() as connection:
        result_row = connection.execute(
            "SELECT result FROM experiments WHERE id = %(id)s", {"id": experiment.id}
        ).fetchone()
    assert result_row is not None
    receipt_payload = result_row[0]["codex_turn_receipt"]
    assert receipt_payload["accounting_unit"] == "chatgpt_codex_turn"
    assert "usd" not in receipt_payload


def test_events_are_persisted_as_they_arrive_in_order(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    experiment = _enqueue_codex(repository, mode="success")

    assert _worker(repository, tmp_path, fake_codex).run_once("worker-1")

    assert _codex_turn_event_types(repository, experiment.id) == [
        "thread.started",
        "turn.started",
        "item.completed",
        "turn.completed",
    ]


def test_pre_start_failure_settles_without_consuming_a_turn(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    experiment = _enqueue_codex(repository, mode="pre_start_failure")

    assert _worker(repository, tmp_path, fake_codex).run_once("worker-1")

    failure = repository.list_failures()[0]
    assert failure.experiment_id == experiment.id
    assert failure.kind == "method"
    assert failure.retryable is False
    status, _ = _codex_turn_row(repository, experiment.id)
    assert status == "failed"
    assert repository.count_events("codex_turn.dispatched") == 0
    assert _codex_turn_event_types(repository, experiment.id) == []


def test_blocks_replay_after_dispatch(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    experiment = _enqueue_codex(repository, mode="dispatched_then_fail")
    worker = _worker(repository, tmp_path, fake_codex)

    assert worker.run_once("worker-1")

    first_failure = repository.list_failures()[0]
    assert first_failure.kind == "infrastructure"
    assert first_failure.retryable is True
    status, _ = _codex_turn_row(repository, experiment.id)
    assert status == "ambiguous"
    assert _codex_turn_count(repository) == 1

    assert repository.requeue_retryable_failures() == 1
    assert worker.run_once("worker-2")

    second_failure = repository.list_failures()[0]
    assert second_failure.kind == "budget"
    assert second_failure.retryable is False
    # The turn was never re-reserved or re-dispatched for this experiment:
    # the row count and status are exactly as the first attempt left them.
    assert _codex_turn_count(repository) == 1
    status_after_retry, _ = _codex_turn_row(repository, experiment.id)
    assert status_after_retry == "ambiguous"


def test_rejects_a_receipt_for_another_reservation(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    experiment = _enqueue_codex(repository, mode="mismatched_receipt")

    assert _worker(repository, tmp_path, fake_codex).run_once("worker-1")

    failure = repository.list_failures()[0]
    assert failure.experiment_id == experiment.id
    assert failure.kind == "method"
    assert failure.retryable is False
    assert "codex turn receipt rejected" in failure.message
    # The turn's own ledger row is left exactly where a trustworthy dispatch
    # left it -- dispatched, not completed and not failed -- since the
    # untrustworthy receipt tells us nothing about what actually happened.
    status, _ = _codex_turn_row(repository, experiment.id)
    assert status == "dispatched"


def test_cleanup_failure_notes_reach_the_persisted_codex_turn_failure_message(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    """A `CodexTurnTimedOut` whose cleanup also fails must not lose that
    evidence by the time it reaches `codex_turns.failure_message`.

    `CodexTurnTimedOut.__reduce__` correctly carries `__notes__` across the
    real forked-child-to-parent pickle boundary (fixed and mutation-verified
    in the prior round), but `_run_codex_turn` used to persist
    `repr(error.cause)` -- which never includes `__notes__` -- discarding
    the evidence one layer downstream from where it was actually fixed. This
    drives the failure through the real `Worker.run_once`/`_fail_codex_turn`
    path, not just pickling in isolation, and asserts the note text itself
    lands in the persisted message.
    """
    experiment = _enqueue_codex(repository, mode="hang_with_failing_cleanup")

    assert _worker(repository, tmp_path, fake_codex).run_once("worker-1")

    status, _ = _codex_turn_row(repository, experiment.id)
    assert status == "timed_out"
    failure_message = _codex_turn_failure_message(repository, experiment.id)
    assert failure_message is not None
    assert "cleanup also failed" in failure_message
    assert "synthetic cleanup failure for note-survival test" in failure_message


# ---------------------------------------------------------------------------
# Low-level pipe-protocol coverage: the new `external_event` extension
# ---------------------------------------------------------------------------


def _codex_test_problem() -> Problem:
    return Problem(
        id=uuid4(),
        source_id="test/codex-pipe-protocol",
        source_uri="local://codex-pipe-protocol",
        source_hash="a" * 64,
        statement="test",
        normalized_statement="test",
        domain="testing",
        features={},
        checker={"kind": "unsupported"},
        status=ProblemStatus.ELIGIBLE,
        cohort="development",
        version=1,
        created_at=datetime.now(UTC),
    )


class EmitEventThenCheckMethod:
    family = "emit-event-then-check"

    def run(self, context: MethodContext) -> MethodResult:
        assert context.emit_external_event is not None
        marker = Path(str(context.config["marker_path"]))
        assert not marker.exists()
        event = CodexEvent(
            sequence=0,
            event_type="turn.started",
            payload={"type": "turn.started"},
            raw_sha256="a" * 64,
        )
        context.emit_external_event(event)
        # If this were reached before the parent's callback ran, the marker
        # file would not exist yet -- proving the parent persists the event
        # before it acknowledges it, and the child never reads ahead of that.
        assert marker.exists()
        return MethodResult(status="lead", summary="event persisted before ack")


def test_boundary_persists_external_event_before_acknowledging(tmp_path: Path) -> None:
    boundary = ProcessExecutionBoundary()
    marker = tmp_path / "event-persisted"
    context = MethodContext(
        problem=_codex_test_problem(),
        seed=1,
        config={"marker_path": str(marker)},
    )
    persisted: list[CodexEvent] = []

    def persist(event: CodexEvent) -> None:
        persisted.append(event)
        marker.write_text("persisted")

    outcome: ExecutionOutcome = boundary.run(
        EmitEventThenCheckMethod(),
        context,
        timeout_seconds=5.0,
        external_event_callback=persist,
    )

    assert outcome.result.status == "lead"
    assert len(persisted) == 1
    assert persisted[0].event_type == "turn.started"


def test_boundary_stops_child_when_event_callback_fails(tmp_path: Path) -> None:
    boundary = ProcessExecutionBoundary()
    context = MethodContext(
        problem=_codex_test_problem(),
        seed=1,
        config={"marker_path": str(tmp_path / "unused")},
    )

    def failing_persist(event: CodexEvent) -> None:
        del event
        raise OSError("ledger unavailable")

    with pytest.raises(ExecutionFailed) as raised:
        boundary.run(
            _AlwaysWritesMarkerFirst(tmp_path / "unused"),
            context,
            timeout_seconds=5.0,
            external_event_callback=failing_persist,
        )

    assert isinstance(raised.value.cause, OSError)
    assert boundary.has_live_child is False


class _SleepsBrieflyMethod:
    """A `SolverMethod` that just runs long enough for a heartbeat tick to fire."""

    family = "sleeps-briefly"

    def run(self, context: MethodContext) -> MethodResult:
        del context
        time.sleep(0.5)
        return MethodResult(status="lead", summary="done")


def test_boundary_aborts_when_heartbeat_callback_raises(tmp_path: Path) -> None:
    """A raising `heartbeat_callback` (e.g. a transient database error) must
    be handled exactly like its two sibling callbacks -- kill the child,
    surface the error -- not escape `run()` unwrapped. Unlike a confirmed
    `False` return, this is `ExecutionLeaseLost` with a `cause` set, since
    the two situations (confirmed loss vs. inconclusive failure) are
    genuinely different even though the safe response is identical.
    """
    boundary = ProcessExecutionBoundary()
    context = MethodContext(problem=_codex_test_problem(), seed=1, config={})

    def failing_heartbeat() -> bool:
        raise RuntimeError("transient database error")

    with pytest.raises(ExecutionLeaseLost) as raised:
        boundary.run(
            _SleepsBrieflyMethod(),
            context,
            timeout_seconds=5.0,
            heartbeat_callback=failing_heartbeat,
            heartbeat_interval_seconds=0.1,
        )

    assert isinstance(raised.value.cause, RuntimeError)
    assert "transient database error" in str(raised.value)
    assert boundary.has_live_child is False


class _AlwaysWritesMarkerFirst:
    family = "always-writes-marker-first"

    def __init__(self, marker: Path) -> None:
        self._marker = marker

    def run(self, context: MethodContext) -> MethodResult:
        assert context.emit_external_event is not None
        self._marker.write_text("about to emit")
        event = CodexEvent(
            sequence=0,
            event_type="turn.started",
            payload={"type": "turn.started"},
            raw_sha256="b" * 64,
        )
        context.emit_external_event(event)
        raise AssertionError("unreachable: the failing callback must stop the child first")


# ---------------------------------------------------------------------------
# Cross-process-boundary coverage: CodexTurnTimedOut must survive pickling
# ---------------------------------------------------------------------------


class _CodexHangMethod:
    """A `SolverMethod` that drives a real `CodexClient` into its own timeout.

    Runs inside a real forked `ProcessExecutionBoundary` child, so the
    `CodexTurnTimedOut` the client raises has to cross a real
    `multiprocessing.Connection` (pickled by the child, unpickled by the
    parent) to reach `ExecutionFailed.cause` -- this is the only way to
    actually exercise that boundary rather than just constructing and
    raising the exception in-process.
    """

    family = "codex-hang"

    def __init__(self, codex_binary: Path, repo_root: Path, worktree_root: Path) -> None:
        self._codex_binary = codex_binary
        self._repo_root = repo_root
        self._worktree_root = worktree_root

    def run(self, context: MethodContext) -> MethodResult:
        base_sha = _git("rev-parse", "HEAD", cwd=self._repo_root).stdout.strip()
        reservation = CodexTurnReservation(
            id=uuid4(),
            experiment_id=uuid4(),
            budget_day=datetime.now(UTC).date(),
            role=CodexModelRole.TERRA,
            model="gpt-5.6-terra",
            deadline_seconds=1800,
            created_at=datetime.now(UTC),
        )
        launch_policy = CodexLaunchPolicy(
            codex_binary=self._codex_binary, codex_home=self._worktree_root / "codex-home"
        )
        worktree_manager = CodexWorktreeManager(
            repo_root=self._repo_root, worktree_root=self._worktree_root
        )
        client = CodexClient(
            launch_policy,
            worktree_manager,
            environment={"PATH": os.environ.get("PATH", ""), "TMPDIR": tempfile.gettempdir()},
            timeout_seconds=1.0,
        )
        request: CodexRequest[ProofSketch] = CodexRequest(
            reservation=reservation,
            prompt="hang",
            base_sha=base_sha,
            response_schema=ProofSketch,
        )
        assert context.emit_external_event is not None
        client.execute(request, context.emit_external_event)
        raise AssertionError("unreachable: the client must time out before returning")


def test_client_timeout_propagates_through_the_forked_boundary(tmp_path: Path) -> None:
    repo_root = tmp_path / "source-repo"
    _init_repo(repo_root)
    worktree_root = tmp_path / "codex-worktrees"
    fake_codex = tmp_path / "fake_codex.py"
    fake_codex.write_text(_FAKE_CODEX_SOURCE)
    fake_codex.chmod(0o700)

    boundary = ProcessExecutionBoundary()
    context = MethodContext(problem=_codex_test_problem(), seed=1, config={})

    with pytest.raises(ExecutionFailed) as raised:
        boundary.run(
            _CodexHangMethod(fake_codex, repo_root, worktree_root),
            context,
            # Generous relative to the client's own 1.0s internal deadline:
            # this outer bound exists only as a backstop and must never be
            # the one that actually fires.
            timeout_seconds=15.0,
        )

    assert isinstance(raised.value.cause, CodexTurnTimedOut)
    assert raised.value.cause.dispatched is True
    assert boundary.has_live_child is False


# ---------------------------------------------------------------------------
# C3: the experiment lease must survive a turn longer than lease_seconds,
# and a worker that loses the lease mid-turn must abort rather than
# complete and discard.
# ---------------------------------------------------------------------------


def test_heartbeat_keeps_the_lease_alive_across_a_turn_longer_than_lease_seconds(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    experiment = _enqueue_codex(repository, mode="slow_success")
    worker = _worker(repository, tmp_path, fake_codex, lease_seconds=3)

    # The fake CLI's mode="slow_success" sleeps 5s -- well past lease_seconds
    # =3 -- so `commit_worker_result`'s own lease-expiry check
    # (`lease_expires_at <= completed_at`) would reject the completion with
    # LeaseConflictError purely on elapsed time, in this single-worker test,
    # unless the lease was actively renewed (heartbeat_interval_seconds =
    # min(60, 3/3) = 1.0s) throughout the run.
    assert worker.run_once("worker-1")

    assert repository.get_experiment(experiment.id).status is ExperimentStatus.SUCCEEDED
    assert repository.count_events("experiment.heartbeat") >= 1


def test_lost_lease_aborts_the_turn_instead_of_completing_and_discarding(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    experiment = _enqueue_codex(repository, mode="slow_success")
    worker = _worker(repository, tmp_path, fake_codex, lease_seconds=3)

    def _steal_soon() -> None:
        time.sleep(1.5)
        _steal_lease(repository, experiment.id, "thief-worker")

    thief = threading.Thread(target=_steal_soon, daemon=True)
    thief.start()
    try:
        # Aborting is still "handled work" from run_once's perspective (the
        # experiment was claimed and dealt with, even though this worker
        # ultimately walked away from it), so this returns True, not False.
        assert worker.run_once("worker-1")
    finally:
        thief.join(timeout=5)

    # The turn must never have been completed by worker-1 after losing the
    # lease: the row is exactly what the "thief" left it as (still leased,
    # by the thief, not succeeded with worker-1's result) -- proving
    # worker-1 aborted instead of finishing the turn and racing
    # commit_worker_result against the new owner.
    status, lease_owner = _experiment_lease(repository, experiment.id)
    assert status == ExperimentStatus.LEASED.value
    assert lease_owner == "thief-worker"
    turn_status, _ = _codex_turn_row(repository, experiment.id)
    assert turn_status == "ambiguous"
