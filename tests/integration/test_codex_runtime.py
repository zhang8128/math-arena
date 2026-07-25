"""End-to-end coverage of Task 7's runtime composition and operator commands.

Every scenario here drives real machinery: a real Postgres `repository`, a
real (small, temporary) git repository as the Codex `codex_repo_root`, and a
real subprocess -- but never the real `codex` CLI. The fake script below
stands in for it: `codex init`'s version/login checks invoke it directly (as
`cli.py` does for the real binary), and a real `CodexClient` invokes it via
`codex exec` for the scenarios that actually run a turn. Nothing here ever
shells out to the genuine Codex CLI or requires a real ChatGPT login, even
though a real `codex` binary happens to be installed on this machine.
"""

import json
import os
import signal
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from typer.testing import CliRunner

import mathloop.cli as cli_module
from mathloop.artifacts import ArtifactStore
from mathloop.cli import app
from mathloop.codex.domain import CodexModelRole, CodexPolicy, CodexTurnStatus
from mathloop.codex.supervisor import CodexSupervisor
from mathloop.config import Settings
from mathloop.domain import Experiment, ExperimentStatus, Problem, ProblemStatus
from mathloop.runtime import build_runtime
from mathloop.storage.repository import Repository

# ---------------------------------------------------------------------------
# Fake Codex CLI: never the real binary, never a real ChatGPT login.
# ---------------------------------------------------------------------------

_FAKE_CODEX_SOURCE = '''\
#!/usr/bin/env python3
import json
import os
import sys
import time


def _emit(payload):
    sys.stdout.write(json.dumps(payload) + "\\n")
    sys.stdout.flush()


def _codex_home():
    return os.environ.get("CODEX_HOME", "")


def _is_authenticated():
    # Mirrors the real CLI's own requirement: a genuine `codex` binary
    # refuses to run at all without an authenticated CODEX_HOME. A fake that
    # skipped this check would conceal exactly the production defect (an
    # unseeded or misconfigured CODEX_HOME) tests exist to catch -- both
    # `login status` and a real turn attempt consult the SAME marker file, so
    # a test can prove they agree.
    home = _codex_home()
    return bool(home) and os.path.exists(os.path.join(home, "auth.json"))


def _turn_sleep_seconds():
    # CODEX_HOME is the only directory this fake CLI is guaranteed to have
    # (CodexLaunchPolicy.environment() always sets it, regardless of the
    # allowlisted environment it otherwise forwards) -- so a test that wants
    # to hold a turn "in flight" for a controlled duration drops a plain text
    # file there rather than an environment variable, since arbitrary
    # env vars (e.g. a hypothetical FAKE_CODEX_TURN_SLEEP_SECONDS) are NOT
    # forwarded to the real launch environment at all.
    home = _codex_home()
    if not home:
        return 0.0
    marker = os.path.join(home, "turn-sleep-seconds.txt")
    if not os.path.exists(marker):
        return 0.0
    with open(marker) as handle:
        content = handle.read().strip()
    return float(content) if content else 0.0


def main():
    argv = sys.argv[1:]
    if argv[:1] == ["--version"]:
        version = os.environ.get("FAKE_CODEX_VERSION", "0.145.0")
        sys.stdout.write("codex-cli " + version + "\\n")
        return 0
    if argv[:2] == ["login", "status"]:
        if _is_authenticated():
            sys.stdout.write("Logged in with ChatGPT\\n")
            return 0
        sys.stdout.write("Not logged in.\\n")
        return 1

    # Anything else is a real `codex exec` turn.
    if not _is_authenticated():
        sys.stderr.write("error: not logged in; run `codex login`\\n")
        return 1

    codex_home = _codex_home()
    os.makedirs(codex_home, exist_ok=True)
    with open(os.path.join(codex_home, "invoked-exec.marker"), "a") as handle:
        handle.write("invoked\\n")

    worktree = None
    if "--cd" in argv:
        worktree = argv[argv.index("--cd") + 1]

    sleep_seconds = _turn_sleep_seconds()
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)

    # NOTE: the real, installed Codex CLI (0.145.0) has been confirmed by
    # direct binary inspection to NOT reliably include `cli_version` here --
    # `CodexClient` falls back to a separate `codex --version` query when
    # this event omits it. This fake keeps emitting the convenient shape
    # because this file's scenarios are about runtime/operator-command
    # wiring, not the CLI-version fallback itself, which has its own
    # dedicated regression coverage in `tests/unit/test_codex_client.py`
    # and `tests/e2e/test_codex_canary.py`. Do not treat this field's
    # presence here as evidence it is guaranteed present on the real CLI.
    _emit({"type": "thread.started", "thread_id": "thread-fake", "cli_version": "0.145.0-test"})
    _emit({"type": "turn.started"})
    if worktree is not None:
        with open(os.path.join(worktree, "NOTES.md"), "w") as handle:
            handle.write("codex was here\\n")
    _emit(
        {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": json.dumps(
                    {
                        "strategy": "induction",
                        "lemmas": ["base case holds"],
                        "risks": ["off-by-one in the inductive step"],
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
    # Written only after the full turn genuinely finished -- a worker killed
    # mid-flight (mid-sleep, or anywhere before this line) never reaches it.
    with open(os.path.join(codex_home, "exec-completed.marker"), "a") as handle:
        handle.write("completed\\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


@pytest.fixture
def fake_codex(tmp_path: Path) -> Path:
    script = tmp_path / "fake_codex.py"
    script.write_text(_FAKE_CODEX_SOURCE)
    script.chmod(0o700)
    return script


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    if (repo / ".git").exists():
        # `_settings` may be called more than once against the same tmp_path
        # (e.g. building two supervisors to simulate a restart); a repo it
        # already initialized is left alone rather than re-committed into a
        # clean working tree, which `git commit` rejects.
        return
    repo.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "codex-runtime-test@example.com", cwd=repo)
    _git("config", "user.name", "Codex Runtime Test", cwd=repo)
    (repo / "README.md").write_text("seed content\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "seed", cwd=repo)


def _codex_home_path(tmp_path: Path) -> Path:
    return tmp_path / "codex-home"


def _seed_authenticated_codex_home(codex_home: Path) -> None:
    """Seed a fake, already-authenticated Codex CLI store for tests.

    Mirrors what a real operator's `~/.codex/auth.json` provides: real
    turns and the fake CLI's own `login status` handler both key off this
    file's presence (see `_FAKE_CODEX_SOURCE`), never an environment
    variable, so this is the one thing that must exist for a test's turns to
    actually run to completion rather than fail unauthenticated.
    """
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "auth.json").write_text('{"fake": "credential"}\n')


def _settings(
    repository: Repository, tmp_path: Path, fake_codex: Path, **overrides: object
) -> Settings:
    repo_root = tmp_path / "source-repo"
    _init_repo(repo_root)
    codex_home = _codex_home_path(tmp_path)
    _seed_authenticated_codex_home(codex_home)
    fields: dict[str, object] = {
        # Without this, `Settings.database_url` falls back to its own
        # default (a local dev Postgres on 55432), not this test's real
        # testcontainers instance. `build_runtime`'s own `repository`
        # parameter shields the CALLING process from that mismatch, but a
        # forked multi-process worker (`_worker_process_main`) reconnects
        # from `settings.database_url` alone -- so a Settings object that
        # never set this would send that worker to a DIFFERENT database
        # entirely, silently, with no exception (it just finds nothing this
        # test scheduled and nothing to do).
        "database_url": repository.database.database_url,
        "artifact_root": tmp_path / "artifacts",
        "incoming_root": tmp_path / "incoming",
        "codex_cli_path": fake_codex,
        "codex_repo_root": repo_root,
        "codex_worktree_root": tmp_path / "codex-worktrees",
        "codex_home": codex_home,
        "codex_turn_timeout_seconds": 60,
    }
    fields.update(overrides)
    return Settings(**fields)  # type: ignore[arg-type]


def _enqueue_experiment(repository: Repository) -> UUID:
    experiment = Experiment(
        id=uuid4(),
        problem_id=uuid4(),
        method_id=uuid4(),
        lane="codex",
        config={},
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(experiment, f"experiment:{experiment.id}")
    return experiment.id


def _ingest_codex_eligible_problem(repository: Repository, *, cohort: str = "development") -> None:
    problem = Problem(
        id=uuid4(),
        source_id=f"test/{uuid4()}",
        source_uri="local://codex-runtime",
        source_hash=uuid4().hex * 2,
        statement="test",
        normalized_statement="test",
        domain="testing",
        features={},
        checker={"kind": "unsupported"},
        status=ProblemStatus.ELIGIBLE,
        cohort=cohort,
        version=1,
        created_at=datetime.now(UTC),
    )
    repository.add_problem(problem, f"problem:{problem.id}")


# ---------------------------------------------------------------------------
# Mutual exclusion: api_enabled and codex_enabled
# ---------------------------------------------------------------------------


def test_runtime_rejects_api_and_codex_together(repository: Repository, tmp_path: Path) -> None:
    artifacts = ArtifactStore(tmp_path / "artifacts")
    settings = Settings(
        artifact_root=tmp_path / "artifacts",
        incoming_root=tmp_path / "incoming",
    )
    with pytest.raises(ValueError, match="mutually exclusive"):
        build_runtime(
            repository,
            artifacts,
            api_enabled=True,
            codex_enabled=True,
            settings=settings,
        )


def test_runtime_rejects_api_and_codex_together_via_direct_construction(
    repository: Repository, tmp_path: Path
) -> None:
    """`build_runtime`'s guard is not the only thing that must hold.

    `Runtime` is a plain, unfrozen dataclass, so nothing stops a caller from
    constructing one directly with both flags set, bypassing `build_runtime`
    entirely. The guarantee that matters -- at most one external provider is
    ever live -- must hold at `register_baseline_methods` itself, regardless
    of how the `Runtime` came to exist.
    """
    artifacts = ArtifactStore(tmp_path / "artifacts")
    settings = Settings(artifact_root=tmp_path / "artifacts", incoming_root=tmp_path / "incoming")
    runtime = build_runtime(repository, artifacts, api_enabled=False, settings=settings)
    runtime.api_enabled = True
    runtime.codex_enabled = True

    with pytest.raises(ValueError, match="mutually exclusive"):
        runtime.register_baseline_methods()


def test_register_baseline_methods_rejects_codex_registered_then_api(
    repository: Repository, tmp_path: Path, fake_codex: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reverse order Task 6's review flagged as unguarded.

    `register_codex_proof_strategy` already refuses to register alongside an
    existing "proof_sketch" -- the order this test exercises is the one that
    was previously unguarded: Codex registers into a registry first, and the
    OpenAI API path must refuse to register into that *same* registry
    afterward.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    settings = _settings(repository, tmp_path, fake_codex)
    codex_runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    api_runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=True,
        codex_enabled=False, settings=settings,
    )
    shared_registry = codex_runtime.methods
    api_runtime.methods = shared_registry

    codex_runtime.register_baseline_methods()
    assert shared_registry.contains("codex_proof_strategy")

    with pytest.raises(ValueError, match="cannot both be registered"):
        api_runtime.register_baseline_methods()


def test_register_baseline_methods_rejects_api_registered_then_codex(
    repository: Repository, tmp_path: Path, fake_codex: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The order Task 6 already covered, re-verified in this shared-registry shape."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    settings = _settings(repository, tmp_path, fake_codex)
    api_runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=True,
        codex_enabled=False, settings=settings,
    )
    codex_runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    shared_registry = api_runtime.methods
    codex_runtime.methods = shared_registry

    api_runtime.register_baseline_methods()
    assert shared_registry.contains("proof_sketch")

    with pytest.raises(ValueError, match="cannot both be registered"):
        codex_runtime.register_baseline_methods()


# ---------------------------------------------------------------------------
# `codex start`
# ---------------------------------------------------------------------------


def _codex_env(monkeypatch: pytest.MonkeyPatch, repository: Repository, tmp_path: Path) -> None:
    (tmp_path / "incoming").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MATHLOOP_DATABASE_URL", repository.database.database_url)
    monkeypatch.setenv("MATHLOOP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("MATHLOOP_INCOMING_ROOT", str(tmp_path / "incoming"))
    monkeypatch.setenv("MATHLOOP_CODEX_WORKTREE_ROOT", str(tmp_path / "codex-worktrees"))
    # Pinned even though nothing in this scenario ever reaches a real turn
    # (see below): a test's configuration surface should never include the
    # operator's real credential store (`~/.codex`, `Settings.codex_home`'s
    # default) by omission.
    monkeypatch.setenv("MATHLOOP_CODEX_HOME", str(tmp_path / "codex-home"))
    # Never the real binary, even though this scenario never actually reaches
    # a codex exec invocation (the incoming root is empty, so nothing is ever
    # scheduled): a placeholder path fails loudly instead of silently
    # shelling out if that ever stops being true.
    monkeypatch.setenv("MATHLOOP_CODEX_CLI_PATH", str(tmp_path / "codex-not-installed"))


def test_codex_start_runs_bounded_turns_and_reports_usage(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
    tmp_path: Path,
) -> None:
    _codex_env(monkeypatch, repository, tmp_path)

    result = cli_runner.invoke(app, ["codex", "start", "--turns", "6", "--workers", "4"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["requested_turns"] == 6
    assert payload["usage"]["daily_limit"] == 100


def test_codex_start_never_exceeds_the_durable_daily_cap_even_when_turns_asks_for_more(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    settings = _settings(
        repository,
        tmp_path,
        fake_codex,
        codex_daily_turn_limit=2,
        codex_luna_turn_limit=2,
        codex_terra_turn_limit=0,
        codex_sol_turn_limit=0,
        codex_reserved_sol_turns=0,
    )
    for _ in range(4):
        _ingest_codex_eligible_problem(repository)
    runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    supervisor = CodexSupervisor(runtime)

    payload = supervisor.start(max_turns=10, workers=1)

    assert payload["usage"]["daily_limit"] == 2
    assert payload["usage"]["daily_reserved"] == 2
    now = datetime.now(UTC)
    assert repository.codex_usage_status(now).daily_reserved == 2


def test_codex_start_re_narrows_each_cycle_to_the_remaining_turn_budget(
    repository: Repository, tmp_path: Path, fake_codex: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task 7 review I1: `worker_iterations` must be re-narrowed to the
    REMAINING budget every cycle, not just once before the loop -- otherwise
    a first cycle that reserves fewer than `max_turns` lets a later cycle
    run a full-size batch again, and `start(6)` could durably over-reserve
    toward roughly double what was asked for.
    """
    settings = _settings(repository, tmp_path, fake_codex)
    runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    supervisor = CodexSupervisor(runtime)
    observed_worker_iterations: list[int] = []
    reservations_per_cycle = iter([2, 0])  # cycle 1 reserves 2 of the 6 requested

    def fake_cycle() -> dict[str, object]:
        observed_worker_iterations.append(runtime.loop.worker_iterations)
        count = next(reservations_per_cycle, 0)
        for _ in range(count):
            repository.record_metric(
                "codex_turn.reserved", {}, idempotency_key=f"fake-reservation:{uuid4()}"
            )
        return {"scheduled": list(range(count)), "worker_runs": count}

    monkeypatch.setattr(runtime.loop, "cycle", fake_cycle)

    payload = supervisor.start(max_turns=6, workers=1)

    assert observed_worker_iterations[0] == 6  # first cycle: the full requested budget
    assert observed_worker_iterations[1] == 4  # second cycle: 6 requested - 2 reserved = 4 left
    assert payload["started_turns"] == 2


def test_codex_start_does_not_permanently_ratchet_a_later_calls_batch_size_down(
    repository: Repository, tmp_path: Path, fake_codex: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task 7 review I1: a small `start(1)` must not permanently shrink a
    later, larger `start(6)` on the same supervisor -- the per-cycle
    narrowing must always narrow from a pristine baseline, never from
    whatever a prior call already left `runtime.loop` holding.
    """
    settings = _settings(repository, tmp_path, fake_codex)
    runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    supervisor = CodexSupervisor(runtime)

    def fake_cycle_noop() -> dict[str, object]:
        return {"scheduled": [], "worker_runs": 0}

    monkeypatch.setattr(runtime.loop, "cycle", fake_cycle_noop)
    supervisor.start(max_turns=1, workers=1)
    assert runtime.loop.worker_iterations == 1  # shrunk by the first call

    observed: list[int] = []

    def fake_cycle_record() -> dict[str, object]:
        observed.append(runtime.loop.worker_iterations)
        return {"scheduled": [], "worker_runs": 0}

    monkeypatch.setattr(runtime.loop, "cycle", fake_cycle_record)
    supervisor.start(max_turns=6, workers=1)

    assert observed[0] == 6  # not permanently capped at 1 by the earlier call


def test_codex_start_clamps_workers_to_the_concurrent_turn_limit(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    """Task 7 review I3: `--workers` has no upper bound of its own, but
    `reserve_codex_turn`'s concurrency cap denial is currently terminal for
    the experiment it was attempted against -- so asking for more workers
    than the concurrency policy allows would permanently fail real
    problem/method pairs for no reason. Clamping here means this call never
    itself creates that self-inflicted over-subscription.
    """
    settings = _settings(repository, tmp_path, fake_codex, codex_concurrent_turn_limit=2)
    runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    supervisor = CodexSupervisor(runtime)

    payload = supervisor.start(max_turns=1, workers=8)

    assert payload["workers"] == 2
    assert runtime.loop.worker_processes == 2


def test_codex_turn_fails_when_codex_home_is_unauthenticated(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    """Task 7 review C2: an unseeded/misconfigured CODEX_HOME must make a
    real turn fail loudly, not run silently unauthenticated and consume
    real, non-refundable daily quota for zero output. Also proves the fake
    CLI itself now enforces this -- a fake that always succeeded regardless
    of CODEX_HOME would conceal the production defect this test exists to
    catch.
    """
    settings = _settings(
        repository, tmp_path, fake_codex, codex_home=tmp_path / "unauthenticated-codex-home"
    )
    _ingest_codex_eligible_problem(repository)
    runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    supervisor = CodexSupervisor(runtime)

    supervisor.start(max_turns=1, workers=1)

    with repository.database.transaction() as connection:
        rows = connection.execute("SELECT status FROM codex_turns").fetchall()
    assert rows  # a reservation was durably made and consumed the day's slot
    assert all(status != "completed" for (status,) in rows)


# ---------------------------------------------------------------------------
# Graceful multi-process SIGINT/SIGTERM: must drain, never hard-kill a turn
# ---------------------------------------------------------------------------


def test_codex_start_sigint_lets_an_in_flight_multi_worker_turn_finish_not_kill_it(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    """Task 7 review C1 (Critical).

    On the multi-process path (`--workers > 1`), a cooperative stop request
    must never SIGTERM a Codex turn's own process group directly -- only the
    forked worker process itself, which then finishes its *current* turn
    before exiting on its own. The fake CLI sleeps mid-turn; a completion
    marker written only after the full turn genuinely finishes proves
    whether it was allowed to finish or was killed mid-flight. Before the
    fix, `_run_workers`'s stop-requested cascade called
    `_terminate_supervised_worker` immediately, which SIGTERMs every
    registered execution descendant -- including the live `codex exec`
    process group -- so this same scenario would have killed the sleeping
    fake CLI well before it could write its completion marker.
    """
    settings = _settings(repository, tmp_path, fake_codex, codex_concurrent_turn_limit=4)
    (settings.codex_home / "turn-sleep-seconds.txt").write_text("2.0")
    for _ in range(6):
        _ingest_codex_eligible_problem(repository)
    runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    # Drives `_run_workers` directly rather than through `CodexSupervisor
    # .start()`'s full `cycle()` (which also runs scheduling, ingestion, and
    # evolution/holdout-routing every cycle): this test is about ONE specific
    # property of the multi-process worker supervision loop, and scheduling
    # once, directly, up front makes exactly how many codex experiments end
    # up in flight deterministic and inspectable, independent of the
    # portfolio policy's lane split or the evolution step's own holdout
    # routing (which can itself allocate Codex work some cycles).
    runtime.register_baseline_methods()
    scheduled = runtime.schedule(10, seed=1)
    assert scheduled
    runtime.loop.worker_iterations = 6
    runtime.loop.worker_processes = 2

    def run_workers() -> None:
        runtime.loop._run_workers(cycle_number=1)

    runner_thread = threading.Thread(target=run_workers, daemon=True)
    runner_thread.start()

    invoked_marker = settings.codex_home / "invoked-exec.marker"
    poll_deadline = time.monotonic() + 15.0
    while time.monotonic() < poll_deadline:
        if invoked_marker.exists() and invoked_marker.read_text().count("invoked") >= 1:
            break
        time.sleep(0.02)
    else:
        pytest.fail("fake codex exec was never invoked within the timeout")

    # A turn is now genuinely in flight (sleeping inside the fake CLI). This
    # is the exact moment an operator's Ctrl-C would land in production.
    runtime.loop.request_stop()
    runner_thread.join(timeout=20.0)
    assert not runner_thread.is_alive()

    completed_marker = settings.codex_home / "exec-completed.marker"
    assert completed_marker.exists()
    with repository.database.transaction() as connection:
        rows = connection.execute(
            "SELECT status FROM codex_turns ORDER BY created_at"
        ).fetchall()
    assert rows
    assert all(status == "completed" for (status,) in rows)


# ---------------------------------------------------------------------------
# `codex status` / `pause` / `resume`
# ---------------------------------------------------------------------------


def _supervisor(repository: Repository, tmp_path: Path, fake_codex: Path) -> CodexSupervisor:
    settings = _settings(repository, tmp_path, fake_codex)
    runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    return CodexSupervisor(runtime)


def test_codex_status_never_mutates_the_ledger(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    supervisor = _supervisor(repository, tmp_path, fake_codex)
    before = repository.count_events("runtime.cycle_metrics")  # any event type, as a canary
    total_before = _total_event_count(repository)

    supervisor.status()
    supervisor.status()

    total_after = _total_event_count(repository)
    assert total_after == total_before
    assert before == repository.count_events("runtime.cycle_metrics")


def _total_event_count(repository: Repository) -> int:
    with repository.database.transaction() as connection:
        row = connection.execute("SELECT count(*) FROM events").fetchone()
    assert row is not None
    return int(row[0])


def test_codex_pause_resume_round_trip_is_idempotent(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    supervisor = _supervisor(repository, tmp_path, fake_codex)

    assert supervisor.status()["paused"] is False
    first_pause = supervisor.pause()
    assert first_pause["paused"] is True
    second_pause = supervisor.pause()  # idempotent: already paused
    assert second_pause["paused"] is True
    assert repository.count_events("codex_supervisor.paused") == 1

    first_resume = supervisor.resume()
    assert first_resume["paused"] is False
    second_resume = supervisor.resume()  # idempotent: already resumed
    assert second_resume["paused"] is False
    assert repository.count_events("codex_supervisor.resumed") == 1


def test_codex_pause_survives_a_supervisor_restart(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    """A pause must be a durable event/projection, not an in-memory flag.

    Two independently constructed `CodexSupervisor`s (standing in for two
    separate process lifetimes -- e.g. a paused `codex start`, then a
    restarted process later checking `codex status`) must agree, because
    both derive the answer from the same durable event counts. Nothing here
    ever calls `pause()` on the second supervisor -- if pause were held only
    in memory, this is exactly the property a restart would break.
    """
    supervisor_before_restart = _supervisor(repository, tmp_path, fake_codex)
    supervisor_before_restart.pause()

    supervisor_after_restart = _supervisor(repository, tmp_path, fake_codex)

    assert supervisor_after_restart.is_paused() is True
    assert supervisor_after_restart.status()["paused"] is True


def test_codex_start_refuses_to_run_while_paused(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    for _ in range(2):
        _ingest_codex_eligible_problem(repository)
    supervisor = _supervisor(repository, tmp_path, fake_codex)
    supervisor.pause()

    payload = supervisor.start(max_turns=5, workers=1)

    assert payload["paused"] is True
    assert payload["started_turns"] == 0
    assert payload["cycles_run"] == 0
    now = datetime.now(UTC)
    assert repository.codex_usage_status(now).daily_reserved == 0


# ---------------------------------------------------------------------------
# `codex drain`
# ---------------------------------------------------------------------------


def test_codex_drain_waits_for_an_active_lease_to_clear_then_returns(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    settings = _settings(repository, tmp_path, fake_codex)
    experiment_id = _enqueue_experiment(repository)
    reservation = repository.reserve_codex_turn(
        experiment_id, "worker-1", CodexModelRole.LUNA, "gpt-5.6-luna",
        _policy_from(settings), datetime.now(UTC),
    )
    assert reservation is not None
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    assert repository.codex_usage_status(datetime.now(UTC)).active_leases == 1

    def clear_the_lease_shortly() -> None:
        time.sleep(0.2)
        repository.fail_codex_turn(
            reservation.id,
            status=CodexTurnStatus.FAILED,
            failure_kind="test",
            failure_message="synthetic completion for the drain test",
        )

    clearer = threading.Thread(target=clear_the_lease_shortly)
    clearer.start()
    runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    supervisor = CodexSupervisor(runtime)
    started_at = time.monotonic()

    payload = supervisor.drain(grace_seconds=5.0, poll_seconds=0.02)
    clearer.join()

    elapsed = time.monotonic() - started_at
    assert payload["drained"] is True
    assert payload["paused"] is True
    assert elapsed < 5.0  # returned once the lease cleared, not after the full grace period


def test_codex_drain_reports_not_drained_when_the_grace_period_expires(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    settings = _settings(repository, tmp_path, fake_codex)
    experiment_id = _enqueue_experiment(repository)
    reservation = repository.reserve_codex_turn(
        experiment_id, "worker-1", CodexModelRole.LUNA, "gpt-5.6-luna",
        _policy_from(settings), datetime.now(UTC),
    )
    assert reservation is not None
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )
    supervisor = CodexSupervisor(runtime)

    payload = supervisor.drain(grace_seconds=0.1, poll_seconds=0.02)

    assert payload["drained"] is False
    assert payload["paused"] is True


def test_codex_status_names_every_turn_that_is_holding_a_concurrency_slot(
    repository: Repository, tmp_path: Path, fake_codex: Path
) -> None:
    """A nonzero `active_leases` must never be reported without naming the rows.

    `active_worktree_ids` only lists `dispatched`/`running` turns, which is
    correct for its own question (which turns own an on-disk worktree) but
    leaves an operator staring at `"active_leases": N` beside
    `"active_worktree_ids": []` whenever the blocking rows are unexpired
    `reserved` or `ambiguous` ones -- the exact shape a lane wedged by
    ambiguous settlements produces, and the one place an operator would look
    to diagnose it. `active_lease_turn_ids` answers that question directly and
    is derived from the very same predicate the cap is enforced against.
    """
    settings = _settings(repository, tmp_path, fake_codex)
    experiment_id = _enqueue_experiment(repository)
    reservation = repository.reserve_codex_turn(
        experiment_id, "worker-1", CodexModelRole.LUNA, "gpt-5.6-luna",
        _policy_from(settings), datetime.now(UTC),
    )
    assert reservation is not None
    repository.mark_codex_turn_dispatched(reservation.id, "worker-1")
    repository.fail_codex_turn(
        reservation.id,
        status=CodexTurnStatus.AMBIGUOUS,
        failure_kind="external",
        failure_message="codex exec exited nonzero after dispatch",
    )
    runtime = build_runtime(
        repository, ArtifactStore(settings.artifact_root), api_enabled=False,
        codex_enabled=True, settings=settings,
    )

    payload = CodexSupervisor(runtime).status()

    usage = payload["usage"]
    assert isinstance(usage, dict)
    assert usage["active_leases"] == 1
    assert payload["active_worktree_ids"] == [], "a settled turn no longer owns a worktree"
    assert payload["active_lease_turn_ids"] == [str(reservation.id)], (
        "the row actually holding the slot is visible in `codex status`"
    )
    assert len(payload["active_lease_turn_ids"]) == usage["active_leases"]  # type: ignore[arg-type]


def _policy_from(settings: Settings) -> CodexPolicy:
    return CodexPolicy(
        daily_turn_limit=settings.codex_daily_turn_limit,
        concurrent_turn_limit=settings.codex_concurrent_turn_limit,
        turn_timeout_seconds=settings.codex_turn_timeout_seconds,
        model_turn_limits={
            "luna": settings.codex_luna_turn_limit,
            "terra": settings.codex_terra_turn_limit,
            "sol": settings.codex_sol_turn_limit,
        },
        reserved_sol_turns=settings.codex_reserved_sol_turns,
    )


# ---------------------------------------------------------------------------
# `codex init`
# ---------------------------------------------------------------------------


def _init_env(monkeypatch: pytest.MonkeyPatch, repository: Repository, tmp_path: Path) -> Path:
    repo_root = tmp_path / "codex-repo"
    _init_repo(repo_root)
    codex_home = _codex_home_path(tmp_path)
    _seed_authenticated_codex_home(codex_home)
    monkeypatch.setenv("MATHLOOP_DATABASE_URL", repository.database.database_url)
    monkeypatch.setenv("MATHLOOP_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("MATHLOOP_INCOMING_ROOT", str(tmp_path / "incoming"))
    monkeypatch.setenv("MATHLOOP_CODEX_REPO_ROOT", str(repo_root))
    monkeypatch.setenv("MATHLOOP_CODEX_WORKTREE_ROOT", str(tmp_path / "codex-worktrees"))
    monkeypatch.setenv("MATHLOOP_CODEX_HOME", str(codex_home))
    return repo_root


def test_codex_init_reports_success_when_every_check_passes(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
    tmp_path: Path,
    fake_codex: Path,
) -> None:
    _init_env(monkeypatch, repository, tmp_path)
    monkeypatch.setenv("MATHLOOP_CODEX_CLI_PATH", str(fake_codex))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.setattr(cli_module, "_sage_image_available", lambda: True)

    result = cli_runner.invoke(app, ["codex", "init"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert all(check["ok"] is True for check in payload["checks"].values())


def test_codex_init_fails_when_login_is_absent(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
    tmp_path: Path,
    fake_codex: Path,
) -> None:
    _init_env(monkeypatch, repository, tmp_path)
    monkeypatch.setenv("MATHLOOP_CODEX_CLI_PATH", str(fake_codex))
    # Point at a directory with no seeded `auth.json` -- the fake CLI (like
    # the real one) treats that as "not logged in", exactly the same marker
    # a real turn attempt also consults.
    monkeypatch.setenv("MATHLOOP_CODEX_HOME", str(tmp_path / "unauthenticated-codex-home"))
    monkeypatch.setattr(cli_module, "_sage_image_available", lambda: True)

    result = cli_runner.invoke(app, ["codex", "init"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["checks"]["codex_login"]["ok"] is False
    # The failure is isolated to the login check -- everything else still ran
    # and reported its own, independent result.
    assert payload["checks"]["codex_cli_version"]["ok"] is True


def test_codex_init_login_check_uses_the_configured_codex_home_not_the_ambient_one(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
    tmp_path: Path,
    fake_codex: Path,
) -> None:
    """Task 7 review C2: the false-positive this preflight most needs to avoid.

    `CodexLaunchPolicy.environment()` always overwrites `CODEX_HOME` with
    `settings.codex_home` for a real turn -- so the login probe must
    validate THAT value, not whatever this process happens to have
    inherited. Here the ambient `CODEX_HOME` (this process's own, inherited
    environment variable) is authenticated, but `settings.codex_home` (via
    `MATHLOOP_CODEX_HOME`) is not; if the probe used the ambient value
    instead, it would report success even though real turns would still run
    unauthenticated.
    """
    _init_env(monkeypatch, repository, tmp_path)
    monkeypatch.setenv("MATHLOOP_CODEX_CLI_PATH", str(fake_codex))
    ambient_codex_home = tmp_path / "ambient-authenticated-codex-home"
    _seed_authenticated_codex_home(ambient_codex_home)
    monkeypatch.setenv("CODEX_HOME", str(ambient_codex_home))
    monkeypatch.setenv("MATHLOOP_CODEX_HOME", str(tmp_path / "unauthenticated-codex-home"))
    monkeypatch.setattr(cli_module, "_sage_image_available", lambda: True)

    result = cli_runner.invoke(app, ["codex", "init"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["checks"]["codex_login"]["ok"] is False


def test_codex_init_fails_when_the_cli_version_is_too_old(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
    tmp_path: Path,
    fake_codex: Path,
) -> None:
    _init_env(monkeypatch, repository, tmp_path)
    monkeypatch.setenv("MATHLOOP_CODEX_CLI_PATH", str(fake_codex))
    monkeypatch.setenv("FAKE_CODEX_VERSION", "0.100.0")
    monkeypatch.setattr(cli_module, "_sage_image_available", lambda: True)

    result = cli_runner.invoke(app, ["codex", "init"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["checks"]["codex_cli_version"]["ok"] is False


def test_codex_init_fails_when_git_is_unavailable(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
    tmp_path: Path,
    fake_codex: Path,
) -> None:
    _init_env(monkeypatch, repository, tmp_path)
    monkeypatch.setenv("MATHLOOP_CODEX_CLI_PATH", str(fake_codex))
    # Not a git working tree at all -- the directory exists but was never
    # `git init`ed.
    not_a_repo = tmp_path / "plain-directory"
    not_a_repo.mkdir()
    monkeypatch.setenv("MATHLOOP_CODEX_REPO_ROOT", str(not_a_repo))
    monkeypatch.setattr(cli_module, "_sage_image_available", lambda: True)

    result = cli_runner.invoke(app, ["codex", "init"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["checks"]["git_repository"]["ok"] is False


def test_codex_init_fails_on_a_dirty_checkout(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
    tmp_path: Path,
    fake_codex: Path,
) -> None:
    repo_root = _init_env(monkeypatch, repository, tmp_path)
    monkeypatch.setenv("MATHLOOP_CODEX_CLI_PATH", str(fake_codex))
    (repo_root / "README.md").write_text("dirtied by the test\n")
    monkeypatch.setattr(cli_module, "_sage_image_available", lambda: True)

    result = cli_runner.invoke(app, ["codex", "init"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["checks"]["git_repository"]["ok"] is False


def test_codex_init_fails_when_the_sage_image_is_missing(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
    tmp_path: Path,
    fake_codex: Path,
) -> None:
    _init_env(monkeypatch, repository, tmp_path)
    monkeypatch.setenv("MATHLOOP_CODEX_CLI_PATH", str(fake_codex))
    monkeypatch.setattr(cli_module, "_sage_image_available", lambda: False)

    result = cli_runner.invoke(app, ["codex", "init"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["checks"]["sage_image"]["ok"] is False


def test_codex_init_never_starts_a_codex_turn(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
    repository: Repository,
    tmp_path: Path,
    fake_codex: Path,
) -> None:
    _init_env(monkeypatch, repository, tmp_path)
    monkeypatch.setenv("MATHLOOP_CODEX_CLI_PATH", str(fake_codex))
    monkeypatch.setattr(cli_module, "_sage_image_available", lambda: True)

    cli_runner.invoke(app, ["codex", "init"])

    marker = _codex_home_path(tmp_path) / "invoked-exec.marker"
    assert not marker.exists()
    assert repository.count_events("codex_turn.reserved") == 0


# ---------------------------------------------------------------------------
# Graceful SIGINT/SIGTERM handling for `codex start`
# ---------------------------------------------------------------------------


def test_codex_start_sigint_requests_a_graceful_stop_not_a_hard_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An interrupted turn still consumed real Codex quota.

    `codex start`'s signal handler must flip the same cooperative stop event
    `mathloop run` already uses (`AutonomousLoop.request_stop`) rather than
    letting the shell's default SIGINT behavior tear the process down: a
    worker mid-turn must be given the chance to finish its *current* claim
    (Codex's own absolute deadline already bounds how long that can take)
    and simply not start another one, rather than being killed outright.
    """
    request_stop_calls: list[bool] = []

    class FakeLoop:
        def __init__(self) -> None:
            self.worker_processes = 1

        def request_stop(self) -> None:
            request_stop_calls.append(True)

    class FakeRuntime:
        def __init__(self) -> None:
            self.loop = FakeLoop()

    captured: dict[str, Event] = {}

    class FakeSupervisor:
        def __init__(self, runtime: object) -> None:
            self.runtime = runtime

        def start(
            self, max_turns: int, *, workers: int, stop_requested: Event | None = None
        ) -> dict[str, object]:
            assert stop_requested is not None
            captured["stop_requested"] = stop_requested
            # Stands in for a real, still-in-flight Codex turn: it does not
            # return the instant the signal is observed by the OS, only once
            # the cooperative event is actually set.
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline and not stop_requested.is_set():
                time.sleep(0.01)
            return {
                "requested_turns": max_turns,
                "started_turns": 0,
                "cycles_run": 0,
                "paused": False,
                "interrupted": stop_requested.is_set(),
                "usage": {},
            }

    from contextlib import contextmanager

    @contextmanager
    def fake_runtime_cm(**kwargs: object):
        del kwargs
        yield FakeRuntime()

    monkeypatch.setattr(cli_module, "_runtime", fake_runtime_cm)
    monkeypatch.setattr(cli_module, "CodexSupervisor", FakeSupervisor)

    def deliver_sigint_shortly() -> None:
        time.sleep(0.15)
        os.kill(os.getpid(), signal.SIGINT)

    sender = threading.Thread(target=deliver_sigint_shortly, daemon=True)
    sender.start()
    result = CliRunner().invoke(app, ["codex", "start", "--turns", "1", "--workers", "1"])
    sender.join()

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["interrupted"] is True
    assert request_stop_calls == [True]
    assert captured["stop_requested"].is_set()
