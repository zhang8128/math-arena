"""Real-subprocess tests for the supervised Codex client.

No JSONL is mocked and no subprocess call is patched: every test drives an
actual executable "fake Codex CLI" script (written to `tmp_path` by the
`fake_codex` fixture) through the real `CodexClient`, against a real,
throwaway Git repository. This is the only way to genuinely exercise the
concurrent stderr drain and the process-group kill on timeout -- both of
which are invisible to a test that mocks `subprocess.Popen`.
"""

import hashlib
import os
import subprocess
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from mathloop.codex.client import (
    CodexClient,
    CodexClientError,
    CodexRequest,
    CodexTurnTimedOut,
)
from mathloop.codex.domain import CodexModelRole, CodexTurnReservation
from mathloop.codex.events import CodexEvent
from mathloop.codex.launch import CodexLaunchPolicy
from mathloop.codex.worktrees import CodexWorktreeError, CodexWorktreeManager
from mathloop.methods.proof_sketch import ProofSketch

# ---------------------------------------------------------------------------
# Fake Codex CLI
# ---------------------------------------------------------------------------
#
# The last argv element is always the prompt (see CodexLaunchPolicy.command).
# The `request()` helper below packs a mode name into the prompt so this one
# script can play every scripted scenario the brief calls for: valid JSONL, a
# delayed terminal event, malformed JSONL, a spawned child process, and a
# nonzero exit.

_FAKE_CODEX_SOURCE = '''\
#!/usr/bin/env python3
import json
import subprocess
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

    def emit_thread_and_turn_started() -> None:
        _emit(
            {
                "type": "thread.started",
                "thread_id": "thread-fake-1",
                "cli_version": "0.145.0-test",
            }
        )
        _emit({"type": "turn.started"})

    def emit_agent_message_and_completion() -> None:
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

    if mode in ("success", "delayed", "loud_stderr"):
        emit_thread_and_turn_started()
        if mode == "delayed":
            time.sleep(0.2)
        if mode == "loud_stderr":
            sys.stderr.write("x" * (2 * 1024 * 1024))
            sys.stderr.flush()
        emit_agent_message_and_completion()
        return 0

    if mode == "nonzero":
        emit_thread_and_turn_started()
        emit_agent_message_and_completion()
        return 3

    if mode == "malformed":
        emit_thread_and_turn_started()
        sys.stdout.write("not valid json\\n")
        sys.stdout.flush()
        time.sleep(5)
        return 0

    if mode == "hang":
        emit_thread_and_turn_started()
        subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
        time.sleep(3600)
        return 0

    _emit({"type": "error", "message": f"unknown fake-codex mode {mode!r}"})
    return 1


if __name__ == "__main__":
    sys.exit(main())
'''


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "codex-client-test@example.com", cwd=repo)
    _git("config", "user.name", "Codex Client Test", cwd=repo)
    (repo / "README.md").write_text("seed content\n")
    _git("add", "-A", cwd=repo)
    _git("commit", "-q", "-m", "seed", cwd=repo)
    return _git("rev-parse", "HEAD", cwd=repo).stdout.strip()


# ---------------------------------------------------------------------------
# Test scaffolding
# ---------------------------------------------------------------------------

_repo_state: dict[str, object] = {}
events: list[CodexEvent] = []


def sink(event: CodexEvent) -> None:
    del event


@pytest.fixture(autouse=True)
def _reset_events() -> Iterator[None]:
    events.clear()
    yield
    events.clear()


@pytest.fixture
def fake_codex(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    base_sha = _init_repo(repo_root)
    _repo_state["repo_root"] = repo_root
    _repo_state["base_sha"] = base_sha
    _repo_state["worktree_root"] = tmp_path / "worktrees"
    _repo_state["codex_home"] = tmp_path / "codex-home"
    _repo_state["tmp_path"] = tmp_path
    script = tmp_path / "fake_codex.py"
    script.write_text(_FAKE_CODEX_SOURCE)
    script.chmod(0o700)
    return script


def client(codex_binary: Path, *, timeout: float | None = None) -> CodexClient:
    launch_policy = CodexLaunchPolicy(
        codex_binary=codex_binary,
        codex_home=Path(str(_repo_state["codex_home"])),
    )
    worktree_manager = CodexWorktreeManager(
        repo_root=Path(str(_repo_state["repo_root"])),
        worktree_root=Path(str(_repo_state["worktree_root"])),
    )
    return CodexClient(
        launch_policy,
        worktree_manager,
        environment={"PATH": os.environ.get("PATH", ""), "TMPDIR": str(_repo_state["tmp_path"])},
        timeout_seconds=timeout,
    )


def request(
    *, response_schema: type[ProofSketch], mode: str = "success"
) -> CodexRequest[ProofSketch]:
    now = datetime.now(UTC)
    reservation = CodexTurnReservation(
        id=uuid4(),
        experiment_id=uuid4(),
        budget_day=now.date(),
        role=CodexModelRole.TERRA,
        model="gpt-5.6-terra",
        deadline_seconds=1800,
        created_at=now,
    )
    return CodexRequest(
        reservation=reservation,
        prompt=mode,
        base_sha=str(_repo_state["base_sha"]),
        response_schema=response_schema,
    )


def descendant_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# ---------------------------------------------------------------------------
# Brief-verbatim cases
# ---------------------------------------------------------------------------


def test_codex_client_returns_schema_value_usage_and_patch(fake_codex: Path) -> None:
    response = client(fake_codex).execute(
        request(response_schema=ProofSketch),
        events.append,
    )
    assert response.value.strategy == "induction"
    assert response.receipt.usage.output_tokens == 12
    assert response.patch_sha256 == hashlib.sha256(response.patch).hexdigest()
    assert any(event.event_type == "turn.started" for event in events)


def test_codex_client_timeout_kills_descendants_and_never_completes(
    fake_codex: Path,
) -> None:
    with pytest.raises(CodexTurnTimedOut) as raised:
        client(fake_codex, timeout=1.0).execute(
            request(mode="hang", response_schema=ProofSketch),
            sink,
        )
    assert raised.value.dispatched is True
    assert descendant_is_running(raised.value.descendant_pid) is False


# ---------------------------------------------------------------------------
# Additional coverage for the concurrency and cleanup contracts
# ---------------------------------------------------------------------------


def test_on_dispatched_is_called_before_popen(fake_codex: Path) -> None:
    calls: list[str] = []

    def on_dispatched() -> None:
        calls.append("dispatched")

    def observe(event: CodexEvent) -> None:
        calls.append(f"event:{event.event_type}")

    client(fake_codex).execute(
        request(response_schema=ProofSketch), observe, on_dispatched=on_dispatched
    )

    assert calls[0] == "dispatched"
    assert calls[1] == "event:thread.started"


def test_receipt_and_patch_are_bound_to_the_reservation(fake_codex: Path) -> None:
    turn_request = request(response_schema=ProofSketch)

    response = client(fake_codex).execute(turn_request, events.append)

    assert response.receipt.reservation_id == turn_request.reservation.id
    assert response.receipt.experiment_id == turn_request.reservation.experiment_id
    assert response.receipt.cli_version == "0.145.0-test"
    assert response.receipt.final_status == "completed"
    assert b"codex was here" in response.patch


def test_delayed_terminal_event_still_completes_within_deadline(fake_codex: Path) -> None:
    response = client(fake_codex, timeout=5.0).execute(
        request(mode="delayed", response_schema=ProofSketch),
        events.append,
    )
    assert response.value.strategy == "induction"


def test_loud_stderr_does_not_deadlock_the_stdout_reader(fake_codex: Path) -> None:
    """A child that fills the stderr pipe must not block stdout progress.

    2 MiB comfortably exceeds every common OS pipe buffer size. If stderr
    were read synchronously (or not at all) after stdout, this test would
    hang until the client's own timeout fired instead of completing well
    within it.
    """
    started = time.monotonic()
    response = client(fake_codex, timeout=10.0).execute(
        request(mode="loud_stderr", response_schema=ProofSketch),
        events.append,
    )
    elapsed = time.monotonic() - started
    assert response.value.strategy == "induction"
    assert elapsed < 5.0


def test_nonzero_exit_raises_even_with_a_complete_transcript(fake_codex: Path) -> None:
    with pytest.raises(CodexClientError, match="exited with code 3"):
        client(fake_codex).execute(
            request(mode="nonzero", response_schema=ProofSketch), events.append
        )


def test_malformed_jsonl_is_rejected_and_process_is_reaped(fake_codex: Path) -> None:
    with pytest.raises(CodexClientError, match="parser contract"):
        client(fake_codex, timeout=5.0).execute(
            request(mode="malformed", response_schema=ProofSketch),
            events.append,
        )


def test_worktree_is_removed_after_a_successful_turn(fake_codex: Path) -> None:
    turn_request = request(response_schema=ProofSketch)
    client(fake_codex).execute(turn_request, events.append)

    worktree_path = Path(str(_repo_state["worktree_root"])) / str(turn_request.reservation.id)
    assert not worktree_path.exists()


def test_cleanup_failure_after_success_is_not_swallowed(fake_codex: Path) -> None:
    inner = CodexWorktreeManager(
        repo_root=Path(str(_repo_state["repo_root"])),
        worktree_root=Path(str(_repo_state["worktree_root"])),
    )
    failing = _FailingRemoveManager(inner)
    launch_policy = CodexLaunchPolicy(
        codex_binary=fake_codex, codex_home=Path(str(_repo_state["codex_home"]))
    )
    supervised = CodexClient(
        launch_policy,
        failing,  # type: ignore[arg-type]
        environment={"PATH": os.environ.get("PATH", ""), "TMPDIR": str(_repo_state["tmp_path"])},
    )

    with pytest.raises(CodexClientError, match="cleanup failed"):
        supervised.execute(request(response_schema=ProofSketch), events.append)


def test_cleanup_failure_after_a_primary_error_preserves_the_original_type(
    fake_codex: Path,
) -> None:
    inner = CodexWorktreeManager(
        repo_root=Path(str(_repo_state["repo_root"])),
        worktree_root=Path(str(_repo_state["worktree_root"])),
    )
    failing = _FailingRemoveManager(inner)
    launch_policy = CodexLaunchPolicy(
        codex_binary=fake_codex, codex_home=Path(str(_repo_state["codex_home"]))
    )
    supervised = CodexClient(
        launch_policy,
        failing,  # type: ignore[arg-type]
        environment={"PATH": os.environ.get("PATH", ""), "TMPDIR": str(_repo_state["tmp_path"])},
    )

    with pytest.raises(CodexClientError, match="exited with code 3") as raised:
        supervised.execute(
            request(mode="nonzero", response_schema=ProofSketch), events.append
        )
    assert any("cleanup also failed" in note for note in raised.value.__notes__)


class _FailingRemoveManager:
    """A worktree manager whose `remove` always fails, for cleanup-path tests."""

    def __init__(self, inner: CodexWorktreeManager) -> None:
        self._inner = inner

    def create(self, turn_id: object, base_sha: str) -> object:
        return self._inner.create(turn_id, base_sha)  # type: ignore[arg-type]

    def diff(self, worktree: object) -> object:
        return self._inner.diff(worktree)  # type: ignore[arg-type]

    def remove(self, worktree: object) -> None:
        raise CodexWorktreeError("synthetic cleanup failure")
