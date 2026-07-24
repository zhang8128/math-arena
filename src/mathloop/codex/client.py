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
created) bounds every phase of the turn itself: worktree creation, schema
write, process start, event reads, process wait, and patch capture. There is
no separate per-stage timeout stacked on top of it for any of those phases.

Final worktree removal is deliberately governed by its own, separate budget
(`cleanup_timeout_seconds`) rather than by however much of the turn's
deadline happens to remain. Reclamation runs strictly *after* the turn has
already concluded -- successfully, or via that same deadline already having
expired -- so it is not a stage of the turn the one-absolute-deadline rule
governs; it is what happens once the turn is already over. Giving it a fixed
floor of its own, rather than `max(0.0, deadline - now)` (which is exactly
`0.0` on every timeout path, by definition), is what keeps a timed-out turn's
worktree from being leaked on every single occurrence.
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
_DEFAULT_CLEANUP_TIMEOUT_SECONDS = 60.0
_READ_CHUNK_BYTES = 65536
_POLL_SECONDS = 0.05
_REAP_GRACE_SECONDS = 0.5


class CodexClientError(RuntimeError):
    """The Codex CLI process or its output violated the supervised contract."""


def _rebuild_codex_turn_timed_out(
    timeout_seconds: float, dispatched: bool, descendant_pid: int
) -> "CodexTurnTimedOut":
    """Reconstruct `CodexTurnTimedOut` from `__reduce__`'s picklable arguments.

    `CodexTurnTimedOut.__init__` requires two keyword-only arguments with no
    defaults; the default `BaseException.__reduce__` only round-trips
    `self.args` (here, just the formatted message string) and reconstructs
    via `cls(*args)`, which raises `TypeError` on unpickle -- exactly the
    failure this exists to prevent, since this exception crosses a real
    process boundary (a forked worker child sending it to its parent over a
    `multiprocessing.Connection`) on every real timeout.
    """
    return CodexTurnTimedOut(
        timeout_seconds, dispatched=dispatched, descendant_pid=descendant_pid
    )


class CodexTurnTimedOut(TimeoutError):
    """The turn's one absolute deadline elapsed before a terminal event arrived.

    `dispatched` is `True` whenever the Codex CLI process had already been
    started at the moment this timeout fired -- which, given `CodexClient`'s
    own control flow, is always the case for any `CodexTurnTimedOut` actually
    raised (a timeout can only fire after `subprocess.Popen` has already
    succeeded). It intentionally does not depend on whether a `turn.started`
    JSONL line was ever parsed: `on_dispatched()` -- the caller's durable
    ledger-dispatch marker, when supplied -- runs immediately before `Popen`,
    strictly earlier than any event can be read, so tying `dispatched` to the
    parser's own progress would let it read `False` for a turn the ledger
    already considers consumed and non-retryable. Naming this constant
    explicitly (rather than hardcoding `True` at each raise site, or deleting
    the field) keeps the invariant self-documenting and safe if a future
    change ever adds a raise site before `Popen`.

    `descendant_pid` is the pid of a process found in the killed Codex
    process group (a subprocess the CLI itself spawned, if any, else the CLI
    process itself), confirmed dead by the time this is raised.
    """

    def __init__(self, timeout_seconds: float, *, dispatched: bool, descendant_pid: int) -> None:
        super().__init__(f"codex turn exceeded its {timeout_seconds}s deadline")
        self.timeout_seconds = timeout_seconds
        self.dispatched = dispatched
        self.descendant_pid = descendant_pid

    def __reduce__(self) -> tuple[object, tuple[object, ...], dict[str, object]]:
        # The 3-tuple form matters: a 2-tuple (callable, args) -- what the
        # first version of this fix returned -- reconstructs the object but
        # drops everything in `self.__dict__`, including `__notes__` (the
        # only channel `CodexClient.execute`'s cleanup-failure handling uses
        # to attach evidence to an already-in-flight exception). Returning
        # `self.__dict__` as the third element makes pickle apply
        # `obj.__dict__.update(self.__dict__)` after reconstruction (the
        # default behavior when no `__setstate__` is defined), which
        # restores `__notes__` -- and redundantly, harmlessly, re-applies
        # the same `timeout_seconds`/`dispatched`/`descendant_pid` values
        # `_rebuild_codex_turn_timed_out` already set from `args`.
        return (
            _rebuild_codex_turn_timed_out,
            (self.timeout_seconds, self.dispatched, self.descendant_pid),
            self.__dict__,
        )


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
        cleanup_timeout_seconds: float = _DEFAULT_CLEANUP_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds is not None and timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_event_bytes < 1:
            raise ValueError("max_event_bytes must be a positive integer")
        if max_stderr_bytes < 1:
            raise ValueError("max_stderr_bytes must be a positive integer")
        if cleanup_timeout_seconds <= 0:
            raise ValueError("cleanup_timeout_seconds must be positive")
        self._launch_policy = launch_policy
        self._worktree_manager = worktree_manager
        self._environment_source = dict(environment if environment is not None else os.environ)
        self._timeout_seconds = timeout_seconds
        self._max_event_bytes = max_event_bytes
        self._max_stderr_bytes = max_stderr_bytes
        self._cleanup_timeout_seconds = cleanup_timeout_seconds

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
        worktree = self._worktree_manager.create(
            request.reservation.id, request.base_sha, deadline=deadline
        )
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
                # A fixed budget of its own -- not `max(0.0, deadline - now)`,
                # which is exactly 0.0 on every timeout path by definition and
                # would make cleanup fail instantly on every single timeout.
                # Reclamation happens after the turn's own deadline has
                # already been spent (successfully or not), so it is a
                # separate phase, not one more stage the turn's deadline
                # must stretch to cover.
                cleanup_deadline = time.monotonic() + self._cleanup_timeout_seconds
                self._worktree_manager.remove(worktree, deadline=cleanup_deadline)
            except (CodexWorktreeError, OSError) as cleanup_error:
                # The primary error already explains what went wrong (if
                # any); a cleanup failure on top of that must never replace
                # it as the exception the caller sees (that would mask
                # genuine evidence of a dispatched-or-not turn), but it also
                # must never be swallowed, so it rides along as a note.
                # `OSError` is caught alongside `CodexWorktreeError` because
                # `_run` can raise a raw `OSError` (e.g. the `git` binary
                # itself is unavailable), not only the wrapped error type.
                if primary_error is not None:
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
        # Kept alive for the child's *entire* lifetime, not just until Popen
        # returns: Popen only initiates fork/exec, and the child still has to
        # start and parse argv before it opens `--output-schema` -- deleting
        # the file any earlier is a real, reproducible race that starves the
        # CLI of its structured-output schema (or crashes it outright).
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
            assert process.stdout is not None
            assert process.stderr is not None
            stderr_chunks: list[bytes] = []
            stderr_thread = threading.Thread(
                target=_drain_stderr,
                args=(process.stderr, stderr_chunks, self._max_stderr_bytes),
                daemon=True,
            )
            stderr_thread.start()
            try:
                return self._stream_turn(
                    request, emit_event, process, stderr_thread, stderr_chunks, worktree,
                    deadline, timeout,
                )
            except BaseException:
                # Any exception past this point -- including one raised by a
                # caller-supplied `emit_event`, or any other bug in the loop
                # below -- must never leave the CLI running and orphaned
                # while `execute()`'s `finally` resets/removes the worktree
                # out from under it. The two specific timeout/parse-error
                # raise sites inside `_stream_turn` already do this
                # themselves (they need the live process to compute
                # `descendant_pid`); calling it again here is a cheap, safe
                # no-op for those (the process is already dead and the
                # thread already joined) and the only thing that saves every
                # *other* exception path -- a raising `emit_event`, an
                # unexpected `os.read`/`select` error, `KeyboardInterrupt`.
                _stop_process(process, stderr_thread)
                raise
        finally:
            schema_path.unlink(missing_ok=True)

    def _stream_turn[T: BaseModel](
        self,
        request: CodexRequest[T],
        emit_event: Callable[[CodexEvent], None],
        process: subprocess.Popen[bytes],
        stderr_thread: threading.Thread,
        stderr_chunks: list[bytes],
        worktree: CodexWorktree,
        deadline: float,
        timeout: float,
    ) -> CodexResponse[T]:
        parser = CodexEventParser(max_bytes=self._max_event_bytes)
        cli_version: str | None = None
        assert process.stdout is not None
        stdout_fd = process.stdout.fileno()
        buffer = bytearray()
        while True:
            try:
                line = _read_line(stdout_fd, buffer, deadline, self._max_event_bytes)
            except TimeoutError:
                descendant_pid = _stop_process(process, stderr_thread)
                raise CodexTurnTimedOut(
                    timeout, dispatched=True, descendant_pid=descendant_pid
                ) from None
            except CodexEventError as error:
                raise CodexClientError(
                    f"codex stdout stream violated the parser contract: {error}"
                ) from error
            if line is None:
                break
            try:
                event = parser.feed(line)
            except CodexEventError as error:
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
            descendant_pid = _stop_process(process, stderr_thread)
            raise CodexTurnTimedOut(timeout, dispatched=True, descendant_pid=descendant_pid)
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            descendant_pid = _stop_process(process, stderr_thread)
            raise CodexTurnTimedOut(
                timeout, dispatched=True, descendant_pid=descendant_pid
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

        patch = self._worktree_manager.diff(worktree, deadline=deadline)
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


def _read_line(fd: int, buffer: bytearray, deadline: float, max_bytes: int) -> bytes | None:
    """Return the next full line (including its trailing `\\n`), or `None` at EOF.

    Blocks only in bounded `select` polls against the absolute `deadline`, so a
    hung child never wedges the caller past its turn budget. `max_bytes` bounds
    the buffer itself -- not just completed lines -- so a child emitting one
    very large line (or a stream with no newline at all) is rejected before it
    grows unbounded in memory, rather than being buffered silently until the
    deadline. This mirrors `CodexEventParser`'s own cap so the two enforce the
    same budget from opposite ends of the same stream.
    """
    while True:
        newline_index = buffer.find(b"\n")
        if newline_index != -1:
            line = bytes(buffer[: newline_index + 1])
            del buffer[: newline_index + 1]
            return line
        if len(buffer) > max_bytes:
            raise CodexEventError(
                f"codex stdout produced a line exceeding max_bytes cap of {max_bytes} "
                "without a newline"
            )
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


def _stop_process(process: subprocess.Popen[bytes], stderr_thread: threading.Thread) -> int:
    """Kill the process group unconditionally; always (re)join the stderr thread.

    Always calls `_kill_process_group`, even when the direct child
    (`process`) has already exited: it may have spawned a descendant that is
    still alive regardless of its own exit status (e.g. it crashed, or ran
    to a nonzero exit, while what it spawned kept running) -- skipping the
    group kill whenever `process.poll()` is not `None` would silently orphan
    exactly that descendant, and would then report `process`'s own (already
    dead) pid as `descendant_pid`, making a caller's "confirmed dead" check
    on that value pass vacuously instead of ever checking the process that
    actually needed killing. `_kill_process_group` itself already tolerates
    an already-exited process cheaply (its own `process.wait()` call at the
    end returns the cached exit status immediately), so calling it
    unconditionally costs at most one extra `ps` scan and a harmless no-op
    signal, and is safe to call more than once for the same process.
    """
    descendant_pid = _kill_process_group(process)
    stderr_thread.join(timeout=_REAP_GRACE_SECONDS)
    return descendant_pid


def _kill_process_group(process: subprocess.Popen[bytes]) -> int:
    """Kill the whole process group `process` leads and return a descendant's pid.

    `process` was started with `start_new_session=True`, so it leads its own
    process group; killing only `process` itself would orphan any subprocess
    it spawned. The returned pid is a process found in that group other than
    `process` itself, if one existed at the moment of the kill, else
    `process`'s own pid.

    Escalation from `SIGTERM` to `SIGKILL` is gated on whether *any* group
    member captured in the initial snapshot is still alive -- not merely
    whether the direct child (`process`) has exited. `process.wait()` only
    ever reports on the direct child; a descendant that traps or ignores
    `SIGTERM` while the CLI itself exits promptly would otherwise survive
    indefinitely, since a direct-child-only check would see the CLI gone and
    never escalate.
    """
    assert process.pid is not None
    try:
        process_group_id = os.getpgid(process.pid)
    except ProcessLookupError:
        process_group_id = process.pid
    members = _process_group_members(process_group_id)
    descendant_pid = next((pid for pid in members if pid != process.pid), process.pid)
    other_pids = tuple(pid for pid in members if pid != process.pid)
    all_known_pids = (process.pid, *other_pids)

    _signal_group(process_group_id, signal.SIGTERM, all_known_pids)
    if _group_still_alive(process, other_pids, deadline=time.monotonic() + _REAP_GRACE_SECONDS):
        _signal_group(process_group_id, signal.SIGKILL, all_known_pids)
        _group_still_alive(process, other_pids, deadline=time.monotonic() + _REAP_GRACE_SECONDS)
    # Best-effort reap of the direct child so it never lingers as a zombie.
    # Other group members are not this process's children and cannot be
    # wait()ed on here at all -- `_group_still_alive` above is the only
    # liveness check available for them.
    try:
        process.wait(timeout=_REAP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        pass
    return descendant_pid


def _signal_group(process_group_id: int, sig: int, known_pids: tuple[int, ...]) -> None:
    try:
        os.killpg(process_group_id, sig)
    except ProcessLookupError:
        # The group no longer exists at all -- nothing left to signal.
        pass
    except PermissionError:
        # Observed in practice (not just theoretically) targeting a group
        # whose leader is our own direct child, already exited but not yet
        # reaped via `process.wait()`/`process.poll()`: `os.kill(pid, 0)`
        # still reports such a zombie as "alive" (its pid slot is still
        # occupied), but this platform's `killpg` refuses with `EPERM`
        # rather than `ESRCH` for that same, already-dead target. That is
        # the *only* case this should swallow silently -- a genuine "we may
        # not signal this group" (e.g. a setuid child, a user-namespace
        # boundary) must not be indistinguishable from "already gone",
        # since a caller relies on the group being confirmed dead once this
        # returns. Gate the swallow on a follow-up liveness check: if none
        # of the pids we were actually trying to reach are still alive, this
        # is the zombie quirk and there is truly nothing left to signal; if
        # any of them are, this was a real permission failure and must not
        # be silently absorbed.
        if any(_pid_alive(pid) for pid in known_pids):
            raise


def _group_still_alive(
    process: subprocess.Popen[bytes], other_pids: tuple[int, ...], *, deadline: float
) -> bool:
    """Poll the direct child and any other captured group members until `deadline`.

    The direct child's liveness is checked via `process.poll()`, not
    `os.kill(process.pid, 0)`: an unreaped zombie child still answers
    `kill(pid, 0)` as "alive" (its pid slot still exists) even though it has
    already exited, which would otherwise force an unnecessary -- and, for a
    group whose leader is that same zombie, `EPERM`-raising -- `SIGKILL`
    escalation every single time. `poll()` is authoritative for our own
    direct child and reaps it the moment it exits. Other group members are
    not this process's children and cannot be reaped here at all, so
    `os.kill(pid, 0)` is the best available liveness check for them.

    Returns as soon as everything is confirmed dead, without waiting out the
    rest of the budget; otherwise polls at a short fixed interval until
    `deadline` and reports whatever is true at that point.
    """
    while True:
        alive = process.poll() is None or any(_pid_alive(pid) for pid in other_pids)
        if not alive:
            return False
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(_POLL_SECONDS, remaining))


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


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
