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
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from mathloop.artifacts import ArtifactStore
from mathloop.codex.client import CodexClient, CodexRequest, CodexTurnTimedOut
from mathloop.codex.domain import CodexModelRole, CodexTurnReservation
from mathloop.codex.events import CodexEvent
from mathloop.codex.launch import CodexLaunchPolicy
from mathloop.codex.worktrees import CodexWorktreeManager
from mathloop.config import Settings
from mathloop.domain import Experiment, ExperimentStatus, MethodVersion, Problem, ProblemStatus
from mathloop.methods.base import MethodContext, MethodRegistry, MethodResult
from mathloop.methods.proof_sketch import ProofSketch
from mathloop.provenance import component_provenance
from mathloop.storage.repository import Repository
from mathloop.worker import ExecutionFailed, ExecutionOutcome, ProcessExecutionBoundary, Worker

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
        worktree_manager = CodexWorktreeManager(
            repo_root=self._repo_root, worktree_root=self._worktree_root
        )
        client = CodexClient(
            launch_policy,
            worktree_manager,
            environment={"PATH": os.environ.get("PATH", ""), "TMPDIR": tempfile.gettempdir()},
            timeout_seconds=30.0,
        )
        request: CodexRequest[ProofSketch] = CodexRequest(
            reservation=reservation,
            prompt="success",
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


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_root=tmp_path / "artifacts",
        incoming_root=tmp_path / "incoming",
        max_experiment_seconds=2,
        lease_seconds=30,
    )


def _worker(repository: Repository, tmp_path: Path, fake_codex: Path) -> Worker:
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
        _settings(tmp_path),
    )


@pytest.fixture
def fake_codex(tmp_path: Path) -> Path:
    script = tmp_path / "fake_codex.py"
    script.write_text(_FAKE_CODEX_SOURCE)
    script.chmod(0o700)
    return script


def _codex_turn_row(repository: Repository, experiment_id: UUID) -> tuple[str, str | None]:
    with repository.database.transaction() as connection:
        row = connection.execute(
            "SELECT status, failure_kind FROM codex_turns WHERE experiment_id = %(id)s",
            {"id": experiment_id},
        ).fetchone()
    assert row is not None
    return row[0], row[1]


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
