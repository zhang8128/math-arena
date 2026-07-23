"""Operator CLI with explicit local and external authority boundaries."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Event
from uuid import UUID

import typer

from mathloop.artifacts import ArtifactStore
from mathloop.config import Settings
from mathloop.provenance import SAGE_IMAGE_DIGEST
from mathloop.runtime import Runtime, build_runtime
from mathloop.storage.db import Database
from mathloop.storage.repository import Repository

app = typer.Typer(help="Mathloop autonomous mathematics solver ecology.")


@contextmanager
def _runtime(*, api_enabled: bool = False, initialize: bool = False) -> Iterator[Runtime]:
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
