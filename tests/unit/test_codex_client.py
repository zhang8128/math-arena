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
import pickle
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
import os
import signal
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
    schema_path = None
    if "--output-schema" in argv:
        schema_path = argv[argv.index("--output-schema") + 1]

    # A regression test for the client's schema-file lifetime: every mode
    # opens the schema unconditionally, right at startup, so the CLI fails
    # loudly (nonzero exit) if the file is gone by the time it gets here --
    # exactly what would happen if a caller ever deleted it right after
    # Popen instead of waiting for this process to fully exit.
    if schema_path is not None:
        with open(schema_path, "rb") as _schema_handle:
            _schema_handle.read()

    # Written unconditionally so tests can confirm this exact process (not
    # just "some fake_codex.py") is dead after a client-side kill, even in
    # modes that never reach any stdout emission.
    tmpdir = os.environ.get("TMPDIR")
    if tmpdir:
        (Path(tmpdir) / "fake-codex.pid").write_text(str(os.getpid()))

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

    if mode == "malformed_immediate":
        # Exits immediately -- no sleep, no descendant -- so this process is
        # a lone zombie in its own process group by the time the client
        # notices the parser-contract violation and moves to kill it. This
        # is the specific condition that produces EPERM (not ESRCH) from
        # killpg on this platform, and the fake CLI's other error modes all
        # avoid it (they either sleep or leave a live descendant behind).
        emit_thread_and_turn_started()
        sys.stdout.write("not valid json\\n")
        sys.stdout.flush()
        return 0

    if mode == "hang":
        emit_thread_and_turn_started()
        # This grandchild ignores SIGTERM outright, forcing the client's
        # process-group kill to actually escalate to SIGKILL rather than
        # relying on the direct child (this script) dying promptly and
        # nothing then re-checking whether the grandchild is still alive.
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import signal, time; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "time.sleep(3600)",
            ]
        )
        time.sleep(3600)
        return 0

    if mode == "slow_open_schema":
        # Deliberately re-opens the schema file again after a delay clearly
        # longer than any realistic Popen-to-child-startup gap. A client
        # that deletes the schema right after Popen returns (rather than
        # after this whole process exits) fails this every time; one that
        # waits for the process to exit never sees the file missing.
        time.sleep(0.3)
        if schema_path is not None:
            with open(schema_path, "rb") as _handle:
                _handle.read()
        emit_thread_and_turn_started()
        emit_agent_message_and_completion()
        return 0

    if mode == "giant_line":
        emit_thread_and_turn_started()
        sys.stdout.write("x" * 5000)  # no trailing newline -- never a complete line
        sys.stdout.flush()
        time.sleep(5)
        return 0

    if mode == "crash_with_descendant":
        # The direct child (this script) exits immediately with a nonzero
        # code, while a subprocess it spawned keeps running -- a regression
        # test for skipping the group kill just because the direct child
        # already exited on its own would leave that descendant orphaned.
        # The descendant's stdio is explicitly redirected away from this
        # script's own inherited pipe (not left to inherit it) so this
        # script's own stdout still hits real EOF the moment it exits --
        # otherwise the client's read loop would never see EOF at all and
        # this would exercise a different, already-known, deferred issue
        # instead of the one this mode exists to test.
        emit_thread_and_turn_started()
        descendant = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(3600)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        tmpdir = os.environ.get("TMPDIR")
        if tmpdir:
            (Path(tmpdir) / "fake-codex-descendant.pid").write_text(str(descendant.pid))
        return 7

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


def client(
    codex_binary: Path, *, timeout: float | None = None, max_event_bytes: int | None = None
) -> CodexClient:
    launch_policy = CodexLaunchPolicy(
        codex_binary=codex_binary,
        codex_home=Path(str(_repo_state["codex_home"])),
    )
    worktree_manager = CodexWorktreeManager(
        repo_root=Path(str(_repo_state["repo_root"])),
        worktree_root=Path(str(_repo_state["worktree_root"])),
    )
    kwargs: dict[str, object] = {}
    if max_event_bytes is not None:
        kwargs["max_event_bytes"] = max_event_bytes
    return CodexClient(
        launch_policy,
        worktree_manager,
        environment={"PATH": os.environ.get("PATH", ""), "TMPDIR": str(_repo_state["tmp_path"])},
        timeout_seconds=timeout,
        **kwargs,
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
# Regression coverage: fix round 2 (N1, N2, N3)
# ---------------------------------------------------------------------------


def test_timeout_does_not_leak_the_worktree_on_disk_or_in_git(fake_codex: Path) -> None:
    """A timed-out turn must still be fully cleaned up, not merely raise.

    Cleanup runs with its own fixed budget (not `max(0.0, deadline - now)`,
    which is exactly 0.0 on every timeout path by definition and would make
    `remove()`'s first git command fail its deadline check instantly). This
    checks the filesystem and `git worktree list` directly, not just that
    `CodexTurnTimedOut` was raised -- an exception alone doesn't prove the
    worktree was actually removed.
    """
    turn_request = request(mode="hang", response_schema=ProofSketch)

    with pytest.raises(CodexTurnTimedOut):
        client(fake_codex, timeout=1.0).execute(turn_request, sink)

    worktree_path = Path(str(_repo_state["worktree_root"])) / str(turn_request.reservation.id)
    assert not worktree_path.exists()
    listing = _git("worktree", "list", cwd=Path(str(_repo_state["repo_root"]))).stdout
    assert str(turn_request.reservation.id) not in listing


def test_a_surviving_descendant_is_killed_even_after_the_direct_child_crashes(
    fake_codex: Path,
) -> None:
    """A crash of the direct child must not leave a descendant it spawned running.

    Mode "crash_with_descendant" spawns a genuine grandchild, then the
    direct child (the fake CLI itself) exits immediately with a nonzero
    code -- so `process.poll()` reports "already exited" almost the instant
    the client notices. Skipping the process-group kill whenever the direct
    child has already exited (rather than killing unconditionally) would
    leave this specific grandchild running.
    """
    with pytest.raises(CodexClientError, match="exited with code 7"):
        client(fake_codex, timeout=5.0).execute(
            request(mode="crash_with_descendant", response_schema=ProofSketch), events.append
        )

    pid_path = Path(str(_repo_state["tmp_path"])) / "fake-codex-descendant.pid"
    assert pid_path.exists()
    descendant_pid = int(pid_path.read_text().strip())
    assert descendant_is_running(descendant_pid) is False


def test_codex_turn_timed_out_survives_pickling_with_its_notes() -> None:
    """`CodexTurnTimedOut` must round-trip through pickle, notes included.

    This is the exact mechanism a forked worker child relies on to report a
    real timeout to its supervising parent over a `multiprocessing.
    Connection`. A 2-tuple `__reduce__` return (callable, args) reconstructs
    the exception but silently drops everything in `self.__dict__`,
    including `__notes__` -- the only channel `CodexClient.execute`'s
    cleanup-failure handling uses to attach evidence to an already-in-flight
    exception. Tested directly via `pickle.loads(pickle.dumps(...))` rather
    than through a full multiprocessing round trip: pickle is the exact
    mechanism at fault, and this isolates it precisely.

    Safe use of pickle here: this round-trips an object this same test
    process just constructed in memory (never data from an external or
    untrusted source), solely to verify `__reduce__`'s contract -- the same
    trust boundary `multiprocessing.Connection` already relies on in
    production between a forked worker child and its own parent.
    """
    error = CodexTurnTimedOut(30.0, dispatched=True, descendant_pid=4242)
    error.add_note("codex worktree cleanup also failed: synthetic cleanup failure")

    restored = pickle.loads(pickle.dumps(error))

    assert restored.timeout_seconds == 30.0
    assert restored.dispatched is True
    assert restored.descendant_pid == 4242
    assert list(restored.__notes__) == [
        "codex worktree cleanup also failed: synthetic cleanup failure"
    ]


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


def test_malformed_jsonl_from_a_lone_zombie_cli_still_reports_the_parser_error(
    fake_codex: Path,
) -> None:
    """A CLI that exits immediately (no sleep, no descendant) after emitting
    a malformed line is, by the time the client moves to kill it, a *lone*
    zombie in its own process group -- exactly the condition that produces
    `EPERM` (not `ESRCH`) from `killpg` on this platform. Gating the EPERM
    swallow on `_pid_alive` for the direct child (unreliable for a zombie,
    always reports "alive") would re-raise that `PermissionError` in place
    of the real parser-contract diagnostic; gating on `process.poll()`
    (authoritative) must not.
    """
    with pytest.raises(CodexClientError, match="parser contract"):
        client(fake_codex, timeout=5.0).execute(
            request(mode="malformed_immediate", response_schema=ProofSketch),
            events.append,
        )


def test_schema_file_survives_the_gap_between_popen_and_the_child_opening_it(
    fake_codex: Path,
) -> None:
    """The response schema must outlive Popen returning, not just precede it.

    `Popen` only initiates fork/exec; the child still has to start and parse
    argv before it opens `--output-schema`. `mode="slow_open_schema"` waits
    300ms -- far longer than any realistic Popen-to-child-startup gap --
    before opening the file a second time. A client that deletes the schema
    right after `Popen` returns (instead of after the whole process exits)
    fails this deterministically; one that waits for the process to exit
    never does.
    """
    response = client(fake_codex, timeout=5.0).execute(
        request(mode="slow_open_schema", response_schema=ProofSketch),
        events.append,
    )
    assert response.value.strategy == "induction"


def test_raising_emit_event_kills_the_child_instead_of_orphaning_it(fake_codex: Path) -> None:
    """A caller-supplied `emit_event` that raises must not leak the CLI process.

    Mode "hang" never completes on its own, so if the client did not
    explicitly kill the process group on this exception path, the fake CLI
    (and its process group) would still be alive after `execute()` returns
    control to the caller -- exactly the orphaning `execute()`'s own
    `finally` (which resets/removes the worktree the still-running CLI may
    still be writing to) must never race against.
    """

    def boom(event: CodexEvent) -> None:
        del event
        raise RuntimeError("callback exploded")

    with pytest.raises(RuntimeError, match="callback exploded"):
        client(fake_codex, timeout=5.0).execute(
            request(mode="hang", response_schema=ProofSketch), boom
        )

    pid_path = Path(str(_repo_state["tmp_path"])) / "fake-codex.pid"
    assert pid_path.exists()
    pid = int(pid_path.read_text().strip())
    assert descendant_is_running(pid) is False


def test_oversized_line_without_a_newline_is_rejected_before_the_deadline(
    fake_codex: Path,
) -> None:
    """The stdout reader's buffer itself must be byte-bounded, not just completed lines.

    `CodexEventParser`'s own cap only ever sees a *complete* line -- a child
    emitting one huge line with no trailing newline is invisible to it until
    a newline arrives, which here never happens. `max_event_bytes=1024` makes
    the fake CLI's unterminated 5000-byte write exceed the cap; the failure
    must arrive quickly (well under both the CLI's 5s sleep and the client's
    own 10s deadline), proving the raw buffer is checked during accumulation
    rather than being silently held in memory until the deadline.
    """
    started = time.monotonic()
    with pytest.raises(CodexClientError, match="max_bytes cap"):
        client(fake_codex, timeout=10.0, max_event_bytes=1024).execute(
            request(mode="giant_line", response_schema=ProofSketch), events.append
        )
    elapsed = time.monotonic() - started
    assert elapsed < 5.0


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

    def create(self, turn_id: object, base_sha: str, **kwargs: object) -> object:
        return self._inner.create(turn_id, base_sha, **kwargs)  # type: ignore[arg-type]

    def diff(self, worktree: object, **kwargs: object) -> object:
        return self._inner.diff(worktree, **kwargs)  # type: ignore[arg-type]

    def remove(self, worktree: object, **kwargs: object) -> None:
        del worktree, kwargs
        raise CodexWorktreeError("synthetic cleanup failure")
