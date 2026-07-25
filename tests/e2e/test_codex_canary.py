"""End-to-end verification of the complete Codex supervisor foundation path.

This file has two tests with very different blast radii:

- `test_codex_supervisor_foundation_offline_end_to_end` drives every real
  component (PostgreSQL, git worktrees, the process/pipe boundary, the turn
  ledger) except the genuine Codex CLI, which is stood in for by a small
  fake script. It never contacts Codex or OpenAI and is part of the ordinary
  offline suite.
- `test_live_codex_cli_compatibility_smoke` is the only test in this plan
  marked `@pytest.mark.live_codex`. It spends one real, credit-consuming
  ChatGPT Codex Luna turn against the operator's own subscription and must
  never run as a side effect of an ordinary test invocation -- see its own
  docstring for the double skip guard.

On the fake CLI used by the offline test: a fake that merely emits
plausible-looking JSONL can hide real defects -- this plan has already found
three that way (a fake that ignored `--output-schema` and hid a schema-file
deletion race; no test crossing the real fork boundary, hiding an unpicklable
exception; a fake that never authenticated, hiding that every real turn would
fail auth). The fake below still does not authenticate against a real ChatGPT
session (that is precisely what the live test exists to check), but it no
longer merely *pretends* about the two things above: it actually requires an
authenticated `CODEX_HOME` (mirroring the real CLI, borrowed from the
already-reviewed fake in `tests/integration/test_codex_runtime.py`), and it
additionally reads and validates the `--output-schema` file -- both when it
starts and again immediately before it exits -- refusing the turn if that
file is ever missing or malformed. It also refuses the turn outright if an
`OPENAI_API_KEY`/`CODEX_API_KEY` ever reaches it, rather than silently
succeeding regardless.

A fourth defect this fake used to conceal, found by direct binary
inspection of the real, installed Codex CLI (0.145.0) rather than by
running it: every fake CLI in this plan emitted `cli_version` on
`thread.started`, and `CodexClient` required it unconditionally -- but the
real CLI's serde tag table contains no such field near that event at all.
This fake now deliberately omits it, so this test exercises the client's
`codex --version` fallback through the complete real path (worker, ledger,
persisted `codex_turns.cli_version`), not just in isolation.
"""

import base64
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

import mathloop.cli as cli_module
from mathloop.artifacts import ArtifactStore
from mathloop.codex.client import CodexClient, CodexRequest
from mathloop.codex.domain import CodexModelRole, CodexTurnReservation, CodexTurnStatus
from mathloop.codex.events import CodexEvent
from mathloop.codex.launch import CodexLaunchPolicy
from mathloop.codex.supervisor import CodexSupervisor
from mathloop.codex.worktrees import CodexWorktreeManager
from mathloop.config import Settings
from mathloop.domain import Experiment, ExperimentStatus
from mathloop.methods.proof_sketch import ProofSketch
from mathloop.runtime import build_runtime
from mathloop.storage.repository import Repository
from mathloop.verification import CalibrationVerificationKernel

# ---------------------------------------------------------------------------
# Fake Codex CLI for the offline test only. Never used by the live test.
# ---------------------------------------------------------------------------

_FAKE_CODEX_SOURCE = '''\
#!/usr/bin/env python3
import json
import os
import sys


def _emit(payload):
    sys.stdout.write(json.dumps(payload) + "\\n")
    sys.stdout.flush()


def _codex_home():
    return os.environ.get("CODEX_HOME", "")


def _is_authenticated():
    home = _codex_home()
    return bool(home) and os.path.exists(os.path.join(home, "auth.json"))


def _fail(message):
    sys.stderr.write(message + "\\n")
    return 1


def main():
    argv = sys.argv[1:]
    if argv[:1] == ["--version"]:
        sys.stdout.write("codex-cli 0.145.0\\n")
        return 0
    if argv[:2] == ["login", "status"]:
        if _is_authenticated():
            sys.stdout.write("Logged in with ChatGPT\\n")
            return 0
        sys.stdout.write("Not logged in.\\n")
        return 1

    # Anything else is a real `codex exec` turn. This fake does not trust
    # that the harness wired things correctly -- it independently checks
    # every safety property a real `codex` binary would depend on, and
    # refuses (rather than silently succeeding) if any of them is absent.
    if "OPENAI_API_KEY" in os.environ or "CODEX_API_KEY" in os.environ:
        return _fail(
            "error: a metered API key reached the codex child process; a "
            "real codex exec would never see one"
        )
    if not _is_authenticated():
        return _fail("error: not logged in; run `codex login`")

    schema_path = argv[argv.index("--output-schema") + 1] if "--output-schema" in argv else None
    if not schema_path or not os.path.exists(schema_path):
        return _fail(
            "error: --output-schema path is missing -- the client deleted or "
            "never wrote the schema file before this process could read it"
        )
    with open(schema_path) as handle:
        try:
            schema = json.load(handle)
        except json.JSONDecodeError:
            return _fail("error: --output-schema file is not valid JSON")
    if not isinstance(schema, dict) or "properties" not in schema:
        return _fail("error: --output-schema file is not a JSON Schema object")

    worktree = argv[argv.index("--cd") + 1] if "--cd" in argv else None

    codex_home = _codex_home()
    with open(os.path.join(codex_home, "invoked-exec.marker"), "a") as handle:
        handle.write("invoked\\n")

    # Deliberately omits `cli_version` here: direct inspection of the real,
    # installed Codex CLI (0.145.0) found no such field anywhere near its
    # real `thread.started` event. `CodexClient` must fall back to a
    # separate `codex --version` query (handled by the `--version` branch
    # above) rather than treating this as fatal -- this end-to-end test is
    # what proves that fallback holds all the way through the real worker
    # and ledger path, not just in isolation.
    _emit({"type": "thread.started", "thread_id": "thread-fake"})
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
    # Re-read the schema file after emitting every event and completing the
    # turn's own work too -- proving it was never deleted mid-flight, not
    # only at the moment this process started.
    if not os.path.exists(schema_path):
        return _fail("error: --output-schema file vanished before the turn finished")
    with open(os.path.join(codex_home, "exec-completed.marker"), "a") as handle:
        handle.write("completed\\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def _write_fake_codex(tmp_path: Path) -> Path:
    script = tmp_path / "fake_codex.py"
    script.write_text(_FAKE_CODEX_SOURCE)
    script.chmod(0o700)
    return script


def _seed_authenticated_codex_home(codex_home: Path) -> None:
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "auth.json").write_text('{"fake": "credential"}\n')


class _NeverCalledJsonRunner:
    """Stands in for the Docker Sage runner; must never be invoked by Codex work.

    `runtime.register_baseline_methods()` -- the real production registration
    entry point, used here rather than hand-rolling a Codex-only path -- also
    wires up `sage_polynomial`, which needs *some* `JsonRunner`. This test
    never schedules or runs a `sage_polynomial` experiment: it enqueues
    exactly one `codex_proof_strategy` experiment directly. This stub exists
    to keep the offline test hermetic (no real Docker/Sage image dependency)
    and to fail loudly, rather than silently, if that invariant is ever
    broken by a future change.
    """

    def run_json(self, payload: dict[str, object]) -> dict[str, object]:
        raise AssertionError(
            "the Docker Sage runner must never be invoked by a Codex proof-strategy lead"
        )


# ---------------------------------------------------------------------------
# Shared git helpers
# ---------------------------------------------------------------------------


def _run_git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_git_repo(repo_root: Path) -> str:
    repo_root.mkdir(parents=True, exist_ok=True)
    _run_git("init", "-q", "-b", "main", cwd=repo_root)
    _run_git("config", "user.email", "codex-canary-test@example.com", cwd=repo_root)
    _run_git("config", "user.name", "Codex Canary Test", cwd=repo_root)
    (repo_root / "README.md").write_text("seed content\n")
    _run_git("add", "-A", cwd=repo_root)
    _run_git("commit", "-q", "-m", "seed", cwd=repo_root)
    return _run_git("rev-parse", "HEAD", cwd=repo_root).stdout.strip()


def _git_status(repo_root: Path) -> str:
    return _run_git("status", "--porcelain", cwd=repo_root).stdout


def _git_head(repo_root: Path) -> str:
    return _run_git("rev-parse", "HEAD", cwd=repo_root).stdout.strip()


# ---------------------------------------------------------------------------
# Step 1/2: the offline end-to-end test
# ---------------------------------------------------------------------------


def test_codex_supervisor_foundation_offline_end_to_end(
    repository: Repository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)

    # -- 1. Initialize real PostgreSQL. ------------------------------------
    # `repository` (tests/conftest.py) is backed by a real, session-scoped
    # testcontainers PostgreSQL with the real schema already applied
    # (`Database.initialize()`); prove it is actually reachable here too,
    # rather than only trusting fixture setup implicitly.
    assert repository.ping() is True

    repo_root = tmp_path / "source-main-checkout"
    base_sha = _init_git_repo(repo_root)
    codex_home = tmp_path / "codex-home"
    _seed_authenticated_codex_home(codex_home)
    fake_codex = _write_fake_codex(tmp_path)

    settings = Settings(
        database_url=repository.database.database_url,
        artifact_root=tmp_path / "artifacts",
        incoming_root=tmp_path / "incoming",
        codex_cli_path=fake_codex,
        codex_repo_root=repo_root,
        codex_worktree_root=tmp_path / "codex-worktrees",
        codex_home=codex_home,
        codex_turn_timeout_seconds=60,
    )
    artifacts = ArtifactStore(settings.artifact_root)
    runtime = build_runtime(
        repository,
        artifacts,
        api_enabled=False,
        codex_enabled=True,
        settings=settings,
        verifier_runner=_NeverCalledJsonRunner(),
    )

    # -- 2. Ingest the calibration corpus. ---------------------------------
    ingested = runtime.ingest(Path("data/calibration/problems.jsonl"))
    assert len(ingested) == 6
    problems = repository.list_eligible_problems()
    assert len(problems) == 6

    # -- 3. Register Codex methods. -----------------------------------------
    # The real production entry point (`register_baseline_methods`), not a
    # hand-rolled shortcut -- it also registers the three local baseline
    # solvers, but none of them is ever scheduled or run below.
    runtime.register_baseline_methods()
    assert runtime.methods.contains("codex_proof_strategy")
    # api_enabled=False is what actually keeps "proof_sketch" from
    # registering here (register_baseline_methods only attempts it when
    # BOTH api_enabled and a live OPENAI_API_KEY are present); the
    # monkeypatch.delenv above only removes an unrelated, redundant risk.
    assert not runtime.methods.contains("proof_sketch")

    method_version = next(
        method for method in repository.list_methods() if method.family == "codex_proof_strategy"
    )
    development_problem = next(problem for problem in problems if problem.cohort == "development")

    # -- 4. Schedule one development proof-strategy experiment. ------------
    # Built via the real scheduler's own config constructor
    # (`RuntimeScheduler._config`, exercised directly in
    # `tests/unit/test_scheduler.py`) rather than a hand-copied dict, then
    # enqueued directly rather than through the full probabilistic
    # `runtime.schedule()` multi-lane allocator -- this keeps the count of
    # Codex experiments in this test exactly one and deterministic. The
    # scheduler's own holdout-exclusion and lane-allocation behavior is
    # already covered by Task 6's dedicated scheduler tests.
    config = runtime.scheduler._config(development_problem, method_version, "exploitation")
    experiment = Experiment(
        id=uuid4(),
        problem_id=development_problem.id,
        method_id=method_version.id,
        lane="exploitation",
        config=config,
        seed=1,
        status=ExperimentStatus.QUEUED,
        created_at=datetime.now(UTC),
    )
    repository.enqueue(experiment, f"e2e-codex:{experiment.id}")
    assert repository.queue_depth() == 1

    verification_calls: list[tuple[UUID, UUID]] = []
    original_verify = CalibrationVerificationKernel.verify

    def _spy_verify(self: CalibrationVerificationKernel, problem: object, claim: object) -> object:
        verification_calls.append((problem.id, claim.id))  # type: ignore[attr-defined]
        return original_verify(self, problem, claim)  # type: ignore[arg-type]

    monkeypatch.setattr(CalibrationVerificationKernel, "verify", _spy_verify)

    before_status = _git_status(repo_root)
    before_head = _git_head(repo_root)
    assert before_status == ""
    assert before_head == base_sha

    # -- 5. Run the fake Codex executable. ----------------------------------
    # A real subprocess, a real disposable git worktree, a real fork-boundary
    # process pipe -- everything except the genuine `codex` binary.
    processed = runtime.worker.run_once("e2e-codex-worker")
    assert processed is True

    experiment_after = repository.get_experiment(experiment.id)
    assert experiment_after.status == ExperimentStatus.SUCCEEDED

    # -- 6. Persist every event and a bound usage receipt. ------------------
    with repository.database.transaction() as connection:
        turn_row = connection.execute(
            "SELECT id, experiment_id, budget_day, role, model, status, thread_id, "
            "cli_version, input_tokens, cached_input_tokens, output_tokens, "
            "reasoning_output_tokens, failure_kind, failure_message "
            "FROM codex_turns WHERE experiment_id = %(experiment_id)s",
            {"experiment_id": experiment.id},
        ).fetchone()
    assert turn_row is not None
    (
        turn_id,
        turn_experiment_id,
        budget_day,
        role,
        model,
        status,
        thread_id,
        cli_version,
        input_tokens,
        cached_input_tokens,
        output_tokens,
        reasoning_output_tokens,
        failure_kind,
        failure_message,
    ) = turn_row
    assert turn_experiment_id == experiment.id
    assert budget_day == datetime.now(UTC).date()
    assert role == CodexModelRole.LUNA.value
    assert model == settings.codex_model_luna
    assert status == CodexTurnStatus.COMPLETED.value
    assert thread_id == "thread-fake"
    # Not "0.145.0-test": the fake CLI's `thread.started` event deliberately
    # omits `cli_version` (matching the real CLI), so this value can only be
    # here because `CodexClient` fell back to its `codex --version` query
    # against the same fake binary and parsed "codex-cli 0.145.0".
    assert cli_version == "0.145.0"
    assert input_tokens == 100
    assert cached_input_tokens == 10
    assert output_tokens == 12
    assert reasoning_output_tokens == 5
    assert failure_kind is None
    assert failure_message is None

    with repository.database.transaction() as connection:
        event_rows = connection.execute(
            "SELECT sequence, event_type, raw_sha256 FROM codex_turn_events "
            "WHERE turn_id = %(turn_id)s ORDER BY sequence",
            {"turn_id": turn_id},
        ).fetchall()
    assert [row[0] for row in event_rows] == [0, 1, 2, 3]
    assert [row[1] for row in event_rows] == [
        "thread.started",
        "turn.started",
        "item.completed",
        "turn.completed",
    ]
    assert all(len(row[2]) == 64 for row in event_rows)  # a real sha256 hex digest each

    # -- 7. Store the patch as non-authoritative artifact evidence. --------
    with repository.database.transaction() as connection:
        artifact_row = connection.execute(
            "SELECT digest, media_type FROM artifacts WHERE experiment_id = %(experiment_id)s",
            {"experiment_id": experiment.id},
        ).fetchone()
    assert artifact_row is not None
    digest, media_type = artifact_row
    assert media_type == "application/json"
    envelope_bytes = artifacts.open(digest)
    assert hashlib.sha256(envelope_bytes).hexdigest() == digest
    envelope = json.loads(envelope_bytes)
    assert envelope["experiment_id"] == str(experiment.id)
    result_payload = envelope["result"]
    method_artifact = json.loads(base64.b64decode(result_payload["method_artifact_base64"]))
    assert method_artifact["accounting_unit"] == "chatgpt_codex_turn"
    assert method_artifact["proof_sketch"]["strategy"] == "induction"

    # Independently reconstruct the exact patch a real `codex exec` turn's
    # edit would produce -- a fresh clone at the same base_sha, the same
    # file edit the fake CLI performs, the same `git add -A` + `git diff
    # --binary --no-ext-diff <base_sha>` sequence `CodexWorktreeManager`
    # itself uses -- and compare its digest to the one recorded as evidence.
    # This does not merely trust the production code's own diff() output (a
    # live spy could not reach it anyway: `CodexClient.execute` runs inside
    # the forked execution-boundary child, a different process whose memory
    # a parent-process monkeypatch never reaches); it recomputes the
    # expected artifact from scratch and checks the two agree.
    verification_clone = tmp_path / "patch-verification-clone"
    subprocess.run(
        ["git", "clone", "-q", str(repo_root), str(verification_clone)], check=True
    )
    (verification_clone / "NOTES.md").write_text("codex was here\n")
    _run_git("add", "-A", cwd=verification_clone)
    expected_patch = subprocess.run(
        ["git", "-C", str(verification_clone), "diff", "--binary", "--no-ext-diff", base_sha],
        capture_output=True,
        check=True,
    ).stdout
    assert method_artifact["patch_sha256"] == hashlib.sha256(expected_patch).hexdigest()

    # The actual patch bytes are stored too, not merely a digest committing
    # to bytes nobody could ever produce again (the disposable worktree that
    # made them is already gone by this point) -- base64-decode what was
    # persisted and confirm it is byte-identical to the independently
    # reconstructed diff above, and that its own digest matches the recorded
    # `patch_sha256` too.
    stored_patch = base64.b64decode(method_artifact["patch_base64"])
    assert stored_patch == expected_patch
    assert hashlib.sha256(stored_patch).hexdigest() == method_artifact["patch_sha256"]

    # Non-authoritative: no claim, and therefore no path into the review
    # queue or publication surface, was ever created from this evidence.
    assert runtime.reporting.review_queue() == []

    # -- 8. Report one consumed Codex turn and zero API dollars. -----------
    # Asserted against the persisted database rows directly, not in-memory
    # objects: `MethodResult`/`CodexTurnReceipt` held only in this test
    # process would say nothing about what was actually durably settled.
    with repository.database.transaction() as connection:
        turn_count = connection.execute("SELECT count(*) FROM codex_turns").fetchone()
        cost_row = connection.execute(
            "SELECT cost_usd FROM experiments WHERE id = %(id)s", {"id": experiment.id}
        ).fetchone()
        budget_reservation_count = connection.execute(
            "SELECT count(*) FROM budget_reservations WHERE experiment_id = %(id)s",
            {"id": experiment.id},
        ).fetchone()
    assert turn_count is not None and turn_count[0] == 1
    assert cost_row is not None and cost_row[0] == Decimal("0")
    assert budget_reservation_count is not None and budget_reservation_count[0] == 0

    usage_status = repository.codex_usage_status(datetime.now(UTC))
    assert usage_status.daily_reserved == 1
    assert usage_status.role_reserved.get(CodexModelRole.LUNA.value) == 1
    assert usage_status.active_leases == 0
    assert usage_status.usage.input_tokens == 100
    assert usage_status.usage.output_tokens == 12

    report = CodexSupervisor(runtime).report()
    assert report["turns_by_status"] == {"completed": 1}
    assert "usd" not in json.dumps(report).lower()

    # -- 9. Prove no claim was machine-verified from the proof sketch. -----
    # Structural, not merely "status == lead": no `CandidateClaim` exists in
    # the database at all, the sole query that ever surfaces a claim for
    # verification returns nothing, `verify_pending()` -- the only call site
    # of the fixed independent verification kernel -- genuinely performed
    # zero verifications, and the kernel's own `verify` method (spied above,
    # safely, since it runs in this same process rather than the forked
    # execution-boundary child) was never entered.
    assert result_payload["status"] == "lead"
    assert result_payload["witness"] is None
    assert result_payload["claim"] is None
    with repository.database.transaction() as connection:
        claims_count = connection.execute("SELECT count(*) FROM claims").fetchone()
    assert claims_count is not None and claims_count[0] == 0
    assert repository.list_candidate_claim_ids() == ()
    assert runtime.worker.verify_pending() == 0
    assert verification_calls == []

    # -- 10. Prove the source checkout is unchanged and cleanup completed. -
    after_status = _git_status(repo_root)
    after_head = _git_head(repo_root)
    assert after_status == before_status == ""
    assert after_head == before_head == base_sha

    worktree_path = settings.codex_worktree_root / str(turn_id)
    assert not worktree_path.exists()
    git_worktree_admin_dir = repo_root / ".git" / "worktrees" / str(turn_id)
    assert not git_worktree_admin_dir.exists()
    worktree_listing = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert worktree_listing.count("worktree ") == 1  # only the main checkout remains


# ---------------------------------------------------------------------------
# Step 3: the explicit live compatibility test. NEVER executed automatically.
# ---------------------------------------------------------------------------


@pytest.mark.live_codex
@pytest.mark.skipif(
    os.environ.get("MATHLOOP_RUN_LIVE_CODEX") != "1",
    reason=(
        "spends one real, credit-consuming ChatGPT Codex Luna turn against "
        "the operator's own subscription; set MATHLOOP_RUN_LIVE_CODEX=1 "
        "immediately before an explicitly approved run"
    ),
)
def test_live_codex_cli_compatibility_smoke(tmp_path: Path) -> None:
    """The only test in this plan that spends a real Codex turn.

    Guarded twice over: both the `live_codex` marker (excluded by `-m "not
    live_codex"`) and this `skipif` on `MATHLOOP_RUN_LIVE_CODEX` must agree,
    so this never runs as a side effect of `pytest -q` or even `pytest -m
    live_codex` alone -- only `MATHLOOP_RUN_LIVE_CODEX=1 pytest -m
    live_codex` reaches it.

    Deliberately narrow in scope: everything the offline test above already
    proves against a fake CLI (event parsing, ledger persistence, worktree
    isolation, non-authoritative artifact evidence) is not re-proven here
    with real money. This test exists only to catch drift between our launch
    policy / event parser and the actual installed `codex` CLI and the
    operator's real ChatGPT login -- the one thing no fake can ever stand in
    for. It talks to `CodexClient` directly and never constructs a
    `Repository` or touches PostgreSQL at all, so no API-dollar billing row
    can exist: this call path never reaches the OpenAI provider, and
    `CodexTurnReceipt` itself has no dollar-denominated field to populate
    even if something tried.
    """
    settings = Settings()
    launch_policy = CodexLaunchPolicy(
        codex_binary=settings.codex_cli_path, codex_home=settings.codex_home
    )

    login_ok, login_detail = cli_module._codex_login_status(launch_policy)
    assert login_ok, f"codex is not ChatGPT-authenticated: {login_detail}"
    # `login_ok` alone is only `returncode == 0` -- codex also supports an
    # API-key credential in the same `auth.json`, which would exit 0 too. If
    # that credential were ever an API key instead of a ChatGPT session, the
    # "subscription turn" below would silently bill metered OpenAI API
    # dollars instead -- exactly the outcome this whole plan forbids. The
    # brief requires asserting a *ChatGPT* login, not merely *a* login.
    assert "ChatGPT" in login_detail, (
        f"codex login status did not report a ChatGPT session: {login_detail!r}"
    )

    version_ok, version_detail = cli_module._codex_cli_version(settings.codex_cli_path)
    assert version_ok, f"codex --version failed: {version_detail}"
    assert cli_module._codex_version_at_least(version_detail, settings.codex_min_cli_version)

    # The meaningful check is against the AMBIENT environment (could this
    # process's own env leak a metered key at all), not the allowlisted
    # output of `launch_policy.environment()` -- that dict structurally can
    # never contain either key regardless of what's ambient, so asserting
    # against it would be a tautology. Reuses the same preflight check
    # `mathloop codex init` already runs.
    env_ok, env_detail = cli_module._codex_launch_environment_clean()
    assert env_ok, env_detail

    repo_root = tmp_path / "live-smoke-repo"
    base_sha = _init_git_repo(repo_root)
    before_status = _git_status(repo_root)

    worktree_manager = CodexWorktreeManager(
        repo_root=repo_root, worktree_root=tmp_path / "codex-worktrees"
    )
    # A single 120-second timeout, sourced from the reservation's own
    # `deadline_seconds` (matching how `CodexClient.execute` resolves its
    # timeout in production: `self._timeout_seconds` only when explicitly
    # set, else `reservation.deadline_seconds`) -- not a second, disconnected
    # `timeout_seconds=` override on the client that `CodexClient` would
    # actually prefer and that would silently make the reservation's own
    # value dead.
    client = CodexClient(launch_policy, worktree_manager)
    reservation = CodexTurnReservation(
        id=uuid4(),
        experiment_id=uuid4(),
        budget_day=datetime.now(UTC).date(),
        role=CodexModelRole.LUNA,
        model=settings.codex_model_luna,
        deadline_seconds=120,
        created_at=datetime.now(UTC),
    )
    request: CodexRequest[ProofSketch] = CodexRequest(
        reservation=reservation,
        prompt=(
            "This is a connectivity smoke test, not a real mathematics task. "
            "Do not modify any files beyond what is required to respond, and "
            "do not run any commands. Respond ONLY with JSON matching the "
            "required output schema exactly: "
            '{"strategy": "ping", "lemmas": ["none"], "risks": ["none"]}.'
        ),
        base_sha=base_sha,
        response_schema=ProofSketch,
    )
    events: list[CodexEvent] = []
    response = client.execute(request, events.append)

    event_types = [event.event_type for event in events]
    assert "thread.started" in event_types
    assert "turn.started" in event_types
    assert "turn.completed" in event_types
    assert isinstance(response.value, ProofSketch)

    usage = response.receipt.usage
    assert usage.input_tokens >= 0
    assert usage.cached_input_tokens >= 0
    assert usage.output_tokens >= 0
    assert usage.reasoning_output_tokens >= 0
    assert response.receipt.final_status == "completed"
    assert cli_module._codex_version_at_least(
        response.receipt.cli_version, settings.codex_min_cli_version
    )

    after_status = _git_status(repo_root)
    assert after_status == before_status == ""
    assert _git_head(repo_root) == base_sha
