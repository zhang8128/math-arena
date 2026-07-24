"""Supervised Codex CLI execution: one turn, one process group, one deadline.

`CodexClient` is the only place a Codex CLI child process is ever started. It
turns a `CodexRequest` into a `CodexResponse` by: creating a disposable
worktree (Task 3), launching `codex exec` with the fail-closed launch policy
(Task 1) inside a fresh process group, streaming its `--json` event lines
through the bounded parser (Task 2), and handing the result to the caller for
durable ledger persistence (Task 4). Nothing here reads or writes the turn
ledger directly -- the caller supplies `emit_event` and `on_dispatched`
callbacks for that, which keeps this module free of any database dependency
and lets it run identically inside a forked worker child or a bare test.

A single absolute deadline (computed once, before the worktree is even
created) bounds every phase: worktree creation, schema write, process start,
event reads, process wait, patch capture, and worktree cleanup. There is no
per-stage timeout to accidentally exceed the turn's real budget.
"""

import json
import os
import select
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from pydantic import BaseModel, ValidationError

from mathloop.codex.domain import CodexTurnReceipt, CodexTurnReservation
from mathloop.codex.events import CodexEvent, CodexEventError, CodexEventParser
from mathloop.codex.launch import CodexLaunchPolicy
from mathloop.codex.worktrees import CodexWorktree, CodexWorktreeError, CodexWorktreeManager

_DEFAULT_MAX_EVENT_BYTES = 16 * 1024 * 1024
_DEFAULT_MAX_STDERR_BYTES = 1 * 1024 * 1024
_READ_CHUNK_BYTES = 65536
_POLL_SECONDS = 0.05
_REAP_GRACE_SECONDS = 0.5


class CodexClientError(RuntimeError):
    """The Codex CLI process or its output violated the supervised contract."""


class CodexTurnTimedOut(TimeoutError):
    """The turn's one absolute deadline elapsed before a terminal event arrived.

    `dispatched` reflects whether a `turn.started` event was ever observed on
    the JSONL stream -- this is what lets a caller record a durable, no-retry
    turn outcome instead of silently discarding evidence of a started turn.
    `descendant_pid` is the pid of a process found in the killed Codex
    process group (a subprocess the CLI itself spawned, if any, else the CLI
    process itself), confirmed dead by the time this is raised.
    """

    def __init__(self, timeout_seconds: float, *, dispatched: bool, descendant_pid: int) -> None:
        super().__init__(f"codex turn exceeded its {timeout_seconds}s deadline")
        self.timeout_seconds = timeout_seconds
        self.dispatched = dispatched
        self.descendant_pid = descendant_pid


@dataclass(frozen=True)
class CodexRequest[T: BaseModel]:
    """One supervised Codex turn: a reservation-bound prompt and schema."""

    reservation: CodexTurnReservation
    prompt: str
    base_sha: str
    response_schema: type[T]


@dataclass(frozen=True)
class CodexResponse[T: BaseModel]:
    """The schema-constrained result of a completed Codex turn."""

    value: T
    receipt: CodexTurnReceipt
    patch: bytes
    patch_sha256: str


class CodexClient:
    """Runs one supervised `codex exec` turn per `execute` call."""

    def __init__(
        self,
        launch_policy: CodexLaunchPolicy,
        worktree_manager: CodexWorktreeManager,
        *,
        environment: Mapping[str, str] | None = None,
        timeout_seconds: float | None = None,
        max_event_bytes: int = _DEFAULT_MAX_EVENT_BYTES,
        max_stderr_bytes: int = _DEFAULT_MAX_STDERR_BYTES,
    ) -> None:
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_event_bytes < 1:
            raise ValueError("max_event_bytes must be a positive integer")
        if max_stderr_bytes < 1:
            raise ValueError("max_stderr_bytes must be a positive integer")
        self._launch_policy = launch_policy
        self._worktree_manager = worktree_manager
        self._environment_source = dict(environment if environment is not None else os.environ)
        self._timeout_seconds = timeout_seconds
        self._max_event_bytes = max_event_bytes
        self._max_stderr_bytes = max_stderr_bytes

    def execute[T: BaseModel](
        self,
        request: CodexRequest[T],
        emit_event: Callable[[CodexEvent], None],
        *,
        on_dispatched: Callable[[], None] | None = None,
    ) -> CodexResponse[T]:
        timeout = (
            self._timeout_seconds
            if self._timeout_seconds is not None
            else float(request.reservation.deadline_seconds)
        )
        deadline = time.monotonic() + timeout
        worktree = self._worktree_manager.create(request.reservation.id, request.base_sha)
        primary_error: BaseException | None = None
        response: CodexResponse[T] | None = None
        try:
            response = self._run_turn(
                request, emit_event, on_dispatched, worktree, deadline, timeout
            )
        except BaseException as error:
            primary_error = error
        finally:
            try:
                self._worktree_manager.remove(worktree)
            except CodexWorktreeError as cleanup_error:
                if primary_error is not None:
                    # The primary error already explains what went wrong; a
                    # cleanup failure on top of that must never replace it as
                    # the exception the caller sees (that would mask genuine
                    # evidence of a dispatched-or-not turn), but it also must
                    # never be swallowed, so it rides along as a note.
                    primary_error.add_note(
                        f"codex worktree cleanup also failed: {cleanup_error}"
                    )
                else:
                    primary_error = CodexClientError(
                        f"codex worktree cleanup failed after a successful turn: {cleanup_error}"
                    )
                    primary_error.__cause__ = cleanup_error
        if primary_error is not None:
            raise primary_error
        assert response is not None
        return response

    def _run_turn[T: BaseModel](
        self,
        request: CodexRequest[T],
        emit_event: Callable[[CodexEvent], None],
        on_dispatched: Callable[[], None] | None,
        worktree: CodexWorktree,
        deadline: float,
        timeout: float,
    ) -> CodexResponse[T]:
        schema_path = self._write_schema(request.response_schema)
        try:
            argv = self._launch_policy.command(
                model=request.reservation.model,
                worktree=worktree.path,
                schema=schema_path,
                prompt=request.prompt,
            )
            env = self._launch_policy.environment(self._environment_source)
            if on_dispatched is not None:
                on_dispatched()
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                bufsize=0,
                start_new_session=True,
                env=env,
                shell=False,
            )
        finally:
            schema_path.unlink(missing_ok=True)

        assert process.stdout is not None
        assert process.stderr is not None
        stderr_chunks: list[bytes] = []
        stderr_thread = threading.Thread(
            target=_drain_stderr,
            args=(process.stderr, stderr_chunks, self._max_stderr_bytes),
            daemon=True,
        )
        stderr_thread.start()

        parser = CodexEventParser(max_bytes=self._max_event_bytes)
        cli_version: str | None = None
        stdout_fd = process.stdout.fileno()
        buffer = bytearray()
        while True:
            try:
                line = _read_line(stdout_fd, buffer, deadline)
            except TimeoutError:
                descendant_pid = _kill_process_group(process)
                stderr_thread.join(timeout=_REAP_GRACE_SECONDS)
                raise CodexTurnTimedOut(
                    timeout, dispatched=parser.dispatched, descendant_pid=descendant_pid
                ) from None
            if line is None:
                break
            try:
                event = parser.feed(line)
            except CodexEventError as error:
                descendant_pid = _kill_process_group(process)
                stderr_thread.join(timeout=_REAP_GRACE_SECONDS)
                raise CodexClientError(
                    f"codex event stream violated the parser contract: {error}"
                ) from error
            if event.event_type == "thread.started":
                reported_version = event.payload.get("cli_version")
                if isinstance(reported_version, str) and reported_version:
                    cli_version = reported_version
            emit_event(event)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            descendant_pid = _kill_process_group(process)
            stderr_thread.join(timeout=_REAP_GRACE_SECONDS)
            raise CodexTurnTimedOut(
                timeout, dispatched=parser.dispatched, descendant_pid=descendant_pid
            )
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            descendant_pid = _kill_process_group(process)
            stderr_thread.join(timeout=_REAP_GRACE_SECONDS)
            raise CodexTurnTimedOut(
                timeout, dispatched=parser.dispatched, descendant_pid=descendant_pid
            ) from None
        stderr_thread.join(timeout=max(0.0, deadline - time.monotonic()))

        if returncode != 0:
            tail = b"".join(stderr_chunks)[-2000:]
            raise CodexClientError(f"codex exited with code {returncode}; stderr tail: {tail!r}")

        try:
            transcript = parser.finish()
        except CodexEventError as error:
            raise CodexClientError(f"codex event stream ended incompletely: {error}") from error
        if transcript.terminal_type != "turn.completed":
            raise CodexClientError(
                f"codex turn ended with a non-success terminal event {transcript.terminal_type!r}"
            )
        if transcript.final_message is None or transcript.usage is None:
            raise CodexClientError("codex turn completed without a final message or usage")
        if cli_version is None:
            raise CodexClientError(
                "codex thread.started event did not report a non-empty 'cli_version'"
            )
        try:
            value = request.response_schema.model_validate_json(transcript.final_message)
        except ValidationError as error:
            raise CodexClientError(
                f"codex final agent message did not match the response schema: {error}"
            ) from error

        patch = self._worktree_manager.diff(worktree)
        receipt = CodexTurnReceipt(
            reservation_id=request.reservation.id,
            experiment_id=request.reservation.experiment_id,
            thread_id=transcript.thread_id,
            model=request.reservation.model,
            cli_version=cli_version,
            usage=transcript.usage,
            final_status="completed",
        )
        return CodexResponse(
            value=value,
            receipt=receipt,
            patch=patch.content,
            patch_sha256=patch.sha256,
        )

    @staticmethod
    def _write_schema(response_schema: type[BaseModel]) -> Path:
        descriptor, raw_path = tempfile.mkstemp(prefix="codex-schema-", suffix=".json")
        path = Path(raw_path)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(json.dumps(response_schema.model_json_schema()).encode())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return path


def _read_line(fd: int, buffer: bytearray, deadline: float) -> bytes | None:
    """Return the next full line (including its trailing `\\n`), or `None` at EOF.

    Blocks only in bounded `select` polls against the absolute `deadline`, so a
    hung child never wedges the caller past its turn budget.
    """
    while True:
        newline_index = buffer.find(b"\n")
        if newline_index != -1:
            line = bytes(buffer[: newline_index + 1])
            del buffer[: newline_index + 1]
            return line
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("codex stdout read exceeded the turn deadline")
        ready, _, _ = select.select([fd], [], [], min(remaining, _POLL_SECONDS))
        if not ready:
            continue
        chunk = os.read(fd, _READ_CHUNK_BYTES)
        if chunk == b"":
            if buffer:
                line = bytes(buffer)
                buffer.clear()
                return line
            return None
        buffer.extend(chunk)


def _drain_stderr(stream: IO[bytes], sink: list[bytes], cap_bytes: int) -> None:
    """Continuously read `stream` to prevent the pipe buffer from filling.

    A child that fills its stderr pipe and blocks on the next write would
    otherwise deadlock the whole turn, since the parent is busy reading
    stdout. Only the first `cap_bytes` are retained (for error messages); the
    rest is read and discarded to keep draining.
    """
    collected = 0
    while True:
        chunk = stream.read(_READ_CHUNK_BYTES)
        if not chunk:
            return
        if collected < cap_bytes:
            take = chunk[: cap_bytes - collected]
            sink.append(take)
            collected += len(take)


def _kill_process_group(process: subprocess.Popen[bytes]) -> int:
    """Kill the whole process group `process` leads and return a descendant's pid.

    `process` was started with `start_new_session=True`, so it leads its own
    process group; killing only `process` itself would orphan any subprocess
    it spawned. The returned pid is a process found in that group other than
    `process` itself, if one existed at the moment of the kill, else
    `process`'s own pid.
    """
    assert process.pid is not None
    try:
        process_group_id = os.getpgid(process.pid)
    except ProcessLookupError:
        process_group_id = process.pid
    members = _process_group_members(process_group_id)
    descendant_pid = next((pid for pid in members if pid != process.pid), process.pid)
    _signal_group(process_group_id, signal.SIGTERM)
    try:
        process.wait(timeout=_REAP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        _signal_group(process_group_id, signal.SIGKILL)
        try:
            process.wait(timeout=_REAP_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass
    return descendant_pid


def _signal_group(process_group_id: int, sig: int) -> None:
    try:
        os.killpg(process_group_id, sig)
    except ProcessLookupError:
        pass


def _process_group_members(process_group_id: int) -> tuple[int, ...]:
    try:
        completed = subprocess.run(
            ["ps", "-axo", "pid=,pgid="],
            check=True,
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    members: list[int] = []
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        try:
            pid, group = int(fields[0]), int(fields[1])
        except ValueError:
            continue
        if group == process_group_id:
            members.append(pid)
    return tuple(members)
