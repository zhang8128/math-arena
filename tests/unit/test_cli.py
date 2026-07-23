import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from typer.testing import CliRunner

import mathloop.cli as cli_module
from mathloop.cli import app
from mathloop.provenance import SAGE_IMAGE_DIGEST


def test_cli_help_is_available() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "mathloop" in result.output.lower()
    for command in ("db-init", "ingest", "schedule", "worker", "run", "report"):
        assert command in result.output


@pytest.mark.parametrize(("returncode", "available"), [(0, True), (1, False)])
def test_sage_preflight_inspects_the_exact_runtime_image_identity(
    returncode: int,
    available: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def inspect(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, returncode)

    monkeypatch.setattr(cli_module.subprocess, "run", inspect)

    assert cli_module._sage_image_available() is available
    assert calls == [
        (
            ["docker", "image", "inspect", SAGE_IMAGE_DIGEST],
            {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "check": False,
                "timeout": 5,
            },
        )
    ]


def test_ingest_reports_repeated_snapshots_as_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_ids = (uuid4(), uuid4())
    repository = SimpleNamespace(count_events=lambda event_type: 7)

    @contextmanager
    def fake_runtime() -> Iterator[SimpleNamespace]:
        yield SimpleNamespace(
            repository=repository,
            ingest=lambda path: problem_ids,
            ingest_with_result=lambda path: SimpleNamespace(
                problem_ids=problem_ids,
                processed=2,
                inserted=0,
                existing=2,
            ),
        )

    monkeypatch.setattr(cli_module, "_runtime", fake_runtime)

    result = CliRunner().invoke(app, ["ingest", "repeated.jsonl"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "processed": 2,
        "inserted": 0,
        "existing": 2,
        "problem_ids": [str(problem_id) for problem_id in problem_ids],
    }


def test_ingest_reports_actual_insert_and_existing_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem_ids = (uuid4(), uuid4(), uuid4())

    class CountingRepository:
        discovered = 11

        def count_events(self, event_type: str) -> int:
            assert event_type == "problem.discovered"
            return self.discovered

    repository = CountingRepository()

    def ingest(path: Path) -> tuple[UUID, ...]:
        assert path == Path("mixed.jsonl")
        repository.discovered += 5
        return problem_ids

    @contextmanager
    def fake_runtime() -> Iterator[SimpleNamespace]:
        yield SimpleNamespace(
            repository=repository,
            ingest=ingest,
            ingest_with_result=lambda path: SimpleNamespace(
                problem_ids=problem_ids,
                processed=3,
                inserted=2,
                existing=1,
            ),
        )

    monkeypatch.setattr(cli_module, "_runtime", fake_runtime)

    result = CliRunner().invoke(app, ["ingest", "mixed.jsonl"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "processed": 3,
        "inserted": 2,
        "existing": 1,
        "problem_ids": [str(problem_id) for problem_id in problem_ids],
    }
