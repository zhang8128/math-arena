"""Operator CLI with explicit local and external authority boundaries."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from threading import Event
from uuid import UUID

import typer

from mathloop.artifacts import ArtifactStore
from mathloop.codex.launch import CodexLaunchPolicy
from mathloop.codex.supervisor import CodexSupervisor
from mathloop.config import Settings
from mathloop.provenance import SAGE_IMAGE_DIGEST
from mathloop.runtime import Runtime, build_runtime
from mathloop.storage.db import Database
from mathloop.storage.repository import Repository

app = typer.Typer(help="Mathloop autonomous mathematics solver ecology.")
codex_app = typer.Typer(help="Operate the bounded Codex proof-strategy provider.")
app.add_typer(codex_app, name="codex")

# The two credentials this whole plan forbids ever reaching a Codex child --
# authentication is always the operator's saved ChatGPT CLI login, never a
# metered API key. `codex init` checks these are absent from *this* process's
# own environment; `CodexLaunchPolicy.environment` is the separate, load-
# bearing guard that keeps them from ever reaching the launched child even if
# they were present here.
_CODEX_FORBIDDEN_ENV_KEYS = ("OPENAI_API_KEY", "CODEX_API_KEY")

# Leading path components `codex init`'s git-cleanliness check tolerates as
# UNTRACKED (never tracked-and-modified, deleted, or renamed -- see
# `_codex_git_state`) without failing the preflight. Restricted to paths this
# plan actually documents as ignored operator state: `.mathloop/` is Codex's
# own worktree/turn-ledger scratch space and is listed in `.gitignore`. Do
# not add entries here that are merely untracked in one operator's sandbox --
# `.claude/`/`.engram/` were removed for exactly that reason (Task 7 review):
# neither appears in `.gitignore`, the plan, or any design doc, so excusing
# them was accidental, not documented.
_CODEX_ALLOWED_UNTRACKED_PATH_COMPONENTS = frozenset({".mathloop"})

_CODEX_VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@contextmanager
def _runtime(
    *, api_enabled: bool = False, codex_enabled: bool = False, initialize: bool = False
) -> Iterator[Runtime]:
    settings = Settings()
    database = Database(settings.database_url)
    try:
        if initialize:
            database.initialize()
        repository = Repository(database)
        runtime = build_runtime(
            repository,
            ArtifactStore(settings.artifact_root),
            api_enabled=api_enabled,
            codex_enabled=codex_enabled,
            settings=settings,
        )
        yield runtime
    finally:
        database.close()


@app.callback()
def main() -> None:
    """Run Mathloop commands."""


@app.command("db-init")
def db_init() -> None:
    """Initialize or migrate the canonical PostgreSQL schema."""
    with _runtime(initialize=True) as runtime:
        if not runtime.repository.ping():
            raise typer.Exit(code=1)
    typer.echo("database initialized")


@app.command()
def ingest(path: Path) -> None:
    """Ingest an immutable local JSONL source snapshot."""
    with _runtime() as runtime:
        result = runtime.ingest_with_result(path)
    typer.echo(
        json.dumps(
            {
                "processed": result.processed,
                "inserted": result.inserted,
                "existing": result.existing,
                "problem_ids": [str(item) for item in result.problem_ids],
            }
        )
    )


@app.command()
def schedule(
    limit: int = typer.Option(..., min=0),
    seed: int = typer.Option(...),
) -> None:
    """Fill a deterministic bounded portfolio batch."""
    with _runtime() as runtime:
        runtime.register_baseline_methods()
        ids = runtime.schedule(limit, seed)
    typer.echo(json.dumps({"scheduled": len(ids), "experiment_ids": [str(item) for item in ids]}))


@app.command()
def worker(
    once: bool = typer.Option(False, "--once"),
    worker_id: str = typer.Option(..., "--worker-id"),
    api_enabled: bool = typer.Option(False, "--api-enabled"),
) -> None:
    """Run disposable local experiments without granting publication authority."""
    with _runtime(api_enabled=api_enabled) as runtime:
        runtime.register_baseline_methods()
        completed = 0
        if once:
            completed = int(runtime.worker.run_once(worker_id))
        else:
            while runtime.worker.run_once(worker_id):
                completed += 1
    typer.echo(json.dumps({"worker_id": worker_id, "processed": completed}))


@app.command()
def run(
    cycles: int = typer.Option(..., min=1),
    workers: int = typer.Option(..., min=1),
    api_enabled: bool = typer.Option(False, "--api-enabled"),
) -> None:
    """Run bounded autonomous cycles; API work remains explicitly credential-gated."""
    with _runtime(api_enabled=api_enabled) as runtime:
        _validate_run_preconditions(runtime)
        runtime.register_baseline_methods()
        stop_requested = Event()

        def request_stop(signum: int, frame: object) -> None:
            del signum, frame
            stop_requested.set()
            runtime.loop.request_stop()

        previous_interrupt = signal.signal(signal.SIGINT, request_stop)
        previous_terminate = signal.signal(signal.SIGTERM, request_stop)
        reports: list[dict[str, object]] = []
        try:
            runtime.loop.worker_processes = workers
            for _ in range(cycles):
                if stop_requested.is_set():
                    break
                reports.append(runtime.loop.cycle())
        finally:
            signal.signal(signal.SIGINT, previous_interrupt)
            signal.signal(signal.SIGTERM, previous_terminate)
    typer.echo(json.dumps({"cycles": reports}, sort_keys=True))


@app.command()
def report(
    output_format: str = typer.Option("json", "--format"),
) -> None:
    """Print review items and metrics without performing external actions."""
    if output_format != "json":
        raise typer.BadParameter("only json format is supported", param_hint="--format")
    with _runtime() as runtime:
        payload = {
            "review_queue": runtime.reporting.review_queue(),
            "metrics": runtime.reporting.metrics(),
        }
    typer.echo(json.dumps(payload, sort_keys=True))


@app.command()
def reproduce(claim_id: UUID) -> None:
    """Re-run local canonical verification against persisted evidence."""
    with _runtime() as runtime:
        result = runtime.reporting.reproduce(claim_id)
    typer.echo(json.dumps(result, sort_keys=True))
    if result["accepted"] is not True:
        raise typer.Exit(code=1)


@codex_app.command("init")
def codex_init() -> None:
    """Preflight-check the local Codex operating environment.

    Never starts a Codex turn: every check here is either free (settings and
    environment variables already in memory) or a read-only probe (`codex
    --version`, `codex login status`, `git status --porcelain`, a Postgres
    ping, a Docker image inspect). Reuses saved ChatGPT CLI authentication --
    it only asks the CLI to report whether it is already logged in, never
    performs a login itself.
    """
    settings = Settings()
    checks: dict[str, dict[str, object]] = {}

    version_ok, version_detail = _codex_cli_version(settings.codex_cli_path)
    if version_ok:
        version_ok = _codex_version_at_least(version_detail, settings.codex_min_cli_version)
        if not version_ok:
            version_detail = (
                f"codex {version_detail} is older than the required minimum "
                f"{settings.codex_min_cli_version}"
            )
    checks["codex_cli_version"] = {"ok": version_ok, "detail": version_detail}

    launch_policy = CodexLaunchPolicy(
        codex_binary=settings.codex_cli_path, codex_home=settings.codex_home
    )
    login_ok, login_detail = _codex_login_status(launch_policy)
    checks["codex_login"] = {"ok": login_ok, "detail": login_detail}

    env_ok, env_detail = _codex_launch_environment_clean()
    checks["launch_environment"] = {"ok": env_ok, "detail": env_detail}

    git_ok, git_detail = _codex_git_state(settings.codex_repo_root)
    checks["git_repository"] = {"ok": git_ok, "detail": git_detail}

    worktree_ok, worktree_detail = _codex_worktree_root_writable(settings.codex_worktree_root)
    checks["worktree_root"] = {"ok": worktree_ok, "detail": worktree_detail}

    postgres_ok, postgres_detail = _codex_postgres_available(settings.database_url)
    checks["postgresql"] = {"ok": postgres_ok, "detail": postgres_detail}

    sage_ok = _sage_image_available()
    checks["sage_image"] = {
        "ok": sage_ok,
        "detail": SAGE_IMAGE_DIGEST if sage_ok else f"{SAGE_IMAGE_DIGEST} is unavailable",
    }

    overall_ok = all(bool(check["ok"]) for check in checks.values())
    typer.echo(json.dumps({"ok": overall_ok, "checks": checks}, sort_keys=True))
    if not overall_ok:
        raise typer.Exit(code=1)


@codex_app.command("start")
def codex_start(
    turns: int = typer.Option(..., "--turns", min=1),
    workers: int = typer.Option(1, "--workers", min=1),
) -> None:
    """Run bounded Codex cycles; the durable ledger caps govern, not --turns."""
    with _runtime(codex_enabled=True) as runtime:
        supervisor = CodexSupervisor(runtime)
        stop_requested = Event()

        def request_stop(signum: int, frame: object) -> None:
            del signum, frame
            stop_requested.set()
            # Reaches the same cooperative multi-process termination path
            # `mathloop run` already uses: a worker still mid-turn finishes
            # its *current* claim (Codex's own absolute deadline governs how
            # long that can take) rather than being hard-killed, and no new
            # claim is started after this fires.
            runtime.loop.request_stop()

        previous_interrupt = signal.signal(signal.SIGINT, request_stop)
        previous_terminate = signal.signal(signal.SIGTERM, request_stop)
        try:
            payload = supervisor.start(turns, workers=workers, stop_requested=stop_requested)
        finally:
            signal.signal(signal.SIGINT, previous_interrupt)
            signal.signal(signal.SIGTERM, previous_terminate)
    typer.echo(json.dumps(payload, sort_keys=True))


@codex_app.command("status")
def codex_status() -> None:
    """Read-only Codex ledger snapshot: never mutates anything."""
    with _runtime() as runtime:
        payload = CodexSupervisor(runtime).status()
    typer.echo(json.dumps(payload, sort_keys=True))


@codex_app.command("pause")
def codex_pause() -> None:
    """Durably pause Codex dispatch; the pause survives a process restart."""
    with _runtime() as runtime:
        payload = CodexSupervisor(runtime).pause()
    typer.echo(json.dumps(payload, sort_keys=True))


@codex_app.command("resume")
def codex_resume() -> None:
    """Durably resume Codex dispatch."""
    with _runtime() as runtime:
        payload = CodexSupervisor(runtime).resume()
    typer.echo(json.dumps(payload, sort_keys=True))


@codex_app.command("drain")
def codex_drain(
    grace_seconds: float = typer.Option(60.0, "--grace-seconds", min=0),
) -> None:
    """Pause, then wait for active Codex leases to clear before returning."""
    with _runtime() as runtime:
        supervisor = CodexSupervisor(runtime)
        stop_requested = Event()

        def request_stop(signum: int, frame: object) -> None:
            del signum, frame
            stop_requested.set()

        previous_interrupt = signal.signal(signal.SIGINT, request_stop)
        previous_terminate = signal.signal(signal.SIGTERM, request_stop)
        try:
            payload = supervisor.drain(grace_seconds=grace_seconds, stop_requested=stop_requested)
        finally:
            signal.signal(signal.SIGINT, previous_interrupt)
            signal.signal(signal.SIGTERM, previous_terminate)
    typer.echo(json.dumps(payload, sort_keys=True))


@codex_app.command("report")
def codex_report() -> None:
    """Read-only Codex accounting summary: turns and tokens, never a dollar figure."""
    with _runtime() as runtime:
        payload = CodexSupervisor(runtime).report()
    typer.echo(json.dumps(payload, sort_keys=True))


def _validate_run_preconditions(runtime: Runtime) -> None:
    if not runtime.repository.ping():
        raise typer.BadParameter("database is unavailable")
    artifact_root = runtime.artifacts.root
    artifact_root.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.NamedTemporaryFile(dir=artifact_root):
            pass
    except OSError as error:
        raise typer.BadParameter("artifact root is not writable") from error
    if not _sage_image_available():
        raise typer.BadParameter(
            f"required restricted Sage image {SAGE_IMAGE_DIGEST} is unavailable"
        )
    if runtime.api_enabled and not os.environ.get("OPENAI_API_KEY"):
        # The runtime persists a capability-unavailable event and continues local work.
        return


def _sage_image_available() -> bool:
    try:
        completed = subprocess.run(
            ["docker", "image", "inspect", SAGE_IMAGE_DIGEST],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


# -- `codex init` preflight checks -------------------------------------------
#
# Every function below is a small, independently testable probe: none of
# them requires a real `codex` binary or a real ChatGPT login to exercise in
# a test (each takes its inputs explicitly and is driven through a fake
# subprocess in tests), and none of them ever starts a Codex turn.


def _codex_version_tuple(raw: str) -> tuple[int, int, int] | None:
    match = _CODEX_VERSION_PATTERN.search(raw)
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def _codex_version_at_least(reported: str, minimum: str) -> bool:
    reported_tuple = _codex_version_tuple(reported)
    minimum_tuple = _codex_version_tuple(minimum)
    if reported_tuple is None or minimum_tuple is None:
        return False
    return reported_tuple >= minimum_tuple


def _codex_cli_version(codex_binary: Path) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            [str(codex_binary), "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"codex --version could not be run: {error}"
    if completed.returncode != 0:
        return False, f"codex --version exited with code {completed.returncode}"
    parsed = _codex_version_tuple(completed.stdout)
    if parsed is None:
        return False, f"could not parse a version from codex --version output: {completed.stdout!r}"
    return True, ".".join(str(part) for part in parsed)


def _codex_login_status(launch_policy: CodexLaunchPolicy) -> tuple[bool, str]:
    """Check login status against the SAME store and environment a real turn gets.

    Two distinct false-positive risks, both closed here:

    1. `CodexLaunchPolicy.environment()` always overwrites `CODEX_HOME` with
       `launch_policy.codex_home` for a real turn, discarding whatever this
       process's own environment happens to contain. Passing `codex_home`
       explicitly (rather than relying on the ambient `CODEX_HOME`) means
       this check validates the store real turns will actually use, not a
       completely different, irrelevant one (e.g. an operator's interactive
       shell `CODEX_HOME`).
    2. A real turn also never runs with this process's full `os.environ` --
       only the 7-key allowlist `CodexLaunchPolicy.environment()` forwards
       (notably, no `HOME`). Running this probe under the SAME restricted
       environment (`launch_policy.environment(os.environ)`), rather than
       the full ambient one, means anything the Codex CLI needs outside
       that allowlist fails HERE, at preflight, rather than passing this
       check and then failing on the first real, quota-consuming turn.
    """
    try:
        completed = subprocess.run(
            [str(launch_policy.codex_binary), "login", "status"],
            env=launch_policy.environment(os.environ),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"codex login status could not be run: {error}"
    if completed.returncode != 0:
        detail = completed.stdout.strip() or completed.stderr.strip() or "not authenticated"
        return False, detail
    # The real CLI writes its success message ("Logged in using ChatGPT") to
    # STDERR, not stdout -- confirmed against the real, installed 0.145.0
    # binary. Falling back to stdout only (as the failure branch above
    # already did, correctly) means `completed.stdout.strip()` is empty and
    # this would silently return the literal string "authenticated" instead
    # of the CLI's own report, making any caller-side check for the actual
    # authentication method (ChatGPT vs. an API key) vacuous.
    return True, completed.stdout.strip() or completed.stderr.strip() or "authenticated"


def _codex_launch_environment_clean() -> tuple[bool, str]:
    present = [key for key in _CODEX_FORBIDDEN_ENV_KEYS if os.environ.get(key)]
    if present:
        return False, f"forbidden credentials present in the launch environment: {present}"
    return True, "OPENAI_API_KEY and CODEX_API_KEY are absent"


def _codex_git_state(repo_root: Path) -> tuple[bool, str]:
    try:
        inside = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"git is unavailable: {error}"
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return False, f"{repo_root} is not a git working tree"

    branch = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if branch.returncode != 0:
        return False, "git rev-parse --abbrev-ref HEAD failed"
    current_branch = branch.stdout.strip()
    if current_branch != "main":
        return False, f"expected the main branch checked out, found {current_branch!r}"

    status = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if status.returncode != 0:
        return False, "git status --porcelain failed"
    # Only a genuinely UNTRACKED ("??") line, whose path's leading component
    # exactly matches a documented entry, is excused. A tracked modification,
    # deletion, or rename is never excused regardless of path text -- porcelain
    # v1 renders a staged rename as "R  ORIG -> DEST" in the same path field a
    # raw-string-prefix check would have matched against ORIG alone, hiding a
    # change that actually landed at DEST (which could be anywhere, including
    # inside src/). Matching on the exact leading path component (not a raw
    # string prefix) also refuses a same-prefix sibling name like
    # `.mathloop-personal-notes/`.
    dirty = [
        path_field
        for status_code, path_field in (
            (line[:2], line[3:]) for line in status.stdout.splitlines() if line
        )
        if not (status_code == "??" and _is_documented_untracked_path(path_field))
    ]
    if dirty:
        return False, f"working tree has undocumented changes: {dirty}"
    return True, "git working tree is clean apart from documented operator paths"


def _is_documented_untracked_path(path_field: str) -> bool:
    first_component = PurePosixPath(path_field).parts[0] if path_field else ""
    return first_component in _CODEX_ALLOWED_UNTRACKED_PATH_COMPONENTS


def _codex_worktree_root_writable(worktree_root: Path) -> tuple[bool, str]:
    try:
        worktree_root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=worktree_root):
            pass
    except OSError as error:
        return False, f"worktree root {worktree_root} is not writable: {error}"
    return True, f"{worktree_root} is writable"


def _codex_postgres_available(database_url: str) -> tuple[bool, str]:
    database = Database(database_url)
    try:
        reachable = Repository(database).ping()
    except Exception as error:  # a preflight check must report failure, never itself crash
        return False, f"postgresql is unavailable: {error!r}"
    finally:
        database.close()
    return reachable, "reachable" if reachable else "unreachable"
