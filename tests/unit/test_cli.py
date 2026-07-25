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

# ---------------------------------------------------------------------------
# `codex init` preflight checks -- unit-level.
#
# Every check below is exercised with a fake `subprocess.run` (or a real,
# throwaway git repository under `tmp_path`): none of these tests ever shells
# out to a real `codex` binary or requires a real ChatGPT login, even though
# a real `codex` binary happens to be installed on this machine's PATH. A
# test suite that only passed because of that would be a broken test suite.
# ---------------------------------------------------------------------------


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


def test_codex_help_lists_operator_subcommands() -> None:
    result = CliRunner().invoke(app, ["codex", "--help"])

    assert result.exit_code == 0
    for command in ("init", "start", "status", "pause", "resume", "drain", "report"):
        assert command in result.output


def _fake_run(returncode: int, stdout: str = "", stderr: str = "") -> object:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

    return run


def test_codex_cli_version_parses_the_reported_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module.subprocess, "run", _fake_run(0, stdout="codex-cli 0.146.2\n")
    )

    ok, detail = cli_module._codex_cli_version(Path("codex"))

    assert ok is True
    assert detail == "0.146.2"


def test_codex_cli_version_reports_failure_when_binary_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        raise FileNotFoundError(f"no such file: {command[0]}")

    monkeypatch.setattr(cli_module.subprocess, "run", run)

    ok, detail = cli_module._codex_cli_version(Path("codex"))

    assert ok is False
    assert "could not be run" in detail


def test_codex_cli_version_reports_failure_on_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_module.subprocess, "run", _fake_run(1, stderr="not found"))

    ok, _detail = cli_module._codex_cli_version(Path("codex"))

    assert ok is False


@pytest.mark.parametrize(
    ("reported", "minimum", "expected"),
    [
        ("0.145.0", "0.145.0", True),
        ("0.146.0", "0.145.0", True),
        ("0.145.1", "0.145.0", True),
        ("0.144.9", "0.145.0", False),
        ("0.145.0", "0.145.1", False),
    ],
)
def test_codex_version_at_least_compares_numerically_not_lexically(
    reported: str, minimum: str, expected: bool
) -> None:
    assert cli_module._codex_version_at_least(reported, minimum) is expected


def test_codex_init_reports_an_old_cli_version_as_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_module.subprocess, "run", _fake_run(0, stdout="codex-cli 0.100.0\n"))

    ok, detail = cli_module._codex_cli_version(Path("codex"))

    assert ok is True
    assert cli_module._codex_version_at_least(detail, "0.145.0") is False


def test_codex_login_status_reports_absent_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module.subprocess, "run", _fake_run(1, stdout="Not logged in.\n")
    )

    ok, detail = cli_module._codex_login_status(Path("codex"))

    assert ok is False
    assert "Not logged in" in detail


def test_codex_login_status_reports_authenticated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module.subprocess, "run", _fake_run(0, stdout="Logged in with ChatGPT\n")
    )

    ok, detail = cli_module._codex_login_status(Path("codex"))

    assert ok is True
    assert "ChatGPT" in detail


@pytest.mark.parametrize("forbidden_key", ["OPENAI_API_KEY", "CODEX_API_KEY"])
def test_codex_launch_environment_clean_detects_forbidden_credentials(
    forbidden_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(forbidden_key, "sk-should-never-be-here")

    ok, detail = cli_module._codex_launch_environment_clean()

    assert ok is False
    assert forbidden_key in detail


def test_codex_launch_environment_clean_when_credentials_are_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)

    ok, _detail = cli_module._codex_launch_environment_clean()

    assert ok is True


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=path)
    _git("config", "user.email", "cli-test@example.com", cwd=path)
    _git("config", "user.name", "CLI Test", cwd=path)
    (path / "README.md").write_text("seed\n")
    _git("add", "-A", cwd=path)
    _git("commit", "-q", "-m", "seed", cwd=path)


def test_codex_git_state_rejects_when_not_a_work_tree(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()

    ok, detail = cli_module._codex_git_state(not_a_repo)

    assert ok is False
    assert "not a git working tree" in detail


def test_codex_git_state_rejects_dirty_checkout_outside_the_allowlist(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "README.md").write_text("dirtied\n")

    ok, detail = cli_module._codex_git_state(repo)

    assert ok is False
    assert "README.md" in detail


def test_codex_git_state_accepts_documented_operator_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / ".mathloop").mkdir()
    (repo / ".mathloop" / "state.json").write_text("{}\n")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.json").write_text("{}\n")

    ok, _detail = cli_module._codex_git_state(repo)

    assert ok is True


def test_codex_worktree_root_writable_reports_success(tmp_path: Path) -> None:
    worktree_root = tmp_path / "codex-worktrees"

    ok, detail = cli_module._codex_worktree_root_writable(worktree_root)

    assert ok is True
    assert str(worktree_root) in detail
    assert worktree_root.is_dir()


def test_codex_worktree_root_writable_detects_a_path_collision(tmp_path: Path) -> None:
    blocked = tmp_path / "codex-worktrees"
    blocked.write_text("a plain file, not a directory\n")

    ok, detail = cli_module._codex_worktree_root_writable(blocked)

    assert ok is False
    assert "not writable" in detail
